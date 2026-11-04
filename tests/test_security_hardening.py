import io
import os
import re
import sys
from pathlib import Path
import pytest
from unittest.mock import patch, MagicMock

# Ensure backend directory is on sys.path
backend_dir = Path(__file__).resolve().parent.parent / "backend"
sys.path.insert(0, str(backend_dir))

from fastapi.testclient import TestClient
from main import app
from app.services.file_service import extract_docx, extract_pdf
from app.services.media_service import validate_media_file
from app.core.logging_config import sanitize_filename
from app.api.summarize import save_uploaded_file
from fastapi import UploadFile, HTTPException

client = TestClient(app)


def test_security_headers_present_on_fastapi_responses():
    """Verify standard HTTP security headers are injected on all backend responses."""
    resp = client.get("/health")
    assert resp.status_code == 200
    assert resp.headers.get("X-Content-Type-Options") == "nosniff"
    assert resp.headers.get("X-Frame-Options") == "DENY"
    assert resp.headers.get("Referrer-Policy") == "strict-origin-when-cross-origin"
    assert "X-Process-Time" in resp.headers
    assert "X-Request-ID" in resp.headers


def test_cors_expose_headers_configuration():
    """Verify CORS responses expose observability headers to cross-origin browsers."""
    resp = client.get(
        "/health",
        headers={"Origin": "http://localhost:3000"}
    )
    assert resp.status_code == 200
    exposed = resp.headers.get("access-control-expose-headers", "")
    assert "X-Process-Time" in exposed
    assert "X-Request-ID" in exposed


def test_filename_crlf_injection_rejected():
    """Verify filenames with CRLF characters are rejected to prevent header and log injection."""
    files = {"file": ("report.txt\r\nInjected: Header", b"Test content", "text/plain")}
    resp = client.post("/summarize", files=files, data={"length": "short", "format": "paragraph"})
    assert resp.status_code == 400
    assert "invalid characters" in resp.json()["detail"].lower()


def test_filename_null_byte_rejected():
    """Verify filenames with null bytes are rejected."""
    files = {"file": ("report.txt\x00.exe", b"Test content", "text/plain")}
    resp = client.post("/summarize", files=files, data={"length": "short", "format": "paragraph"})
    assert resp.status_code == 400
    assert "invalid characters" in resp.json()["detail"].lower()


def test_media_filename_sanitization_and_validation():
    """Verify validate_media_file rejects invalid characters and sanitizes paths."""
    # Rejects empty
    with pytest.raises(ValueError, match="No media filename"):
        validate_media_file("")

    # Rejects null bytes
    with pytest.raises(ValueError, match="invalid characters"):
        validate_media_file("audio.mp3\x00.exe")

    # Rejects CRLF
    with pytest.raises(ValueError, match="invalid characters"):
        validate_media_file("audio.mp3\r\n")

    # Rejects unsupported format
    with pytest.raises(ValueError, match="Unsupported media format"):
        validate_media_file("video.exe")

    # Normalizes Windows backslashes and succeeds for valid extension
    ext = validate_media_file(r"..\..\recordings\interview.mp4")
    assert ext == ".mp4"


def test_path_traversal_filename_normalized_safely():
    """Verify path traversal characters in upload filename are normalized to UUID and base extension."""
    with patch("app.api.summarize.summarize_text", return_value="Mock summary"):
        files = {"file": ("../../../../etc/passwd.txt", b"Safe text payload", "text/plain")}
        resp = client.post("/summarize", files=files, data={"length": "short", "format": "paragraph"})
        assert resp.status_code == 200
        assert resp.json()["summary"] == "Mock summary"


def test_docx_error_masks_internal_filesystem_paths():
    """Verify corrupt DOCX parsing error does not leak absolute filesystem paths."""
    import tempfile
    with tempfile.NamedTemporaryFile(suffix=".docx", delete=False) as tmp:
        tmp.write(b"not a real zip archive")
        tmp_path = tmp.name

    try:
        with pytest.raises(ValueError) as excinfo:
            extract_docx(tmp_path)
        err_msg = str(excinfo.value)
        # Verify the actual temporary path is NOT in the error message
        assert tmp_path not in err_msg
        assert "<document>" in err_msg
    finally:
        if os.path.exists(tmp_path):
            os.remove(tmp_path)


def test_save_uploaded_file_masks_internal_storage_paths():
    """Verify unexpected storage exceptions in save_uploaded_file do not leak internal directory paths."""
    mock_upload = MagicMock(spec=UploadFile)
    mock_upload.filename = "valid.txt"
    mock_upload.file = MagicMock()
    mock_upload.file.read.side_effect = IOError("Disk I/O error at D:\\Secret\\Path\\uploads\\123.txt")

    with pytest.raises(HTTPException) as excinfo:
        save_uploaded_file(mock_upload)

    assert excinfo.value.status_code == 500
    assert "D:\\Secret\\Path" not in excinfo.value.detail
    assert "internal server error" in excinfo.value.detail.lower()


def test_sanitize_filename_strips_control_characters_and_paths():
    """Verify sanitize_filename strips control chars, CRLF, and extracts basename."""
    dirty_name = "../../uploads/quarterly\r\n_report\x00.pdf"
    safe = sanitize_filename(dirty_name)
    assert "/" not in safe
    assert "\\" not in safe
    assert "\r" not in safe
    assert "\n" not in safe
    assert "\x00" not in safe
    assert safe == "quarterly_report.pdf"


def test_missing_groq_api_key_fails_safely():
    """Verify missing GROQ_API_KEY produces controlled RuntimeError without leaking internals."""
    from app.services import groq_service
    with patch.object(groq_service, "GROQ_API_KEY", None), patch.dict(os.environ, {"GROQ_API_KEY": ""}):
        with pytest.raises(RuntimeError) as excinfo:
            groq_service._client = None
            groq_service.get_groq_client()
        assert "GROQ_API_KEY is not configured" in str(excinfo.value)

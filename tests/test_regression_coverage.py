import os
import io
import sys
import tempfile
import subprocess
from pathlib import Path
from unittest.mock import patch, MagicMock

# Ensure backend directory is in path
backend_dir = Path(__file__).resolve().parent.parent / "backend"
sys.path.insert(0, str(backend_dir))

import pytest
from fastapi.testclient import TestClient
from docx import Document

from main import app
from app.core.config import UPLOAD_DIR
from app.services.file_service import extract_text, extract_txt, extract_pdf, extract_docx
from app.services.media_service import extract_audio, transcribe_media, transcribe_audio
from app.services.groq_service import compare_documents, update_summary

client = TestClient(app)


# ============================================================
# 1. TEMPORARY FILE CLEANUP ON FAILURE ACROSS ENDPOINTS
# ============================================================

def test_compare_endpoint_cleans_up_files_on_llm_failure():
    """Verify both file_a and file_b temporary uploads are unlinked if LLM fails."""
    initial_files = set(os.listdir(UPLOAD_DIR))

    with patch(
        "app.services.groq_service._call_groq_chat",
        side_effect=RuntimeError("Groq Cloud provider error during comparison")
    ):
        res = client.post(
            "/compare",
            files={
                "file_a": ("doc_a.txt", b"Document A content.", "text/plain"),
                "file_b": ("doc_b.txt", b"Document B content differs.", "text/plain"),
            }
        )
        assert res.status_code == 500

    # Ensure no leftover files in uploads directory
    after_files = set(os.listdir(UPLOAD_DIR))
    leftovers = after_files - initial_files
    assert len(leftovers) == 0, f"Temporary files were leaked in UPLOAD_DIR: {leftovers}"


def test_summarize_multiple_cleans_up_files_on_extraction_error():
    """Verify all uploaded files in a batch are unlinked if an extraction error occurs."""
    initial_files = set(os.listdir(UPLOAD_DIR))

    # File 2 is corrupted / empty
    files = [
        ("files", ("valid.txt", b"Valid document content.", "text/plain")),
        ("files", ("corrupt.pdf", b"Not a real PDF file", "application/pdf")),
    ]
    res = client.post("/summarize-multiple", files=files)
    assert res.status_code == 400

    after_files = set(os.listdir(UPLOAD_DIR))
    leftovers = after_files - initial_files
    assert len(leftovers) == 0, f"Temporary files were leaked in UPLOAD_DIR: {leftovers}"


def test_summarize_media_cleans_up_file_on_transcription_failure():
    """Verify temporary media file is unlinked from uploads if transcription raises error."""
    initial_files = set(os.listdir(UPLOAD_DIR))

    with patch(
        "app.api.summarize.transcribe_media",
        side_effect=RuntimeError("Whisper transcription internal failure")
    ):
        res = client.post(
            "/summarize-media",
            files={"file": ("test.wav", b"RIFF dummy wav data", "audio/wav")},
            data={"length": "short", "format": "paragraph"}
        )
        assert res.status_code == 500

    after_files = set(os.listdir(UPLOAD_DIR))
    leftovers = after_files - initial_files
    assert len(leftovers) == 0, f"Temporary media file leaked in UPLOAD_DIR: {leftovers}"


# ============================================================
# 2. DOCUMENT EXTRACTION RESILIENCE (DOCX, PDF, ENCODINGS)
# ============================================================

def test_extract_docx_paragraphs_and_tables():
    """Verify extract_docx extracts both narrative paragraphs and structured tables with ' | ' delimiters."""
    doc = Document()
    doc.add_paragraph("First narrative paragraph in DOCX.")
    doc.add_paragraph("Second narrative paragraph detailing requirements.")

    table = doc.add_table(rows=2, cols=3)
    table.cell(0, 0).text = "Service"
    table.cell(0, 1).text = "Protocol"
    table.cell(0, 2).text = "Latency"
    table.cell(1, 0).text = "Groq Cloud"
    table.cell(1, 1).text = "HTTPS"
    table.cell(1, 2).text = "42ms"

    buf = io.BytesIO()
    doc.save(buf)

    with tempfile.NamedTemporaryFile(suffix=".docx", delete=False) as f:
        f.write(buf.getvalue())
        temp_path = f.name

    try:
        extracted = extract_text(temp_path)
        assert "First narrative paragraph in DOCX." in extracted
        assert "Second narrative paragraph detailing requirements." in extracted
        assert "Service | Protocol | Latency" in extracted
        assert "Groq Cloud | HTTPS | 42ms" in extracted
    finally:
        if os.path.exists(temp_path):
            os.remove(temp_path)


def test_extract_txt_encodings_utf8_bom_and_latin1():
    """Verify extract_txt successfully parses UTF-8 with BOM and Latin-1 encoded files."""
    # 1. UTF-8 with BOM
    bom_content = "\ufeffTitle with UTF-8 BOM marker\nSecond line with valid data."
    with tempfile.NamedTemporaryFile(suffix=".txt", delete=False, mode="w", encoding="utf-8-sig") as f:
        f.write(bom_content)
        bom_path = f.name

    try:
        extracted = extract_text(bom_path)
        assert "Title with UTF-8 BOM marker" in extracted
        assert "Second line with valid data." in extracted
    finally:
        if os.path.exists(bom_path):
            os.remove(bom_path)

    # 2. Latin-1 / ANSI encoding with accented characters
    latin1_text = "Café au lait costs £4.50 and François signed the résumé."
    with tempfile.NamedTemporaryFile(suffix=".txt", delete=False, mode="wb") as f:
        f.write(latin1_text.encode("latin-1"))
        latin1_path = f.name

    try:
        extracted = extract_text(latin1_path)
        assert "Café au lait" in extracted
        assert "François" in extracted
    finally:
        if os.path.exists(latin1_path):
            os.remove(latin1_path)


def test_extract_pdf_encrypted_raises_value_error():
    """Verify extract_pdf detects password-protected or encrypted PDFs and raises ValueError."""
    mock_doc = MagicMock()
    mock_doc.is_encrypted = True

    with patch("app.services.file_service.fitz.open", return_value=mock_doc):
        with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as f:
            f.write(b"%PDF-1.4 dummy bytes")
            pdf_path = f.name

        try:
            with pytest.raises(ValueError) as exc_info:
                extract_pdf(pdf_path)
            assert "password-protected or encrypted" in str(exc_info.value).lower()
        finally:
            if os.path.exists(pdf_path):
                os.remove(pdf_path)


# ============================================================
# 3. MEDIA PIPELINE ROUTING AND FFMPEG TIMEOUT PROTECTION
# ============================================================

def test_transcribe_media_video_vs_audio_routing():
    """Verify video formats invoke extract_audio, while native audio files bypass FFmpeg extraction."""
    # Case A: Video format (.mp4) -> must invoke extract_audio
    with patch("app.services.media_service.extract_audio", return_value="temp.wav") as mock_extract, \
         patch("app.services.media_service.transcribe_audio", return_value="Video transcript content.") as mock_transcribe, \
         patch("os.path.exists", return_value=False):
        res = transcribe_media("recording.mp4")
        assert res == "Video transcript content."
        mock_extract.assert_called_once_with("recording.mp4")
        mock_transcribe.assert_called_once_with("temp.wav")

    # Case B: Audio format (.mp3) -> must directly transcribe without extract_audio
    with patch("app.services.media_service.extract_audio") as mock_extract, \
         patch("app.services.media_service.transcribe_audio", return_value="Audio transcript content.") as mock_transcribe:
        res = transcribe_media("podcast.mp3")
        assert res == "Audio transcript content."
        assert not mock_extract.called, "extract_audio should not be called for direct audio files"
        mock_transcribe.assert_called_once_with("podcast.mp3")


def test_extract_audio_ffmpeg_timeout_cleanup():
    """Verify FFmpeg subprocess timeout unlinks temporary wav and raises clear RuntimeError."""
    with patch("subprocess.run", side_effect=subprocess.TimeoutExpired(cmd="ffmpeg", timeout=120)), \
         patch("os.path.exists", return_value=True):
        with tempfile.NamedTemporaryFile(suffix=".mp4", delete=False) as f:
            f.write(b"dummy mp4")
            dummy_mp4 = f.name

        try:
            with pytest.raises(RuntimeError) as exc_info:
                extract_audio(dummy_mp4)
            assert "timed out after 120 seconds" in str(exc_info.value)
        finally:
            if os.path.exists(dummy_mp4):
                os.remove(dummy_mp4)


# ============================================================
# 4. OBSERVABILITY: X-REQUEST-ID TRACE HEADERS
# ============================================================

def test_x_request_id_uniqueness_across_requests():
    """Verify successive requests receive distinct, unique X-Request-ID headers."""
    request_ids = []
    for _ in range(5):
        res = client.get("/health")
        assert res.status_code == 200
        req_id = res.headers.get("x-request-id")
        assert req_id is not None
        request_ids.append(req_id)

    # All 5 IDs should be distinct
    assert len(set(request_ids)) == 5, f"Collision detected in generated request IDs: {request_ids}"


def test_x_request_id_preserved_on_client_errors():
    """Verify inbound X-Request-ID header is echoed on 400 and 422 error responses."""
    # 400 Bad Request (empty file)
    trace_400 = "client-trace-400-test"
    res_400 = client.post(
        "/summarize",
        files={"file": ("empty.txt", b"", "text/plain")},
        headers={"X-Request-ID": trace_400}
    )
    assert res_400.status_code == 400
    assert res_400.headers.get("x-request-id") == trace_400

    # 422 Unprocessable Entity (missing file field)
    trace_422 = "client-trace-422-test"
    res_422 = client.post(
        "/summarize",
        data={"length": "medium"},
        headers={"X-Request-ID": trace_422}
    )
    assert res_422.status_code == 422
    assert res_422.headers.get("x-request-id") == trace_422


# ============================================================
# 5. FAST-PATH COMPARISON & DELTA SUMMARY NORMALIZATION
# ============================================================

def test_compare_fast_path_whitespace_normalization():
    """Verify comparing documents differing only in leading/trailing whitespace takes fast path."""
    text_a = "Enterprise microservices architecture with Redis caching."
    text_b = "   \n\n Enterprise microservices architecture with Redis caching.   \t\r\n"

    with patch("app.services.groq_service._call_groq_chat") as mock_chat:
        report = compare_documents(text_a, text_b)
        assert "identical" in report.lower()
        assert "Differences:\nNone identified." in report
        assert not mock_chat.called, "Should take fast path without invoking LLM"


def test_update_summary_fast_path_whitespace_normalization():
    """Verify updating summary with identical text differing only in whitespace takes fast path."""
    prev_summary = "System throughput scaled to 15,000 requests per second."
    curr_text = "   System throughput scaled to 15,000 requests per second.  \n"

    with patch("app.services.groq_service._call_groq_chat") as mock_chat:
        report = update_summary(prev_summary, curr_text)
        assert "identical" in report.lower()
        assert "New Information:\nNone identified." in report
        assert "Changed Information:\nNone identified." in report
        assert not mock_chat.called, "Should take fast path without invoking LLM"

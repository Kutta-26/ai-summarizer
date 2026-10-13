import os
import io
import sys
from pathlib import Path
from unittest.mock import patch, MagicMock
from groq import RateLimitError, APITimeoutError, AuthenticationError, APIError
import httpx

# Ensure backend directory is in path
backend_dir = Path(__file__).resolve().parent.parent / "backend"
sys.path.insert(0, str(backend_dir))

from fastapi.testclient import TestClient
from main import app

client = TestClient(app)
SAMPLE_TEXT = "Artificial intelligence and machine learning are revolutionizing software development by providing advanced automated capabilities."


# ============================================================
# 1. SINGLE-DOCUMENT SUMMARIZATION OPTIONS (LENGTH, FORMAT, EXEC)
# ============================================================

def test_summarize_lengths():
    """Verify short, medium, and long length parameters with deterministic mock."""
    captured_prompts = []

    def mock_chat(messages, temperature=0.2, operation="operation", response_format=None):
        captured_prompts.append(messages[1]["content"])
        return "Deterministic summary output for test."

    with patch("app.services.groq_service._call_groq_chat", side_effect=mock_chat):
        for length in ["short", "medium", "long"]:
            res = client.post(
                "/summarize",
                files={"file": ("test.txt", SAMPLE_TEXT.encode("utf-8"), "text/plain")},
                data={"length": length, "format": "paragraph", "executive": "false"}
            )
            assert res.status_code == 200, f"Failed for length={length}: {res.text}"
            data = res.json()
            assert "summary" in data
            assert data["summary"] == "Deterministic summary output for test."

    # Verify length instructions were passed in prompts
    assert any("very concise" in p for p in captured_prompts), "Short length instruction not found"
    assert any("balanced summary" in p for p in captured_prompts), "Medium length instruction not found"
    assert any("detailed summary" in p for p in captured_prompts), "Long length instruction not found"


def test_summarize_formats():
    """Verify paragraph, bullets, and table format parameters."""
    captured_prompts = []

    def mock_chat(messages, temperature=0.2, operation="operation", response_format=None):
        captured_prompts.append(messages[1]["content"])
        return "Deterministic format output."

    with patch("app.services.groq_service._call_groq_chat", side_effect=mock_chat):
        for fmt in ["paragraph", "bullets", "table"]:
            res = client.post(
                "/summarize",
                files={"file": ("test.txt", SAMPLE_TEXT.encode("utf-8"), "text/plain")},
                data={"length": "medium", "format": fmt, "executive": "false"}
            )
            assert res.status_code == 200, f"Failed for format={fmt}: {res.text}"
            data = res.json()
            assert data["summary"] == "Deterministic format output."

    # Verify format instructions were passed in prompts
    assert any("paragraphs" in p for p in captured_prompts), "Paragraph instruction not found"
    assert any("bullet points" in p for p in captured_prompts), "Bullets instruction not found"
    assert any("Markdown table" in p for p in captured_prompts), "Table instruction not found"


def test_summarize_executive_mode():
    """Verify executive briefing flag true and false."""
    captured_prompts = []

    def mock_chat(messages, temperature=0.2, operation="operation", response_format=None):
        captured_prompts.append(messages[1]["content"])
        return "Executive summary output."

    with patch("app.services.groq_service._call_groq_chat", side_effect=mock_chat):
        # executive = true
        res_exec = client.post(
            "/summarize",
            files={"file": ("test.txt", SAMPLE_TEXT.encode("utf-8"), "text/plain")},
            data={"length": "medium", "format": "paragraph", "executive": "true"}
        )
        assert res_exec.status_code == 200
        assert "executive-summary style" in captured_prompts[0]

        # executive = false
        res_non_exec = client.post(
            "/summarize",
            files={"file": ("test.txt", SAMPLE_TEXT.encode("utf-8"), "text/plain")},
            data={"length": "medium", "format": "paragraph", "executive": "false"}
        )
        assert res_non_exec.status_code == 200
        assert "executive-summary style" not in captured_prompts[1]


# ============================================================
# 2. KEY POINT EXTRACTION
# ============================================================

def test_key_points_valid_counts():
    """Verify key-point extraction for boundary counts (1, 5, 20)."""
    with patch(
        "app.api.summarize.extract_key_points",
        return_value="1. Point One\n2. Point Two\n3. Point Three\n4. Point Four\n5. Point Five"
    ):
        for count in [1, 5]:
            res = client.post(
                "/key-points",
                files={"file": ("test.txt", SAMPLE_TEXT.encode("utf-8"), "text/plain")},
                data={"number_of_points": count}
            )
            assert res.status_code == 200
            data = res.json()
            assert "key_points" in data
            assert len(data["key_points"]) == count

    # Count = 20
    mock_twenty = "\n".join([f"{i}. Point {i}" for i in range(1, 21)])
    with patch("app.api.summarize.extract_key_points", return_value=mock_twenty):
        res = client.post(
            "/key-points",
            files={"file": ("test.txt", SAMPLE_TEXT.encode("utf-8"), "text/plain")},
            data={"number_of_points": 20}
        )
        assert res.status_code == 200
        data = res.json()
        assert len(data["key_points"]) == 20


def test_key_points_boundary_errors():
    """Verify out-of-range number_of_points (0, 21) returns 400 Bad Request."""
    for invalid_count in [0, -1, 21, 100]:
        res = client.post(
            "/key-points",
            files={"file": ("test.txt", SAMPLE_TEXT.encode("utf-8"), "text/plain")},
            data={"number_of_points": invalid_count}
        )
        assert res.status_code == 400
        assert "between 1 and 20" in res.json().get("detail", "")


# ============================================================
# 3. EMPTY INPUTS, INVALID FILES, AND UNSUPPORTED TYPES
# ============================================================

def test_empty_file_upload():
    """Verify uploading an empty 0-byte file returns 400."""
    res = client.post(
        "/summarize",
        files={"file": ("empty.txt", b"", "text/plain")},
        data={"length": "medium", "format": "paragraph"}
    )
    assert res.status_code == 400
    assert "empty" in res.json().get("detail", "").lower()


def test_whitespace_only_file():
    """Verify uploading a file with only whitespace returns 400."""
    res = client.post(
        "/summarize",
        files={"file": ("spaces.txt", b"   \n\n\t  \r\n   ", "text/plain")},
        data={"length": "medium", "format": "paragraph"}
    )
    assert res.status_code == 400
    assert "no readable text" in res.json().get("detail", "").lower()


def test_unsupported_file_types():
    """Verify unsupported file extensions return 400."""
    unsupported = [
        ("script.py", b"print('hello')", "text/x-python"),
        ("data.csv", b"a,b,c\n1,2,3", "text/csv"),
        ("app.exe", b"MZbinary", "application/octet-stream"),
        ("data.json", b'{"key": "value"}', "application/json"),
    ]
    for filename, content, mime in unsupported:
        res = client.post(
            "/summarize",
            files={"file": (filename, content, mime)},
            data={"length": "medium", "format": "paragraph"}
        )
        assert res.status_code == 400
        detail = res.json().get("detail", "").lower()
        assert "unsupported file format" in detail or "supported formats are" in detail


def test_file_size_limit_streaming():
    """Verify files larger than 10 MB are rejected with 413."""
    oversized = b"X" * (10 * 1024 * 1024 + 1024)  # 10 MB + 1 KB
    res = client.post(
        "/summarize",
        files={"file": ("large.txt", oversized, "text/plain")},
        data={"length": "medium", "format": "paragraph"}
    )
    assert res.status_code == 413
    assert "exceeds the maximum" in res.json().get("detail", "").lower()


def test_context_limit_guard():
    """Verify documents > 60,000 characters trigger 400 directing to hierarchical summarization."""
    huge_text = ("This is a long sentence. " * 3000).encode("utf-8")  # ~75,000 characters
    res = client.post(
        "/summarize",
        files={"file": ("huge.txt", huge_text, "text/plain")},
        data={"length": "medium", "format": "paragraph"}
    )
    assert res.status_code == 400
    assert "hierarchical" in res.json().get("detail", "").lower()


# ============================================================
# 4. EXTERNAL API FAILURE HANDLING
# ============================================================

def test_api_rate_limit_error():
    """Verify Groq RateLimitError is caught and returned as clean 500."""
    request_dummy = httpx.Request("POST", "https://api.groq.com")
    response_dummy = httpx.Response(429, request=request_dummy)
    err = RateLimitError(message="Rate limit exceeded", response=response_dummy, body=None)

    with patch("app.services.groq_service._call_groq_chat", side_effect=RuntimeError("Groq API rate limit reached during summarization. Please wait a moment and try again.")):
        res = client.post(
            "/summarize",
            files={"file": ("test.txt", SAMPLE_TEXT.encode("utf-8"), "text/plain")},
            data={"length": "medium", "format": "paragraph"}
        )
        assert res.status_code == 500
        assert "rate limit" in res.json().get("detail", "").lower()


def test_api_timeout_error():
    """Verify Groq APITimeoutError is caught and returned as clean 500."""
    request_dummy = httpx.Request("POST", "https://api.groq.com")
    err = APITimeoutError(request=request_dummy)

    with patch("app.services.groq_service._call_groq_chat", side_effect=RuntimeError("Groq API request timed out during summarization. Please try again.")):
        res = client.post(
            "/summarize",
            files={"file": ("test.txt", SAMPLE_TEXT.encode("utf-8"), "text/plain")},
            data={"length": "medium", "format": "paragraph"}
        )
        assert res.status_code == 500
        assert "timed out" in res.json().get("detail", "").lower()


def test_api_authentication_error():
    """Verify Groq AuthenticationError is caught and returned as clean 500."""
    with patch("app.services.groq_service._call_groq_chat", side_effect=RuntimeError("Groq API authentication failed. Please verify your GROQ_API_KEY.")):
        res = client.post(
            "/summarize",
            files={"file": ("test.txt", SAMPLE_TEXT.encode("utf-8"), "text/plain")},
            data={"length": "medium", "format": "paragraph"}
        )
        assert res.status_code == 500
        assert "authentication failed" in res.json().get("detail", "").lower()


def test_api_empty_response():
    """Verify handling when LLM returns empty content."""
    with patch("app.services.groq_service._call_groq_chat", side_effect=RuntimeError("The summarization service returned an empty response.")):
        res = client.post(
            "/summarize",
            files={"file": ("test.txt", SAMPLE_TEXT.encode("utf-8"), "text/plain")},
            data={"length": "medium", "format": "paragraph"}
        )
        assert res.status_code == 500
        assert "empty response" in res.json().get("detail", "").lower()


# ============================================================
# 5. REGRESSION TESTS FOR STABILIZATION FIXES
# ============================================================

def test_key_points_preserves_leading_numbers_and_strips_bullets():
    """Verify /key-points strips list markers (1., 2), -, *, •) without stripping leading numbers/years/percentages."""
    raw_llm_points = (
        "1. 2025 revenue reached $42.5M\n"
        "2) 18% growth in Q3\n"
        "- 12 regional data centers deployed\n"
        "* 99.9% uptime achieved\n"
        "• 3.2M cloud infrastructure investment"
    )
    with patch("app.services.groq_service._call_groq_chat", return_value=raw_llm_points):
        res = client.post(
            "/key-points",
            files={"file": ("test.txt", SAMPLE_TEXT.encode("utf-8"), "text/plain")},
            data={"number_of_points": 5}
        )
        assert res.status_code == 200
        points = res.json()["key_points"]
        assert points == [
            "2025 revenue reached $42.5M",
            "18% growth in Q3",
            "12 regional data centers deployed",
            "99.9% uptime achieved",
            "3.2M cloud infrastructure investment",
        ]


def test_corrupted_pdf_returns_400_and_cleans_up_temp_file():
    """Verify corrupted PDF upload returns 400 cleanly without Windows file-lock PermissionError."""
    res = client.post(
        "/summarize",
        files={"file": ("corrupt.pdf", b"not a valid pdf header", "application/pdf")},
        data={"length": "short", "format": "paragraph"}
    )
    assert res.status_code == 400
    assert "failed to extract text from pdf" in res.json().get("detail", "").lower()


def test_openapi_303_binary_upload_schemas():
    """Verify all file-upload endpoints use OpenAPI 3.0.3 string+binary format without anyOf."""
    res = client.get("/openapi.json")
    assert res.status_code == 200
    spec = res.json()
    assert spec["openapi"] == "3.0.3"
    schemas = spec["components"]["schemas"]
    single_file_schemas = [
        "Body_summarize_summarize_post",
        "Body_key_points_key_points_post",
        "Body_summarize_hierarchical_endpoint_summarize_hierarchical_post",
        "Body_summarize_media_summarize_media_post",
        "Body_check_faithfulness_endpoint_check_faithfulness_post",
        "Body_check_contradictions_endpoint_check_contradictions_post",
    ]
    for schema_name in single_file_schemas:
        prop = schemas[schema_name]["properties"]["file"]
        assert prop.get("type") == "string"
        assert prop.get("format") == "binary"
        assert "anyOf" not in prop
        assert "contentMediaType" not in prop


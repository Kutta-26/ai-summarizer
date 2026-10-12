import os
import io
import sys
from pathlib import Path
from unittest.mock import patch, MagicMock

# Ensure backend directory is in path
backend_dir = Path(__file__).resolve().parent.parent / "backend"
sys.path.insert(0, str(backend_dir))

from fastapi.testclient import TestClient
from main import app
from app.services.youtube_service import extract_video_id, fetch_youtube_transcript
from app.services.media_service import validate_media_file
from app.services.groq_service import chunk_text

client = TestClient(app)


# ============================================================
# 1. MULTI-DOCUMENT SUMMARIZATION
# ============================================================

def test_multi_document_summarization():
    """Verify multi-document cross-synthesis endpoint."""
    captured_messages = []

    def mock_chat(messages, temperature=0.2, operation="operation", response_format=None):
        captured_messages.append(messages[1]["content"])
        return "Consolidated summary across doc1 and doc2."

    with patch("app.services.groq_service._call_groq_chat", side_effect=mock_chat):
        res = client.post(
            "/summarize-multiple",
            files=[
                ("files", ("doc1.txt", b"First document discusses cloud architecture.", "text/plain")),
                ("files", ("doc2.txt", b"Second document covers database optimization.", "text/plain"))
            ],
            data={"length": "medium", "format": "bullets", "executive": "false"}
        )
        assert res.status_code == 200
        data = res.json()
        assert "summary" in data
        assert "Consolidated summary" in data["summary"]

    # Verify document delimiters in prompt
    prompt = captured_messages[0]
    assert "--- Document: doc1.txt ---" in prompt
    assert "--- Document: doc2.txt ---" in prompt


def test_multi_document_empty_files_rejected():
    """Verify empty file array returns 422 or 400."""
    res = client.post(
        "/summarize-multiple",
        data={"length": "medium", "format": "paragraph"}
    )
    assert res.status_code == 422


# ============================================================
# 2. DOCUMENT COMPARISON
# ============================================================

def test_document_comparison():
    """Verify side-by-side comparison of two documents."""
    captured_messages = []

    def mock_chat(messages, temperature=0.2, operation="operation", response_format=None):
        captured_messages.append(messages[1]["content"])
        return (
            "Document A Summary: Feature X\n\n"
            "Document B Summary: Feature Y\n\n"
            "Similarities: Both are web frameworks\n\n"
            "Differences: Performance and syntax differ"
        )

    with patch("app.services.groq_service._call_groq_chat", side_effect=mock_chat):
        res = client.post(
            "/compare",
            files={
                "file_a": ("framework_a.txt", b"Framework A uses synchronous threads.", "text/plain"),
                "file_b": ("framework_b.txt", b"Framework B uses an async event loop.", "text/plain")
            }
        )
        assert res.status_code == 200
        data = res.json()
        assert "summary" in data
        assert "Similarities" in data["summary"]

    prompt = captured_messages[0]
    assert "DOCUMENT A" in prompt
    assert "DOCUMENT B" in prompt


# ============================================================
# 3. UPDATE / DELTA SUMMARY
# ============================================================

def test_update_summary_delta_detection():
    """Verify update summary endpoint detects additions, changes, and removals."""
    captured_messages = []

    def mock_chat(messages, temperature=0.2, operation="operation", response_format=None):
        captured_messages.append(messages[1]["content"])
        return (
            "New Information:\n- Added GraphQL support.\n\n"
            "Changed Information:\n- Deprecated Python 3.8 support.\n\n"
            "Removed Information:\nNone identified.\n\n"
            "Unchanged Information:\n- Core REST architecture remains active."
        )

    with patch("app.services.groq_service._call_groq_chat", side_effect=mock_chat):
        res = client.post(
            "/update-summary",
            data={
                "previous_summary": "Version 1.0 supports REST API and Python 3.8.",
                "current_text": "Version 2.0 supports REST API, GraphQL, and Python 3.11+. Python 3.8 is deprecated."
            }
        )
        assert res.status_code == 200
        data = res.json()
        assert "summary" in data
        assert "New Information" in data["summary"]


# ============================================================
# 4. HIERARCHICAL SUMMARIZATION & CHUNKING
# ============================================================

def test_chunking_heading_awareness():
    """Verify chunk_text splits cleanly along headings and paragraphs."""
    sample_text = (
        "# Introduction\n\n"
        "This is the introductory section explaining the project scope.\n\n"
        "# Methodology\n\n"
        "Here are the research methods and data collection procedures.\n\n"
        "# Results\n\n"
        "Here are the final numerical results and benchmarks."
    )
    chunks = chunk_text(sample_text, chunk_size=100)
    assert len(chunks) >= 3
    # Check that chunks preserve section content
    assert any("Introduction" in c for c in chunks)
    assert any("Methodology" in c for c in chunks)
    assert any("Results" in c for c in chunks)


def test_hierarchical_endpoint_enrichment():
    """Verify hierarchical summarization includes importance, redundancy, faithfulness, and contradictions."""
    long_doc = (
        "# Chapter 1: Introduction\n"
        "Revenue grew by 25% to $4.2 million in Q4 2025. " * 15 + "\n\n"
        "# Chapter 2: Technical Architecture\n"
        "The distributed cluster deployed 12 nodes across 3 availability zones. " * 15 + "\n\n"
        "# Chapter 3: Duplicate Summary\n"
        "Revenue grew by 25% to $4.2 million in Q4 2025. " * 15
    )

    with patch(
        "app.services.groq_service._call_groq_chat",
        return_value="Unified final master summary of the document."
    ):
        res = client.post(
            "/summarize-hierarchical",
            files={"file": ("long_doc.txt", long_doc.encode("utf-8"), "text/plain")},
            data={"chunk_size": 1500, "length": "medium", "format": "paragraph"}
        )
        assert res.status_code == 200
        data = res.json()

        # Check required fields
        assert "final_summary" in data
        assert "section_summaries" in data
        assert "total_sections" in data
        assert "redundant_sections_count" in data
        assert "faithfulness" in data
        assert "contradictions" in data

        # Check section summary attributes
        for sec in data["section_summaries"]:
            assert "section_index" in sec
            assert "summary" in sec
            assert "importance_score" in sec
            assert "is_redundant" in sec

        # Check faithfulness schema
        assert "faithfulness_score" in data["faithfulness"]
        assert "status" in data["faithfulness"]

        # Check contradiction schema
        assert "has_contradiction" in data["contradictions"]
        assert "status" in data["contradictions"]


# ============================================================
# 5. MEDIA WORKFLOW (VALIDATION & MOCKED TRANSCRIBE)
# ============================================================

def test_media_file_validation():
    """Verify validate_media_file accepts allowed audio/video and rejects invalid."""
    valid_exts = ["song.mp3", "audio.wav", "track.m4a", "video.mp4", "movie.mkv", "clip.mov", "stream.webm", "file.avi", "lossless.flac", "audio.ogg"]
    for fname in valid_exts:
        assert validate_media_file(fname) is not None

    invalid_exts = ["doc.pdf", "text.txt", "doc.docx", "script.py", "app.exe"]
    for fname in invalid_exts:
        try:
            validate_media_file(fname)
            assert False, f"Should have failed for {fname}"
        except ValueError:
            pass


def test_summarize_media_endpoint_mocked():
    """Verify /summarize-media executes audio pipeline and Groq synthesis."""
    with patch("app.api.summarize.transcribe_media", return_value="The conference keynote discussed AI engineering advancements."), \
         patch("app.api.summarize.summarize_text", return_value="Keynote summary: AI engineering advancements were discussed."):
        res = client.post(
            "/summarize-media",
            files={"file": ("speech.wav", b"RIFF dummy wav binary data", "audio/wav")},
            data={"length": "short", "format": "paragraph"}
        )
        assert res.status_code == 200
        data = res.json()
        assert "summary" in data
        assert "Keynote summary" in data["summary"]


# ============================================================
# 6. YOUTUBE WORKFLOW (VIDEO ID EXTRACTION & MOCKED RETRIEVAL)
# ============================================================

def test_youtube_video_id_extraction():
    """Verify extract_video_id extracts 11-char ID from all supported URL patterns."""
    test_urls = [
        ("https://www.youtube.com/watch?v=dQw4w9WgXcQ", "dQw4w9WgXcQ"),
        ("https://youtu.be/dQw4w9WgXcQ", "dQw4w9WgXcQ"),
        ("https://www.youtube.com/embed/dQw4w9WgXcQ", "dQw4w9WgXcQ"),
        ("https://www.youtube.com/v/dQw4w9WgXcQ", "dQw4w9WgXcQ"),
        ("https://www.youtube.com/shorts/dQw4w9WgXcQ", "dQw4w9WgXcQ"),
        ("https://www.youtube.com/watch?feature=shared&v=dQw4w9WgXcQ", "dQw4w9WgXcQ"),
        ("dQw4w9WgXcQ", "dQw4w9WgXcQ"),
    ]
    for url, expected_id in test_urls:
        assert extract_video_id(url) == expected_id, f"Failed extracting video ID from {url}"


def test_youtube_summarization_mocked():
    """Verify /summarize-youtube extracts transcript and synthesizes summary."""
    with patch(
        "app.api.summarize.fetch_youtube_transcript",
        return_value="Welcome to this tutorial on building scalable web APIs with FastAPI."
    ), patch(
        "app.api.summarize.summarize_text",
        return_value="This video covers building scalable web APIs using FastAPI."
    ):
        res = client.post(
            "/summarize-youtube",
            data={"url": "https://www.youtube.com/watch?v=dQw4w9WgXcQ", "length": "short", "format": "paragraph"}
        )
        assert res.status_code == 200
        data = res.json()
        assert "summary" in data
        assert "FastAPI" in data["summary"]

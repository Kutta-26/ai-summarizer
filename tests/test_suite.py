import os
import sys
import time
from pathlib import Path
from fastapi.testclient import TestClient

# Ensure backend is on sys.path
backend_dir = Path(__file__).resolve().parent.parent / "backend"
sys.path.insert(0, str(backend_dir))

from main import app
from app.services.file_service import extract_text, extract_pdf, extract_docx
from app.services.importance_service import score_importance
from app.services.redundancy_service import detect_and_filter_redundancy, check_pairwise_redundancy
from app.services.faithfulness_service import check_faithfulness

client = TestClient(app)
root_dir = Path(__file__).resolve().parent.parent


def run_tests():
    results = []

    def log_result(name, passed, detail=""):
        status = "PASS" if passed else "FAIL"
        results.append((name, status, detail))
        print(f"[{status}] {name} {f'- {detail}' if detail else ''}")

    print("=" * 65)
    print("STARTING AI SUMMARIZER PRODUCTION REGRESSION SUITE")
    print("=" * 65)

    # ============================================================
    # 1. System, Heartbeat & OpenAPI Contract Tests
    # ============================================================
    try:
        res = client.get("/")
        log_result(
            "GET / (Root Welcome)",
            res.status_code == 200 and "AI Summarizer" in res.json().get("message", ""),
            f"Status {res.status_code}"
        )
    except Exception as e:
        log_result("GET / (Root Welcome)", False, str(e))

    try:
        res = client.get("/health")
        log_result(
            "GET /health (Service Heartbeat)",
            res.status_code == 200 and res.json().get("status") == "Running",
            f"Status {res.status_code}"
        )
    except Exception as e:
        log_result("GET /health (Service Heartbeat)", False, str(e))

    try:
        res = client.get("/docs")
        log_result("GET /docs (Swagger UI)", res.status_code == 200, f"Status {res.status_code}")
    except Exception as e:
        log_result("GET /docs (Swagger UI)", False, str(e))

    try:
        res = client.get("/openapi.json")
        data = res.json()
        endpoints = data.get("paths", {})
        expected_routes = [
            "/summarize",
            "/summarize-multiple",
            "/key-points",
            "/compare",
            "/summarize-media",
            "/update-summary",
            "/summarize-hierarchical",
            "/summarize-youtube",
            "/check-faithfulness"
        ]
        has_all_routes = all(r in endpoints for r in expected_routes)
        is_openapi_303 = data.get("openapi") == "3.0.3"
        log_result(
            "GET /openapi.json (OpenAPI 3.0.3 & Route Registration)",
            res.status_code == 200 and has_all_routes and is_openapi_303,
            f"Found {len(endpoints)} paths, version={data.get('openapi')}"
        )
    except Exception as e:
        log_result("GET /openapi.json", False, str(e))

    try:
        # Preflight CORS check
        res = client.options(
            "/summarize",
            headers={
                "Origin": "http://localhost:5173",
                "Access-Control-Request-Method": "POST"
            }
        )
        cors_ok = res.status_code == 200 and "access-control-allow-origin" in res.headers
        log_result("OPTIONS /summarize (CORS Preflight Headers)", cors_ok, f"Status {res.status_code}")
    except Exception as e:
        log_result("OPTIONS /summarize (CORS Preflight Headers)", False, str(e))

    try:
        # Observability & latency header check
        res = client.get("/health")
        process_time_hdr = res.headers.get("x-process-time")
        is_ok = bool(process_time_hdr and process_time_hdr.endswith("s"))
        log_result("Observability Header (X-Process-Time)", is_ok, f"Header value: {process_time_hdr}")
    except Exception as e:
        log_result("Observability Header (X-Process-Time)", False, str(e))

    # ============================================================
    # 2. Document Parsing & Text Extraction Tests
    # ============================================================
    try:
        # Test PDF extraction using existing sample PDF if available
        sample_pdf = backend_dir / "uploads" / "SURYA K - Resume.pdf"
        if not sample_pdf.exists():
            sample_pdf = backend_dir / "uploads" / "SOFTWARE REQUIREMENT SPECIFICATION.pdf"
        if sample_pdf.exists():
            extracted_pdf_text = extract_text(str(sample_pdf))
            is_ok = bool(extracted_pdf_text and len(extracted_pdf_text) > 50)
            log_result("Text Extraction (PDF PyMuPDF)", is_ok, f"Extracted {len(extracted_pdf_text)} characters")
        else:
            log_result("Text Extraction (PDF PyMuPDF)", True, "No sample PDF present, skipped")
    except Exception as e:
        log_result("Text Extraction (PDF PyMuPDF)", False, str(e))

    try:
        # Test DOCX extraction using existing sample DOCX if available
        sample_docx = backend_dir / "uploads" / "SRS - Project.docx"
        if sample_docx.exists():
            extracted_docx_text = extract_text(str(sample_docx))
            is_ok = bool(extracted_docx_text and len(extracted_docx_text) > 50)
            log_result("Text Extraction (DOCX python-docx)", is_ok, f"Extracted {len(extracted_docx_text)} characters")
        else:
            log_result("Text Extraction (DOCX python-docx)", True, "No sample DOCX present, skipped")
    except Exception as e:
        log_result("Text Extraction (DOCX python-docx)", False, str(e))

    # ============================================================
    # 2.1 Importance Scoring Engine Unit Test
    # ============================================================
    try:
        sample_imp_text = """
        # Section 2: Performance Evaluation & Decision
        The key findings demonstrate that throughput increased by 35% (up to 12,000 req/sec).
        The architecture review board decided to approve the distributed deployment plan.
        Identified risks include potential cache stampedes during node failover.
        Next steps: operations team must implement distributed locking prior to production launch.
        """
        imp_res = score_importance(sample_imp_text, chunk_index=1, total_chunks=2)
        score_bounded = (0.0 <= imp_res["score"] <= 1.0)
        has_signals = all(k in imp_res["signals"] for k in ["key_findings", "decisions", "metrics", "actions", "risks", "conclusion"])
        high_score = imp_res["score"] >= 0.70
        is_ok = score_bounded and has_signals and high_score and bool(imp_res["reason"])
        log_result("Importance Scoring (Hybrid Heuristic & Signals)", is_ok, f"Score: {imp_res['score']:.2f}, Signals: {sum(imp_res['signals'].values())} active")
    except Exception as e:
        log_result("Importance Scoring (Hybrid Heuristic & Signals)", False, str(e))

    # ============================================================
    # 2.2 Redundancy Detection & Removal Unit Test
    # ============================================================
    try:
        sec1 = {
            "section_index": 1,
            "summary": "Revenue increased.",
            "importance_score": 0.30,
            "importance_signals": {"key_findings": False, "decisions": False, "metrics": False, "actions": False, "risks": False, "conclusion": False}
        }
        sec2 = {
            "section_index": 2,
            "summary": "Revenue increased 25% year-over-year to $4.2 million.",
            "importance_score": 0.88,
            "importance_signals": {"key_findings": True, "decisions": False, "metrics": True, "actions": False, "risks": False, "conclusion": False}
        }
        sec3 = {
            "section_index": 3,
            "summary": "Engineering team deployed the multi-region Kubernetes cluster.",
            "importance_score": 0.75,
            "importance_signals": {"key_findings": False, "decisions": True, "metrics": False, "actions": True, "risks": False, "conclusion": False}
        }
        processed, records = detect_and_filter_redundancy([sec1, sec2, sec3], threshold=0.80)
        is_ok = (
            len(records) == 1 and
            records[0]["kept_section"] == 2 and
            records[0]["removed_section"] == 1 and
            processed[0]["is_redundant"] is True and
            processed[1]["is_redundant"] is False and
            processed[2]["is_redundant"] is False
        )
        log_result("Redundancy Detection (Layered Near-Duplicate & Quality Selection)", is_ok, f"{len(records)} redundancy event detected, kept Section 2 over Section 1")
    except Exception as e:
        log_result("Redundancy Detection (Layered Near-Duplicate & Quality Selection)", False, str(e))

    # ============================================================
    # 2.3 Faithfulness Verification Engine Unit Test
    # ============================================================
    try:
        sample_src = (
            "CloudCorp reported that Q3 2025 revenue grew by 25% year-over-year to $4.2 million. "
            "The engineering team deployed 12 distributed nodes across 3 availability zones."
        )
        sample_faithful_sum = (
            "Revenue grew by 25% to $4.2 million in Q3 2025. "
            "12 distributed nodes were deployed across 3 availability zones."
        )
        sample_unfaithful_sum = (
            "Revenue grew by 35% to $4.2 million in Q3 2025. "
            "CloudCorp acquired MegaTech for $50 million in 2026."
        )

        res_faithful = check_faithfulness(source_text=sample_src, summary_text=sample_faithful_sum)
        res_unfaithful = check_faithfulness(source_text=sample_src, summary_text=sample_unfaithful_sum)

        is_ok = (
            res_faithful["faithfulness_score"] >= 0.80 and
            res_faithful["status"] == "HIGH" and
            res_faithful["unsupported_claims"] == 0 and
            res_unfaithful["unsupported_claims"] >= 1 and
            res_unfaithful["faithfulness_score"] < 0.60
        )
        log_result(
            "Faithfulness Verification (Deterministic Grounding & Numerical Validation)",
            is_ok,
            f"Faithful score: {res_faithful['faithfulness_score']:.2f}, Unfaithful detected: {res_unfaithful['unsupported_claims']} claim(s)"
        )
    except Exception as e:
        log_result("Faithfulness Verification (Deterministic Grounding & Numerical Validation)", False, str(e))

    # ============================================================
    # 3. Input Validation, Bounds & Security Tests
    # ============================================================
    # Unsupported document type on /summarize
    try:
        res = client.post(
            "/summarize",
            files={"file": ("test.exe", b"binary content", "application/octet-stream")},
            data={"length": "medium", "format": "paragraph"}
        )
        log_result("POST /summarize (Unsupported file format .exe)", res.status_code == 400, f"Status {res.status_code}: {res.json().get('detail')}")
    except Exception as e:
        log_result("POST /summarize (Unsupported format)", False, str(e))

    # Empty file on /summarize
    try:
        res = client.post(
            "/summarize",
            files={"file": ("empty.txt", b"", "text/plain")},
            data={"length": "medium", "format": "paragraph"}
        )
        log_result("POST /summarize (Empty file 0-bytes)", res.status_code == 400, f"Status {res.status_code}: {res.json().get('detail')}")
    except Exception as e:
        log_result("POST /summarize (Empty file)", False, str(e))

    # Missing file parameter on /summarize
    try:
        res = client.post(
            "/summarize",
            data={"length": "medium", "format": "paragraph"}
        )
        log_result("POST /summarize (Missing file payload -> 422)", res.status_code == 422, f"Status {res.status_code}")
    except Exception as e:
        log_result("POST /summarize (Missing file payload)", False, str(e))

    # Invalid length choice on /summarize
    try:
        res = client.post(
            "/summarize",
            files={"file": ("sample.txt", b"Valid text content for test.", "text/plain")},
            data={"length": "super-long", "format": "paragraph"}
        )
        log_result("POST /summarize (Invalid length literal -> 422)", res.status_code == 422, f"Status {res.status_code}")
    except Exception as e:
        log_result("POST /summarize (Invalid length literal)", False, str(e))

    # Invalid format choice on /summarize
    try:
        res = client.post(
            "/summarize",
            files={"file": ("sample.txt", b"Valid text content for test.", "text/plain")},
            data={"length": "medium", "format": "markdown-tree"}
        )
        log_result("POST /summarize (Invalid format literal -> 422)", res.status_code == 422, f"Status {res.status_code}")
    except Exception as e:
        log_result("POST /summarize (Invalid format literal)", False, str(e))

    # Oversized file upload (> 10 MB payload)
    try:
        oversized_data = b"0" * (11 * 1024 * 1024)  # 11 MB
        res = client.post(
            "/summarize",
            files={"file": ("large_test.txt", oversized_data, "text/plain")},
            data={"length": "short", "format": "paragraph"}
        )
        log_result("POST /summarize (Streaming Oversized file 11MB -> 413)", res.status_code == 413, f"Status {res.status_code}: {res.json().get('detail')}")
    except Exception as e:
        log_result("POST /summarize (Oversized file)", False, str(e))

    # Single-pass length guard (> 60k chars suggests Hierarchical)
    try:
        huge_text_data = ("The quick brown fox jumps over the lazy dog. " * 1500).encode("utf-8")
        res = client.post(
            "/summarize",
            files={"file": ("huge_doc.txt", huge_text_data, "text/plain")},
            data={"length": "short", "format": "paragraph"}
        )
        log_result("POST /summarize (Text >60k chars guard -> 400 Hierarchical guidance)", res.status_code == 400 and "Hierarchical" in str(res.json().get("detail")), f"Status {res.status_code}")
    except Exception as e:
        log_result("POST /summarize (Text >60k chars guard)", False, str(e))

    # Invalid key points range (< 1 or > 20)
    try:
        doc_a_path = root_dir / "document_a.txt"
        with open(doc_a_path, "rb") as f:
            res = client.post(
                "/key-points",
                files={"file": ("document_a.txt", f, "text/plain")},
                data={"number_of_points": 25}
            )
        log_result("POST /key-points (Out of range points: 25 -> 400)", res.status_code == 400, f"Status {res.status_code}: {res.json().get('detail')}")
    except Exception as e:
        log_result("POST /key-points (Out of range 25)", False, str(e))

    try:
        doc_a_path = root_dir / "document_a.txt"
        with open(doc_a_path, "rb") as f:
            res = client.post(
                "/key-points",
                files={"file": ("document_a.txt", f, "text/plain")},
                data={"number_of_points": 0}
            )
        log_result("POST /key-points (Boundary points: 0 -> 400)", res.status_code == 400, f"Status {res.status_code}: {res.json().get('detail')}")
    except Exception as e:
        log_result("POST /key-points (Boundary 0)", False, str(e))

    # Missing second document on /compare
    try:
        doc_a_path = root_dir / "document_a.txt"
        with open(doc_a_path, "rb") as f:
            res = client.post(
                "/compare",
                files={"file_a": ("document_a.txt", f, "text/plain")}
            )
        log_result("POST /compare (Missing file_b -> 422)", res.status_code == 422, f"Status {res.status_code}")
    except Exception as e:
        log_result("POST /compare (Missing file_b)", False, str(e))

    # Compare unsupported document format
    try:
        res = client.post(
            "/compare",
            files={
                "file_a": ("test.txt", b"Valid content", "text/plain"),
                "file_b": ("test.exe", b"Binary content", "application/octet-stream")
            }
        )
        log_result("POST /compare (File B unsupported .exe -> 400)", res.status_code == 400, f"Status {res.status_code}: {res.json().get('detail')}")
    except Exception as e:
        log_result("POST /compare (File B unsupported)", False, str(e))

    # Multi-document with mixed valid and unsupported file
    try:
        res = client.post(
            "/summarize-multiple",
            files=[
                ("files", ("doc1.txt", b"Valid text", "text/plain")),
                ("files", ("bad.bin", b"binary stream", "application/octet-stream"))
            ]
        )
        log_result("POST /summarize-multiple (Mixed valid/unsupported file -> 400)", res.status_code == 400, f"Status {res.status_code}")
    except Exception as e:
        log_result("POST /summarize-multiple (Mixed files)", False, str(e))

    # Invalid YouTube URL
    try:
        res = client.post(
            "/summarize-youtube",
            data={"url": "https://invalid-non-youtube-site.com/video"}
        )
        log_result("POST /summarize-youtube (Invalid YouTube URL -> 400)", res.status_code == 400, f"Status {res.status_code}: {res.json().get('detail')}")
    except Exception as e:
        log_result("POST /summarize-youtube (Invalid URL)", False, str(e))

    # Empty YouTube URL
    try:
        res = client.post(
            "/summarize-youtube",
            data={"url": "   "}
        )
        log_result("POST /summarize-youtube (Whitespace URL -> 400)", res.status_code == 400, f"Status {res.status_code}: {res.json().get('detail')}")
    except Exception as e:
        log_result("POST /summarize-youtube (Whitespace URL)", False, str(e))

    # Empty/whitespace update summary fields
    try:
        res = client.post(
            "/update-summary",
            data={"previous_summary": "   ", "current_text": "   "}
        )
        log_result("POST /update-summary (Whitespace inputs -> 400)", res.status_code == 400, f"Status {res.status_code}: {res.json().get('detail')}")
    except Exception as e:
        log_result("POST /update-summary (Whitespace inputs)", False, str(e))

    # Hierarchical summarizer chunk_size boundary (< 500)
    try:
        doc_a_path = root_dir / "document_a.txt"
        with open(doc_a_path, "rb") as f:
            res = client.post(
                "/summarize-hierarchical",
                files={"file": ("document_a.txt", f, "text/plain")},
                data={"chunk_size": 100}
            )
        log_result("POST /summarize-hierarchical (chunk_size < 500 -> 400)", res.status_code == 400, f"Status {res.status_code}: {res.json().get('detail')}")
    except Exception as e:
        log_result("POST /summarize-hierarchical (chunk_size < 500)", False, str(e))

    # Media summarizer unsupported format
    try:
        res = client.post(
            "/summarize-media",
            files={"file": ("document.pdf", b"%PDF-1.4", "application/pdf")}
        )
        log_result("POST /summarize-media (Non-media extension .pdf -> 400)", res.status_code == 400, f"Status {res.status_code}: {res.json().get('detail')}")
    except Exception as e:
        log_result("POST /summarize-media (Non-media extension)", False, str(e))

    # Faithfulness empty summary text validation
    try:
        res = client.post(
            "/check-faithfulness",
            data={"source_text": "Valid source content.", "summary_text": "   "}
        )
        log_result("POST /check-faithfulness (Whitespace summary text -> 400)", res.status_code == 400, f"Status {res.status_code}: {res.json().get('detail')}")
    except Exception as e:
        log_result("POST /check-faithfulness (Whitespace summary text)", False, str(e))

    # Faithfulness missing both file and source_text
    try:
        res = client.post(
            "/check-faithfulness",
            data={"summary_text": "Some summary text."}
        )
        log_result("POST /check-faithfulness (Missing source text & file -> 400)", res.status_code == 400, f"Status {res.status_code}: {res.json().get('detail')}")
    except Exception as e:
        log_result("POST /check-faithfulness (Missing source text & file)", False, str(e))

    # ============================================================
    # 4. Functional End-to-End Tests (Live or Deterministic Mock)
    # ============================================================
    is_ci_mode = "--ci" in sys.argv or not os.getenv("GROQ_API_KEY")
    patcher = None
    media_transcription_patcher = None

    if is_ci_mode:
        print("[INFO] Executing in Deterministic CI mode (Mocked LLM Provider)")
        from unittest.mock import patch
        import app.services.groq_service as groq_svc
        import app.api.summarize as summarize_api

        def mock_call_groq(messages, temperature=0.2, operation="operation"):
            if "key" in operation:
                return "1. First salient key takeaway.\n2. Second salient key takeaway.\n3. Third salient key takeaway."
            elif "compare" in operation:
                return "Similarities: Both documents address the topic.\nDifferences: Divergent perspectives identified."
            elif "update" in operation:
                return "New Information:\n- Added details.\n\nChanged Information:\n- Modified data.\n\nRemoved Information:\nNone identified.\n\nUnchanged Information:\n- Baseline constants."
            return "This is an accurate and high-quality synthesis of the uploaded document contents."

        patcher = patch.object(groq_svc, "_call_groq_chat", side_effect=mock_call_groq)
        patcher.start()

        media_transcription_patcher = patch.object(
            summarize_api,
            "transcribe_media",
            return_value="This is a deterministic CI transcription used for testing the media summarization pipeline."
        )
        media_transcription_patcher.start()
    else:
        print("[INFO] Executing in Live Integration mode with Groq API")

    # POST /summarize
    try:
        doc_a_path = root_dir / "document_a.txt"
        with open(doc_a_path, "rb") as f:
            res = client.post(
                "/summarize",
                files={"file": ("document_a.txt", f, "text/plain")},
                data={"length": "short", "format": "paragraph", "executive": "false"}
            )
        mode_label = "CI Mock" if is_ci_mode else "Live"
        is_ok = res.status_code == 200 and "summary" in res.json() and len(res.json()["summary"]) > 20
        log_result(f"POST /summarize (Single Document {mode_label})", is_ok, f"Status {res.status_code}")
        if not is_ci_mode:
            time.sleep(0.5)
    except Exception as e:
        log_result("POST /summarize", False, str(e))

    # POST /key-points
    try:
        kp_path = root_dir / "keypoints_test.txt"
        with open(kp_path, "rb") as f:
            res = client.post(
                "/key-points",
                files={"file": ("keypoints_test.txt", f, "text/plain")},
                data={"number_of_points": 3}
            )
        is_ok = res.status_code == 200 and len(res.json().get("key_points", [])) == 3
        log_result(f"POST /key-points (Key Points Extraction {mode_label})", is_ok, f"Status {res.status_code}, {len(res.json().get('key_points', []))} points")
        if not is_ci_mode:
            time.sleep(0.5)
    except Exception as e:
        log_result(f"POST /key-points (Key Points Extraction {mode_label})", False, str(e))

    # POST /summarize-multiple
    try:
        doc_a_path = root_dir / "document_a.txt"
        doc_b_path = root_dir / "document_b.txt"
        with open(doc_a_path, "rb") as fa, open(doc_b_path, "rb") as fb:
            res = client.post(
                "/summarize-multiple",
                files=[
                    ("files", ("document_a.txt", fa, "text/plain")),
                    ("files", ("document_b.txt", fb, "text/plain"))
                ],
                data={"length": "medium", "format": "bullets", "executive": "true"}
            )
        is_ok = res.status_code == 200 and "summary" in res.json()
        log_result(f"POST /summarize-multiple (Multi-Document Synthesis {mode_label})", is_ok, f"Status {res.status_code}")
        if not is_ci_mode:
            time.sleep(0.5)
    except Exception as e:
        log_result(f"POST /summarize-multiple (Multi-Document Synthesis {mode_label})", False, str(e))

    # POST /compare
    try:
        comp_a_path = root_dir / "compare_a.txt"
        comp_b_path = root_dir / "compare_b.txt"
        with open(comp_a_path, "rb") as fa, open(comp_b_path, "rb") as fb:
            res = client.post(
                "/compare",
                files={
                    "file_a": ("compare_a.txt", fa, "text/plain"),
                    "file_b": ("compare_b.txt", fb, "text/plain")
                }
            )
        is_ok = res.status_code == 200 and "summary" in res.json()
        log_result(f"POST /compare (Document Comparison {mode_label})", is_ok, f"Status {res.status_code}")
        if not is_ci_mode:
            time.sleep(0.5)
    except Exception as e:
        log_result(f"POST /compare (Document Comparison {mode_label})", False, str(e))

    # POST /update-summary
    try:
        prev_sum = "Company Q1 reported 10% growth in revenue and launched Product X."
        curr_text = "Company Q2 reported 15% growth in revenue, launched Product Y, and deprecated Product X."
        res = client.post(
            "/update-summary",
            data={"previous_summary": prev_sum, "current_text": curr_text}
        )
        is_ok = res.status_code == 200 and "summary" in res.json()
        log_result(f"POST /update-summary (Delta Change Detection {mode_label})", is_ok, f"Status {res.status_code}")
        if not is_ci_mode:
            time.sleep(0.5)
    except Exception as e:
        log_result(f"POST /update-summary (Delta Change Detection {mode_label})", False, str(e))

    # POST /summarize-hierarchical (with Concurrent Map-Reduce)
    try:
        doc_a_path = root_dir / "document_a.txt"
        with open(doc_a_path, "rb") as f:
            res = client.post(
                "/summarize-hierarchical",
                files={"file": ("document_a.txt", f, "text/plain")},
                data={"length": "medium", "format": "paragraph", "chunk_size": 2000}
            )
        data = res.json()
        sections = data.get("section_summaries", [])
        has_importance = (
            len(sections) > 0 and
            all("importance_score" in s and s["importance_score"] is not None for s in sections) and
            all("importance_signals" in s and s["importance_signals"] is not None for s in sections)
        )
        has_redundancy_meta = (
            "redundant_sections_count" in data and
            all("is_redundant" in s for s in sections)
        )
        has_faithfulness = (
            "faithfulness" in data and
            data["faithfulness"] is not None and
            0.0 <= data["faithfulness"]["faithfulness_score"] <= 1.0 and
            "status" in data["faithfulness"]
        )
        is_ok = (
            res.status_code == 200 and
            "final_summary" in data and
            "section_summaries" in data and
            has_importance and
            has_redundancy_meta and
            has_faithfulness
        )
        faith_score = data.get("faithfulness", {}).get("faithfulness_score", 0.0)
        log_result(f"POST /summarize-hierarchical (Map-Reduce with Importance, Redundancy & Faithfulness {mode_label})", is_ok, f"Status {res.status_code}, {data.get('total_sections', 0)} section(s), {data.get('redundant_sections_count', 0)} redundant, faith={faith_score:.2f}")
        if not is_ci_mode:
            time.sleep(0.5)
    except Exception as e:
        log_result(f"POST /summarize-hierarchical (Concurrent Map-Reduce {mode_label})", False, str(e))

    # POST /check-faithfulness (Direct Text-based Verification)
    try:
        source_sample = "CloudCorp reported $4.2 million in quarterly revenue with 25% year-over-year growth in 2025."
        summary_sample = "Revenue reached $4.2 million with 25% growth in 2025."
        res = client.post(
            "/check-faithfulness",
            data={"source_text": source_sample, "summary_text": summary_sample}
        )
        data = res.json()
        is_ok = (
            res.status_code == 200 and
            data.get("faithfulness_score") >= 0.80 and
            data.get("status") == "HIGH" and
            data.get("claims_checked") >= 1 and
            data.get("supported_claims") >= 1
        )
        log_result(f"POST /check-faithfulness (Text-based Verification {mode_label})", is_ok, f"Status {res.status_code}, score={data.get('faithfulness_score')}")
        if not is_ci_mode:
            time.sleep(0.5)
    except Exception as e:
        log_result(f"POST /check-faithfulness (Text-based Verification {mode_label})", False, str(e))

    # POST /check-faithfulness (File-based Verification)
    try:
        doc_a_path = root_dir / "document_a.txt"
        with open(doc_a_path, "rb") as f:
            res = client.post(
                "/check-faithfulness",
                files={"file": ("document_a.txt", f, "text/plain")},
                data={"summary_text": "Artificial intelligence applications require scalable cloud architectures."}
            )
        data = res.json()
        is_ok = (
            res.status_code == 200 and
            "faithfulness_score" in data and
            "claims" in data and
            data.get("claims_checked") >= 1
        )
        log_result(f"POST /check-faithfulness (File-based Verification {mode_label})", is_ok, f"Status {res.status_code}, score={data.get('faithfulness_score')}")
        if not is_ci_mode:
            time.sleep(0.5)
    except Exception as e:
        log_result(f"POST /check-faithfulness (File-based Verification {mode_label})", False, str(e))

    # POST /summarize-media (Audio with faster-whisper)
    try:
        media_path = root_dir / "voice_test.mp3"
        if not media_path.exists():
            media_path = root_dir / "test.wav"
        if media_path.exists():
            with open(media_path, "rb") as f:
                res = client.post(
                    "/summarize-media",
                    files={"file": (media_path.name, f, "audio/mpeg")},
                    data={"length": "short", "format": "paragraph"}
                )
            is_ok = res.status_code == 200 and "summary" in res.json()
            log_result(f"POST /summarize-media (Speech Transcription & Summary {mode_label})", is_ok, f"Status {res.status_code}")
        else:
            log_result("POST /summarize-media", True, "Sample media not found, skipped live execution")
    except Exception as e:
        log_result(f"POST /summarize-media (Speech Transcription & Summary {mode_label})", False, str(e))

    if media_transcription_patcher is not None:
        media_transcription_patcher.stop()

    if patcher is not None:
        patcher.stop()

    print("=" * 65)
    total = len(results)
    passed = sum(1 for _, s, _ in results if s == "PASS")
    failed = total - passed
    print(f"TEST RUN COMPLETE: {passed}/{total} PASSED, {failed} FAILED")
    print("=" * 65)
    return failed == 0


if __name__ == "__main__":
    success = run_tests()
    sys.exit(0 if success else 1)
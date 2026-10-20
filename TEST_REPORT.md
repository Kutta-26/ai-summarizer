# AI Summarizer — QA & End-to-End Verification Test Report

## 1. Test Environment

- **Operating System**: Windows 11 with Smart App Control / Code Integrity Policy enforced
- **Python Version**: Python 3.11.9
- **Node.js / npm**: Node.js v20.x, npm v11.x
- **Docker**: Docker Engine 29.8.0, Docker Compose 5.5.1
- **Docker Runtime**: Docker Desktop Linux containers through WSL2
- **Inference Hardware**: Local CPU with faster-whisper INT8 and native FFmpeg decoding fallback + Groq Cloud
- **Primary LLM Model**: `openai/gpt-oss-20b` on Groq Cloud

---

## 2. Automated Test Execution Matrix

### Overall Result: 48/48 Automated Regression Tests Passing — 100% Success Rate
*(Plus 92/92 automated pytest unit tests across core, advanced, importance, redundancy, faithfulness, and contradiction suites)*

| Test Suite | Endpoint / Component | Test Case | Status | Notes |
| :--- | :--- | :--- | :---: | :--- |
| **System** | `GET /` | Root Welcome Endpoint | **PASS** | Returns `{"message": "Welcome to AI Summarizer API"}` with HTTP 200 |
| **System** | `GET /health` | Service Heartbeat | **PASS** | Returns `{"status":"Running"}` with HTTP 200 |
| **System** | `GET /docs` | Swagger UI API Documentation | **PASS** | Interactive OpenAPI documentation rendered successfully |
| **System** | `GET /openapi.json` | OpenAPI Specification | **PASS** | Schema validated (`3.0.3`) with 12 registered paths and binary upload schemas |
| **CORS** | `OPTIONS /summarize` | CORS Preflight Handling | **PASS** | `access-control-allow-origin` header verified |
| **Observability** | `GET /health` | Latency Header (`X-Process-Time`) | **PASS** | Latency header verified |
| **Document Parsers** | `file_service.extract_text` | PDF PyMuPDF Extraction | **PASS** | Successfully parsed sample PDF |
| **Document Parsers** | `file_service.extract_text` | DOCX python-docx Extraction | **PASS** | Successfully parsed sample DOCX |
| **Importance Engine** | `importance_service.score_importance` | Hybrid Heuristic & Signals | **PASS** | Score: 0.96 with 5 active signals |
| **Redundancy Engine** | `redundancy_service.detect_and_filter_redundancy` | Near-Duplicate & Quality Selection | **PASS** | 1 redundancy event detected, kept Section 2 over Section 1 |
| **Faithfulness Engine** | `faithfulness_service.check_faithfulness` | Grounding & Numerical Validation | **PASS** | Faithful: 1.00 score; Unfaithful: 2 unsupported claims detected |
| **Contradiction Engine**| `contradiction_service.detect_contradictions` | Conflict & Antonym Detection | **PASS** | Clean: 0 conflicts; Conflict: 2 detected conflicts (numerical & antonym) |
| **Error Handling** | `POST /summarize` | Unsupported format (`.exe`) | **PASS** | HTTP 400: Unsupported file format restriction |
| **Error Handling** | `POST /summarize` | Empty file validation | **PASS** | HTTP 400: empty-file validation |
| **Error Handling** | `POST /summarize` | Missing file payload | **PASS** | HTTP 422: FastAPI validation |
| **Error Handling** | `POST /summarize` | Invalid length parameter | **PASS** | HTTP 422: parameter validation rejection |
| **Error Handling** | `POST /summarize` | Invalid format parameter | **PASS** | HTTP 422: parameter validation rejection |
| **Security & Limits** | `POST /summarize` | Streaming oversized file | **PASS** | HTTP 413: 10 MB upload limit enforced |
| **Context Safety** | `POST /summarize` | Direct text >60k characters | **PASS** | HTTP 400: guidance to use Hierarchical Summarizer |
| **Error Handling** | `POST /key-points` | Out-of-range count | **PASS** | HTTP 400: count validation |
| **Error Handling** | `POST /key-points` | Boundary value: 0 points | **PASS** | HTTP 400: count validation |
| **Error Handling** | `POST /compare` | Missing `file_b` field | **PASS** | HTTP 422: required-field validation |
| **Error Handling** | `POST /compare` | File B unsupported format | **PASS** | HTTP 400: format restriction |
| **Error Handling** | `POST /summarize-multiple` | Mixed valid/unsupported files | **PASS** | HTTP 400: unsupported format rejection |
| **Error Handling** | `POST /summarize-youtube` | Invalid/non-YouTube URL | **PASS** | HTTP 400: video ID validation |
| **Error Handling** | `POST /summarize-youtube` | Whitespace-only URL | **PASS** | HTTP 400: empty URL validation |
| **Error Handling** | `POST /update-summary` | Whitespace input | **PASS** | HTTP 400: previous summary validation |
| **Context Safety** | `POST /compare` | Document >60k characters | **PASS** | HTTP 400: comparison context safety limit rejection |
| **Context Safety** | `POST /update-summary` | Text >60k characters | **PASS** | HTTP 400: delta summary context safety limit rejection |
| **Error Handling** | `POST /summarize-hierarchical` | Invalid chunk-size boundary | **PASS** | HTTP 400: chunk-size validation |
| **Error Handling** | `POST /summarize-media` | Non-media extension | **PASS** | HTTP 400: media extension validation |
| **Error Handling** | `POST /check-faithfulness` | Whitespace summary text | **PASS** | HTTP 400: summary text validation |
| **Error Handling** | `POST /check-faithfulness` | Missing source text & file | **PASS** | HTTP 400: required source material validation |
| **Error Handling** | `POST /check-contradictions` | Whitespace summary text | **PASS** | HTTP 400: summary text validation |
| **Error Handling** | `POST /check-contradictions` | Missing source text & file | **PASS** | HTTP 400: required source material validation |
| **Single Document** | `POST /summarize` | `document_a.txt` | **PASS** | HTTP 200: valid Groq-generated summary |
| **Key Points** | `POST /key-points` | `keypoints_test.txt` | **PASS** | HTTP 200: requested key points returned |
| **Multi-Document** | `POST /summarize-multiple` | `document_a.txt` + `document_b.txt` | **PASS** | HTTP 200: multi-document synthesis |
| **Compare** | `POST /compare` | `compare_a.txt` vs `compare_b.txt` | **PASS** | HTTP 200: comparative report |
| **Compare** | `POST /compare` | Identical documents fast-path | **PASS** | HTTP 200: deterministic instant comparison without LLM tokens |
| **Update Summary** | `POST /update-summary` | Previous summary vs current text | **PASS** | HTTP 200: delta analysis |
| **Update Summary** | `POST /update-summary` | Identical content fast-path | **PASS** | HTTP 200: deterministic instant delta without LLM tokens |
| **Hierarchical** | `POST /summarize-hierarchical` | Map-Reduce with Importance, Redundancy, Faithfulness & Contradictions | **PASS** | HTTP 200: section synthesis, importance signals, redundancy filter, faithfulness & contradiction checks |
| **Faithfulness Check**| `POST /check-faithfulness` | Direct Text-based Verification | **PASS** | HTTP 200: verified supported claims, score 1.00 |
| **Faithfulness Check**| `POST /check-faithfulness` | File-based Document Verification | **PASS** | HTTP 200: verified claims against uploaded file |
| **Contradiction Check**| `POST /check-contradictions` | Direct Text-based Conflict Detection | **PASS** | HTTP 200: verified status CLEAN, 0 conflicts |
| **Contradiction Check**| `POST /check-contradictions` | File-based Document Conflict Detection | **PASS** | HTTP 200: verified status CLEAN against uploaded file |
| **Media Pipeline** | `POST /summarize-media` | `voice_test.mp3` | **PASS** | HTTP 200: FFmpeg + Whisper + Groq pipeline |

---

### Dedicated Pytest Unit Test Suites (92/92 Passing)

| Test Module | Coverage Area | Tests Passed | Status |
| :--- | :--- | :---: | :---: |
| `tests/test_core_summarization.py` | Lengths, formats, executive summary, key points boundaries & leading-number preservation, corrupt PDF cleanup, OpenAPI 3.0.3 binary schemas, 10MB limit, 60k char guard, Groq API errors | 17 / 17 | **PASS** |
| `tests/test_advanced_features.py` | Multi-doc synthesis, document comparison identical/context guards, delta update detection identical/context guards, chunking headers, hierarchical enrichment, media, YouTube | 16 / 16 | **PASS** |
| `tests/test_importance.py` | Scoring bounds, numerical/entity/definition signals, structural formatting, batch processing | 5 / 5 | **PASS** |
| `tests/test_redundancy.py` | Exact/near duplicates, semantic preservation, quality selection, fallback filters | 9 / 9 | **PASS** |
| `tests/test_faithfulness.py` | Entailment, numerical validation, leading-number bullet claims, date/entity checks, LLM fallback & error handling, hierarchical integration | 18 / 18 | **PASS** |
| `tests/test_contradiction.py` | Numerical/percentage/temporal/entity/antonym conflicts, leading-number bullet conflicts, schema bounds, LLM ambiguity resolution | 27 / 27 | **PASS** |
| **Total Pytest Unit Tests** | | **92 / 92** | **PASS (100%)** |

---

## 3. Production Build Verification

The React frontend was compiled successfully using Vite.

- **Vite Version**: 5.4.21
- **Modules Transformed**: 1,844
- **Build Status**: 0 errors, 0 warnings
- **Recorded Build Time**: approximately 3.38 seconds
- **`dist/index.html`**: 0.81 kB, gzip 0.45 kB
- **CSS Bundle**: 17.24 kB, gzip 3.64 kB
- **JavaScript Bundle**: 206.01 kB, gzip 59.56 kB

The production build completed successfully without compilation errors or warnings.

---

## 4. Manual QA Verification

A final manual QA pass covered 20 scenarios from `TC-QA-001` through `TC-QA-020`.

| Test Case | Area | Status | Verification |
| :--- | :--- | :---: | :--- |
| TC-QA-001 | Single-document summarization | **PASS** | Upload, loading, summary generation, result rendering and copy functionality |
| TC-QA-002 | Multi-document summarization | **PASS** | Multiple documents synthesized successfully |
| TC-QA-003 | Length controls | **PASS** | Short, Medium and Long options exercised |
| TC-QA-004 | Paragraph format | **PASS** | Paragraph output verified |
| TC-QA-005 | Bullet format | **PASS** | Bullet output verified |
| TC-QA-006 | Table format | **PASS** | Markdown table output verified |
| TC-QA-007 | Key-point extraction | **PASS** | Requested points displayed with individual copy controls |
| TC-QA-008 | Comparative summarization | **PASS** | Comparison workflow completed |
| TC-QA-009 | Update summarization | **PASS** | Updated and unchanged information detected |
| TC-QA-010 | Hierarchical summarization | **PASS** | Hierarchical workflow completed |
| TC-QA-011 | Audio summarization | **PASS** | Audio transcription and summarization completed |
| TC-QA-012 | Video summarization | **PASS** | Speech-containing MP4 processed successfully |
| TC-QA-013 | YouTube summarization | **PASS** | Live workflow verified on an unrestricted network |
| TC-QA-014 | Invalid input handling | **PASS** | Client and server validation behaved correctly |
| TC-QA-015 | Unsupported file handling | **PASS** | Unsupported extension rejected clearly |
| TC-QA-016 | Oversized file handling | **PASS** | Client rejected oversized file; backend 413 verified automatically |
| TC-QA-017 | Loading-state behavior | **PASS** | Loading indicator appeared and submit button was disabled |
| TC-QA-018 | Duplicate submission protection | **PASS** | Rapid clicks resulted in one `/summarize` request |
| TC-QA-019 | Network failure/recovery | **PASS** | Offline/error state shown and service recovered after backend restart |
| TC-QA-020 | Responsive UI | **PASS** | Mobile and tablet-style layouts exercised successfully |

### Media Re-Test

A speech-containing MP4 was specifically re-tested during final QA.

- FFmpeg extraction completed successfully.
- faster-whisper transcription completed successfully.
- `POST /summarize-media` returned HTTP 200.
- Recorded end-to-end request time was approximately 15.8 seconds for the manual test.

### YouTube Live Verification

The YouTube summarization workflow was successfully tested on an unrestricted network connection.

Earlier failures on an institutional/college network were associated with SSL inspection, firewall restrictions, and certificate re-signing. The application was subsequently verified successfully when tested on an unrestricted network.

---

## 5. Requirement Compliance Matrix

All 15 internship requirements were implemented and verified.

| # | Requirement | Implementation Status | Verification Method |
| :-: | :--- | :---: | :--- |
| 1 | Single document summarization | **VERIFIED** | Automated and manual end-to-end testing |
| 2 | Multi-document summarization | **VERIFIED** | Multiple-file automated and manual testing |
| 3 | Length control — Short/Medium/Long | **VERIFIED** | API validation and manual UI testing |
| 4 | Format preservation — Paragraph/Bullets/Table | **VERIFIED** | Automated validation and manual UI testing |
| 5 | Key point extraction | **VERIFIED** | Automated endpoint testing and manual UI testing |
| 6 | Executive summary mode | **VERIFIED** | Executive-summary workflow verification |
| 7 | Audio/video summarization | **VERIFIED** | FFmpeg + faster-whisper + Groq pipeline |
| 8 | Comparative summarization | **VERIFIED** | Dual-document comparative analysis |
| 9 | Update / delta summaries | **VERIFIED** | Baseline/current change detection |
| 10 | Hierarchical / Map-Reduce summarization | **VERIFIED** | Concurrent section processing and master synthesis |
| 11 | LLM API integration | **VERIFIED** | Groq Cloud integration with connection pooling and TLS verification |
| 12 | YouTube transcript summarization | **VERIFIED** | URL validation plus successful live transcript workflow on unrestricted network |
| 13 | Podcast / audio support | **VERIFIED** | MP3/WAV/M4A/OGG media pipeline |
| 14 | Negative & boundary safety | **VERIFIED** | Automated negative/boundary tests and manual QA |
| 15 | Observability & latency monitoring | **VERIFIED** | `X-Process-Time` header and structured stage logging |

### Important Testing Distinctions

#### YouTube Live Caption/Transcript Fetching

The URL parser, error responses, endpoint integration, and live transcript extraction were verified.

An earlier institutional/college network produced failures associated with SSL inspection, firewall restrictions, and certificate re-signing. The workflow was subsequently tested successfully on an unrestricted network.

**Final status: VERIFIED.**

#### Docker Container Runtime

The Docker environment was verified running with Docker Desktop Linux containers through WSL2.

Verification execution:
- `docker compose build`: Succeeded with 0 errors for both `ai-summarizer-backend` (Python 3.11-slim + FFmpeg) and `ai-summarizer-frontend` (Node 20 builder + Nginx Alpine).
- `docker compose up -d`: Recreated and launched both services into `healthy` state.
- `ai-summarizer-backend`: Container status `healthy`, mapped to `0.0.0.0:8000->8000/tcp`. `GET /health` returned HTTP 200 `{"status":"Running"}`.
- `ai-summarizer-frontend`: Container status `healthy`, mapped to `0.0.0.0:3000->80/tcp`. `GET http://localhost:3000/` returned HTTP 200.
- Persistent upload volume `ai-summarizer_backend_uploads` attached to `/app/uploads`.

**Final status: VERIFIED.**

---

## 6. Docker Runtime Verification

Docker deployment verification is **VERIFIED (PASS)**.

### Docker Environment & Runtime Summary

- **Docker Engine**: 29.8.0
- **Docker Compose**: 5.5.1
- **WSL2 Kernel**: 6.18.33.2-microsoft-standard-WSL2
- **Backend Service**: `ai-summarizer-backend` — Status: `Up (healthy)`, Port: `8000` -> Health check: PASS (HTTP 200 `{"status":"Running"}`)
- **Frontend Service**: `ai-summarizer-frontend` — Status: `Up (healthy)`, Port: `3000` -> Health check: PASS (HTTP 200)
- **Container Network**: `summarizer-net` (bridge)
- **Persistent Volume**: `ai-summarizer_backend_uploads` mounted to `/app/uploads`

---

## 7. Defect Resolution Summary (Session Fixes)

1. **`frontend/src/components/HierarchicalSummarizer.jsx`**:
   - Defect: Contained CP1252 byte `0x95` causing `UnicodeDecodeError` in UTF-8 environments.
   - Resolution: Replaced with valid UTF-8 bullet character `•`.
2. **`tests/test_contradiction.py`**:
   - Defect: Test functions declared below `if __name__ == "__main__":` block causing `NameError` during direct script execution.
   - Resolution: Relocated all test definitions above main runner and cleaned duplicate declarations.
3. **`backend/app/services/groq_service.py`**:
   - Defect: `_call_groq_chat` did not accept or forward `response_format`, causing `TypeError` during JSON-mode LLM contradiction checks; logger string contained escaped `{{e}}`.
   - Resolution: Added `response_format: dict = None` parameter, passed `**create_kwargs` to Groq API client, and corrected logger interpolation.
4. **`frontend/src/services/api.js`**:
   - Defect: Missing exported API client function `checkContradictions` corresponding to `POST /check-contradictions`.
   - Resolution: Implemented and exported `checkContradictions({ file, sourceText, summaryText, useLlm })`.
5. **`backend/app/services/groq_service.py` & `docker-compose.yml`**:
   - Defect: Inside the Linux Docker container on institutional SSL-inspected networks, Groq API requests failed with `APIConnectionError: [SSL: CERTIFICATE_VERIFY_FAILED]` because `docker/certs/sophos-ca.pem` was neither mounted into the container nor loaded into the `httpx` SSL context.
   - Resolution: Mounted `./docker/certs:/app/certs:ro` in `docker-compose.yml` and updated `get_groq_client()` to load custom CA bundles (`/app/certs/sophos-ca.pem`, `docker/certs/sophos-ca.pem`, `SSL_CERT_FILE`, `REQUESTS_CA_BUNDLE`) when present.
6. **`backend/app/services/file_service.py`**:
   - Defect: `extract_pdf()` opened PDF files directly by path (`fitz.open(file_path)`). When a corrupted PDF failed inside `fitz.open.__init__`, PyMuPDF left an OS file handle open in the exception traceback on Windows, causing `os.remove(file_path)` in `finally:` to raise `PermissionError: [WinError 32]` (HTTP 500 instead of HTTP 400).
   - Resolution: Read file bytes via `with open(file_path, "rb")` first and pass `stream=pdf_bytes, filetype="pdf"` to `fitz.open()`, guaranteeing immediate OS file-handle closure.
7. **`backend/app/api/summarize.py`**:
   - Defect: In `/key-points`, `line.lstrip("0123456789.-) ")` stripped leading numbers, years, and percentages from the content of extracted key points (e.g., `"1. 2025 revenue..."` -> `"revenue..."`) and did not strip `*` or `•` bullet markers.
   - Resolution: Replaced character-set `lstrip` with regex prefix stripping `r"^(?:\s*(?:\d+[.)]|[-*•])\s+)+"`.
8. **`backend/app/services/faithfulness_service.py`**:
   - Defect: `clean_sentence_for_claim()` used `re.sub(r"^[\s*•\-\d\.\)\#]+", "", cleaned)`, stripping leading quantities/years from summary claims (e.g., `"- 99 regional data centers..."` -> `"regional data centers..."`), which prevented both faithfulness and contradiction engines from detecting numerical/percentage conflicts at the start of a claim.
   - Resolution: Updated `clean_sentence_for_claim()` to strip only markdown header/list prefixes (`r"^(?:\s*(?:#+\s+|[-*•]\s+|\d+[.)]\s+))+"`) and normalize Unicode narrow no-break spaces/hyphens and bold markers.
9. **`backend/app/core/config.py` & `backend/main.py`**:
   - Defect: `config.py` loaded `backend/.env` before project root `.env`, allowing a stale `backend/.env` key to shadow the valid root `.env` key; `custom_openapi()` in `main.py` omitted `/check-faithfulness` and `/check-contradictions` from OpenAPI 3.0.3 binary upload schema normalization.
   - Resolution: Prioritized `_root_dir / ".env"` in `config.py` and added `/check-faithfulness` and `/check-contradictions` (plus `anyOf` cleanup) to `_enforce_binary_field()` in `main.py`.
10. **`backend/app/services/groq_service.py` & `backend/app/api/summarize.py`**:
    - Defect: `/compare` and `/update-summary` lacked context safety character guards (unlike `/summarize`), allowing oversized inputs (>60,000 characters) to be sent directly to Groq, triggering rate limits/TPM exhaustion (`Error code: 413`) and unhandled HTTP 500 errors.
    - Resolution: Added explicit context safety validations (`len > 60000`) raising `ValueError` (mapped to HTTP 400), updated endpoint OpenAPI documentation with context constraints, and added regression tests.
11. **`backend/app/services/groq_service.py`**:
    - Defect: Comparing identical documents or requesting an update summary with identical text invoked external LLM calls, incurring unnecessary latency, token consumption, and risk of slight non-deterministic paraphrasing.
    - Resolution: Implemented deterministic fast-paths for identical content in both `compare_documents()` and `update_summary()`, instantly returning structured zero-difference reports without LLM invocations.
    - Defect: Delta and comparison prompts did not explicitly enforce contrast format for conflicting numerical metrics, percentages, dates, and currency amounts or guide classification of semantic paraphrasing.
    - Resolution: Enhanced prompt rules in `compare_documents` to explicitly highlight factual contradictions under 'Differences' and semantic equivalence under 'Similarities'; enhanced `update_summary` prompt to contrast old vs. new values for numerical/date changes and categorize paraphrasing under 'Unchanged Information'.
12. **`frontend/src/components/SummaryResult.jsx` & `frontend/src/index.css`**:
    - Defect: `SummaryResult` rendered markdown headers (`# `, `## `) and delta/comparison section titles (`New Information:`, `Similarities:`, etc.) as plain paragraph text, making analytical reports hard to scan.
    - Resolution: Added header parser and pill badges for structured section titles with `.summary-section-heading` and `.section-title-pill` styling in `index.css`.

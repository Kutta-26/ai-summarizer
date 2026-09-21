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

### Overall Result: 32/32 Automated Tests Passing — 100% Success Rate

| Test Suite | Endpoint / Component | Test Case | Status | Notes |
| :--- | :--- | :--- | :---: | :--- |
| **System** | `GET /` | Root Welcome Endpoint | **PASS** | Returns `{"message": "Welcome to AI Summarizer API"}` with HTTP 200 |
| **System** | `GET /health` | Service Heartbeat | **PASS** | Returns `{"status":"Running"}` with HTTP 200 |
| **System** | `GET /docs` | Swagger UI API Documentation | **PASS** | Interactive OpenAPI documentation rendered successfully |
| **System** | `GET /openapi.json` | OpenAPI Specification | **PASS** | Schema validated with 10 registered paths |
| **CORS** | `OPTIONS /summarize` | CORS Preflight Handling | **PASS** | `access-control-allow-origin` header verified |
| **Observability** | `GET /health` | Latency Header (`X-Process-Time`) | **PASS** | Latency header verified |
| **Document Parsers** | `file_service.extract_text` | PDF PyMuPDF Extraction | **PASS** | Successfully parsed 4,012 characters from sample PDF |
| **Document Parsers** | `file_service.extract_text` | DOCX python-docx Extraction | **PASS** | Successfully parsed 19,286 characters from sample DOCX |
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
| **Error Handling** | `POST /summarize-hierarchical` | Invalid chunk-size boundary | **PASS** | HTTP 400: chunk-size validation |
| **Error Handling** | `POST /summarize-media` | Non-media extension | **PASS** | HTTP 400: media extension validation |
| **Single Document** | `POST /summarize` | `document_a.txt` | **PASS** | HTTP 200: valid Groq-generated summary |
| **Key Points** | `POST /key-points` | `keypoints_test.txt` | **PASS** | HTTP 200: requested key points returned |
| **Multi-Document** | `POST /summarize-multiple` | `document_a.txt` + `document_b.txt` | **PASS** | HTTP 200: multi-document synthesis |
| **Compare** | `POST /compare` | `compare_a.txt` vs `compare_b.txt` | **PASS** | HTTP 200: comparative report |
| **Update Summary** | `POST /update-summary` | Previous summary vs current text | **PASS** | HTTP 200: delta analysis |
| **Hierarchical** | `POST /summarize-hierarchical` | Concurrent Map-Reduce pipeline | **PASS** | HTTP 200: section synthesis + master summary |
| **Media Pipeline** | `POST /summarize-media` | `voice_test.mp3` | **PASS** | HTTP 200: FFmpeg + Whisper + Groq pipeline |

---

## 3. Production Build Verification

The React frontend was compiled successfully using Vite.

- **Vite Version**: 5.4.21
- **Modules Transformed**: 1,844
- **Build Status**: 0 errors, 0 warnings
- **Recorded Build Time**: approximately 1.64 seconds
- **`dist/index.html`**: 0.81 kB, gzip 0.45 kB
- **CSS Bundle**: 17.24 kB, gzip 3.64 kB
- **JavaScript Bundle**: 195.88 kB, gzip 57.80 kB

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

The Docker configuration was initially statically audited and subsequently validated through actual runtime execution.

The following were successfully verified:

- Docker image builds
- Backend container startup
- Frontend container startup
- Backend health check
- Frontend health check
- Document summarization through Docker
- Media summarization through Docker
- Persistent upload volume
- Container restart and recovery

**Final status: VERIFIED.**

---

## 6. Docker Runtime Verification

Docker deployment was fully exercised rather than only statically inspected.

### Docker Environment

- **Docker Engine**: 29.8.0
- **Docker Compose**: 5.5.1
- **Runtime**: Docker Desktop Linux containers through WSL2
- **Docker Context**: `desktop-linux`

### Backend Container

- Backend image built successfully.
- Backend container started successfully.
- Backend container reached `healthy` status.
- `GET /health` returned HTTP 200.
- FastAPI was accessible through published port `8000`.

Final backend state:

```text
ai-summarizer-backend    Up (healthy)
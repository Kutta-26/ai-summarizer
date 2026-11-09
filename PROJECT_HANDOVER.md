# AI Summarizer — Project Handover & Release Validation

**Document Version:** 1.0.0
**Release Target:** v1.0 Production Release
**Release Checkpoint Commit:** `8401532`
**Date:** November 2026
**Audience:** Development, QA, Operations, and Maintenance Teams

---

## 1. Project Overview

**AI Summarizer** is an enterprise-grade document, audio, video, and YouTube intelligence and synthesis platform. It is engineered to accept diverse source material (structured documents, multimedia speech, and video captions) and distill it into structured, controllable, and hallucination-resistant summaries.

### Primary Capabilities
- Multi-format ingestion: `.txt`, `.pdf` (PyMuPDF), `.docx` (python-docx), `.mp3`, `.wav`, `.m4a`, `.mp4`, `.mkv`, `.webm`, and YouTube video URLs.
- Granular control over summary length (`short`, `medium`, `long`), presentation format (`paragraph`, `bullets`, `table`), and executive briefings.
- Deep document intelligence: Salient key takeaways, dual-document side-by-side comparison, delta/update summaries, and Map-Reduce hierarchical long-form synthesis.
- Quality & verification pipelines: Heuristic importance scoring, near-duplicate redundancy filtering, deterministic faithfulness checking, and contradiction detection.

---

## 2. Architecture & Technology Stack

```mermaid
flowchart TD
    User([User Browser]) <--> Frontend[React 18 + Vite SPA\nNginx Docker :3000 / Vite :5173]
    Frontend <-->|REST API / Form-Data| Backend[FastAPI Application\nUvicorn :8000]

    Backend --> Parsers[Text Extractors\nPyMuPDF | python-docx | UTF-8]
    Backend --> Media[Media Engine\nFFmpeg CLI + faster-whisper INT8]
    Backend --> YouTube[Caption Extractor\nyoutube-transcript-api]

    Parsers --> LLMService[Groq Cloud LLM Service\nopenai/gpt-oss-20b]
    Media --> LLMService
    YouTube --> LLMService

    LLMService --> Guardrails[Verification Pipelines\nImportance | Redundancy | Faithfulness | Contradiction]
    Guardrails --> Response[Standardized JSON Response\nX-Process-Time | X-Request-ID]
```

### Technology Matrix
| Layer | Technologies | Role |
|:---|:---|:---|
| **Frontend** | React 18, Vite 5, Lucide React | SPA interface with real-time health monitoring and dark theme design |
| **Backend API** | Python 3.11, FastAPI 0.141, Starlette, Uvicorn | Async HTTP API, streaming upload guards, OpenAPI 3.0.3 contract |
| **Document Processing** | PyMuPDF 1.28, python-docx 1.2 | Local PDF text/metadata extraction and Word DOCX parsing |
| **Media Processing** | FFmpeg CLI, faster-whisper 1.2, CTranslate2 | Native audio demuxing and offline CPU speech transcription (INT8) |
| **LLM Inference** | Groq Cloud SDK (`groq` 1.6), `openai/gpt-oss-20b` | High-speed structured inference with exponential backoff & retry |
| **Containerization** | Docker Engine, Docker Compose, Nginx Alpine | Multi-stage production container images with isolated bridge network |
| **Testing** | pytest 9.1, Playwright 1.64, TestClient | Unit, regression, security, contract, and browser E2E test suites |

---

## 3. Feature-Completeness Matrix

| # | Feature | Frontend Component | Backend Endpoint / Service | Automated Test Evidence | Verification Status |
|:---:|:---|:---|:---|:---|:---:|
| 1 | Single-document summarization | `SingleSummarizer.jsx` | `POST /summarize` (`groq_service.py`) | `test_core_summarization.py`, `summarizer.spec.js` #2 | **Verified** |
| 2 | Multi-document summarization | `MultiSummarizer.jsx` | `POST /summarize-multiple` | `test_advanced_features.py`, `test_suite.py` #7 | **Verified** |
| 3 | Summary length control | Pill selectors across all tabs | `length: short\|medium\|long` | `test_core_summarization.py::test_summarize_lengths` | **Verified** |
| 4 | Output formats (paragraph/bullet/table) | Pill selectors & `SummaryResult.jsx` | `format: paragraph\|bullets\|table` | `test_core_summarization.py`, `summarizer.spec.js` #4 | **Verified** |
| 5 | Key-point extraction | `KeyPointsTab.jsx` | `POST /key-points` | `test_core_summarization.py`, `summarizer.spec.js` #9 | **Verified** |
| 6 | Executive summary | Checkbox toggle across tabs | `executive: bool` | `test_core_summarization.py::test_summarize_executive_mode` | **Verified** |
| 7 | Audio summarization | `MediaSummarizer.jsx` | `POST /summarize-media` | `test_advanced_features.py`, `test_suite.py` #9 | **Verified** |
| 8 | Video summarization | `MediaSummarizer.jsx` | `POST /summarize-media` (`media_service.py`) | `test_regression_coverage.py::test_transcribe_media_video_vs_audio_routing` | **Verified** |
| 9 | Comparative summarization | `CompareTab.jsx` | `POST /compare` | `test_advanced_features.py`, `summarizer.spec.js` #10 | **Verified** |
| 10 | Update/delta summaries | `UpdateSummaryTab.jsx` | `POST /update-summary` | `test_advanced_features.py`, `test_regression_coverage.py` | **Verified** |
| 11 | Hierarchical Map-Reduce summarization | `HierarchicalSummarizer.jsx` | `POST /summarize-hierarchical` | `test_advanced_features.py`, `test_faithfulness.py` | **Verified** |
| 12 | LLM API integration | Status badge, timing & tokens | `backend/app/services/groq_service.py` | `test_api_reliability.py` (11 tests), `test_security_hardening.py` | **Verified** |
| 13 | YouTube transcript summarization | `YouTubeSummarizer.jsx` | `POST /summarize-youtube` | `test_advanced_features.py`, `test_suite.py` #12 | **Verified** |
| 14 | Podcast/audio support | `MediaSummarizer.jsx` | `POST /summarize-media` | `test_advanced_features.py::test_media_file_validation` | **Verified** |
| 15 | Negative & boundary input handling | FileUpload & alert banners | Streaming 10MB guard, 60k char limit, 400/413/422 | `test_core_summarization.py`, `test_security_hardening.py` | **Verified** |

---

## 4. Repository & Release Checkpoint

- **Git Repository:** `https://github.com/Kutta-26/ai-summarizer`
- **Active Branch:** `main`
- **Baseline Checkpoint Commit:** `8401532` (`security(release): audit production configuration and harden verified gaps`)
- **Working Tree State:** Clean, all tests passing.

---

## 5. Local Development Setup

### Prerequisites
- Python 3.11+
- Node.js 18+ (Node 20+ recommended)
- FFmpeg CLI installed and available in system `PATH`
- Active Groq Cloud API Key ([console.groq.com](https://console.groq.com))

### Backend Setup
```powershell
# In project root:
.\.venv\Scripts\Activate.ps1
pip install -r backend/requirements.txt
Copy-Item backend\.env.example backend\.env
# Populate GROQ_API_KEY inside backend\.env

# Run FastAPI Development Server:
cd backend
..\.venv\Scripts\python.exe -m uvicorn main:app --host 127.0.0.1 --port 8000 --reload
```

### Frontend Setup
```powershell
cd frontend
npm install
npm run dev
# Accessible at http://localhost:5173
```

---

## 6. Docker Deployment Instructions

The repository includes multi-stage containerization with health checks and volume persistence:

```bash
# Build and launch all services in detached mode
docker compose up -d --build

# Verify container statuses
docker compose ps

# Inspect container logs
docker compose logs -f backend
docker compose logs -f frontend

# Graceful shutdown
docker compose down

# Stop containers without destroying volume data
docker compose stop
```

**Deployed Container Endpoints:**
- Frontend Web Application: `http://localhost:3000`
- Backend API & Health Check: `http://localhost:8000/health`
- Interactive OpenAPI Swagger UI: `http://localhost:8000/docs`

---

## 7. Environment Configuration Variables

> [!IMPORTANT]
> Never commit actual credentials or `.env` files into source control. All variables must be populated through deployment environment configurations or ignored `.env` files.

| Variable Name | Required | Default Value | Description |
|:---|:---:|:---|:---|
| `GROQ_API_KEY` | **Yes** | *None* | Groq Cloud API authentication key |
| `GROQ_MODEL` | No | `openai/gpt-oss-20b` | Groq LLM model identifier |
| `MAX_FILE_SIZE` | No | `10485760` (10 MB) | Maximum upload file limit in bytes |
| `REQUEST_TIMEOUT` | No | `60.0` | HTTP request timeout to Groq API in seconds |
| `WHISPER_MODEL_SIZE` | No | `small` | faster-whisper speech recognition model size |
| `WHISPER_CACHE_DIR` | No | *System default* | HuggingFace model cache directory override |
| `CORS_ORIGINS` | No | `http://localhost:5173,...` | Comma-separated list of allowed web origins |
| `VITE_API_BASE_URL` | No | `http://127.0.0.1:8000` | Backend API base URL consumed by Vite frontend |

---

## 8. Test Execution Commands & Verified Results

### Verified Test Evidence

| Test Suite | Command | Total | Passed | Failed | Skipped | Duration |
|:---|:---|---:|---:|---:|---:|---:|
| **Pytest Backend Unit Tests** | `.\.venv\Scripts\python.exe -m pytest` | 135 | 135 | 0 | 0 | 3.63s |
| **CI Regression Test Suite** | `.\.venv\Scripts\python.exe tests\test_suite.py --ci` | 55 | 55 | 0 | 0 | 20.6s |
| **Frontend Playwright E2E** | `npm --prefix frontend run test:e2e` | 11 | 10 | 0 | 1 | 24.0s |
| **Frontend Vite Production Build** | `npm --prefix frontend run build` | 1844 modules | 0 errors | 0 errors | 0 | 2.57s |

*Note on Skipped Test:* `live-summarizer.spec.js` is deliberately skipped in local offline test runs when `LIVE_E2E` is not set to `true`, preventing unintended token spend during standard CI runs.

---

## 9. Known Limitations

1. **YouTube Subtitle Dependency:** The `/summarize-youtube` endpoint relies on publicly accessible captions/transcripts. Videos without subtitles, restricted content, or geoblocked videos will return HTTP 400.
2. **Audio File Size and CPU Inference:** Video and audio files larger than 10 MB or containing extensive speech can take 15–45 seconds to transcribe on CPU-only instances. High-volume production deployments should leverage GPU acceleration (`device="cuda"`).
3. **Single-Pass Context Window:** Single-document summarization (`/summarize`) enforces a strict 60,000 character limit (~15,000 words). Documents exceeding this limit must use the Map-Reduce `/summarize-hierarchical` endpoint.
4. **Local Network Docker Access:** In local development on Windows, containers bind to `127.0.0.1`. When running in sandboxed or isolated enterprise network environments, loopback permissions must be appropriately configured.

---

## 10. Future Recommendations

1. **Asynchronous Task Queue:** For audio/video files exceeding 5 minutes or documents over 100 pages, transition from synchronous HTTP request/response to background task processing using Celery or Redis with WebSocket progress updates.
2. **User Authentication & Quota Management:** Implement OAuth2 / JWT authentication with per-user rate limits and token tracking to prevent abuse of upstream Groq API quotas.
3. **Multi-Model Fallback:** Introduce secondary LLM provider routing (e.g. Google Gemini or Anthropic Claude) in `groq_service.py` to seamlessly handle Groq Cloud outages or regional rate limits.
4. **Enhanced OCR for Scanned Documents:** Integrate Tesseract or AWS Textract for scanned PDFs containing images rather than native text streams.

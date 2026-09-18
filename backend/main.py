from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.openapi.utils import get_openapi

import time
from app.core.config import CORS_ORIGINS, UPLOAD_DIR
from app.core.logging_config import get_logger
from app.api.summarize import router as summarize_router
from app.schemas.summarize import MessageResponse, HealthResponse

logger = get_logger("http")

# ============================================================
# SWAGGER TAGS & API METADATA
# ============================================================

TAGS_METADATA = [
    {
        "name": "System",
        "description": "System health, connectivity, and heartbeat monitoring endpoints."
    },
    {
        "name": "Document Summarization",
        "description": "Core document summarization engines supporting single documents, multi-document cross-synthesis, and Map-Reduce hierarchical long-form synthesis."
    },
    {
        "name": "Analysis & Extraction",
        "description": "Specialized analytical endpoints including key-point extraction, side-by-side document comparison, and delta change detection."
    },
    {
        "name": "Media & Video",
        "description": "Multimodal speech and video pipelines supporting offline faster-whisper transcription and direct YouTube caption extraction."
    }
]

API_DESCRIPTION = """
# AI Summarizer API

Welcome to the **AI Summarizer** developer API documentation.

AI Summarizer is a production-grade multi-modal document, audio, video, and YouTube intelligence platform powered by **FastAPI**, **Groq Cloud LLM** (`openai/gpt-oss-20b`), **PyMuPDF**, **python-docx**, local **faster-whisper** transcription, and **FFmpeg**.

---

## 🌟 Key Capabilities
- **Document Summarization**: Single-document (`/summarize`), multi-document cross-synthesis (`/summarize-multiple`), and Map-Reduce hierarchical synthesis (`/summarize-hierarchical`).
- **Granular Controls**: Target length (`short`, `medium`, `long`), presentation format (`paragraph`, `bullets`, `table`), and executive briefings.
- **Deep Document Analytics**: Salient key takeaway extraction (`/key-points`), comparative dual-document analysis (`/compare`), and delta change detection (`/update-summary`).
- **Multimodal Intelligence**: Audio/video transcription & summarization (`/summarize-media`), and YouTube caption extraction (`/summarize-youtube`).

---

## 📋 Input & Upload Constraints
- **Document Formats**: `.txt`, `.pdf`, `.docx`
- **Media Formats**: `.mp3`, `.wav`, `.m4a`, `.mp4`, `.mkv`, `.mov`, `.webm`, `.avi`, `.flac`, `.ogg`
- **Maximum File Size**: **10 MB** (enforced with chunked streaming validation)
- **Context Limit**: Single-pass endpoints accept up to 60,000 characters. For larger documents, use `/summarize-hierarchical`.

---

## ⏱ Observability
Every HTTP response returns an execution latency header: `X-Process-Time`.
"""

# ============================================================
# FASTAPI APPLICATION
# ============================================================

app = FastAPI(
    title="AI Summarizer API",
    description=API_DESCRIPTION,
    version="1.0.0",
    openapi_version="3.0.3",
    openapi_tags=TAGS_METADATA,
)


# ============================================================
# OBSERVABILITY & TIMING MIDDLEWARE
# ============================================================

@app.middleware("http")
async def record_process_time(request: Request, call_next):
    """
    Measures and logs endpoint execution latency, and injects
    the standard X-Process-Time header into the HTTP response.
    """
    start_time = time.perf_counter()
    response = await call_next(request)
    duration = time.perf_counter() - start_time
    response.headers["X-Process-Time"] = f"{duration:.4f}s"
    logger.info(f"{request.method} {request.url.path} -> {response.status_code} ({duration * 1000.0:.1f}ms)")
    return response


# ============================================================
# CORS CONFIGURATION
# ============================================================

# Starlette CORS requires allow_credentials=False when using wildcard origins
allow_creds = "*" not in CORS_ORIGINS

app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ORIGINS,
    allow_credentials=allow_creds,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ============================================================
# LIFECYCLE / CLEANUP
# ============================================================

@app.on_event("startup")
def cleanup_orphaned_uploads():
    """
    Remove orphaned temporary files in the uploads directory
    older than 1 hour on server startup.
    """
    try:
        now = time.time()
        if UPLOAD_DIR.exists():
            for item in UPLOAD_DIR.iterdir():
                if item.is_file() and (now - item.stat().st_mtime > 3600):
                    try:
                        item.unlink()
                    except OSError:
                        pass
    except Exception:
        pass



# ============================================================
# REGISTER ROUTES
# ============================================================

app.include_router(summarize_router)


# ============================================================
# HOME
# ============================================================

@app.get(
    "/",
    response_model=MessageResponse,
    tags=["System"],
    summary="API Root Welcome",
    description="Welcome endpoint verifying that the AI Summarizer API is operational and accessible.",
    response_description="Root welcome message payload",
    responses={
        200: {"description": "Service is reachable and operational."}
    }
)
def home():
    return {
        "message": "Welcome to AI Summarizer API"
    }


# ============================================================
# HEALTH CHECK
# ============================================================

@app.get(
    "/health",
    response_model=HealthResponse,
    tags=["System"],
    summary="Service Health Check",
    description="Heartbeat endpoint reporting the current operational status of the service along with the `X-Process-Time` latency header.",
    response_description="Service availability status",
    responses={
        200: {"description": "Service heartbeat is running normally."}
    }
)
def health():
    return {
        "status": "Running"
    }


# ============================================================
# CUSTOM OPENAPI
# ============================================================

def custom_openapi():

    if app.openapi_schema:
        return app.openapi_schema

    # Generate standard OpenAPI schema with configured tags and descriptions
    openapi_schema = get_openapi(
        title=app.title,
        version=app.version,
        description=app.description,
        routes=app.routes,
        tags=TAGS_METADATA,
    )

    # Force OpenAPI 3.0.3 specification standard
    openapi_schema["openapi"] = "3.0.3"

    # --------------------------------------------------------
    # Get all component schemas
    # --------------------------------------------------------

    schemas = (
        openapi_schema
        .get("components", {})
        .get("schemas", {})
    )

    def _enforce_binary_field(schema_name: str, field_name: str, is_array: bool = False, description: str = None):
        target_schema = schemas.get(schema_name)
        if not target_schema:
            return
        properties = target_schema.get("properties", {})
        if field_name not in properties:
            properties[field_name] = {}
        prop = properties[field_name]
        prop.pop("contentMediaType", None)
        if is_array:
            prop["type"] = "array"
            prop["items"] = {"type": "string", "format": "binary"}
        else:
            prop["type"] = "string"
            prop["format"] = "binary"
        if description and not prop.get("description"):
            prop["description"] = description

    # ========================================================
    # 1. /summarize
    # ========================================================
    _enforce_binary_field(
        "Body_summarize_summarize_post",
        "file",
        description="Document file to summarize (.txt, .pdf, or .docx, max 10 MB)"
    )

    # ========================================================
    # 2. /summarize-multiple
    # ========================================================
    _enforce_binary_field(
        "Body_summarize_multiple_summarize_multiple_post",
        "files",
        is_array=True,
        description="Array of document files to synthesize (.txt, .pdf, or .docx, max 10 MB each)"
    )

    # ========================================================
    # 3. /key-points
    # ========================================================
    _enforce_binary_field(
        "Body_key_points_key_points_post",
        "file",
        description="Document file to extract key takeaways from (.txt, .pdf, or .docx, max 10 MB)"
    )

    # ========================================================
    # 4. /compare
    # ========================================================
    _enforce_binary_field(
        "Body_compare_compare_post",
        "file_a",
        description="First document to compare (.txt, .pdf, or .docx, max 10 MB)"
    )
    _enforce_binary_field(
        "Body_compare_compare_post",
        "file_b",
        description="Second document to compare (.txt, .pdf, or .docx, max 10 MB)"
    )

    # ========================================================
    # 5. /summarize-hierarchical
    # ========================================================
    _enforce_binary_field(
        "Body_summarize_hierarchical_endpoint_summarize_hierarchical_post",
        "file",
        description="Document file (TXT, PDF, DOCX) to summarize hierarchically (max 10 MB)"
    )

    # ========================================================
    # 6. /summarize-media
    # ========================================================
    _enforce_binary_field(
        "Body_summarize_media_summarize_media_post",
        "file",
        description="Audio or video file (.mp3, .wav, .m4a, .mp4, .mkv, .mov, .webm, .avi, .flac, .ogg, max 10 MB)"
    )

    # ========================================================
    # Save schema
    # ========================================================

    app.openapi_schema = openapi_schema

    return app.openapi_schema


# ============================================================
# REGISTER CUSTOM OPENAPI
# ============================================================

app.openapi = custom_openapi
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.openapi.utils import get_openapi

import time
from app.core.config import CORS_ORIGINS, UPLOAD_DIR
from app.core.logging_config import get_logger
from app.api.summarize import router as summarize_router

logger = get_logger("http")

# ============================================================
# FASTAPI APPLICATION
# ============================================================

app = FastAPI(
    title="AI Summarizer API",
    version="1.0.0",
    openapi_version="3.0.3",
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

@app.get("/")
def home():
    return {
        "message": "Welcome to AI Summarizer API"
    }


# ============================================================
# HEALTH CHECK
# ============================================================

@app.get("/health")
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

    # Generate normal OpenAPI schema
    openapi_schema = get_openapi(
        title="AI Summarizer API",
        version="1.0.0",
        description="API for AI-powered document summarization",
        routes=app.routes,
    )

    # Force OpenAPI 3.0.3
    openapi_schema["openapi"] = "3.0.3"

    # --------------------------------------------------------
    # Get all schemas
    # --------------------------------------------------------

    schemas = (
        openapi_schema
        .get("components", {})
        .get("schemas", {})
    )

    # ========================================================
    # 1. /summarize
    # ========================================================

    summarize_schema = schemas.get(
        "Body_summarize_summarize_post"
    )

    if summarize_schema:

        properties = summarize_schema.get(
            "properties", {}
        )

        # Single uploaded file
        properties["file"] = {
            "type": "string",
            "format": "binary"
        }

    # ========================================================
    # 2. /summarize-multiple
    # ========================================================

    multiple_schema = schemas.get(
        "Body_summarize_multiple_summarize_multiple_post"
    )

    if multiple_schema:

        properties = multiple_schema.get(
            "properties", {}
        )

        # Multiple uploaded files
        properties["files"] = {
            "type": "array",
            "items": {
                "type": "string",
                "format": "binary"
            }
        }

    # ========================================================
    # 3. /key-points
    # ========================================================

    key_points_schema = schemas.get(
        "Body_key_points_key_points_post"
    )

    if key_points_schema:

        properties = key_points_schema.get(
            "properties", {}
        )

        # Single uploaded file
        properties["file"] = {
            "type": "string",
            "format": "binary"
        }

    # ========================================================
    # 4. /compare
    # ========================================================

    compare_schema = schemas.get(
        "Body_compare_compare_post"
    )

    if compare_schema:

        properties = compare_schema.get(
            "properties", {}
        )

        # First document
        properties["file_a"] = {
            "type": "string",
            "format": "binary"
        }

        # Second document
        properties["file_b"] = {
            "type": "string",
            "format": "binary"
        }

    # ========================================================
    # 5. /summarize-hierarchical
    # ========================================================

    hierarchical_schema = schemas.get(
        "Body_summarize_hierarchical_endpoint_summarize_hierarchical_post"
    )

    if hierarchical_schema:

        properties = hierarchical_schema.get(
            "properties", {}
        )

        # Single uploaded file
        properties["file"] = {
            "type": "string",
            "format": "binary"
        }

    # ========================================================
    # Save schema
    # ========================================================

    app.openapi_schema = openapi_schema

    return app.openapi_schema


# ============================================================
# REGISTER CUSTOM OPENAPI
# ============================================================

app.openapi = custom_openapi
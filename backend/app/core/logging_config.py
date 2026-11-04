import os
import logging
import sys
import contextvars
from typing import Optional

# ============================================================
# STRUCTURED OBSERVABILITY LOGGING & CORRELATION IDS
# ============================================================

LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO").upper()

request_id_ctx: contextvars.ContextVar[Optional[str]] = contextvars.ContextVar("request_id", default=None)


def set_request_id(req_id: str):
    """Set the current asynchronous task's request correlation ID."""
    return request_id_ctx.set(req_id)


def get_request_id() -> Optional[str]:
    """Retrieve the current request correlation ID if inside an active request."""
    return request_id_ctx.get(None)


class RequestIdFilter(logging.Filter):
    """Injects active request correlation ID into the log record."""
    def filter(self, record: logging.LogRecord) -> bool:
        req_id = request_id_ctx.get(None)
        record.req_id_prefix = f"[{req_id}] " if req_id else ""
        return True


_formatter = logging.Formatter(
    fmt="[%(asctime)s] [%(levelname)s] [%(name)s]: %(req_id_prefix)s%(message)s",
    datefmt="%Y-%m-%d %H:%M:%S"
)

# Standard stdout stream handler
_handler = logging.StreamHandler(sys.stdout)
_handler.setFormatter(_formatter)
_handler.addFilter(RequestIdFilter())

# Configure root logger
_root_logger = logging.getLogger("ai_summarizer")
_root_logger.setLevel(getattr(logging, LOG_LEVEL, logging.INFO))
if not _root_logger.handlers:
    _root_logger.addHandler(_handler)


def get_logger(name: str) -> logging.Logger:
    """
    Returns a configured logger for the given module or component name.
    """
    return logging.getLogger(f"ai_summarizer.{name}")


def sanitize_filename(filename: str) -> str:
    """
    Sanitize uploaded filenames for safe logging without exposing path artifacts
    or allowing log/CRLF injection.
    """
    if not filename:
        return "<unnamed>"
    import re
    # Normalize cross-platform separators and extract base filename
    safe = os.path.basename(str(filename).replace("\\", "/"))
    # Strip ASCII control characters and non-printable sequences
    safe = re.sub(r"[\r\n\x00-\x1f\x7f-\x9f]", "", safe).strip()
    return safe or "<unnamed>"

import os
import logging
import sys

# ============================================================
# STRUCTURED OBSERVABILITY LOGGING
# ============================================================

LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO").upper()

_formatter = logging.Formatter(
    fmt="[%(asctime)s] [%(levelname)s] [%(name)s]: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S"
)

# Standard stdout stream handler
_handler = logging.StreamHandler(sys.stdout)
_handler.setFormatter(_formatter)

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
    Sanitize uploaded filenames for safe logging without exposing path artifacts.
    """
    if not filename:
        return "<unnamed>"
    return os.path.basename(filename)

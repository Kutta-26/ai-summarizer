import os
import time
from app.core.logging_config import get_logger, sanitize_filename

try:
    import pymupdf as fitz
except ImportError:
    import fitz  # PyMuPDF fallback
from docx import Document

logger = get_logger("file")


def extract_text(file_path: str) -> str:
    """
    Detects the file type, measures extraction latency, and extracts text.
    """
    start_t = time.perf_counter()
    lower_path = file_path.lower()
    safe_name = sanitize_filename(file_path)

    if lower_path.endswith(".txt"):
        text = extract_txt(file_path)
        ftype = "TXT"
    elif lower_path.endswith(".pdf"):
        text = extract_pdf(file_path)
        ftype = "PDF"
    elif lower_path.endswith(".docx"):
        text = extract_docx(file_path)
        ftype = "DOCX"
    else:
        raise ValueError(
            f"Unsupported file format for '{safe_name}'. "
            "Supported formats are TXT, PDF, and DOCX."
        )

    elapsed_ms = (time.perf_counter() - start_t) * 1000.0
    logger.info(f"Extracted {len(text)} characters from {ftype} ({safe_name}) in {elapsed_ms:.1f}ms")
    return text


def extract_txt(file_path: str) -> str:
    """
    Extract text from a TXT file with multiple encoding fallbacks.
    """
    # Try standard UTF-8 first
    try:
        with open(file_path, "r", encoding="utf-8") as file:
            return file.read()
    except UnicodeDecodeError:
        pass

    # Fallback to latin-1 / Windows ANSI
    try:
        with open(file_path, "r", encoding="latin-1") as file:
            return file.read()
    except UnicodeDecodeError:
        pass

    # Safe replace fallback
    with open(file_path, "r", encoding="utf-8", errors="replace") as file:
        return file.read()


def extract_pdf(file_path: str) -> str:
    """
    Extract text from a PDF file using PyMuPDF (with safe context manager).
    Reads into memory stream first so OS file handles are never left open on Windows if parsing fails.
    """
    try:
        with open(file_path, "rb") as pdf_file:
            pdf_bytes = pdf_file.read()
        with fitz.open(stream=pdf_bytes, filetype="pdf") as document:
            if document.is_encrypted:
                raise ValueError(
                    "The uploaded PDF is password-protected or encrypted. "
                    "Please provide an unencrypted document."
                )
            text_parts = []
            for page in document:
                page_text = page.get_text()
                if page_text and page_text.strip():
                    text_parts.append(page_text.strip())
            return "\n\n".join(text_parts)
    except ValueError:
        raise
    except Exception as e:
        import re
        clean_msg = re.sub(r"['\"][^'\"]*[\\/][^'\"]*['\"]", "'<document>'", str(e))
        raise ValueError(f"Failed to extract text from PDF: {clean_msg}") from e


def extract_docx(file_path: str) -> str:
    """
    Extract text from a DOCX file including paragraphs and tables.
    """
    try:
        document = Document(file_path)
        text_parts = []

        for paragraph in document.paragraphs:
            if paragraph.text.strip():
                text_parts.append(paragraph.text)

        # Also extract text from any tables in the document
        for table in document.tables:
            for row in table.rows:
                row_text = " | ".join(cell.text.strip() for cell in row.cells if cell.text.strip())
                if row_text:
                    text_parts.append(row_text)

        return "\n".join(text_parts)
    except Exception as e:
        import re
        clean_msg = re.sub(r"['\"][^'\"]*[\\/][^'\"]*['\"]", "'<document>'", str(e))
        raise ValueError(f"Failed to extract text from DOCX: {clean_msg}") from e
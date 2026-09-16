import os

try:
    import pymupdf as fitz
except ImportError:
    import fitz  # PyMuPDF fallback
from docx import Document


def extract_text(file_path: str) -> str:
    """
    Detects the file type and extracts text.
    """
    lower_path = file_path.lower()

    if lower_path.endswith(".txt"):
        return extract_txt(file_path)

    elif lower_path.endswith(".pdf"):
        return extract_pdf(file_path)

    elif lower_path.endswith(".docx"):
        return extract_docx(file_path)

    else:
        raise ValueError(
            f"Unsupported file format for '{os.path.basename(file_path)}'. "
            "Supported formats are TXT, PDF, and DOCX."
        )


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
    """
    try:
        with fitz.open(file_path) as document:
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
        raise ValueError(f"Failed to extract text from PDF: {str(e)}") from e


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
        raise ValueError(f"Failed to extract text from DOCX: {str(e)}") from e
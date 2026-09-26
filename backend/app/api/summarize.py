from fastapi import APIRouter, UploadFile, File, Form, HTTPException
from typing import Literal, Annotated, Optional

from app.core.config import MAX_FILE_SIZE, UPLOAD_DIR

from app.schemas.summarize import (
    SummaryResponse,
    KeyPointsResponse,
    HierarchicalSummaryResponse,
    FaithfulnessResult,
    ErrorResponse
)

from app.services.file_service import extract_text

from app.services.faithfulness_service import check_faithfulness

from app.services.groq_service import (
    summarize_text,
    extract_key_points,
    compare_documents,
    update_summary,
    hierarchical_summarize
)

from app.services.media_service import (
    validate_media_file,
    transcribe_media
)

from app.services.youtube_service import fetch_youtube_transcript

import os
import uuid


router = APIRouter()


# ============================================================
# Configuration
# ============================================================

ALLOWED_EXTENSIONS = {
    ".txt",
    ".pdf",
    ".docx"
}


# ============================================================
# Standardized OpenAPI Error Responses
# ============================================================

STANDARD_DOCUMENT_RESPONSES = {
    400: {
        "model": ErrorResponse,
        "description": "Bad Request — Unsupported document extension, empty file, unreadable text, or text exceeding 60,000 chars context limit."
    },
    413: {
        "model": ErrorResponse,
        "description": "Payload Too Large — File size exceeds the maximum allowed limit of 10 MB."
    },
    422: {
        "description": "Unprocessable Entity — Missing required file/form fields or invalid enum selection."
    },
    500: {
        "model": ErrorResponse,
        "description": "Internal Server Error — Document extraction failure, file saving error, or upstream Groq LLM API failure."
    },
}

KEY_POINTS_RESPONSES = {
    400: {
        "model": ErrorResponse,
        "description": "Bad Request — 'number_of_points' outside allowed range [1, 20], unsupported format, or empty file."
    },
    413: {
        "model": ErrorResponse,
        "description": "Payload Too Large — File size exceeds 10 MB limit."
    },
    422: {
        "description": "Unprocessable Entity — Missing required file or invalid parameter types."
    },
    500: {
        "model": ErrorResponse,
        "description": "Internal Server Error — Key points extraction or Groq API failure."
    },
}

HIERARCHICAL_RESPONSES = {
    400: {
        "model": ErrorResponse,
        "description": "Bad Request — 'chunk_size' outside allowed range [500, 20000], unsupported format, or empty document."
    },
    413: {
        "model": ErrorResponse,
        "description": "Payload Too Large — File size exceeds 10 MB limit."
    },
    422: {
        "description": "Unprocessable Entity — Missing required file or invalid form parameters."
    },
    500: {
        "model": ErrorResponse,
        "description": "Internal Server Error — Map-Reduce section processing or Groq API failure."
    },
}

MEDIA_RESPONSES = {
    400: {
        "model": ErrorResponse,
        "description": "Bad Request — Unsupported media extension (must be .mp3, .wav, .m4a, .mp4, .mkv, .mov, .webm, .avi, .flac, .ogg), empty file, or no speech detected."
    },
    413: {
        "model": ErrorResponse,
        "description": "Payload Too Large — Media file exceeds 10 MB limit."
    },
    422: {
        "description": "Unprocessable Entity — Missing required media file or invalid form parameters."
    },
    500: {
        "model": ErrorResponse,
        "description": "Internal Server Error — FFmpeg audio extraction failure, Whisper transcription error, or LLM inference error."
    },
}

UPDATE_SUMMARY_RESPONSES = {
    400: {
        "model": ErrorResponse,
        "description": "Bad Request — 'previous_summary' or 'current_text' is empty or whitespace-only."
    },
    422: {
        "description": "Unprocessable Entity — Missing required form parameters."
    },
    500: {
        "model": ErrorResponse,
        "description": "Internal Server Error — Groq LLM update synthesis failure."
    },
}

YOUTUBE_RESPONSES = {
    400: {
        "model": ErrorResponse,
        "description": "Bad Request — Empty URL, invalid YouTube video ID, or video lacks accessible closed-captions/transcripts."
    },
    422: {
        "description": "Unprocessable Entity — Missing required 'url' form field."
    },
    500: {
        "model": ErrorResponse,
        "description": "Internal Server Error — Transcript retrieval or Groq LLM synthesis failure."
    },
}

FAITHFULNESS_RESPONSES = {
    400: {
        "model": ErrorResponse,
        "description": "Bad Request — Missing both source file and source text, empty summary text, or unreadable document."
    },
    413: {
        "model": ErrorResponse,
        "description": "Payload Too Large — Source file exceeds 10 MB limit."
    },
    422: {
        "description": "Unprocessable Entity — Missing required parameters."
    },
    500: {
        "model": ErrorResponse,
        "description": "Internal Server Error — Faithfulness verification processing failure."
    },
}



# ============================================================
# File Validation
# ============================================================

def validate_file(file: UploadFile):
    """
    Validate uploaded file type and filename.
    """
    safe_filename = os.path.basename(file.filename or "")
    if not safe_filename:
        raise HTTPException(
            status_code=400,
            detail="No filename provided."
        )

    extension = os.path.splitext(
        safe_filename
    )[1].lower()

    if extension not in ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=400,
            detail=(
                f"Unsupported file format '{extension}'. "
                "Supported formats are TXT, PDF, and DOCX."
            )
        )


# ============================================================
# Save Uploaded File (Streaming Chunk Validation)
# ============================================================

def save_uploaded_file(file: UploadFile, max_size: int = MAX_FILE_SIZE) -> str:
    """
    Save uploaded file using a unique filename while enforcing
    streaming byte-size limits to protect disk and memory.
    """
    upload_folder = str(UPLOAD_DIR)
    os.makedirs(
        upload_folder,
        exist_ok=True
    )

    safe_filename = os.path.basename(file.filename or "")
    extension = os.path.splitext(
        safe_filename
    )[1].lower()

    unique_filename = (
        f"{uuid.uuid4()}{extension}"
    )

    file_path = os.path.join(
        upload_folder,
        unique_filename
    )


    file.file.seek(0)
    total_size = 0
    chunk_size = 1024 * 1024  # 1 MB

    try:
        with open(file_path, "wb") as buffer:
            while True:
                chunk = file.file.read(chunk_size)
                if not chunk:
                    break
                total_size += len(chunk)
                if total_size > max_size:
                    buffer.close()
                    if os.path.exists(file_path):
                        os.remove(file_path)
                    max_mb = max_size // (1024 * 1024)
                    raise HTTPException(
                        status_code=413,
                        detail=(
                            f"File size exceeds the maximum "
                            f"allowed size of {max_mb} MB."
                        )
                    )
                buffer.write(chunk)
    except HTTPException:
        raise
    except Exception as e:
        if os.path.exists(file_path):
            os.remove(file_path)
        raise HTTPException(
            status_code=500,
            detail=f"Failed to save uploaded file: {str(e)}"
        ) from e

    # --------------------------------------------------------
    # Empty file
    # --------------------------------------------------------

    if total_size == 0:
        if os.path.exists(file_path):
            os.remove(file_path)

        raise HTTPException(
            status_code=400,
            detail="The uploaded file is empty."
        )

    return file_path


# ============================================================
# SINGLE DOCUMENT SUMMARIZATION
# ============================================================

@router.post(
    "/summarize",
    response_model=SummaryResponse,
    summary="Summarize Single Document",
    description=(
        "Upload and summarize a single document (**TXT**, **PDF**, or **DOCX**).\n\n"
        "### Processing Pipeline:\n"
        "1. **Validation**: Enforces supported extensions (`.txt`, `.pdf`, `.docx`) and max 10 MB file size.\n"
        "2. **Text Extraction**: Uses PyMuPDF for PDFs, python-docx for DOCX, or direct UTF-8 decoding for TXT.\n"
        "3. **Synthesis**: Groq Cloud LLM (`openai/gpt-oss-20b`) synthesizes text into the requested length, format, and executive briefing mode.\n\n"
        "### Supported Document Formats:\n"
        "- `.txt`: Plain text\n"
        "- `.pdf`: Portable Document Format (extracts clean text across all pages)\n"
        "- `.docx`: Microsoft Word document\n\n"
        "### Constraints:\n"
        "- Maximum file size: **10 MB** (streaming chunk-enforced)\n"
        "- Context safety guard: Documents >60,000 characters should use `/summarize-hierarchical`"
    ),
    response_description="Synthesized document summary generated by Groq LLM",
    tags=["Document Summarization"],
    responses=STANDARD_DOCUMENT_RESPONSES
)
def summarize(
    file: Annotated[
        UploadFile,
        File(description="Document file to summarize (.txt, .pdf, or .docx, max 10 MB)")
    ],

    length: Annotated[
        Literal["short", "medium", "long"],
        Form(description="Summary length: 'short' (~1-2 paragraphs), 'medium' (~3-4 paragraphs), or 'long' (detailed)")
    ] = "medium",

    format: Annotated[
        Literal["paragraph", "bullets", "table"],
        Form(description="Output presentation format: 'paragraph' (narrative), 'bullets' (bullet points), or 'table' (markdown table)")
    ] = "paragraph",

    executive: Annotated[
        bool,
        Form(description="When true, generates a high-level strategic executive summary tailored for leadership")
    ] = False
):

    # --------------------------------------------------------
    # Validate uploaded file
    # --------------------------------------------------------

    validate_file(file)

    # --------------------------------------------------------
    # Save file temporarily
    # --------------------------------------------------------

    file_path = save_uploaded_file(
        file
    )

    try:

        # ----------------------------------------------------
        # Extract text
        # ----------------------------------------------------

        text = extract_text(
            file_path
        )

        if not text or not text.strip():

            raise HTTPException(
                status_code=400,
                detail=(
                    "No readable text was found "
                    "in the uploaded file."
                )
            )

        # ----------------------------------------------------
        # Generate summary
        # ----------------------------------------------------

        summary = summarize_text(
            text=text,
            length=length,
            format=format,
            executive=executive
        )

        return SummaryResponse(
            summary=summary
        )

    except ValueError as e:
        raise HTTPException(
            status_code=400,
            detail=str(e)
        ) from e

    except RuntimeError as e:
        raise HTTPException(
            status_code=500,
            detail=str(e)
        ) from e

    finally:

        # ----------------------------------------------------
        # Delete temporary file
        # ----------------------------------------------------

        if os.path.exists(file_path):

            os.remove(
                file_path
            )


# ============================================================
# MULTIPLE DOCUMENT SUMMARIZATION
# ============================================================

@router.post(
    "/summarize-multiple",
    response_model=SummaryResponse,
    summary="Synthesize Multiple Documents",
    description=(
        "Upload and synthesize multiple documents (**TXT**, **PDF**, or **DOCX**) into a consolidated overview.\n\n"
        "### Processing Pipeline:\n"
        "1. **Batch Validation**: Validates each document's extension and enforces the 10 MB limit per file.\n"
        "2. **Text Extraction & Separation**: Extracts text from each document and labels document boundaries with contextual delimiters.\n"
        "3. **Cross-Synthesis**: Groq Cloud LLM synthesizes common themes and key insights across all documents.\n\n"
        "### Constraints:\n"
        "- Accepts multiple files in the `files` field (`.txt`, `.pdf`, `.docx`)\n"
        "- Maximum file size: **10 MB per file**\n"
        "- Total combined text must not exceed 60,000 characters"
    ),
    response_description="Consolidated multi-document summary generated by Groq LLM",
    tags=["Document Summarization"],
    responses=STANDARD_DOCUMENT_RESPONSES
)
def summarize_multiple(
    files: Annotated[
        list[UploadFile],
        File(description="Array of document files to synthesize (.txt, .pdf, or .docx, max 10 MB each)")
    ],

    length: Annotated[
        Literal["short", "medium", "long"],
        Form(description="Summary length: 'short', 'medium', or 'long'")
    ] = "medium",

    format: Annotated[
        Literal["paragraph", "bullets", "table"],
        Form(description="Output presentation format: 'paragraph', 'bullets', or 'table'")
    ] = "paragraph",

    executive: Annotated[
        bool,
        Form(description="When true, generates a strategic executive summary tailored for leadership")
    ] = False
):

    # --------------------------------------------------------
    # Make sure at least one file was supplied
    # --------------------------------------------------------

    if not files:

        raise HTTPException(
            status_code=400,
            detail="At least one file is required."
        )

    file_paths = []

    try:

        combined_text = ""

        # ----------------------------------------------------
        # Process every uploaded document
        # ----------------------------------------------------

        for uploaded_file in files:

            # Validate extension
            validate_file(
                uploaded_file
            )

            # Save temporarily
            file_path = save_uploaded_file(
                uploaded_file
            )

            file_paths.append(
                file_path
            )

            # Extract text
            text = extract_text(
                file_path
            )

            if not text or not text.strip():

                raise HTTPException(
                    status_code=400,
                    detail=(
                        "No readable text was found "
                        f"in '{uploaded_file.filename}'."
                    )
                )

            # ------------------------------------------------
            # Preserve document boundaries
            # ------------------------------------------------

            combined_text += (
                "\n\n"
                f"--- Document: {uploaded_file.filename} ---"
                "\n\n"
            )

            combined_text += text

        # ----------------------------------------------------
        # Final validation
        # ----------------------------------------------------

        if not combined_text.strip():

            raise HTTPException(
                status_code=400,
                detail=(
                    "No readable text was found "
                    "in the uploaded files."
                )
            )

        # ----------------------------------------------------
        # Generate combined summary
        # ----------------------------------------------------

        summary = summarize_text(
            text=combined_text,
            length=length,
            format=format,
            executive=executive
        )

        return SummaryResponse(
            summary=summary
        )

    except ValueError as e:
        raise HTTPException(
            status_code=400,
            detail=str(e)
        ) from e

    except RuntimeError as e:
        raise HTTPException(
            status_code=500,
            detail=str(e)
        ) from e

    finally:

        # ----------------------------------------------------
        # Delete all temporary files
        # ----------------------------------------------------

        for file_path in file_paths:

            if os.path.exists(file_path):

                os.remove(
                    file_path
                )


# ============================================================
# KEY POINT EXTRACTION
# ============================================================

@router.post(
    "/key-points",
    response_model=KeyPointsResponse,
    summary="Extract Key Takeaways",
    description=(
        "Extract a configurable number of crisp, salient key takeaways from an uploaded document.\n\n"
        "### Processing Pipeline:\n"
        "1. **Text Extraction**: Extracts clean text from `.txt`, `.pdf`, or `.docx`.\n"
        "2. **Salience Extraction**: Groq LLM identifies the most critical concepts, facts, or decisions.\n"
        "3. **Normalization**: Strips list numbering into a clean JSON array of strings.\n\n"
        "### Parameters:\n"
        "- `number_of_points`: Integer count between **1** and **20** (default: 5)\n"
        "- Maximum file size: **10 MB**"
    ),
    response_description="Structured list of extracted key takeaways",
    tags=["Analysis & Extraction"],
    responses=KEY_POINTS_RESPONSES
)
def key_points(
    file: Annotated[
        UploadFile,
        File(description="Document file to extract key takeaways from (.txt, .pdf, or .docx, max 10 MB)")
    ],
    number_of_points: Annotated[
        int,
        Form(description="Number of key points to extract (between 1 and 20)")
    ] = 5
):

    # --------------------------------------------------------
    # Validate number of requested points
    # --------------------------------------------------------

    if number_of_points < 1 or number_of_points > 20:

        raise HTTPException(
            status_code=400,
            detail=(
                "Number of points must be "
                "between 1 and 20."
            )
        )

    # --------------------------------------------------------
    # Validate uploaded file
    # --------------------------------------------------------

    validate_file(
        file
    )

    # --------------------------------------------------------
    # Save file temporarily
    # --------------------------------------------------------

    file_path = save_uploaded_file(
        file
    )

    try:

        # ----------------------------------------------------
        # Extract text from TXT/PDF/DOCX
        # ----------------------------------------------------

        text = extract_text(
            file_path
        )

        if not text or not text.strip():

            raise HTTPException(
                status_code=400,
                detail=(
                    "No readable text was found "
                    "in the uploaded file."
                )
            )

        # ----------------------------------------------------
        # Extract key points using Groq
        # ----------------------------------------------------

        result = extract_key_points(
            text=text,
            number_of_points=number_of_points
        )

        # ----------------------------------------------------
        # Convert Groq numbered-list response
        # into a Python list
        # ----------------------------------------------------

        points = []

        for line in result.splitlines():

            line = line.strip()

            if not line:
                continue

            # Remove common numbering formats:
            #
            # 1. Point
            # 2) Point
            # - Point
            # * Point
            #
            cleaned_line = line.lstrip(
                "0123456789.-) "
            ).strip()

            if cleaned_line:

                points.append(
                    cleaned_line
                )

        # ----------------------------------------------------
        # Make sure Groq returned something
        # ----------------------------------------------------

        if not points:

            raise HTTPException(
                status_code=500,
                detail="Unable to extract key points."
            )

        # ----------------------------------------------------
        # Return only requested number of points
        # ----------------------------------------------------

        points = points[
            :number_of_points
        ]

        return KeyPointsResponse(
            key_points=points
        )

    except ValueError as e:
        raise HTTPException(
            status_code=400,
            detail=str(e)
        ) from e

    except RuntimeError as e:
        raise HTTPException(
            status_code=500,
            detail=str(e)
        ) from e

    finally:

        # ----------------------------------------------------
        # Delete temporary file
        # ----------------------------------------------------

        if os.path.exists(file_path):

            os.remove(
                file_path
            )


# ============================================================
# COMPARATIVE DOCUMENT SUMMARIZATION
# ============================================================

@router.post(
    "/compare",
    response_model=SummaryResponse,
    summary="Side-by-Side Document Comparison",
    description=(
        "Perform a comparative analysis of two uploaded documents (`file_a` and `file_b`).\n\n"
        "### Processing Pipeline:\n"
        "1. **Independent Ingestion**: Validates and extracts text from each document.\n"
        "2. **Comparative Synthesis**: Groq LLM evaluates both texts side-by-side to highlight:\n"
        "   - **Common Themes & Similarities**: Shared arguments, mutual findings, and baseline overlap.\n"
        "   - **Key Differences**: Divergent conclusions, conflicting metrics, and contrasting stances.\n"
        "   - **Unique Details**: Facts or data points present in only one document.\n\n"
        "### Supported Formats:\n"
        "- Both `file_a` and `file_b` accept `.txt`, `.pdf`, and `.docx` up to 10 MB each."
    ),
    response_description="Structured comparative analysis report highlighting commonalities and differences",
    tags=["Analysis & Extraction"],
    responses=STANDARD_DOCUMENT_RESPONSES
)
def compare(
    file_a: Annotated[
        UploadFile,
        File(description="First document to compare (.txt, .pdf, or .docx, max 10 MB)")
    ],
    file_b: Annotated[
        UploadFile,
        File(description="Second document to compare (.txt, .pdf, or .docx, max 10 MB)")
    ]
):

    file_a_path = None
    file_b_path = None

    try:

        # ====================================================
        # VALIDATE FILE A
        # ====================================================

        validate_file(file_a)

        # ====================================================
        # VALIDATE FILE B
        # ====================================================

        validate_file(file_b)

        # ====================================================
        # SAVE FILE A
        # ====================================================

        file_a_path = save_uploaded_file(file_a)

        # ====================================================
        # SAVE FILE B
        # ====================================================

        file_b_path = save_uploaded_file(file_b)

        # ====================================================
        # EXTRACT TEXT FROM FILE A
        # ====================================================

        text_a = extract_text(file_a_path)

        if not text_a or not text_a.strip():
            raise HTTPException(
                status_code=400,
                detail=(
                    f"No readable text was found in "
                    f"'{file_a.filename}'."
                )
            )

        # ====================================================
        # EXTRACT TEXT FROM FILE B
        # ====================================================

        text_b = extract_text(file_b_path)

        if not text_b or not text_b.strip():
            raise HTTPException(
                status_code=400,
                detail=(
                    f"No readable text was found in "
                    f"'{file_b.filename}'."
                )
            )

        # ====================================================
        # COMPARE DOCUMENTS USING GROQ
        # ====================================================

        comparison = compare_documents(
            text_a=text_a,
            text_b=text_b,
            document_a_name=file_a.filename,
            document_b_name=file_b.filename
        )

        # ====================================================
        # RETURN RESPONSE
        # ====================================================

        return SummaryResponse(
            summary=comparison
        )

    except ValueError as e:
        raise HTTPException(
            status_code=400,
            detail=str(e)
        ) from e

    except RuntimeError as e:
        raise HTTPException(
            status_code=500,
            detail=str(e)
        ) from e

    finally:

        # ====================================================
        # DELETE TEMPORARY FILE A
        # ====================================================

        if (
            file_a_path
            and os.path.exists(file_a_path)
        ):
            os.remove(file_a_path)

        # ====================================================
        # DELETE TEMPORARY FILE B
        # ====================================================

        if (
            file_b_path
            and os.path.exists(file_b_path)
        ):
            os.remove(file_b_path)

# ============================================================
# AUDIO / VIDEO SUMMARIZATION
# ============================================================

@router.post(
    "/summarize-media",
    response_model=SummaryResponse,
    summary="Transcribe & Summarize Audio/Video",
    description=(
        "Upload an audio or video file to extract audio via FFmpeg, transcribe speech locally using faster-whisper, and generate a structured summary using Groq LLM.\n\n"
        "### Processing Pipeline:\n"
        "1. **Validation**: Verifies that the file extension is supported and under 10 MB.\n"
        "2. **FFmpeg Audio Extraction**: Normalizes media stream to 16 kHz mono 16-bit PCM WAV (with OS code-integrity fallback).\n"
        "3. **Local Whisper Transcription**: Transcribes speech offline using `faster-whisper` INT8 quantized model.\n"
        "4. **LLM Synthesis**: Groq Cloud LLM (`openai/gpt-oss-20b`) synthesizes the transcript into the requested length and format.\n\n"
        "### Supported Media Formats:\n"
        "- **Audio**: `.mp3`, `.wav`, `.m4a`, `.flac`, `.ogg`\n"
        "- **Video**: `.mp4`, `.mkv`, `.mov`, `.webm`, `.avi`\n\n"
        "### Constraints:\n"
        "- Maximum file size: **10 MB**\n"
        "- Speech must be present and audible in the recording."
    ),
    response_description="Synthesized summary of spoken audio/video content",
    tags=["Media & Video"],
    responses=MEDIA_RESPONSES
)
def summarize_media(
    file: Annotated[
        UploadFile,
        File(description="Audio or video file (.mp3, .wav, .m4a, .mp4, .mkv, .mov, .webm, .avi, .flac, .ogg, max 10 MB)")
    ],

    length: Annotated[
        Literal["short", "medium", "long"],
        Form(description="Summary length: 'short', 'medium', or 'long'")
    ] = "medium",

    format: Annotated[
        Literal["paragraph", "bullets", "table"],
        Form(description="Output presentation format: 'paragraph', 'bullets', or 'table'")
    ] = "paragraph",

    executive: Annotated[
        bool,
        Form(description="When true, generates a strategic executive briefing")
    ] = False
):

    media_path = None

    try:

        # ----------------------------------------------------
        # Validate media file
        # ----------------------------------------------------

        validate_media_file(
            file.filename
        )

        # ----------------------------------------------------
        # Save uploaded media with streaming validation
        # ----------------------------------------------------

        media_path = save_uploaded_file(file)

        # ----------------------------------------------------
        # Transcribe media
        # ----------------------------------------------------

        transcript = transcribe_media(
            media_path
        )

        if not transcript or not transcript.strip():

            raise HTTPException(
                status_code=400,
                detail=(
                    "No speech could be detected "
                    "in the uploaded media."
                )
            )

        # ----------------------------------------------------
        # Summarize transcript
        # ----------------------------------------------------

        summary = summarize_text(
            text=transcript,
            length=length,
            format=format,
            executive=executive
        )

        # ----------------------------------------------------
        # Return summary
        # ----------------------------------------------------

        return SummaryResponse(
            summary=summary
        )

    except ValueError as e:

        raise HTTPException(
            status_code=400,
            detail=str(e)
        ) from e

    except RuntimeError as e:

        raise HTTPException(
            status_code=500,
            detail=str(e)
        ) from e

    finally:

        # ----------------------------------------------------
        # Delete uploaded media
        # ----------------------------------------------------

        if (
            media_path
            and os.path.exists(media_path)
        ):

            os.remove(
                media_path
            )

# ============================================================
# UPDATE / DELTA SUMMARY
# ============================================================

@router.post(
    "/update-summary",
    response_model=SummaryResponse,
    summary="Delta Update Summarization",
    description=(
        "Compare an existing document summary against the latest document content and isolate delta updates.\n\n"
        "### Processing Pipeline:\n"
        "1. Ingests `previous_summary` and updated `current_text`.\n"
        "2. Groq Cloud LLM detects and structures updates into four distinct categories:\n"
        "   - **New Information**: Newly introduced facts, findings, and statements.\n"
        "   - **Changed Information**: Contradictions, updated data points, and changed timelines.\n"
        "   - **Removed Information**: Concepts in the previous summary that no longer appear.\n"
        "   - **Unchanged Information**: Key aspects that remain consistent."
    ),
    response_description="Categorized delta summary highlighting additions, modifications, and removals",
    tags=["Analysis & Extraction"],
    responses=UPDATE_SUMMARY_RESPONSES
)
def update_summary_endpoint(
    previous_summary: Annotated[
        str,
        Form(description="Existing summary text to compare against", examples=["Company Q1 reported 10% growth in revenue and launched Product X."])
    ],

    current_text: Annotated[
        str,
        Form(description="Current updated document content", examples=["Company Q2 reported 15% growth in revenue, launched Product Y, and deprecated Product X."])
    ]
):

    try:

        # ----------------------------------------------------
        # Validate previous summary
        # ----------------------------------------------------

        if not previous_summary.strip():

            raise HTTPException(
                status_code=400,
                detail="Previous summary cannot be empty."
            )

        # ----------------------------------------------------
        # Validate current document
        # ----------------------------------------------------

        if not current_text.strip():

            raise HTTPException(
                status_code=400,
                detail="Current document cannot be empty."
            )

        # ----------------------------------------------------
        # Generate update summary
        # ----------------------------------------------------

        result = update_summary(
            previous_summary=previous_summary,
            current_text=current_text
        )

        # ----------------------------------------------------
        # Return response
        # ----------------------------------------------------

        return SummaryResponse(
            summary=result
        )

    except ValueError as e:

        raise HTTPException(
            status_code=400,
            detail=str(e)
        ) from e

    except RuntimeError as e:

        raise HTTPException(
            status_code=500,
            detail=str(e)
        ) from e


# ============================================================
# HIERARCHICAL SUMMARIZATION ENDPOINT
# ============================================================

@router.post(
    "/summarize-hierarchical",
    response_model=HierarchicalSummaryResponse,
    summary="Map-Reduce Hierarchical Summarization",
    description=(
        "Summarize large documents using a high-throughput parallelized Map-Reduce architecture.\n\n"
        "### Processing Pipeline:\n"
        "1. **Semantic Partitioning (Map)**: Splits document text along heading, chapter, and paragraph boundaries into target chunks (500–20,000 characters).\n"
        "2. **Parallel Section Synthesis**: Dispatches chunk summarization concurrently across worker threads (`ThreadPoolExecutor(max_workers=4)`).\n"
        "3. **Master Synthesis (Reduce)**: Aggregates individual section summaries into a cohesive, structured final master summary.\n\n"
        "### Returns:\n"
        "- `final_summary`: Comprehensive synthesis covering all sections.\n"
        "- `section_summaries`: Array of individual section indexes and summaries.\n"
        "- `total_sections`: Total number of partitioned chunks processed.\n\n"
        "### Supported Formats:\n"
        "- Document files: `.txt`, `.pdf`, `.docx` up to 10 MB."
    ),
    response_description="Master synthesized summary and individual section breakdown",
    tags=["Document Summarization"],
    responses=HIERARCHICAL_RESPONSES
)
def summarize_hierarchical_endpoint(
    file: Annotated[
        UploadFile,
        File(description="Document file (TXT, PDF, DOCX) to summarize hierarchically (max 10 MB)")
    ],

    length: Annotated[
        Literal["short", "medium", "long"],
        Form(description="Summary length: 'short', 'medium', or 'long'")
    ] = "medium",

    format: Annotated[
        Literal["paragraph", "bullets", "table"],
        Form(description="Output presentation format: 'paragraph', 'bullets', or 'table'")
    ] = "paragraph",

    executive: Annotated[
        bool,
        Form(description="When true, generates an executive-level strategic overview")
    ] = False,

    chunk_size: Annotated[
        int,
        Form(description="Target character size per section chunk (between 500 and 20000 characters)")
    ] = 2000
):

    # --------------------------------------------------------
    # Validate uploaded file
    # --------------------------------------------------------
    validate_file(file)

    # --------------------------------------------------------
    # Save file temporarily
    # --------------------------------------------------------
    file_path = save_uploaded_file(file)

    try:
        # ----------------------------------------------------
        # Extract text from document
        # ----------------------------------------------------
        text = extract_text(file_path)

        if not text or not text.strip():
            raise HTTPException(
                status_code=400,
                detail="No readable text was found in the uploaded file."
            )

        # ----------------------------------------------------
        # Execute hierarchical summarization
        # ----------------------------------------------------
        result = hierarchical_summarize(
            text=text,
            chunk_size=chunk_size,
            length=length,
            format=format,
            executive=executive
        )

        return HierarchicalSummaryResponse(**result)

    except ValueError as e:
        raise HTTPException(
            status_code=400,
            detail=str(e)
        ) from e

    except RuntimeError as e:
        raise HTTPException(
            status_code=500,
            detail=str(e)
        ) from e

    finally:
        # ----------------------------------------------------
        # Cleanup temporary file
        # ----------------------------------------------------
        if file_path and os.path.exists(file_path):
            os.remove(file_path)


# ============================================================
# YOUTUBE VIDEO TRANSCRIPT SUMMARIZATION
# ============================================================

@router.post(
    "/summarize-youtube",
    response_model=SummaryResponse,
    summary="Summarize YouTube Video Transcript",
    description=(
        "Extract closed captions and transcripts from a YouTube video URL and generate a structured summary.\n\n"
        "### Supported YouTube URL Formats:\n"
        "- Standard Watch: `https://www.youtube.com/watch?v=VIDEO_ID`\n"
        "- Shortened Share: `https://youtu.be/VIDEO_ID`\n"
        "- Embedded Link: `https://www.youtube.com/embed/VIDEO_ID`\n"
        "- YouTube Shorts: `https://www.youtube.com/shorts/VIDEO_ID`\n\n"
        "### Processing Pipeline:\n"
        "1. **Video ID Extraction**: Extracts the 11-character video ID using regex pattern matching.\n"
        "2. **Captions Retrieval**: Queries YouTube's caption endpoint via `youtube-transcript-api`.\n"
        "3. **Cleaning**: Strips sound markers (e.g. `[Music]`, `[Applause]`) and aggregates text.\n"
        "4. **Synthesis**: Groq Cloud LLM generates a cohesive summary in the requested length and format."
    ),
    response_description="Synthesized summary generated from YouTube video transcript",
    tags=["Media & Video"],
    responses=YOUTUBE_RESPONSES
)
def summarize_youtube_endpoint(
    url: Annotated[
        str,
        Form(
            description="YouTube video URL (e.g. https://www.youtube.com/watch?v=...)",
            examples=["https://www.youtube.com/watch?v=dQw4w9WgXcQ"]
        )
    ],

    length: Annotated[
        Literal["short", "medium", "long"],
        Form(description="Summary length: 'short', 'medium', or 'long'")
    ] = "medium",

    format: Annotated[
        Literal["paragraph", "bullets", "table"],
        Form(description="Output presentation format: 'paragraph', 'bullets', or 'table'")
    ] = "paragraph",

    executive: Annotated[
        bool,
        Form(description="When true, generates a strategic executive briefing")
    ] = False
):
    if not url or not url.strip():
        raise HTTPException(
            status_code=400,
            detail="YouTube URL cannot be empty."
        )

    try:
        # 1. Fetch transcript from YouTube
        transcript = fetch_youtube_transcript(url.strip())

        if not transcript or not transcript.strip():
            raise HTTPException(
                status_code=400,
                detail="No speech or transcript text could be retrieved for this YouTube video."
            )

        # 2. Summarize using existing Groq service
        summary = summarize_text(
            text=transcript,
            length=length,
            format=format,
            executive=executive
        )

        return SummaryResponse(
            summary=summary
        )

    except ValueError as e:
        raise HTTPException(
            status_code=400,
            detail=str(e)
        ) from e

    except RuntimeError as e:
        raise HTTPException(
            status_code=500,
            detail=str(e)
        ) from e


# ============================================================
# FAITHFULNESS VERIFICATION ENDPOINT
# ============================================================

@router.post(
    "/check-faithfulness",
    response_model=FaithfulnessResult,
    summary="Check Summary Faithfulness against Source Material",
    description=(
        "Evaluate whether a generated summary is supported by the source document.\n\n"
        "### Processing Pipeline:\n"
        "1. **Claim Extraction**: Extracts substantive factual and quantitative claims from the summary.\n"
        "2. **Evidence Matching**: Deterministically matches claims to source document passages using token overlap and sequence similarity.\n"
        "3. **Validation Layers**: Performs deterministic numerical, date, and named entity verification.\n"
        "4. **Optional LLM Gate**: Resolves ambiguous claims via bounded Groq verification if enabled.\n"
        "5. **Scoring**: Computes bounded faithfulness score (0.0–1.0) and categorical status (HIGH, MODERATE, LOW).\n\n"
        "### Input Options:\n"
        "- Supply source material either via file upload (`file`) OR direct text (`source_text`)."
    ),
    response_description="Structured faithfulness verification results with individual claim breakdowns",
    tags=["Analysis & Extraction"],
    responses=FAITHFULNESS_RESPONSES
)
def check_faithfulness_endpoint(
    summary_text: Annotated[
        str,
        Form(description="Generated summary text to evaluate for faithfulness against source material")
    ],
    source_text: Annotated[
        Optional[str],
        Form(description="Raw source text to verify the summary against (optional if 'file' is provided)")
    ] = None,
    file: Annotated[
        Optional[UploadFile],
        File(description="Source document file (TXT, PDF, DOCX) to verify against (optional if 'source_text' is provided)")
    ] = None,
    use_llm: Annotated[
        bool,
        Form(description="When true, leverages bounded Groq LLM verification for ambiguous claims")
    ] = False
):
    if not summary_text or not summary_text.strip():
        raise HTTPException(
            status_code=400,
            detail="Summary text cannot be empty."
        )

    file_path = None
    extracted_source = ""

    try:
        # Handle file upload if supplied
        if file and file.filename:
            validate_file(file)
            file_path = save_uploaded_file(file)
            extracted_source = extract_text(file_path)

        # Merge or prioritize direct source_text if provided
        final_source = (source_text or "").strip() or extracted_source.strip()

        if not final_source:
            raise HTTPException(
                status_code=400,
                detail="Either 'file' or 'source_text' must be provided with readable source content."
            )

        result = check_faithfulness(
            source_text=final_source,
            summary_text=summary_text,
            use_llm=use_llm
        )

        return FaithfulnessResult(**result)

    except HTTPException:
        raise
    except ValueError as e:
        raise HTTPException(
            status_code=400,
            detail=str(e)
        ) from e
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Faithfulness verification failed: {str(e)}"
        ) from e
    finally:
        if file_path and os.path.exists(file_path):
            os.remove(file_path)

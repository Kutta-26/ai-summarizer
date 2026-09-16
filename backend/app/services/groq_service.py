import os
import re
import concurrent.futures

from pathlib import Path
from dotenv import load_dotenv
from groq import (
    Groq,
    APIError,
    RateLimitError,
    APITimeoutError,
    APIConnectionError,
    AuthenticationError
)

from app.core.config import (
    GROQ_API_KEY,
    GROQ_MODEL,
    REQUEST_TIMEOUT
)


import ssl
import httpx
from app.core.logging_config import get_logger

logger = get_logger("groq")

# ============================================================
# ENVIRONMENT & CLIENT CONFIGURATION
# ============================================================

MODEL_NAME = GROQ_MODEL
_client = None


def get_groq_client() -> Groq:
    """
    Lazily initialize and return the Groq client.
    Ensures safe module imports, connection pooling, and cross-platform
    SSL certificate resolution (including Windows System CA store).
    """
    global _client
    if _client is None:
        key = GROQ_API_KEY or os.getenv("GROQ_API_KEY")
        if not key:
            raise RuntimeError(
                "GROQ_API_KEY is not configured. Please set GROQ_API_KEY in .env or environment variables."
            )
        try:
            # Provide an optimized HTTP client with system SSL context and connection pooling
            ssl_ctx = ssl.create_default_context()
            http_client = httpx.Client(
                verify=ssl_ctx,
                timeout=REQUEST_TIMEOUT,
                limits=httpx.Limits(max_keepalive_connections=10, max_connections=20)
            )
            _client = Groq(
                api_key=key,
                http_client=http_client,
                timeout=REQUEST_TIMEOUT,
                max_retries=2
            )
        except Exception:
            _client = Groq(
                api_key=key,
                timeout=REQUEST_TIMEOUT,
                max_retries=2
            )
    return _client



import time

def _handle_groq_exception(e: Exception, operation: str = "operation") -> RuntimeError:
    """
    Map raw Groq SDK and HTTP exceptions to clear, user-actionable RuntimeErrors.
    """
    if isinstance(e, RateLimitError):
        return RuntimeError(
            f"Groq API rate limit reached during {operation}. Please wait a moment and try again."
        )
    if isinstance(e, APITimeoutError):
        return RuntimeError(
            f"Groq API request timed out during {operation}. Please try again."
        )
    if isinstance(e, APIConnectionError):
        return RuntimeError(
            f"Could not connect to Groq API during {operation}. Please check your network connection."
        )
    if isinstance(e, AuthenticationError):
        return RuntimeError(
            "Groq API authentication failed. Please verify your GROQ_API_KEY."
        )
    return RuntimeError(
        f"{operation.capitalize()} failed: {str(e)}"
    )


def _call_groq_chat(
    messages: list[dict],
    temperature: float = 0.2,
    operation: str = "operation"
) -> str:
    """
    Executes a Groq chat completion with automatic exponential backoff for transient rate limits and network drops.
    """
    max_attempts = 4
    delay = 2.0

    for attempt in range(1, max_attempts + 1):
        try:
            groq_client = get_groq_client()
            response = groq_client.chat.completions.create(
                model=MODEL_NAME,
                messages=messages,
                temperature=temperature
            )

            content = response.choices[0].message.content
            if not content or not content.strip():
                raise RuntimeError(
                    f"The {operation} service returned an empty response."
                )
            return content.strip()

        except RateLimitError as e:
            if attempt == max_attempts:
                raise RuntimeError(
                    f"Groq API rate limit reached during {operation}. Please wait a moment and try again."
                ) from e
            time.sleep(delay)
            delay *= 2.0

        except (APITimeoutError, APIConnectionError) as e:
            if attempt == max_attempts:
                raise _handle_groq_exception(e, operation) from e
            time.sleep(delay)
            delay *= 2.0

        except (ValueError, RuntimeError):
            raise

        except Exception as e:
            raise _handle_groq_exception(e, operation) from e

    raise RuntimeError(f"{operation.capitalize()} failed after {max_attempts} attempts.")


# ============================================================
# SINGLE / MULTIPLE DOCUMENT SUMMARIZATION
# ============================================================

def summarize_text(
    text: str,
    length: str = "medium",
    format: str = "paragraph",
    executive: bool = False
):
    """
    Generate an AI-powered summary of one or more documents.

    Supported lengths:
        short
        medium
        long

    Supported formats:
        paragraph
        bullets
        table

    The same function is used by:
        POST /summarize
        POST /summarize-multiple
    """

    # --------------------------------------------------------
    # Validate input text
    # --------------------------------------------------------

    if not text or not text.strip():
        raise ValueError(
            "Cannot summarize empty text."
        )

    if len(text) > 60000:
        raise ValueError(
            "Document exceeds 60,000 characters (~15,000 words) for direct summarization. "
            "Please use the Hierarchical Summarizer (Map-Reduce) feature for large documents."
        )

    # --------------------------------------------------------
    # Length instructions
    # --------------------------------------------------------

    length_instruction = {
        "short": (
            "Keep the summary very concise and include only "
            "the most important information."
        ),

        "medium": (
            "Provide a balanced summary containing the important "
            "information without unnecessary details."
        ),

        "long": (
            "Provide a detailed summary while preserving important "
            "facts, context, and meaning."
        )
    }

    # --------------------------------------------------------
    # Format instructions
    # --------------------------------------------------------

    format_instruction = {
        "paragraph": (
            "Write the summary as clear, well-organized paragraphs."
        ),

        "bullets": (
            "Write the summary as clear bullet points. "
            "Each bullet should contain one meaningful idea."
        ),

        "table": (
            "Write the summary as a Markdown table. "
            "Use meaningful column headings. "
            "Organize the important information into rows. "
            "Do not write the main summary as paragraphs outside "
            "the table unless a very short introductory sentence "
            "is absolutely necessary."
        )
    }

    # --------------------------------------------------------
    # Validate length
    # --------------------------------------------------------

    if length not in length_instruction:

        raise ValueError(
            "length must be one of: short, medium, long."
        )

    # --------------------------------------------------------
    # Validate format
    # --------------------------------------------------------

    if format not in format_instruction:

        raise ValueError(
            "format must be one of: paragraph, bullets, table."
        )

    # --------------------------------------------------------
    # Executive summary instructions
    # --------------------------------------------------------

    executive_instruction = ""

    if executive:

        executive_instruction = """
Create the summary in an executive-summary style.

Focus on:

- Key findings
- Important facts
- Major conclusions
- Decisions
- Actionable information

Keep the executive summary focused, professional,
and easy to understand.
"""

    # --------------------------------------------------------
    # Additional table instructions
    # --------------------------------------------------------

    table_instruction = ""

    if format == "table":

        table_instruction = """
TABLE-SPECIFIC REQUIREMENTS:

- Return a valid Markdown table.
- Include a header row.
- Include a separator row using Markdown syntax.
- Organize information into meaningful rows.
- Keep each cell concise.
- Do not put the entire document into one cell.
- Use columns that make sense for the document.
- Do not invent information.
- Preserve important facts and meaning.
"""

    # --------------------------------------------------------
    # Build prompt
    # --------------------------------------------------------

    prompt = f"""
Summarize the following document.

LENGTH REQUIREMENT:
{length_instruction[length]}

FORMAT REQUIREMENT:
{format_instruction[format]}

{executive_instruction}

{table_instruction}

IMPORTANT RULES:

- Preserve the original meaning.
- Do not invent information.
- Do not add facts that are not present.
- Do not change the meaning of the document.
- Remove unnecessary repetition.
- Focus on the most important information.
- Keep the output clear and professional.
- Use only information contained in the document.

DOCUMENT:

{text}
"""

    # --------------------------------------------------------
    # Call Groq with automatic retry
    # --------------------------------------------------------

    messages = [
        {
            "role": "system",
            "content": (
                "You are a professional document "
                "summarization assistant. "
                "Summarize documents accurately using "
                "only the information provided."
            )
        },
        {
            "role": "user",
            "content": prompt
        }
    ]

    return _call_groq_chat(
        messages=messages,
        temperature=0.3,
        operation="summarization"
    )


# ============================================================
# KEY POINT EXTRACTION
# ============================================================

def extract_key_points(
    text: str,
    number_of_points: int = 5
):
    """
    Extract the most important points from a document.
    """

    # --------------------------------------------------------
    # Validate text
    # --------------------------------------------------------

    if not text or not text.strip():

        raise ValueError(
            "Cannot extract key points from empty text."
        )

    # --------------------------------------------------------
    # Validate number of points
    # --------------------------------------------------------

    if number_of_points < 1 or number_of_points > 20:

        raise ValueError(
            "number_of_points must be between 1 and 20."
        )

    # --------------------------------------------------------
    # Build prompt
    # --------------------------------------------------------

    prompt = f"""
Extract the {number_of_points} most important points
from the following document.

REQUIREMENTS:

- Return exactly {number_of_points} important points.
- Each point must contain meaningful information.
- Focus on the main ideas, facts, requirements,
  findings, decisions, or conclusions.
- Do not include minor details.
- Do not invent information.
- Do not repeat the same idea.
- Keep each point concise and clear.
- Return each point on a separate line.
- Do not add an introduction.
- Do not add a conclusion.
- Do not use unnecessary numbering.

DOCUMENT:

{text}
"""

    # --------------------------------------------------------
    # Call Groq with automatic retry
    # --------------------------------------------------------

    messages = [
        {
            "role": "system",
            "content": (
                "You are a professional information "
                "extraction assistant. Extract only "
                "information supported by the provided "
                "document."
            )
        },
        {
            "role": "user",
            "content": prompt
        }
    ]

    result = _call_groq_chat(
        messages=messages,
        temperature=0.2,
        operation="key-points extraction"
    )

    return result


# ============================================================
# COMPARATIVE DOCUMENT SUMMARIZATION
# ============================================================

def compare_documents(
    text_a: str,
    text_b: str,
    document_a_name: str = "Document A",
    document_b_name: str = "Document B"
):
    """
    Compare two documents and generate
    an AI-powered detailed comparison.
    """

    # --------------------------------------------------------
    # Validate Document A
    # --------------------------------------------------------

    if not text_a or not text_a.strip():

        raise ValueError(
            f"{document_a_name} does not contain readable text."
        )

    # --------------------------------------------------------
    # Validate Document B
    # --------------------------------------------------------

    if not text_b or not text_b.strip():

        raise ValueError(
            f"{document_b_name} does not contain readable text."
        )

    # --------------------------------------------------------
    # Build comparison prompt
    # --------------------------------------------------------

    prompt = f"""
Compare the following two documents.

============================================================
DOCUMENT A
============================================================

Document name:
{document_a_name}

Content:

{text_a}


============================================================
DOCUMENT B
============================================================

Document name:
{document_b_name}

Content:

{text_b}


============================================================
COMPARISON REQUIREMENTS
============================================================

Analyze both documents carefully.

Identify:

1. The main topic or purpose of Document A.

2. The main topic or purpose of Document B.

3. The major similarities between the documents.

4. The major differences between the documents.

5. Important differences in:
   - Facts
   - Requirements
   - Findings
   - Decisions
   - Features
   - Conclusions

6. Important information that appears only
   in Document A.

7. Important information that appears only
   in Document B.

8. The overall relationship between the documents.


============================================================
OUTPUT FORMAT
============================================================

Use exactly these sections:

Document A Summary:

Document B Summary:

Similarities:

Differences:

Unique Information in Document A:

Unique Information in Document B:

Overall Comparison:


============================================================
IMPORTANT RULES
============================================================

- Use only information contained in the documents.
- Do not invent information.
- Do not assume missing information.
- Do not make unsupported claims.
- Do not repeat the same information unnecessarily.
- Focus on meaningful similarities and differences.
- Keep the comparison clear and professional.
- Preserve the meaning of both documents.
"""

    # --------------------------------------------------------
    # Call Groq with automatic retry
    # --------------------------------------------------------

    messages = [
        {
            "role": "system",
            "content": (
                "You are a professional document "
                "comparison assistant. Compare documents "
                "accurately and use only information "
                "supported by the provided documents."
            )
        },
        {
            "role": "user",
            "content": prompt
        }
    ]

    return _call_groq_chat(
        messages=messages,
        temperature=0.2,
        operation="document comparison"
    )

# ============================================================
# UPDATE / DELTA SUMMARY
# ============================================================

def update_summary(
    previous_summary: str,
    current_text: str
):
    """
    Compare a previous summary with the current document
    and identify what is new, changed, removed, or unchanged.
    """

    # --------------------------------------------------------
    # Validate previous summary
    # --------------------------------------------------------

    if not previous_summary or not previous_summary.strip():
        raise ValueError(
            "Previous summary cannot be empty."
        )

    # --------------------------------------------------------
    # Validate current document
    # --------------------------------------------------------

    if not current_text or not current_text.strip():
        raise ValueError(
            "Current document cannot be empty."
        )

    # --------------------------------------------------------
    # Build prompt
    # --------------------------------------------------------

    prompt = f"""
Compare the PREVIOUS SUMMARY with the CURRENT DOCUMENT.

Your goal is to identify what has changed since the
previous summary.

============================================================
PREVIOUS SUMMARY
============================================================

{previous_summary}


============================================================
CURRENT DOCUMENT
============================================================

{current_text}


============================================================
ANALYSIS REQUIREMENTS
============================================================

Identify:

1. NEW INFORMATION

Information present in the current document that was
not present in the previous summary.

2. CHANGED INFORMATION

Information that was present previously but has now
changed in the current document.

3. REMOVED INFORMATION

Information mentioned in the previous summary that
is no longer supported by the current document.

4. UNCHANGED INFORMATION

Important information that remains the same.

============================================================
OUTPUT FORMAT
============================================================

Use exactly these sections:

New Information:

Changed Information:

Removed Information:

Unchanged Information:

Overall Update:


============================================================
IMPORTANT RULES
============================================================

- Compare only the information provided.
- Do not invent information.
- Do not assume information that is not present.
- Do not treat rewording as a change unless the meaning
  actually changed.
- Clearly distinguish genuinely new information from
  information already present in the previous summary.
- If a section has no meaningful items, write:
  "None identified."
- Keep the result clear and professional.
"""

    # --------------------------------------------------------
    # Call Groq with automatic retry
    # --------------------------------------------------------

    messages = [
        {
            "role": "system",
            "content": (
                "You are a professional document "
                "change-detection assistant. "
                "Compare previous and current information "
                "accurately and identify meaningful changes "
                "without inventing information."
            )
        },
        {
            "role": "user",
            "content": prompt
        }
    ]

    return _call_groq_chat(
        messages=messages,
        temperature=0.2,
        operation="update-summary"
    )


# ============================================================
# DOCUMENT CHUNKING UTILITY (HEADING & STRUCTURE AWARE)
# ============================================================

HEADING_PATTERNS = [
    re.compile(r"^#{1,6}\s+\S+", re.MULTILINE),  # Markdown headings: # Heading
    re.compile(r"^\d+(\.\d+)*\s+[A-Z]", re.MULTILINE),  # Numbered sections: 1. Introduction, 2.1 Methods
    re.compile(r"^(Chapter|Section|Part|Appendix|Overview|Background|Methodology|Results|Discussion|Conclusion)\b", re.IGNORECASE | re.MULTILINE),
    re.compile(r"^[A-Z0-9\s\-_:]{4,50}$", re.MULTILINE)  # ALL CAPS HEADINGS
]


def is_heading(line: str) -> bool:
    """
    Check if a line matches a heading or major section boundary.
    """
    line = line.strip()
    if not line or len(line) > 100:
        return False
    return any(p.match(line) for p in HEADING_PATTERNS)


def chunk_text(
    text: str,
    chunk_size: int = 2000,
    chunk_overlap: int = 150
) -> list[str]:
    """
    Split text into logical chunks respecting heading, paragraph,
    and sentence boundaries while preserving contextual continuity.
    """
    if not text or not text.strip():
        return []

    text = text.strip()

    # If the text is already small enough, return as a single clean chunk
    if len(text) <= chunk_size:
        return [text]

    # Split text into paragraphs
    raw_paragraphs = re.split(r"\n\s*\n", text)
    chunks = []
    current_chunk = ""

    for para in raw_paragraphs:
        para = para.strip()
        if not para:
            continue

        # Check if the paragraph starts with a heading/section title
        first_line = para.split("\n")[0].strip()
        starts_heading = is_heading(first_line)

        # If it starts with a heading and the current chunk already has substantial content,
        # close the current chunk and begin a fresh chunk at the heading.
        if starts_heading and len(current_chunk) >= (chunk_size * 0.4):
            chunks.append(current_chunk.strip())
            current_chunk = ""

        # If a single paragraph exceeds chunk_size, split by sentences
        if len(para) > chunk_size:
            if current_chunk:
                chunks.append(current_chunk.strip())
                current_chunk = ""

            sentences = re.split(r"(?<=[.!?])\s+", para)
            sentence_chunk = ""

            for sentence in sentences:
                sentence = sentence.strip()
                if not sentence:
                    continue

                if len(sentence) > chunk_size:
                    if sentence_chunk:
                        chunks.append(sentence_chunk.strip())
                        sentence_chunk = ""

                    # Break long sentences at word boundaries
                    words = sentence.split()
                    word_chunk = ""
                    for word in words:
                        if len(word_chunk) + len(word) + 1 <= chunk_size:
                            word_chunk = f"{word_chunk} {word}".strip()
                        else:
                            if word_chunk:
                                chunks.append(word_chunk.strip())
                            word_chunk = word
                    if word_chunk:
                        sentence_chunk = word_chunk
                else:
                    if len(sentence_chunk) + len(sentence) + 1 <= chunk_size:
                        sentence_chunk = f"{sentence_chunk} {sentence}".strip()
                    else:
                        if sentence_chunk:
                            chunks.append(sentence_chunk.strip())
                        sentence_chunk = sentence

            if sentence_chunk:
                chunks.append(sentence_chunk.strip())

        else:
            # Paragraph fits within remaining chunk budget
            if len(current_chunk) + len(para) + 2 <= chunk_size:
                if current_chunk:
                    current_chunk = f"{current_chunk}\n\n{para}"
                else:
                    current_chunk = para
            else:
                if current_chunk:
                    chunks.append(current_chunk.strip())
                current_chunk = para

    if current_chunk:
        chunks.append(current_chunk.strip())

    # Filter out empty or whitespace-only chunks and chunks with negligible content
    filtered_chunks = []
    for c in chunks:
        clean = c.strip()
        # Keep chunk if it contains any readable alphanumeric characters
        if clean and any(ch.isalnum() for ch in clean):
            filtered_chunks.append(clean)

    return filtered_chunks if filtered_chunks else ([text] if text else [])


# ============================================================
# CHUNK / SECTION SUMMARIZATION (MAP STEP)
# ============================================================

def summarize_chunk(
    chunk: str,
    chunk_index: int,
    total_chunks: int
) -> str:
    """
    Summarize a single document section/chunk.
    Preserves facts, key findings, entities, and context.
    """
    prompt = f"""
You are analyzing Section {chunk_index} of {total_chunks} of a larger document.

Summarize the key information, factual details, decisions, and findings in this section.
Keep the summary clear, accurate, and concise so it can be combined with other sections.

RULES:
- Preserve factual accuracy.
- Do not invent information.
- Extract the essential points, metrics, and context.
- Keep output concise (1-3 paragraphs or structured bullet points).

SECTION {chunk_index} CONTENT:
{chunk}
"""

    messages = [
        {
            "role": "system",
            "content": (
                "You are an expert document analysis assistant. "
                "Accurately summarize the section provided without hallucination."
            )
        },
        {
            "role": "user",
            "content": prompt
        }
    ]

    return _call_groq_chat(
        messages=messages,
        temperature=0.2,
        operation=f"section {chunk_index} summarization"
    )


# ============================================================
# TIER-2 INTERMEDIATE SYNTHESIS (FOR LARGE DOCUMENTS)
# ============================================================

def synthesize_intermediate_batch(
    section_summaries_subset: list[dict],
    batch_index: int,
    total_batches: int
) -> str:
    """
    Condense a batch of section summaries into a higher-tier intermediate summary.
    Enables safe summarization of very large documents without exceeding LLM context limits.
    """
    batch_text = "\n\n".join(
        f"--- Section {s['section_index']} ---\n{s['summary']}"
        for s in section_summaries_subset
    )

    prompt = f"""
You are consolidating Part {batch_index} of {total_batches} of a multi-part document analysis.
The following are intermediate summaries of sequential document sections:

{batch_text}

INSTRUCTIONS:
- Synthesize these section summaries into a coherent, condensed intermediate summary.
- Retain all essential facts, decisions, requirements, and findings.
- Remove redundant repetition between sections.
- Keep the result concise and factual.
"""

    messages = [
        {
            "role": "system",
            "content": "You are a master document synthesizer preparing intermediate consolidated summaries."
        },
        {
            "role": "user",
            "content": prompt
        }
    ]

    return _call_groq_chat(
        messages=messages,
        temperature=0.2,
        operation=f"intermediate batch {batch_index} consolidation"
    )


# ============================================================
# HIERARCHICAL SUMMARIZATION (MAP-REDUCE PIPELINE)
# ============================================================

def hierarchical_summarize(
    text: str,
    chunk_size: int = 2000,
    length: str = "medium",
    format: str = "paragraph",
    executive: bool = False
) -> dict:
    """
    Performs hierarchical (Map-Reduce) summarization on a document:
    1. Splits document into logical, heading-aware sections/chunks.
    2. Generates an intermediate summary for each section (Map).
    3. If document is massive, performs multi-tier intermediate consolidation.
    4. Synthesizes all summaries into a final cohesive summary (Reduce).
    """

    # --------------------------------------------------------
    # Validate input text
    # --------------------------------------------------------
    if not text or not text.strip():
        raise ValueError("Cannot summarize empty text.")

    # --------------------------------------------------------
    # Validate chunk_size
    # --------------------------------------------------------
    if chunk_size < 500 or chunk_size > 20000:
        raise ValueError(
            "chunk_size must be between 500 and 20000 characters."
        )

    # --------------------------------------------------------
    # Validate length and format
    # --------------------------------------------------------
    valid_lengths = {"short", "medium", "long"}
    if length not in valid_lengths:
        raise ValueError("length must be one of: short, medium, long.")

    valid_formats = {"paragraph", "bullets", "table"}
    if format not in valid_formats:
        raise ValueError("format must be one of: paragraph, bullets, table.")

    # --------------------------------------------------------
    # Chunk text
    # --------------------------------------------------------
    chunks = chunk_text(text, chunk_size=chunk_size)

    if not chunks:
        raise ValueError("No valid content found to summarize.")

    # If document has only 1 chunk, perform direct summarization
    if len(chunks) == 1:
        final_summary = summarize_text(
            text=chunks[0],
            length=length,
            format=format,
            executive=executive
        )
        return {
            "final_summary": final_summary,
            "section_summaries": [
                {
                    "section_index": 1,
                    "summary": final_summary
                }
            ],
            "total_sections": 1
        }

    # --------------------------------------------------------
    # Map Step: Summarize each chunk concurrently (preserves order)
    # --------------------------------------------------------
    total_chunks = len(chunks)
    section_summaries = [None] * total_chunks

    def _process_chunk(chunk_idx, chunk_text):
        return {
            "section_index": chunk_idx,
            "summary": summarize_chunk(
                chunk=chunk_text,
                chunk_index=chunk_idx,
                total_chunks=total_chunks
            )
        }

    max_workers = min(4, total_chunks)
    start_hierarchical = time.perf_counter()
    logger.info(f"Starting hierarchical Map-Reduce ({total_chunks} chunks, max_workers={max_workers})")

    with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = {
            executor.submit(_process_chunk, idx, chunk): idx
            for idx, chunk in enumerate(chunks, start=1)
        }
        for future in concurrent.futures.as_completed(futures):
            idx = futures[future]
            section_summaries[idx - 1] = future.result()

    map_elapsed = time.perf_counter() - start_hierarchical
    logger.info(f"Hierarchical Map phase completed in {map_elapsed * 1000.0:.1f}ms ({total_chunks} sections)")


    # --------------------------------------------------------
    # Multi-Tier Consolidation for Large Documents (if > 6 sections)
    # --------------------------------------------------------
    intermediate_to_synthesize = ""

    if len(section_summaries) > 6:
        # Group into batches of 3-4 sections to avoid massive single prompt
        batch_size = 4
        batches = [
            section_summaries[i:i + batch_size]
            for i in range(0, len(section_summaries), batch_size)
        ]
        tier2_summaries = []
        for b_idx, batch in enumerate(batches, start=1):
            consolidated = synthesize_intermediate_batch(
                batch,
                batch_index=b_idx,
                total_batches=len(batches)
            )
            tier2_summaries.append(
                f"--- PART {b_idx} SUMMARY (Sections {batch[0]['section_index']}-{batch[-1]['section_index']}) ---\n"
                f"{consolidated}"
            )
        intermediate_to_synthesize = "\n\n".join(tier2_summaries)
    else:
        # Direct combination of section summaries
        combined = []
        for sec in section_summaries:
            combined.append(
                f"--- SECTION {sec['section_index']} SUMMARY ---\n"
                f"{sec['summary']}"
            )
        intermediate_to_synthesize = "\n\n".join(combined)

    # --------------------------------------------------------
    # Reduce Step: Final Synthesis with Style/Length Controls
    # --------------------------------------------------------
    length_instruction = {
        "short": "Keep the final summary very concise and capture only high-level core takeaways.",
        "medium": "Provide a balanced final summary covering the major points of all sections without excessive detail.",
        "long": "Provide a comprehensive, detailed final summary synthesising all section summaries thoroughly."
    }

    format_instruction = {
        "paragraph": "Write the final summary as cohesive, well-connected paragraphs.",
        "bullets": "Write the final summary as organized bullet points representing the main takeaways across all sections.",
        "table": "Write the final summary as a Markdown table with clear column headers summarizing key aspects across sections."
    }

    executive_instruction = ""
    if executive:
        executive_instruction = """
EXECUTIVE SUMMARY FORMAT:
- Focus on key findings, critical decisions, major risks, metrics, and actionable conclusions.
- Structure for leadership review.
"""

    synthesis_prompt = f"""
You are synthesizing intermediate section summaries of a document into a single cohesive final summary.

LENGTH REQUIREMENT:
{length_instruction[length]}

FORMAT REQUIREMENT:
{format_instruction[format]}

{executive_instruction}

IMPORTANT RULES:
- Synthesize the information across all sections into one unified document summary.
- Eliminate cross-section redundancy and repetition.
- Preserve factual accuracy and do not invent any information.
- Provide a coherent flow from start to finish.

INTERMEDIATE SECTION SUMMARIES:
{intermediate_to_synthesize}
"""

    messages = [
        {
            "role": "system",
            "content": (
                "You are a master document synthesizer. "
                "Create a unified, accurate final summary from the provided section summaries."
            )
        },
        {
            "role": "user",
            "content": synthesis_prompt
        }
    ]

    final_summary = _call_groq_chat(
        messages=messages,
        temperature=0.3,
        operation="final synthesis summarization"
    )

    total_elapsed = time.perf_counter() - start_hierarchical
    logger.info(f"Hierarchical summarization completed in {total_elapsed * 1000.0:.1f}ms")

    return {
        "final_summary": final_summary,
        "section_summaries": section_summaries,
        "total_sections": len(section_summaries)
    }

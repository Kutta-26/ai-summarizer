import re
import json
from typing import Optional, Dict, Any, List, Tuple
from app.core.logging_config import get_logger
from app.services.redundancy_service import (
    normalize_text_for_comparison,
    tokenize_words,
    compute_sequence_similarity,
    compute_token_overlap
)

logger = get_logger("faithfulness")

# ============================================================
# PATTERNS FOR CLAIM & FACTUAL ENTITY EXTRACTION
# ============================================================

# Number and metric patterns
PERCENTAGE_PATTERN = re.compile(r"\b\d+(?:\.\d+)?%")
CURRENCY_PATTERN = re.compile(
    r"[\$€£¥]\s*\d+(?:,\d{3})*(?:\.\d+)?(?:\s*(?:billion|million|thousand|trillion|k|m|b))?"
    r"|\b\d+(?:,\d{3})*(?:\.\d+)?\s*(?:billion|million|thousand|trillion|USD|EUR|GBP|dollars?|cents?)\b",
    re.IGNORECASE
)
MEASUREMENT_PATTERN = re.compile(
    r"\b\d+(?:\.\d+)?\s*(?:GB|MB|KB|TB|ms|sec|seconds?|minutes?|hours?|days?|weeks?|months?|years?|kg|km|m|cm|mm|pages?|users?|requests?|tokens?|queries|records|rows|bps|kbps|mbps)\b",
    re.IGNORECASE
)
YEAR_PATTERN = re.compile(r"\b(?:19|20)\d{2}\b")
QUARTER_PATTERN = re.compile(r"\bQ[1-4]\s*(?:20\d{2}|19\d{2})?\b", re.IGNORECASE)
DATE_PATTERN = re.compile(
    r"\b(?:Jan(?:uary)?|Feb(?:ruary)?|Mar(?:ch)?|Apr(?:il)?|May|Jun(?:e)?|Jul(?:y)?|Aug(?:ust)?|Sep(?:tember)?|Oct(?:ober)?|Nov(?:ember)?|Dec(?:ember)?)\s+\d{1,2}(?:st|nd|rd|th)?(?:\s*,?\s*\d{4})?\b",
    re.IGNORECASE
)
NUMERIC_VALUE_PATTERN = re.compile(r"\b\d+(?:,\d{3})*(?:\.\d+)?\b")

# Common boilerplate / non-factual sentence filters
BOILERPLATE_PATTERNS = [
    re.compile(r"^(in summary|in conclusion|to summarize|overall|the following (?:table|points|bullets|summary)|below is|this document (?:outlines|describes|presents|summarizes))\b", re.IGNORECASE),
    re.compile(r"^(section \d+|part \d+|chapter \d+|summary:)\s*$", re.IGNORECASE),
]

# Common English stop words not to treat as entities
COMMON_WORDS = {
    "the", "a", "an", "this", "that", "these", "those", "it", "its", "they",
    "their", "we", "our", "you", "your", "he", "she", "his", "her", "in", "on",
    "at", "by", "for", "with", "about", "against", "between", "into", "through",
    "during", "before", "after", "above", "below", "to", "from", "up", "down",
    "and", "but", "or", "so", "if", "because", "as", "until", "while", "of",
    "furthermore", "moreover", "however", "therefore", "thus", "consequently",
    "additionally", "similarly", "meanwhile", "overall", "first", "second",
    "third", "finally", "specifically", "key", "main", "primary", "important",
    "critical", "high", "low", "new", "major", "minor", "system", "document",
    "section", "table", "chart", "report", "analysis", "data", "results", "summary"
}


# ============================================================
# NORMALIZATION HELPERS
# ============================================================

def normalize_number(num_str: str) -> str:
    """
    Normalizes a numerical string (stripping currency, lowercasing, converting word multipliers).
    Examples:
      '$4.2 million' -> '4.2m'
      '25%' -> '25%'
      '1,000' -> '1000'
    """
    if not num_str:
        return ""
    s = num_str.lower().strip()
    s = s.replace(",", "").replace("$", "").replace("€", "").replace("£", "").replace("¥", "").strip()
    s = re.sub(r"\bmillion\b", "m", s)
    s = re.sub(r"\bbillion\b", "b", s)
    s = re.sub(r"\bthousand\b", "k", s)
    s = re.sub(r"\btrillion\b", "t", s)
    s = re.sub(r"\s+", "", s)
    return s


def match_number_in_text(num: str, text: str) -> bool:
    """
    Checks if a number/percentage/currency quantity is supported by a text passage.
    """
    norm_num = normalize_number(num)
    extracted = extract_numbers_from_text(text)
    for ext in extracted:
        if normalize_number(ext) == norm_num:
            return True

    # Check exact substring with boundary
    clean_num = num.replace("$", "").replace("€", "").replace("£", "").replace("¥", "").strip()
    pattern = r"(?<![\w\.])" + re.escape(clean_num) + r"(?![\w\.])"
    if re.search(pattern, text, re.IGNORECASE):
        return True

    return False


def normalize_date(date_str: str) -> str:
    """Normalizes a date/year string for comparison."""
    if not date_str:
        return ""
    return re.sub(r"\s+", " ", date_str.lower().strip())


def match_date_in_text(date_str: str, text: str) -> bool:
    """Checks if a date/quarter/year is supported by a text passage."""
    norm_d = normalize_date(date_str)
    extracted = extract_dates_from_text(text)
    for ext in extracted:
        norm_ext = normalize_date(ext)
        if norm_ext == norm_d or norm_d in norm_ext or norm_ext in norm_d:
            return True

    pattern = r"(?<!\w)" + re.escape(date_str.strip()) + r"(?!\w)"
    if re.search(pattern, text, re.IGNORECASE):
        return True

    return False


# ============================================================
# LEVEL 1: CLAIM EXTRACTION
# ============================================================

def clean_sentence_for_claim(text: str) -> str:
    """
    Strips leading markdown list markers, numbering, table pipes, and excess whitespace.
    """
    cleaned = text.strip()
    if cleaned.startswith("|") and cleaned.endswith("|"):
        cells = [c.strip() for c in cleaned.split("|") if c.strip() and not set(c.strip()).issubset({"-", ":"})]
        cleaned = " — ".join(cells)
    cleaned = re.sub(r"^[\s*•\-\d\.\)\#]+", "", cleaned).strip()
    return cleaned


def is_factual_claim(sentence: str) -> bool:
    """
    Determines if a sentence is a substantive factual claim worth verifying.
    Excludes pure headers, boilerplate intros, or trivial greetings.
    """
    if not sentence or len(sentence.strip()) < 10:
        return False
    clean = sentence.strip()
    for bp in BOILERPLATE_PATTERNS:
        if bp.search(clean):
            return False
    words = clean.split()
    if len(words) < 3:
        return False
    return True


def extract_numbers_from_text(text: str) -> List[str]:
    """
    Extracts all distinct numbers, percentages, currencies, and measurements from text.
    """
    numbers = []
    # 1. Percentages
    for p in PERCENTAGE_PATTERN.findall(text):
        if p not in numbers:
            numbers.append(p)
    # 2. Currency
    for c in CURRENCY_PATTERN.findall(text):
        if c not in numbers:
            numbers.append(c)
    # 3. Measurements with units
    for m in MEASUREMENT_PATTERN.findall(text):
        if m not in numbers:
            numbers.append(m)
    # 4. Standalone numbers (integers / decimals)
    for n in NUMERIC_VALUE_PATTERN.findall(text):
        if len(n) == 4 and (n.startswith("19") or n.startswith("20")):
            continue
        if n not in numbers and not any(n in existing for existing in numbers):
            numbers.append(n)
    return numbers


def extract_dates_from_text(text: str) -> List[str]:
    """
    Extracts dates, years, and quarters from text.
    """
    dates = []
    for d in DATE_PATTERN.findall(text):
        if d not in dates:
            dates.append(d)
    for q in QUARTER_PATTERN.findall(text):
        if q not in dates:
            dates.append(q)
    for y in YEAR_PATTERN.findall(text):
        if y not in dates and not any(y in d for d in dates):
            dates.append(y)
    return dates


def extract_entities_from_text(text: str) -> List[str]:
    """
    Lightweight, deterministic named-entity and proper-noun extractor.
    Extracts capitalized sequences and specific identifiers without heavy NLP dependencies.
    """
    entities = []
    pattern = re.compile(r"\b[A-Z][a-zA-Z0-9]*(?:\s+[A-Z][a-zA-Z0-9]*)*\b")
    for match in pattern.finditer(text):
        candidate = match.group(0).strip()
        # Strip leading preposition if attached (e.g. "In Q3" -> "Q3")
        for prep in ["In ", "On ", "At ", "By ", "From ", "To ", "With ", "For "]:
            if candidate.startswith(prep):
                candidate = candidate[len(prep):].strip()
        if not candidate:
            continue
        candidate_words = candidate.split()
        if len(candidate_words) == 1:
            word_lower = candidate.lower()
            if word_lower in COMMON_WORDS or len(candidate) < 3:
                continue
            if re.match(r"^(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec|Quarter|Q[1-4])$", candidate, re.IGNORECASE):
                continue
        else:
            if all(w.lower() in COMMON_WORDS for w in candidate_words):
                continue
            # If it's a date or quarter, skip from entities
            if re.search(r"\b(?:19|20)\d{2}\b", candidate) or re.search(r"\bQ[1-4]\b", candidate):
                continue
        if candidate not in entities:
            entities.append(candidate)
    return entities


def extract_claims(summary_text: str) -> List[Dict[str, Any]]:
    """
    Extracts structured factual claims from summary text.
    Decomposes paragraphs, lists, and table rows into discrete claims.
    """
    if not summary_text or not summary_text.strip():
        return []

    claims = []
    raw_lines = summary_text.splitlines()
    sentences = []

    for line in raw_lines:
        line_clean = line.strip()
        if not line_clean:
            continue
        if line_clean.startswith("|") and line_clean.endswith("|"):
            cleaned_row = clean_sentence_for_claim(line_clean)
            if is_factual_claim(cleaned_row):
                sentences.append(cleaned_row)
            continue
        parts = re.split(r"(?<=[.!?])\s+", line_clean)
        for part in parts:
            cleaned_part = clean_sentence_for_claim(part)
            if is_factual_claim(cleaned_part):
                sentences.append(cleaned_part)

    for sent in sentences:
        numbers = extract_numbers_from_text(sent)
        dates = extract_dates_from_text(sent)
        entities = extract_entities_from_text(sent)

        if numbers:
            claim_type = "quantitative"
        elif dates:
            claim_type = "date_specific"
        elif entities:
            claim_type = "entity_statement"
        else:
            claim_type = "factual"

        claims.append({
            "claim": sent,
            "type": claim_type,
            "numbers": numbers,
            "dates": dates,
            "entities": entities
        })

    return claims


# ============================================================
# LEVEL 2: SOURCE EVIDENCE MATCHING
# ============================================================

def segment_source_into_evidence_units(source_text: str) -> List[str]:
    """
    Segments source document into fine-grained sentence/clause units for candidate retrieval.
    """
    if not source_text or not source_text.strip():
        return []
    units = []
    for paragraph in source_text.splitlines():
        paragraph = paragraph.strip()
        if not paragraph:
            continue
        sents = re.split(r"(?<=[.!?])\s+", paragraph)
        for s in sents:
            s_clean = s.strip()
            if len(s_clean) >= 15:
                units.append(s_clean)
    return units if units else [source_text.strip()]


def find_candidate_evidence(
    claim: Dict[str, Any],
    evidence_units: List[str]
) -> List[Tuple[str, float]]:
    """
    Searches source evidence units for the most relevant candidate passages supporting the claim.
    Combines token Jaccard overlap, asymmetric containment, and sequence similarity.
    Returns ranked list of (passage, similarity_score).
    """
    claim_text = claim["claim"]
    claim_numbers = set(normalize_number(n) for n in claim.get("numbers", []))
    claim_dates = set(normalize_date(d) for d in claim.get("dates", []))
    claim_entities = set(e.lower() for e in claim.get("entities", []))

    scored_units = []

    for unit in evidence_units:
        seq_sim = compute_sequence_similarity(claim_text, unit)
        jaccard, cont_claim, cont_unit = compute_token_overlap(claim_text, unit)

        combined_sim = (0.45 * seq_sim) + (0.35 * jaccard) + (0.20 * cont_claim)

        # Numerical overlap bonus
        unit_numbers = set(normalize_number(n) for n in extract_numbers_from_text(unit))
        if claim_numbers:
            matching_numbers = claim_numbers.intersection(unit_numbers)
            if matching_numbers:
                combined_sim += 0.25 * (len(matching_numbers) / len(claim_numbers))

        # Date overlap bonus
        unit_dates = set(normalize_date(d) for d in extract_dates_from_text(unit))
        if claim_dates:
            matching_dates = claim_dates.intersection(unit_dates)
            if matching_dates:
                combined_sim += 0.20 * (len(matching_dates) / len(claim_dates))

        # Entity overlap bonus
        unit_entities = set(e.lower() for e in extract_entities_from_text(unit))
        if claim_entities:
            matching_entities = claim_entities.intersection(unit_entities)
            if matching_entities:
                combined_sim += 0.15 * (len(matching_entities) / len(claim_entities))

        normalized_score = min(1.0, combined_sim)
        if normalized_score > 0.15:
            scored_units.append((unit, normalized_score))

    scored_units.sort(key=lambda x: x[1], reverse=True)
    return scored_units[:5]


# ============================================================
# LEVELS 3, 4, 5: NUMERICAL, DATE & ENTITY VALIDATION
# ============================================================

def validate_numerics(
    claim_numbers: List[str],
    candidate_evidence: List[Tuple[str, float]],
    source_text: str
) -> Tuple[bool, Optional[str], Optional[str]]:
    """
    Strict numerical validation.
    Checks whether numbers in the claim are supported by the source evidence.
    Returns: (is_supported, reason, evidence_match)
    """
    if not claim_numbers:
        return True, None, None

    for num in claim_numbers:
        # Check if number exists anywhere in source text
        if match_number_in_text(num, source_text):
            continue

        # If not in source, check if candidate evidence has a differing number
        diff_number_found = None
        for cand_text, _ in candidate_evidence:
            cand_numbers = extract_numbers_from_text(cand_text)
            for cn in cand_numbers:
                if normalize_number(cn) != normalize_number(num):
                    diff_number_found = cn
                    break
            if diff_number_found:
                break

        if diff_number_found:
            return (
                False,
                f"Unsupported/inconsistent numerical claim: summary states '{num}', but source evidence states '{diff_number_found}'.",
                candidate_evidence[0][0] if candidate_evidence else None
            )
        else:
            return (
                False,
                f"Unsupported numerical claim: number '{num}' is not supported by source material.",
                candidate_evidence[0][0] if candidate_evidence else None
            )

    return True, None, None


def validate_dates(
    claim_dates: List[str],
    candidate_evidence: List[Tuple[str, float]],
    source_text: str
) -> Tuple[bool, Optional[str], Optional[str]]:
    """
    Strict date and year validation.
    Checks whether dates in the claim are supported by the source evidence.
    """
    if not claim_dates:
        return True, None, None

    for date_item in claim_dates:
        if match_date_in_text(date_item, source_text):
            continue

        diff_date_found = None
        for cand_text, _ in candidate_evidence:
            cand_dates = extract_dates_from_text(cand_text)
            for cd in cand_dates:
                if normalize_date(cd) != normalize_date(date_item):
                    diff_date_found = cd
                    break
            if diff_date_found:
                break

        if diff_date_found:
            return (
                False,
                f"Unsupported date claim: summary mentions '{date_item}', but source evidence states '{diff_date_found}'.",
                candidate_evidence[0][0] if candidate_evidence else None
            )
        else:
            return (
                False,
                f"Unsupported date claim: '{date_item}' is not supported by source material.",
                candidate_evidence[0][0] if candidate_evidence else None
            )

    return True, None, None


def validate_entities(
    claim_entities: List[str],
    candidate_evidence: List[Tuple[str, float]],
    source_text: str
) -> Tuple[bool, Optional[str], Optional[str]]:
    """
    Validates important named entities and proper nouns.
    Ensures that named technologies, companies, or persons asserted in the claim exist in the source.
    """
    if not claim_entities:
        return True, None, None

    for entity in claim_entities:
        entity_clean = entity.strip()
        pattern = r"(?<!\w)" + re.escape(entity_clean) + r"(?!\w)"
        if re.search(pattern, source_text, re.IGNORECASE):
            continue

        return (
            False,
            f"Unsupported entity: '{entity_clean}' does not appear in source material.",
            candidate_evidence[0][0] if candidate_evidence else None
        )

    return True, None, None


# ============================================================
# LEVEL 6: OPTIONAL BOUNDED LLM VERIFICATION
# ============================================================

def verify_claims_with_llm_batch(
    unresolved_claims: List[Dict[str, Any]],
    source_context: str
) -> List[Dict[str, Any]]:
    """
    Batches unresolved claims into a single bounded Groq LLM call.
    Uses strict prompt rules prohibiting external knowledge and hallucination.
    Falls back safely if LLM call fails, times out, or returns malformed response.
    """
    if not unresolved_claims:
        return []

    try:
        from app.services.groq_service import _call_groq_chat

        claims_prompt_list = []
        for idx, item in enumerate(unresolved_claims, start=1):
            claim_text = item["claim"]
            cand_evidence = item.get("evidence", "No direct sentence match.")
            claims_prompt_list.append(
                f"Claim {idx}:\nText: \"{claim_text}\"\nRelevant Evidence Excerpt: \"{cand_evidence}\"\n"
            )

        claims_formatted = "\n".join(claims_prompt_list)

        prompt = f"""
You are a strict faithfulness verification judge.
Determine if each generated summary claim is supported by the provided source evidence.

CRITICAL RULES:
1. Use ONLY the provided source evidence.
2. Do NOT use external or background knowledge.
3. If evidence is insufficient, return "UNCERTAIN".
4. If the claim introduces facts, entities, numbers, or dates not in the evidence, return "UNSUPPORTED".
5. If the claim is fully supported by the evidence, return "SUPPORTED".
6. If parts are supported but key details are omitted or unverified, return "PARTIALLY_SUPPORTED".
7. Preserve numerical and date precision.

CLAIMS TO VERIFY:
{claims_formatted}

SOURCE CONTEXT:
{source_context[:3000]}

Respond ONLY with a valid JSON array of objects formatted exactly as:
[
  {{
    "claim_index": 1,
    "status": "SUPPORTED" | "PARTIALLY_SUPPORTED" | "UNSUPPORTED" | "UNCERTAIN",
    "confidence": <float between 0.0 and 1.0>,
    "reason": "<concise explanation>"
  }}
]
"""

        messages = [
            {
                "role": "system",
                "content": "You are a professional faithfulness verifier. Output valid JSON array only."
            },
            {
                "role": "user",
                "content": prompt
            }
        ]

        content = _call_groq_chat(
            messages=messages,
            temperature=0.1,
            operation="faithfulness verification"
        )

        match = re.search(r"\[.*\]", content, re.DOTALL)
        if match:
            results = json.loads(match.group(0))
            if isinstance(results, list):
                mapped_results = []
                for idx, item in enumerate(unresolved_claims, start=1):
                    llm_item = next((r for r in results if r.get("claim_index") == idx), None)
                    if llm_item and llm_item.get("status") in {"SUPPORTED", "PARTIALLY_SUPPORTED", "UNSUPPORTED", "UNCERTAIN"}:
                        mapped_results.append({
                            **item,
                            "status": llm_item["status"],
                            "confidence": float(llm_item.get("confidence", 0.90)),
                            "reason": llm_item.get("reason", "Verified by LLM against source evidence.")
                        })
                    else:
                        mapped_results.append(item)
                return mapped_results

    except Exception as e:
        logger.warning(f"LLM verification call failed or bypassed, using deterministic fallback: {str(e)}")

    return unresolved_claims


# ============================================================
# DETERMINISTIC VERIFICATION ENGINE
# ============================================================

def verify_single_claim(
    claim: Dict[str, Any],
    candidate_evidence: List[Tuple[str, float]],
    source_text: str
) -> Dict[str, Any]:
    """
    Deterministically verifies an individual claim against candidate evidence and source document.
    """
    claim_text = claim["claim"]
    best_evidence = candidate_evidence[0][0] if candidate_evidence else None
    best_sim = candidate_evidence[0][1] if candidate_evidence else 0.0

    # 1. Numerical check
    num_ok, num_reason, num_ev = validate_numerics(claim.get("numbers", []), candidate_evidence, source_text)
    if not num_ok:
        return {
            "claim": claim_text,
            "status": "UNSUPPORTED",
            "evidence": num_ev or best_evidence,
            "confidence": 0.98,
            "claim_type": claim["type"],
            "reason": num_reason
        }

    # 2. Date check
    date_ok, date_reason, date_ev = validate_dates(claim.get("dates", []), candidate_evidence, source_text)
    if not date_ok:
        return {
            "claim": claim_text,
            "status": "UNSUPPORTED",
            "evidence": date_ev or best_evidence,
            "confidence": 0.98,
            "claim_type": claim["type"],
            "reason": date_reason
        }

    # 3. Entity check
    ent_ok, ent_reason, ent_ev = validate_entities(claim.get("entities", []), candidate_evidence, source_text)
    if not ent_ok:
        return {
            "claim": claim_text,
            "status": "UNSUPPORTED",
            "evidence": ent_ev or best_evidence,
            "confidence": 0.95,
            "claim_type": claim["type"],
            "reason": ent_reason
        }

    # 4. Textual alignment & token overlap check
    if best_sim >= 0.50:
        return {
            "claim": claim_text,
            "status": "SUPPORTED",
            "evidence": best_evidence,
            "confidence": round(min(1.0, 0.70 + (best_sim * 0.30)), 2),
            "claim_type": claim["type"],
            "reason": "Directly supported by matching source passage."
        }
    elif best_sim >= 0.32:
        return {
            "claim": claim_text,
            "status": "PARTIALLY_SUPPORTED",
            "evidence": best_evidence,
            "confidence": round(best_sim, 2),
            "claim_type": claim["type"],
            "reason": "Partially supported by source context; wording differs."
        }
    elif best_sim >= 0.20:
        return {
            "claim": claim_text,
            "status": "UNCERTAIN",
            "evidence": best_evidence,
            "confidence": 0.50,
            "claim_type": claim["type"],
            "reason": "Weak contextual overlap; cannot confidently confirm or refute from source."
        }
    else:
        return {
            "claim": claim_text,
            "status": "UNSUPPORTED",
            "evidence": None,
            "confidence": 0.90,
            "claim_type": claim["type"],
            "reason": "Unsupported claim: no matching evidence found in source document."
        }


# ============================================================
# SCORING & ORCHESTRATION
# ============================================================

def calculate_faithfulness_score(verified_claims: List[Dict[str, Any]]) -> Tuple[float, str]:
    """
    Calculates explainable faithfulness score strictly bounded in [0.0, 1.0].
    Formula:
        score = (supported + 0.5 * partially_supported + 0.25 * uncertain) / total_claims
    Returns: (score, status: 'HIGH' | 'MODERATE' | 'LOW')
    """
    if not verified_claims:
        return 1.0, "HIGH"

    total = len(verified_claims)
    supported = sum(1 for c in verified_claims if c["status"] == "SUPPORTED")
    partially = sum(1 for c in verified_claims if c["status"] == "PARTIALLY_SUPPORTED")
    uncertain = sum(1 for c in verified_claims if c["status"] == "UNCERTAIN")

    weighted_points = supported + (0.50 * partially) + (0.25 * uncertain)
    raw_score = weighted_points / total
    bounded_score = max(0.0, min(1.0, round(raw_score, 2)))

    if bounded_score >= 0.80:
        status = "HIGH"
    elif bounded_score >= 0.50:
        status = "MODERATE"
    else:
        status = "LOW"

    return bounded_score, status


def check_faithfulness(
    source_text: str,
    summary_text: str,
    use_llm: bool = False
) -> Dict[str, Any]:
    """
    Main entry point for Faithfulness Checking.
    Evaluates whether the generated summary is supported by the source document.

    Pipeline:
    1. Validate inputs (empty source / summary guards).
    2. Extract substantive claims with numerical, date, and entity metadata.
    3. Retrieve candidate source evidence using deterministic overlap.
    4. Deterministically validate numbers, dates, entities, and textual overlap.
    5. Optionally resolve ambiguous/uncertain claims via batched LLM verification.
    6. Calculate explainable, bounded faithfulness score and classification.

    Returns structured dictionary conforming to FaithfulnessResult schema.
    """
    if not source_text or not source_text.strip():
        return {
            "faithfulness_score": 0.0,
            "status": "LOW",
            "claims_checked": 0,
            "supported_claims": 0,
            "partially_supported_claims": 0,
            "unsupported_claims": 0,
            "uncertain_claims": 0,
            "claims": []
        }

    if not summary_text or not summary_text.strip():
        return {
            "faithfulness_score": 1.0,
            "status": "HIGH",
            "claims_checked": 0,
            "supported_claims": 0,
            "partially_supported_claims": 0,
            "unsupported_claims": 0,
            "uncertain_claims": 0,
            "claims": []
        }

    extracted_claims = extract_claims(summary_text)

    if not extracted_claims:
        return {
            "faithfulness_score": 1.0,
            "status": "HIGH",
            "claims_checked": 0,
            "supported_claims": 0,
            "partially_supported_claims": 0,
            "unsupported_claims": 0,
            "uncertain_claims": 0,
            "claims": []
        }

    evidence_units = segment_source_into_evidence_units(source_text)

    verified_claims = []
    unresolved_claims_indices = []

    for idx, claim in enumerate(extracted_claims):
        candidate_evidence = find_candidate_evidence(claim, evidence_units)
        verified = verify_single_claim(claim, candidate_evidence, source_text)
        verified_claims.append(verified)

        if use_llm and verified["status"] in {"UNCERTAIN", "PARTIALLY_SUPPORTED"}:
            unresolved_claims_indices.append(idx)

    if use_llm and unresolved_claims_indices:
        unresolved_subset = [verified_claims[i] for i in unresolved_claims_indices]
        llm_resolved = verify_claims_with_llm_batch(unresolved_subset, source_text[:3000])
        for orig_idx, resolved_item in zip(unresolved_claims_indices, llm_resolved):
            verified_claims[orig_idx] = resolved_item

    score, status = calculate_faithfulness_score(verified_claims)

    supported_count = sum(1 for c in verified_claims if c["status"] == "SUPPORTED")
    partially_count = sum(1 for c in verified_claims if c["status"] == "PARTIALLY_SUPPORTED")
    unsupported_count = sum(1 for c in verified_claims if c["status"] == "UNSUPPORTED")
    uncertain_count = sum(1 for c in verified_claims if c["status"] == "UNCERTAIN")

    logger.info(
        f"Faithfulness check complete: score={score:.2f} ({status}), "
        f"checked={len(verified_claims)}, supported={supported_count}, unsupported={unsupported_count}"
    )

    return {
        "faithfulness_score": score,
        "status": status,
        "claims_checked": len(verified_claims),
        "supported_claims": supported_count,
        "partially_supported_claims": partially_count,
        "unsupported_claims": unsupported_count,
        "uncertain_claims": uncertain_count,
        "claims": verified_claims
    }

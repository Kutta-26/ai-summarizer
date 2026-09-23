import re
import difflib
import json
from typing import Optional, Dict, Any, List, Tuple
from app.core.logging_config import get_logger
from app.services.importance_service import (
    score_importance,
    compute_information_density,
    compute_metrics_count
)

logger = get_logger("redundancy")

# ============================================================
# NORMALIZATION & DETERMINISTIC SIMILARITY
# ============================================================

def normalize_text_for_comparison(text: str) -> str:
    """
    Normalize text for robust duplicate comparison:
    - Lowercase
    - Strip leading/trailing whitespace
    - Normalize consecutive whitespace to a single space
    - Strip trailing sentence punctuation
    Preserves alphanumeric terms, numbers, and core structure.
    """
    if not text:
        return ""
    cleaned = text.lower().strip()
    # Normalize all internal whitespace/newlines to single space
    cleaned = re.sub(r"\s+", " ", cleaned)
    # Strip standard sentence ending punctuation
    cleaned = re.sub(r"[.,;:!?]+$", "", cleaned).strip()
    return cleaned


def tokenize_words(text: str) -> List[str]:
    """Extract alphanumeric words from normalized text."""
    return re.findall(r"\b[a-zA-Z0-9_-]+\b", text.lower())


def compute_sequence_similarity(text_a: str, text_b: str) -> float:
    """
    Compute sequence matcher ratio between two strings using standard difflib.
    Returns float in range [0.0, 1.0].
    """
    norm_a = normalize_text_for_comparison(text_a)
    norm_b = normalize_text_for_comparison(text_b)
    if not norm_a or not norm_b:
        return 0.0
    if norm_a == norm_b:
        return 1.0
    return difflib.SequenceMatcher(None, norm_a, norm_b).ratio()


def compute_token_overlap(text_a: str, text_b: str) -> Tuple[float, float, float]:
    """
    Compute token Jaccard similarity and directional containment ratios.
    Returns:
        jaccard: |A & B| / |A | B|
        containment_a: |A & B| / |A| (ratio of A covered by B)
        containment_b: |A & B| / |B| (ratio of B covered by A)
    """
    tokens_a = set(tokenize_words(text_a))
    tokens_b = set(tokenize_words(text_b))

    if not tokens_a or not tokens_b:
        return 0.0, 0.0, 0.0

    intersection = tokens_a.intersection(tokens_b)
    union = tokens_a.union(tokens_b)

    jaccard = len(intersection) / len(union) if union else 0.0
    containment_a = len(intersection) / len(tokens_a) if tokens_a else 0.0
    containment_b = len(intersection) / len(tokens_b) if tokens_b else 0.0

    return jaccard, containment_a, containment_b


def compute_deterministic_similarity(text_a: str, text_b: str) -> float:
    """
    Layered deterministic similarity combining SequenceMatcher ratio,
    word-level Jaccard index, and asymmetric containment.
    Returns a normalized similarity score in range [0.0, 1.0].
    """
    norm_a = normalize_text_for_comparison(text_a)
    norm_b = normalize_text_for_comparison(text_b)

    if not norm_a or not norm_b:
        return 0.0
    if norm_a == norm_b:
        return 1.0

    seq_sim = compute_sequence_similarity(text_a, text_b)
    jaccard, cont_a, cont_b = compute_token_overlap(text_a, text_b)

    # If sequence similarity is high, trust sequence alignment
    if seq_sim >= 0.85:
        return round(seq_sim, 3)

    # If one text's content is heavily subsumed by the other (>= 80% containment)
    max_containment = max(cont_a, cont_b)
    if max_containment >= 0.80:
        return round(max_containment * 0.95, 3)

    # Blended similarity: 50% sequence alignment + 30% Jaccard + 20% containment
    blended = (0.50 * seq_sim) + (0.30 * jaccard) + (0.20 * max_containment)
    return round(min(1.0, max(0.0, blended)), 3)


# ============================================================
# IMPORTANCE-AWARE SECTION EVALUATION
# ============================================================

def evaluate_section_quality(section: Dict[str, Any]) -> float:
    """
    Compute an information quality score to determine which redundant version survives.
    Prefers sections with:
    1. Higher importance score (Phase 1 signal)
    2. Richer numerical and quantitative metrics
    3. Higher lexical information density
    4. More active key signals
    5. Greater specific content depth
    """
    summary_text = section.get("summary", "")
    importance_score = section.get("importance_score")

    if importance_score is None:
        importance_info = score_importance(summary_text)
        importance_score = importance_info["score"]
        signals = importance_info["signals"]
    else:
        signals = section.get("importance_signals") or {}

    density = compute_information_density(summary_text)
    metrics_count = compute_metrics_count(summary_text)
    active_signals_count = sum(1 for v in signals.values() if v)

    # Word count factor (log-scaled to reward specific detail without runaway bias)
    words = tokenize_words(summary_text)
    word_count_factor = min(1.0, len(words) / 50.0)

    quality = (
        (0.40 * importance_score) +
        (0.25 * density) +
        (0.15 * min(1.0, metrics_count * 0.25)) +
        (0.10 * min(1.0, active_signals_count / 4.0)) +
        (0.10 * word_count_factor)
    )

    return round(quality, 4)


# ============================================================
# PAIRWISE REDUNDANCY CHECK
# ============================================================

def check_pairwise_redundancy(
    sec_a: Dict[str, Any],
    sec_b: Dict[str, Any],
    threshold: float = 0.80,
    use_llm: bool = False
) -> Optional[Dict[str, Any]]:
    """
    Compare two section summaries to determine if one is redundant with the other.
    Returns a structured redundancy result dict if redundant, or None if distinct.

    Result format:
    {
        "is_redundant": True,
        "redundancy_type": "exact_duplicate" | "near_duplicate" | "semantic_redundancy",
        "similarity": float,
        "kept_section": int,
        "removed_section": int,
        "reason": str
    }
    """
    text_a = sec_a.get("summary", "").strip()
    text_b = sec_b.get("summary", "").strip()

    if not text_a or not text_b:
        return None

    idx_a = sec_a.get("section_index", 1)
    idx_b = sec_b.get("section_index", 2)

    norm_a = normalize_text_for_comparison(text_a)
    norm_b = normalize_text_for_comparison(text_b)

    # --------------------------------------------------------
    # LEVEL 1: Exact Duplicate Detection
    # --------------------------------------------------------
    if norm_a == norm_b:
        quality_a = evaluate_section_quality(sec_a)
        quality_b = evaluate_section_quality(sec_b)
        # If equal, prefer the earlier section for stability
        if quality_b > quality_a:
            kept_idx, removed_idx = idx_b, idx_a
        else:
            kept_idx, removed_idx = idx_a, idx_b

        return {
            "is_redundant": True,
            "redundancy_type": "exact_duplicate",
            "similarity": 1.0,
            "kept_section": kept_idx,
            "removed_section": removed_idx,
            "reason": (
                f"Section {removed_idx} is an exact duplicate of Section {kept_idx}. "
                f"Preserved Section {kept_idx}."
            )
        }

    # --------------------------------------------------------
    # LEVEL 2: Near-Duplicate Detection (Deterministic)
    # --------------------------------------------------------
    similarity = compute_deterministic_similarity(text_a, text_b)

    if similarity >= threshold:
        quality_a = evaluate_section_quality(sec_a)
        quality_b = evaluate_section_quality(sec_b)

        if quality_b > quality_a:
            kept_idx, removed_idx = idx_b, idx_a
            kept_q, removed_q = quality_b, quality_a
            kept_sec, removed_sec = sec_b, sec_a
        else:
            kept_idx, removed_idx = idx_a, idx_b
            kept_q, removed_q = quality_a, quality_b
            kept_sec, removed_sec = sec_a, sec_b

        imp_kept = kept_sec.get("importance_score", 0.0)
        imp_removed = removed_sec.get("importance_score", 0.0)
        metrics_kept = compute_metrics_count(kept_sec.get("summary", ""))
        metrics_removed = compute_metrics_count(removed_sec.get("summary", ""))

        reason = (
            f"Section {removed_idx} is a near-duplicate ({int(similarity * 100)}% similarity) of Section {kept_idx}. "
            f"Preserved Section {kept_idx} based on higher information quality "
            f"(importance score {imp_kept:.2f} vs {imp_removed:.2f}, {metrics_kept} vs {metrics_removed} metrics)."
        )

        return {
            "is_redundant": True,
            "redundancy_type": "near_duplicate",
            "similarity": similarity,
            "kept_section": kept_idx,
            "removed_section": removed_idx,
            "reason": reason
        }

    # --------------------------------------------------------
    # LEVEL 3: Semantic Redundancy (Bounded LLM Candidate Check)
    # --------------------------------------------------------
    if use_llm and similarity >= 0.65:
        llm_res = _call_llm_for_redundancy(text_a, text_b, idx_a, idx_b)
        if llm_res and llm_res.get("is_redundant"):
            quality_a = evaluate_section_quality(sec_a)
            quality_b = evaluate_section_quality(sec_b)

            if quality_b > quality_a:
                kept_idx, removed_idx = idx_b, idx_a
            else:
                kept_idx, removed_idx = idx_a, idx_b

            return {
                "is_redundant": True,
                "redundancy_type": "semantic_redundancy",
                "similarity": float(llm_res.get("similarity", similarity)),
                "kept_section": kept_idx,
                "removed_section": removed_idx,
                "reason": llm_res.get(
                    "reason",
                    f"Section {removed_idx} is semantically redundant with Section {kept_idx}."
                )
            }

    return None


def _call_llm_for_redundancy(
    text_a: str,
    text_b: str,
    idx_a: int,
    idx_b: int
) -> Optional[Dict[str, Any]]:
    """
    Optionally assess semantic redundancy using Groq LLM for candidate pairs.
    Bounded and safe: fails gracefully to deterministic fallback on error.
    """
    try:
        from app.services.groq_service import _call_groq_chat

        prompt = f"""
Compare the following two document section summaries to determine if one is semantically redundant with the other.

SECTION {idx_a}:
{text_a[:1000]}

SECTION {idx_b}:
{text_b[:1000]}

RULES:
- A section is redundant ONLY if it conveys essentially the same core finding or fact without adding distinct context or unique decisions.
- If both sections describe different metrics, time periods, or distinct components, they are NOT redundant.

Respond strictly in valid JSON format:
{{
    "is_redundant": <true/false>,
    "similarity": <float between 0.0 and 1.0>,
    "reason": "<concise explanation>"
}}
"""
        messages = [
            {
                "role": "system",
                "content": "You are a professional document redundancy analyzer. Respond in valid JSON only."
            },
            {
                "role": "user",
                "content": prompt
            }
        ]

        content = _call_groq_chat(
            messages=messages,
            temperature=0.1,
            operation="semantic redundancy check"
        )

        match = re.search(r"\{.*\}", content, re.DOTALL)
        if match:
            return json.loads(match.group(0))
    except Exception as e:
        logger.warning(f"Semantic redundancy LLM check bypassed: {str(e)}")

    return None


# ============================================================
# MULTI-SECTION DEDUPLICATION PIPELINE
# ============================================================

def detect_and_filter_redundancy(
    section_summaries: List[Dict[str, Any]],
    threshold: float = 0.80,
    use_llm: bool = False
) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
    """
    Analyzes an array of section summaries, detects redundant sections,
    and enriches each section dictionary with redundancy metadata.

    Preserves all sections in the returned list for UI inspection, marking
    redundant sections with:
    - is_redundant: True
    - redundancy_info: { ... }

    Returns:
    - processed_sections: all original sections with is_redundant and redundancy_info.
    - redundancy_records: list of detected redundancy events.
    """
    if not section_summaries or len(section_summaries) <= 1:
        # 0 or 1 section cannot be redundant
        clean_sections = []
        for s in section_summaries:
            item = dict(s)
            item.setdefault("is_redundant", False)
            item.setdefault("redundancy_info", None)
            clean_sections.append(item)
        return clean_sections, []

    # Make working copy of sections
    processed = [dict(s) for s in section_summaries]
    for p in processed:
        p.setdefault("is_redundant", False)
        p.setdefault("redundancy_info", None)

    redundancy_records = []
    n = len(processed)

    # Compare pairs sequentially
    for i in range(n):
        if processed[i].get("is_redundant"):
            continue

        for j in range(i + 1, n):
            if processed[j].get("is_redundant"):
                continue

            redundancy = check_pairwise_redundancy(
                sec_a=processed[i],
                sec_b=processed[j],
                threshold=threshold,
                use_llm=use_llm
            )

            if redundancy and redundancy.get("is_redundant"):
                removed_idx = redundancy["removed_section"]
                kept_idx = redundancy["kept_section"]

                # Mark the removed section as redundant
                target_sec = processed[i] if processed[i].get("section_index") == removed_idx else processed[j]
                target_sec["is_redundant"] = True
                target_sec["redundancy_info"] = redundancy
                redundancy_records.append(redundancy)

                logger.info(
                    f"Redundancy detected: Section {removed_idx} redundant with Section {kept_idx} "
                    f"({redundancy['redundancy_type']}, similarity={redundancy['similarity']:.2f})"
                )

                # If section i was the one removed, stop comparing it against subsequent sections
                if processed[i].get("section_index") == removed_idx:
                    break

    return processed, redundancy_records


def filter_synthesis_sections(section_summaries: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    Extracts only the non-redundant sections to be sent to the Reduce synthesis phase.
    Safety guarantee: If all sections happen to be marked redundant, preserves at least
    the single highest-quality section so synthesis never starves.
    """
    if not section_summaries:
        return []

    active_sections = [s for s in section_summaries if not s.get("is_redundant", False)]

    # Safety fallback: preserve highest-quality section if all were filtered
    if not active_sections:
        best_section = max(section_summaries, key=evaluate_section_quality)
        active_sections = [best_section]

    return active_sections

import re
from typing import Optional, Dict, Any, List, Tuple, Set
from app.core.logging_config import get_logger
from app.services.redundancy_service import (
    normalize_text_for_comparison,
    tokenize_words,
    compute_sequence_similarity,
    compute_token_overlap
)
from app.services.faithfulness_service import (
    extract_claims,
    segment_source_into_evidence_units,
    extract_numbers_from_text,
    extract_dates_from_text,
    extract_entities_from_text,
    normalize_number,
    normalize_date,
    PERCENTAGE_PATTERN,
    CURRENCY_PATTERN,
    MEASUREMENT_PATTERN,
    YEAR_PATTERN,
    QUARTER_PATTERN,
    DATE_PATTERN,
    NUMERIC_VALUE_PATTERN
)

logger = get_logger("contradiction")

# ============================================================
# CONSTANTS & LEXICAL PATTERNS
# ============================================================

PERCENT_EXPR_PATTERN = re.compile(
    r"\b(\d+(?:\.\d+)?)\s*(?:%(?!\w)|\bpercent\b|\bpercentage\b)",
    re.IGNORECASE
)

MONTH_DATE_PATTERN = re.compile(
    r"\b(?:Jan(?:uary)?|Feb(?:ruary)?|Mar(?:ch)?|Apr(?:il)?|May|Jun(?:e)?|Jul(?:y)?|Aug(?:ust)?|Sep(?:tember)?|Oct(?:ober)?|Nov(?:ember)?|Dec(?:ember)?)(?:\s+\d{1,2}(?:st|nd|rd|th)?)?(?:\s*,?\s*(?:19|20)\d{2})?\b",
    re.IGNORECASE
)

# Geographic and common non-exclusive location indicators
LOCATION_TERMS = {
    "london", "paris", "tokyo", "berlin", "new york", "san francisco",
    "sydney", "singapore", "toronto", "boston", "chicago", "seattle",
    "beijing", "shanghai", "mumbai", "dublin", "amsterdam", "austin"
}

# Transaction & exclusive relation verbs/phrases where entity substitution indicates conflict
EXCLUSIVE_TRANSACTION_VERBS = {
    "acquire", "acquired", "acquires", "acquiring", "acquisition",
    "bought", "buys", "buying", "purchased", "purchases", "purchasing",
    "takeover", "merged with", "merging with",
    "appointed", "appoints", "named", "elected", "promoted",
    "succeeded", "replaces", "replaced",
    "invented by", "founded by", "authored by", "discovered by",
    "headquartered in", "founded in"
}

# Antonym pairs for direct factual conflict detection (both directions checked)
ANTONYM_PAIRS: List[Tuple[str, str]] = [
    # Approval & Acceptance
    ("approved", "rejected"),
    ("approved", "denied"),
    ("approved", "disapproved"),
    ("approved", "cancelled"),
    ("accepted", "rejected"),
    ("accepted", "declined"),
    # Success & Failure
    ("passed", "failed"),
    ("succeeded", "failed"),
    ("success", "failure"),
    ("successful", "unsuccessful"),
    # Directional Growth & Decline
    ("increased", "decreased"),
    ("increased", "reduced"),
    ("increased", "dropped"),
    ("increased", "declined"),
    ("increased", "fell"),
    ("grew", "shrank"),
    ("expanded", "contracted"),
    ("expansion", "contraction"),
    ("rose", "fell"),
    ("growth", "decline"),
    ("rise", "fall"),
    ("gain", "loss"),
    ("gained", "lost"),
    # Capability & Feature enablement
    ("enabled", "disabled"),
    ("activated", "deactivated"),
    ("supported", "unsupported"),
    # Permission & Legality
    ("permitted", "prohibited"),
    ("permitted", "forbidden"),
    ("allowed", "banned"),
    ("legal", "illegal"),
    ("lawful", "unlawful"),
    ("compliant", "non-compliant"),
    ("valid", "invalid"),
    ("safe", "unsafe"),
    ("secure", "insecure"),
    ("mandatory", "optional"),
    ("required", "optional"),
    # Financial state
    ("profitable", "unprofitable"),
    ("profit", "loss"),
    ("stable", "unstable"),
    ("reliable", "unreliable"),
    ("accelerated", "decelerated"),
]

# Negation words/phrases for polarity checking
NEGATION_PATTERNS = [
    re.compile(r"\b(?:does|did|do|will|would|can|could|should|is|are|was|were|has|have|had)\s+not\b", re.IGNORECASE),
    re.compile(r"\bcannot\b", re.IGNORECASE),
    re.compile(r"\bnever\b", re.IGNORECASE),
    re.compile(r"\bno\s+longer\b", re.IGNORECASE),
    re.compile(r"\bfails?\s+to\b", re.IGNORECASE),
]


# ============================================================
# HELPER EXTRACTION & NORMALIZATION
# ============================================================

def parse_percentage_value(text: str) -> Optional[float]:
    """Extracts a numeric percentage value as float, e.g. '25%' -> 25.0."""
    m = PERCENT_EXPR_PATTERN.search(text)
    if m:
        try:
            return float(m.group(1))
        except ValueError:
            return None
    return None


def extract_all_percentages(text: str) -> List[Tuple[str, float]]:
    """
    Extracts all percentage expressions and their float values.
    Returns list of (raw_match, numeric_val).
    """
    results = []
    for m in PERCENT_EXPR_PATTERN.finditer(text):
        raw = m.group(0).strip()
        val = float(m.group(1))
        results.append((raw, val))
    return results


def strip_negation(text: str) -> Tuple[str, bool]:
    """
    Strips explicit negation prefixes/words from text.
    Returns: (text_without_negation, has_negation)
    """
    has_neg = False
    cleaned = text
    for np in NEGATION_PATTERNS:
        if np.search(cleaned):
            has_neg = True
            cleaned = np.sub("", cleaned)
    # Also strip standalone 'not' if remaining
    if re.search(r"\bnot\b", cleaned, re.IGNORECASE):
        has_neg = True
        cleaned = re.sub(r"\bnot\b", "", cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r"\s+", " ", cleaned).strip()
    return cleaned, has_neg


def strip_numbers_and_dates(text: str) -> str:
    """Strips numeric values, percentages, and dates to compare core semantic frames."""
    s = PERCENTAGE_PATTERN.sub(" ", text)
    s = CURRENCY_PATTERN.sub(" ", s)
    s = MEASUREMENT_PATTERN.sub(" ", s)
    s = DATE_PATTERN.sub(" ", s)
    s = MONTH_DATE_PATTERN.sub(" ", s)
    s = QUARTER_PATTERN.sub(" ", s)
    s = YEAR_PATTERN.sub(" ", s)
    s = NUMERIC_VALUE_PATTERN.sub(" ", s)
    return re.sub(r"\s+", " ", s).strip()


def extract_temporal_expressions(text: str) -> List[str]:
    """
    Extracts dates, month-years, standalone months, quarters, and years from text.
    """
    dates = []
    for d in MONTH_DATE_PATTERN.findall(text):
        d_clean = d.strip()
        if d_clean and d_clean not in dates:
            dates.append(d_clean)
    for q in QUARTER_PATTERN.findall(text):
        q_clean = q.strip()
        if q_clean and q_clean not in dates:
            dates.append(q_clean)
    for y in YEAR_PATTERN.findall(text):
        if y not in dates and not any(y in d for d in dates):
            dates.append(y)
    return dates


def extract_structured_numbers(text: str) -> List[Dict[str, Any]]:
    """
    Extracts numbers accompanied by local contextual anchors (currency, unit, or adjacent noun).
    Excludes standalone 4-digit years (handled by temporal analysis).
    """
    items = []
    # 1. Currency
    for c in CURRENCY_PATTERN.findall(text):
        norm = normalize_number(c)
        items.append({
            "raw": c.strip(),
            "norm": norm,
            "type": "currency"
        })

    # 2. Measurements with units (e.g. 120 employees, 45ms, 10 GB)
    # Custom pattern to also catch numbers followed by count nouns like employees, users, workers
    count_noun_pattern = re.compile(
        r"\b(\d+(?:,\d{3})*(?:\.\d+)?)\s+([a-zA-Z]{3,15})\b",
        re.IGNORECASE
    )
    for m in count_noun_pattern.finditer(text):
        num_str = m.group(1)
        noun = m.group(2).lower()
        if noun in {"in", "on", "at", "to", "by", "for", "with", "percent", "percentage"}:
            continue
        if len(num_str) == 4 and (num_str.startswith("19") or num_str.startswith("20")):
            continue
        items.append({
            "raw": m.group(0).strip(),
            "norm": normalize_number(num_str),
            "unit": noun,
            "type": "counted_noun"
        })

    # 3. Measurements
    for m in MEASUREMENT_PATTERN.findall(text):
        norm = normalize_number(m)
        if not any(it["raw"] == m.strip() for it in items):
            items.append({
                "raw": m.strip(),
                "norm": norm,
                "type": "measurement"
            })

    # 4. Standalone numbers (exclude numbers that belong to percentages or existing items)
    pct_raws = [raw for raw, _ in extract_all_percentages(text)]
    for n in NUMERIC_VALUE_PATTERN.findall(text):
        if len(n) == 4 and (n.startswith("19") or n.startswith("20")):
            continue
        if any(n in p_raw for p_raw in pct_raws):
            continue
        if not any(n in it["raw"] for it in items):
            items.append({
                "raw": n.strip(),
                "norm": normalize_number(n),
                "type": "standalone"
            })

    return items


# ============================================================
# CONTRADICTION CANDIDATE EVIDENCE RETRIEVAL
# ============================================================

def find_evidence_for_contradiction(
    claim_text: str,
    evidence_units: List[str]
) -> List[Tuple[str, float]]:
    """
    Ranks source evidence units by semantic frame and topic overlap with the claim.
    Focuses on predicate and subject overlap so that conflicting statements on the
    same topic are prioritized as candidate evidence.
    """
    if not claim_text or not evidence_units:
        return []

    # Semantic frame without numbers/dates
    claim_frame = strip_numbers_and_dates(claim_text)
    claim_words = set(tokenize_words(normalize_text_for_comparison(claim_frame)))

    ranked = []
    for unit in evidence_units:
        unit_frame = strip_numbers_and_dates(unit)
        unit_words = set(tokenize_words(normalize_text_for_comparison(unit_frame)))

        seq_sim = compute_sequence_similarity(claim_frame, unit_frame)
        jaccard, cont_claim, _ = compute_token_overlap(claim_frame, unit_frame)

        # Base alignment score
        score = (0.40 * seq_sim) + (0.35 * jaccard) + (0.25 * cont_claim)

        # Shared core action/noun bonus
        shared_words = claim_words.intersection(unit_words)
        if len(claim_words) > 0 and len(shared_words) >= 2:
            score += 0.20 * min(1.0, len(shared_words) / len(claim_words))

        ranked.append((unit, min(1.0, score)))

    ranked.sort(key=lambda x: x[1], reverse=True)
    return ranked[:5]


# ============================================================
# DETERMINISTIC CONFLICT DETECTORS
# ============================================================

def detect_percentage_conflict(
    claim_text: str,
    evidence_text: str
) -> Optional[Dict[str, Any]]:
    """
    Detects direct percentage mismatches between summary claim and source evidence on the same topic.
    Example:
      Source: 'Revenue increased by 25%.'
      Summary: 'Revenue increased by 35%.'
      -> percentage_conflict: 35% vs 25%
    """
    claim_pcts = extract_all_percentages(claim_text)
    if not claim_pcts:
        return None

    evidence_pcts = extract_all_percentages(evidence_text)
    if not evidence_pcts:
        return None

    # Contextual check: strip percentages and check if they talk about the same metric/action
    claim_stripped = re.sub(PERCENT_EXPR_PATTERN, " ", claim_text)
    ev_stripped = re.sub(PERCENT_EXPR_PATTERN, " ", evidence_text)
    seq_sim = compute_sequence_similarity(claim_stripped, ev_stripped)
    jaccard, cont_c, _ = compute_token_overlap(claim_stripped, ev_stripped)
    context_score = (0.5 * seq_sim) + (0.3 * jaccard) + (0.2 * cont_c)

    if context_score < 0.40:
        return None

    for c_raw, c_val in claim_pcts:
        # Check if identical percentage exists in evidence
        if any(abs(c_val - e_val) < 0.001 for _, e_val in evidence_pcts):
            continue

        # Differing percentage found in the same context
        for e_raw, e_val in evidence_pcts:
            if abs(c_val - e_val) >= 0.001:
                return {
                    "conflict_type": "percentage_conflict",
                    "confidence": 0.98,
                    "severity": "HIGH",
                    "summary_value": c_raw,
                    "source_value": e_raw,
                    "reason": (
                        f"Percentage conflict: summary states '{c_raw}', but source evidence states '{e_raw}' "
                        f"for the same metric."
                    )
                }

    return None


def detect_numerical_conflict(
    claim_text: str,
    evidence_text: str
) -> Optional[Dict[str, Any]]:
    """
    Detects numerical conflicts where numbers refer to the same metric, currency, or counted entity.
    Protects against flagging unrelated numbers.
    """
    claim_items = extract_structured_numbers(claim_text)
    if not claim_items:
        return None

    evidence_items = extract_structured_numbers(evidence_text)
    if not evidence_items:
        return None

    # Compare items by category and anchor
    for c_item in claim_items:
        c_norm = c_item["norm"]
        c_raw = c_item["raw"]
        c_type = c_item["type"]
        c_unit = c_item.get("unit")

        # If number matches exactly in evidence, no conflict for this item
        if any(e_item["norm"] == c_norm for e_item in evidence_items):
            continue

        # 1. Currency conflict check: both are currency expressions in a similar sentence
        if c_type == "currency":
            for e_item in evidence_items:
                if e_item["type"] == "currency" and e_item["norm"] != c_norm:
                    # Check context around currency
                    c_clean = CURRENCY_PATTERN.sub(" ", claim_text)
                    e_clean = CURRENCY_PATTERN.sub(" ", evidence_text)
                    if compute_token_overlap(c_clean, e_clean)[0] >= 0.35:
                        return {
                            "conflict_type": "numerical_conflict",
                            "confidence": 0.96,
                            "severity": "HIGH",
                            "summary_value": c_raw,
                            "source_value": e_item["raw"],
                            "reason": (
                                f"Numerical conflict: summary states '{c_raw}', but source evidence states "
                                f"'{e_item['raw']}' for the same metric."
                            )
                        }

        # 2. Counted noun conflict (e.g. '150 employees' vs '120 employees')
        if c_unit:
            for e_item in evidence_items:
                if e_item.get("unit") == c_unit and e_item["norm"] != c_norm:
                    return {
                        "conflict_type": "numerical_conflict",
                        "confidence": 0.96,
                        "severity": "HIGH",
                        "summary_value": c_raw,
                        "source_value": e_item["raw"],
                        "reason": (
                            f"Numerical conflict: summary states '{c_raw}', but source evidence states "
                            f"'{e_item['raw']}'."
                        )
                    }

        # 3. Standalone number with strong contextual alignment (>0.60 overlap)
        if c_type == "standalone":
            for e_item in evidence_items:
                if e_item["type"] == "standalone" and e_item["norm"] != c_norm:
                    c_no_num = NUMERIC_VALUE_PATTERN.sub(" ", claim_text)
                    e_no_num = NUMERIC_VALUE_PATTERN.sub(" ", evidence_text)
                    seq_sim = compute_sequence_similarity(c_no_num, e_no_num)
                    jaccard, _, _ = compute_token_overlap(c_no_num, e_no_num)
                    if seq_sim >= 0.60 and jaccard >= 0.50:
                        return {
                            "conflict_type": "numerical_conflict",
                            "confidence": 0.92,
                            "severity": "HIGH",
                            "summary_value": c_raw,
                            "source_value": e_item["raw"],
                            "reason": (
                                f"Numerical conflict: summary states '{c_raw}', but source evidence states "
                                f"'{e_item['raw']}' for the same context."
                            )
                        }

    return None


def detect_temporal_conflict(
    claim_text: str,
    evidence_text: str
) -> Optional[Dict[str, Any]]:
    """
    Detects date, month, year, or quarter conflicts for the same event or action.
    Example:
      Source: 'The product launched in March 2026.'
      Summary: 'The product launched in June 2026.'
      -> temporal_conflict: June 2026 vs March 2026
    """
    claim_dates = extract_temporal_expressions(claim_text)
    if not claim_dates:
        return None

    evidence_dates = extract_temporal_expressions(evidence_text)
    if not evidence_dates:
        return None

    # Check if temporal expressions match
    for c_date in claim_dates:
        c_norm = normalize_date(c_date)
        if any(normalize_date(e) == c_norm for e in evidence_dates):
            continue

        # Look for conflicting date in comparable event context
        for e_date in evidence_dates:
            e_norm = normalize_date(e_date)
            if c_norm != e_norm:
                # Strip dates to compare event/action frame
                c_clean = strip_numbers_and_dates(claim_text)
                e_clean = strip_numbers_and_dates(evidence_text)
                seq_sim = compute_sequence_similarity(c_clean, e_clean)
                jaccard, _, _ = compute_token_overlap(c_clean, e_clean)

                if (seq_sim >= 0.55 or jaccard >= 0.45):
                    return {
                        "conflict_type": "temporal_conflict",
                        "confidence": 0.95,
                        "severity": "HIGH",
                        "summary_value": c_date,
                        "source_value": e_date,
                        "reason": (
                            f"Temporal conflict: summary states '{c_date}', but source evidence states "
                            f"'{e_date}' for the same event."
                        )
                    }

    return None


def detect_entity_conflict(
    claim_text: str,
    evidence_text: str,
    source_text: str
) -> Optional[Dict[str, Any]]:
    """
    Detects entity substitution conflicts for exclusive transactions/roles (e.g. acquisitions, appointments).
    Avoids false positives for additive non-exclusive statements (e.g. opening offices in cities).
    Example:
      Source: 'The company acquired ABC Corp.'
      Summary: 'The company acquired XYZ Corp.'
      -> entity_conflict: XYZ Corp vs ABC Corp
    """
    claim_entities = extract_entities_from_text(claim_text)
    evidence_entities = extract_entities_from_text(evidence_text)

    if not claim_entities or not evidence_entities:
        return None

    # Check if this sentence contains an exclusive transaction or role verb
    claim_lower = claim_text.lower()
    evidence_lower = evidence_text.lower()

    matched_verb = None
    for verb in EXCLUSIVE_TRANSACTION_VERBS:
        if verb in claim_lower and verb in evidence_lower:
            matched_verb = verb
            break

    if not matched_verb:
        return None

    # Check for entity substitution on this exclusive transaction
    for c_ent in claim_entities:
        c_ent_clean = c_ent.strip()
        # If entity is a location, skip (e.g. cities are non-exclusive)
        if c_ent_clean.lower() in LOCATION_TERMS:
            continue

        # If summary entity exists in source text, it's not a hallucinated substitution
        if re.search(r"(?<!\w)" + re.escape(c_ent_clean) + r"(?!\w)", source_text, re.IGNORECASE):
            continue

        # Look for the corresponding source entity in evidence
        for e_ent in evidence_entities:
            e_ent_clean = e_ent.strip()
            if e_ent_clean.lower() in LOCATION_TERMS:
                continue

            if c_ent_clean.lower() != e_ent_clean.lower():
                # Check sentence structure similarity outside the entities
                c_clean = re.sub(re.escape(c_ent_clean), " ", claim_text, flags=re.IGNORECASE)
                e_clean = re.sub(re.escape(e_ent_clean), " ", evidence_text, flags=re.IGNORECASE)
                sim = compute_sequence_similarity(c_clean, e_clean)
                jaccard, _, _ = compute_token_overlap(c_clean, e_clean)

                if sim >= 0.55 or jaccard >= 0.50:
                    return {
                        "conflict_type": "entity_conflict",
                        "confidence": 0.95,
                        "severity": "HIGH",
                        "summary_value": c_ent_clean,
                        "source_value": e_ent_clean,
                        "reason": (
                            f"Entity conflict: summary states '{c_ent_clean}' was {matched_verb}, "
                            f"but source evidence states '{e_ent_clean}'."
                        )
                    }

    return None


def detect_factual_conflict(
    claim_text: str,
    evidence_text: str
) -> Optional[Dict[str, Any]]:
    """
    Detects direct factual conflicts via antonym inversion or polarity negation on the same subject.
    Examples:
      Source: 'The project was approved.'
      Summary: 'The project was rejected.'
      -> factual_conflict: rejected vs approved

      Source: 'The device supports Bluetooth.'
      Summary: 'The device does not support Bluetooth.'
      -> factual_conflict: does not support vs supports
    """
    claim_lower = claim_text.lower().strip()
    evidence_lower = evidence_text.lower().strip()

    # 1. Check direct Antonym pairs
    for word_a, word_b in ANTONYM_PAIRS:
        pattern_a = r"\b" + re.escape(word_a) + r"\b"
        pattern_b = r"\b" + re.escape(word_b) + r"\b"

        # Case 1: Evidence has word_a, Claim has word_b
        if re.search(pattern_a, evidence_lower) and re.search(pattern_b, claim_lower):
            # Check context outside of the antonyms
            c_clean = re.sub(pattern_b, " ", claim_lower)
            e_clean = re.sub(pattern_a, " ", evidence_lower)
            sim = compute_sequence_similarity(c_clean, e_clean)
            jaccard, _, _ = compute_token_overlap(c_clean, e_clean)
            if sim >= 0.50 or jaccard >= 0.40:
                return {
                    "conflict_type": "factual_conflict",
                    "confidence": 0.95,
                    "severity": "HIGH",
                    "summary_value": word_b,
                    "source_value": word_a,
                    "reason": (
                        f"Direct factual conflict: summary states '{word_b}', but source evidence states "
                        f"'{word_a}' for the same subject."
                    )
                }

        # Case 2: Evidence has word_b, Claim has word_a
        if re.search(pattern_b, evidence_lower) and re.search(pattern_a, claim_lower):
            c_clean = re.sub(pattern_a, " ", claim_lower)
            e_clean = re.sub(pattern_b, " ", evidence_lower)
            sim = compute_sequence_similarity(c_clean, e_clean)
            jaccard, _, _ = compute_token_overlap(c_clean, e_clean)
            if sim >= 0.50 or jaccard >= 0.40:
                return {
                    "conflict_type": "factual_conflict",
                    "confidence": 0.95,
                    "severity": "HIGH",
                    "summary_value": word_a,
                    "source_value": word_b,
                    "reason": (
                        f"Direct factual conflict: summary states '{word_a}', but source evidence states "
                        f"'{word_b}' for the same subject."
                    )
                }

    # 2. Check Negation / Polarity Inversion (Affirmative vs Negative on same predicate)
    c_stripped, c_has_neg = strip_negation(claim_lower)
    e_stripped, e_has_neg = strip_negation(evidence_lower)

    if c_has_neg != e_has_neg:
        # One is negated, one is affirmative
        sim = compute_sequence_similarity(c_stripped, e_stripped)
        jaccard, cont_c, cont_e = compute_token_overlap(c_stripped, e_stripped)

        # High alignment on non-negated predicate & entities
        if sim >= 0.65 and (jaccard >= 0.50 or cont_c >= 0.65):
            sum_val = "negated statement" if c_has_neg else "affirmative statement"
            src_val = "negated statement" if e_has_neg else "affirmative statement"
            return {
                "conflict_type": "factual_conflict",
                "confidence": 0.94,
                "severity": "HIGH",
                "summary_value": sum_val,
                "source_value": src_val,
                "reason": (
                    f"Direct factual conflict: summary {'negates' if c_has_neg else 'affirms'} "
                    f"a statement that source evidence {'affirms' if c_has_neg else 'negates'}."
                )
            }

    return None


# ============================================================
# SINGLE CLAIM VERIFICATION DISPATCHER
# ============================================================

def evaluate_claim_contradiction(
    claim: Dict[str, Any],
    candidate_evidence: List[Tuple[str, float]],
    source_text: str
) -> Optional[Dict[str, Any]]:
    """
    Evaluates a single summary claim against ranked candidate source evidence.
    Applies detectors in strict order of specificity:
      1. percentage_conflict
      2. temporal_conflict
      3. numerical_conflict
      4. factual_conflict
      5. entity_conflict
    Returns contradiction dictionary if a conflict is detected, otherwise None.
    """
    if not candidate_evidence:
        return None

    claim_text = claim["claim"]

    for ev_text, sim_score in candidate_evidence:
        # Ignore completely unrelated candidate sentences
        if sim_score < 0.20:
            continue

        # 1. Percentage conflict
        pct_conflict = detect_percentage_conflict(claim_text, ev_text)
        if pct_conflict:
            return {
                "claim": claim_text,
                "source_evidence": ev_text,
                **pct_conflict
            }

        # 2. Temporal conflict
        temporal_conflict = detect_temporal_conflict(claim_text, ev_text)
        if temporal_conflict:
            return {
                "claim": claim_text,
                "source_evidence": ev_text,
                **temporal_conflict
            }

        # 3. Numerical conflict
        num_conflict = detect_numerical_conflict(claim_text, ev_text)
        if num_conflict:
            return {
                "claim": claim_text,
                "source_evidence": ev_text,
                **num_conflict
            }

        # 4. Direct factual conflict (Antonyms & Polarity)
        fact_conflict = detect_factual_conflict(claim_text, ev_text)
        if fact_conflict:
            return {
                "claim": claim_text,
                "source_evidence": ev_text,
                **fact_conflict
            }

        # 5. Entity conflict
        entity_conflict = detect_entity_conflict(claim_text, ev_text, source_text)
        if entity_conflict:
            return {
                "claim": claim_text,
                "source_evidence": ev_text,
                **entity_conflict
            }

    return None


# ============================================================
# MAIN ORCHESTRATION PIPELINE
# ============================================================

def check_contradictions(
    source_text: str,
    summary_text: str,
    use_llm: bool = False
) -> Dict[str, Any]:
    """
    Main entry point for Contradiction and Conflict Detection.
    Evaluates whether any claims in the summary contradict or conflict with source material.

    Pipeline:
    1. Guard against empty source or empty summary.
    2. Extract substantive claims with quantitative and entity metadata.
    3. Segment source document into evidence candidate units.
    4. Rank candidate evidence by semantic frame and topic alignment.
    5. Evaluate each claim across deterministic conflict layers:
       - numerical_conflict
       - percentage_conflict
       - temporal_conflict
       - entity_conflict
       - factual_conflict
    6. Construct standardized ContradictionResult payload.
    """
    if not source_text or not source_text.strip() or not summary_text or not summary_text.strip():
        return {
            "has_contradiction": False,
            "status": "CLEAN",
            "total_conflicts": 0,
            "conflicts_by_type": {},
            "claims_checked": 0,
            "conflicts": []
        }

    extracted_claims = extract_claims(summary_text)
    if not extracted_claims:
        return {
            "has_contradiction": False,
            "status": "CLEAN",
            "total_conflicts": 0,
            "conflicts_by_type": {},
            "claims_checked": 0,
            "conflicts": []
        }

    evidence_units = segment_source_into_evidence_units(source_text)
    if not evidence_units:
        return {
            "has_contradiction": False,
            "status": "CLEAN",
            "total_conflicts": 0,
            "conflicts_by_type": {},
            "claims_checked": len(extracted_claims),
            "conflicts": []
        }

    conflicts: List[Dict[str, Any]] = []
    conflicts_by_type: Dict[str, int] = {}

    ambiguous_claims = []

    for claim in extracted_claims:
        candidate_evidence = find_evidence_for_contradiction(claim["claim"], evidence_units)
        conflict = evaluate_claim_contradiction(claim, candidate_evidence, source_text)
        if conflict:
            conflicts.append(conflict)
            ctype = conflict["conflict_type"]
            conflicts_by_type[ctype] = conflicts_by_type.get(ctype, 0) + 1
        elif candidate_evidence:
            best_ev, best_score = candidate_evidence[0]
            # Consider it an ambiguous claim if there's high semantic overlap but no deterministic conflict
            if best_score >= 0.50:
                ambiguous_claims.append({
                    "claim": claim["claim"],
                    "candidate_evidence": best_ev,
                    "score": best_score
                })

    if use_llm and ambiguous_claims:
        # Sort and take top 5 to keep LLM calls strictly bounded
        ambiguous_claims.sort(key=lambda x: x["score"], reverse=True)
        ambiguous_claims = ambiguous_claims[:5]
        
        try:
            from app.services.groq_service import check_ambiguous_contradictions_llm
            llm_conflicts = check_ambiguous_contradictions_llm(ambiguous_claims, source_text)
            for c in llm_conflicts:
                conflicts.append(c)
                ctype = c["conflict_type"]
                conflicts_by_type[ctype] = conflicts_by_type.get(ctype, 0) + 1
        except Exception as e:
            logger.error(f"LLM contradiction check failed: {e}. Falling back to deterministic results.")

    has_contradiction = len(conflicts) > 0
    status = "CONFLICT_DETECTED" if has_contradiction else "CLEAN"

    logger.info(
        f"Contradiction check complete: status={status}, conflicts={len(conflicts)}, "
        f"claims_checked={len(extracted_claims)}"
    )

    return {
        "has_contradiction": has_contradiction,
        "status": status,
        "total_conflicts": len(conflicts),
        "conflicts_by_type": conflicts_by_type,
        "claims_checked": len(extracted_claims),
        "conflicts": conflicts
    }

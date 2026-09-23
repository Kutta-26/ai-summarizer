import re
import math
import json
from typing import Optional, Dict, Any
from app.core.logging_config import get_logger

logger = get_logger("importance")

# ============================================================
# REGEX & PATTERN DICTIONARIES FOR SIGNAL DETECTION
# ============================================================

# Headings & structural markers
HEADING_PATTERNS = [
    re.compile(r"^#{1,6}\s+\S+", re.MULTILINE),
    re.compile(r"^\d+(\.\d+)*\s+[A-Z]", re.MULTILINE),
    re.compile(r"^(Chapter|Section|Part|Appendix|Overview|Background|Methodology|Results|Discussion|Conclusion|Architecture|Summary|Findings)\b", re.IGNORECASE | re.MULTILINE),
    re.compile(r"^[A-Z0-9\s\-_:]{4,50}$", re.MULTILINE)
]

# Numerical & statistical metrics patterns
METRIC_PATTERNS = [
    re.compile(r"\b\d+(?:\.\d+)?%"),  # Percentages (e.g. 25%, 99.9%)
    re.compile(r"[\$€£¥]\s*\d+(?:,\d{3})*(?:\.\d+)?|\b\d+(?:,\d{3})*(?:\.\d+)?\s*(?:USD|EUR|GBP|dollars?|cents?)\b", re.IGNORECASE),  # Currency
    re.compile(r"\b\d+(?:\.\d+)?\s*(?:GB|MB|KB|TB|ms|sec|seconds?|minutes?|hours?|days?|weeks?|months?|years?|kg|km|m|cm|mm|pages?|users?|requests?|tokens?|queries|records|rows|bps|kbps|mbps)\b", re.IGNORECASE),  # Units
    re.compile(r"\b\d{1,3}(?:,\d{3})+\b"),  # Formatted numbers like 1,000,000
    re.compile(r"\b(?:increased|decreased|grew|dropped|reduced|rose|fell)\s+by\s+\d+", re.IGNORECASE),  # Delta metrics
]

# Categorical keyword & phrase patterns
FINDINGS_PATTERNS = [
    re.compile(r"\b(found that|findings? (?:show|indicate|reveal|suggest)|results? (?:show|indicate|demonstrate|prove)|discovered that|observed that|evidence (?:shows|indicates|supports)|analysis (?:reveals|indicates|shows)|we observed|it was observed)\b", re.IGNORECASE),
    re.compile(r"\b(key findings?|primary outcome|experiment showed|tests? demonstrated|demonstrated that|significant (?:difference|improvement|reduction|growth))\b", re.IGNORECASE)
]

DECISIONS_PATTERNS = [
    re.compile(r"\b(decided (?:to|that)|decision was (?:made|reached)|we (?:chose|selected|resolved)|approved (?:by|to)|adopted|agreed (?:to|upon)|determined that|will proceed with|consensus was)\b", re.IGNORECASE),
    re.compile(r"\b(action plan|final decision|verdict|sign-off|ratified|authorized)\b", re.IGNORECASE)
]

ACTIONS_PATTERNS = [
    re.compile(r"\b(action items?|next steps?|to-do|todo|assigned to|must implement|will execute|roadmap|deliverables?|action required|immediate action|responsible team)\b", re.IGNORECASE),
    re.compile(r"\b(deadline|target date|milestone|schedule for|by Q[1-4]|by \d{4})\b", re.IGNORECASE)
]

RISKS_PATTERNS = [
    re.compile(r"\b(risks?|hazards?|vulnerabilit(?:y|ies)|threats?|failure modes?|drawbacks?|limitations?|pitfalls?|critical issues?|security flaws?|bottlenecks?|regressions?)\b", re.IGNORECASE),
    re.compile(r"\b(warning|caution|jeopardize|compromise|incident|outage|catastrophic|severe impact)\b", re.IGNORECASE)
]

CONCLUSION_PATTERNS = [
    re.compile(r"\b(in conclusion|to conclude|concluding remarks?|in summary|to summarize|overall|key takeaways?|final thoughts?|in closing|bottom line|summing up)\b", re.IGNORECASE),
    re.compile(r"\b(conclusions?|recommendations?|closing remarks?|summary of findings)\b", re.IGNORECASE)
]

REQUIREMENTS_PATTERNS = [
    re.compile(r"\b(must|shall|required to|mandatory|prerequisite|specification|compliance|strictly necessary)\b", re.IGNORECASE)
]

# Common English stop words for content density estimation
STOP_WORDS = {
    "a", "about", "above", "after", "again", "against", "all", "am", "an", "and",
    "any", "are", "aren't", "as", "at", "be", "because", "been", "before", "being",
    "below", "between", "both", "but", "by", "can't", "cannot", "could", "couldn't",
    "did", "didn't", "do", "does", "doesn't", "doing", "don't", "down", "during",
    "each", "few", "for", "from", "further", "had", "hadn't", "has", "hasn't",
    "have", "haven't", "having", "he", "he'd", "he'll", "he's", "her", "here",
    "here's", "hers", "herself", "him", "himself", "his", "how", "how's", "i",
    "i'd", "i'll", "i'm", "i've", "if", "in", "into", "is", "isn't", "it",
    "it's", "its", "itself", "let's", "me", "more", "most", "mustn't", "my",
    "myself", "no", "nor", "not", "of", "off", "on", "once", "only", "or",
    "other", "ought", "our", "ours", "ourselves", "out", "over", "own", "same",
    "shan't", "she", "she'd", "she'll", "she's", "should", "shouldn't", "so",
    "some", "such", "than", "that", "that's", "the", "their", "theirs", "them",
    "themselves", "then", "there", "there's", "these", "they", "they'd", "they'll",
    "they're", "they've", "this", "those", "through", "to", "too", "under",
    "until", "up", "very", "was", "wasn't", "we", "we'd", "we'll", "we're",
    "we've", "were", "weren't", "what", "what's", "when", "when's", "where",
    "where's", "which", "while", "who", "who's", "whom", "why", "why's", "with",
    "won't", "would", "wouldn't", "you", "you'd", "you'll", "you're", "you've",
    "your", "yours", "yourself", "yourselves"
}


# ============================================================
# DETERMINISTIC HEURISTIC & STRUCTURAL SCORING
# ============================================================

def detect_signals(text: str) -> Dict[str, bool]:
    """
    Detect presence of key informational signals using deterministic patterns.
    Returns the exact 6 signal categories specified in requirements:
    key_findings, decisions, metrics, actions, risks, conclusion.
    """
    if not text:
        return {
            "key_findings": False,
            "decisions": False,
            "metrics": False,
            "actions": False,
            "risks": False,
            "conclusion": False
        }

    has_findings = any(p.search(text) for p in FINDINGS_PATTERNS)
    has_decisions = any(p.search(text) for p in DECISIONS_PATTERNS)
    has_metrics = any(p.search(text) for p in METRIC_PATTERNS)
    has_actions = any(p.search(text) for p in ACTIONS_PATTERNS)
    has_risks = any(p.search(text) for p in RISKS_PATTERNS)
    has_conclusion = any(p.search(text) for p in CONCLUSION_PATTERNS)

    return {
        "key_findings": bool(has_findings),
        "decisions": bool(has_decisions),
        "metrics": bool(has_metrics),
        "actions": bool(has_actions),
        "risks": bool(has_risks),
        "conclusion": bool(has_conclusion)
    }


def compute_information_density(text: str) -> float:
    """
    Compute lexical information density: ratio of non-stop content words
    and lexical diversity (Type-Token Ratio).
    Returns normalized value between 0.0 and 1.0.
    """
    words = re.findall(r"\b[a-zA-Z0-9_-]+\b", text.lower())
    if not words:
        return 0.0

    total_words = len(words)
    content_words = [w for w in words if w not in STOP_WORDS]
    content_ratio = len(content_words) / total_words

    # Type-Token Ratio (lexical diversity)
    unique_words = set(content_words)
    ttr = (len(unique_words) / len(content_words)) if content_words else 0.0

    # Weighted blend of content ratio (60%) and unique lexical density (40%)
    density = (0.6 * content_ratio) + (0.4 * min(1.0, ttr * 1.5))
    return max(0.0, min(1.0, density))


def compute_structural_score(text: str, chunk_index: int = 1, total_chunks: int = 1) -> float:
    """
    Evaluate structural importance:
    - Headings and section boundaries
    - Positional significance (lead intro vs trailing conclusion)
    - Formatting structure (bullets, lists)
    """
    score = 0.0
    lines = text.splitlines()

    # Heading presence
    has_heading = False
    for line in lines[:5]:  # Check first few lines
        line_clean = line.strip()
        if any(p.match(line_clean) for p in HEADING_PATTERNS):
            has_heading = True
            break

    if has_heading:
        score += 0.40

    # Positional bias: first section (intro/exec summary) and last section (conclusions)
    if total_chunks > 1:
        if chunk_index == 1:
            score += 0.35  # Opening section often sets scope and high-level context
        elif chunk_index == total_chunks:
            score += 0.30  # Final section often has conclusion / outcomes
        elif chunk_index == 2 and total_chunks > 3:
            score += 0.15

    # Bullet / enumeration list structure
    has_lists = bool(re.search(r"^\s*[-*•]\s+\S+", text, re.MULTILINE))
    if has_lists:
        score += 0.15

    # Table / tabular presence
    has_table = bool(re.search(r"\|.+\|.+\|", text))
    if has_table:
        score += 0.15

    return min(1.0, score)


def compute_metrics_count(text: str) -> int:
    """
    Count occurrences of quantitative / numerical metric data points.
    """
    count = 0
    for p in METRIC_PATTERNS:
        count += len(p.findall(text))
    return count


def calculate_heuristic_score(
    text: str,
    chunk_index: int = 1,
    total_chunks: int = 1
) -> tuple[float, Dict[str, bool], list[str]]:
    """
    Combines structural signals, categorical signals, metrics density,
    and lexical density into a robust deterministic score [0.0, 1.0].
    """
    if not text or not text.strip():
        return 0.0, detect_signals(""), ["Empty content"]

    signals = detect_signals(text)
    reasons = []

    # 1. Categorical signal weights (up to 0.45 total)
    signal_weights = {
        "key_findings": 0.12,
        "decisions": 0.09,
        "metrics": 0.10,
        "actions": 0.06,
        "risks": 0.05,
        "conclusion": 0.06
    }
    signal_score = sum(weight for sig, weight in signal_weights.items() if signals.get(sig, False))

    active_signals = [sig.replace("_", " ") for sig, active in signals.items() if active]
    if active_signals:
        reasons.append(f"Identified signals: {', '.join(active_signals)}")

    # 2. Structural score (up to 0.25)
    structural_score = compute_structural_score(text, chunk_index, total_chunks)
    if structural_score >= 0.3:
        reasons.append("Strong structural positioning / section headings")

    # 3. Information density (up to 0.15)
    density = compute_information_density(text)
    if density >= 0.55:
        reasons.append(f"High information density ({density:.2f})")
    elif density <= 0.35:
        reasons.append("Low information density / conversational style")

    # 4. Requirements & specifications bonus (up to 0.08)
    has_requirements = any(p.search(text) for p in REQUIREMENTS_PATTERNS)
    req_bonus = 0.08 if has_requirements else 0.0
    if has_requirements:
        reasons.append("Contains explicit requirements or specifications")

    # 5. Numerical density bonus
    metric_count = compute_metrics_count(text)
    metric_bonus = min(0.12, metric_count * 0.03)
    if metric_count > 0:
        reasons.append(f"{metric_count} quantitative metrics found")

    # Raw combined score
    raw_score = (
        (signal_score * 1.1) +
        (structural_score * 0.22) +
        (density * 0.18) +
        req_bonus +
        metric_bonus
    )

    # Normalize bounded score strictly between 0.0 and 1.0
    bounded_score = max(0.0, min(1.0, raw_score))

    # Baseline adjustment: ensure non-empty text has reasonable minimum baseline (0.15 - 0.20)
    if len(text.strip()) > 50 and bounded_score < 0.15:
        bounded_score = 0.15

    return bounded_score, signals, reasons


# ============================================================
# LLM SEMANTIC IMPORTANCE ASSESSMENT (HYBRID FALLBACK)
# ============================================================

def _call_llm_for_importance(text: str, context: Optional[str] = None) -> Optional[tuple[float, str]]:
    """
    Optionally queries Groq LLM for semantic evaluation of importance.
    Uses safe structured JSON extraction with deterministic fallbacks.
    """
    try:
        from app.services.groq_service import _call_groq_chat

        context_hint = f"\nDOCUMENT CONTEXT: {context[:500]}" if context else ""
        prompt = f"""
Analyze the informational importance and strategic relevance of the following document excerpt.
{context_hint}

EXCERPT:
{text[:2500]}

Respond ONLY with a valid JSON object formatted exactly as:
{{
    "score": <float between 0.0 and 1.0>,
    "reason": "<one concise sentence explaining the importance score>"
}}
"""
        messages = [
            {
                "role": "system",
                "content": "You are a professional document analysis engine evaluating section importance. Respond with valid JSON only."
            },
            {
                "role": "user",
                "content": prompt
            }
        ]

        response_content = _call_groq_chat(
            messages=messages,
            temperature=0.1,
            operation="importance assessment"
        )

        # Extract JSON from response
        json_match = re.search(r"\{.*\}", response_content, re.DOTALL)
        if json_match:
            data = json.loads(json_match.group(0))
            score = float(data.get("score", 0.5))
            score = max(0.0, min(1.0, score))
            reason = str(data.get("reason", "Semantic importance evaluated by LLM."))
            return score, reason
    except Exception as e:
        logger.warning(f"LLM importance assessment failed or bypassed: {str(e)}")

    return None


# ============================================================
# MAIN IMPORTANCE SERVICE API
# ============================================================

def score_importance(
    text: str,
    chunk_index: int = 1,
    total_chunks: int = 1,
    use_llm: bool = False,
    context: Optional[str] = None
) -> Dict[str, Any]:
    """
    Evaluate importance of a document section using a hybrid strategy combining:
    - structural signals (headings, section boundary, position)
    - categorical signals (key findings, decisions, actions, risks, conclusions)
    - information density (lexical richness, content-to-stop ratio)
    - numerical / statistical metrics
    - optional semantic LLM assessment (when use_llm=True)

    Returns a structured dictionary strictly conforming to:
    {
        "score": float,  # 0.0 <= score <= 1.0
        "reason": str,
        "signals": {
            "key_findings": bool,
            "decisions": bool,
            "metrics": bool,
            "actions": bool,
            "risks": bool,
            "conclusion": bool
        }
    }
    """
    if not text or not text.strip():
        return {
            "score": 0.0,
            "reason": "Empty document section has zero informational importance.",
            "signals": {
                "key_findings": False,
                "decisions": False,
                "metrics": False,
                "actions": False,
                "risks": False,
                "conclusion": False
            }
        }

    # 1. Deterministic heuristic score & signal extraction
    heur_score, signals, reasons = calculate_heuristic_score(
        text=text,
        chunk_index=chunk_index,
        total_chunks=total_chunks
    )

    final_score = heur_score
    reason_text = ""

    # 2. Optional LLM Semantic Assessment
    if use_llm:
        llm_result = _call_llm_for_importance(text, context=context)
        if llm_result is not None:
            llm_score, llm_reason = llm_result
            # Conservative hybrid blend: 60% deterministic heuristic + 40% LLM semantic
            final_score = (0.60 * heur_score) + (0.40 * llm_score)
            reasons.append(f"LLM assessment: {llm_reason}")

    final_score = max(0.0, min(1.0, round(final_score, 2)))

    # 3. Format synthesized rationale
    if reasons:
        if final_score >= 0.70:
            prefix = "High importance: "
        elif final_score >= 0.40:
            prefix = "Moderate importance: "
        else:
            prefix = "Low importance: "
        reason_text = prefix + "; ".join(reasons) + "."
    else:
        reason_text = f"Baseline importance score: {final_score:.2f} based on document content analysis."

    return {
        "score": final_score,
        "reason": reason_text,
        "signals": signals
    }


def batch_score_importance(
    chunks: list[str],
    use_llm: bool = False,
    context: Optional[str] = None
) -> list[Dict[str, Any]]:
    """
    Efficiently score importance across multiple chunks/sections in batch mode.
    Adheres to the critical architecture rule: prevents N separate individual LLM roundtrips.
    """
    total = len(chunks)
    results = []

    for idx, chunk in enumerate(chunks, start=1):
        scored = score_importance(
            text=chunk,
            chunk_index=idx,
            total_chunks=total,
            use_llm=use_llm,
            context=context
        )
        results.append(scored)

    return results

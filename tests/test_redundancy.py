import sys
from pathlib import Path

backend_dir = Path(__file__).resolve().parent.parent / "backend"
sys.path.insert(0, str(backend_dir))

from app.services.redundancy_service import (
    normalize_text_for_comparison,
    compute_sequence_similarity,
    compute_deterministic_similarity,
    evaluate_section_quality,
    check_pairwise_redundancy,
    detect_and_filter_redundancy,
    filter_synthesis_sections
)
from app.services.groq_service import hierarchical_summarize


def test_empty_input():
    # 1. Empty input handling
    processed, records = detect_and_filter_redundancy([])
    assert processed == []
    assert records == []

    # Single section input
    single = [{"section_index": 1, "summary": "Single section content."}]
    processed_single, records_single = detect_and_filter_redundancy(single)
    assert len(processed_single) == 1
    assert processed_single[0]["is_redundant"] is False
    assert records_single == []


def test_exact_duplicate_detection_and_removal():
    # 2. Exact duplicate detection & 3. Exact duplicate removal
    sec1 = {
        "section_index": 1,
        "summary": "The company's quarterly revenue reached $10 million with 20% growth.",
        "importance_score": 0.85
    }
    sec2 = {
        "section_index": 2,
        "summary": "  the company's quarterly revenue reached $10 million with 20% growth.  ",
        "importance_score": 0.85
    }

    res = check_pairwise_redundancy(sec1, sec2)
    assert res is not None
    assert res["is_redundant"] is True
    assert res["redundancy_type"] == "exact_duplicate"
    assert res["similarity"] == 1.0
    assert res["kept_section"] == 1
    assert res["removed_section"] == 2

    # Verify pipeline marking and filtering
    processed, records = detect_and_filter_redundancy([sec1, sec2])
    assert len(records) == 1
    assert processed[0]["is_redundant"] is False
    assert processed[1]["is_redundant"] is True
    assert processed[1]["redundancy_info"]["kept_section"] == 1

    synthesis_ready = filter_synthesis_sections(processed)
    assert len(synthesis_ready) == 1
    assert synthesis_ready[0]["section_index"] == 1


def test_near_duplicate_detection():
    # 4. Near-duplicate detection
    sec1 = {
        "section_index": 1,
        "summary": "The operating system kernel scheduled the thread across multiple CPU cores efficiently.",
        "importance_score": 0.70
    }
    sec2 = {
        "section_index": 2,
        "summary": "The operating system kernel scheduled the thread across multiple CPU cores very efficiently.",
        "importance_score": 0.65
    }

    res = check_pairwise_redundancy(sec1, sec2, threshold=0.80)
    assert res is not None
    assert res["is_redundant"] is True
    assert res["redundancy_type"] == "near_duplicate"
    assert 0.80 <= res["similarity"] <= 1.0


def test_clearly_different_content_not_marked():
    # 5. Clearly different content is not marked redundant
    sec1 = {
        "section_index": 1,
        "summary": "Machine learning transformers use multi-head self-attention mechanisms for representation.",
        "importance_score": 0.80
    }
    sec2 = {
        "section_index": 2,
        "summary": "FastAPI leverages Python type hints and Starlette for asynchronous ASGI routing.",
        "importance_score": 0.75
    }

    res = check_pairwise_redundancy(sec1, sec2, threshold=0.80)
    assert res is None

    processed, records = detect_and_filter_redundancy([sec1, sec2])
    assert len(records) == 0
    assert all(not s["is_redundant"] for s in processed)
    assert len(filter_synthesis_sections(processed)) == 2


def test_importance_aware_selection():
    # 6. Importance-aware selection: Section B with metrics and higher score beats Section A
    sec_a = {
        "section_index": 1,
        "summary": "Revenue increased.",
        "importance_score": 0.30,
        "importance_signals": {"key_findings": False, "decisions": False, "metrics": False, "actions": False, "risks": False, "conclusion": False}
    }
    sec_b = {
        "section_index": 2,
        "summary": "Revenue increased 25% year-over-year to $4.2 million.",
        "importance_score": 0.88,
        "importance_signals": {"key_findings": True, "decisions": False, "metrics": True, "actions": False, "risks": False, "conclusion": False}
    }

    # Sec B has much higher quality and metrics despite being Section 2
    qual_a = evaluate_section_quality(sec_a)
    qual_b = evaluate_section_quality(sec_b)
    assert qual_b > qual_a, f"Expected Section B quality > Section A, got {qual_b} vs {qual_a}"

    res = check_pairwise_redundancy(sec_a, sec_b, threshold=0.80)
    assert res is not None
    assert res["is_redundant"] is True
    # The higher-information version (Sec B, index 2) MUST be kept, Sec A removed
    assert res["kept_section"] == 2
    assert res["removed_section"] == 1


def test_multiple_redundant_sections():
    # 7. Multiple redundant sections (3 copies of same topic)
    sec1 = {"section_index": 1, "summary": "System latency dropped by 30% after memory optimization.", "importance_score": 0.75}
    sec2 = {"section_index": 2, "summary": "System latency dropped by 30% after memory optimization.", "importance_score": 0.75}
    sec3 = {"section_index": 3, "summary": "System latency dropped by 30% after memory optimization.", "importance_score": 0.75}
    sec4 = {"section_index": 4, "summary": "Database indexes were migrated to PostgreSQL B-trees.", "importance_score": 0.70}

    processed, records = detect_and_filter_redundancy([sec1, sec2, sec3, sec4])
    assert len(records) == 2  # sec2 and sec3 redundant with sec1
    assert processed[0]["is_redundant"] is False
    assert processed[1]["is_redundant"] is True
    assert processed[2]["is_redundant"] is True
    assert processed[3]["is_redundant"] is False

    synthesis_ready = filter_synthesis_sections(processed)
    assert len(synthesis_ready) == 2
    assert [s["section_index"] for s in synthesis_ready] == [1, 4]


def test_no_accidental_removal_of_unique_info():
    # 8. No accidental removal of unique information
    # Both mention quarterly results, but for DIFFERENT quarters and DIFFERENT metrics
    sec_q1 = {
        "section_index": 1,
        "summary": "In Q1 2024, gross margin was 42% and North American sales expanded.",
        "importance_score": 0.75
    }
    sec_q2 = {
        "section_index": 2,
        "summary": "In Q2 2024, gross margin was 48% and European operations launched.",
        "importance_score": 0.75
    }

    processed, records = detect_and_filter_redundancy([sec_q1, sec_q2], threshold=0.80)
    assert len(records) == 0, f"Expected distinct quarters not to be flagged, got {records}"
    assert len(filter_synthesis_sections(processed)) == 2


def test_similarity_score_bounded():
    # 9. Similarity score remains bounded [0.0, 1.0]
    pairs = [
        ("", ""),
        ("Exact match string", "Exact match string"),
        ("Completely divergent topic", "Another unrelated concept entirely"),
        ("Slight variation on sentence.", "Slight variation on sentence!"),
        ("Short", "Very long paragraph containing lots of detailed information and facts.")
    ]
    for a, b in pairs:
        sim = compute_deterministic_similarity(a, b)
        assert 0.0 <= sim <= 1.0, f"Similarity {sim} out of bounds for '{a}' vs '{b}'"


def test_safety_fallback_filter():
    # 10. Safety guarantee: If all sections marked redundant, preserves at least one
    all_redundant = [
        {"section_index": 1, "summary": "Duplicate content A", "is_redundant": True, "importance_score": 0.4},
        {"section_index": 2, "summary": "Duplicate content B", "is_redundant": True, "importance_score": 0.9}
    ]
    filtered = filter_synthesis_sections(all_redundant)
    assert len(filtered) == 1
    assert filtered[0]["section_index"] == 2  # Best quality preserved


if __name__ == "__main__":
    print("Running Redundancy Detection Unit Tests...")
    test_empty_input()
    print("[PASS] test_empty_input")
    test_exact_duplicate_detection_and_removal()
    print("[PASS] test_exact_duplicate_detection_and_removal")
    test_near_duplicate_detection()
    print("[PASS] test_near_duplicate_detection")
    test_clearly_different_content_not_marked()
    print("[PASS] test_clearly_different_content_not_marked")
    test_importance_aware_selection()
    print("[PASS] test_importance_aware_selection")
    test_multiple_redundant_sections()
    print("[PASS] test_multiple_redundant_sections")
    test_no_accidental_removal_of_unique_info()
    print("[PASS] test_no_accidental_removal_of_unique_info")
    test_similarity_score_bounded()
    print("[PASS] test_similarity_score_bounded")
    test_safety_fallback_filter()
    print("[PASS] test_safety_fallback_filter")
    print("ALL 9 REDUNDANCY UNIT TESTS PASSED!")

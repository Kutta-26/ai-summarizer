import sys
from pathlib import Path
from unittest.mock import patch

backend_dir = Path(__file__).resolve().parent.parent / "backend"
sys.path.insert(0, str(backend_dir))

from app.services.faithfulness_service import (
    extract_claims,
    extract_numbers_from_text,
    extract_dates_from_text,
    extract_entities_from_text,
    find_candidate_evidence,
    validate_numerics,
    validate_dates,
    validate_entities,
    verify_single_claim,
    calculate_faithfulness_score,
    check_faithfulness,
    verify_claims_with_llm_batch
)
from app.schemas.summarize import HierarchicalSummaryResponse, FaithfulnessResult, FaithfulnessClaim
from app.services.groq_service import hierarchical_summarize


# 1. Empty source
def test_empty_source():
    res = check_faithfulness(source_text="", summary_text="Revenue reached $10 million in 2025.")
    assert res["faithfulness_score"] == 0.0
    assert res["status"] == "LOW"
    assert res["claims_checked"] == 0
    assert res["claims"] == []


# 2. Empty summary
def test_empty_summary():
    source = "The company reported gross revenue of $10 million in Q4 2025."
    res = check_faithfulness(source_text=source, summary_text="")
    assert res["faithfulness_score"] == 1.0
    assert res["status"] == "HIGH"
    assert res["claims_checked"] == 0
    assert res["claims"] == []


# 3. Fully faithful summary
def test_fully_faithful_summary():
    source = (
        "In Q3 2025, CloudCorp reported that operating revenue grew by 25% year-over-year "
        "to $4.2 million. The engineering team deployed the Kubernetes cluster across 3 availability zones."
    )
    summary = (
        "Operating revenue grew by 25% to $4.2 million in Q3 2025. "
        "CloudCorp deployed the Kubernetes cluster across 3 availability zones."
    )
    res = check_faithfulness(source_text=source, summary_text=summary)
    assert res["faithfulness_score"] >= 0.80
    assert res["status"] == "HIGH"
    assert res["supported_claims"] >= 2
    assert res["unsupported_claims"] == 0
    for claim in res["claims"]:
        assert claim["status"] == "SUPPORTED"
        assert claim["evidence"] is not None


# 4. Partially faithful summary
def test_partially_faithful_summary():
    source = "Revenue increased by 25% to $4.2 million in 2025. The company launched 4 new services."
    summary = (
        "Revenue increased by 25% to $4.2 million in 2025. "
        "The company expanded its global presence to 95 countries."  # Unsupported claim
    )
    res = check_faithfulness(source_text=source, summary_text=summary)
    assert 0.0 < res["faithfulness_score"] < 1.0
    assert res["claims_checked"] == 2
    assert res["supported_claims"] == 1
    assert res["unsupported_claims"] == 1


# 5. Unsupported claim
def test_unsupported_claim():
    source = "Quantum computing relies on superposition and entanglement to perform complex operations."
    summary = "The company experienced an unprecedented 80% loss due to supply chain failure."
    res = check_faithfulness(source_text=source, summary_text=summary)
    assert res["unsupported_claims"] >= 1
    assert res["supported_claims"] == 0
    assert res["faithfulness_score"] <= 0.40
    assert res["status"] == "LOW"


# 6. Incorrect number
def test_incorrect_number():
    source = "The quarterly gross revenue was $4.2 million."
    summary = "The quarterly gross revenue reached $5.2 million."
    res = check_faithfulness(source_text=source, summary_text=summary)
    assert res["unsupported_claims"] == 1
    assert res["supported_claims"] == 0
    claim_record = res["claims"][0]
    assert claim_record["status"] == "UNSUPPORTED"
    assert "numerical claim" in claim_record["reason"].lower() or "5.2" in claim_record["reason"]


# 7. Incorrect percentage
def test_incorrect_percentage():
    source = "Sales conversion increased by 25% following the UI redesign."
    summary = "Sales conversion increased by 35% following the UI redesign."
    res = check_faithfulness(source_text=source, summary_text=summary)
    assert res["unsupported_claims"] == 1
    assert res["supported_claims"] == 0
    claim_record = res["claims"][0]
    assert claim_record["status"] == "UNSUPPORTED"
    assert "numerical claim" in claim_record["reason"].lower() or "35%" in claim_record["reason"]


# 8. Incorrect date
def test_incorrect_date():
    source = "The platform successfully migrated to PostgreSQL in Q1 2025."
    summary = "The platform successfully migrated to PostgreSQL in Q1 2026."
    res = check_faithfulness(source_text=source, summary_text=summary)
    assert res["unsupported_claims"] == 1
    claim_record = res["claims"][0]
    assert claim_record["status"] == "UNSUPPORTED"
    assert "date" in claim_record["reason"].lower() or "2026" in claim_record["reason"]


# 9. Unsupported entity
def test_unsupported_entity():
    source = "Apple and Microsoft announced a partnership on developer accessibility standards."
    summary = "Netflix acquired OrionSystems to accelerate streaming infrastructure."
    res = check_faithfulness(source_text=source, summary_text=summary)
    assert res["unsupported_claims"] >= 1
    assert any("entity" in c.get("reason", "").lower() or c["status"] == "UNSUPPORTED" for c in res["claims"])


# 10. Multiple claims
def test_multiple_claims():
    source = """
    AlphaCorp launched ProductX in 2024.
    Revenue grew by 15% to $3 million.
    The customer support team resolved 99.4% of tickets within 2 hours.
    """
    summary = """
    AlphaCorp launched ProductX in 2024.
    Revenue grew by 15% to $3 million.
    The customer support team resolved 99.4% of tickets within 2 hours.
    """
    res = check_faithfulness(source_text=source, summary_text=summary)
    assert res["claims_checked"] == 3
    assert res["supported_claims"] == 3
    assert res["unsupported_claims"] == 0
    assert res["faithfulness_score"] == 1.0


# 11. Score bounded between 0 and 1
def test_score_bounded_between_0_and_1():
    test_cases = [
        ("", ""),
        ("Some source text here.", "Completely unrelated statement."),
        ("Revenue grew 10%.", "Revenue grew 10%."),
        ("A" * 500, "B" * 100),
        ("In 2020 we did X.", "In 2020 we did X. In 2021 we did Y. In 2022 we did Z.")
    ]
    for src, summ in test_cases:
        res = check_faithfulness(source_text=src, summary_text=summ)
        assert 0.0 <= res["faithfulness_score"] <= 1.0
        assert res["status"] in {"HIGH", "MODERATE", "LOW"}


# 12. No factual claims
def test_no_factual_claims():
    source = "Comprehensive system documentation discussing system overview."
    summary = "In summary.\nOverall."
    res = check_faithfulness(source_text=source, summary_text=summary)
    assert res["claims_checked"] == 0
    assert res["faithfulness_score"] == 1.0
    assert res["status"] == "HIGH"


# 13. Deterministic verification
def test_deterministic_verification():
    source = "Latency dropped by 45ms across all European data centers."
    summary = "Latency dropped by 45ms across all European data centers."
    # With use_llm=False, check that it executes 100% deterministically
    res = check_faithfulness(source_text=source, summary_text=summary, use_llm=False)
    assert res["supported_claims"] == 1
    assert res["faithfulness_score"] == 1.0


# 14. LLM fallback
def test_llm_fallback_on_error():
    source = "Microservices architecture uses distributed event streams for state synchronization."
    unresolved_claims = [{
        "claim": "The architecture utilizes event streams.",
        "type": "factual",
        "evidence": "Microservices architecture uses distributed event streams for state synchronization."
    }]

    with patch("app.services.groq_service._call_groq_chat", side_effect=RuntimeError("Groq timeout or network failure")):
        resolved = verify_claims_with_llm_batch(unresolved_claims, source)
        assert len(resolved) == 1
        # Confirms graceful degradation without raising an exception
        assert resolved[0]["claim"] == unresolved_claims[0]["claim"]


# 15. Malformed LLM response
def test_malformed_llm_response():
    source = "Document context content."
    unresolved_claims = [{
        "claim": "Some claim.",
        "type": "factual",
        "evidence": "Evidence passage."
    }]

    with patch("app.services.groq_service._call_groq_chat", return_value="Invalid non-JSON response string from LLM"):
        resolved = verify_claims_with_llm_batch(unresolved_claims, source)
        assert len(resolved) == 1
        assert resolved[0]["claim"] == unresolved_claims[0]["claim"]


# 16. Existing hierarchical summarization integration
def test_hierarchical_integration():
    source = (
        "# Section 1: Overview\n"
        "Revenue increased 20% in 2024.\n\n"
        "# Section 2: Technical Milestones\n"
        "The team migrated to Docker containers."
    )

    with patch("app.services.groq_service._call_groq_chat", return_value="Revenue increased 20% in 2024 and the team migrated to Docker containers."):
        result = hierarchical_summarize(
            text=source,
            chunk_size=1000,
            length="short",
            format="paragraph"
        )
        assert "final_summary" in result
        assert "section_summaries" in result
        assert "faithfulness" in result
        faithfulness = result["faithfulness"]
        assert faithfulness is not None
        assert 0.0 <= faithfulness["faithfulness_score"] <= 1.0
        assert faithfulness["status"] in {"HIGH", "MODERATE", "LOW"}


# 17. Backward compatibility
def test_backward_compatibility():
    # Confirm HierarchicalSummaryResponse can be constructed with or without faithfulness
    legacy_data = {
        "final_summary": "Synthesized summary.",
        "section_summaries": [
            {
                "section_index": 1,
                "summary": "Section 1 summary.",
                "importance_score": 0.8,
                "is_redundant": False
            }
        ],
        "total_sections": 1,
        "redundant_sections_count": 0
    }
    response_legacy = HierarchicalSummaryResponse(**legacy_data)
    assert response_legacy.faithfulness is None

    # With faithfulness
    modern_data = {
        **legacy_data,
        "faithfulness": {
            "faithfulness_score": 0.95,
            "status": "HIGH",
            "claims_checked": 2,
            "supported_claims": 2,
            "partially_supported_claims": 0,
            "unsupported_claims": 0,
            "uncertain_claims": 0,
            "claims": [
                {
                    "claim": "Section 1 summary.",
                    "status": "SUPPORTED",
                    "evidence": "Source text.",
                    "confidence": 0.98,
                    "claim_type": "factual",
                    "reason": "Supported"
                }
            ]
        }
    }
    response_modern = HierarchicalSummaryResponse(**modern_data)
    assert response_modern.faithfulness is not None
    assert response_modern.faithfulness.faithfulness_score == 0.95
    assert response_modern.faithfulness.status == "HIGH"


if __name__ == "__main__":
    print("Running Faithfulness Service Unit Tests (17 scenarios)...")
    test_empty_source()
    print("[PASS] 1. test_empty_source")
    test_empty_summary()
    print("[PASS] 2. test_empty_summary")
    test_fully_faithful_summary()
    print("[PASS] 3. test_fully_faithful_summary")
    test_partially_faithful_summary()
    print("[PASS] 4. test_partially_faithful_summary")
    test_unsupported_claim()
    print("[PASS] 5. test_unsupported_claim")
    test_incorrect_number()
    print("[PASS] 6. test_incorrect_number")
    test_incorrect_percentage()
    print("[PASS] 7. test_incorrect_percentage")
    test_incorrect_date()
    print("[PASS] 8. test_incorrect_date")
    test_unsupported_entity()
    print("[PASS] 9. test_unsupported_entity")
    test_multiple_claims()
    print("[PASS] 10. test_multiple_claims")
    test_score_bounded_between_0_and_1()
    print("[PASS] 11. test_score_bounded_between_0_and_1")
    test_no_factual_claims()
    print("[PASS] 12. test_no_factual_claims")
    test_deterministic_verification()
    print("[PASS] 13. test_deterministic_verification")
    test_llm_fallback_on_error()
    print("[PASS] 14. test_llm_fallback_on_error")
    test_malformed_llm_response()
    print("[PASS] 15. test_malformed_llm_response")
    test_hierarchical_integration()
    print("[PASS] 16. test_hierarchical_integration")
    test_backward_compatibility()
    print("[PASS] 17. test_backward_compatibility")
    print("=" * 55)
    print("ALL 17 FAITHFULNESS UNIT TESTS PASSED!")
    print("=" * 55)

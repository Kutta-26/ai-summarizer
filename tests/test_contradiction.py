import sys
from pathlib import Path
from unittest.mock import patch

backend_dir = Path(__file__).resolve().parent.parent / "backend"
sys.path.insert(0, str(backend_dir))

from app.services.contradiction_service import (
    check_contradictions,
    detect_percentage_conflict,
    detect_numerical_conflict,
    detect_temporal_conflict,
    detect_entity_conflict,
    detect_factual_conflict
)
from app.schemas.summarize import (
    ContradictionResult,
    ContradictionItem,
    HierarchicalSummaryResponse
)
from app.services.groq_service import hierarchical_summarize


# ============================================================
# SECTION 9 FOCUSED TESTS (A - J)
# ============================================================

# A. No contradiction
def test_no_contradiction():
    source = "Revenue increased by 25%."
    summary = "Revenue increased by 25%."
    res = check_contradictions(source_text=source, summary_text=summary)
    assert not res["has_contradiction"]
    assert res["status"] == "CLEAN"
    assert res["total_conflicts"] == 0
    assert len(res["conflicts"]) == 0
    assert res["claims_checked"] >= 1


# B. Numerical conflict
def test_numerical_conflict_currency():
    source = "Revenue was $25 million."
    summary = "Revenue was $35 million."
    res = check_contradictions(source_text=source, summary_text=summary)
    assert res["has_contradiction"]
    assert res["status"] == "CONFLICT_DETECTED"
    assert res["total_conflicts"] == 1
    conflict = res["conflicts"][0]
    assert conflict["conflict_type"] == "numerical_conflict"
    assert "$35 million" in conflict["summary_value"] or "35" in conflict["summary_value"]
    assert "$25 million" in conflict["source_value"] or "25" in conflict["source_value"]
    assert conflict["confidence"] >= 0.90
    assert conflict["severity"] == "HIGH"


def test_numerical_conflict_counted_noun():
    source = "The company hired 120 employees."
    summary = "The company hired 150 employees."
    res = check_contradictions(source_text=source, summary_text=summary)
    assert res["has_contradiction"]
    assert res["status"] == "CONFLICT_DETECTED"
    assert res["total_conflicts"] == 1
    conflict = res["conflicts"][0]
    assert conflict["conflict_type"] == "numerical_conflict"
    assert "150" in conflict["summary_value"]
    assert "120" in conflict["source_value"]


# C. Percentage conflict
def test_percentage_conflict():
    source = "Revenue increased by 25%."
    summary = "Revenue increased by 35%."
    res = check_contradictions(source_text=source, summary_text=summary)
    assert res["has_contradiction"]
    assert res["status"] == "CONFLICT_DETECTED"
    assert res["total_conflicts"] == 1
    conflict = res["conflicts"][0]
    assert conflict["conflict_type"] == "percentage_conflict"
    assert "35%" in conflict["summary_value"]
    assert "25%" in conflict["source_value"]
    assert conflict["confidence"] >= 0.95


def test_percentage_conflict_word_form():
    source = "Sales conversion improved by 10 percent during Q2."
    summary = "Sales conversion improved by 20 percent during Q2."
    res = check_contradictions(source_text=source, summary_text=summary)
    assert res["has_contradiction"]
    assert res["total_conflicts"] == 1
    conflict = res["conflicts"][0]
    assert conflict["conflict_type"] == "percentage_conflict"


# D. Temporal conflict
def test_temporal_conflict_month_year():
    source = "The product launched in March 2026."
    summary = "The product launched in June 2026."
    res = check_contradictions(source_text=source, summary_text=summary)
    assert res["has_contradiction"]
    assert res["status"] == "CONFLICT_DETECTED"
    assert res["total_conflicts"] == 1
    conflict = res["conflicts"][0]
    assert conflict["conflict_type"] == "temporal_conflict"
    assert "June 2026" in conflict["summary_value"]
    assert "March 2026" in conflict["source_value"]


def test_temporal_conflict_year_only():
    source = "The core platform was established in 2021."
    summary = "The core platform was established in 2024."
    res = check_contradictions(source_text=source, summary_text=summary)
    assert res["has_contradiction"]
    assert res["total_conflicts"] == 1
    conflict = res["conflicts"][0]
    assert conflict["conflict_type"] == "temporal_conflict"
    assert "2024" in conflict["summary_value"]
    assert "2021" in conflict["source_value"]


# E. Entity conflict
def test_entity_conflict():
    source = "The company acquired ABC Corp."
    summary = "The company acquired XYZ Corp."
    res = check_contradictions(source_text=source, summary_text=summary)
    assert res["has_contradiction"]
    assert res["status"] == "CONFLICT_DETECTED"
    assert res["total_conflicts"] == 1
    conflict = res["conflicts"][0]
    assert conflict["conflict_type"] == "entity_conflict"
    assert "XYZ Corp" in conflict["summary_value"]
    assert "ABC Corp" in conflict["source_value"]


# F. Direct factual conflict
def test_factual_conflict_antonym():
    source = "The project was approved."
    summary = "The project was rejected."
    res = check_contradictions(source_text=source, summary_text=summary)
    assert res["has_contradiction"]
    assert res["status"] == "CONFLICT_DETECTED"
    assert res["total_conflicts"] == 1
    conflict = res["conflicts"][0]
    assert conflict["conflict_type"] == "factual_conflict"
    assert conflict["summary_value"] == "rejected"
    assert conflict["source_value"] == "approved"


def test_factual_conflict_negation():
    source = "The device supports Bluetooth."
    summary = "The device does not support Bluetooth."
    res = check_contradictions(source_text=source, summary_text=summary)
    assert res["has_contradiction"]
    assert res["status"] == "CONFLICT_DETECTED"
    assert res["total_conflicts"] == 1
    conflict = res["conflicts"][0]
    assert conflict["conflict_type"] == "factual_conflict"
    assert "negat" in conflict["reason"].lower() or "not" in conflict["summary_value"].lower()


def test_factual_conflict_direction():
    source = "The company increased production."
    summary = "The company decreased production."
    res = check_contradictions(source_text=source, summary_text=summary)
    assert res["has_contradiction"]
    assert res["status"] == "CONFLICT_DETECTED"
    assert res["total_conflicts"] == 1
    conflict = res["conflicts"][0]
    assert conflict["conflict_type"] == "factual_conflict"
    assert conflict["summary_value"] == "decreased"
    assert conflict["source_value"] == "increased"


# G. Unsupported but NOT contradictory
def test_unsupported_not_contradictory():
    source = "The company opened a new office in London."
    summary = "The company opened a new office in Paris."
    res = check_contradictions(source_text=source, summary_text=summary)
    # Opening an office in Paris is an unsupported claim, NOT a contradiction of opening in London
    assert not res["has_contradiction"]
    assert res["status"] == "CLEAN"
    assert res["total_conflicts"] == 0
    assert len(res["conflicts"]) == 0


# H. Unrelated numbers
def test_unrelated_numbers():
    source = "The company has 120 employees and revenue was $25 million."
    summary = "The company has 120 employees."
    res = check_contradictions(source_text=source, summary_text=summary)
    assert not res["has_contradiction"]
    assert res["status"] == "CLEAN"
    assert res["total_conflicts"] == 0


# I. Multiple facts (only conflicting claim reported)
def test_multiple_facts_partial_conflict():
    source = (
        "AlphaCorp launched ProductX in 2024. "
        "Revenue grew by 15% to $3 million. "
        "The customer support team resolved 99% of tickets."
    )
    summary = (
        "AlphaCorp launched ProductX in 2024. "
        "Revenue grew by 35% to $3 million. "  # Conflicting percentage
        "The customer support team resolved 99% of tickets."
    )
    res = check_contradictions(source_text=source, summary_text=summary)
    assert res["has_contradiction"]
    assert res["total_conflicts"] == 1
    assert res["conflicts_by_type"].get("percentage_conflict") == 1
    conflict = res["conflicts"][0]
    assert conflict["conflict_type"] == "percentage_conflict"
    assert "35%" in conflict["summary_value"]
    assert "15%" in conflict["source_value"]


# J. Empty/short inputs
def test_empty_source():
    res = check_contradictions(source_text="", summary_text="Revenue was $10 million.")
    assert not res["has_contradiction"]
    assert res["status"] == "CLEAN"
    assert res["total_conflicts"] == 0
    assert res["claims_checked"] == 0
    assert res["conflicts"] == []


def test_empty_summary():
    res = check_contradictions(source_text="Revenue was $10 million.", summary_text="")
    assert not res["has_contradiction"]
    assert res["status"] == "CLEAN"
    assert res["total_conflicts"] == 0
    assert res["claims_checked"] == 0
    assert res["conflicts"] == []


def test_very_short_text():
    res = check_contradictions(source_text="Hi.", summary_text="Hello.")
    assert not res["has_contradiction"]
    assert res["status"] == "CLEAN"
    assert res["total_conflicts"] == 0


def test_no_comparable_claims():
    source = "The solar system contains eight major planets."
    summary = "The football team won the championship."
    res = check_contradictions(source_text=source, summary_text=summary)
    # Different topics without factual conflict
    assert not res["has_contradiction"]
    assert res["status"] == "CLEAN"
    assert res["total_conflicts"] == 0


# ============================================================
# SCHEMA VALIDATION & INTEGRATION TESTS
# ============================================================

def test_pydantic_schema_validation():
    source = "Revenue increased by 25%."
    summary = "Revenue increased by 35%."
    res = check_contradictions(source_text=source, summary_text=summary)
    schema_model = ContradictionResult(**res)
    assert schema_model.has_contradiction is True
    assert schema_model.status == "CONFLICT_DETECTED"
    assert schema_model.total_conflicts == 1
    assert len(schema_model.conflicts) == 1
    item = schema_model.conflicts[0]
    assert item.conflict_type == "percentage_conflict"
    assert item.confidence >= 0.90
    assert item.severity == "HIGH"
    assert item.summary_value == "35%"
    assert item.source_value == "25%"


def test_hierarchical_summarization_includes_contradictions():
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
        assert "contradictions" in result
        contradictions = result["contradictions"]
        assert contradictions is not None
        assert "has_contradiction" in contradictions
        assert "status" in contradictions
        assert contradictions["status"] in {"CLEAN", "CONFLICT_DETECTED"}

        # Validate with HierarchicalSummaryResponse schema
        response = HierarchicalSummaryResponse(**result)
        assert response.contradictions is not None
        assert response.contradictions.status in {"CLEAN", "CONFLICT_DETECTED"}


def test_backward_compatibility_schema():
    # Verify HierarchicalSummaryResponse works without contradictions
    legacy_payload = {
        "final_summary": "Legacy summary without contradictions field.",
        "section_summaries": [
            {
                "section_index": 1,
                "summary": "Section 1 summary.",
                "importance_score": 0.85,
                "is_redundant": False
            }
        ],
        "total_sections": 1,
        "redundant_sections_count": 0
    }
    model = HierarchicalSummaryResponse(**legacy_payload)
    assert model.contradictions is None
    assert model.faithfulness is None


def test_api_check_contradictions_endpoint():
    from main import app
    from fastapi.testclient import TestClient
    client = TestClient(app)

    # 1. Clean endpoint test
    res = client.post(
        "/check-contradictions",
        data={
            "source_text": "Revenue increased by 25%.",
            "summary_text": "Revenue increased by 25%."
        }
    )
    assert res.status_code == 200
    data = res.json()
    assert data["has_contradiction"] is False
    assert data["status"] == "CLEAN"
    assert data["total_conflicts"] == 0

    # 2. Conflict endpoint test
    res = client.post(
        "/check-contradictions",
        data={
            "source_text": "Revenue increased by 25%.",
            "summary_text": "Revenue increased by 35%."
        }
    )
    assert res.status_code == 200
    data = res.json()
    assert data["has_contradiction"] is True
    assert data["status"] == "CONFLICT_DETECTED"
    assert data["total_conflicts"] == 1
    assert data["conflicts"][0]["conflict_type"] == "percentage_conflict"

    # 3. Empty summary validation test (400)
    res = client.post(
        "/check-contradictions",
        data={
            "source_text": "Revenue increased by 25%.",
            "summary_text": "   "
        }
    )
    assert res.status_code == 400

    # 4. Missing source validation test (400)
    res = client.post(
        "/check-contradictions",
        data={
            "summary_text": "Some summary text."
        }
    )
    assert res.status_code == 400


if __name__ == "__main__":
    print("Running Contradiction Service Unit Tests...")
    test_no_contradiction()
    print("[PASS] A. test_no_contradiction")
    test_numerical_conflict_currency()
    print("[PASS] B1. test_numerical_conflict_currency")
    test_numerical_conflict_counted_noun()
    print("[PASS] B2. test_numerical_conflict_counted_noun")
    test_percentage_conflict()
    print("[PASS] C1. test_percentage_conflict")
    test_percentage_conflict_word_form()
    print("[PASS] C2. test_percentage_conflict_word_form")
    test_temporal_conflict_month_year()
    print("[PASS] D1. test_temporal_conflict_month_year")
    test_temporal_conflict_year_only()
    print("[PASS] D2. test_temporal_conflict_year_only")
    test_entity_conflict()
    print("[PASS] E. test_entity_conflict")
    test_factual_conflict_antonym()
    print("[PASS] F1. test_factual_conflict_antonym")
    test_factual_conflict_negation()
    print("[PASS] F2. test_factual_conflict_negation")
    test_factual_conflict_direction()
    print("[PASS] F3. test_factual_conflict_direction")
    test_unsupported_not_contradictory()
    print("[PASS] G. test_unsupported_not_contradictory")
    test_unrelated_numbers()
    print("[PASS] H. test_unrelated_numbers")
    test_multiple_facts_partial_conflict()
    print("[PASS] I. test_multiple_facts_partial_conflict")
    test_empty_source()
    print("[PASS] J1. test_empty_source")
    test_empty_summary()
    print("[PASS] J2. test_empty_summary")
    test_very_short_text()
    print("[PASS] J3. test_very_short_text")
    test_no_comparable_claims()
    print("[PASS] J4. test_no_comparable_claims")
    test_pydantic_schema_validation()
    print("[PASS] K. test_pydantic_schema_validation")
    test_hierarchical_summarization_includes_contradictions()
    print("[PASS] L. test_hierarchical_summarization_includes_contradictions")
    test_backward_compatibility_schema()
    print("[PASS] M. test_backward_compatibility_schema")
    test_api_check_contradictions_endpoint()
    print("[PASS] N. test_api_check_contradictions_endpoint")
    test_llm_ambiguous_case_confirms_contradiction()
    print("[PASS] O1. test_llm_ambiguous_case_confirms_contradiction")
    test_llm_says_no_contradiction()
    print("[PASS] O2. test_llm_says_no_contradiction")
    test_llm_timeout_or_error_fallback()
    print("[PASS] O3. test_llm_timeout_or_error_fallback")
    test_bounded_call_behavior()
    print("[PASS] O4. test_bounded_call_behavior")
    print("=" * 55)
    print("ALL CONTRADICTION UNIT TESTS PASSED!")
    print("=" * 55)

# ============================================================
# LLM AMBIGUITY RESOLUTION TESTS
# ============================================================

def test_llm_ambiguous_case_confirms_contradiction():
    source = "The project was approved by the board on Monday."
    summary = "The board rejected the project on Monday."
    
    with patch("app.services.contradiction_service.find_evidence_for_contradiction", return_value=[("The project was approved by the board on Monday.", 0.95)]):
        with patch("app.services.contradiction_service.evaluate_claim_contradiction", return_value=None):
            with patch("app.services.groq_service.check_ambiguous_contradictions_llm") as mock_llm:
                mock_llm.return_value = [{
                    "conflict_type": "factual_conflict",
                    "confidence": 0.95,
                    "severity": "HIGH",
                    "summary_value": "rejected",
                    "source_value": "approved",
                    "reason": "The summary claims it was rejected, but the source says it was approved."
                }]
                
                res = check_contradictions(source_text=source, summary_text=summary, use_llm=True)
                
                assert mock_llm.called
                assert res["has_contradiction"] is True
                assert res["total_conflicts"] == 1
                assert res["conflicts"][0]["summary_value"] == "rejected"

def test_llm_says_no_contradiction():
    source = "The project was greenlit by the board on Monday."
    summary = "The board approved the project on Monday."
    
    with patch("app.services.contradiction_service.find_evidence_for_contradiction", return_value=[("The project was greenlit by the board on Monday.", 0.95)]):
        with patch("app.services.contradiction_service.evaluate_claim_contradiction", return_value=None):
            with patch("app.services.groq_service.check_ambiguous_contradictions_llm") as mock_llm:
                mock_llm.return_value = []
                
                res = check_contradictions(source_text=source, summary_text=summary, use_llm=True)
                
                assert mock_llm.called
                assert res["has_contradiction"] is False
                assert res["total_conflicts"] == 0

def test_llm_timeout_or_error_fallback():
    source = "The project was approved by the board on Monday."
    summary = "The board rejected the project on Monday."
    
    with patch("app.services.contradiction_service.find_evidence_for_contradiction", return_value=[("The project was approved by the board on Monday.", 0.95)]):
        with patch("app.services.contradiction_service.evaluate_claim_contradiction", return_value=None):
            with patch("app.services.groq_service.check_ambiguous_contradictions_llm", side_effect=Exception("API Timeout")):
                res = check_contradictions(source_text=source, summary_text=summary, use_llm=True)
                
                assert res["has_contradiction"] is False
                assert res["total_conflicts"] == 0

def test_bounded_call_behavior():
    source = "A. B. C. D. E. F. G."
    summary = "A. B. C. D. E. F. G."
    
    with patch("app.services.contradiction_service.extract_claims") as mock_claims:
        mock_claims.return_value = [{"claim": str(i)} for i in range(10)]
        with patch("app.services.contradiction_service.find_evidence_for_contradiction") as mock_evidence:
            mock_evidence.return_value = [("evidence", 0.9)]
            with patch("app.services.contradiction_service.evaluate_claim_contradiction", return_value=None):
                with patch("app.services.groq_service.check_ambiguous_contradictions_llm") as mock_llm:
                    mock_llm.return_value = []
                    
                    check_contradictions(source_text=source, summary_text=summary, use_llm=True)
                    
                    assert mock_llm.called
                    args, _ = mock_llm.call_args
                    passed_claims = args[0]
                    assert len(passed_claims) == 5

# Add to test runner

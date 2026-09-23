import sys
from pathlib import Path

backend_dir = Path(__file__).resolve().parent.parent / "backend"
sys.path.insert(0, str(backend_dir))

from app.services.importance_service import (
    score_importance,
    batch_score_importance,
    detect_signals,
    compute_information_density,
    compute_structural_score,
    calculate_heuristic_score
)


def test_empty_text():
    res = score_importance("")
    assert res["score"] == 0.0
    assert "Empty" in res["reason"]
    assert all(val is False for val in res["signals"].values())


def test_high_importance_signals():
    text = """
    # Section 3: Financial & Operational Results
    The key findings reveal that revenue grew by 24.5% ($12.5M) in Q3.
    The executive committee decided to approve the expansion budget.
    Critical risks include supply chain latency of 450ms.
    Action items: team must implement the failover protocol before deadline.
    In conclusion, overall performance exceeded the target roadmap.
    """
    res = score_importance(text, chunk_index=1, total_chunks=3)
    assert 0.0 <= res["score"] <= 1.0
    assert res["score"] >= 0.70, f"Expected high score >= 0.70, got {res['score']}"
    assert "High importance" in res["reason"]

    # Verify signal categories
    signals = res["signals"]
    assert signals["key_findings"] is True
    assert signals["decisions"] is True
    assert signals["metrics"] is True
    assert signals["actions"] is True
    assert signals["risks"] is True
    assert signals["conclusion"] is True


def test_low_importance_text():
    text = "Well, you know, maybe we can kind of talk about this sometime whenever everyone is around."
    res = score_importance(text, chunk_index=2, total_chunks=5)
    assert 0.0 <= res["score"] <= 1.0
    assert res["score"] < 0.40, f"Expected low score < 0.40, got {res['score']}"
    assert "Low importance" in res["reason"]


def test_bounded_scores():
    # Boundary check: Ensure score is strictly bounded [0.0, 1.0] across diverse texts
    texts = [
        "",
        "Short text.",
        "A " * 500,
        "# Critical Alert: 100% outage detected with $5,000,000 loss! Decision: shutdown immediately. Next steps: restore backup. In conclusion, severe risk.",
        "Normal documentation describing a simple module interface with no metrics."
    ]
    for t in texts:
        res = score_importance(t)
        assert 0.0 <= res["score"] <= 1.0
        assert isinstance(res["reason"], str)
        assert isinstance(res["signals"], dict)
        for key in ["key_findings", "decisions", "metrics", "actions", "risks", "conclusion"]:
            assert key in res["signals"]
            assert isinstance(res["signals"][key], bool)


def test_batch_scoring():
    chunks = [
        "# Chapter 1: Introduction and Background",
        "The committee decided to allocate $500,000 for the infrastructure project.",
        "Just some auxiliary commentary with no direct decisions."
    ]
    results = batch_score_importance(chunks)
    assert len(results) == 3
    for r in results:
        assert 0.0 <= r["score"] <= 1.0
        assert "signals" in r


if __name__ == "__main__":
    print("Running Importance Service Unit Tests...")
    test_empty_text()
    print("[PASS] test_empty_text")
    test_high_importance_signals()
    print("[PASS] test_high_importance_signals")
    test_low_importance_text()
    print("[PASS] test_low_importance_text")
    test_bounded_scores()
    print("[PASS] test_bounded_scores")
    test_batch_scoring()
    print("[PASS] test_batch_scoring")
    print("ALL 5 IMPORTANCE UNIT TESTS PASSED!")

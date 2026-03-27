"""
Unit tests for pattern_scorer.py (HOS-99 T7 acceptance criteria).

Tests cover:
  - Followed feedback boosts rank
  - Rejected feedback penalises rank
  - Neutral feedback leaves score unchanged
  - Recency weighting pulls recent patterns higher
  - Empty input handled gracefully
  - top_k returns correct slice
  - Score clamped to >= 0
"""
import pytest
from datetime import datetime, timedelta, timezone
from app.services.pattern_scorer import score_patterns, top_k, _FEEDBACK_BOOST_FOLLOWED, _FEEDBACK_PENALTY_REJECTED


def _make_pattern(pid: str, score: float, feedback: str) -> dict:
    return {
        "id": pid,
        "score": score,
        "payload": {
            "service_type": "dinner",
            "feedback_status": feedback,
            "pattern_text": f"Pattern {pid}",
        },
    }


# ---------------------------------------------------------------------------
# Feedback boost / penalty
# ---------------------------------------------------------------------------

class TestFeedbackAdjustment:
    def test_followed_lowers_score(self):
        p = _make_pattern("a", 0.5, "followed")
        result = score_patterns([p])
        assert result[0]["final_score"] < 0.5

    def test_rejected_raises_score(self):
        p = _make_pattern("b", 0.5, "rejected")
        result = score_patterns([p])
        assert result[0]["final_score"] > 0.5

    def test_neutral_score_unchanged(self):
        p = _make_pattern("c", 0.5, "neutral")
        result = score_patterns([p])
        assert result[0]["final_score"] == pytest.approx(0.5, abs=1e-6)

    def test_followed_boost_magnitude(self):
        p = _make_pattern("d", 0.5, "followed")
        result = score_patterns([p])
        assert result[0]["final_score"] == pytest.approx(0.5 + _FEEDBACK_BOOST_FOLLOWED, abs=1e-6)

    def test_rejected_penalty_magnitude(self):
        p = _make_pattern("e", 0.5, "rejected")
        result = score_patterns([p])
        assert result[0]["final_score"] == pytest.approx(0.5 + _FEEDBACK_PENALTY_REJECTED, abs=1e-6)

    def test_score_clamped_to_zero(self):
        """A very-similar followed pattern cannot go below 0."""
        p = _make_pattern("f", 0.0, "followed")
        result = score_patterns([p])
        assert result[0]["final_score"] >= 0.0


# ---------------------------------------------------------------------------
# Sorting
# ---------------------------------------------------------------------------

class TestSorting:
    def test_followed_ranks_above_neutral(self):
        neutral = _make_pattern("n", 0.4, "neutral")
        followed = _make_pattern("f", 0.4, "followed")
        result = score_patterns([neutral, followed])
        assert result[0]["id"] == "f"

    def test_neutral_ranks_above_rejected(self):
        neutral = _make_pattern("n", 0.4, "neutral")
        rejected = _make_pattern("r", 0.4, "rejected")
        result = score_patterns([neutral, rejected])
        assert result[0]["id"] == "n"

    def test_followed_ranks_above_rejected(self):
        rejected = _make_pattern("r", 0.3, "rejected")
        followed = _make_pattern("f", 0.5, "followed")
        result = score_patterns([rejected, followed])
        assert result[0]["id"] == "f"

    def test_multiple_patterns_sorted_ascending(self):
        patterns = [
            _make_pattern("a", 0.9, "followed"),
            _make_pattern("b", 0.1, "neutral"),
            _make_pattern("c", 0.5, "rejected"),
        ]
        result = score_patterns(patterns)
        scores = [r["final_score"] for r in result]
        assert scores == sorted(scores)


# ---------------------------------------------------------------------------
# Recency weighting
# ---------------------------------------------------------------------------

class TestRecencyWeight:
    def test_recent_pattern_scores_lower_than_old(self):
        pid_new = "new"
        pid_old = "old"
        patterns = [
            _make_pattern(pid_old, 0.5, "neutral"),
            _make_pattern(pid_new, 0.5, "neutral"),
        ]
        recency_map = {
            pid_new: datetime.now(timezone.utc) - timedelta(days=1),
            pid_old: datetime.now(timezone.utc) - timedelta(days=365),
        }
        result = score_patterns(patterns, recency_map=recency_map)
        by_id = {r["id"]: r["final_score"] for r in result}
        assert by_id[pid_new] < by_id[pid_old]

    def test_no_recency_map_same_as_no_adjustment(self):
        p = _make_pattern("x", 0.5, "neutral")
        without_map = score_patterns([p])
        with_map = score_patterns([p], recency_map={})  # no entry for "x"
        assert without_map[0]["final_score"] == pytest.approx(with_map[0]["final_score"], abs=1e-6)


# ---------------------------------------------------------------------------
# Edge cases
# ---------------------------------------------------------------------------

class TestEdgeCases:
    def test_empty_input_returns_empty(self):
        assert score_patterns([]) == []

    def test_single_pattern(self):
        p = _make_pattern("solo", 0.3, "neutral")
        result = score_patterns([p])
        assert len(result) == 1
        assert result[0]["id"] == "solo"

    def test_final_score_present_on_all_results(self):
        patterns = [_make_pattern(str(i), 0.5, "neutral") for i in range(5)]
        result = score_patterns(patterns)
        assert all("final_score" in r for r in result)

    def test_original_dict_not_mutated(self):
        p = _make_pattern("m", 0.5, "neutral")
        score_patterns([p])
        assert "final_score" not in p


# ---------------------------------------------------------------------------
# top_k
# ---------------------------------------------------------------------------

class TestTopK:
    def test_top_k_limits_results(self):
        patterns = [_make_pattern(str(i), float(i) / 10, "neutral") for i in range(10)]
        result = top_k(patterns, k=3)
        assert len(result) == 3

    def test_top_k_returns_lowest_scores(self):
        patterns = [_make_pattern(str(i), float(i) / 10, "neutral") for i in range(10)]
        result = top_k(patterns, k=3)
        scores = [r["final_score"] for r in result]
        assert max(scores) <= 0.3  # 0, 0.1, 0.2 are the best

    def test_top_k_larger_than_input(self):
        patterns = [_make_pattern("a", 0.5, "neutral")]
        result = top_k(patterns, k=5)
        assert len(result) == 1

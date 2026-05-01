"""Unit tests for backend/app/services/pattern_scorer.py.

Acceptance criteria (HOS-99):
- Boost patterns with feedback = 'followed'
- Penalise patterns with feedback = 'rejected'
- Sort by recency (newer > older at equal base score and feedback)
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from app.services.pattern_scorer import _recency_weight, score_patterns


# ---------------------------------------------------------------------------
# _recency_weight
# ---------------------------------------------------------------------------


class TestRecencyWeight:
    def test_today_is_one(self):
        now = datetime.now(timezone.utc)
        assert _recency_weight(now) == pytest.approx(1.0, abs=1e-3)

    def test_half_life_is_half(self):
        past = datetime.now(timezone.utc) - timedelta(days=30)
        assert _recency_weight(past) == pytest.approx(0.5, abs=1e-2)

    def test_none_returns_one(self):
        assert _recency_weight(None) == pytest.approx(1.0)

    def test_string_iso_parsed(self):
        ts = (datetime.now(timezone.utc) - timedelta(days=30)).isoformat()
        assert _recency_weight(ts) == pytest.approx(0.5, abs=1e-2)

    def test_naive_datetime_treated_as_utc(self):
        naive = datetime.utcnow() - timedelta(days=30)
        assert _recency_weight(naive) == pytest.approx(0.5, abs=1e-2)

    def test_invalid_string_returns_one(self):
        assert _recency_weight("not-a-date") == pytest.approx(1.0)

    def test_older_weight_is_lower(self):
        old = datetime.now(timezone.utc) - timedelta(days=60)
        recent = datetime.now(timezone.utc) - timedelta(days=10)
        assert _recency_weight(old) < _recency_weight(recent)


# ---------------------------------------------------------------------------
# score_patterns — feedback signal
# ---------------------------------------------------------------------------

_NOW = datetime.now(timezone.utc).isoformat()


def _pattern(score: float, feedback: str | None, created_at: str = _NOW) -> dict:
    return {
        "id": "test-id",
        "score": score,
        "payload": {"manager_feedback": feedback, "created_at": created_at},
    }


class TestFeedbackSignal:
    def test_followed_ranks_above_no_feedback(self):
        patterns = [
            _pattern(0.8, None),
            _pattern(0.8, "followed"),
        ]
        result = score_patterns(patterns)
        assert result[0]["payload"]["manager_feedback"] == "followed"

    def test_rejected_ranks_below_no_feedback(self):
        patterns = [
            _pattern(0.8, "rejected"),
            _pattern(0.8, None),
        ]
        result = score_patterns(patterns)
        assert result[0]["payload"]["manager_feedback"] is None

    def test_followed_ranks_above_rejected(self):
        patterns = [
            _pattern(0.8, "rejected"),
            _pattern(0.8, "followed"),
        ]
        result = score_patterns(patterns)
        assert result[0]["payload"]["manager_feedback"] == "followed"

    def test_composite_score_attached(self):
        patterns = [_pattern(0.5, "followed")]
        result = score_patterns(patterns)
        assert "composite_score" in result[0]
        # followed boost = 1.5 × 0.5 × ~1.0 ≈ 0.75
        assert result[0]["composite_score"] == pytest.approx(0.75, abs=0.01)

    def test_rejected_composite_score(self):
        patterns = [_pattern(1.0, "rejected")]
        result = score_patterns(patterns)
        # penalty = 0.3 × 1.0 × ~1.0 ≈ 0.3
        assert result[0]["composite_score"] == pytest.approx(0.3, abs=0.01)

    def test_neutral_no_change_to_score(self):
        patterns = [_pattern(0.6, "neutral")]
        result = score_patterns(patterns)
        assert result[0]["composite_score"] == pytest.approx(0.6, abs=0.01)


# ---------------------------------------------------------------------------
# score_patterns — recency signal
# ---------------------------------------------------------------------------


class TestRecencySignal:
    def test_newer_beats_older_at_same_feedback(self):
        old_ts = (datetime.now(timezone.utc) - timedelta(days=90)).isoformat()
        new_ts = datetime.now(timezone.utc).isoformat()
        patterns = [
            _pattern(0.8, "followed", old_ts),
            _pattern(0.8, "followed", new_ts),
        ]
        result = score_patterns(patterns)
        assert result[0]["payload"]["created_at"] == new_ts

    def test_high_score_old_vs_low_score_new(self):
        old_ts = (datetime.now(timezone.utc) - timedelta(days=120)).isoformat()
        new_ts = datetime.now(timezone.utc).isoformat()
        # Very old pattern with high score vs fresh pattern with lower score
        patterns = [
            _pattern(1.0, "followed", old_ts),
            _pattern(0.9, "followed", new_ts),
        ]
        result = score_patterns(patterns)
        # newer should win because recency decay on 120-day-old = 0.5^4 = 0.0625
        # old:  1.0 × 1.5 × 0.0625 ≈ 0.094
        # new:  0.9 × 1.5 × ~1.0  ≈ 1.35
        assert result[0]["payload"]["created_at"] == new_ts


# ---------------------------------------------------------------------------
# score_patterns — edge cases
# ---------------------------------------------------------------------------


class TestEdgeCases:
    def test_empty_list_returns_empty(self):
        assert score_patterns([]) == []

    def test_missing_payload_key(self):
        pattern = {"id": "x", "score": 0.7}
        result = score_patterns([pattern])
        assert len(result) == 1
        assert result[0]["composite_score"] == pytest.approx(0.7, abs=0.01)

    def test_none_score_treated_as_zero(self):
        pattern = {"id": "x", "score": None, "payload": {}}
        result = score_patterns([pattern])
        assert result[0]["composite_score"] == pytest.approx(0.0)

    def test_original_keys_preserved(self):
        pattern = {"id": "abc", "score": 0.5, "payload": {"extra": "data"}}
        result = score_patterns([pattern])
        assert result[0]["id"] == "abc"
        assert result[0]["payload"]["extra"] == "data"

    def test_unknown_feedback_uses_neutral_multiplier(self):
        pattern = {"id": "x", "score": 0.6, "payload": {"manager_feedback": "unknown"}}
        result = score_patterns([pattern])
        # unknown → fallback 1.0 multiplier
        assert result[0]["composite_score"] == pytest.approx(0.6, abs=0.01)

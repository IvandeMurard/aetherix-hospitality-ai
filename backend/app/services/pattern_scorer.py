"""
Pattern Scorer — feedback-aware ranking layer (HOS-99 T7).

Takes the raw similarity-ordered results from RAGService and re-ranks them
by combining:
  1. Cosine similarity score (lower = more similar in pgvector)
  2. Manager feedback boost / penalty
  3. Recency weight (more recent patterns weighted higher)

This replaces the implicit "memory injection" that Backboard.io performed
and makes the scoring logic explicit, testable, and tunable.

Score semantics (output): lower final_score = better rank.
"""Pattern scoring layer — replaces the Backboard "memory recall" ranking.

Takes raw pgvector results (cosine similarity score + payload) and re-ranks
them using two signals:

1. **Feedback boost/penalty** — patterns that managers followed get a 1.5×
   multiplier; patterns they rejected get a 0.3× penalty.
2. **Recency weighting** — exponential decay with a 30-day half-life so that
   stale patterns gradually lose influence without being discarded.

composite_score = base_score × feedback_multiplier × recency_weight

Results are returned sorted descending by composite_score.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

# ------------------------------------------------------------------
# Tuning constants (adjust per business experiment)
# ------------------------------------------------------------------
_FEEDBACK_BOOST_FOLLOWED = -0.15   # cosine-distance penalty: pull rank up
_FEEDBACK_PENALTY_REJECTED = +0.40  # pull rank down hard
_RECENCY_MAX_WEIGHT = -0.10         # applied to patterns from last 7 days
_RECENCY_HALF_LIFE_DAYS = 30        # weight halves every 30 days


def _recency_weight(created_at: Optional[datetime]) -> float:
    """
    Returns a negative score adjustment for recent patterns.
    Ranges from _RECENCY_MAX_WEIGHT (today) to ~0 (very old).
    """
    if created_at is None:
        return 0.0
    if created_at.tzinfo is None:
        created_at = created_at.replace(tzinfo=timezone.utc)
    age_days = (datetime.now(timezone.utc) - created_at).days
    # Exponential decay: weight = MAX * 0.5^(age / half_life)
    decay = 0.5 ** (age_days / _RECENCY_HALF_LIFE_DAYS)
    return _RECENCY_MAX_WEIGHT * decay


def score_patterns(
    patterns: List[Dict[str, Any]],
    *,
    recency_map: Optional[Dict[str, datetime]] = None,
) -> List[Dict[str, Any]]:
    """
    Re-ranks *patterns* from RAGService.find_similar_patterns.

    Each pattern dict is expected to have:
      - "score"   : float  — raw cosine distance from pgvector (0=identical, 1=orthogonal)
      - "payload" : dict   — must contain "feedback_status" key
      - "id"      : str

    Optional *recency_map*: {pattern_id → created_at datetime}.
    When provided, recency weighting is applied.

    Returns the same list, sorted by "final_score" ascending, with
    "final_score" added to each dict.
    """
    if not patterns:
        return []

    scored = []
    for p in patterns:
        base = float(p.get("score", 1.0))
        feedback = p.get("payload", {}).get("feedback_status", "neutral")

        adjustment = 0.0
        if feedback == "followed":
            adjustment += _FEEDBACK_BOOST_FOLLOWED
        elif feedback == "rejected":
            adjustment += _FEEDBACK_PENALTY_REJECTED

        if recency_map is not None:
            created_at = recency_map.get(p.get("id", ""))
            adjustment += _recency_weight(created_at)

        final = max(0.0, base + adjustment)  # clamp to [0, ∞)
        scored.append({**p, "final_score": round(final, 6)})

    scored.sort(key=lambda x: x["final_score"])
    return scored


def top_k(
    patterns: List[Dict[str, Any]],
    k: int = 3,
    *,
    recency_map: Optional[Dict[str, datetime]] = None,
) -> List[Dict[str, Any]]:
    """Convenience wrapper: score then return top-k."""
    return score_patterns(patterns, recency_map=recency_map)[:k]
from typing import Any, Dict, List

# Feedback multipliers — ordered for clarity
_FEEDBACK_MULTIPLIER: Dict[str | None, float] = {
    "followed": 1.5,
    "neutral": 1.0,
    None: 1.0,
    "rejected": 0.3,
}

# Recency: weight = 0.5^(age_days / HALF_LIFE)
_RECENCY_HALF_LIFE_DAYS: float = 30.0


def _recency_weight(created_at: datetime | str | None) -> float:
    """Exponential-decay recency weight in [0, 1].

    A pattern created today has weight 1.0; one created 30 days ago has
    weight 0.5; 60 days ago → 0.25, etc.
    """
    if created_at is None:
        return 1.0

    if isinstance(created_at, str):
        try:
            created_at = datetime.fromisoformat(created_at)
        except ValueError:
            return 1.0

    if created_at.tzinfo is None:
        created_at = created_at.replace(tzinfo=timezone.utc)

    age_days = (datetime.now(timezone.utc) - created_at).total_seconds() / 86_400
    return 0.5 ** (age_days / _RECENCY_HALF_LIFE_DAYS)


def score_patterns(patterns: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Re-rank *patterns* by composite_score and return them sorted descending.

    Each element is expected to have:
    - ``score``   : float  — cosine similarity from pgvector (0–1 after ``1 - distance``)
    - ``payload`` : dict   — JSONB row payload; may contain:
        * ``manager_feedback`` : str | None  — 'followed' | 'rejected' | 'neutral'
        * ``created_at``       : str | datetime | None

    A new key ``composite_score`` is added to each element.
    """
    scored: List[Dict[str, Any]] = []

    for pattern in patterns:
        payload: Dict[str, Any] = pattern.get("payload") or {}

        feedback = payload.get("manager_feedback")  # str or None
        boost = _FEEDBACK_MULTIPLIER.get(feedback, 1.0)

        recency = _recency_weight(payload.get("created_at"))

        base_score = float(pattern.get("score") or 0.0)
        composite = base_score * boost * recency

        scored.append({**pattern, "composite_score": round(composite, 6)})

    scored.sort(key=lambda p: p["composite_score"], reverse=True)
    return scored

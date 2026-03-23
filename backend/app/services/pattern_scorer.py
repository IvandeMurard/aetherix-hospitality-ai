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

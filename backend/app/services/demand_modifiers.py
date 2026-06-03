"""Demand modifier functions for anomaly detection.

Provides:
  - weather_modifier(condition_code) -> (float, dict)
  - event_modifier(events)           -> (float, list[dict])

Returns both a numeric multiplier offset and structured triggering_factor dicts
for persistence in the demand_anomalies.triggering_factors JSONB column.

Architecture: Fat Backend — all modifier logic lives here, never in Next.js.
[Source: architecture.md#Structure-Patterns]
"""
from __future__ import annotations

from typing import Any, Dict, List, Tuple

# ---------------------------------------------------------------------------
# Weather modifier table
# ---------------------------------------------------------------------------
_WEATHER_MODIFIERS: Dict[str, float] = {
    "thunderstorm": -0.20,
    "rain": -0.10,
    "showers": -0.10,
    "snow": -0.15,
    "fog": -0.05,
    "clear": +0.05,
    "partly_cloudy": 0.00,
}


def weather_modifier(condition_code: str) -> Tuple[float, Dict[str, Any]]:
    """Return (modifier_offset, triggering_factor_dict) for a weather condition.

    Unknown condition codes default to 0.0 (no impact).

    Args:
        condition_code: Normalised weather condition string, e.g. "thunderstorm".

    Returns:
        A tuple of:
          - float modifier offset (e.g. -0.20)
          - dict suitable for storage in triggering_factors JSONB
    """
    modifier = _WEATHER_MODIFIERS.get(condition_code.lower(), 0.0)
    impact_pct = f"{modifier:+.0%}"
    factor: Dict[str, Any] = {
        "type": "weather",
        "condition": condition_code.lower(),
        "impact": impact_pct,
    }
    return modifier, factor


# ---------------------------------------------------------------------------
# Event modifier table
# ---------------------------------------------------------------------------
_EVENT_MODIFIERS: Dict[str, float] = {
    "conference": +0.25,
    "concert": +0.20,
    "sports": +0.15,
    "festival": +0.20,
    "community": +0.05,
    "other": +0.05,
}

_EVENT_MODIFIER_CAP = 0.50  # maximum cumulative event modifier


def event_modifier(
    events: List[Any],
) -> Tuple[float, List[Dict[str, Any]]]:
    """Return (cumulative_modifier_offset, triggering_factors_list) for a list of events.

    The cumulative modifier is capped at +_EVENT_MODIFIER_CAP (default +0.50).

    Args:
        events: List of LocalEvent ORM instances (or duck-typed objects with
                `category`, `id`/`predicthq_event_id`, and `impact_score` attrs).

    Returns:
        A tuple of:
          - float cumulative modifier offset (capped at +0.50)
          - list of triggering_factor dicts
    """
    cumulative = 0.0
    factors: List[Dict[str, Any]] = []

    for event in events:
        category = getattr(event, "category", "other").lower()
        per_event = _EVENT_MODIFIERS.get(category, _EVENT_MODIFIERS["other"])
        # Respect cap
        remaining_cap = _EVENT_MODIFIER_CAP - cumulative
        applied = min(per_event, remaining_cap)
        if applied <= 0:
            break  # cap already reached
        cumulative += applied

        event_id = str(
            getattr(event, "predicthq_event_id", None)
            or getattr(event, "id", "unknown")
        )
        factor: Dict[str, Any] = {
            "type": "event",
            "event_id": event_id,
            "category": category,
            "impact": f"{applied:+.0%}",
        }
        factors.append(factor)

    return cumulative, factors

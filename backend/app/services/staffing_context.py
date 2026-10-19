"""Staffing context classes — HOS-345 (Décisions #43, #44).

A hotel does not staff an event night, a banquet or a summer terrace like a
quiet Tuesday. Its staffing rules (HOS-343, ``hotel_parameters``) can be set
per context class; this module says which classes apply to one service.

The list of classes is **closed** (``CONTEXT_CLASSES``) and each class is
resolved from a signal the pipeline already has, never guessed by a model:

==================  ==========================================================
class               signal
==================  ==========================================================
banquet             ``context["banquet"] is True``: declared by the hotel or
                    its agent (the hotel's own group / private event). No
                    source fills it automatically today.
event_night         an event in ``context["events"]`` (PredictHQ producer)
                    with rank or local rank ≥ ``EVENT_MIN_RANK`` or expected
                    attendance ≥ ``EVENT_MIN_ATTENDANCE``, and not farther
                    than ``EVENT_MAX_DISTANCE_KM`` when its distance is known
public_holiday      French public holiday on the date (``holidays``, installed
                    with Prophet, same calendar as the forecast's holidays)
school_holidays     ``context["school_holidays"] is True``: declared, like
                    banquet. No school calendar is in the pipeline yet.
high_season         the date's month falls in the hotel's own high season
                    (``high_season_start_month`` → ``high_season_end_month``,
                    wrapping over the new year); not set → never applies
breakfast / lunch   the service type of the forecast
/ dinner
==================  ==========================================================

Priority (written, tested): the order of ``CONTEXT_CLASSES``. For each rule
(a role's ratio, a role's usual team), the first applicable class for which
the hotel set a value wins; then the hotel's flat value; then the system
default. An event night at dinner therefore uses the hotel's event-night
ratio if set, else its dinner ratio, else its flat ratio.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from typing import Any, Mapping, Optional

CONTEXT_CLASSES: tuple[str, ...] = (
    "banquet", "event_night", "public_holiday", "school_holidays", "high_season",
    "breakfast", "lunch", "dinner",
)
SERVICE_TYPES: tuple[str, ...] = ("breakfast", "lunch", "dinner")
CLASS_LABELS: dict[str, dict[str, str]] = {
    "en": {"banquet": "banquet", "event_night": "event night", "public_holiday": "public holiday",
           "school_holidays": "school holidays", "high_season": "high season",
           "breakfast": "breakfast", "lunch": "lunch", "dinner": "dinner"},
    "fr": {"banquet": "banquet", "event_night": "soirée événement", "public_holiday": "jour férié",
           "school_holidays": "vacances scolaires", "high_season": "haute saison",
           "breakfast": "petit-déjeuner", "lunch": "déjeuner", "dinner": "dîner"},
}

EVENT_MIN_RANK = 60
EVENT_MIN_ATTENDANCE = 2000
EVENT_MAX_DISTANCE_KM = 5.0


@dataclass(frozen=True)
class ContextResolution:
    """The classes that apply, in priority order, and the signal behind each."""

    classes: tuple[str, ...] = ()
    signals: dict[str, Any] = field(default_factory=dict)

    def as_dict(self) -> dict:
        return {"classes": list(self.classes), "signals": dict(self.signals)}


def _number(v: Any) -> Optional[float]:
    return float(v) if isinstance(v, (int, float)) and not isinstance(v, bool) else None


def qualifying_event(event: Mapping) -> bool:
    distance = _number(event.get("distance_km"))
    if distance is not None and distance > EVENT_MAX_DISTANCE_KM:
        return False
    rank = max((_number(event.get(k)) or 0.0) for k in ("rank", "local_rank"))
    attendance = _number(event.get("phq_attendance")) or 0.0
    return rank >= EVENT_MIN_RANK or attendance >= EVENT_MIN_ATTENDANCE


def _public_holiday(day: date) -> Optional[str]:
    try:
        import holidays  # installed with Prophet
    except ImportError:  # pragma: no cover — prophet always brings it
        return None
    return holidays.France(years=day.year).get(day)


def in_season(month: int, start: Optional[float], end: Optional[float]) -> bool:
    if start is None or end is None:
        return False
    s, e = int(start), int(end)
    return s <= month <= e if s <= e else (month >= s or month <= e)


def resolve(
    target_date: Optional[date],
    service_type: Optional[str],
    context: Optional[Mapping],
    params: Any = None,
) -> ContextResolution:
    """Applicable classes for one service, in ``CONTEXT_CLASSES`` order.
    ``params``: the hotel's parameters (anything with ``get``), for its season."""
    context = context or {}
    found: dict[str, Any] = {}
    if context.get("banquet") is True:
        found["banquet"] = "declared"
    events = [e for e in (context.get("events") or []) if isinstance(e, Mapping) and qualifying_event(e)]
    if events:
        found["event_night"] = [str(e.get("title") or e.get("name") or "event") for e in events][:3]
    if target_date is not None:
        name = _public_holiday(target_date)
        if name:
            found["public_holiday"] = name
    if context.get("school_holidays") is True:
        found["school_holidays"] = "declared"
    if target_date is not None and params is not None and in_season(
        target_date.month, params.get("high_season_start_month"), params.get("high_season_end_month"),
    ):
        found["high_season"] = (f"months {int(params.get('high_season_start_month'))}"
                                f"-{int(params.get('high_season_end_month'))}")
    if service_type in SERVICE_TYPES:
        found[service_type] = "service_type"
    classes = tuple(c for c in CONTEXT_CLASSES if c in found)
    return ContextResolution(classes=classes, signals={c: found[c] for c in classes})

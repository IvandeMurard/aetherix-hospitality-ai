"""Forecast context — one builder, from what is stored, true or absent (HOS-358).

Every forecast path builds its context here: the WhatsApp ``prévision`` command,
the MCP tool ``get_operational_predictions``, ``POST /predict`` and
``GET /predictions/current``. The same hotel, day and service get the same
context whatever the surface (Décision #44). Before HOS-358 the MCP tool passed
"Unknown" weather, no events and no occupancy, and ``/predictions/current``
wrote "Clear, 22 °C" and an 85 % occupancy that came from nowhere (HOS-352).

What is read, all stored by the existing syncs:

* **weather** — ``weather_forecasts`` (Open-Meteo, ``workers/weather_sync``):
  the row nearest the service hour, within ``WEATHER_WINDOW``. WMO code →
  label. Absent → ``{}`` (consumers read ``weather.get("condition")``).
* **events** — ``local_events`` (PredictHQ, ``workers/event_sync``), active
  that day within 5 km (``events_enrichment``). None found → ``[]``.
* **occupancy** — ``pms_sync_logs`` for that day: ``rooms_sold /
  rooms_available`` when the PMS gave both (HOS-352). Absent → ``None``.

``context_sources`` says, for each element, where it came from or why it is
absent, so a reply can say "occupancy unknown" instead of guessing. No default
is ever written as data.

What the context does NOT do yet: Prophet reads ``context["regressors"]``,
which no caller supplies, so the covers figure does not move with this
context. It feeds the reasoning text, the memory query and the staffing
context class (event night, HOS-345). Passing it as regressors is a separate,
evaluated change.
"""
from __future__ import annotations

import logging
from datetime import date, datetime, time, timedelta, timezone
from typing import Any, Mapping, Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import PMSSyncLog, RestaurantProfile, WeatherForecast
from app.providers.pms.base import PMSDataStatus
from app.services.events_enrichment import enrich_events_context

logger = logging.getLogger(__name__)

# The hour each service is looked up at, in the hotel's local time.
SERVICE_HOUR = {"breakfast": 8, "lunch": 13, "dinner": 20}
WEATHER_WINDOW = timedelta(hours=3)

# WMO weather interpretation codes (Open-Meteo) → the labels the rest of the
# code uses (demand_modifiers._WEATHER_MODIFIERS).
_WMO_LABELS: tuple[tuple[range, str], ...] = (
    (range(0, 1), "clear"),
    (range(1, 3), "partly_cloudy"),
    (range(3, 4), "cloudy"),
    (range(45, 49), "fog"),
    (range(51, 68), "rain"),
    (range(71, 78), "snow"),
    (range(80, 83), "showers"),
    (range(85, 87), "snow"),
    (range(95, 100), "thunderstorm"),
)


def wmo_label(code: Optional[int]) -> Optional[str]:
    if code is None:
        return None
    return next((label for codes, label in _WMO_LABELS if int(code) in codes), None)


def _source(status: str, source: Optional[str] = None, **detail: Any) -> dict:
    return {"status": status, "source": source, **detail}


async def _weather(db: AsyncSession, profile: RestaurantProfile, day: date,
                   service_type: str) -> tuple[dict, dict]:
    if getattr(profile, "latitude", None) is None or getattr(profile, "longitude", None) is None:
        return {}, _source("absent", "open-meteo", reason="no_hotel_coordinates")
    # Open-Meteo is called with timezone=auto: its hours are the hotel's local
    # wall time, stored with a UTC tzinfo (weather_ingestion). Compare alike.
    target = datetime.combine(day, time(SERVICE_HOUR.get(service_type, 20)), tzinfo=timezone.utc)
    try:
        rows = (await db.execute(
            select(WeatherForecast).where(
                WeatherForecast.tenant_id == profile.tenant_id,
                WeatherForecast.forecast_timestamp >= target - WEATHER_WINDOW,
                WeatherForecast.forecast_timestamp <= target + WEATHER_WINDOW,
            )
        )).scalars().all()
    except Exception:  # noqa: BLE001 — context never breaks a forecast
        logger.warning("forecast_context: weather lookup failed", exc_info=True)
        return {}, _source("absent", "open-meteo", reason="lookup_failed")

    def _gap(row: WeatherForecast) -> float:
        ts = row.forecast_timestamp
        ts = ts if ts.tzinfo else ts.replace(tzinfo=timezone.utc)
        return abs((ts - target).total_seconds())

    row = min(rows, key=_gap, default=None)
    if row is None:
        return {}, _source("absent", "open-meteo", reason="no_forecast_near_service")
    weather = {
        "condition": wmo_label(row.condition_code),
        "condition_code": row.condition_code,
        "temp": row.temperature_c,
        "precipitation_prob": row.precipitation_prob,
    }
    return ({k: v for k, v in weather.items() if v is not None},
            _source("ok", row.source or "open-meteo"))


async def _occupancy(db: AsyncSession, profile: RestaurantProfile,
                     day: date) -> tuple[Optional[float], dict]:
    try:
        log = (await db.execute(
            select(PMSSyncLog)
            .where(PMSSyncLog.tenant_id == profile.tenant_id, PMSSyncLog.sync_date == day)
            .order_by(PMSSyncLog.id.desc())
            .limit(1)
        )).scalars().first()
    except Exception:  # noqa: BLE001
        logger.warning("forecast_context: occupancy lookup failed", exc_info=True)
        return None, _source("absent", "pms", reason="lookup_failed")
    if log is None:
        return None, _source("absent", "pms", reason="not_synced_for_day")
    try:
        has_value = PMSDataStatus(log.occupancy_status).has_value
    except ValueError:
        has_value = False
    if not has_value or not log.rooms_available or log.rooms_sold is None:
        return None, _source("absent", "pms", reason=log.occupancy_status or "no_data")
    rate = round(log.rooms_sold / log.rooms_available, 3)
    return rate, _source(log.occupancy_status, "pms")


async def build(
    db: AsyncSession,
    profile: Optional[RestaurantProfile],
    target_date: date,
    service_type: str = "dinner",
) -> dict[str, Any]:
    """The stored context of one hotel, day and service. Every element is what
    a sync stored, or absent with the reason in ``context_sources``."""
    if profile is None:
        reason = _source("absent", None, reason="unknown_hotel")
        return {"weather": {}, "events": [], "occupancy": None,
                "context_sources": {"weather": reason, "events": reason, "occupancy": reason}}
    weather, weather_src = await _weather(db, profile, target_date, service_type)
    events = await enrich_events_context(db, profile, target_date)
    occupancy, occupancy_src = await _occupancy(db, profile, target_date)
    if getattr(profile, "latitude", None) is None:
        events_src = _source("absent", "predicthq", reason="no_hotel_coordinates")
    else:
        events_src = _source("ok", "predicthq", count=len(events))
    return {
        "weather": weather,
        "events": events,
        "occupancy": occupancy,
        "context_sources": {"weather": weather_src, "events": events_src,
                            "occupancy": occupancy_src},
    }


def merge(caller: Optional[Mapping[str, Any]], built: Mapping[str, Any]) -> dict[str, Any]:
    """A context a caller supplied (MCP, ``/predict``) stays authoritative for
    every key it actually fills; the stored context fills the rest. An empty
    value ("Unknown" weather, ``[]``, ``None``) is not a value."""
    out = dict(built)
    sources = dict(built.get("context_sources") or {})
    for key, value in (caller or {}).items():
        if key == "context_sources":
            continue
        if key == "weather" and isinstance(value, Mapping):
            condition = value.get("condition")
            if not condition or str(condition).lower() == "unknown":
                continue
        elif value is None or value == [] or value == {}:
            continue
        out[key] = value
        if key in sources:
            sources[key] = _source("caller", "caller")
    out["context_sources"] = sources
    return out


async def build_for_tenant(db: AsyncSession, tenant_id: str, target_date: date,
                           service_type: str = "dinner") -> dict[str, Any]:
    profile = (await db.execute(
        select(RestaurantProfile).where(RestaurantProfile.tenant_id == tenant_id)
    )).scalars().first()
    return await build(db, profile, target_date, service_type)

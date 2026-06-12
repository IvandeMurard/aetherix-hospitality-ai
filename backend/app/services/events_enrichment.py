"""Local-events context enrichment for the predictions route (HOS-225 / P3-11c).

Wires the ``local_events`` table (ingested by HOS-84, ranked by PredictHQ) into the
forecast context so the reasoning layer can cite *concrete* demand drivers
("Tech Conference 2026 (2.1 km)") instead of an opaque "events: []".

Why a dedicated module: the predictions route stays thin, and the query +
radius filtering is unit-testable in isolation.

Distance + nearest-first sorting are delegated to :func:`geo.enrich_events_with_distance`
(HOS-215) — this module only owns the DB query and the radius cut. Keeping
``latitude``/``longitude`` on each returned dict makes the downstream HOS-215
re-enrichment (inside ReasoningService) idempotent.
"""
from __future__ import annotations

import logging
from datetime import date, datetime, time, timezone
from typing import Any, Dict, List

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

from app.db.models import LocalEvent
from app.services.geo import enrich_events_with_distance

logger = logging.getLogger(__name__)

# Default catchment radius for "is this event near the hotel?" — a 5 km walk/short
# transit band is the operationally relevant zone for F&B spillover demand.
DEFAULT_RADIUS_KM = 5.0


async def enrich_events_context(
    db: AsyncSession,
    profile: Any,
    target_date: date,
    radius_km: float = DEFAULT_RADIUS_KM,
) -> List[Dict[str, Any]]:
    """Return local events active on ``target_date`` within ``radius_km`` of the hotel.

    The list is enriched with ``distance_km`` and sorted nearest-first (HOS-215 AC4),
    ready to drop into ``context['events']``.

    Behaviour (matches HOS-225 AC):
      - Active-on-date window: ``start_dt`` on/before the target day AND
        (``end_dt`` is open-ended OR on/after the target day).
      - Events without coordinates — or any event when the hotel itself has no
        coordinates — get no ``distance_km`` and are dropped by the radius cut
        (no crash).
      - Empty result on any error: enrichment must never break a forecast.
    """
    if profile is None:
        return []

    # Compare against UTC day bounds rather than ``::date`` casting so the same
    # query works on Postgres (prod) and SQLite (tests), and stays tz-safe against
    # the timezone-aware ``start_dt`` / ``end_dt`` columns.
    day_start = datetime.combine(target_date, time.min, tzinfo=timezone.utc)
    day_end = datetime.combine(target_date, time.max, tzinfo=timezone.utc)

    try:
        result = await db.execute(
            select(LocalEvent)
            .where(
                LocalEvent.tenant_id == profile.tenant_id,
                LocalEvent.start_dt <= day_end,
                (LocalEvent.end_dt.is_(None)) | (LocalEvent.end_dt >= day_start),
            )
            .order_by(LocalEvent.start_dt.asc())
        )
        rows = result.scalars().all()
    except Exception as exc:  # pragma: no cover - defensive; never break a forecast
        logger.warning("events enrichment query failed (non-blocking): %s", exc)
        return []

    mapped: List[Dict[str, Any]] = [
        {
            "name": row.title,
            "title": row.title,
            "category": row.category,
            "rank": row.rank,
            "phq_attendance": row.phq_attendance,
            # kept so ReasoningService's HOS-215 re-enrichment is idempotent
            "latitude": row.latitude,
            "longitude": row.longitude,
        }
        for row in rows
    ]

    # HOS-215: inject distance_km + sort nearest-first.
    enriched = enrich_events_with_distance(
        mapped,
        getattr(profile, "latitude", None),
        getattr(profile, "longitude", None),
    )

    # Radius cut — drop events with no computable distance (missing hotel/event
    # coords) and anything beyond the catchment band.
    within = [
        e
        for e in enriched
        if isinstance(e.get("distance_km"), (int, float)) and e["distance_km"] <= radius_km
    ]

    logger.debug(
        "events enrichment: tenant=%s date=%s -> %d/%d within %.1f km",
        profile.tenant_id, target_date, len(within), len(mapped), radius_km,
    )
    return within

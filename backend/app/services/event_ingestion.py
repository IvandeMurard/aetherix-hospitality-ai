"""EventIngestionService — HOS-84 Story 3.2.

Fetches upcoming local events from PredictHQ (within a configurable radius
around the property's GPS coordinates) and upserts normalized records into
the ``local_events`` table.

Design constraints followed:
- Fat Backend: no PredictHQ API calls from Next.js (architecture constraint).
- Tenacity retry: max 3 attempts, exponential back-off (SC #6).
- Idempotency: ON CONFLICT DO NOTHING on (tenant_id, event_id) (SC #7).
- Tenant isolation: every row carries tenant_id; RLS enforced at DB level (SC #5).
"""
from __future__ import annotations

import logging
import os
from datetime import date, datetime, timedelta, timezone
from typing import List, Optional

import httpx
from tenacity import (
    retry,
    stop_after_attempt,
    wait_exponential,
    retry_if_exception_type,
    before_sleep_log,
)
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import LocalEvent, RestaurantProfile
from app.schemas.events import EventRecord

logger = logging.getLogger(__name__)

# PredictHQ API base URL
_PHQ_BASE_URL = "https://api.predicthq.com/v1"

# Default search window and radius
_DEFAULT_RADIUS_KM = 5
_DEFAULT_DAYS_AHEAD = 30

# Categories relevant to F&B demand prediction
_DEFAULT_CATEGORIES = (
    "conferences,concerts,festivals,performing-arts,sports,"
    "expos,community,public-holidays"
)


class EventIngestionService:
    """Orchestrates fetching + normalizing + persisting PredictHQ event data."""

    def __init__(self, http_client: Optional[httpx.AsyncClient] = None) -> None:
        # Allow injection for testing
        self._client = http_client
        self._api_key: str = os.environ.get("PREDICTHQ_API_KEY", "")

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    async def sync_for_tenant(
        self,
        session: AsyncSession,
        profile: RestaurantProfile,
        radius_km: float = _DEFAULT_RADIUS_KM,
        days_ahead: int = _DEFAULT_DAYS_AHEAD,
    ) -> int:
        """Fetch and persist upcoming events for one property.

        Returns the number of rows upserted (new records only; duplicates
        are silently ignored).

        Raises ``ValueError`` if the property has no GPS coordinates.
        Raises ``RuntimeError`` if PREDICTHQ_API_KEY is not configured.
        """
        if profile.latitude is None or profile.longitude is None:
            raise ValueError(
                f"Property '{profile.tenant_id}' has no GPS coordinates — "
                "set latitude/longitude before syncing events."
            )

        if not self._api_key:
            raise RuntimeError(
                "PREDICTHQ_API_KEY is not set. "
                "Configure it in the environment before running event sync."
            )

        raw_events = await self._fetch_events(
            lat=profile.latitude,
            lng=profile.longitude,
            radius_km=radius_km,
            days_ahead=days_ahead,
        )
        records = self._normalize(raw_events)
        inserted = await self._upsert(session, profile.tenant_id, records)
        logger.info(
            "Event sync OK  tenant=%s  rows_new=%d  rows_total=%d",
            profile.tenant_id,
            inserted,
            len(records),
        )
        return inserted

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    @retry(
        retry=retry_if_exception_type((httpx.HTTPError, httpx.TimeoutException)),
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=10),
        before_sleep=before_sleep_log(logger, logging.WARNING),
        reraise=True,
    )
    async def _fetch_events(
        self,
        lat: float,
        lng: float,
        radius_km: float,
        days_ahead: int,
    ) -> List[dict]:
        """GET PredictHQ /v1/events with tenacity retry (SC #6).

        Handles pagination automatically and returns a flat list of raw
        event dicts across all pages.
        """
        today = date.today()
        date_from = today.isoformat()
        date_to = (today + timedelta(days=days_ahead)).isoformat()

        params = {
            "within": f"{radius_km}km@{lat},{lng}",
            "active.gte": date_from,
            "active.lte": date_to,
            "category": _DEFAULT_CATEGORIES,
            "limit": 100,
            "sort": "rank",
        }
        headers = {
            "Authorization": f"Bearer {self._api_key}",
            "Accept": "application/json",
        }

        all_results: List[dict] = []
        url = f"{_PHQ_BASE_URL}/events/"

        while url:
            if self._client is not None:
                resp = await self._client.get(url, params=params, headers=headers, timeout=15)
            else:
                async with httpx.AsyncClient() as client:
                    resp = await client.get(url, params=params, headers=headers, timeout=15)

            resp.raise_for_status()
            data = resp.json()

            all_results.extend(data.get("results", []))

            # Follow cursor-based pagination (PredictHQ uses `next` URL)
            next_url = data.get("next")
            if next_url:
                url = next_url
                params = {}  # next URL already encodes all params
            else:
                break

        logger.debug("PredictHQ returned %d raw events", len(all_results))
        return all_results

    @staticmethod
    def _normalize(raw_events: List[dict]) -> List[EventRecord]:
        """Map PredictHQ event dicts → list of EventRecord."""
        records: List[EventRecord] = []

        for ev in raw_events:
            # Parse start / end datetimes (PredictHQ uses ISO-8601)
            start_dt = _parse_phq_datetime(ev.get("start"))
            if start_dt is None:
                logger.warning("Skipping event with unparseable start: %s", ev.get("id"))
                continue

            end_dt = _parse_phq_datetime(ev.get("end"))

            # Extract centroid from geo.geometry.coordinates [lng, lat]
            lat: Optional[float] = None
            lng: Optional[float] = None
            geo = ev.get("geo") or {}
            geometry = geo.get("geometry") or {}
            coords = geometry.get("coordinates")
            if coords and len(coords) >= 2:
                lng, lat = coords[0], coords[1]

            records.append(
                EventRecord(
                    event_id=ev.get("id", ""),
                    title=ev.get("title", ""),
                    category=ev.get("category", "other"),
                    rank=ev.get("rank"),
                    local_rank=ev.get("local_rank"),
                    phq_attendance=ev.get("phq_attendance"),
                    start_dt=start_dt,
                    end_dt=end_dt,
                    latitude=lat,
                    longitude=lng,
                    raw_labels=ev.get("labels"),
                )
            )

        return records

    @staticmethod
    async def _upsert(
        session: AsyncSession,
        tenant_id: str,
        records: List[EventRecord],
    ) -> int:
        """Bulk-insert records; skip duplicates via ON CONFLICT DO NOTHING (SC #7).

        Uses the PostgreSQL dialect for production (Supabase) and falls back to
        the SQLite dialect when running tests against an in-memory database.

        Returns the count of newly inserted rows.
        """
        if not records:
            return 0

        now = datetime.now(tz=timezone.utc)
        values = [
            {
                "tenant_id": tenant_id,
                "event_id": r.event_id,
                "title": r.title,
                "category": r.category,
                "rank": r.rank,
                "local_rank": r.local_rank,
                "phq_attendance": r.phq_attendance,
                "start_dt": r.start_dt,
                "end_dt": r.end_dt,
                "latitude": r.latitude,
                "longitude": r.longitude,
                "raw_labels": r.raw_labels,
                "fetched_at": now,
                "created_at": now,
            }
            for r in records
        ]

        # Resolve dialect at runtime so the same service code works in tests
        # (SQLite) and production (PostgreSQL / Supabase).
        dialect_name: str = session.get_bind().dialect.name  # type: ignore[union-attr]

        if dialect_name == "sqlite":
            from sqlalchemy.dialects.sqlite import insert as _insert

            stmt = (
                _insert(LocalEvent)
                .values(values)
                .on_conflict_do_nothing()
            )
        else:
            # PostgreSQL (default / production)
            from sqlalchemy.dialects.postgresql import insert as _insert  # type: ignore[no-redef]

            stmt = (
                _insert(LocalEvent)
                .values(values)
                .on_conflict_do_nothing(
                    index_elements=["tenant_id", "event_id"]
                )
            )

        result = await session.execute(stmt)
        await session.commit()
        return result.rowcount if result.rowcount is not None else 0


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _parse_phq_datetime(value: Optional[str]) -> Optional[datetime]:
    """Parse a PredictHQ ISO-8601 datetime string → UTC-aware datetime."""
    if not value:
        return None
    try:
        dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt
    except (ValueError, AttributeError):
        return None

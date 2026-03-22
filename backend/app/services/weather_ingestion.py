"""WeatherIngestionService — HOS-83 Story 3.1.

Fetches hourly weather forecasts from Open-Meteo (free tier, no API key)
and upserts normalized records into the ``weather_forecasts`` table.

Design constraints followed:
- Fat Backend: no weather API calls from Next.js (architecture constraint).
- Tenacity retry: max 3 attempts, exponential back-off (SC #6).
- Idempotency: ON CONFLICT DO NOTHING on (tenant_id, property_id, forecast_timestamp) (SC #7).
- Tenant isolation: every row carries tenant_id; RLS enforced at DB level (SC #5).
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import List

import httpx
from tenacity import (
    retry,
    stop_after_attempt,
    wait_exponential,
    retry_if_exception_type,
    before_sleep_log,
)
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import WeatherForecast, RestaurantProfile
from app.schemas.weather import WeatherForecastRecord

logger = logging.getLogger(__name__)

# Open-Meteo endpoint — free tier, no API key required
_OPEN_METEO_URL = "https://api.open-meteo.com/v1/forecast"

# Variables requested from Open-Meteo
_HOURLY_VARS = "temperature_2m,precipitation_probability,weathercode,windspeed_10m"


class WeatherIngestionService:
    """Orchestrates fetching + normalizing + persisting weather data."""

    def __init__(self, http_client: httpx.AsyncClient | None = None) -> None:
        # Allow injection for testing
        self._client = http_client

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    async def sync_for_tenant(
        self,
        session: AsyncSession,
        profile: RestaurantProfile,
    ) -> int:
        """Fetch and persist 7-day hourly forecast for one property.

        Returns the number of rows upserted (new records only; duplicates
        are silently ignored).

        Raises ``ValueError`` if the property has no GPS coordinates.
        """
        if profile.latitude is None or profile.longitude is None:
            raise ValueError(
                f"Property '{profile.tenant_id}' has no GPS coordinates — "
                "set latitude/longitude before syncing weather."
            )

        raw = await self._fetch_forecast(profile.latitude, profile.longitude)
        records = self._normalize(raw)
        inserted = await self._upsert(session, profile.tenant_id, profile.tenant_id, records)
        logger.info(
            "Weather sync OK  tenant=%s  rows_new=%d  rows_total=%d",
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
    async def _fetch_forecast(self, lat: float, lng: float) -> dict:
        """GET Open-Meteo with tenacity retry (SC #6)."""
        params = {
            "latitude": lat,
            "longitude": lng,
            "hourly": _HOURLY_VARS,
            "forecast_days": 7,
            "timezone": "auto",
        }

        if self._client is not None:
            resp = await self._client.get(_OPEN_METEO_URL, params=params, timeout=15)
        else:
            async with httpx.AsyncClient() as client:
                resp = await client.get(_OPEN_METEO_URL, params=params, timeout=15)

        resp.raise_for_status()
        return resp.json()

    @staticmethod
    def _normalize(raw: dict) -> List[WeatherForecastRecord]:
        """Map Open-Meteo hourly arrays → list of WeatherForecastRecord."""
        hourly = raw.get("hourly", {})
        times: List[str] = hourly.get("time", [])
        temps: List[float | None] = hourly.get("temperature_2m", [None] * len(times))
        precip: List[int | None] = hourly.get("precipitation_probability", [None] * len(times))
        codes: List[int | None] = hourly.get("weathercode", [None] * len(times))
        winds: List[float | None] = hourly.get("windspeed_10m", [None] * len(times))

        records: List[WeatherForecastRecord] = []
        for i, ts_str in enumerate(times):
            # Open-Meteo returns naive ISO strings; treat as UTC
            try:
                ts = datetime.fromisoformat(ts_str).replace(tzinfo=timezone.utc)
            except ValueError:
                logger.warning("Skipping unparseable timestamp: %s", ts_str)
                continue

            records.append(
                WeatherForecastRecord(
                    condition_code=codes[i] if i < len(codes) else None,
                    temperature_c=temps[i] if i < len(temps) else None,
                    precipitation_prob=precip[i] if i < len(precip) else None,
                    wind_speed_kmh=winds[i] if i < len(winds) else None,
                    forecast_timestamp=ts,
                )
            )
        return records

    @staticmethod
    async def _upsert(
        session: AsyncSession,
        tenant_id: str,
        property_id: str,
        records: List[WeatherForecastRecord],
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
                "property_id": property_id,
                "condition_code": r.condition_code,
                "temperature_c": r.temperature_c,
                "precipitation_prob": r.precipitation_prob,
                "wind_speed_kmh": r.wind_speed_kmh,
                "forecast_timestamp": r.forecast_timestamp,
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
                _insert(WeatherForecast)
                .values(values)
                .on_conflict_do_nothing()
            )
        else:
            # PostgreSQL (default / production)
            from sqlalchemy.dialects.postgresql import insert as _insert  # type: ignore[no-redef]

            stmt = (
                _insert(WeatherForecast)
                .values(values)
                .on_conflict_do_nothing(
                    index_elements=["tenant_id", "property_id", "forecast_timestamp"]
                )
            )

        result = await session.execute(stmt)
        await session.commit()
        # rowcount is the number of rows actually inserted (duplicates excluded)
        return result.rowcount if result.rowcount is not None else 0

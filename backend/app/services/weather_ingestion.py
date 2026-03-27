"""WeatherIngestionService — Story 3.1: Ingest Localized Weather Data (HOS-83).

Responsibilities:
- Fetch 7-day hourly forecasts from Open-Meteo (free, no API key).
- Normalize raw JSON into WeatherForecast ORM rows.
- Upsert into Supabase via SQLAlchemy (idempotent on tenant_id + property_id + forecast_timestamp).
- Retry failed HTTP calls with exponential backoff via tenacity (max 3 attempts).
- Log failures; never crash the background task or affect other tenants.

Architecture constraints:
- Fat Backend: all HTTP calls stay in this service, not in routes.
- No side effects on normalise() -- pure function, testable in isolation.
- Tenacity retry: max 3 attempts, exponential back-off (SC #6).
- Idempotency: ON CONFLICT DO NOTHING on (tenant_id, property_id, forecast_timestamp) (SC #7).
- Tenant isolation: every row carries tenant_id; RLS enforced at DB level (SC #5).
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any

import httpx
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession
from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

from app.db.models import RestaurantProfile, WeatherForecast
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

# Hourly variables requested
# Variables requested from Open-Meteo
_HOURLY_VARS = "temperature_2m,precipitation_probability,weathercode,windspeed_10m"


class WeatherIngestionService:
    """Fetches, normalises, and persists weather forecast data for one property."""

    def __init__(self, http_client: httpx.AsyncClient | None = None) -> None:
        # Allow injection of a mock client in tests
        self._client = http_client

    # ── Public API ─────────────────────────────────────────────────────────

    async def sync_property(self, property_id: str, db: AsyncSession) -> int:
        """Fetch and upsert weather forecasts for a single property.

        Args:
            property_id: The tenant_id of the RestaurantProfile to sync.
            db: Async SQLAlchemy session (caller owns commit/rollback).

        Returns:
            Number of rows upserted.

        Raises:
            ValueError: If the property has no GPS coordinates configured.
        """
        profile = await self._get_profile(property_id, db)

        if profile.latitude is None or profile.longitude is None:
            raise ValueError(
                f"Property '{property_id}' has no GPS coordinates configured. "
                "Set latitude and longitude in the restaurant profile."
            )

        raw = await self._fetch_forecast(profile.latitude, profile.longitude)
        rows = self.normalise(raw, tenant_id=profile.tenant_id, property_id=property_id)
        count = await self._upsert(rows, db)
        logger.info("Weather sync OK — property=%s rows=%d", property_id, count)
        return count

    # ── Normalisation (pure, fully testable) ───────────────────────────────

    @staticmethod
    def normalise(
        raw: dict[str, Any],
        *,
        tenant_id: str,
        property_id: str,
    ) -> list[WeatherForecast]:
        """Transform Open-Meteo JSON into WeatherForecast ORM objects.

        The function is deterministic and side-effect-free — safe to unit test
        without a database.
        """
        hourly = raw.get("hourly", {})
        timestamps: list[str] = hourly.get("time", [])
        temperatures: list[float | None] = hourly.get("temperature_2m", [])
        precip_probs: list[int | None] = hourly.get("precipitation_probability", [])
        weathercodes: list[int | None] = hourly.get("weathercode", [])
        windspeeds: list[float | None] = hourly.get("windspeed_10m", [])

        fetched_at = datetime.now(tz=timezone.utc)
        rows: list[WeatherForecast] = []

        for i, ts_str in enumerate(timestamps):
            try:
                forecast_ts = datetime.fromisoformat(ts_str).replace(tzinfo=timezone.utc)
            except ValueError:
                logger.warning("Skipping unparseable timestamp: %s", ts_str)
                continue

            rows.append(
                WeatherForecast(
                    tenant_id=tenant_id,
                    property_id=property_id,
                    forecast_timestamp=forecast_ts,
                    condition_code=_safe_get(weathercodes, i),
                    temperature_c=_safe_get(temperatures, i),
                    precipitation_prob=_safe_get(precip_probs, i),
                    wind_speed_kmh=_safe_get(windspeeds, i),
                    source="open-meteo",
                    fetched_at=fetched_at,
                )
            )

        return rows

    # ── Private helpers ────────────────────────────────────────────────────

    async def _get_profile(self, property_id: str, db: AsyncSession) -> RestaurantProfile:
        from sqlalchemy.future import select

        result = await db.execute(
            select(RestaurantProfile).where(RestaurantProfile.tenant_id == property_id)
        )
        profile = result.scalars().first()
        if not profile:
            raise ValueError(f"No restaurant profile found for property_id='{property_id}'")
        return profile
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
        wait=wait_exponential(multiplier=1, min=2, max=16),
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

    async def _upsert(self, rows: list[WeatherForecast], db: AsyncSession) -> int:
        """Upsert rows using PostgreSQL ON CONFLICT DO UPDATE.

        Idempotent: re-running for the same property + time window overwrites
        with fresh data instead of creating duplicates.
        """
        if not rows:
            return 0

        stmt = text(
            """
            INSERT INTO weather_forecasts (
                id, tenant_id, property_id, forecast_timestamp,
                condition_code, temperature_c, precipitation_prob,
                wind_speed_kmh, source, fetched_at, created_at
            )
            VALUES (
                gen_random_uuid(), :tenant_id, :property_id, :forecast_timestamp,
                :condition_code, :temperature_c, :precipitation_prob,
                :wind_speed_kmh, :source, :fetched_at, NOW()
            )
            ON CONFLICT (tenant_id, property_id, forecast_timestamp)
            DO UPDATE SET
                condition_code     = EXCLUDED.condition_code,
                temperature_c      = EXCLUDED.temperature_c,
                precipitation_prob = EXCLUDED.precipitation_prob,
                wind_speed_kmh     = EXCLUDED.wind_speed_kmh,
                source             = EXCLUDED.source,
                fetched_at         = EXCLUDED.fetched_at
            """
        )

        values = [
            {
                "tenant_id": row.tenant_id,
                "property_id": row.property_id,
                "forecast_timestamp": row.forecast_timestamp,
                "condition_code": row.condition_code,
                "temperature_c": float(row.temperature_c) if row.temperature_c is not None else None,
                "precipitation_prob": row.precipitation_prob,
                "wind_speed_kmh": float(row.wind_speed_kmh) if row.wind_speed_kmh is not None else None,
                "source": row.source,
                "fetched_at": row.fetched_at,
            }
            for row in rows
        ]

        await db.execute(stmt, values)
        await db.commit()
        return len(rows)


# ── Utilities ──────────────────────────────────────────────────────────────

def _safe_get(lst: list, index: int) -> Any:
    """Return lst[index] or None if out of bounds."""
    try:
        return lst[index]
    except IndexError:
        return None
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

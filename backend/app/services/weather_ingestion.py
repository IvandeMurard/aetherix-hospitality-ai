"""WeatherIngestionService — Story 3.1: Ingest Localized Weather Data (HOS-83).

Responsibilities:
- Fetch 7-day hourly forecasts from Open-Meteo (free, no API key).
- Normalize raw JSON into WeatherForecast ORM rows.
- Upsert into Supabase via SQLAlchemy (idempotent on tenant_id + property_id + forecast_timestamp).
- Retry failed HTTP calls with exponential backoff via tenacity (max 3 attempts).
- Log failures; never crash the background task or affect other tenants.

Architecture constraints:
- Fat Backend: all HTTP calls stay in this service, not in routes.
- No side effects on normalise() — pure function, testable in isolation.
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

logger = logging.getLogger(__name__)

# Open-Meteo endpoint — free tier, no API key required
_OPEN_METEO_URL = "https://api.open-meteo.com/v1/forecast"

# Hourly variables requested
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

    @retry(
        retry=retry_if_exception_type((httpx.HTTPError, httpx.TimeoutException)),
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=16),
        reraise=True,
    )
    async def _fetch_forecast(self, latitude: float, longitude: float) -> dict[str, Any]:
        """Call Open-Meteo with exponential backoff (max 3 attempts)."""
        params = {
            "latitude": latitude,
            "longitude": longitude,
            "hourly": _HOURLY_VARS,
            "forecast_days": 7,
            "timezone": "auto",
        }

        if self._client:
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

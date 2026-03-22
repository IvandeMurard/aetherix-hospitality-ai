"""Pydantic schemas for weather ingestion (HOS-83 Story 3.1).

All output models use camelCase aliases per architecture constraint.
"""
from __future__ import annotations

from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, Field


def _to_camel(s: str) -> str:
    parts = s.split("_")
    return parts[0] + "".join(p.capitalize() for p in parts[1:])


class _CamelModel(BaseModel):
    model_config = {"populate_by_name": True, "alias_generator": _to_camel}


# ---------------------------------------------------------------------------
# Inbound (normalized from Open-Meteo response)
# ---------------------------------------------------------------------------

class WeatherForecastRecord(_CamelModel):
    """One hourly slot ingested from Open-Meteo."""

    condition_code: Optional[int] = Field(None, description="WMO weather interpretation code")
    temperature_c: Optional[float] = Field(None, description="Air temperature at 2 m (°C)")
    precipitation_prob: Optional[int] = Field(
        None, ge=0, le=100, description="Precipitation probability (0-100 %)"
    )
    wind_speed_kmh: Optional[float] = Field(None, description="Wind speed at 10 m (km/h)")
    forecast_timestamp: datetime = Field(..., description="ISO-8601 UTC timestamp of the forecast slot")


# ---------------------------------------------------------------------------
# API request / response
# ---------------------------------------------------------------------------

class WeatherSyncRequest(_CamelModel):
    """Body for POST /api/v1/weather/sync (all fields optional — resolved from profile)."""

    tenant_id: Optional[str] = None
    force: bool = Field(False, description="If true, re-fetch even if data exists for the window")


class WeatherSyncResponse(_CamelModel):
    """202 Accepted response for POST /api/v1/weather/sync."""

    message: str
    tenant_id: str
    property_id: str
    latitude: float
    longitude: float
    records_queued: int = Field(..., description="Number of hourly slots scheduled for upsert")


class WeatherForecastOut(_CamelModel):
    """Serialized WeatherForecast ORM row returned by read endpoints."""

    id: int
    tenant_id: str
    property_id: str
    condition_code: Optional[int]
    temperature_c: Optional[float]
    precipitation_prob: Optional[int]
    wind_speed_kmh: Optional[float]
    forecast_timestamp: datetime
    fetched_at: Optional[datetime]

    model_config = {"from_attributes": True, "populate_by_name": True, "alias_generator": _to_camel}

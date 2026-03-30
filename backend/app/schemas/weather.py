"""Pydantic schemas for weather ingestion (HOS-83 Story 3.1).

All output models use camelCase aliases per architecture constraint.
RFC 7807 error format is handled at the route layer.
"""
from __future__ import annotations

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field
from pydantic.alias_generators import to_camel


def _cfg() -> ConfigDict:
    return ConfigDict(alias_generator=to_camel, populate_by_name=True)


# ---------------------------------------------------------------------------
# Internal record (normalized from Open-Meteo response)
# ---------------------------------------------------------------------------

class WeatherForecastRecord(BaseModel):
    """One hourly slot ingested from Open-Meteo."""
    model_config = _cfg()

    condition_code: Optional[int] = Field(None, description="WMO weather interpretation code")
    temperature_c: Optional[float] = Field(None, description="Air temperature at 2 m (deg C)")
    precipitation_prob: Optional[int] = Field(None, ge=0, le=100)
    wind_speed_kmh: Optional[float] = Field(None, description="Wind speed at 10 m (km/h)")
    forecast_timestamp: datetime = Field(..., description="ISO-8601 UTC timestamp")


# ---------------------------------------------------------------------------
# API request / response
# ---------------------------------------------------------------------------

class WeatherSyncRequest(BaseModel):
    """Body for POST /api/v1/weather/sync (all fields optional)."""
    model_config = _cfg()

    tenant_id: Optional[str] = Field(
        default=None,
        description="Target property (tenant_id). Defaults to the authenticated user's property.",
    )


class WeatherSyncResponse(BaseModel):
    """202 Accepted response body for POST /api/v1/weather/sync."""
    model_config = _cfg()

    message: str
    property_id: str
    triggered_by: Optional[str] = None


# ---------------------------------------------------------------------------
# Read schema (for future GET endpoints)
# ---------------------------------------------------------------------------

class WeatherForecastOut(BaseModel):
    """Serialized WeatherForecast ORM row returned by read endpoints."""
    model_config = ConfigDict(
        from_attributes=True,
        alias_generator=to_camel,
        populate_by_name=True,
    )

    id: int
    tenant_id: str
    property_id: str
    condition_code: Optional[int] = None
    temperature_c: Optional[float] = None
    precipitation_prob: Optional[int] = None
    wind_speed_kmh: Optional[float] = None
    forecast_timestamp: datetime
    fetched_at: Optional[datetime] = None

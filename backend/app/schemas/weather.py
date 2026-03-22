"""Pydantic schemas for weather forecast data.

Story 3.1: Ingest Localized Weather Data (HOS-83).
- camelCase output via alias_generator (architecture constraint).
- RFC 7807 error format is handled at the route layer.
"""
from __future__ import annotations

from datetime import datetime
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field
from pydantic.alias_generators import to_camel


class WeatherForecastBase(BaseModel):
    """Fields shared across request/response schemas."""
    model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True)

    tenant_id: str
    property_id: str
    forecast_timestamp: datetime
    condition_code: Optional[int] = None
    temperature_c: Optional[float] = None
    precipitation_prob: Optional[int] = Field(default=None, ge=0, le=100)
    wind_speed_kmh: Optional[float] = None
    source: str = "open-meteo"


class WeatherForecastRead(WeatherForecastBase):
    """Response schema — includes DB-generated fields."""
    id: UUID
    fetched_at: datetime
    created_at: datetime


class WeatherSyncRequest(BaseModel):
    """Body for POST /api/v1/weather/sync (optional — defaults to current user's property)."""
    model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True)

    property_id: Optional[str] = Field(
        default=None,
        description="Target property (tenant_id). Defaults to the authenticated user's property.",
    )


class WeatherSyncResponse(BaseModel):
    """202 Accepted response body for POST /api/v1/weather/sync."""
    model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True)

    message: str
    property_id: str
    triggered_by: Optional[str] = None

"""Pydantic schemas for PredictHQ event ingestion (HOS-84 Story 3.2).

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
# Inbound (normalized from PredictHQ API response)
# ---------------------------------------------------------------------------

class EventRecord(_CamelModel):
    """One event ingested from PredictHQ /v2/events."""

    event_id: str = Field(..., description="Stable PredictHQ event UUID")
    title: str = Field(..., description="Event title")
    category: str = Field(..., description="PredictHQ category slug (e.g. 'conferences')")
    rank: Optional[int] = Field(None, ge=0, le=100, description="PredictHQ rank score")
    local_rank: Optional[int] = Field(None, ge=0, le=100, description="Local rank within radius")
    phq_attendance: Optional[int] = Field(None, description="Predicted attendance")
    start_dt: datetime = Field(..., description="Event start (UTC)")
    end_dt: Optional[datetime] = Field(None, description="Event end (UTC)")
    latitude: Optional[float] = Field(None, description="Event centroid latitude")
    longitude: Optional[float] = Field(None, description="Event centroid longitude")
    raw_labels: Optional[List[str]] = Field(None, description="PredictHQ label tags")


# ---------------------------------------------------------------------------
# API request / response
# ---------------------------------------------------------------------------

class EventSyncRequest(_CamelModel):
    """Body for POST /api/v1/events/sync (all fields optional)."""

    tenant_id: Optional[str] = None
    radius_km: float = Field(5.0, gt=0, le=50, description="Search radius in km (default 5 km)")
    days_ahead: int = Field(30, gt=0, le=90, description="Number of days ahead to fetch (default 30)")


class EventSyncResponse(_CamelModel):
    """202 Accepted response for POST /api/v1/events/sync."""

    message: str
    tenant_id: str
    latitude: float
    longitude: float
    radius_km: float
    records_queued: int = Field(..., description="Number of events scheduled for upsert")


class LocalEventOut(_CamelModel):
    """Serialized LocalEvent ORM row returned by read endpoints."""

    id: int
    tenant_id: str
    event_id: str
    title: str
    category: str
    rank: Optional[int]
    local_rank: Optional[int]
    phq_attendance: Optional[int]
    start_dt: datetime
    end_dt: Optional[datetime]
    latitude: Optional[float]
    longitude: Optional[float]
    raw_labels: Optional[List[str]]
    fetched_at: Optional[datetime]

    model_config = {"from_attributes": True, "populate_by_name": True, "alias_generator": _to_camel}

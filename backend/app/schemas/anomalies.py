"""Pydantic schemas for demand anomaly API responses.

Architecture constraints:
- camelCase output via alias_generator for all API responses.
- snake_case internally.
- RFC 7807 errors are handled at the route/handler level.
[Source: architecture.md#Naming-Patterns]
"""
from __future__ import annotations

import uuid
from datetime import datetime
from decimal import Decimal
from typing import Any, List, Optional

from pydantic import BaseModel, ConfigDict, Field
from pydantic.alias_generators import to_camel


class AnomalyBase(BaseModel):
    """Shared fields for anomaly create / read schemas."""

    model_config = ConfigDict(
        alias_generator=to_camel,
        populate_by_name=True,
    )

    tenant_id: uuid.UUID
    property_id: uuid.UUID
    window_start: datetime
    window_end: datetime
    expected_demand: Decimal
    baseline_demand: Decimal
    deviation_pct: Decimal
    direction: str  # 'surge' | 'lull'
    triggering_factors: List[Any] = Field(default_factory=list)
    status: str = "detected"


class DemandAnomalyCreate(AnomalyBase):
    """Schema used internally when creating a new anomaly record."""
    pass


class DemandAnomalyRead(AnomalyBase):
    """Schema returned by GET /api/v1/anomalies."""

    id: uuid.UUID
    detected_at: datetime
    roi_revenue_opp: Optional[Decimal] = None
    roi_labor_cost: Optional[Decimal] = None
    roi_net: Optional[Decimal] = None
    recommendation_text: Optional[str] = None

    model_config = ConfigDict(
        alias_generator=to_camel,
        populate_by_name=True,
        from_attributes=True,
    )


class AnomalyScanResponse(BaseModel):
    """Response body for POST /api/v1/anomalies/scan (202 Accepted)."""

    model_config = ConfigDict(
        alias_generator=to_camel,
        populate_by_name=True,
    )

    message: str = "Anomaly scan triggered"
    property_id: Optional[uuid.UUID] = None
    triggered_by: Optional[str] = None


class AnomalyListResponse(BaseModel):
    """Paginated wrapper for GET /api/v1/anomalies."""

    model_config = ConfigDict(
        alias_generator=to_camel,
        populate_by_name=True,
    )

    items: List[DemandAnomalyRead]
    total: int
    page: int
    page_size: int

"""Pydantic v2 schemas for staffing recommendations.

Follows camelCase JSON output convention (alias_generator = to_camel),
consistent with app/schemas/anomalies.py.

Story 3.3c (HOS-23): Format Staffing Recommendations for Dispatch.

Architecture constraints:
- camelCase output via alias_generator for all API responses.
- snake_case internally.
- RFC 7807 errors are handled at the route/handler level.
[Source: architecture.md#Naming-Patterns, story 3.3c HOS-23]
"""
from __future__ import annotations

import uuid
from datetime import datetime
from decimal import Decimal
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field
from pydantic.alias_generators import to_camel


# ---------------------------------------------------------------------------
# Base
# ---------------------------------------------------------------------------


class _CamelModel(BaseModel):
    """Base model with camelCase JSON serialisation for all response schemas."""

    model_config = ConfigDict(
        alias_generator=to_camel,
        populate_by_name=True,
        from_attributes=True,
    )


# ---------------------------------------------------------------------------
# Request / trigger schemas
# ---------------------------------------------------------------------------


class FormatTriggerRequest(_CamelModel):
    """Optional body for POST /api/v1/anomalies/format.

    If *property_id* is provided only that property is processed;
    otherwise the formatter runs across all tenants.
    """

    property_id: Optional[uuid.UUID] = Field(
        default=None,
        description="Restrict formatting run to a specific property UUID.",
    )


# ---------------------------------------------------------------------------
# Response schemas
# ---------------------------------------------------------------------------


class StaffingRecommendationRead(_CamelModel):
    """Full read representation of a StaffingRecommendation database row."""

    id: uuid.UUID
    tenant_id: uuid.UUID
    property_id: uuid.UUID
    anomaly_id: uuid.UUID
    message_text: str
    triggering_factor: Optional[str] = None
    recommended_headcount: Optional[int] = None
    window_start: datetime
    window_end: datetime
    roi_net: Optional[Decimal] = None
    roi_labor_cost: Optional[Decimal] = None
    status: str
    created_at: datetime
    updated_at: datetime


class FormatTriggerResponse(_CamelModel):
    """Immediate 202 Accepted response for POST /api/v1/anomalies/format."""

    accepted: bool = True
    message: str = "Recommendation formatting job accepted."
    property_id: Optional[uuid.UUID] = None
    recommendations_created: Optional[int] = None

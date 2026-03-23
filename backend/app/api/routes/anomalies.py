"""API routes for demand anomaly detection.

Endpoints:
  POST /api/v1/anomalies/scan  — trigger immediate scan for the authenticated
                                  user's property; returns 202 Accepted.
  GET  /api/v1/anomalies        — paginated list of anomalies for the
                                  authenticated user's property.

Architecture constraints:
- Routes contain NO business logic — all logic lives in app/services/.
- POST returns 202 immediately; work runs as BackgroundTask.
- All HTTPExceptions use RFC 7807 Problem Details (registered in main.py).
- camelCase JSON output via Pydantic alias generator.
[Source: architecture.md#Architectural-Boundaries, story 3.3a Task 5]
"""
from __future__ import annotations

import uuid
from typing import Any, Dict, List

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import get_current_user
from app.db.session import get_db
from app.schemas.anomalies import AnomalyListResponse, AnomalyScanResponse, DemandAnomalyRead
from app.services.anomaly_detection import AnomalyDetectionService

router = APIRouter(prefix="/anomalies", tags=["anomalies"])

_service = AnomalyDetectionService()


# ---------------------------------------------------------------------------
# POST /api/v1/anomalies/scan
# ---------------------------------------------------------------------------
@router.post(
    "/scan",
    status_code=202,
    response_model=AnomalyScanResponse,
    summary="Trigger an immediate anomaly scan for the current user's property",
)
async def trigger_anomaly_scan(
    background_tasks: BackgroundTasks,
    current_user: Dict[str, Any] = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> AnomalyScanResponse:
    """Immediately queue an anomaly detection scan for the authenticated user.

    Returns 202 Accepted; the scan runs asynchronously as a BackgroundTask.
    """
    # Resolve property and tenant for the authenticated user
    property_id, tenant_id = await _resolve_property_for_user(db, current_user)

    background_tasks.add_task(
        _run_scan_background,
        property_id=property_id,
        tenant_id=tenant_id,
    )

    return AnomalyScanResponse(
        message="Anomaly scan triggered",
        property_id=property_id,
        triggered_by=current_user.get("email"),
    )


async def _run_scan_background(
    property_id: uuid.UUID,
    tenant_id: uuid.UUID,
) -> None:
    """Background task: open a new DB session and run the scan."""
    from app.db.session import AsyncSessionLocal

    async with AsyncSessionLocal() as session:
        await _service.detect_for_property(
            session,
            property_id=property_id,
            tenant_id=tenant_id,
        )


# ---------------------------------------------------------------------------
# GET /api/v1/anomalies
# ---------------------------------------------------------------------------
@router.get(
    "",
    response_model=AnomalyListResponse,
    summary="List anomalies for the current user's property",
)
async def list_anomalies(
    page: int = Query(1, ge=1, description="Page number (1-indexed)"),
    page_size: int = Query(20, ge=1, le=100, description="Items per page"),
    current_user: Dict[str, Any] = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> AnomalyListResponse:
    """Return a paginated list of anomalies ordered by window_start descending."""
    property_id, _ = await _resolve_property_for_user(db, current_user)

    offset = (page - 1) * page_size

    count_result = await db.execute(
        text(
            "SELECT COUNT(*) FROM demand_anomalies WHERE property_id = :property_id"
        ),
        {"property_id": str(property_id)},
    )
    total = count_result.scalar() or 0

    rows_result = await db.execute(
        text(
            """
            SELECT id, tenant_id, property_id, window_start, window_end,
                   expected_demand, baseline_demand, deviation_pct,
                   direction, triggering_factors, status, detected_at,
                   roi_revenue_opp, roi_labor_cost, roi_net, recommendation_text
            FROM demand_anomalies
            WHERE property_id = :property_id
            ORDER BY window_start DESC
            LIMIT :limit OFFSET :offset
            """
        ),
        {"property_id": str(property_id), "limit": page_size, "offset": offset},
    )
    rows = rows_result.fetchall()

    items: List[DemandAnomalyRead] = []
    for row in rows:
        items.append(
            DemandAnomalyRead(
                id=row[0],
                tenant_id=row[1],
                property_id=row[2],
                window_start=row[3],
                window_end=row[4],
                expected_demand=row[5],
                baseline_demand=row[6],
                deviation_pct=row[7],
                direction=row[8],
                triggering_factors=row[9] or [],
                status=row[10],
                detected_at=row[11],
                roi_revenue_opp=row[12],
                roi_labor_cost=row[13],
                roi_net=row[14],
                recommendation_text=row[15],
            )
        )

    return AnomalyListResponse(
        items=items,
        total=total,
        page=page,
        page_size=page_size,
    )


# ---------------------------------------------------------------------------
# Helper
# ---------------------------------------------------------------------------
async def _resolve_property_for_user(
    db: AsyncSession,
    current_user: Dict[str, Any],
) -> tuple[uuid.UUID, uuid.UUID]:
    """Resolve (property_id, tenant_id) for the authenticated user.

    Raises HTTPException 404 (RFC 7807) if no property is linked.
    """
    user_id = current_user.get("id")
    result = await db.execute(
        text(
            """
            SELECT id, tenant_id
            FROM properties
            WHERE owner_id = :user_id
              AND is_active = TRUE
            LIMIT 1
            """
        ),
        {"user_id": str(user_id)},
    )
    row = result.fetchone()
    if not row:
        raise HTTPException(
            status_code=404,
            detail="No active property linked to the authenticated user.",
        )
    return uuid.UUID(str(row[0])), uuid.UUID(str(row[1]))

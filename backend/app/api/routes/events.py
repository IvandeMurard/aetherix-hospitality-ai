"""Events sync endpoint — HOS-84 Story 3.2.

POST /api/v1/events/sync
  → 202 Accepted immediately (BackgroundTasks pattern)
  → Background task calls EventIngestionService.sync_for_tenant

Architecture constraints:
- Fat Backend: no PredictHQ calls from Next.js.
- RFC 7807 error format via problem_details_handler (registered in main.py).
- camelCase output via Pydantic alias generator on response model.
"""
from __future__ import annotations

from typing import Any, Dict

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

from app.core.security import get_current_user
from app.db.models import RestaurantProfile
from app.db.session import AsyncSessionLocal, get_db
from app.schemas.events import EventSyncRequest, EventSyncResponse
from app.services.event_ingestion import EventIngestionService

router = APIRouter(prefix="/events", tags=["events"])


async def _background_sync(tenant_id: str, radius_km: float, days_ahead: int) -> None:
    """Run event sync in a fire-and-forget background task."""
    service = EventIngestionService()
    async with AsyncSessionLocal() as session:
        result = await session.execute(
            select(RestaurantProfile).where(RestaurantProfile.tenant_id == tenant_id)
        )
        profile = result.scalars().first()
        if profile is None:
            return
        try:
            await service.sync_for_tenant(session, profile, radius_km=radius_km, days_ahead=days_ahead)
        except Exception:  # noqa: BLE001
            # Logged inside service; do not propagate out of background task
            pass


@router.post(
    "/sync",
    status_code=status.HTTP_202_ACCEPTED,
    response_model=EventSyncResponse,
    summary="Trigger PredictHQ event sync for the current tenant",
)
async def trigger_event_sync(
    background_tasks: BackgroundTasks,
    body: EventSyncRequest = EventSyncRequest(),
    current_user: Dict[str, Any] = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> EventSyncResponse:
    """
    Enqueues a background PredictHQ event ingestion job for the authenticated
    user's property.

    Returns **202 Accepted** immediately; ingestion runs asynchronously.
    Events within ``radius_km`` of the property GPS (default 5 km) and
    starting within the next ``days_ahead`` days (default 30) are fetched.
    """
    result = await db.execute(
        select(RestaurantProfile).where(
            RestaurantProfile.owner_id == current_user["id"]
            if not body.tenant_id
            else RestaurantProfile.tenant_id == body.tenant_id
        )
    )
    profile = result.scalars().first()

    if profile is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No restaurant profile found for this user.",
        )

    if profile.latitude is None or profile.longitude is None:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=(
                f"Property '{profile.tenant_id}' has no GPS coordinates. "
                "Set latitude and longitude before syncing events."
            ),
        )

    background_tasks.add_task(
        _background_sync,
        profile.tenant_id,
        body.radius_km,
        body.days_ahead,
    )

    return EventSyncResponse(
        message="Event sync triggered — running in background.",
        tenant_id=profile.tenant_id,
        latitude=profile.latitude,
        longitude=profile.longitude,
        radius_km=body.radius_km,
        records_queued=0,  # Unknown until background task completes
    )

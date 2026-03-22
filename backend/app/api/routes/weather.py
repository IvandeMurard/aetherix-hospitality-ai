"""Weather API routes — Story 3.1: Ingest Localized Weather Data (HOS-83).

Endpoints:
    POST /api/v1/weather/sync  → 202 Accepted (triggers background sync)

Architecture constraints:
- Returns 202 immediately; actual work runs in BackgroundTasks (Fat Backend).
- All exceptions formatted as RFC 7807 Problem Details (registered in main.py).
- camelCase output via Pydantic alias_generator on response schemas.
"""
from __future__ import annotations

from typing import Any, Dict

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

from app.core.security import get_current_user
from app.db.models import RestaurantProfile
from app.db.session import get_db
from app.schemas.weather import WeatherSyncRequest, WeatherSyncResponse
from app.services.weather_ingestion import WeatherIngestionService

router = APIRouter(prefix="/weather", tags=["weather"])

_service = WeatherIngestionService()


@router.post(
    "/sync",
    status_code=202,
    response_model=WeatherSyncResponse,
    summary="Trigger weather forecast sync for a property",
    responses={
        202: {"description": "Sync accepted and running in background"},
        404: {"description": "No property linked to this user"},
        422: {"description": "Property has no GPS coordinates configured"},
    },
)
async def trigger_weather_sync(
    body: WeatherSyncRequest = WeatherSyncRequest(),
    background_tasks: BackgroundTasks = BackgroundTasks(),
    current_user: Dict[str, Any] = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> WeatherSyncResponse:
    """Trigger a weather forecast ingestion for the authenticated user's property.

    Returns **202 Accepted** immediately.  The actual HTTP call to Open-Meteo
    and database upsert run asynchronously via BackgroundTasks so the caller
    is never blocked.

    If `propertyId` is omitted in the body, the user's default property is used.
    """
    # Resolve the target property
    property_id = body.property_id

    if property_id is None:
        # Default: the property owned by the current user
        result = await db.execute(
            select(RestaurantProfile).where(
                RestaurantProfile.owner_id == current_user["id"]
            )
        )
        profile = result.scalars().first()
        if not profile:
            raise HTTPException(
                status_code=404,
                detail="No restaurant profile linked to this user.",
            )
        property_id = profile.tenant_id
    else:
        # Verify the property exists
        result = await db.execute(
            select(RestaurantProfile).where(
                RestaurantProfile.tenant_id == property_id
            )
        )
        if not result.scalars().first():
            raise HTTPException(
                status_code=404,
                detail=f"Property '{property_id}' not found.",
            )

    # Enqueue background task — returns 202 immediately
    background_tasks.add_task(_run_sync, property_id)

    return WeatherSyncResponse(
        message="Weather sync triggered successfully in background",
        property_id=property_id,
        triggered_by=current_user.get("email"),
    )


async def _run_sync(property_id: str) -> None:
    """Background coroutine: open a fresh DB session and run the sync."""
    from app.db.session import AsyncSessionLocal

    try:
        async with AsyncSessionLocal() as db:
            await _service.sync_property(property_id, db)
    except Exception as exc:  # noqa: BLE001
        import logging
        logging.getLogger(__name__).error(
            "Background weather sync failed — property=%s error=%s",
            property_id,
            exc,
            exc_info=True,
        )

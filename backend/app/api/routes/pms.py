import logging
import os
from datetime import date
from typing import Any, Dict, Optional

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

from app.core.security import get_current_user
from app.db.models import RestaurantProfile
from app.db.session import get_db
from app.services.apaleo_adapter import ApaleoSyncError, ApaleoPMSAdapter
from app.services.apaleo_mcp_adapter import ApaleoMCPAdapter
from app.services.pms_sync import MockPMSAdapter, PMSSyncService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/pms", tags=["pms"])


async def _sync_task(service: PMSSyncService, property_id: str, sync_date: date) -> None:
    """Background task wrapper that catches ApaleoSyncError and logs without DB write."""
    try:
        await service.sync_daily_data(property_id, sync_date)
    except ApaleoSyncError as exc:
        logger.error(
            "PMS sync failed for property %s on %s — Apaleo error: %s",
            property_id,
            sync_date,
            exc,
        )

@router.get("/status")
async def get_pms_status(
    current_user: Dict[str, Any] = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Returns the current connection status of the PMS."""
    # Fetch property for this user
    result = await db.execute(
        select(RestaurantProfile).where(RestaurantProfile.owner_id == current_user["id"])
    )
    profile = result.scalars().first()
    
    is_connected = bool(os.getenv("APALEO_CLIENT_ID"))
    return {
        "status": "connected" if (is_connected and profile) else "disconnected",
        "provider": profile.pms_type if profile else "none",
        "property_name": profile.property_name if profile else "No property linked",
        "last_sync": date.today().isoformat(),
        "authorized_user": current_user.get("email")
    }

@router.post("/sync")
async def trigger_pms_sync(
    background_tasks: BackgroundTasks,
    target_date: Optional[date] = None,
    use_mock: bool = Query(True, description="Whether to use the Mock adapter for pilot verification"),
    use_mcp: bool = Query(False, description="Use Apaleo MCP Server instead of raw REST API (HOS-101)"),
    current_user: Dict[str, Any] = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Triggers a data sync from the PMS for a specific property and date.
    Guarded by 'get_current_user' to ensure tenant-only access.

    Adapter priority: mock > mcp > raw API.
    """
    sync_date = target_date or date.today()

    # Initialize appropriate adapter
    if use_mock:
        adapter = MockPMSAdapter()
        adapter_label = "mock"
    elif use_mcp:
        adapter = ApaleoMCPAdapter()
        adapter_label = "apaleo_mcp"
    else:
        adapter = ApaleoPMSAdapter()
        adapter_label = "apaleo_raw"

    # Fetch property for this user
    result = await db.execute(
        select(RestaurantProfile).where(RestaurantProfile.owner_id == current_user["id"])
    )
    profile = result.scalars().first()

    if not profile:
        raise HTTPException(status_code=404, detail="No restaurant profile linked to this user.")

    # Use the linked property ID
    property_id = profile.tenant_id

    service = PMSSyncService(adapter)

    # Run sync in background (includes DB persistence)
    background_tasks.add_task(_sync_task, service, property_id, sync_date)

    return {
        "message": "PMS sync triggered successfully in background",
        "property_id": property_id,
        "property_name": profile.property_name,
        "date": sync_date.isoformat(),
        "adapter": adapter_label,
        "triggered_by": current_user.get("email")
    }

from fastapi import APIRouter, BackgroundTasks, HTTPException, Query, Depends
from datetime import date
from typing import Optional, Dict, Any
from app.services.pms_sync import PMSSyncService, MockPMSAdapter
from app.services.apaleo_adapter import ApaleoPMSAdapter
from app.integrations.apaleo_mcp_client import ApaleoMCPClient
from app.core.security import get_current_user
from app.db.session import get_db
from app.db.models import RestaurantProfile
from sqlalchemy.future import select
from sqlalchemy.ext.asyncio import AsyncSession
import os
import time

router = APIRouter(prefix="/pms", tags=["pms"])

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

@router.get("/mcp/probe")
async def mcp_probe():
    """
    Validate the full Apaleo MCP pipeline: credentials → OAuth2 → list_tools → tool call.
    Returns {status, tools, latency_ms}. No auth required (ops/sandbox validation endpoint).
    """
    client = ApaleoMCPClient()
    t0 = time.monotonic()

    if not client.has_credentials:
        raise HTTPException(
            status_code=503,
            detail="APALEO_CLIENT_ID / APALEO_CLIENT_SECRET not configured in environment.",
        )

    try:
        await client.authenticate()
    except Exception as exc:
        raise HTTPException(
            status_code=503,
            detail=f"Apaleo OAuth2 failed: {exc}",
        )

    tools = client.list_tools()

    try:
        await client.call_tool("APALEO_GET_OCCUPANCY_METRICS")
    except Exception as exc:
        raise HTTPException(
            status_code=503,
            detail=f"APALEO_GET_OCCUPANCY_METRICS failed: {exc}",
        )

    latency_ms = int((time.monotonic() - t0) * 1000)
    return {"status": "ok", "tools": len(tools), "latency_ms": latency_ms}


@router.post("/sync")
async def trigger_pms_sync(
    background_tasks: BackgroundTasks,
    target_date: Optional[date] = None,
    use_mock: bool = Query(True, description="Whether to use the Mock adapter for pilot verification"),
    current_user: Dict[str, Any] = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Triggers a data sync from the PMS for a specific property and date.
    Guarded by 'get_current_user' to ensure tenant-only access.
    """
    sync_date = target_date or date.today()
    
    # Initialize appropriate adapter
    if use_mock:
        adapter = MockPMSAdapter()
    else:
        adapter = ApaleoPMSAdapter()
    
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
    background_tasks.add_task(service.sync_daily_data, property_id, sync_date)
    
    return {
        "message": "PMS sync triggered successfully in background",
        "property_id": property_id,
        "property_name": profile.property_name,
        "date": sync_date.isoformat(),
        "adapter": "mock" if use_mock else "apaleo",
        "triggered_by": current_user.get("email")
    }

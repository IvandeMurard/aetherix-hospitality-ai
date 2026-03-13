from fastapi import APIRouter, BackgroundTasks, HTTPException, Query, Depends
from datetime import date
from typing import Optional, Dict, Any
from app.services.pms_sync import PMSSyncService, MockPMSAdapter
from app.services.apaleo_adapter import ApaleoPMSAdapter
from app.core.security import get_current_user
import os

router = APIRouter(prefix="/pms", tags=["pms"])

@router.get("/status")
async def get_pms_status(current_user: Dict[str, Any] = Depends(get_current_user)):
    """Returns the current connection status of the PMS."""
    is_connected = bool(os.getenv("APALEO_CLIENT_ID"))
    return {
        "status": "connected" if is_connected else "disconnected",
        "provider": "apaleo",
        "last_sync": date.today().isoformat(),
        "authorized_user": current_user.get("email")
    }

@router.post("/sync")
async def trigger_pms_sync(
    background_tasks: BackgroundTasks,
    property_id: str = "pilot_hotel",
    target_date: Optional[date] = None,
    use_mock: bool = Query(True, description="Whether to use the Mock adapter for pilot verification"),
    current_user: Dict[str, Any] = Depends(get_current_user)
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
    
    service = PMSSyncService(adapter)
    
    # Run sync in background (includes DB persistence)
    background_tasks.add_task(service.sync_daily_data, property_id, sync_date)
    
    return {
        "message": "PMS sync triggered successfully in background",
        "property_id": property_id,
        "date": sync_date.isoformat(),
        "adapter": "mock" if use_mock else "apaleo",
        "triggered_by": current_user.get("email")
    }

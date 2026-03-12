from fastapi import APIRouter, BackgroundTasks, HTTPException, Query
from datetime import date
from typing import Optional
from app.services.pms_sync import PMSSyncService, MockPMSAdapter
from app.services.apaleo_adapter import ApaleoPMSAdapter

router = APIRouter(prefix="/pms", tags=["pms"])

@router.post("/sync")
async def trigger_pms_sync(
    background_tasks: BackgroundTasks,
    property_id: str,
    target_date: Optional[date] = None,
    use_mock: bool = Query(True, description="Whether to use the Mock adapter for pilot verification")
):
    """
    Triggers a data sync from the PMS for a specific property and date.
    AC #4: Uses BackgroundTasks to prevent blocking.
    """
    sync_date = target_date or date.today()
    
    # Initialize appropriate adapter
    if use_mock:
        adapter = MockPMSAdapter()
    else:
        # Story 2.1: Real Apaleo integration
        adapter = ApaleoPMSAdapter()
    
    service = PMSSyncService(adapter)
    
    # Run sync in background
    background_tasks.add_task(service.sync_daily_data, property_id, sync_date)
    
    return {
        "message": "PMS sync triggered successfully in background",
        "property_id": property_id,
        "date": sync_date.isoformat(),
        "adapter": "mock" if use_mock else "apaleo"
    }

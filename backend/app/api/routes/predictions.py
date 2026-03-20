from fastapi import APIRouter, Depends, HTTPException, Query
from typing import Dict, Any, Optional
from datetime import date
from app.services.aetherix_engine import AetherixEngine
from app.core.security import get_current_user
from app.db.session import get_db
from app.db.models import RestaurantProfile
from sqlalchemy.future import select
from sqlalchemy.ext.asyncio import AsyncSession

router = APIRouter(prefix="/predictions", tags=["predictions"])
engine = AetherixEngine()

@router.get("/current")
async def get_property_prediction(
    target_date: Optional[date] = None,
    service_type: str = "dinner",
    current_user: Dict[str, Any] = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Fetches a hybrid prediction (Prophet + RAG) for a property.
    """
    prediction_date = target_date or date.today()
    
    # Context dictionary for external factors (mocked for now)
    context = {
        "weather": {"condition": "Clear", "temp": 22},
        "events": [],
        "occupancy": 0.85
    }
    
    # Fetch property for this user
    result = await db.execute(
        select(RestaurantProfile).where(RestaurantProfile.owner_id == current_user["id"])
    )
    profile = result.scalars().first()
    
    if not profile:
        raise HTTPException(status_code=404, detail="No restaurant profile linked to this user.")

    # Use the linked property ID
    property_id = profile.tenant_id
    
    try:
        result = await engine.get_forecast(property_id, prediction_date, service_type, context)
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

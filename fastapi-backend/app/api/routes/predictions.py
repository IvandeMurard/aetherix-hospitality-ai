from fastapi import APIRouter, HTTPException
from datetime import date
from typing import Optional, Dict, Any
from app.services.aetherix_engine import AetherixEngine

router = APIRouter(prefix="/predictions", tags=["predictions"])
engine = AetherixEngine()

@router.get("/{property_id}")
async def get_property_prediction(
    property_id: str,
    target_date: Optional[date] = None,
    service_type: str = "dinner"
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
    
    try:
        result = await engine.get_forecast(property_id, prediction_date, service_type, context)
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

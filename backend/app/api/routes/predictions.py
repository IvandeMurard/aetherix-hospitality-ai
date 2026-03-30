from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
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


# ---------------------------------------------------------------------------
# Schemas for POST /predict (MCP-callable, agent-facing)
# ---------------------------------------------------------------------------

class PredictRequest(BaseModel):
    """Input for the agent-callable predict endpoint."""
    hotel_id: str = Field(..., description="Tenant / property identifier")
    target_date: date = Field(..., description="Date to forecast (ISO-8601)")
    service_type: str = Field("dinner", description="Meal service type: breakfast | lunch | dinner")
    context: Optional[Dict[str, Any]] = Field(
        None,
        description=(
            "Optional external context: "
            "{weather: {condition, temp}, events: [...], occupancy: 0.0-1.0}"
        ),
    )


class PredictResponse(BaseModel):
    """Structured output — stable schema for Agent SEO / MCP callers."""
    hotel_id: str
    target_date: str
    service_type: str
    predicted_covers: int
    confidence: float
    range_min: int
    range_max: int
    reasoning_summary: str
    confidence_factors: list
    claude_used: bool
    staffing_recommendation: Dict[str, Any]

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


@router.post("/predict", response_model=PredictResponse, summary="Forecast F&B covers (MCP-callable)")
async def predict(body: PredictRequest):
    """MCP-callable endpoint: given a hotel_id and date, returns a structured
    demand forecast with LLM reasoning (Claude Sonnet) or a heuristic fallback
    when ANTHROPIC_API_KEY is absent.

    Designed for agent-to-agent use (HOS-37 / HOS-71 MCP Server). No JWT auth
    required — authenticate at the infrastructure layer (API key header, VPN, etc.)
    when exposing publicly.

    Schema stability: BREAKING changes require a version bump (Agent SEO policy).
    """
    ctx = body.context or {
        "weather": {"condition": "Unknown", "temp": None},
        "events": [],
        "occupancy": None,
    }

    try:
        result = await engine.get_forecast(
            body.hotel_id, body.target_date, body.service_type, ctx
        )
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))

    pred = result["prediction"]
    # Use reasoning_detail (full dict) when available, fall back to the summary string.
    reasoning_detail = result.get("reasoning_detail", {})
    summary = reasoning_detail.get("summary") or str(result.get("reasoning", ""))
    confidence_factors = reasoning_detail.get("confidence_factors", [])
    claude_used = reasoning_detail.get("claude_used", False)

    return PredictResponse(
        hotel_id=body.hotel_id,
        target_date=result.get("date", body.target_date.isoformat()),
        service_type=result.get("service_type", body.service_type),
        predicted_covers=pred.get("covers", pred.get("predicted_covers", 0)),
        confidence=pred.get("confidence", 0.0),
        range_min=pred.get("interval", [pred.get("covers", 0), pred.get("covers", 0)])[0],
        range_max=pred.get("interval", [pred.get("covers", 0), pred.get("covers", 0)])[1],
        reasoning_summary=summary,
        confidence_factors=confidence_factors,
        claude_used=claude_used,
        staffing_recommendation=result.get("staffing_recommendation", {}),
    )

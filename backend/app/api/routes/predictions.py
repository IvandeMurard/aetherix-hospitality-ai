import json
import logging
import os
from datetime import date, timedelta
from pathlib import Path
from typing import Any, Dict, Optional

import pandas as pd
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

from app.core.security import get_current_user
from app.db.models import RestaurantProfile
from app.db.session import get_db
from app.services.aetherix_engine import AetherixEngine

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/predictions", tags=["predictions"])
engine = AetherixEngine()

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------
_REPO_ROOT = Path(__file__).parent.parent.parent.parent.parent  # backend/../..
_DEMO_DATA = _REPO_ROOT / "demo_data" / "prophet_training.json"
_MODEL_PATH = str(_REPO_ROOT / "demo_data" / "prophet_model.json")


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
    is_mock: bool
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
        is_mock=pred.get("is_mock", False),
        reasoning_summary=summary,
        confidence_factors=confidence_factors,
        claude_used=claude_used,
        staffing_recommendation=result.get("staffing_recommendation", {}),
    )


# ---------------------------------------------------------------------------
# Training endpoint — HOS-143 (Decision #13)
# ---------------------------------------------------------------------------

class TrainRequest(BaseModel):
    """Input for POST /predictions/train."""
    property_id: str = Field(
        "demo_hotel",
        description="Apaleo property ID.  Ignored when DEMO_MODE=true.",
    )
    start_date: date = Field(
        default_factory=lambda: date.today() - timedelta(days=365),
        description="Historical window start (live mode only).",
    )
    end_date: date = Field(
        default_factory=lambda: date.today() - timedelta(days=1),
        description="Historical window end (live mode only).",
    )


class TrainResponse(BaseModel):
    status: str
    rows_trained: int
    demo_mode: bool
    model_saved_to: str
    message: str


@router.post(
    "/train",
    response_model=TrainResponse,
    summary="Train Prophet model (DEMO_MODE or live Apaleo)",
)
async def train_prophet(body: TrainRequest = TrainRequest()):
    """Connect the Prophet training pipeline (Decision #13 gap).

    **DEMO_MODE=true** (default for local dev):
      Loads ``demo_data/prophet_training.json`` — synthetic 365-day Paris 4*
      dataset.  No Apaleo credentials required.

    **DEMO_MODE=false**:
      Fetches live historical reservations from Apaleo MCP, transforms them
      via ``DataTransformer.stay_records_to_prophet()``, and trains Prophet.

    After training, the model is:
    - Active in-process immediately (subsequent ``/predict`` calls use it).
    - Persisted to ``demo_data/prophet_model.json`` for restart-resilience.
    """
    demo_mode = os.getenv("DEMO_MODE", "false").lower() in ("1", "true", "yes")

    try:
        if demo_mode:
            df = _load_demo_dataframe()
            source = "demo_data/prophet_training.json"
        else:
            df = await _load_live_dataframe(body.property_id, body.start_date, body.end_date)
            source = f"Apaleo/{body.property_id} ({body.start_date}→{body.end_date})"
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Data loading failed: {exc}") from exc

    if df.empty:
        raise HTTPException(
            status_code=422,
            detail=(
                "Training dataset is empty.  "
                "Set DEMO_MODE=true or supply valid Apaleo credentials."
            ),
        )

    try:
        engine.forecaster.train(df)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Prophet training failed: {exc}") from exc

    engine.forecaster.save_model(_MODEL_PATH)
    logger.info("Prophet trained on %d rows from %s, saved to %s", len(df), source, _MODEL_PATH)

    return TrainResponse(
        status="ok",
        rows_trained=len(df),
        demo_mode=demo_mode,
        model_saved_to=_MODEL_PATH,
        message=(
            f"Prophet model trained on {len(df)} days from {source}. "
            "is_mock will be false on subsequent /predict calls."
        ),
    )


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _load_demo_dataframe() -> pd.DataFrame:
    """Load the pre-generated synthetic dataset into a Prophet-ready DataFrame."""
    if not _DEMO_DATA.exists():
        raise FileNotFoundError(
            f"Demo dataset not found at {_DEMO_DATA}.  "
            "Run: python scripts/generate_demo_data.py"
        )
    rows = json.loads(_DEMO_DATA.read_text(encoding="utf-8"))
    df = pd.DataFrame(rows)
    df["ds"] = pd.to_datetime(df["ds"])
    return df


async def _load_live_dataframe(
    property_id: str, start_date: date, end_date: date
) -> pd.DataFrame:
    """Fetch Apaleo reservations and transform them into a Prophet DataFrame."""
    from app.services.apaleo_mcp_adapter import ApaleoMCPAdapter
    from app.services.data_transformer import DataTransformer

    adapter = ApaleoMCPAdapter()
    records = await adapter.get_historical_data(property_id, start_date, end_date)
    return DataTransformer.stay_records_to_prophet(records)

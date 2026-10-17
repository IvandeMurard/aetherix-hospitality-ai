import json
import logging
import time
import uuid
from datetime import date, timedelta
from enum import Enum
from pathlib import Path
from typing import Any, Dict, Optional

import numpy as np
import pandas as pd
from fastapi import APIRouter, Depends, Header, HTTPException, Request, Response
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

from app.core.security import get_current_user
from app.db.models import CaptationBaseline, MCPApiToken, RestaurantProfile, TrainingRun
from app.db.session import get_db
from app.mcp_core import ADMIN_TRAIN_SCOPE, MCPAuthError
from app.mcp_server import verify_bearer
from app.services.events_enrichment import enrich_events_context

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/predictions", tags=["predictions"])


# ---------------------------------------------------------------------------
# MCP bearer-token auth dependencies (HOS-149)
# ---------------------------------------------------------------------------

def _require_mcp_scope(scope: str):
    """Factory: returns a FastAPI dependency that validates bearer + scope."""
    async def _dep(
        authorization: Optional[str] = Header(None),
        db: AsyncSession = Depends(get_db),
    ) -> MCPApiToken:
        try:
            tok = await verify_bearer(authorization, db)
        except MCPAuthError as exc:
            raise HTTPException(
                status_code=exc.status,
                headers={"WWW-Authenticate": "Bearer"},
                detail=exc.detail,
            )
        if scope not in (tok.scopes or []):
            raise HTTPException(
                status_code=403,
                detail=f"Token missing required scope: {scope}",
            )
        return tok
    return _dep


# Named at module level so tests can apply dependency_overrides
_predict_auth = _require_mcp_scope("predict")
_train_auth = _require_mcp_scope(ADMIN_TRAIN_SCOPE)

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------
_BACKEND_ROOT = Path(__file__).parent.parent.parent.parent  # routes/ → backend/
_DEMO_DATA = _BACKEND_ROOT / "data" / "demo" / "prophet_training.json"
_MODEL_PATH = str(_BACKEND_ROOT / "data" / "demo" / "prophet_model.json")


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
    # ADR-0007 §18.2: range_min/max is Prophet's nominal-80 % interval, whose
    # measured coverage was below nominal. calibrated_interval carries the
    # recalibrated one with its provenance label, or null when none applies.
    interval_nominal_level: Optional[float] = None
    calibrated_interval: Optional[dict] = None
    is_mock: bool
    reasoning_summary: str
    confidence_factors: list
    claude_used: bool
    staffing_recommendation: Dict[str, Any]

@router.get("/current")
async def get_property_prediction(
    request: Request,
    target_date: Optional[date] = None,
    service_type: str = "dinner",
    current_user: Dict[str, Any] = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Fetches a hybrid prediction (Prophet + RAG) for a property.
    """
    engine = request.app.state.engine
    prediction_date = target_date or date.today()

    result = await db.execute(
        select(RestaurantProfile).where(RestaurantProfile.owner_id == current_user["id"])
    )
    profile = result.scalars().first()

    if not profile:
        raise HTTPException(status_code=404, detail="No restaurant profile linked to this user.")

    property_id = profile.tenant_id

    # HOS-225: wire real local events (PredictHQ, HOS-84) into the forecast
    # context so reasoning cites concrete drivers instead of "events: []".
    context = {
        "weather": {"condition": "Clear", "temp": 22},
        "events": await enrich_events_context(db, profile, prediction_date),
        "occupancy": 0.85,
    }

    try:
        result = await engine.get_forecast(property_id, prediction_date, service_type, context)
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post(
    "/predict",
    response_model=PredictResponse,
    summary="Forecast F&B covers (MCP-callable)",
    openapi_extra={"x-agent-callable": True, "x-mcp-compatible": True},
)
async def predict(
    request: Request,
    body: PredictRequest,
    response: Response,
    tok: MCPApiToken = Depends(_predict_auth),
    db: AsyncSession = Depends(get_db),
):
    """MCP-callable endpoint: given a hotel_id and date, returns a structured
    demand forecast with LLM reasoning (Claude Sonnet) or a heuristic fallback
    when ANTHROPIC_API_KEY is absent.

    Requires a valid MCP bearer token with scope `predict` (HOS-149 AC2).
    hotel_id is always taken from the token — body.hotel_id is ignored if it
    differs (HOS-149 AC3).

    Schema stability: BREAKING changes require a version bump (Agent SEO policy).
    """
    engine = request.app.state.engine
    # AC3: hotel_id is bound to the token — never trusted from caller
    if body.hotel_id and body.hotel_id != tok.hotel_id:
        logger.warning(
            "predict: hotel_id mismatch body=%s token=%s — using token hotel_id",
            body.hotel_id,
            tok.hotel_id,
        )
    hotel_id = tok.hotel_id
    response.headers["X-Aetherix-Hotel-Id"] = hotel_id

    ctx = body.context or {
        "weather": {"condition": "Unknown", "temp": None},
        "events": [],
        "occupancy": None,
    }

    # HOS-225: enrich with real local events only when the caller didn't supply
    # them. An explicit non-empty `events` list is respected (back-compat: MCP
    # callers that pass their own context stay authoritative).
    if not ctx.get("events"):
        prof_result = await db.execute(
            select(RestaurantProfile).where(RestaurantProfile.tenant_id == hotel_id)
        )
        profile = prof_result.scalars().first()
        ctx = {**ctx, "events": await enrich_events_context(db, profile, body.target_date)}

    try:
        result = await engine.get_forecast(hotel_id, body.target_date, body.service_type, ctx)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))

    pred = result["prediction"]
    reasoning_detail = result.get("reasoning_detail", {})
    summary = reasoning_detail.get("summary") or str(result.get("reasoning", ""))
    confidence_factors = reasoning_detail.get("confidence_factors", [])
    claude_used = reasoning_detail.get("claude_used", False)

    covers = pred.get("covers", pred.get("predicted_covers", 0))
    return PredictResponse(
        hotel_id=hotel_id,
        target_date=result.get("date", body.target_date.isoformat()),
        service_type=result.get("service_type", body.service_type),
        predicted_covers=covers,
        confidence=pred.get("confidence", 0.0),
        range_min=pred.get("range_min", covers),
        range_max=pred.get("range_max", covers),
        interval_nominal_level=pred.get("interval_nominal_level"),
        calibrated_interval=pred.get("calibrated_interval"),
        is_mock=pred.get("is_mock", False),
        reasoning_summary=summary,
        confidence_factors=confidence_factors,
        claude_used=claude_used,
        staffing_recommendation=result.get("staffing_recommendation", {}),
    )


# ---------------------------------------------------------------------------
# Training endpoint — HOS-143 (Decision #13)
# ---------------------------------------------------------------------------

class DataSource(str, Enum):
    mcp_sandbox = "mcp_sandbox"
    synthetic = "synthetic"
    hybrid = "hybrid"


class TrainRequest(BaseModel):
    property_id: Optional[str] = Field(
        None,
        description=(
            "Deprecated (HOS-347): the PMS property is resolved from the token's hotel. "
            "If given, it must equal that hotel's PMS property id."
        ),
    )
    start_date: date = Field(
        default_factory=lambda: date.today() - timedelta(days=365),
        description="Historical window start (live MCP modes only).",
    )
    end_date: date = Field(
        default_factory=lambda: date.today() - timedelta(days=1),
        description="Historical window end (live MCP modes only).",
    )
    data_source: DataSource = Field(
        DataSource.synthetic,
        description=(
            "mcp_sandbox: live Apaleo MCP only. "
            "synthetic: demo_data/prophet_training.json only. "
            "hybrid: merge both, tag each row with its source."
        ),
    )
    include_weather: bool = Field(True)
    include_events: bool = Field(True)
    include_occupancy: bool = Field(True)


class TrainResponse(BaseModel):
    training_id: str
    status: str
    records_processed: int
    duration_ms: int
    model_path: str
    mape_training: Optional[float] = None
    data_source: str
    message: str


@router.post(
    "/train",
    response_model=TrainResponse,
    summary="Train Prophet model — orchestrates MCP adapter → DataTransformer → PredictionEngine (Decision #13)",
)
async def train_prophet(
    request: Request,
    body: TrainRequest = TrainRequest(),
    db: AsyncSession = Depends(get_db),
    tok: MCPApiToken = Depends(_train_auth),
):
    """Orchestrates the full Prophet training pipeline (Decision #13 gap closure).

    data_source=synthetic  → loads demo_data/prophet_training.json (default, no credentials needed)
    data_source=mcp_sandbox → fetches live Apaleo MCP reservations
    data_source=hybrid      → merges both sources, each row tagged with 'source' column

    After training the model is active in-process and persisted for restart-resilience.
    Every call is audit-logged to the training_runs table.
    """
    engine = request.app.state.engine
    t0 = time.monotonic()
    training_id = str(uuid.uuid4())

    # HOS-347: the hotel is the token's (tenant id, used for everything stored);
    # its PMS property id is resolved from its profile and only used to call
    # the PMS. Synthetic training needs no PMS.
    tenant_id = tok.hotel_id
    pms_property_id: Optional[str] = None
    if body.data_source != DataSource.synthetic:
        from app.services.pms_identity import PmsIdentityError, resolve_by_tenant

        try:
            target = await resolve_by_tenant(db, tenant_id)
        except PmsIdentityError as exc:
            raise HTTPException(status_code=409, detail=exc.detail) from None
        if target.pms_type != "apaleo":
            # The PMS-backed loader is Apaleo's (MCP); other PMSs need their
            # adapter first (Décision #28). Never load through another vendor.
            raise HTTPException(
                status_code=409,
                detail=f"no training data loader yet for this hotel's PMS ({target.pms_type})",
            )
        if body.property_id and body.property_id != target.pms_property_id:
            raise HTTPException(
                status_code=422,
                detail="property_id does not match this hotel's PMS property id",
            )
        pms_property_id = target.pms_property_id

    try:
        df = await _build_training_dataframe(body, pms_property_id)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Data loading failed: {exc}") from exc

    if df.empty:
        raise HTTPException(
            status_code=422,
            detail=(
                "Training dataset is empty. Use data_source=synthetic or "
                "supply valid APALEO_MCP_SERVER_URL credentials."
            ),
        )

    if len(df) < 60:
        raise HTTPException(
            status_code=422,
            detail=f"Insufficient data: {len(df)} days found, minimum 60 required for reliable training.",
        )

    # Apply per-property captation rate calibration when available
    df = await _apply_captation_calibration(df, tenant_id, db)

    try:
        await engine.forecaster.train(
            df,
            include_weather=body.include_weather,
            include_events=body.include_events,
            include_occupancy=body.include_occupancy,
            data_source=body.data_source.value,
        )
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Prophet training failed: {exc}") from exc

    engine.forecaster.save_model(_MODEL_PATH)

    duration_ms = int((time.monotonic() - t0) * 1000)
    mape_training = _compute_in_sample_mape(engine.forecaster, df)

    # Audit log (best-effort — don't fail the response if DB write fails)
    try:
        run = TrainingRun(
            id=uuid.UUID(training_id),
            property_id=tenant_id,  # column holds the tenant id since HOS-347
            source=body.data_source.value,
            records_count=len(df),
            mape_training=mape_training,
            duration_ms=duration_ms,
            model_path=_MODEL_PATH,
        )
        db.add(run)
        await db.commit()
    except Exception as db_exc:
        logger.warning("training_runs audit log failed (non-blocking): %s", db_exc)

    logger.info(
        "Prophet trained: id=%s property=%s source=%s rows=%d mape=%.2f%% duration=%dms",
        training_id, tenant_id, body.data_source.value,
        len(df), (mape_training or 0) * 100, duration_ms,
    )

    return TrainResponse(
        training_id=training_id,
        status="ok",
        records_processed=len(df),
        duration_ms=duration_ms,
        model_path=_MODEL_PATH,
        mape_training=mape_training,
        data_source=body.data_source.value,
        message=(
            f"Prophet model trained on {len(df)} days "
            f"(source={body.data_source.value}, mape_training="
            f"{'N/A' if mape_training is None else f'{mape_training*100:.1f}%'}). "
            "is_mock will be False on subsequent /predict calls."
        ),
    )


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _load_demo_dataframe() -> pd.DataFrame:
    if not _DEMO_DATA.exists():
        raise FileNotFoundError(
            f"Demo dataset not found at {_DEMO_DATA}. "
            "Run: python scripts/generate_demo_data.py"
        )
    rows = json.loads(_DEMO_DATA.read_text(encoding="utf-8"))
    df = pd.DataFrame(rows)
    df["ds"] = pd.to_datetime(df["ds"])
    df["_source"] = "synthetic"
    return df


async def _load_mcp_dataframe(
    property_id: str, start_date: date, end_date: date
) -> pd.DataFrame:
    from app.providers.pms.apaleo_mcp_adapter import ApaleoMCPAdapter
    from app.services.data_transformer import DataTransformer

    adapter = ApaleoMCPAdapter()
    records = await adapter.get_historical_data(property_id, start_date, end_date)
    df = DataTransformer.stay_records_to_prophet(records)
    if not df.empty:
        df["_source"] = "mcp_sandbox"
    return df


async def _build_training_dataframe(body: "TrainRequest", pms_property_id: Optional[str] = None) -> pd.DataFrame:
    """``pms_property_id``: the hotel's PMS id, resolved by the caller (HOS-347)."""
    if body.data_source == DataSource.synthetic:
        return _load_demo_dataframe()
    pms_id = pms_property_id or body.property_id
    if not pms_id:
        raise ValueError("a PMS property id is required for PMS-backed training")
    if body.data_source == DataSource.mcp_sandbox:
        return await _load_mcp_dataframe(pms_id, body.start_date, body.end_date)
    # hybrid: merge both, prefer MCP where dates overlap
    df_synthetic = _load_demo_dataframe()
    df_mcp = await _load_mcp_dataframe(pms_id, body.start_date, body.end_date)
    if df_mcp.empty:
        logger.warning("hybrid mode: MCP returned no data, falling back to synthetic only")
        return df_synthetic
    # Union — MCP rows override synthetic rows on the same date
    mcp_dates = set(df_mcp["ds"].dt.normalize())
    df_synthetic_trimmed = df_synthetic[~df_synthetic["ds"].dt.normalize().isin(mcp_dates)]
    df_merged = pd.concat([df_synthetic_trimmed, df_mcp], ignore_index=True)
    df_merged.sort_values("ds", inplace=True)
    df_merged.reset_index(drop=True, inplace=True)
    return df_merged


async def _apply_captation_calibration(
    df: pd.DataFrame, property_id: str, db: AsyncSession
) -> pd.DataFrame:
    """Scale 'y' values by per-property captation baseline when available."""
    try:
        result = await db.execute(
            select(CaptationBaseline)
            .where(CaptationBaseline.tenant_id == property_id)
            .order_by(CaptationBaseline.computed_at.desc())
            .limit(1)
        )
        baseline = result.scalars().first()
        if baseline and baseline.avg_fb_revenue_per_room and baseline.avg_fb_revenue_per_room > 0:
            scale = float(baseline.avg_fb_revenue_per_room)
            df = df.copy()
            df["y"] = (df["y"] * scale).round().astype(int)
            logger.info("Captation calibration applied: property=%s scale=%.3f", property_id, scale)
        else:
            logger.debug("No captation baseline for property=%s, using raw values", property_id)
    except Exception as exc:
        logger.warning("Captation calibration failed (non-blocking): %s", exc)
    return df


def _compute_in_sample_mape(forecaster: Any, df: pd.DataFrame) -> Optional[float]:
    """Compute in-sample MAPE on training data as a training quality signal."""
    try:
        if not forecaster.is_trained or forecaster.model is None:
            return None
        pred_df = forecaster.model.predict(df[["ds"]].copy())
        y_true = df["y"].values
        y_pred = pred_df["yhat"].values
        mask = y_true > 0
        if mask.sum() == 0:
            return None
        mape = float(np.mean(np.abs((y_true[mask] - y_pred[mask]) / y_true[mask])))
        return round(mape, 4)
    except Exception as exc:
        logger.warning("In-sample MAPE computation failed: %s", exc)
        return None

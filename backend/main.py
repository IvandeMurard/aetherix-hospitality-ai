# -*- coding: utf-8 -*-
# LOAD ENVIRONMENT VARIABLES FIRST
from pathlib import Path
from dotenv import load_dotenv

# Find .env file (project root)
env_path = Path(__file__).parent.parent / ".env"
load_dotenv(dotenv_path=env_path)
print(f"[STARTUP] Loaded .env from: {env_path} (exists: {env_path.exists()})")

# IMPORT UTF-8 CONFIG FIRST - before any other imports
import backend.utf8_config  # noqa: F401

import asyncio
import os
import sys
import io

import uuid
from datetime import datetime, timezone, date
from fastapi import HTTPException


def get_debug_log_path() -> str | None:
    """Get debug log path from environment or use relative path.
    Returns None if file logging is disabled (for Docker/production)."""
    if os.getenv("DISABLE_FILE_LOGGING", "").lower() in ("true", "1", "yes"):
        return None
    return os.getenv("DEBUG_LOG_PATH", str(Path(__file__).parent.parent / "debug.log"))


def _write_debug_log(message: str) -> None:
    """Write to debug log file if file logging is enabled."""
    debug_log_path = get_debug_log_path()
    if debug_log_path is None:
        return
    try:
        with open(debug_log_path, "a", encoding="utf-8") as f:
            f.write(f"{message} - {datetime.now()}\n")
            f.flush()
    except Exception:
        pass  # Silently ignore file logging errors in production

"""
F&B Operations Agent - FastAPI Backend
MVP Phase 1 - Entry point
"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI(
    title="F&B Operations Agent API",
    description="AI-powered staffing forecasting for restaurants",
    version="0.1.0"
)

# Add middleware to log all requests with CORS diagnostics
@app.middleware("http")
async def log_requests(request, call_next):
    import sys
    import logging
    
    logger = logging.getLogger("uvicorn")
    
    # Log request details including origin header for CORS debugging
    origin = request.headers.get("origin", "no-origin-header")
    referer = request.headers.get("referer", "no-referer-header")
    user_agent = request.headers.get("user-agent", "no-user-agent")[:100]
    
    logger.info(
        f"[MIDDLEWARE] Request: {request.method} {request.url.path} | "
        f"Origin: {origin} | Referer: {referer[:50]}"
    )
    _write_debug_log(
        f"[MIDDLEWARE] Request: {request.method} {request.url.path} | "
        f"Origin: {origin} | Referer: {referer[:50]}"
    )
    
    response = await call_next(request)
    
    # Log response with CORS headers
    cors_headers = {
        "access-control-allow-origin": response.headers.get("access-control-allow-origin", "not-set"),
        "access-control-allow-methods": response.headers.get("access-control-allow-methods", "not-set"),
        "access-control-allow-headers": response.headers.get("access-control-allow-headers", "not-set"),
    }
    
    logger.info(
        f"[MIDDLEWARE] Response: {response.status_code} | "
        f"CORS Origin: {cors_headers['access-control-allow-origin']}"
    )
    _write_debug_log(
        f"[MIDDLEWARE] Response: {response.status_code} | "
        f"CORS Headers: {cors_headers}"
    )
    
    return response

# CORS for frontend
# Allow all origins to fix 403 errors from Streamlit Cloud and HuggingFace Space
# Note: FastAPI CORSMiddleware with allow_credentials=True cannot use ["*"]
# So we set allow_credentials=False to allow "*" origins (required for CORS with "*")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Allow all origins - required for Streamlit Cloud and HF Space
    allow_credentials=False,  # Set to False to allow "*" origins (required for CORS with "*")
    allow_methods=["*"],  # Allow all HTTP methods
    allow_headers=["*"],  # Allow all headers
    expose_headers=["*"],  # Expose all headers
)

# Log CORS configuration at startup
import logging
logger = logging.getLogger("uvicorn")
logger.info("[CORS] Configured: allow_origins=['*'], allow_credentials=False")
_write_debug_log("[CORS] Configured: allow_origins=['*'], allow_credentials=False")

# F&B Agent API routes (restaurant profile, predictions, feedback)
from backend.api.routes import router as api_router
from backend.api.restaurant_profile_routes import router as restaurant_profile_router

app.include_router(api_router)
app.include_router(restaurant_profile_router)

@app.get("/")
async def root():
    return {
        "name": "F&B Operations Agent API",
        "version": "1.0.0",
        "status": "running",
        "docs": "/docs"
    }

@app.get("/health")
async def health():
    return {"status": "healthy", "version": "1.0.0"}

@app.get("/diagnostic")
async def diagnostic():
    """
    Diagnostic endpoint to check system health and configuration.
    Useful for debugging 403 errors and CORS issues.
    """
    import os
    required_vars = [
        "ANTHROPIC_API_KEY",
        "QDRANT_URL",
        "QDRANT_API_KEY",
        "MISTRAL_API_KEY",
        "SUPABASE_URL",
        "SUPABASE_KEY",
    ]
    missing_vars = [k for k in required_vars if not os.getenv(k)]
    
    # Check if backend can import required modules
    backend_status = "ok"
    try:
        from backend.utils.claude_client import ClaudeClient
        from backend.utils.qdrant_client import QdrantManager
    except Exception as e:
        backend_status = f"error: {str(e)}"
    
    return {
        "status": "running",
        "version": "1.0.0",
        "cors_configured": True,
        "cors_allow_origins": ["*"],
        "cors_allow_credentials": False,
        "environment": os.getenv("ENVIRONMENT", "production"),
        "port": os.getenv("PORT", "7860"),
        "missing_env_vars": missing_vars,
        "env_vars_count": len([k for k in required_vars if os.getenv(k)]),
        "backend_status": backend_status,
        "api_base_url": os.getenv("AETHERIX_API_BASE", "not-set"),
    }

@app.get("/test/claude")
async def test_claude():
    """Test Claude API connection"""
    from backend.utils.claude_client import ClaudeClient
    async with ClaudeClient() as client:
        return await client.test_connection()

@app.get("/test/qdrant")
async def test_qdrant():
    """Test Qdrant connection"""
    from .utils.qdrant_client import QdrantManager
    client = QdrantManager()
    return await client.test_connection()

# ============================================
# PHASE 1: Prediction Endpoints
# ============================================

import math

from backend.models.schemas import (
    PredictionRequest,
    PredictionResponse,
    BatchPredictionRequest,
    Reasoning,
    StaffRecommendation,
    StaffDelta,
    AccuracyMetrics,
    ServiceType,
)
from backend.agents.demand_predictor import get_demand_predictor
from backend.api.prediction_store import store_prediction_for_feedback

@app.post("/predict", response_model=PredictionResponse)
async def create_prediction(request: PredictionRequest):
    """
    Create a staffing prediction
    
    Phase 1: Basic prediction (mocked data)
    Phase 2: Full integration (real patterns, APIs)
    """
    import logging
    logger = logging.getLogger("uvicorn")
    
    try:
        logger.info(f"[PREDICT] Request: {request.service_date} ({request.service_type})")
        _write_debug_log(f"[PREDICT] Request: {request.service_date} ({request.service_type})")
        
        # Get demand predictor
        predictor = get_demand_predictor()
        
        # Generate prediction
        result = await predictor.predict(request)
        logger.info(f"[PREDICT] Result: {result.get('predicted_covers')} covers")
        
        # TODO Hour 3-4: Add reasoning engine + staff recommender
        # For now, return basic structure
        
        # Extract reasoning from predictor result (now includes Claude-generated reasoning)
        reasoning_data = result.get("reasoning", {})
        patterns_from_result = reasoning_data.get("patterns_used", [])
        
        reasoning = Reasoning(
            summary=reasoning_data.get("summary", f"{int(result['confidence']*100)}% confidence"),
            patterns_used=patterns_from_result[:3] if patterns_from_result else [],
            confidence_factors=reasoning_data.get("confidence_factors", ["Historical patterns"])
        )
        
        # Create StaffRecommendation object from dynamic calculation
        staff_data = result.get("staff_recommendation", {})
        staff_recommendation = StaffRecommendation(
            servers=StaffDelta(
                recommended=staff_data.get("servers", {}).get("recommended", 7),
                usual=staff_data.get("servers", {}).get("usual", 7),
                delta=staff_data.get("servers", {}).get("delta", 0)
            ),
            hosts=StaffDelta(
                recommended=staff_data.get("hosts", {}).get("recommended", 2),
                usual=staff_data.get("hosts", {}).get("usual", 2),
                delta=staff_data.get("hosts", {}).get("delta", 0)
            ),
            kitchen=StaffDelta(
                recommended=staff_data.get("kitchen", {}).get("recommended", 3),
                usual=staff_data.get("kitchen", {}).get("usual", 3),
                delta=staff_data.get("kitchen", {}).get("delta", 0)
            ),
            rationale=staff_data.get("rationale", ""),
            covers_per_staff=staff_data.get("covers_per_staff", 0.0)
        )
        restaurant_context = None

        # Enrich with restaurant profile when available (IVA-52)
        try:
            from backend.api.routes import get_supabase
            supabase = get_supabase()
            profile_resp = (
                supabase.table("restaurant_profiles")
                .select("*")
                .eq("outlet_name", request.restaurant_id)
                .limit(1)
                .execute()
            )
            if profile_resp.data and len(profile_resp.data) > 0:
                profile = profile_resp.data[0]
                predicted = result["predicted_covers"]
                turns_dinner = profile.get("turns_dinner", 2.0)
                total_seats = profile["total_seats"]
                capacity_pct = round(
                    (predicted / (total_seats * turns_dinner)) * 100, 1
                )
                restaurant_context = {
                    "total_seats": total_seats,
                    "breakeven_covers": profile.get("breakeven_covers"),
                    "target_covers": profile.get("target_covers"),
                    "capacity_pct": capacity_pct,
                }
                # Override staff recommendation with profile-based calculation
                servers_rec = max(
                    math.ceil(predicted / profile["covers_per_server"]),
                    profile.get("min_foh_staff", 2),
                )
                hosts_rec = max(
                    math.ceil(predicted / profile["covers_per_host"]),
                    1,
                )
                kitchen_rec = max(
                    math.ceil(predicted / profile["covers_per_kitchen"]),
                    profile.get("min_boh_staff", 2),
                )
                staff_recommendation = StaffRecommendation(
                    servers=StaffDelta(
                        recommended=servers_rec,
                        usual=servers_rec,
                        delta=0,
                    ),
                    hosts=StaffDelta(
                        recommended=hosts_rec,
                        usual=hosts_rec,
                        delta=0,
                    ),
                    kitchen=StaffDelta(
                        recommended=kitchen_rec,
                        usual=kitchen_rec,
                        delta=0,
                    ),
                    rationale=staff_data.get("rationale", ""),
                    covers_per_staff=round(
                        predicted / (servers_rec + hosts_rec + kitchen_rec), 1
                    )
                    if (servers_rec + hosts_rec + kitchen_rec) > 0
                    else 0.0,
                )
        except Exception as e:
            logger.debug(f"[PREDICT] No restaurant profile for {request.restaurant_id}: {e}")

        # Extract accuracy_metrics from result
        accuracy_data = result.get("accuracy_metrics", {})
        accuracy_metrics = None
        if accuracy_data:
            # Convert tuple to list for prediction_interval if present
            if "prediction_interval" in accuracy_data and accuracy_data["prediction_interval"]:
                if isinstance(accuracy_data["prediction_interval"], tuple):
                    accuracy_data["prediction_interval"] = list(accuracy_data["prediction_interval"])
            accuracy_metrics = AccuracyMetrics(**accuracy_data)

        # Extraire range_low et range_high
        interval = accuracy_metrics.prediction_interval if accuracy_metrics else None
        range_low = interval[0] if interval and len(interval) >= 2 else result["predicted_covers"] - 10
        range_high = interval[1] if interval and len(interval) >= 2 else result["predicted_covers"] + 10

        # Extraire patterns pour stockage (convertis en dict si besoin)
        patterns_for_storage = []
        if reasoning_data and "patterns_used" in reasoning_data:
            raw = reasoning_data["patterns_used"]
            for p in raw:
                if isinstance(p, dict):
                    patterns_for_storage.append(p)
                elif hasattr(p, "model_dump"):
                    patterns_for_storage.append(p.model_dump())
                else:
                    patterns_for_storage.append(dict(p) if hasattr(p, "__iter__") else {})

        # Extraire confidence_factors
        confidence_factors = reasoning_data.get("confidence_factors", []) if reasoning_data else []

        # Stocker en Supabase pour feedback loop
        stored_id = None
        try:
            stored_id = store_prediction_for_feedback(
                restaurant_id=request.restaurant_id,
                service_date=request.service_date,
                service_type=request.service_type.value if hasattr(request.service_type, "value") else str(request.service_type),
                predicted_covers=result["predicted_covers"],
                confidence=result["confidence"],
                range_low=range_low,
                range_high=range_high,
                estimated_mape=accuracy_metrics.estimated_mape if accuracy_metrics else None,
                patterns=patterns_for_storage,
                confidence_factors=confidence_factors
            )
        except Exception as e:
            logger.warning(f"[PREDICT] Store for feedback failed: {e}")

        # Utiliser l'UUID Supabase si disponible, sinon fallback
        prediction_id = stored_id if stored_id else f"pred_{uuid.uuid4().hex[:8]}"

        # Return PredictionResponse
        return PredictionResponse(
            prediction_id=prediction_id,
            service_date=request.service_date,
            service_type=request.service_type,
            predicted_covers=result["predicted_covers"],
            confidence=result["confidence"],
            reasoning=reasoning,
            staff_recommendation=staff_recommendation,
            accuracy_metrics=accuracy_metrics,
            restaurant_context=restaurant_context,
            created_at=datetime.now(timezone.utc).isoformat()
        )
        
    except ValueError as e:
        error_detail = str(e).encode('utf-8', errors='replace').decode('utf-8', errors='replace')
        logger.warning(f"[PREDICT] ValueError: {error_detail}")
        raise HTTPException(status_code=422, detail=error_detail)
    except Exception as e:
        error_detail = str(e).encode('utf-8', errors='replace').decode('utf-8', errors='replace')
        logger.error(f"[PREDICT] Error: {error_detail}")
        raise HTTPException(status_code=500, detail=error_detail)


# Limit concurrent predictions to avoid overwhelming Claude/Mistral APIs
BATCH_CONCURRENCY = 5


async def _create_prediction_with_semaphore(sem: asyncio.Semaphore, single: PredictionRequest, d: str):
    """Run create_prediction with semaphore; return (date_str, result_or_exception)."""
    async with sem:
        try:
            resp = await create_prediction(single)
            out = resp.model_dump()
            out["date"] = d
            out["service_date"] = d
            return (d, out)
        except Exception as e:
            return (d, e)


@app.post("/predict/batch")
async def create_prediction_batch(request: BatchPredictionRequest):
    """
    Generate predictions for multiple dates at once.
    Runs up to BATCH_CONCURRENCY predictions in parallel for faster loading.
    Max 31 dates per request.
    """
    import logging
    logger = logging.getLogger("uvicorn")
    
    try:
        logger.info(f"[PREDICT/BATCH] Request: {len(request.dates)} dates for {request.restaurant_id} ({request.service_type})")
        _write_debug_log(f"[PREDICT/BATCH] Request: {len(request.dates)} dates for {request.restaurant_id} ({request.service_type})")
        
        MAX_DATES = 31
        dates = request.dates[:MAX_DATES]
        try:
            st_enum = ServiceType(request.service_type.lower())
        except (ValueError, AttributeError):
            st_enum = ServiceType.DINNER

        # Build list of (date_str, PredictionRequest) for valid dates
        singles = []
        for d in dates:
            try:
                service_date = date.fromisoformat(d)
            except ValueError as e:
                logger.warning(f"[PREDICT/BATCH] Invalid date format: {d} - {e}")
                continue
            singles.append((
                d,
                PredictionRequest(
                    restaurant_id=request.restaurant_id,
                    service_date=service_date,
                    service_type=st_enum,
                ),
            ))

        # Run predictions in parallel with semaphore
        sem = asyncio.Semaphore(BATCH_CONCURRENCY)
        tasks = [_create_prediction_with_semaphore(sem, single, d) for d, single in singles]
        results = await asyncio.gather(*tasks, return_exceptions=False)

        predictions = []
        fallback = {
            "predicted_covers": 0,
            "confidence": 0.0,
            "accuracy_metrics": {"prediction_interval": [0, 0]},
            "staff_recommendation": {},
        }
        for (date_str, result) in results:
            if isinstance(result, Exception):
                logger.warning(f"[PREDICT/BATCH] Skip date {date_str}: {result}")
                _write_debug_log(f"[PREDICT/BATCH] Skip date {date_str}: {result}")
                predictions.append({"date": date_str, "service_date": date_str, **fallback})
            else:
                predictions.append(result)

        logger.info(f"[PREDICT/BATCH] Success: {len(predictions)} predictions generated")
        _write_debug_log(f"[PREDICT/BATCH] Success: {len(predictions)} predictions generated")
        
        return {
            "predictions": predictions,
            "count": len(predictions),
            "service_type": request.service_type,
            "restaurant_id": request.restaurant_id,
        }
    except Exception as e:
        error_detail = str(e).encode('utf-8', errors='replace').decode('utf-8', errors='replace')
        logger.error(f"[PREDICT/BATCH] Error: {error_detail}")
        _write_debug_log(f"[PREDICT/BATCH] Error: {error_detail}")
        raise HTTPException(status_code=500, detail=f"Batch prediction failed: {error_detail}")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=8000)
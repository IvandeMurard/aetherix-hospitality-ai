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

# Initialize Prophet engine after logger is configured
_init_prophet_engine()

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
from backend.agents.reasoning_engine import get_reasoning_engine
from backend.ml.prediction_engine import get_prediction_engine
from backend.api.prediction_store import store_prediction_for_feedback

# Initialize Prophet engine at startup (load model if available)
_prophet_engine = None
_prophet_model_path = Path(__file__).parent / "ml" / "models" / "prophet_model.json"

def _init_prophet_engine():
    """Initialize Prophet engine and load model if available"""
    global _prophet_engine
    import logging
    logger = logging.getLogger("uvicorn")
    try:
        engine = get_prediction_engine()
        if _prophet_model_path.exists():
            logger.info(f"[PROPHET] Loading model from {_prophet_model_path}")
            engine.load_model(str(_prophet_model_path))
            _prophet_engine = engine
            logger.info("[PROPHET] Model loaded successfully")
        else:
            logger.warning(f"[PROPHET] Model file not found: {_prophet_model_path}")
            logger.warning("[PROPHET] Will fallback to RAG-based prediction")
            _prophet_engine = None
    except Exception as e:
        logger.error(f"[PROPHET] Failed to initialize engine: {e}")
        _prophet_engine = None

# Initialize Prophet engine (will be called after app creation)
# Note: Called after logger is configured in main.py

def _map_weather_to_score(weather: dict) -> float:
    """Map weather condition to weather_score (0-1, 1 = bad weather)"""
    condition = weather.get("condition", "").lower()
    if condition in ["rain", "heavy rain", "snow"]:
        return 0.9
    elif condition == "cloudy":
        return 0.5
    else:
        return 0.1

def _map_events_to_impact(events: list) -> float:
    """Map events to event_impact (0-1, 1 = major event)"""
    if not events or len(events) == 0:
        return 0.0
    # Impact based on number of events
    return min(1.0, len(events) * 0.3)

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
        
        # Get demand predictor for context and RAG
        predictor = get_demand_predictor()
        
        # Fetch external context (weather, events)
        context = await predictor._fetch_external_context(request)
        logger.info(f"[PREDICT] Context: {context.get('day_type')}, {len(context.get('events', []))} events")
        
        # Use Prophet if available, otherwise fallback to RAG
        if _prophet_engine and _prophet_engine.is_trained:
            logger.info("[PREDICT] Using Prophet for calculation")
            
            # Map context to Prophet features
            features = {
                "weather_score": _map_weather_to_score(context.get("weather", {})),
                "event_impact": _map_events_to_impact(context.get("events", []))
            }
            
            # Prophet prediction
            date_str = request.service_date.strftime("%Y-%m-%d")
            prophet_result = _prophet_engine.predict(date_str, features)
            
            predicted_covers = prophet_result.predicted
            confidence = prophet_result.confidence
            range_low = prophet_result.lower
            range_high = prophet_result.upper
            
            logger.info(f"[PREDICT] Prophet result: {predicted_covers} covers (confidence: {confidence:.2%})")
            
            # Get RAG patterns for explanation context
            similar_patterns = await predictor._find_similar_patterns(request, context)
            logger.info(f"[PREDICT] Found {len(similar_patterns)} similar patterns from RAG")
            
            # Generate explanation with Claude (using Prophet result + RAG patterns)
            reasoning_engine = get_reasoning_engine()
            reasoning_data = await reasoning_engine.generate_explanation(
                predicted_covers=predicted_covers,
                range_min=range_low,
                range_max=range_high,
                confidence=confidence,
                date=date_str,
                weather=context.get("weather", {}),
                events=context.get("events", []),
                features=features,
                patterns=similar_patterns,
                day_of_week=context.get("day_of_week"),
                service_type=request.service_type.value if hasattr(request.service_type, 'value') else str(request.service_type)
            )
            
            # Calculate staff recommendation
            from backend.agents.staff_recommender import StaffRecommenderAgent
            staff_recommender = StaffRecommenderAgent()
            staff_result = await staff_recommender.recommend(
                predicted_covers=predicted_covers,
                restaurant_id=request.restaurant_id
            )
            
            # Build result dict compatible with existing code
            result = {
                "predicted_covers": predicted_covers,
                "confidence": confidence,
                "reasoning": reasoning_data,
                "staff_recommendation": staff_result,
                "accuracy_metrics": {
                    "method": "prophet",
                    "estimated_mape": None,
                    "prediction_interval": [range_low, range_high],
                    "patterns_analyzed": len(similar_patterns),
                    "note": "Prophet time-series forecast"
                }
            }
            
        else:
            # Fallback to RAG-based prediction
            logger.warning("[PREDICT] Prophet not available, using RAG fallback")
            result = await predictor.predict(request)
        
        logger.info(f"[PREDICT] Result: {result.get('predicted_covers')} covers")
        
        # Extract reasoning from result (Prophet or RAG)
        reasoning_data = result.get("reasoning", {})
        patterns_from_result = reasoning_data.get("patterns_used", [])
        
        # Convert Pattern objects to list for Reasoning schema
        patterns_for_reasoning = []
        if patterns_from_result:
            for p in patterns_from_result[:3]:
                if isinstance(p, dict):
                    # Already a dict, convert to Pattern if needed
                    from backend.models.schemas import Pattern
                    try:
                        patterns_for_reasoning.append(Pattern(**p))
                    except:
                        pass
                elif hasattr(p, 'date'):
                    patterns_for_reasoning.append(p)
        
        reasoning = Reasoning(
            summary=reasoning_data.get("summary", f"{int(result['confidence']*100)}% confidence"),
            patterns_used=patterns_for_reasoning,
            confidence_factors=reasoning_data.get("confidence_factors", ["Historical patterns"])
        )
        
        # Create StaffRecommendation object
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

async def _create_prediction_batch_prophet(
    dates: list[str],
    request: BatchPredictionRequest,
    predictor
) -> list:
    """Create batch predictions using Prophet predict_batch"""
    if not _prophet_engine or not _prophet_engine.is_trained:
        return None  # Fallback to individual calls
    
    logger.info(f"[PREDICT/BATCH] Using Prophet batch prediction for {len(dates)} dates")
    
    # Build features per date
    features_per_date = {}
    for date_str in dates:
        try:
            service_date = date.fromisoformat(date_str)
            single_request = PredictionRequest(
                restaurant_id=request.restaurant_id,
                service_date=service_date,
                service_type=ServiceType(request.service_type.lower())
            )
            context = await predictor._fetch_external_context(single_request)
            features_per_date[date_str] = {
                "weather_score": _map_weather_to_score(context.get("weather", {})),
                "event_impact": _map_events_to_impact(context.get("events", []))
            }
        except Exception as e:
            logger.warning(f"[PREDICT/BATCH] Failed to get context for {date_str}: {e}")
            features_per_date[date_str] = {}
    
    # Prophet batch prediction
    prophet_results = _prophet_engine.predict_batch(dates, features_per_date)
    
    # Convert to response format (still need RAG + Claude per date for explanation)
    predictions = []
    for date_str, prophet_result in zip(dates, prophet_results):
        try:
            service_date = date.fromisoformat(date_str)
            single_request = PredictionRequest(
                restaurant_id=request.restaurant_id,
                service_date=service_date,
                service_type=ServiceType(request.service_type.lower())
            )
            context = await predictor._fetch_external_context(single_request)
            similar_patterns = await predictor._find_similar_patterns(single_request, context)
            
            # Generate explanation
            reasoning_engine = get_reasoning_engine()
            reasoning_data = await reasoning_engine.generate_explanation(
                predicted_covers=prophet_result.predicted,
                range_min=prophet_result.lower,
                range_max=prophet_result.upper,
                confidence=prophet_result.confidence,
                date=date_str,
                weather=context.get("weather", {}),
                events=context.get("events", []),
                features=features_per_date.get(date_str, {}),
                patterns=similar_patterns,
                day_of_week=context.get("day_of_week"),
                service_type=request.service_type
            )
            
            # Build response (simplified, will be converted to PredictionResponse in batch endpoint)
            predictions.append({
                "date": date_str,
                "service_date": date_str,
                "predicted_covers": prophet_result.predicted,
                "confidence": prophet_result.confidence,
                "reasoning": reasoning_data,
                "accuracy_metrics": {
                    "method": "prophet",
                    "prediction_interval": [prophet_result.lower, prophet_result.upper]
                }
            })
        except Exception as e:
            logger.warning(f"[PREDICT/BATCH] Failed for {date_str}: {e}")
            predictions.append({
                "date": date_str,
                "service_date": date_str,
                "predicted_covers": 0,
                "confidence": 0.0,
                "accuracy_metrics": {"prediction_interval": [0, 0]}
            })
    
    return predictions


@app.post("/predict/batch")
async def create_prediction_batch(request: BatchPredictionRequest):
    """
    Generate predictions for multiple dates at once.
    Uses Prophet batch prediction if available, otherwise falls back to parallel individual calls.
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

        # Try Prophet batch first if available
        predictor = get_demand_predictor()
        prophet_batch_results = await _create_prediction_batch_prophet(dates, request, predictor)
        
        if prophet_batch_results:
            # Use Prophet batch results
            logger.info(f"[PREDICT/BATCH] Using Prophet batch results")
            predictions = []
            for batch_result in prophet_batch_results:
                # Convert to full PredictionResponse format
                try:
                    service_date = date.fromisoformat(batch_result["date"])
                    single_request = PredictionRequest(
                        restaurant_id=request.restaurant_id,
                        service_date=service_date,
                        service_type=st_enum
                    )
                    # Get staff recommendation
                    from backend.agents.staff_recommender import StaffRecommenderAgent
                    staff_recommender = StaffRecommenderAgent()
                    staff_result = await staff_recommender.recommend(
                        predicted_covers=batch_result["predicted_covers"],
                        restaurant_id=request.restaurant_id
                    )
                    
                    # Build full response
                    reasoning_data = batch_result.get("reasoning", {})
                    patterns_from_result = reasoning_data.get("patterns_used", [])
                    patterns_for_reasoning = []
                    if patterns_from_result:
                        for p in patterns_from_result[:3]:
                            if isinstance(p, dict):
                                from backend.models.schemas import Pattern
                                try:
                                    patterns_for_reasoning.append(Pattern(**p))
                                except:
                                    pass
                            elif hasattr(p, 'date'):
                                patterns_for_reasoning.append(p)
                    
                    reasoning = Reasoning(
                        summary=reasoning_data.get("summary", f"{int(batch_result['confidence']*100)}% confidence"),
                        patterns_used=patterns_for_reasoning,
                        confidence_factors=reasoning_data.get("confidence_factors", [])
                    )
                    
                    accuracy_data = batch_result.get("accuracy_metrics", {})
                    accuracy_metrics = None
                    if accuracy_data:
                        if "prediction_interval" in accuracy_data and accuracy_data["prediction_interval"]:
                            if isinstance(accuracy_data["prediction_interval"], tuple):
                                accuracy_data["prediction_interval"] = list(accuracy_data["prediction_interval"])
                        accuracy_metrics = AccuracyMetrics(**accuracy_data)
                    
                    staff_recommendation = StaffRecommendation(
                        servers=StaffDelta(
                            recommended=staff_result.get("servers", {}).get("recommended", 7),
                            usual=staff_result.get("servers", {}).get("usual", 7),
                            delta=staff_result.get("servers", {}).get("delta", 0)
                        ),
                        hosts=StaffDelta(
                            recommended=staff_result.get("hosts", {}).get("recommended", 2),
                            usual=staff_result.get("hosts", {}).get("usual", 2),
                            delta=staff_result.get("hosts", {}).get("delta", 0)
                        ),
                        kitchen=StaffDelta(
                            recommended=staff_result.get("kitchen", {}).get("recommended", 3),
                            usual=staff_result.get("kitchen", {}).get("usual", 3),
                            delta=staff_result.get("kitchen", {}).get("delta", 0)
                        ),
                        rationale=staff_result.get("rationale", ""),
                        covers_per_staff=staff_result.get("covers_per_staff", 0.0)
                    )
                    
                    predictions.append({
                        "date": batch_result["date"],
                        "service_date": batch_result["service_date"],
                        "predicted_covers": batch_result["predicted_covers"],
                        "confidence": batch_result["confidence"],
                        "reasoning": reasoning,
                        "staff_recommendation": staff_recommendation,
                        "accuracy_metrics": accuracy_metrics
                    })
                except Exception as e:
                    logger.warning(f"[PREDICT/BATCH] Failed to format result for {batch_result.get('date')}: {e}")
                    predictions.append({
                        "date": batch_result.get("date", ""),
                        "service_date": batch_result.get("service_date", ""),
                        "predicted_covers": 0,
                        "confidence": 0.0,
                        "accuracy_metrics": {"prediction_interval": [0, 0]}
                    })
        else:
            # Fallback to parallel individual calls
            logger.info(f"[PREDICT/BATCH] Using parallel individual calls (Prophet not available)")
            
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
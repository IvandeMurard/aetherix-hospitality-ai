# -*- coding: utf-8 -*-
"""
F&B Agent API Routes
Week 1: Restaurant Profile + Predictions Storage
"""

from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import date, datetime
from uuid import UUID
import os
from supabase import create_client, Client

# ============================================
# SUPABASE CLIENT
# ============================================

def get_supabase() -> Client:
    url = os.environ.get("SUPABASE_URL")
    key = os.environ.get("SUPABASE_KEY")
    if not url or not key:
        raise HTTPException(500, "Supabase not configured")
    
    # Workaround for SSL certificate issues on Windows (local dev only)
    # Set SUPABASE_SSL_VERIFY=false in .env to disable SSL verification
    ssl_verify = os.environ.get("SUPABASE_SSL_VERIFY", "true").lower() not in ("false", "0", "no")
    
    if not ssl_verify:
        import ssl
        # Disable SSL verification globally (local dev only!)
        ssl._create_default_https_context = ssl._create_unverified_context
    
    return create_client(url, key)

# ============================================
# SCHEMAS
# ============================================

class RestaurantProfileCreate(BaseModel):
    name: str
    service_style: str = "casual"
    is_hotel_restaurant: bool = True
    total_seats: int = 60
    turns_breakfast: float = 1.0
    turns_lunch: float = 1.5
    turns_dinner: float = 1.2
    breakeven_covers: int = 25
    target_covers: int = 45
    avg_ticket: Optional[float] = 35.00
    labor_cost_target: float = 0.30
    covers_per_server: int = 20
    covers_per_host: int = 60
    covers_per_busser: int = 40
    covers_per_kitchen: int = 30
    min_foh_staff: int = 2
    min_boh_staff: int = 2
    rate_server: float = 15.00
    rate_host: float = 13.00
    rate_busser: float = 12.00
    rate_kitchen: float = 16.00

class RestaurantProfileResponse(RestaurantProfileCreate):
    id: UUID
    created_at: datetime
    updated_at: datetime

class PredictionFactor(BaseModel):
    name: str
    value: float
    impact_pct: float
    description: Optional[str] = None

class SimilarPattern(BaseModel):
    date: str
    covers: int
    similarity: float
    day_of_week: Optional[str] = None

class PredictionCreate(BaseModel):
    restaurant_id: UUID
    service_date: date
    service_type: str
    predicted_covers: int
    confidence: float
    range_low: int
    range_high: int
    estimated_mape: Optional[float] = None
    factors: List[PredictionFactor] = []
    similar_patterns: List[SimilarPattern] = []

class PredictionResponse(PredictionCreate):
    id: UUID
    created_at: datetime

class FeedbackCreate(BaseModel):
    prediction_id: str  # UUID as string (from /predict response)
    restaurant_id: str  # String like "hotel_main" - will be converted
    feedback_type: str  # 'pre_service' or 'post_service'
    
    # Pre-service
    pre_validation: Optional[str] = None  # 'accurate', 'higher', 'lower'
    pre_reasons: List[str] = []
    pre_adjusted_covers: Optional[int] = None
    
    # Post-service
    actual_covers: Optional[int] = None
    staff_foh_used: Optional[int] = None
    staff_boh_used: Optional[int] = None
    staff_rating: Optional[str] = None  # 'understaffed', 'optimal', 'overstaffed'
    notes: Optional[str] = None

class FeedbackResponse(FeedbackCreate):
    id: UUID
    accuracy_pct: Optional[float] = None
    within_range: Optional[bool] = None
    created_at: datetime

# ============================================
# ROUTER
# ============================================

router = APIRouter(prefix="/api", tags=["F&B Agent"])

# --- Restaurant Profile ---

@router.get("/restaurant/profile", response_model=RestaurantProfileResponse)
async def get_restaurant_profile(supabase: Client = Depends(get_supabase)):
    """Get the first restaurant profile (single-tenant for MVP)"""
    result = supabase.table("restaurant_profile").select("*").limit(1).execute()
    if not result.data:
        raise HTTPException(404, "No restaurant profile found")
    return result.data[0]

@router.post("/restaurant/profile", response_model=RestaurantProfileResponse)
async def create_restaurant_profile(
    profile: RestaurantProfileCreate,
    supabase: Client = Depends(get_supabase)
):
    """Create or update restaurant profile"""
    # Check if exists
    existing = supabase.table("restaurant_profile").select("id").limit(1).execute()
    
    if existing.data:
        # Update existing
        result = supabase.table("restaurant_profile")\
            .update(profile.model_dump())\
            .eq("id", existing.data[0]["id"])\
            .execute()
    else:
        # Create new
        result = supabase.table("restaurant_profile")\
            .insert(profile.model_dump())\
            .execute()
    
    return result.data[0]

@router.get("/restaurant/defaults")
async def get_industry_defaults():
    """Return industry standard defaults for restaurant configuration"""
    return {
        "casual_dining": {
            "covers_per_server": 20,
            "covers_per_host": 60,
            "covers_per_busser": 40,
            "covers_per_kitchen": 30,
            "turns_lunch": 1.5,
            "turns_dinner": 1.2,
            "labor_cost_target": 0.30
        },
        "fine_dining": {
            "covers_per_server": 12,
            "covers_per_host": 40,
            "covers_per_busser": 25,
            "covers_per_kitchen": 20,
            "turns_lunch": 1.0,
            "turns_dinner": 1.0,
            "labor_cost_target": 0.35
        },
        "fast_casual": {
            "covers_per_server": 35,
            "covers_per_host": 100,
            "covers_per_busser": 60,
            "covers_per_kitchen": 40,
            "turns_lunch": 2.5,
            "turns_dinner": 2.0,
            "labor_cost_target": 0.25
        }
    }

# --- Predictions ---

@router.post("/predictions", response_model=PredictionResponse)
async def store_prediction(
    prediction: PredictionCreate,
    supabase: Client = Depends(get_supabase)
):
    """Store a prediction for feedback tracking"""
    data = prediction.model_dump()
    data["service_date"] = str(data["service_date"])
    data["restaurant_id"] = str(data["restaurant_id"])
    data["factors"] = [f.model_dump() if hasattr(f, 'model_dump') else f for f in data["factors"]]
    data["similar_patterns"] = [p.model_dump() if hasattr(p, 'model_dump') else p for p in data["similar_patterns"]]
    
    result = supabase.table("predictions").insert(data).execute()
    return result.data[0]

@router.get("/predictions/{prediction_id}", response_model=PredictionResponse)
async def get_prediction(
    prediction_id: UUID,
    supabase: Client = Depends(get_supabase)
):
    """Get a specific prediction"""
    result = supabase.table("predictions")\
        .select("*")\
        .eq("id", str(prediction_id))\
        .execute()
    if not result.data:
        raise HTTPException(404, "Prediction not found")
    return result.data[0]

# --- Feedback ---

@router.post("/feedback", response_model=FeedbackResponse)
async def submit_feedback(
    feedback: FeedbackCreate,
    supabase: Client = Depends(get_supabase)
):
    """Submit pre-service or post-service feedback"""
    import logging
    from backend.api.prediction_store import convert_restaurant_id

    logger = logging.getLogger(__name__)

    # prediction_id must be a valid UUID (stored in Supabase). "pred_xxx" means storage failed.
    if feedback.prediction_id.startswith("pred_"):
        raise HTTPException(
            status_code=400,
            detail="Prediction was not stored (Supabase tables may be missing or storage failed). "
            "Ensure predictions and user_feedback tables exist. Re-run the prediction to try again."
        )

    data = feedback.model_dump()
    data["prediction_id"] = feedback.prediction_id
    data["restaurant_id"] = convert_restaurant_id(feedback.restaurant_id)

    try:
        result = supabase.table("user_feedback").insert(data).execute()
        if not result.data:
            raise HTTPException(status_code=500, detail="Insert returned no data")
        return result.data[0]
    except Exception as e:
        logger.exception(f"[FEEDBACK] Insert failed: {e}")
        err_msg = str(e)
        if "foreign key" in err_msg.lower() or "violates" in err_msg.lower():
            raise HTTPException(
                status_code=400,
                detail="Invalid prediction_id or prediction not found. The prediction may have expired."
            )
        raise HTTPException(status_code=500, detail=f"Failed to save feedback: {err_msg}")

@router.get("/feedback/prediction/{prediction_id}")
async def get_prediction_feedback(
    prediction_id: UUID,
    supabase: Client = Depends(get_supabase)
):
    """Get all feedback for a prediction"""
    result = supabase.table("user_feedback")\
        .select("*")\
        .eq("prediction_id", str(prediction_id))\
        .order("created_at", desc=True)\
        .execute()
    return result.data

# --- Accuracy (Week 3, but endpoint ready) ---

@router.get("/accuracy/summary")
async def get_accuracy_summary(
    days: int = 7,
    supabase: Client = Depends(get_supabase)
):
    """Get accuracy summary for last N days"""
    # Get feedbacks with accuracy
    result = supabase.table("user_feedback")\
        .select("accuracy_pct, within_range, created_at")\
        .not_.is_("accuracy_pct", "null")\
        .order("created_at", desc=True)\
        .limit(100)\
        .execute()
    
    if not result.data:
        return {
            "period_days": days,
            "feedbacks_count": 0,
            "avg_accuracy": None,
            "within_range_pct": None,
            "message": "No feedback data yet. Submit actual covers to start tracking."
        }
    
    feedbacks = result.data
    accuracies = [f["accuracy_pct"] for f in feedbacks if f["accuracy_pct"]]
    within_range = [f["within_range"] for f in feedbacks if f["within_range"] is not None]
    
    return {
        "period_days": days,
        "feedbacks_count": len(feedbacks),
        "avg_accuracy": sum(accuracies) / len(accuracies) if accuracies else None,
        "within_range_pct": (sum(within_range) / len(within_range) * 100) if within_range else None
    }

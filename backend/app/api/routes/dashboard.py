from fastapi import APIRouter, Depends, HTTPException
from typing import Dict, Any, List
from app.core.security import get_current_user
from app.db.session import get_db
from app.db.models import RestaurantProfile, PMSSyncLog, RecommendationCache
from sqlalchemy.future import select
from sqlalchemy.ext.asyncio import AsyncSession
from datetime import date, timedelta

router = APIRouter(prefix="/dashboard", tags=["dashboard"])

@router.get("/metrics")
async def get_dashboard_metrics(
    current_user: Dict[str, Any] = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Fetches key metrics for the dashboard, isolated by tenant.
    """
    # Fetch property for this user
    result = await db.execute(
        select(RestaurantProfile).where(RestaurantProfile.owner_id == current_user["id"])
    )
    profile = result.scalars().first()
    
    if not profile:
        return {
            "occupancy": 0,
            "revenue": 0,
            "property_name": "No property linked",
            "recommendations_count": 0
        }

    # Fetch latest sync log
    sync_result = await db.execute(
        select(PMSSyncLog)
        .where(PMSSyncLog.tenant_id == profile.tenant_id)
        .order_by(PMSSyncLog.sync_date.desc())
        .limit(1)
    )
    latest_sync = sync_result.scalars().first()

    # Fetch pending recommendations
    rec_result = await db.execute(
        select(RecommendationCache)
        .where(RecommendationCache.tenant_id == profile.tenant_id)
        .where(RecommendationCache.is_pushed == False)
    )
    pending_recs = rec_result.scalars().all()

    return {
        "property_id": profile.tenant_id,
        "property_name": profile.property_name,
        "occupancy": latest_sync.occupancy if latest_sync else 0,
        "revenue": latest_sync.fb_revenue if latest_sync else 0,
        "last_sync_date": latest_sync.sync_date.isoformat() if latest_sync else None,
        "pending_recommendations": len(pending_recs)
    }

@router.get("/recommendations")
async def get_dashboard_recommendations(
    current_user: Dict[str, Any] = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Fetches the latest staffing recommendations for the dashboard.
    """
    result = await db.execute(
        select(RestaurantProfile).where(RestaurantProfile.owner_id == current_user["id"])
    )
    profile = result.scalars().first()
    
    if not profile:
        return []

    rec_result = await db.execute(
        select(RecommendationCache)
        .where(RecommendationCache.tenant_id == profile.tenant_id)
        .order_by(RecommendationCache.target_date.asc())
        .limit(5)
    )
    recommendations = rec_result.scalars().all()

    return [
        {
            "id": r.id,
            "date": r.target_date.isoformat(),
            "recommendation": r.staffing_recommendation,
            "reasoning": r.reasoning_summary,
            "is_pushed": r.is_pushed
        }
        for r in recommendations
    ]

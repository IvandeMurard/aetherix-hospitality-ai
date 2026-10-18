from typing import Any, Dict, Optional

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

from app.core.security import get_current_user
from app.db.models import PMSSyncLog, RecommendationCache, RestaurantProfile
from app.db.session import get_db

router = APIRouter(prefix="/dashboard", tags=["dashboard"])


def sync_metrics(log: Optional[PMSSyncLog]) -> Dict[str, Any]:
    """The figures of one sync row as reported by the PMS, or null (HOS-352).
    Rows from before HOS-352 have no room counts: their occupancy is null."""
    if log is None:
        return {"occupancy": None, "rooms_sold": None, "rooms_available": None, "occupancy_status": None,
                "revenue": None, "revenue_currency": None, "revenue_status": None}
    rate = None
    if log.rooms_sold is not None and log.rooms_available:
        rate = round(log.rooms_sold / log.rooms_available * 100)
    return {
        "occupancy": rate,
        "rooms_sold": log.rooms_sold,
        "rooms_available": log.rooms_available,
        "occupancy_status": log.occupancy_status,
        "revenue": log.fb_revenue if log.fb_revenue_status in ("ok", "fixture") else None,
        "revenue_currency": log.fb_revenue_currency,
        "revenue_status": log.fb_revenue_status,
    }

@router.get("/metrics")
async def get_dashboard_metrics(
    current_user: Dict[str, Any] = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Fetches key metrics for the dashboard, isolated by tenant.

    HOS-352: ``occupancy`` is a whole-number percentage computed from the
    rooms the PMS reported; ``occupancy`` and ``revenue`` are ``null`` when the
    PMS gave no figure (the ``*_status`` fields say why), never 0.
    """
    # Fetch property for this user
    result = await db.execute(
        select(RestaurantProfile).where(RestaurantProfile.owner_id == current_user["id"])
    )
    profile = result.scalars().first()

    if not profile:
        return {
            "occupancy": None,
            "revenue": None,
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
        .where(RecommendationCache.is_pushed.is_(False))
    )
    pending_recs = rec_result.scalars().all()

    return {
        "property_id": profile.tenant_id,
        "property_name": profile.property_name,
        **sync_metrics(latest_sync),
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

"""Captation baseline endpoints.

Story 2.4 — Calculate Baseline Captation Rates.

GET  /baselines/{tenant_id}          — retrieve the current baseline.
POST /baselines/{tenant_id}/recalculate — trigger a (re)calculation.
"""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import get_current_user
from app.db.session import get_db
from app.services.captation_service import CaptationService, InsufficientDataError

router = APIRouter(prefix="/baselines", tags=["baselines"])
_service = CaptationService()


@router.get("/{tenant_id}")
async def get_baseline(
    tenant_id: str,
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Return the stored captation baseline for *tenant_id*."""
    baseline = await _service.get_baseline(tenant_id, db)
    if baseline is None:
        raise HTTPException(
            status_code=404,
            detail=f"No captation baseline found for tenant '{tenant_id}'. "
                   "Trigger /recalculate once enough PMS data has been ingested.",
        )
    return {
        "tenant_id": baseline.tenant_id,
        "period_start": baseline.period_start.isoformat(),
        "period_end": baseline.period_end.isoformat(),
        "avg_fb_revenue_per_room": baseline.avg_fb_revenue_per_room,
        "dow_factors": baseline.dow_factors,
        "monthly_factors": baseline.monthly_factors,
        "data_points_count": baseline.data_points_count,
        "computed_at": baseline.computed_at.isoformat(),
    }


@router.post("/{tenant_id}/recalculate", status_code=200)
async def recalculate_baseline(
    tenant_id: str,
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """(Re)calculate the captation baseline from all historical PMS sync data."""
    try:
        baseline = await _service.calculate_baseline(tenant_id, db)
    except InsufficientDataError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc

    return {
        "status": "recalculated",
        "tenant_id": baseline.tenant_id,
        "avg_fb_revenue_per_room": baseline.avg_fb_revenue_per_room,
        "data_points_count": baseline.data_points_count,
        "computed_at": baseline.computed_at.isoformat(),
    }

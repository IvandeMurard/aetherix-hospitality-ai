"""Learning loop review — ADR-0007 §18.5 (Décision #40).

Nothing the learning loop proposes is applied until a named person approves
it here. Tenant-scoped via ``tenant_scope.require_user_owns_tenant`` (owner
or superuser); calibration, eval cases, policy and upstream-filter items are
Ivan's (superuser) only — enforced in ``learning_store``.

GET  /hotels/{tenant_id}/learning/report                   arm C report (read-only, computed now)
GET  /hotels/{tenant_id}/learning/items[?status=]          review queue
POST /hotels/{tenant_id}/learning/items/{item_id}/approve  {note?, case?} → applies
POST /hotels/{tenant_id}/learning/items/{item_id}/reject   {note?}
POST /hotels/{tenant_id}/learning/items/{item_id}/rollback applied parameter proposal → replaced value
POST /hotels/{tenant_id}/learning/calibration/rollback     {forecaster?} → previous version
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.tenant_scope import require_user_owns_tenant
from app.core.security import get_current_user
from app.db.session import get_db
from app.services import forecast_calibration as fc
from app.services import learning_loop as ll
from app.services import learning_store as ls
from app.services.risk_assessment import ANOMALY_FORECASTER

router = APIRouter(prefix="/hotels", tags=["learning"])


class Decision(BaseModel):
    note: Optional[str] = Field(None, max_length=1000)
    case: Optional[dict[str, Any]] = Field(None, description="eval_case only: the reviewer-written case")


class Rollback(BaseModel):
    forecaster: str = ANOMALY_FORECASTER


def _http(exc: ls.LearningError) -> HTTPException:
    return HTTPException(status_code=exc.status, detail=exc.detail)


@router.get("/{tenant_id}/learning/report")
async def get_report(
    tenant_id: str, lookback_days: int = 180,
    current_user: dict = Depends(get_current_user), db: AsyncSession = Depends(get_db),
):
    await require_user_owns_tenant(db, current_user, tenant_id)
    lookback_days = max(1, min(int(lookback_days), 730))
    rows = await ls.recommendation_rows(db, tenant_id, datetime.now(timezone.utc) - timedelta(days=lookback_days))
    report = ll.risk_statement_calibration(rows)
    return {
        "tenant_id": tenant_id,
        "rows": len(rows),
        "risk_calibration": report,
        "alerts": ll.miscalibration_alerts(report),
        "interval_coverage": fc.realised_coverage([{**r, **ls.stored_interval(r)} for r in rows]),
    }


@router.get("/{tenant_id}/learning/items")
async def get_items(
    tenant_id: str, status: Optional[str] = None,
    current_user: dict = Depends(get_current_user), db: AsyncSession = Depends(get_db),
):
    await require_user_owns_tenant(db, current_user, tenant_id)
    return {"tenant_id": tenant_id, "items": await ls.list_items(db, tenant_id, status)}


async def _decide(tenant_id, item_id, body, approve, current_user, db):
    await require_user_owns_tenant(db, current_user, tenant_id)
    try:
        out = await ls.decide(db, tenant_id, item_id, approve=approve, actor=current_user,
                              note=body.note, case=body.case)
    except ls.LearningError as exc:
        raise _http(exc) from exc
    await db.commit()
    return out


@router.post("/{tenant_id}/learning/items/{item_id}/approve")
async def approve(
    tenant_id: str, item_id: str, body: Decision,
    current_user: dict = Depends(get_current_user), db: AsyncSession = Depends(get_db),
):
    return await _decide(tenant_id, item_id, body, True, current_user, db)


@router.post("/{tenant_id}/learning/items/{item_id}/reject")
async def reject(
    tenant_id: str, item_id: str, body: Decision,
    current_user: dict = Depends(get_current_user), db: AsyncSession = Depends(get_db),
):
    return await _decide(tenant_id, item_id, body, False, current_user, db)


@router.post("/{tenant_id}/learning/items/{item_id}/rollback")
async def rollback_item(
    tenant_id: str, item_id: str,
    current_user: dict = Depends(get_current_user), db: AsyncSession = Depends(get_db),
):
    """An applied parameter proposal → the value it replaced (HOS-344)."""
    await require_user_owns_tenant(db, current_user, tenant_id)
    try:
        out = await ls.rollback_parameter(db, tenant_id, item_id, current_user)
    except ls.LearningError as exc:
        raise _http(exc) from exc
    await db.commit()
    return out


@router.post("/{tenant_id}/learning/calibration/rollback")
async def rollback(
    tenant_id: str, body: Rollback,
    current_user: dict = Depends(get_current_user), db: AsyncSession = Depends(get_db),
):
    await require_user_owns_tenant(db, current_user, tenant_id)
    try:
        out = await ls.rollback_calibration(db, tenant_id, body.forecaster, current_user)
    except ls.LearningError as exc:
        raise _http(exc) from exc
    await db.commit()
    return out

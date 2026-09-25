"""Per-hotel decision parameters — costs, labour constraints, commit offsets.

ADR-0007 §18.3 (Décision #40). Dashboard users set their own hotel's values;
every write records who set it and when (append-only). Tenant-scoped through
``app/api/tenant_scope.require_user_owns_tenant`` (owner or superuser, 403
otherwise, no enumeration).

GET  /hotels/{tenant_id}/decision-parameters              values in force + catalog
GET  /hotels/{tenant_id}/decision-parameters/history      every change, newest first
PUT  /hotels/{tenant_id}/decision-parameters/{parameter}  set (value) or clear (null)
"""
from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.tenant_scope import require_user_owns_tenant
from app.core.security import get_current_user
from app.db.session import get_db
from app.services import hotel_parameters as hp

router = APIRouter(prefix="/hotels", tags=["hotel-parameters"])


class ParameterWrite(BaseModel):
    value: Optional[float] = Field(None, description="null clears the parameter")
    note: Optional[str] = Field(None, max_length=500)


@router.get("/{tenant_id}/decision-parameters")
async def get_parameters(
    tenant_id: str,
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    await require_user_owns_tenant(db, current_user, tenant_id)
    params = await hp.load(db, tenant_id)
    return {**params.as_dict(), "catalog": hp.catalog_as_dict()}


@router.get("/{tenant_id}/decision-parameters/history")
async def get_history(
    tenant_id: str,
    parameter: Optional[str] = None,
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    await require_user_owns_tenant(db, current_user, tenant_id)
    return {"tenant_id": tenant_id, "history": await hp.history(db, tenant_id, parameter)}


@router.put("/{tenant_id}/decision-parameters/{parameter}")
async def put_parameter(
    tenant_id: str,
    parameter: str,
    body: ParameterWrite,
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    await require_user_owns_tenant(db, current_user, tenant_id)
    try:
        row = await hp.set_parameter(
            db, tenant_id, parameter, body.value,
            set_by=str(current_user.get("email") or current_user.get("id") or ""),
            set_via="dashboard_api",
            note=body.note,
        )
    except hp.ParameterError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    await db.commit()
    return row

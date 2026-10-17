"""Hotel data ownership — HOS-346 (Décision #43).

The hotel can see, export and delete everything Aetherix holds about it, and
decides whether it contributes to the Hive. Owner of the tenant or superuser
(``tenant_scope.require_user_owns_tenant``); 403 otherwise, without saying
whether the other tenant exists.

GET  /hotels/{tenant_id}/data/export          everything about the hotel (JSON)
GET  /hotels/{tenant_id}/data/deletion-plan   ordered steps + dry-run row counts
POST /hotels/{tenant_id}/data/deletion        {confirm_tenant_id, dry_run=true}
GET  /hotels/{tenant_id}/hive-consent         consent in force + history
PUT  /hotels/{tenant_id}/hive-consent         {opted_in, note?}
"""
from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.tenant_scope import require_user_owns_tenant
from app.core.security import get_current_user
from app.db.session import get_db
from app.services import hive_gate
from app.services import hotel_data

router = APIRouter(prefix="/hotels", tags=["hotel-data"])


class DeletionRequest(BaseModel):
    confirm_tenant_id: str = Field(..., description="Type the tenant id to confirm.")
    dry_run: bool = Field(True, description="True (default): report what would be deleted, delete nothing.")


class ConsentRequest(BaseModel):
    opted_in: bool
    note: Optional[str] = Field(None, max_length=500)


def _who(current_user: dict) -> str:
    return str(current_user.get("email") or current_user.get("id") or "").strip()


@router.get("/{tenant_id}/data/export")
async def export_data(
    tenant_id: str, current_user: dict = Depends(get_current_user), db: AsyncSession = Depends(get_db),
):
    await require_user_owns_tenant(db, current_user, tenant_id)
    return await hotel_data.export_hotel_data(db, tenant_id)


@router.get("/{tenant_id}/data/deletion-plan")
async def deletion_plan(
    tenant_id: str, current_user: dict = Depends(get_current_user), db: AsyncSession = Depends(get_db),
):
    profile = await require_user_owns_tenant(db, current_user, tenant_id)
    steps = hotel_data.build_deletion_plan(tenant_id, getattr(profile, "pms_property_id", None))
    preview = await hotel_data.execute_deletion(db, tenant_id, dry_run=True)
    return {
        "tenant_id": tenant_id,
        "steps": [{"order": s.order, "table": s.table, "match": s.match, "rationale": s.rationale} for s in steps],
        "rows_that_would_be_deleted": preview.rows,
        "caveats": list(hotel_data.CAVEATS),
    }


@router.post("/{tenant_id}/data/deletion")
async def delete_data(
    tenant_id: str, body: DeletionRequest,
    current_user: dict = Depends(get_current_user), db: AsyncSession = Depends(get_db),
):
    await require_user_owns_tenant(db, current_user, tenant_id)
    if body.confirm_tenant_id != tenant_id:
        raise HTTPException(status_code=422, detail="confirm_tenant_id must equal the tenant id in the path")
    report = await hotel_data.execute_deletion(db, tenant_id, dry_run=body.dry_run)
    return report.as_dict()


@router.get("/{tenant_id}/hive-consent")
async def get_consent(
    tenant_id: str, current_user: dict = Depends(get_current_user), db: AsyncSession = Depends(get_db),
):
    await require_user_owns_tenant(db, current_user, tenant_id)
    return await hive_gate.consent_for(db, tenant_id)


@router.put("/{tenant_id}/hive-consent")
async def put_consent(
    tenant_id: str, body: ConsentRequest,
    current_user: dict = Depends(get_current_user), db: AsyncSession = Depends(get_db),
):
    await require_user_owns_tenant(db, current_user, tenant_id)
    row = await hive_gate.set_consent(
        db, tenant_id, body.opted_in, set_by=_who(current_user), set_via="dashboard_api", note=body.note,
    )
    await db.commit()
    return row

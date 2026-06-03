"""Receipt drill-down route — P2-6 (HOS-172).

GET /api/v1/receipts/{hotel_id}/{date}
  → Returns a ReceiptPayload (P2-1/P2-2 enriched) for the given hotel and date.
  → Auth: MCP bearer token with `receipts:read` scope (OQ3, Decision #15).
  → Used by the WhatsApp deep link and the Next.js web drill-down page.

Auth model: same `verify_bearer` plumbing as predictions.py — no fastapi-users.
Named dependency at module level (`_receipts_auth`) for test overrides.
"""
from __future__ import annotations

import logging
from datetime import date
from typing import Optional

from fastapi import APIRouter, Depends, Header, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.mcp_core import MCPAuthError, RECEIPTS_READ_SCOPE
from app.mcp_server import verify_bearer
from app.services.receipts import ReceiptPayload, ReceiptsService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/receipts", tags=["receipts"])


def _require_receipts_scope():
    """FastAPI dependency: validates bearer token with receipts:read scope."""
    async def _dep(
        authorization: Optional[str] = Header(None),
        db: AsyncSession = Depends(get_db),
    ):
        try:
            tok = await verify_bearer(authorization, db)
        except MCPAuthError as exc:
            raise HTTPException(
                status_code=exc.status,
                headers={"WWW-Authenticate": "Bearer"},
                detail=exc.detail,
            )
        if RECEIPTS_READ_SCOPE not in (tok.scopes or []):
            raise HTTPException(
                status_code=403,
                detail=f"Token missing required scope: {RECEIPTS_READ_SCOPE}",
            )
        return tok
    return _dep


# Named at module level so tests can apply dependency_overrides
_receipts_auth = _require_receipts_scope()


@router.get("/{hotel_id}/{receipt_date}", response_model=ReceiptPayload)
async def get_receipt(
    hotel_id: str,
    receipt_date: date,
    token=Depends(_receipts_auth),
    db: AsyncSession = Depends(get_db),
) -> ReceiptPayload:
    """Return the enriched ReceiptPayload for `hotel_id` on `receipt_date`.

    The token's hotel_id is not enforced here — the frontend passes the hotel_id
    from the deep link. For Phase 2 Sandbox (single-hotel), this is sufficient.
    Multi-hotel scoping will be added in Phase 3 when tenant isolation is required.
    """
    service = ReceiptsService(db)
    payload = await service.daily_receipt(hotel_id, receipt_date)
    logger.info(
        "receipts_route: served hotel_id=%s date=%s total_actions=%d",
        hotel_id,
        receipt_date,
        payload.total_actions,
    )
    return payload

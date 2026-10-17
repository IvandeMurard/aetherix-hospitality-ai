import logging
import os
import time
from datetime import date
from typing import Any, Dict, Optional

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query
from mcp import ClientSession
from mcp.client.streamable_http import streamablehttp_client
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

from app.core.security import get_current_user
from app.db.models import RestaurantProfile
from app.db.session import get_db
from app.integrations.apaleo_mcp_client import ApaleoMCPClient
from app.services.apaleo_adapter import ApaleoPMSAdapter, ApaleoSyncError
from app.services.apaleo_mcp_adapter import ApaleoMCPAdapter
from app.services.pms_sync import MockPMSAdapter, PMSSyncService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/pms", tags=["pms"])


def adapter_for(target, *, use_mock: bool = False, use_mcp: bool = False):
    """The adapter of the hotel's own PMS (HOS-347). Adding a PMS = adding an
    entry here once its adapter exists (Décision #28); until then, refused."""
    from app.services.pms_identity import PmsIdentityError

    if use_mock:
        return MockPMSAdapter(), "mock"
    if target.pms_type == "apaleo":
        return (ApaleoMCPAdapter(), "apaleo_mcp") if use_mcp else (ApaleoPMSAdapter(), "apaleo_raw")
    if use_mcp:
        raise PmsIdentityError("pms_not_supported", "use_mcp applies to Apaleo only")
    raise PmsIdentityError("pms_not_supported",
                           f"no adapter yet for this hotel's PMS ({target.pms_type}); nothing was synced")


async def _sync_task(service: PMSSyncService, target, sync_date: date) -> None:
    """Background task wrapper that catches ApaleoSyncError and logs without DB write."""
    try:
        await service.sync_daily_data(target, sync_date)
    except ApaleoSyncError as exc:
        logger.error(
            "PMS sync failed for tenant %s (PMS property %s) on %s — Apaleo error: %s",
            target.tenant_id,
            target.pms_property_id,
            sync_date,
            exc,
        )

@router.get("/mcp/probe")
async def probe_mcp_connection(
    current_user: Dict[str, Any] = Depends(get_current_user),
) -> Dict[str, Any]:
    """
    Synchronous health-check for the Apaleo MCP connection.

    Validates:
    1. Required env vars are present (APALEO_CLIENT_ID, APALEO_CLIENT_SECRET,
       APALEO_MCP_SERVER_URL).
    2. OAuth2 client-credentials token can be acquired.
    3. MCP session can be initialised (streamable-HTTP, list_tools handshake).

    Returns a JSON payload with connection status and latency — no DB writes,
    no background tasks, safe to call as a readiness probe.
    """
    client = ApaleoMCPClient()

    if not client.is_configured:
        raise HTTPException(
            status_code=503,
            detail={
                "status": "misconfigured",
                "missing": [
                    v for v in ("APALEO_CLIENT_ID", "APALEO_CLIENT_SECRET", "APALEO_MCP_SERVER_URL")
                    if not os.getenv(v)
                ],
                "hint": "Set the missing env vars and restart the server.",
            },
        )

    t0 = time.monotonic()
    try:
        token = await client._get_token()  # noqa: SLF001 — internal probe only
        token_ms = round((time.monotonic() - t0) * 1000, 1)

        t1 = time.monotonic()
        async with streamablehttp_client(
            client.server_url,
            headers={"Authorization": f"Bearer {token}"},
        ) as (read_stream, write_stream, _):
            async with ClientSession(read_stream, write_stream) as session:
                await session.initialize()
                tools_result = await session.list_tools()
                tool_names = [t.name for t in (tools_result.tools or [])]
        mcp_ms = round((time.monotonic() - t1) * 1000, 1)

    except Exception as exc:
        raise HTTPException(
            status_code=503,
            detail={
                "status": "unreachable",
                "error": str(exc),
                "server_url": client.server_url,
            },
        ) from exc

    return {
        "status": "ok",
        "server_url": client.server_url,
        "token_latency_ms": token_ms,
        "mcp_latency_ms": mcp_ms,
        "tools_available": len(tool_names),
        "tools": tool_names[:20],  # cap to avoid oversized responses
    }


@router.get("/status")
async def get_pms_status(
    current_user: Dict[str, Any] = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Returns the current connection status of the PMS."""
    # Fetch property for this user
    result = await db.execute(
        select(RestaurantProfile).where(RestaurantProfile.owner_id == current_user["id"])
    )
    profile = result.scalars().first()
    
    is_connected = bool(os.getenv("APALEO_CLIENT_ID"))
    return {
        "status": "connected" if (is_connected and profile) else "disconnected",
        "provider": profile.pms_type if profile else "none",
        "property_name": profile.property_name if profile else "No property linked",
        "last_sync": date.today().isoformat(),
        "authorized_user": current_user.get("email")
    }

@router.post("/sync")
async def trigger_pms_sync(
    background_tasks: BackgroundTasks,
    target_date: Optional[date] = None,
    use_mock: bool = Query(True, description="Whether to use the Mock adapter for pilot verification"),
    use_mcp: bool = Query(False, description="Apaleo only: use its MCP server instead of its REST API (HOS-101)"),
    current_user: Dict[str, Any] = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Triggers a data sync from the hotel's own PMS for a date.
    Guarded by 'get_current_user' to ensure tenant-only access.

    PMS-agnostic (HOS-347, Décision #28): the adapter follows the hotel's
    ``pms_type``; a PMS without an adapter yet is refused (409), never synced
    through another vendor's adapter. ``use_mock`` overrides for pilot checks.
    """
    sync_date = target_date or date.today()

    # Fetch property for this user
    result = await db.execute(
        select(RestaurantProfile).where(RestaurantProfile.owner_id == current_user["id"])
    )
    profile = result.scalars().first()

    if not profile:
        raise HTTPException(status_code=404, detail="No restaurant profile linked to this user.")

    # HOS-347: the PMS is called with the hotel's PMS property id, everything
    # stored uses its tenant id. An unlinked hotel cannot sync (except mock).
    from app.services.pms_identity import PmsIdentityError, target_from_profile

    try:
        target = target_from_profile(profile, allow_unlinked_mock=use_mock)
        adapter, adapter_label = adapter_for(target, use_mock=use_mock, use_mcp=use_mcp)
    except PmsIdentityError as exc:
        raise HTTPException(status_code=409, detail=exc.detail) from None

    service = PMSSyncService(adapter)

    # Run sync in background (includes DB persistence)
    background_tasks.add_task(_sync_task, service, target, sync_date)

    return {
        "message": "PMS sync triggered successfully in background",
        "tenant_id": target.tenant_id,
        "pms_property_id": target.pms_property_id,
        "property_id": target.tenant_id,  # kept for existing callers; = tenant_id
        "property_name": profile.property_name,
        "date": sync_date.isoformat(),
        "adapter": adapter_label,
        "triggered_by": current_user.get("email")
    }

import abc
import asyncio
import logging
from datetime import date
from typing import Any, Dict, List

from app.core.money import format_money
from app.core.demo_events import demo_emit
from app.core.pii import digest_identifier
from app.db.models import PMSSyncLog
from app.db.session import AsyncSessionLocal

logger = logging.getLogger(__name__)


class PMSAdapter(abc.ABC):
    """Base class for all Property Management System (PMS) adapters.

    Occupancy and revenue are read through the canonical ``fetch_*`` methods
    (``app.providers.pms.base.PMSProvider``). ``get_occupancy`` and
    ``get_revenue`` were removed by HOS-352: they returned a bare number whose
    unit and origin (PMS or placeholder) could not be told.
    """

    @abc.abstractmethod
    async def get_historical_data(self, property_id: str, start_date: date, end_date: date) -> List[Dict[str, Any]]:
        """Fetch historical data for a range of dates."""
        ...

    @abc.abstractmethod
    async def update_staffing_in_pms(self, property_id: str, target_date: date, staffing_deltas: Dict[str, int]) -> bool:
        """Write staffing recommendations back to the PMS schedules/tasks."""
        ...

# HOS-280 (Décision #28): the adapters live in ``app.providers.pms``; this
# ABC stays for existing callers, and the moved adapters are registered as
# its virtual subclasses so isinstance checks keep holding.
from app.providers.pms.apaleo_adapter import ApaleoPMSAdapter as _ApaleoREST  # noqa: E402
from app.providers.pms.apaleo_mcp_adapter import ApaleoMCPAdapter as _ApaleoMCP  # noqa: E402
from app.providers.pms.base import (  # noqa: E402
    NormalizedOccupancy,
    NormalizedRevenue,
    PMSDataStatus,
)
from app.providers.pms.mock_adapter import MockPMSAdapter  # noqa: E402,F401 — re-export

for _cls in (_ApaleoREST, _ApaleoMCP, MockPMSAdapter):
    PMSAdapter.register(_cls)

class PIIStripper:
    """Utility to ensure GDPR compliance by stripping/hashing guest PII."""

    @staticmethod
    def strip_guest_data(reservation: Dict[str, Any]) -> Dict[str, Any]:
        """
        Removes sensitive guest fields and replaces them with a salted hash
        if a unique identifier is needed for frequency analysis.
        """
        # Remove direct PII
        reservation.pop("guest_name", None)
        reservation.pop("guest_email", None)
        reservation.pop("guest_phone", None)

        # Hash guest_id if it exists to allow count-based analytics without identifying the person.
        #
        # Story 7.5 / HOS-115 — this used to be a bare sha256. A PMS guest_id is
        # drawn from a small, enumerable space: anyone holding the property's id
        # list could rebuild the mapping offline. Peppered HMAC moves that out of
        # reach of a database dump alone. It is still pseudonymisation, not
        # anonymisation (considérant 26) — nothing downstream may treat a
        # `guest_hashed_id` as non-personal.
        if "guest_id" in reservation:
            guest_id = str(reservation["guest_id"])
            reservation["guest_hashed_id"] = digest_identifier(guest_id)
            reservation.pop("guest_id")

        return reservation

class PMSSyncService:
    """Service to orchestrate data ingestion from PMS."""

    def __init__(self, adapter: PMSAdapter):
        self.adapter = adapter
        self.stripper = PIIStripper()

    async def _fetch_day(self, pms_id: str, target_date: date):
        """Both figures of the day, each true or absent (HOS-352). An adapter
        that raises instead of returning an absent value is a ``pms_error``."""
        provider = self.adapter.provider_name
        try:
            occ = await self.adapter.fetch_occupancy(pms_id, target_date)
        except Exception as exc:  # noqa: BLE001
            occ = NormalizedOccupancy.absent(pms_id, target_date, provider, PMSDataStatus.PMS_ERROR, str(exc)[:200])
        try:
            rev = await self.adapter.fetch_fb_revenue(pms_id, target_date)
        except Exception as exc:  # noqa: BLE001
            rev = NormalizedRevenue.absent(pms_id, target_date, provider, PMSDataStatus.PMS_ERROR, str(exc)[:200])
        return occ, rev

    async def sync_daily_data(self, target, target_date: date):
        """Orchestrate the sync and storage of data for a specific day.

        ``target`` is a ``pms_identity.PmsTarget`` (HOS-347): the PMS is called
        with ``target.pms_property_id``; everything stored or logged uses
        ``target.tenant_id``. A bare string is refused: it cannot say which of
        the two ids it is.

        HOS-352: a figure the PMS did not give is stored as NULL with its
        status (``not_configured``, ``pms_error``, ``no_data``), never as a
        default. The row is still written, so the gap itself is on record.
        """
        from app.services.pms_identity import PmsTarget

        if not isinstance(target, PmsTarget):
            raise TypeError("sync_daily_data needs a PmsTarget (pms_identity.resolve_by_tenant)")
        pms_id, tenant_id = target.pms_property_id, target.tenant_id
        occ, rev = await self._fetch_day(pms_id, target_date)
        complete = occ.status.has_value and rev.status.has_value
        if not complete:
            logger.warning(
                "pms_sync: figure absent for %s on %s (occupancy=%s, fb_revenue=%s)",
                tenant_id, target_date, occ.status.value, rev.status.value,
            )
        property_id = tenant_id  # everything below is Aetherix-side
        status = "success" if complete else "incomplete"
        details = list(dict.fromkeys(d for d in (occ.detail, rev.detail) if d))

        # Story 2.2: Persist sync result to Supabase
        async with AsyncSessionLocal() as session:
            sync_log = PMSSyncLog(
                tenant_id=tenant_id,
                sync_date=target_date,
                rooms_sold=occ.rooms_sold,
                rooms_available=occ.rooms_available,
                occupancy_status=occ.status.value,
                fb_revenue=rev.amount,
                fb_revenue_currency=rev.currency,
                fb_revenue_status=rev.status.value,
                status=status,
                error_message="; ".join(details)[:500] or None,
            )
            session.add(sync_log)
            await session.commit()

        # Story 2.4: Recalculate captation baseline on every new data ingestion
        await self._trigger_captation_recalculation(property_id)

        rate = occ.rate
        result = {
            "property_id": property_id,
            "date": target_date.isoformat(),
            "rooms_sold": occ.rooms_sold,
            "rooms_available": occ.rooms_available,
            "occupancy_rate": None if rate is None else round(rate * 100),
            "occupancy_status": occ.status.value,
            "fb_revenue": rev.amount,
            "fb_revenue_currency": rev.currency,
            "fb_revenue_status": rev.status.value,
            "status": status,
        }
        occupancy_cell = (
            f"{occ.rooms_sold} / {occ.rooms_available} rooms ({round(rate * 100)}%)"
            if rate is not None else f"absent ({occ.status.value})"
        )
        revenue_cell = (
            f"{format_money(rev.amount, 2)} {rev.currency or ''}".strip()
            if rev.amount is not None else f"absent ({rev.status.value})"
        )

        from app.integrations.obsidian import VAULT_FOLDERS  # noqa: PLC0415
        from app.services.ops_dispatcher import dispatch_report  # noqa: PLC0415
        await dispatch_report(
            title=f"PMS Sync — {property_id} — {target_date.isoformat()}",
            content=(
                f"# PMS Sync Log\n\n"
                f"**Property:** {property_id}  \n"
                f"**Date:** {target_date.isoformat()}  \n\n"
                f"| Field | Value |\n|---|---|\n"
                f"| Occupancy | {occupancy_cell} |\n"
                f"| F&B Revenue (net) | {revenue_cell} |\n"
                f"| Status | {status} |\n"
            ),
            folder=VAULT_FOLDERS["sync_logs"],
            tags=["pms-sync", property_id],
        )
        # Demo board: highlight PMS Sync node after successful sync
        asyncio.create_task(demo_emit("pms_sync"))
        return result

    async def _trigger_captation_recalculation(self, property_id: str) -> None:
        """Re-compute the captation baseline after each successful sync.

        Errors are caught and logged so they never block the sync response.
        """
        from app.services.captation_service import (  # noqa: PLC0415
            CaptationService,
            InsufficientDataError,
        )

        try:
            async with AsyncSessionLocal() as session:
                await CaptationService().calculate_baseline(property_id, session)
        except InsufficientDataError as exc:
            logger.debug("Captation baseline skipped (not enough data): %s", exc)
        except Exception as exc:  # pylint: disable=broad-except
            logger.warning("Captation baseline recalculation failed for %s: %s", property_id, exc)

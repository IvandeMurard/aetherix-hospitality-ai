import abc
import asyncio
from datetime import date
from typing import Any, Dict, List

from app.core.money import format_money
from app.core.demo_events import demo_emit
from app.core.pii import digest_identifier
from app.db.models import PMSSyncLog
from app.db.session import AsyncSessionLocal


class PMSAdapter(abc.ABC):
    """Base class for all Property Management System (PMS) adapters."""
    
    @abc.abstractmethod
    async def get_occupancy(self, property_id: str, target_date: date) -> int:
        """Fetch occupancy (rooms sold) for a specific date."""
        ...

    @abc.abstractmethod
    async def get_revenue(self, property_id: str, target_date: date, category: str = "Total") -> float:
        """Fetch revenue for a specific date and category (e.g., F&B)."""
        ...

    @abc.abstractmethod
    async def get_historical_data(self, property_id: str, start_date: date, end_date: date) -> List[Dict[str, Any]]:
        """Fetch historical data for a range of dates."""
        ...

    @abc.abstractmethod
    async def update_staffing_in_pms(self, property_id: str, target_date: date, staffing_deltas: Dict[str, int]) -> bool:
        """Write staffing recommendations back to the PMS schedules/tasks."""
        ...

class MockPMSAdapter(PMSAdapter):
    """Mock adapter for development and pilot verification."""
    
    def __init__(self):
        # Mocking some baseline data
        self.mock_data = {
            "pilot_hotel": {
                "base_occupancy": 100,
                "base_fb_revenue": 2500.0,
            }
        }

    async def get_occupancy(self, property_id: str, target_date: date) -> int:
        return int(self.mock_data.get(property_id, {}).get("base_occupancy", 50))

    async def get_revenue(self, property_id: str, target_date: date, category: str = "Total") -> float:
        return self.mock_data.get(property_id, {}).get("base_fb_revenue", 1000.0)

    async def get_historical_data(self, property_id: str, start_date: date, end_date: date) -> List[Dict[str, Any]]:
        return [
            {
                "date": target_date.isoformat(),
                "occupancy": 80,
                "fb_revenue": 2000.0,
            } for target_date in [start_date] # Simplification for mock
        ]

    async def update_staffing_in_pms(self, property_id: str, target_date: date, staffing_deltas: Dict[str, int]) -> bool:
        # Simulate successful write-back
        print(f"Mocked push to {property_id} on {target_date}: {staffing_deltas}")
        return True

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

    async def sync_daily_data(self, property_id: str, target_date: date):
        """Orchestrate the sync and storage of data for a specific day."""
        occupancy = await self.adapter.get_occupancy(property_id, target_date)
        revenue = await self.adapter.get_revenue(property_id, target_date, category="F&B")

        # Story 2.2: Persist sync result to Supabase
        async with AsyncSessionLocal() as session:
            sync_log = PMSSyncLog(
                tenant_id=property_id,
                sync_date=target_date,
                occupancy=occupancy,
                fb_revenue=revenue,
                status="success"
            )
            session.add(sync_log)
            await session.commit()

        # Story 2.4: Recalculate captation baseline on every new data ingestion
        await self._trigger_captation_recalculation(property_id)

        result = {
            "property_id": property_id,
            "date": target_date.isoformat(),
            "occupancy": occupancy,
            "fb_revenue": revenue,
        }

        from app.integrations.obsidian import VAULT_FOLDERS  # noqa: PLC0415
        from app.services.ops_dispatcher import dispatch_report  # noqa: PLC0415
        await dispatch_report(
            title=f"PMS Sync — {property_id} — {target_date.isoformat()}",
            content=(
                f"# PMS Sync Log\n\n"
                f"**Property:** {property_id}  \n"
                f"**Date:** {target_date.isoformat()}  \n\n"
                f"| Field | Value |\n|---|---|\n"
                f"| Occupancy | {occupancy} rooms |\n"
                f"| F&B Revenue | {format_money(revenue, 2)} |\n"
                f"| Status | success |\n"
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
        import logging  # noqa: PLC0415
        _log = logging.getLogger(__name__)

        from app.services.captation_service import (  # noqa: PLC0415
            CaptationService,
            InsufficientDataError,
        )

        try:
            async with AsyncSessionLocal() as session:
                await CaptationService().calculate_baseline(property_id, session)
        except InsufficientDataError as exc:
            _log.debug("Captation baseline skipped (not enough data): %s", exc)
        except Exception as exc:  # pylint: disable=broad-except
            _log.warning("Captation baseline recalculation failed for %s: %s", property_id, exc)

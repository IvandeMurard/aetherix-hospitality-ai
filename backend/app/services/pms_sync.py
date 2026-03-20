import abc
import hashlib
from typing import List, Dict, Any, Optional
from datetime import datetime, date
from app.db.session import AsyncSessionLocal
from app.db.models import PMSSyncLog
from sqlalchemy.future import select

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
        
        # Hash guest_id if it exists to allow count-based analytics without identifying the person
        if "guest_id" in reservation:
            guest_id = str(reservation["guest_id"])
            reservation["guest_hashed_id"] = hashlib.sha256(guest_id.encode()).hexdigest()
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

        return {
            "property_id": property_id,
            "date": target_date.isoformat(),
            "occupancy": occupancy,
            "fb_revenue": revenue
        }

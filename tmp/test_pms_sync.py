import asyncio
import sys
import os
from datetime import date

# Add the app directory to sys.path
sys.path.append(os.path.abspath("fastapi-backend"))

from app.services.pms_sync import PMSSyncService, MockPMSAdapter

async def main():
    print("Starting PMS Sync Smoke Test...")
    adapter = MockPMSAdapter()
    service = PMSSyncService(adapter)
    
    property_id = "pilot_hotel"
    target_date = date.today()
    
    print(f"Triggering sync for {property_id} on {target_date}...")
    result = await service.sync_daily_data(property_id, target_date)
    
    print("Sync Result:")
    print(result)
    
    assert result["property_id"] == "pilot_hotel"
    assert result["occupancy"] == 100
    assert result["fb_revenue"] == 2500.0
    print("Smoke Test PASSED!")

if __name__ == "__main__":
    asyncio.run(main())

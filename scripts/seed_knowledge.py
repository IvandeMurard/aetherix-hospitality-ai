import asyncio
import os
import sys
from datetime import datetime

# Ensure app is in path to use MemoryService
sys.path.append(os.path.join(os.getcwd(), "fastapi-backend"))

from app.services.memory_service import MemoryService

INITIAL_INSIGHTS = [
    {
        "tenant_id": "pilot_hotel",
        "reflection": "The local Tuesday market significantly increases lunch walk-ins; increase server count projections by 2 on Tuesdays.",
        "tags": ["operations", "staffing", "knowledge"]
    },
    {
        "tenant_id": "pilot_hotel",
        "reflection": "Friday night guests are predominantly wine-focused; ensure a second Sommelier is scheduled if predicted covers exceed 140.",
        "tags": ["premium", "upsell", "staffing"]
    },
    {
        "tenant_id": "pilot_hotel",
        "reflection": "Historical data shows a 15% revenue lift when cross-selling the 'Chef's Table' during mid-week surpluses.",
        "tags": ["revenue", "strategy"]
    }
]

async def seed():
    memory = MemoryService()
    print(f"🌱 Seeding {len(INITIAL_INSIGHTS)} insights into Backboard.io...")
    
    for insight in INITIAL_INSIGHTS:
        try:
            await memory.store_reflection(
                tenant_id=insight["tenant_id"],
                reflection=insight["reflection"],
                tags=insight["tags"]
            )
            print(f"✅ Stored: {insight['reflection'][:40]}...")
        except Exception as e:
            print(f"❌ Failed to store insight: {str(e)}")

if __name__ == "__main__":
    if not os.getenv("BACKBOARD_API_KEY"):
        print("❌ Error: BACKBOARD_API_KEY not set.")
        sys.exit(1)
    asyncio.run(seed())

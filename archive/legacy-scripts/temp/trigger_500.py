import asyncio
from httpx import AsyncClient
from app.main import app
import json

async def trigger_500():
    print("Directly calling registration via app...")
    async with AsyncClient(app=app, base_url="http://test") as ac:
        user_data = {
            "email": "test_direct@example.com",
            "password": "password123",
            "is_active": True,
            "is_superuser": False,
            "is_verified": False,
            "first_name": "Test",
            "last_name": "User",
            "tenant_id": "tenant-123"
        }
        try:
            resp = await ac.post("/auth/register", json=user_data)
            print(f"Status Code: {resp.status_code}")
            print(f"Response: {resp.text}")
        except Exception as e:
            print(f"Exception triggered: {e}")
            import traceback
            traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(trigger_500())

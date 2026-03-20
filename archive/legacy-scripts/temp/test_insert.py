import asyncio
from app.db.session import AsyncSessionLocal
from app.db.models import User
import uuid
import os
from dotenv import load_dotenv

async def test_insert():
    load_dotenv()
    print("Attempting to insert user manually...")
    async with AsyncSessionLocal() as session:
        new_user = User(
            id=uuid.uuid4(),
            email=f"test_manual_{uuid.uuid4().hex[:6]}@example.com",
            hashed_password="hashed_password",
            is_active=True,
            is_superuser=False,
            is_verified=False,
            full_name="Manual Test",
            department_role="operations"
        )
        try:
            session.add(new_user)
            await session.commit()
            print("Successfully inserted user!")
        except Exception as e:
            print(f"Insertion failed: {e}")
            import traceback
            traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(test_insert())

import asyncio
from app.db.session import engine
from app.db.models import Base
from dotenv import load_dotenv

async def create_tables():
    load_dotenv(override=True)
    print("Attempting to create tables...")
    try:
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        print("Successfully created tables!")
    except Exception as e:
        print(f"Failed to create tables: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(create_tables())

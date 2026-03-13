import asyncio
from sqlalchemy.ext.asyncio import create_async_engine
import os
from dotenv import load_dotenv, find_dotenv

async def test_db():
    dotenv_path = find_dotenv()
    print(f"Loading .env from: {dotenv_path}")
    load_dotenv(dotenv_path, override=True)
    db_url = os.getenv("DATABASE_URL")
    print(f"Testing connection to: {db_url}")
    engine = create_async_engine(db_url)
    try:
        async with engine.connect() as conn:
            print("Successfully connected to the database!")
    except Exception as e:
        print(f"Connection failed: {e}")
    finally:
        await engine.dispose()

if __name__ == "__main__":
    asyncio.run(test_db())

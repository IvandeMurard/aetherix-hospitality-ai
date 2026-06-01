import os

from dotenv import load_dotenv
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker

load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL")
if not DATABASE_URL:
    # Fallback for local development if .env is missing
    DATABASE_URL = "postgresql+asyncpg://postgres:password@localhost:5432/aetherix"

# Supabase Transaction Pooler (port 6543 / Supavisor) does not support
# named prepared statements. Disable them when connecting via the pooler.
_is_pooler = ":6543" in DATABASE_URL

engine = create_async_engine(
    DATABASE_URL,
    echo=False,
    pool_pre_ping=True,
    pool_recycle=1800,
    connect_args={"statement_cache_size": 0} if _is_pooler else {},
)
AsyncSessionLocal = sessionmaker(
    engine, class_=AsyncSession, expire_on_commit=False
)

async def get_db():
    async with AsyncSessionLocal() as session:
        yield session

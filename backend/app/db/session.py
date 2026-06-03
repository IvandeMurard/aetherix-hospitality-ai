import os
import uuid

from dotenv import load_dotenv
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker

load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL")
if not DATABASE_URL:
    # Fallback for local development if .env is missing
    DATABASE_URL = "postgresql+asyncpg://postgres:password@localhost:5432/aetherix"

# Supabase Transaction Pooler (port 6543 / Supavisor) runs pgbouncer in
# transaction mode, which does not support server-side prepared statements
# safely: a pooled server connection is shared across transactions, so the
# asyncpg dialect's reused statement names (``__asyncpg_stmt_N__``) collide
# with a DuplicatePreparedStatementError. The documented SQLAlchemy fix is to
# (1) disable the statement cache and (2) generate a unique prepared-statement
# name per prepare so names never clash on a recycled server connection.
# Validated end-to-end on Fly staging against the 6543 pooler (HOS-190 AC6).
_is_pooler = ":6543" in DATABASE_URL
_pooler_connect_args = {
    "statement_cache_size": 0,
    "prepared_statement_cache_size": 0,
    "prepared_statement_name_func": lambda: f"__asyncpg_{uuid.uuid4()}__",
}

engine = create_async_engine(
    DATABASE_URL,
    echo=False,
    pool_pre_ping=True,
    pool_recycle=1800,
    connect_args=_pooler_connect_args if _is_pooler else {},
)
AsyncSessionLocal = sessionmaker(
    engine, class_=AsyncSession, expire_on_commit=False
)

async def get_db():
    async with AsyncSessionLocal() as session:
        yield session

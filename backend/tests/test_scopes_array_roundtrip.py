"""HOS-150 AC3 — scopes column ARRAY round-trip + verify_bearer/require_scope integration.

Covers:
- StringArray TypeDecorator: PostgreSQL ARRAY(String), SQLite JSON fallback
- MCPApiToken.scopes round-trip: save -> load returns the list intact
- AgentActionLog.scopes round-trip: save -> load returns the list intact
- verify_bearer hands `tok.scopes` straight to require_scope without ever being
  None when the row was saved with a non-empty list (the prod bug).
"""
from __future__ import annotations

import hashlib

import pytest
from sqlalchemy import select
from sqlalchemy.dialects.postgresql import ARRAY as _PgArray
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from app.db.models import AgentActionLog, Base, MCPApiToken, StringArray
from app.mcp_core import MCPAuthError, require_scope

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _hash(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


@pytest.fixture
async def session() -> AsyncSession:
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    async with factory() as s:
        yield s
    await engine.dispose()


# ---------------------------------------------------------------------------
# StringArray dialect routing
# ---------------------------------------------------------------------------

class TestStringArrayTypeDecorator:
    def test_postgresql_dialect_returns_array_string(self):
        from sqlalchemy.dialects import postgresql

        col_type = StringArray()
        impl = col_type.load_dialect_impl(postgresql.dialect())
        assert isinstance(impl, _PgArray)

    def test_sqlite_dialect_returns_json(self):
        from sqlalchemy.dialects import sqlite
        from sqlalchemy.types import JSON

        col_type = StringArray()
        impl = col_type.load_dialect_impl(sqlite.dialect())
        assert isinstance(impl, JSON)


# ---------------------------------------------------------------------------
# MCPApiToken round-trip
# ---------------------------------------------------------------------------

class TestMCPApiTokenScopesRoundTrip:
    @pytest.mark.asyncio
    async def test_default_scopes_persist_as_list(self, session: AsyncSession):
        token = MCPApiToken(
            hotel_id="hotel_1",
            token_hash=_hash("atx_test_default"),
            token_prefix="atx_test",
        )
        session.add(token)
        await session.flush()
        token_id = token.id

        # Force a fresh load
        session.expunge_all()
        loaded = (
            await session.execute(select(MCPApiToken).where(MCPApiToken.id == token_id))
        ).scalar_one()

        assert loaded.scopes == ["predict", "recommend", "feedback"], (
            f"Default scopes did not round-trip: {loaded.scopes}"
        )

    @pytest.mark.asyncio
    async def test_custom_scopes_persist_as_list(self, session: AsyncSession):
        token = MCPApiToken(
            hotel_id="hotel_1",
            token_hash=_hash("atx_test_custom"),
            token_prefix="atx_test",
            scopes=["predict"],  # narrowed scope
        )
        session.add(token)
        await session.flush()
        token_id = token.id

        session.expunge_all()
        loaded = (
            await session.execute(select(MCPApiToken).where(MCPApiToken.id == token_id))
        ).scalar_one()

        assert loaded.scopes == ["predict"]
        # Critical: scopes must NOT be None — that was the prod bug.
        assert loaded.scopes is not None

    @pytest.mark.asyncio
    async def test_loaded_scopes_drive_require_scope(self, session: AsyncSession):
        """End-to-end: persisted scopes must satisfy require_scope without
        any extra parsing."""
        token = MCPApiToken(
            hotel_id="hotel_1",
            token_hash=_hash("atx_test_e2e"),
            token_prefix="atx_test",
            scopes=["predict", "recommend"],
        )
        session.add(token)
        await session.flush()
        session.expunge_all()
        loaded = (
            await session.execute(
                select(MCPApiToken).where(MCPApiToken.token_hash == _hash("atx_test_e2e"))
            )
        ).scalar_one()

        # scope predict -> get_operational_predictions
        require_scope(loaded.scopes, "get_operational_predictions")

        # Missing scope (feedback) → forbidden
        with pytest.raises(MCPAuthError) as exc:
            require_scope(loaded.scopes, "submit_feedback_to_memory")
        assert exc.value.status == 403


# ---------------------------------------------------------------------------
# AgentActionLog round-trip
# ---------------------------------------------------------------------------

class TestAgentActionLogScopesRoundTrip:
    @pytest.mark.asyncio
    async def test_empty_list_persists(self, session: AsyncSession):
        row = AgentActionLog(
            hotel_id="hotel_1",
            tool_name="ping",
            scopes=[],
            status="ok",
        )
        session.add(row)
        await session.flush()
        row_id = row.id

        session.expunge_all()
        loaded = (
            await session.execute(select(AgentActionLog).where(AgentActionLog.id == row_id))
        ).scalar_one()
        assert loaded.scopes == []

    @pytest.mark.asyncio
    async def test_populated_list_persists(self, session: AsyncSession):
        row = AgentActionLog(
            hotel_id="hotel_1",
            tool_name="get_operational_predictions",
            scopes=["predict", "recommend"],
            status="ok",
            latency_ms=42,
        )
        session.add(row)
        await session.flush()
        row_id = row.id

        session.expunge_all()
        loaded = (
            await session.execute(select(AgentActionLog).where(AgentActionLog.id == row_id))
        ).scalar_one()
        assert loaded.scopes == ["predict", "recommend"]

    @pytest.mark.asyncio
    async def test_null_scopes_persist_as_none(self, session: AsyncSession):
        """The ORM column is nullable=True; explicit None must round-trip."""
        row = AgentActionLog(
            hotel_id="hotel_1",
            tool_name="ping",
            scopes=None,
            status="auth_error",
        )
        session.add(row)
        await session.flush()
        row_id = row.id

        session.expunge_all()
        loaded = (
            await session.execute(select(AgentActionLog).where(AgentActionLog.id == row_id))
        ).scalar_one()
        assert loaded.scopes is None

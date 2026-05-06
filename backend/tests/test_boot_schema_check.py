"""HOS-150 AC7 — boot-time critical-table verification.

Covers:
- verify_schema() raises SchemaValidationError listing every missing table
- verify_schema() passes silently when all critical tables exist
- AETHERIX_SKIP_BOOT_SCHEMA_CHECK bypasses the check
- The error message includes the supabase remediation instruction
- The lifespan in app.main.app aborts startup when verify_schema raises
"""
from __future__ import annotations

import pytest
from sqlalchemy.ext.asyncio import create_async_engine

from app.db.schema_check import (
    CRITICAL_TABLES,
    SchemaValidationError,
    verify_schema,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

async def _make_sqlite_engine_with_tables(*table_names: str):
    """Create an in-memory SQLite engine and CREATE TABLE for each name."""
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conn:
        from sqlalchemy import text
        for tn in table_names:
            await conn.execute(text(f"CREATE TABLE {tn} (id INTEGER PRIMARY KEY)"))
    return engine


# ---------------------------------------------------------------------------
# verify_schema — happy path
# ---------------------------------------------------------------------------

class TestVerifySchemaHappyPath:
    @pytest.mark.asyncio
    async def test_all_tables_present_passes(self):
        engine = await _make_sqlite_engine_with_tables(*CRITICAL_TABLES)
        try:
            await verify_schema(engine)  # must not raise
        finally:
            await engine.dispose()

    @pytest.mark.asyncio
    async def test_custom_tables_argument_overrides_critical_set(self):
        engine = await _make_sqlite_engine_with_tables("only_one")
        try:
            await verify_schema(engine, tables=["only_one"])
        finally:
            await engine.dispose()


# ---------------------------------------------------------------------------
# verify_schema — failure modes
# ---------------------------------------------------------------------------

class TestVerifySchemaFailureModes:
    @pytest.mark.asyncio
    async def test_missing_one_table_raises(self):
        # Set up DB with all critical tables EXCEPT operational_memory
        present = [t for t in CRITICAL_TABLES if t != "operational_memory"]
        engine = await _make_sqlite_engine_with_tables(*present)
        try:
            with pytest.raises(SchemaValidationError) as exc_info:
                await verify_schema(engine)
            assert "operational_memory" in str(exc_info.value)
        finally:
            await engine.dispose()

    @pytest.mark.asyncio
    async def test_missing_all_tables_lists_every_one(self):
        engine = await _make_sqlite_engine_with_tables()  # no tables
        try:
            with pytest.raises(SchemaValidationError) as exc_info:
                await verify_schema(engine)
            msg = str(exc_info.value)
            for tbl in CRITICAL_TABLES:
                assert tbl in msg, f"{tbl} missing from error message"
        finally:
            await engine.dispose()

    @pytest.mark.asyncio
    async def test_error_message_includes_remediation(self):
        engine = await _make_sqlite_engine_with_tables()
        try:
            with pytest.raises(SchemaValidationError) as exc_info:
                await verify_schema(engine)
            msg = str(exc_info.value)
            assert "supabase db reset" in msg or "supabase db push" in msg, (
                "Remediation instruction missing"
            )
            assert "AETHERIX_SKIP_BOOT_SCHEMA_CHECK" in msg, (
                "Bypass instruction missing"
            )
        finally:
            await engine.dispose()


# ---------------------------------------------------------------------------
# Bypass via env var
# ---------------------------------------------------------------------------

class TestSkipEnvVar:
    @pytest.mark.asyncio
    async def test_skip_env_var_bypasses_check(self, monkeypatch):
        monkeypatch.setenv("AETHERIX_SKIP_BOOT_SCHEMA_CHECK", "true")
        engine = await _make_sqlite_engine_with_tables()  # no tables
        try:
            await verify_schema(engine)  # must not raise
        finally:
            await engine.dispose()

    @pytest.mark.asyncio
    async def test_skip_env_var_accepts_truthy_values(self, monkeypatch):
        for value in ("true", "TRUE", "1", "yes", "Yes"):
            monkeypatch.setenv("AETHERIX_SKIP_BOOT_SCHEMA_CHECK", value)
            engine = await _make_sqlite_engine_with_tables()
            try:
                await verify_schema(engine)
            finally:
                await engine.dispose()

    @pytest.mark.asyncio
    async def test_skip_env_var_falsy_does_not_bypass(self, monkeypatch):
        for value in ("false", "0", "no", ""):
            monkeypatch.setenv("AETHERIX_SKIP_BOOT_SCHEMA_CHECK", value)
            engine = await _make_sqlite_engine_with_tables()
            try:
                with pytest.raises(SchemaValidationError):
                    await verify_schema(engine)
            finally:
                await engine.dispose()


# ---------------------------------------------------------------------------
# main.py lifespan integration
# ---------------------------------------------------------------------------

class TestLifespanAbortsOnMissingSchema:
    @pytest.mark.asyncio
    async def test_lifespan_propagates_schema_error(self, monkeypatch):
        """The FastAPI lifespan must surface SchemaValidationError, not swallow it."""
        # Override verify_schema to simulate a missing critical table.
        async def _failing_verify(*args, **kwargs):
            raise SchemaValidationError("simulated: missing operational_memory")

        monkeypatch.setattr("app.main.verify_schema", _failing_verify)

        from app.main import app, lifespan

        with pytest.raises(SchemaValidationError, match="operational_memory"):
            async with lifespan(app):
                pass

    @pytest.mark.asyncio
    async def test_lifespan_no_create_all_call(self, monkeypatch):
        """Regression: no path through lifespan should call Base.metadata.create_all."""
        called = {"flag": False}

        def _sync_marker(_engine, *args, **kwargs):
            called["flag"] = True

        # Patch Base.metadata.create_all if anyone re-introduces it
        monkeypatch.setattr("app.db.models.Base.metadata.create_all", _sync_marker)

        # Make verify_schema a noop so we exercise the rest of the lifespan
        async def _noop(*args, **kwargs):
            return None

        monkeypatch.setattr("app.main.verify_schema", _noop)

        # Patch out the heavy init so we don't actually start schedulers
        monkeypatch.setattr("app.main.get_llm_provider", lambda: _DummyProvider())
        monkeypatch.setattr("app.main.get_embedding_provider", lambda: _DummyProvider())
        monkeypatch.setattr("app.main.register_anomaly_scan_job", lambda s: None)
        monkeypatch.setattr("app.main.register_dispatch_job", lambda s: None)
        monkeypatch.setattr("app.main.register_memory_metrics_job", lambda s: None)
        monkeypatch.setattr("app.main.register_partition_rotation_job", lambda s: None)
        monkeypatch.setattr("app.main.start_weather_scheduler", lambda: None)
        monkeypatch.setattr("app.main.stop_weather_scheduler", lambda: None)
        monkeypatch.setattr("app.main.start_event_scheduler", lambda: None)
        monkeypatch.setattr("app.main.stop_event_scheduler", lambda: None)

        # Make the scheduler a no-op
        monkeypatch.setattr("app.main._scheduler.start", lambda: None)
        monkeypatch.setattr("app.main._scheduler.shutdown", lambda **kwargs: None)
        monkeypatch.setattr("app.main._scheduler.get_jobs", lambda: [])

        from app.main import app, lifespan

        async with lifespan(app):
            pass

        assert called["flag"] is False, (
            "lifespan called Base.metadata.create_all — that path must stay removed (HOS-150 AC7)"
        )


class _DummyProvider:
    model_id = "dummy"

    async def aclose(self):
        return None

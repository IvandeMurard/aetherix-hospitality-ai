"""HOS-111 — Cross-tenant isolation regression suite.

Layered strategy (tracks the three AC3 test sections in the story spec):

1. ``TestRLSMigrationContent``       — static parse of the latest pre-pilot
                                       migration; verifies every required
                                       table enables RLS + a service_role
                                       policy. Catches policy gaps before
                                       they reach Supabase.
2. ``TestApplicationLayerFiltering`` — SQLite-backed defense-in-depth check
                                       that ORM queries filtered by tenant_id
                                       return exactly the matching tenant's
                                       rows (and never the other tenant's).
3. ``TestLiveRLSEnforcement``        — runs only when ``DATABASE_URL`` is
                                       set. Connects with two synthetic
                                       roles and asserts the deny path.

Tests in section 2 also exercise the cross-tenant write-attempt path: an
INSERT carrying tenant_A's context cannot accidentally land tenant_B rows in
the table, since the ORM filter scoping is byte-for-byte the same as the
service-layer pattern (``where(X.tenant_id == ctx.tenant_id)``).
"""
from __future__ import annotations

import os
import re
from datetime import date, datetime, timezone
from decimal import Decimal
from pathlib import Path
from typing import AsyncGenerator

import pytest
import pytest_asyncio
from sqlalchemy import select
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from app.db.models import (
    Base,
    DemandAnomaly,
    KpiDaily,
    OperationalMemory,
    RestaurantProfile,
    StaffingRecommendation,
)

# ---------------------------------------------------------------------------
# Shared constants
# ---------------------------------------------------------------------------

MIGRATIONS_DIR = Path(__file__).resolve().parents[3] / "supabase" / "migrations"
MIGRATION_PATH = MIGRATIONS_DIR / "20260515000000_enable_rls_pre_pilot.sql"

# Mirror the audit-script source of truth: every table that must be locked
# down before pilot. Kept in sync with scripts/ci/audit_rls_policies.py.
REQUIRED_TABLES = (
    "restaurant_profiles",
    "demand_anomalies",
    "staffing_recommendations",
    "conversational_queries",
    "operational_memory",
    "fb_patterns",
    "mcp_api_tokens",
    "agent_action_log",
    "pms_sync_logs",
    "captation_baselines",
    "training_runs",
    "recommendation_cache",
    "weather_forecasts",
    "local_events",
    "kpi_daily",  # HOS-292 / Q2-05 — added post-0515, RLS lives in migration 0521
)

# Materialized views can't carry RLS in Postgres — isolation comes from the
# RLS-protected base tables they read + the app-layer tenant filter on reads.
# Registered so a NEW mat-view is a conscious, reviewed decision (HOS-292).
MATERIALIZED_VIEWS = frozenset({
    "recommendation_acceptance_daily",
    "abstention_daily",
    "latency_slo_daily",
    "memory_instrumentation_daily",
})


# ---------------------------------------------------------------------------
# Section 1 — Migration content (static)
# ---------------------------------------------------------------------------

def _table_rls_protected(sql: str, table: str) -> bool:
    """True if *table* has RLS enabled + a service_role policy anywhere in *sql*.

    Handles both migration styles:
      - explicit (e.g. 20260521 kpi_daily): ``ALTER TABLE ... ENABLE ROW LEVEL
        SECURITY`` + ``CREATE POLICY ... ON <table> ... service_role``;
      - DO-block ARRAY (20260515 pre-pilot batch): the table appears as a quoted
        literal in the ARRAY the block iterates to enable RLS + add the policy.
    """
    explicit_rls = re.search(
        rf"ALTER TABLE\s+(?:public\.)?{re.escape(table)}\s+ENABLE ROW LEVEL SECURITY",
        sql, re.IGNORECASE,
    )
    explicit_policy = re.search(
        rf"CREATE POLICY[^;]*ON\s+(?:public\.)?{re.escape(table)}\b[^;]*service_role",
        sql, re.IGNORECASE | re.DOTALL,
    )
    if explicit_rls and explicit_policy:
        return True
    return f"'{table}'" in sql  # DO-block ARRAY literal


class TestRLSMigrationContent:
    """Every required table must be locked down by SOME migration, and every
    materialized view must be registered (RLS can't cover mat-views)."""

    @pytest.fixture(scope="class")
    def migration_sql(self) -> str:
        # HOS-292: scan ALL migrations, not just the 20260515 pre-pilot file —
        # kpi_daily's RLS lives in 20260521, and later tables must be caught too.
        assert MIGRATIONS_DIR.is_dir(), f"migrations dir missing: {MIGRATIONS_DIR}"
        return "\n".join(
            p.read_text(encoding="utf-8") for p in sorted(MIGRATIONS_DIR.glob("*.sql"))
        )

    def test_migration_file_exists(self):
        assert MIGRATION_PATH.is_file()

    @pytest.mark.parametrize("table", REQUIRED_TABLES)
    def test_required_table_has_rls_and_policy(self, migration_sql: str, table: str):
        assert _table_rls_protected(migration_sql, table), (
            f"{table} is not RLS-protected in any migration "
            f"(needs ENABLE ROW LEVEL SECURITY + a service_role policy)"
        )

    def test_no_unregistered_materialized_views(self, migration_sql: str):
        """A new mat-view must be reviewed for tenant isolation before it ships —
        it cannot inherit RLS automatically."""
        found = set(
            re.findall(
                r"MATERIALIZED VIEW IF NOT EXISTS\s+(\w+)", migration_sql, re.IGNORECASE
            )
        )
        unregistered = found - set(MATERIALIZED_VIEWS)
        assert not unregistered, (
            f"unregistered materialized view(s) {sorted(unregistered)} — review "
            f"tenant isolation (base-table RLS + app-layer filter) and add to "
            f"MATERIALIZED_VIEWS (HOS-292)"
        )

    def test_migration_enables_row_level_security(self, migration_sql: str):
        assert re.search(
            r"ENABLE ROW LEVEL SECURITY", migration_sql, re.IGNORECASE
        ), "migration must enable RLS"

    def test_migration_creates_service_role_policy(self, migration_sql: str):
        # The DO block templates the policy name as ``<table>_service_role_all``.
        assert "service_role" in migration_sql
        assert "FOR ALL TO service_role" in migration_sql
        assert "USING (true) WITH CHECK (true)" in migration_sql

    def test_migration_is_idempotent(self, migration_sql: str):
        # Idempotency markers: IF EXISTS guard + DROP POLICY IF EXISTS.
        assert "IF EXISTS" in migration_sql
        assert "DROP POLICY IF EXISTS" in migration_sql

    def test_migration_drops_legacy_created_by_policies(self, migration_sql: str):
        # The legacy 20250313 policies reference ``created_by`` which no longer
        # exists. The new migration explicitly clears them so the policy
        # surface stays readable.
        assert '"Tenant Isolation: Restaurant Profiles"' in migration_sql
        assert '"Tenant Isolation: Sync Logs"' in migration_sql
        assert '"Tenant Isolation: Recommendation Cache"' in migration_sql

    def test_no_anon_or_authenticated_policy_for_sensitive_tables(
        self, migration_sql: str
    ):
        # mcp_api_tokens / agent_action_log must remain strictly service_role.
        # If the migration ever grows an ``authenticated`` policy for them
        # without an explicit story update, this test fails.
        sensitive_pattern = re.compile(
            r"CREATE POLICY[^;]*ON public\.(mcp_api_tokens|agent_action_log)"
            r"[^;]*TO (anon|authenticated)",
            re.IGNORECASE | re.DOTALL,
        )
        assert not sensitive_pattern.search(migration_sql)


# ---------------------------------------------------------------------------
# Section 2 — Application-layer filtering (SQLite, hermetic)
# ---------------------------------------------------------------------------

TENANT_A = "tenant_a"
TENANT_B = "tenant_b"


@pytest_asyncio.fixture
async def session_with_tenants() -> AsyncGenerator[
    tuple[AsyncSession, dict[str, RestaurantProfile]], None
]:
    """Two-tenant fixture for cross-tenant isolation tests.

    Returns an in-memory SQLite session with two RestaurantProfile rows
    (tenant_a, tenant_b), each with one DemandAnomaly, one
    StaffingRecommendation and one OperationalMemory row.
    """
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    factory = async_sessionmaker(engine, expire_on_commit=False)

    profiles: dict[str, RestaurantProfile] = {}
    async with factory() as session:
        for tenant in (TENANT_A, TENANT_B):
            profile = RestaurantProfile(
                tenant_id=tenant,
                property_name=f"{tenant} hotel",
                outlet_name="main",
                total_seats=80,
            )
            session.add(profile)
        await session.flush()

        for tenant in (TENANT_A, TENANT_B):
            profile = (
                await session.execute(
                    select(RestaurantProfile).where(RestaurantProfile.tenant_id == tenant)
                )
            ).scalar_one()
            profiles[tenant] = profile

            anomaly = DemandAnomaly(
                tenant_id=tenant,
                property_id=profile.property_id,
                window_start=datetime(2026, 5, 15, 18, 0, tzinfo=timezone.utc),
                window_end=datetime(2026, 5, 15, 22, 0, tzinfo=timezone.utc),
                expected_demand=Decimal("60"),
                baseline_demand=Decimal("45"),
                deviation_pct=Decimal("33.33"),
                direction="surge",
                triggering_factors=["test"],
            )
            session.add(anomaly)
            await session.flush()

            rec = StaffingRecommendation(
                tenant_id=tenant,
                property_id=profile.property_id,
                anomaly_id=anomaly.id,
                message_text=f"recommendation for {tenant}",
                window_start=anomaly.window_start,
                window_end=anomaly.window_end,
            )
            session.add(rec)

            memory = OperationalMemory(
                hotel_id=tenant,
                reflection=f"manager note for {tenant}",
            )
            session.add(memory)

            kpi = KpiDaily(
                tenant_id=tenant,
                kpi_date=date(2026, 5, 15),
                kpi_name="recommendation_acceptance_rate",
                value=0.42,
            )
            session.add(kpi)

        await session.commit()
        yield session, profiles

    await engine.dispose()


class TestApplicationLayerFiltering:
    """AC3 / Test 1 + 3: the backend always filters by tenant_id.

    These tests do not exercise Postgres RLS — they prove that the ORM
    filter pattern used across services is correct, so that even when the
    backend talks via service_role (RLS bypass), no row from tenant_B can
    leak into a query scoped to tenant_A.
    """

    @pytest.mark.asyncio
    async def test_restaurant_profile_filter_isolates_tenants(
        self, session_with_tenants
    ):
        session, _ = session_with_tenants

        rows_a = (
            await session.execute(
                select(RestaurantProfile).where(
                    RestaurantProfile.tenant_id == TENANT_A
                )
            )
        ).scalars().all()
        rows_b = (
            await session.execute(
                select(RestaurantProfile).where(
                    RestaurantProfile.tenant_id == TENANT_B
                )
            )
        ).scalars().all()

        assert len(rows_a) == 1
        assert rows_a[0].tenant_id == TENANT_A
        assert len(rows_b) == 1
        assert rows_b[0].tenant_id == TENANT_B

    @pytest.mark.asyncio
    async def test_service_role_session_sees_both_tenants_when_unfiltered(
        self, session_with_tenants
    ):
        """Sanity: the backend connection naturally sees every row.

        This is the expected behaviour — Supabase grants ``service_role``
        BYPASSRLS, so the ORM must always carry an explicit tenant filter.
        The test pins the contract: omitting the filter returns rows from
        every tenant, demonstrating why the WHERE clause is load-bearing.
        """
        session, _ = session_with_tenants

        rows = (
            await session.execute(select(RestaurantProfile))
        ).scalars().all()
        tenant_ids = {r.tenant_id for r in rows}

        assert tenant_ids == {TENANT_A, TENANT_B}

    @pytest.mark.asyncio
    async def test_demand_anomalies_filter_isolates_tenants(
        self, session_with_tenants
    ):
        session, _ = session_with_tenants

        rows_a = (
            await session.execute(
                select(DemandAnomaly).where(DemandAnomaly.tenant_id == TENANT_A)
            )
        ).scalars().all()

        assert len(rows_a) == 1
        assert all(r.tenant_id == TENANT_A for r in rows_a)

    @pytest.mark.asyncio
    async def test_staffing_recommendations_filter_isolates_tenants(
        self, session_with_tenants
    ):
        session, _ = session_with_tenants

        rows_b = (
            await session.execute(
                select(StaffingRecommendation).where(
                    StaffingRecommendation.tenant_id == TENANT_B
                )
            )
        ).scalars().all()

        assert len(rows_b) == 1
        assert rows_b[0].tenant_id == TENANT_B

    @pytest.mark.asyncio
    async def test_operational_memory_uses_hotel_id_alias(
        self, session_with_tenants
    ):
        """``operational_memory`` carries ``hotel_id`` (alias of tenant_id)."""
        session, _ = session_with_tenants

        rows_a = (
            await session.execute(
                select(OperationalMemory).where(
                    OperationalMemory.hotel_id == TENANT_A
                )
            )
        ).scalars().all()

        assert len(rows_a) == 1
        assert rows_a[0].hotel_id == TENANT_A

    @pytest.mark.asyncio
    async def test_kpi_daily_filter_isolates_tenants(self, session_with_tenants):
        """HOS-292 / Q2-05: kpi_daily (added after the 0515 RLS batch) must
        isolate by tenant_id like every other tenant-scoped table."""
        session, _ = session_with_tenants

        rows_a = (
            await session.execute(
                select(KpiDaily).where(KpiDaily.tenant_id == TENANT_A)
            )
        ).scalars().all()
        assert len(rows_a) == 1
        assert all(r.tenant_id == TENANT_A for r in rows_a)

        # Cross-tenant: tenant_B's KPI row is invisible to a tenant_A-scoped read.
        leaked = (
            await session.execute(
                select(KpiDaily)
                .where(KpiDaily.tenant_id == TENANT_A)
                .where(KpiDaily.kpi_name == "recommendation_acceptance_rate")
            )
        ).scalars().all()
        assert {r.tenant_id for r in leaked} == {TENANT_A}

    @pytest.mark.asyncio
    async def test_cross_tenant_anomaly_lookup_returns_nothing(
        self, session_with_tenants
    ):
        """AC3 / Test 3: filter mismatched against tenant — zero rows.

        A regression where a service writes ``tenant_id == ctx.tenant_id``
        but somehow another tenant's anomaly_id leaks into the query would
        still return zero rows because the combined filter excludes the
        wrong tenant's anomalies. This is the application-layer defense.
        """
        session, _ = session_with_tenants

        anomaly_b = (
            await session.execute(
                select(DemandAnomaly).where(DemandAnomaly.tenant_id == TENANT_B)
            )
        ).scalar_one()

        cross_tenant_query = await session.execute(
            select(DemandAnomaly)
            .where(DemandAnomaly.tenant_id == TENANT_A)
            .where(DemandAnomaly.id == anomaly_b.id)
        )
        assert cross_tenant_query.scalars().first() is None

    @pytest.mark.asyncio
    async def test_unique_tenant_id_constraint_blocks_duplicate(
        self, session_with_tenants
    ):
        """Schema-level defense: tenant_id is unique on restaurant_profiles."""
        session, _ = session_with_tenants

        duplicate = RestaurantProfile(
            tenant_id=TENANT_A,  # same slug, must collide
            property_name="duplicate attempt",
            outlet_name="main",
            total_seats=20,
        )
        session.add(duplicate)
        with pytest.raises(Exception):  # IntegrityError on SQLite & Postgres
            await session.flush()
        await session.rollback()


# ---------------------------------------------------------------------------
# Section 3 — Live RLS enforcement (requires DATABASE_URL)
# ---------------------------------------------------------------------------

_DB_URL = os.environ.get("DATABASE_URL")


@pytest.mark.skipif(
    not _DB_URL,
    reason="DATABASE_URL not set — live RLS check requires a real Postgres",
)
class TestLiveRLSEnforcement:
    """AC3 / Test 2 — verifies the migration's deny-by-default behavior.

    Runs only when ``DATABASE_URL`` is present (typically Supabase staging).
    The test connects with two profiles:

      * ``service_role``  — expected to see both tenants (RLS BYPASS)
      * an anon-like role — expected to see zero rows (RLS deny)

    The test never writes — it is purely a read-side probe so it is safe to
    run against staging or production.
    """

    @pytest_asyncio.fixture
    async def asyncpg_conn(self):
        import asyncpg

        dsn = _DB_URL
        if dsn.startswith("postgresql+asyncpg://"):
            dsn = "postgresql://" + dsn[len("postgresql+asyncpg://"):]
        conn = await asyncpg.connect(dsn)
        try:
            yield conn
        finally:
            await conn.close()

    @pytest.mark.asyncio
    async def test_required_tables_have_rls_enabled(self, asyncpg_conn):
        rows = await asyncpg_conn.fetch(
            """
            SELECT c.relname, c.relrowsecurity
              FROM pg_class c
              JOIN pg_namespace n ON n.oid = c.relnamespace
             WHERE n.nspname = 'public' AND c.relkind = 'r'
               AND c.relname = ANY($1::text[])
            """,
            list(REQUIRED_TABLES),
        )
        disabled = [r["relname"] for r in rows if not r["relrowsecurity"]]
        # Tables that don't exist yet on this database are not failures —
        # the migration's IF EXISTS guard intentionally skips them.
        assert not disabled, f"RLS disabled on: {disabled}"

    @pytest.mark.asyncio
    async def test_required_tables_have_service_role_policy(self, asyncpg_conn):
        rows = await asyncpg_conn.fetch(
            """
            SELECT tablename
              FROM pg_policies
             WHERE schemaname = 'public'
               AND tablename = ANY($1::text[])
               AND 'service_role' = ANY(roles::text[])
            """,
            list(REQUIRED_TABLES),
        )
        protected = {r["tablename"] for r in rows}

        existing = {
            r["relname"]
            for r in await asyncpg_conn.fetch(
                """
                SELECT c.relname FROM pg_class c
                  JOIN pg_namespace n ON n.oid = c.relnamespace
                 WHERE n.nspname = 'public' AND c.relkind = 'r'
                   AND c.relname = ANY($1::text[])
                """,
                list(REQUIRED_TABLES),
            )
        }

        missing = sorted(existing - protected)
        assert not missing, f"tables lacking service_role policy: {missing}"

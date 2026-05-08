"""HOS-165 / HOS-159-C — pipeline ID consistency after the type-normalisation
migration (`supabase/migrations/20260508000000_normalize_id_types.sql`).

Convention reminder (docs/context/data-conventions.md):

    id / property_id  -> UUID
    tenant_id / hotel_id -> human-readable slug (TEXT in Postgres, str in Python)

The tests below seed an in-memory SQLite DB with the canonical four-row scenario
exercised by the agent pipeline:

    1 RestaurantProfile  + 1 MCPApiToken
    1 DemandAnomaly      + 1 StaffingRecommendation

…and assert two things:

    A. UUID joins on `property_id` resolve to the right rows in both directions.
    B. The slug stored as `tenant_id` on RestaurantProfile / DemandAnomaly /
       StaffingRecommendation matches the `hotel_id` carried by the MCPApiToken.

A regression on either axis points to a fresh ID-type drift.
"""
from __future__ import annotations

import hashlib
import uuid
from datetime import datetime, timedelta, timezone
from decimal import Decimal

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from app.db.models import (
    Base,
    ConversationalQuery,
    DemandAnomaly,
    MCPApiToken,
    RestaurantProfile,
    StaffingRecommendation,
)


HOTEL_SLUG = "demo_hotel"


def _sha(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


@pytest.fixture
async def session() -> AsyncSession:
    """Fresh in-memory SQLite DB with the full ORM schema."""
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    async with factory() as s:
        yield s
    await engine.dispose()


@pytest.fixture
async def seeded(session: AsyncSession):
    """Seed: 1 RestaurantProfile + 1 MCPApiToken + 1 DemandAnomaly + 1 StaffingRecommendation."""
    profile = RestaurantProfile(
        id=uuid.uuid4(),
        property_id=None,                 # populated below to mirror id
        tenant_id=HOTEL_SLUG,
        property_name="Demo Hotel",
        outlet_name="Main Restaurant",
        total_seats=80,
    )
    profile.property_id = profile.id      # convention: property_id == id
    session.add(profile)

    token = MCPApiToken(
        id=uuid.uuid4(),
        hotel_id=HOTEL_SLUG,              # slug — must match RestaurantProfile.tenant_id
        token_hash=_sha("atx_test_demo"),
        token_prefix="atx_test",
    )
    session.add(token)

    now = datetime.now(tz=timezone.utc)
    anomaly = DemandAnomaly(
        id=uuid.uuid4(),
        tenant_id=HOTEL_SLUG,             # slug, not UUID
        property_id=profile.property_id,  # UUID join target
        window_start=now,
        window_end=now + timedelta(hours=3),
        expected_demand=Decimal("130.00"),
        baseline_demand=Decimal("100.00"),
        deviation_pct=Decimal("30.00"),
        direction="surge",
        triggering_factors=[{"label": "Tech conference", "weight": 0.9}],
        status="ready_to_push",
    )
    session.add(anomaly)
    await session.flush()                 # need anomaly.id before FK insert

    rec = StaffingRecommendation(
        id=uuid.uuid4(),
        tenant_id=HOTEL_SLUG,
        property_id=profile.property_id,
        anomaly_id=anomaly.id,
        message_text="Call in 2 extra servers for dinner.",
        triggering_factor="Tech conference",
        recommended_headcount=2,
        window_start=anomaly.window_start,
        window_end=anomaly.window_end,
        roi_net=Decimal("620.00"),
        roi_labor_cost=Decimal("180.00"),
        status="ready_to_push",
    )
    session.add(rec)
    await session.commit()

    return {
        "profile": profile,
        "token": token,
        "anomaly": anomaly,
        "rec": rec,
    }


# ---------------------------------------------------------------------------
# A. UUID joins: property_id <-> property_id
# ---------------------------------------------------------------------------


class TestPropertyIdJoins:
    @pytest.mark.asyncio
    async def test_anomaly_property_id_matches_profile_property_id(
        self, session: AsyncSession, seeded
    ):
        profile = seeded["profile"]

        result = await session.execute(
            select(DemandAnomaly).where(
                DemandAnomaly.property_id == profile.property_id
            )
        )
        anomalies = result.scalars().all()
        assert len(anomalies) == 1
        assert anomalies[0].id == seeded["anomaly"].id

    @pytest.mark.asyncio
    async def test_recommendation_property_id_matches_profile_property_id(
        self, session: AsyncSession, seeded
    ):
        profile = seeded["profile"]

        result = await session.execute(
            select(StaffingRecommendation).where(
                StaffingRecommendation.property_id == profile.property_id
            )
        )
        recs = result.scalars().all()
        assert len(recs) == 1
        assert recs[0].id == seeded["rec"].id

    @pytest.mark.asyncio
    async def test_property_id_equals_id_for_seeded_profile(
        self, session: AsyncSession, seeded
    ):
        """Backfill convention: property_id mirrors id on RestaurantProfile."""
        profile = seeded["profile"]
        assert profile.property_id == profile.id

    @pytest.mark.asyncio
    async def test_recommendation_to_anomaly_join_via_uuid(
        self, session: AsyncSession, seeded
    ):
        """The anomaly_id FK round-trips as a UUID."""
        rec = seeded["rec"]
        anomaly_id = rec.anomaly_id

        result = await session.execute(
            select(DemandAnomaly).where(DemandAnomaly.id == anomaly_id)
        )
        anomaly = result.scalar_one()
        assert anomaly.id == seeded["anomaly"].id


# ---------------------------------------------------------------------------
# B. tenant_id slug == MCPApiToken.hotel_id
# ---------------------------------------------------------------------------


class TestTenantIdSlugConsistency:
    @pytest.mark.asyncio
    async def test_profile_tenant_id_matches_token_hotel_id(
        self, session: AsyncSession, seeded
    ):
        profile = seeded["profile"]
        token = seeded["token"]
        assert isinstance(profile.tenant_id, str)
        assert isinstance(token.hotel_id, str)
        assert profile.tenant_id == token.hotel_id == HOTEL_SLUG

    @pytest.mark.asyncio
    async def test_anomaly_tenant_id_matches_token_hotel_id(
        self, session: AsyncSession, seeded
    ):
        anomaly = seeded["anomaly"]
        token = seeded["token"]
        assert isinstance(anomaly.tenant_id, str)
        assert anomaly.tenant_id == token.hotel_id == HOTEL_SLUG

    @pytest.mark.asyncio
    async def test_recommendation_tenant_id_matches_token_hotel_id(
        self, session: AsyncSession, seeded
    ):
        rec = seeded["rec"]
        token = seeded["token"]
        assert isinstance(rec.tenant_id, str)
        assert rec.tenant_id == token.hotel_id == HOTEL_SLUG

    @pytest.mark.asyncio
    async def test_token_lookup_by_hotel_id_returns_seeded_token(
        self, session: AsyncSession, seeded
    ):
        result = await session.execute(
            select(MCPApiToken).where(MCPApiToken.hotel_id == HOTEL_SLUG)
        )
        tokens = result.scalars().all()
        assert len(tokens) == 1
        assert tokens[0].id == seeded["token"].id


# ---------------------------------------------------------------------------
# C. Conversational queries: tenant_id is now a slug, not a UUID
# ---------------------------------------------------------------------------


class TestConversationalQueryTenantId:
    @pytest.mark.asyncio
    async def test_can_persist_query_with_slug_tenant_id(
        self, session: AsyncSession, seeded
    ):
        profile = seeded["profile"]
        rec = seeded["rec"]

        q = ConversationalQuery(
            id=uuid.uuid4(),
            tenant_id=HOTEL_SLUG,                # slug
            property_id=profile.property_id,     # UUID
            from_number="+33600000000",
            body="OK accepted",
            recommendation_id=rec.id,
            status="pending",
        )
        session.add(q)
        await session.commit()

        loaded = (
            await session.execute(
                select(ConversationalQuery).where(
                    ConversationalQuery.tenant_id == HOTEL_SLUG
                )
            )
        ).scalar_one()
        assert isinstance(loaded.tenant_id, str)
        assert loaded.tenant_id == HOTEL_SLUG
        assert loaded.property_id == profile.property_id

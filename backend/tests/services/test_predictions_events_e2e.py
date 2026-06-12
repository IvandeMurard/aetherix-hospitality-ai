"""E2E + unit coverage for local-events → predictions wiring (HOS-225 / P3-11c).

What this proves
----------------
1. ``enrich_events_context`` (unit): active-on-date window, radius cut,
   nearest-first ordering, missing-coords drop — no crash.
2. POST /predict (handler-level E2E): seeded local events flow through the real
   route → orchestrator → ReasoningService heuristic, and the reasoning summary
   names the *closest* event with its distance in km. The far event (beyond the
   5 km catchment) and any coordinate-less event never reach the explanation.

The /predict handler coroutine is invoked directly (not via TestClient) so the
seeded in-memory SQLite session and the request run in one event loop — this
exercises the identical route code without the cross-loop aiosqlite hazard.
"""
from __future__ import annotations

from datetime import date, datetime, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.future import select
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.db.models import Base, LocalEvent, RestaurantProfile

TENANT = "hotel-001"
TARGET = date(2026, 7, 15)

# Hotel sits in central Paris.
HOTEL_LAT, HOTEL_LNG = 48.8566, 2.3522


# ---------------------------------------------------------------------------
# Fixtures + seeding helpers
# ---------------------------------------------------------------------------

@pytest_asyncio.fixture
async def session() -> AsyncSession:
    """In-memory async SQLite shared across the test via StaticPool."""
    engine = create_async_engine(
        "sqlite+aiosqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    factory = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async with factory() as s:
        yield s
    await engine.dispose()


def _profile() -> RestaurantProfile:
    return RestaurantProfile(
        tenant_id=TENANT,
        property_name="Test Hotel",
        outlet_name="Test Restaurant",
        total_seats=100,
        latitude=HOTEL_LAT,
        longitude=HOTEL_LNG,
    )


def _event(
    event_id: str,
    title: str,
    lat: float | None,
    lng: float | None,
    *,
    category: str = "conferences",
    rank: int = 60,
    phq_attendance: int = 2000,
    tenant_id: str = TENANT,
) -> LocalEvent:
    return LocalEvent(
        tenant_id=tenant_id,
        event_id=event_id,
        title=title,
        category=category,
        rank=rank,
        phq_attendance=phq_attendance,
        start_dt=datetime(2026, 7, 15, 19, 0, tzinfo=timezone.utc),
        end_dt=datetime(2026, 7, 15, 23, 0, tzinfo=timezone.utc),
        latitude=lat,
        longitude=lng,
    )


async def _seed(session: AsyncSession, profile: RestaurantProfile, events: list[LocalEvent]) -> None:
    session.add(profile)
    for e in events:
        session.add(e)
    await session.commit()


# Coordinates: dlat 0.005 ≈ 0.56 km, dlat 0.01 ≈ 1.11 km (both << 5 km);
# dlat 0.44 ≈ 49 km (well beyond the 5 km catchment).
_NEAR = (48.8616, HOTEL_LNG)     # ~0.56 km
_MID = (48.8666, HOTEL_LNG)      # ~1.11 km
_FAR = (49.30, HOTEL_LNG)        # ~49 km


# ---------------------------------------------------------------------------
# Unit — enrich_events_context
# ---------------------------------------------------------------------------

class TestEnrichEventsContext:
    @pytest.mark.asyncio
    async def test_radius_cut_drops_far_event(self, session):
        prof = _profile()
        await _seed(session, prof, [
            _event("near", "Paris Tech Summit", *_MID),
            _event("far", "Lyon Festival", *_FAR),
        ])
        from app.services.events_enrichment import enrich_events_context

        events = await enrich_events_context(session, prof, TARGET)

        assert [e["name"] for e in events] == ["Paris Tech Summit"]
        assert events[0]["distance_km"] <= 5.0

    @pytest.mark.asyncio
    async def test_missing_coords_event_dropped_no_crash(self, session):
        prof = _profile()
        await _seed(session, prof, [
            _event("near", "Paris Tech Summit", *_MID),
            _event("ghost", "Phantom Gala", None, None),
        ])
        from app.services.events_enrichment import enrich_events_context

        events = await enrich_events_context(session, prof, TARGET)

        assert [e["name"] for e in events] == ["Paris Tech Summit"]

    @pytest.mark.asyncio
    async def test_sorted_nearest_first(self, session):
        prof = _profile()
        await _seed(session, prof, [
            _event("mid", "Mid Event", *_MID),    # ~1.11 km
            _event("near", "Near Event", *_NEAR),  # ~0.56 km
        ])
        from app.services.events_enrichment import enrich_events_context

        events = await enrich_events_context(session, prof, TARGET)

        assert [e["name"] for e in events] == ["Near Event", "Mid Event"]
        assert events[0]["distance_km"] <= events[1]["distance_km"]

    @pytest.mark.asyncio
    async def test_off_date_event_excluded(self, session):
        prof = _profile()
        ev = _event("near", "Paris Tech Summit", *_MID)
        ev.start_dt = datetime(2026, 8, 1, 19, 0, tzinfo=timezone.utc)
        ev.end_dt = datetime(2026, 8, 1, 23, 0, tzinfo=timezone.utc)
        await _seed(session, prof, [ev])
        from app.services.events_enrichment import enrich_events_context

        events = await enrich_events_context(session, prof, TARGET)

        assert events == []

    @pytest.mark.asyncio
    async def test_open_ended_event_included(self, session):
        """end_dt NULL + start_dt on/before target → still active."""
        prof = _profile()
        ev = _event("expo", "Long Expo", *_MID)
        ev.start_dt = datetime(2026, 7, 1, 9, 0, tzinfo=timezone.utc)
        ev.end_dt = None
        await _seed(session, prof, [ev])
        from app.services.events_enrichment import enrich_events_context

        events = await enrich_events_context(session, prof, TARGET)

        assert [e["name"] for e in events] == ["Long Expo"]


# ---------------------------------------------------------------------------
# E2E — POST /predict wires events into the reasoning summary
# ---------------------------------------------------------------------------

def _stub_engine(profile_lat=HOTEL_LAT, profile_lng=HOTEL_LNG):
    """Real OrchestratorAgent with stubbed collaborators + real ReasoningService.

    The reasoner's LLM raises RuntimeError → deterministic heuristic path, which
    names events with their distance (HOS-201 + HOS-215).
    """
    from orchestrator.agent import OrchestratorAgent
    from app.services.reasoning_service import ReasoningService

    forecast = SimpleNamespace(predicted=95, confidence=0.82, is_mock=True, lower=80, upper=110)

    forecaster = SimpleNamespace(predict=AsyncMock(return_value=forecast))
    rag = SimpleNamespace(
        build_context_string=MagicMock(return_value="ctx"),
        find_similar_patterns=AsyncMock(return_value=[]),
    )
    memory = SimpleNamespace(get_relevant_context=AsyncMock(return_value=""))
    staffer = SimpleNamespace(calculate_recommendation=AsyncMock(return_value={"servers": 4}))

    mock_llm = MagicMock()
    mock_llm.complete = AsyncMock(side_effect=RuntimeError("no api key"))
    reasoner = ReasoningService(llm=mock_llm)

    async def _loader(tenant_id):
        return SimpleNamespace(tenant_id=tenant_id, latitude=profile_lat, longitude=profile_lng)

    return OrchestratorAgent(
        forecaster=forecaster,
        rag=rag,
        reasoner=reasoner,
        staffer=staffer,
        memory=memory,
        profile_loader=_loader,
    )


async def _call_predict(session: AsyncSession, engine):
    from app.api.routes.predictions import PredictRequest, predict
    from fastapi import Response

    request = SimpleNamespace(app=SimpleNamespace(state=SimpleNamespace(engine=engine)))
    tok = SimpleNamespace(hotel_id=TENANT, scopes=["predict"])
    body = PredictRequest(hotel_id=TENANT, target_date=TARGET, service_type="dinner")

    return await predict(request=request, body=body, response=Response(), tok=tok, db=session)


class TestPredictWiresEvents:
    @pytest.mark.asyncio
    async def test_summary_names_closest_event_with_km(self, session):
        await _seed(session, _profile(), [
            _event("near", "Paris Tech Summit", *_MID),
            _event("far", "Lyon Festival", *_FAR),
        ])

        result = await _call_predict(session, _stub_engine())
        summary = result.reasoning_summary

        assert "Paris Tech Summit" in summary, summary
        assert "km" in summary, summary
        # Far event is outside the 5 km catchment → never surfaced.
        assert "Lyon Festival" not in summary, summary

    @pytest.mark.asyncio
    async def test_event_without_coords_dropped_no_crash(self, session):
        await _seed(session, _profile(), [
            _event("near", "Paris Tech Summit", *_MID),
            _event("ghost", "Phantom Gala", None, None),
        ])

        result = await _call_predict(session, _stub_engine())
        summary = result.reasoning_summary

        assert "Paris Tech Summit" in summary, summary
        assert "Phantom Gala" not in summary, summary

    @pytest.mark.asyncio
    async def test_no_events_seeded_is_graceful(self, session):
        await _seed(session, _profile(), [])

        result = await _call_predict(session, _stub_engine())

        # No nearby events → summary still produced, no event clause crash.
        assert result.predicted_covers == 95
        assert len(result.reasoning_summary) > 0

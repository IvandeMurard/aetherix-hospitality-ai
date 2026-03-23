"""Tests for EventIngestionService — HOS-84 Story 3.2.

Coverage:
  Unit:
    - _normalize(): maps PredictHQ response correctly
    - _normalize(): skips events with unparseable start datetime
    - _normalize(): extracts geo coordinates from GeoJSON
    - _parse_phq_datetime(): handles Z-suffix, naive, and None values
  Integration (mocked HTTP + in-memory SQLite):
    - sync_for_tenant(): raises ValueError when GPS missing
    - sync_for_tenant(): raises RuntimeError when API key not set
    - sync_for_tenant(): calls PredictHQ and persists records
    - Idempotency: re-running sync does NOT create duplicate rows
    - Cross-tenant isolation: tenant A cannot see tenant B rows
    - API failure retries and re-raises after exhaustion
"""
from __future__ import annotations

import os
from datetime import datetime, timezone
from typing import Any, Dict, List
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
import pytest_asyncio
import httpx
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.future import select

from app.db.models import Base, LocalEvent, RestaurantProfile
from app.schemas.events import EventRecord
from app.services.event_ingestion import EventIngestionService, _parse_phq_datetime


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest_asyncio.fixture
async def async_session():
    """In-memory async SQLite session for integration tests."""
    engine = create_async_engine(
        "sqlite+aiosqlite:///:memory:",
        connect_args={"check_same_thread": False},
    )
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    async_session_factory = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async with async_session_factory() as session:
        yield session

    await engine.dispose()


def _make_profile(
    tenant_id: str,
    lat: float | None = 48.8566,
    lng: float | None = 2.3522,
) -> RestaurantProfile:
    return RestaurantProfile(
        id=tenant_id,
        tenant_id=tenant_id,
        property_name="Test Hotel",
        outlet_name="Test Restaurant",
        total_seats=100,
        latitude=lat,
        longitude=lng,
    )


def _phq_event(
    event_id: str = "evt-001",
    title: str = "Tech Conference 2026",
    category: str = "conferences",
    start: str = "2026-03-25T09:00:00Z",
    end: str = "2026-03-25T18:00:00Z",
    rank: int = 72,
    local_rank: int = 55,
    phq_attendance: int = 3000,
    lat: float = 48.860,
    lng: float = 2.350,
    labels: List[str] | None = None,
) -> Dict[str, Any]:
    return {
        "id": event_id,
        "title": title,
        "category": category,
        "rank": rank,
        "local_rank": local_rank,
        "phq_attendance": phq_attendance,
        "start": start,
        "end": end,
        "geo": {
            "geometry": {
                "type": "Point",
                "coordinates": [lng, lat],
            }
        },
        "labels": labels or ["technology", "b2b"],
    }


def _phq_page(events: List[Dict], next_url: str | None = None) -> Dict[str, Any]:
    """Minimal PredictHQ paginated response."""
    return {
        "count": len(events),
        "next": next_url,
        "previous": None,
        "results": events,
    }


def _mock_http_client(pages: List[Dict]) -> AsyncMock:
    """Build a mock AsyncClient that returns pages in sequence."""
    responses = []
    for page in pages:
        mock_resp = MagicMock()
        mock_resp.raise_for_status = MagicMock()
        mock_resp.json.return_value = page
        responses.append(mock_resp)

    mock_client = AsyncMock(spec=httpx.AsyncClient)
    mock_client.get = AsyncMock(side_effect=responses)
    return mock_client


# ---------------------------------------------------------------------------
# Unit tests — _parse_phq_datetime
# ---------------------------------------------------------------------------

class TestParsePHQDatetime:
    def test_z_suffix(self):
        dt = _parse_phq_datetime("2026-03-25T09:00:00Z")
        assert dt is not None
        assert dt.tzinfo is not None
        assert dt.year == 2026

    def test_offset_aware(self):
        dt = _parse_phq_datetime("2026-03-25T09:00:00+02:00")
        assert dt is not None
        assert dt.tzinfo is not None

    def test_naive_iso(self):
        dt = _parse_phq_datetime("2026-03-25T09:00:00")
        assert dt is not None
        assert dt.tzinfo == timezone.utc

    def test_none_input(self):
        assert _parse_phq_datetime(None) is None

    def test_empty_string(self):
        assert _parse_phq_datetime("") is None

    def test_garbage_string(self):
        assert _parse_phq_datetime("not-a-date") is None


# ---------------------------------------------------------------------------
# Unit tests — _normalize
# ---------------------------------------------------------------------------

class TestNormalize:
    def test_maps_all_fields(self):
        raw = [_phq_event()]
        records = EventIngestionService._normalize(raw)

        assert len(records) == 1
        r = records[0]
        assert r.event_id == "evt-001"
        assert r.title == "Tech Conference 2026"
        assert r.category == "conferences"
        assert r.rank == 72
        assert r.local_rank == 55
        assert r.phq_attendance == 3000
        assert r.start_dt.tzinfo is not None
        assert r.end_dt is not None
        assert r.latitude == pytest.approx(48.860)
        assert r.longitude == pytest.approx(2.350)
        assert r.raw_labels == ["technology", "b2b"]

    def test_skips_event_with_no_start(self, caplog):
        import logging
        raw = [
            {**_phq_event(event_id="bad"), "start": None},
            _phq_event(event_id="good"),
        ]
        with caplog.at_level(logging.WARNING):
            records = EventIngestionService._normalize(raw)

        assert len(records) == 1
        assert records[0].event_id == "good"

    def test_skips_event_with_unparseable_start(self):
        raw = [
            {**_phq_event(event_id="bad"), "start": "not-a-date"},
            _phq_event(event_id="ok"),
        ]
        records = EventIngestionService._normalize(raw)
        assert len(records) == 1
        assert records[0].event_id == "ok"

    def test_extracts_geo_from_geojson(self):
        raw = [_phq_event(lat=51.507, lng=-0.127)]
        records = EventIngestionService._normalize(raw)
        assert records[0].latitude == pytest.approx(51.507)
        assert records[0].longitude == pytest.approx(-0.127)

    def test_geo_missing_gracefully(self):
        ev = _phq_event()
        del ev["geo"]
        records = EventIngestionService._normalize([ev])
        assert records[0].latitude is None
        assert records[0].longitude is None

    def test_optional_fields_none(self):
        ev = _phq_event()
        ev["rank"] = None
        ev["local_rank"] = None
        ev["phq_attendance"] = None
        ev["end"] = None
        ev["labels"] = None
        records = EventIngestionService._normalize([ev])
        r = records[0]
        assert r.rank is None
        assert r.end_dt is None
        assert r.raw_labels is None

    def test_empty_list(self):
        assert EventIngestionService._normalize([]) == []


# ---------------------------------------------------------------------------
# Integration tests — sync_for_tenant (mocked HTTP + SQLite)
# ---------------------------------------------------------------------------

class TestSyncForTenant:
    @pytest.mark.asyncio
    async def test_raises_when_no_gps(self, async_session):
        profile = _make_profile("tenant_no_gps", lat=None, lng=None)
        async_session.add(profile)
        await async_session.commit()

        service = EventIngestionService()
        with pytest.raises(ValueError, match="GPS coordinates"):
            await service.sync_for_tenant(async_session, profile)

    @pytest.mark.asyncio
    async def test_raises_when_no_api_key(self, async_session):
        profile = _make_profile("tenant_no_key")
        async_session.add(profile)
        await async_session.commit()

        with patch.dict(os.environ, {"PREDICTHQ_API_KEY": ""}):
            service = EventIngestionService()
            with pytest.raises(RuntimeError, match="PREDICTHQ_API_KEY"):
                await service.sync_for_tenant(async_session, profile)

    @pytest.mark.asyncio
    async def test_persists_records(self, async_session):
        profile = _make_profile("tenant_paris")
        async_session.add(profile)
        await async_session.commit()

        events = [_phq_event(event_id=f"evt-{i:03d}") for i in range(3)]
        mock_client = _mock_http_client([_phq_page(events)])

        with patch.dict(os.environ, {"PREDICTHQ_API_KEY": "test-key"}):
            service = EventIngestionService(http_client=mock_client)
            inserted = await service.sync_for_tenant(async_session, profile)

        assert inserted == 3
        mock_client.get.assert_awaited_once()

        rows = (
            await async_session.execute(
                select(LocalEvent).where(LocalEvent.tenant_id == "tenant_paris")
            )
        ).scalars().all()
        assert len(rows) == 3

    @pytest.mark.asyncio
    async def test_persists_all_fields(self, async_session):
        profile = _make_profile("tenant_fields")
        async_session.add(profile)
        await async_session.commit()

        ev = _phq_event(event_id="evt-check", title="Jazz Fest", category="concerts")
        mock_client = _mock_http_client([_phq_page([ev])])

        with patch.dict(os.environ, {"PREDICTHQ_API_KEY": "test-key"}):
            service = EventIngestionService(http_client=mock_client)
            await service.sync_for_tenant(async_session, profile)

        row = (
            await async_session.execute(
                select(LocalEvent).where(LocalEvent.event_id == "evt-check")
            )
        ).scalars().first()

        assert row is not None
        assert row.title == "Jazz Fest"
        assert row.category == "concerts"
        assert row.rank == 72
        assert row.phq_attendance == 3000
        assert row.tenant_id == "tenant_fields"

    @pytest.mark.asyncio
    async def test_idempotency_no_duplicates(self, async_session):
        """Running sync twice for the same property+events must not create duplicates."""
        profile = _make_profile("tenant_idempotent")
        async_session.add(profile)
        await async_session.commit()

        events = [_phq_event(event_id="evt-001"), _phq_event(event_id="evt-002")]
        # Provide two identical pages so both calls succeed
        mock_client = _mock_http_client([_phq_page(events), _phq_page(events)])

        with patch.dict(os.environ, {"PREDICTHQ_API_KEY": "test-key"}):
            service = EventIngestionService(http_client=mock_client)
            first_run = await service.sync_for_tenant(async_session, profile)
            second_run = await service.sync_for_tenant(async_session, profile)

        assert first_run == 2
        assert second_run == 0  # All conflict — no new rows

        rows = (
            await async_session.execute(
                select(LocalEvent).where(LocalEvent.tenant_id == "tenant_idempotent")
            )
        ).scalars().all()
        assert len(rows) == 2

    @pytest.mark.asyncio
    async def test_cross_tenant_isolation(self, async_session):
        """Rows inserted for tenant A must not be visible when querying tenant B."""
        profile_a = _make_profile("tenant_a_ev")
        profile_b = _make_profile("tenant_b_ev", lat=51.5074, lng=-0.1278)
        async_session.add_all([profile_a, profile_b])
        await async_session.commit()

        events_a = [_phq_event(event_id="evt-a1"), _phq_event(event_id="evt-a2")]
        mock_client = _mock_http_client([_phq_page(events_a)])

        with patch.dict(os.environ, {"PREDICTHQ_API_KEY": "test-key"}):
            service = EventIngestionService(http_client=mock_client)
            await service.sync_for_tenant(async_session, profile_a)

        rows_b = (
            await async_session.execute(
                select(LocalEvent).where(LocalEvent.tenant_id == "tenant_b_ev")
            )
        ).scalars().all()
        assert rows_b == [], "Tenant B must not see Tenant A's event rows"

    @pytest.mark.asyncio
    async def test_http_failure_reraises_after_retries(self, async_session):
        """After all retries exhausted, the HTTP exception propagates."""
        profile = _make_profile("tenant_fail_ev")
        async_session.add(profile)
        await async_session.commit()

        mock_client = AsyncMock(spec=httpx.AsyncClient)
        mock_client.get = AsyncMock(side_effect=httpx.ConnectError("unreachable"))

        with patch.dict(os.environ, {"PREDICTHQ_API_KEY": "test-key"}):
            service = EventIngestionService(http_client=mock_client)
            with pytest.raises(httpx.ConnectError):
                await service.sync_for_tenant(async_session, profile)

    @pytest.mark.asyncio
    async def test_empty_response_inserts_zero(self, async_session):
        """PredictHQ returning no events for a radius should not crash."""
        profile = _make_profile("tenant_empty")
        async_session.add(profile)
        await async_session.commit()

        mock_client = _mock_http_client([_phq_page([])])

        with patch.dict(os.environ, {"PREDICTHQ_API_KEY": "test-key"}):
            service = EventIngestionService(http_client=mock_client)
            inserted = await service.sync_for_tenant(async_session, profile)

        assert inserted == 0

    @pytest.mark.asyncio
    async def test_categories_cover_fb_relevant_types(self, async_session):
        """Ensure ingested categories include F&B-relevant event types."""
        profile = _make_profile("tenant_cats")
        async_session.add(profile)
        await async_session.commit()

        categories_to_test = ["conferences", "concerts", "sports", "festivals"]
        events = [
            _phq_event(event_id=f"evt-{cat}", category=cat)
            for cat in categories_to_test
        ]
        mock_client = _mock_http_client([_phq_page(events)])

        with patch.dict(os.environ, {"PREDICTHQ_API_KEY": "test-key"}):
            service = EventIngestionService(http_client=mock_client)
            inserted = await service.sync_for_tenant(async_session, profile)

        assert inserted == len(categories_to_test)

        rows = (
            await async_session.execute(
                select(LocalEvent).where(LocalEvent.tenant_id == "tenant_cats")
            )
        ).scalars().all()
        persisted_categories = {r.category for r in rows}
        assert persisted_categories == set(categories_to_test)

"""One mapping between a hotel's tenant and its PMS property (HOS-347).

Calls to the PMS use the PMS property id; everything stored uses the tenant
id. The two are never substituted for one another.
"""
from __future__ import annotations

import uuid
from datetime import date
from unittest.mock import AsyncMock, patch

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

from app.db.models import Base, RestaurantProfile
from app.services.pms_identity import (
    PmsIdentityError, PmsTarget, resolve_by_pms_property, resolve_by_tenant, target_from_profile,
)

OWNER = "a1b2c3d4-0000-4000-8000-00000000000a"


@pytest_asyncio.fixture()
async def db():
    engine = create_async_engine(
        "sqlite+aiosqlite:///:memory:", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    maker = async_sessionmaker(engine, expire_on_commit=False)
    async with maker() as s:
        yield s
    await engine.dispose()


async def _hotel(db, tenant, pms=None, pms_type="apaleo"):
    db.add(RestaurantProfile(tenant_id=tenant, property_name=f"P {tenant}", outlet_name="O", total_seats=80,
                             owner_id=uuid.UUID(OWNER), pms_property_id=pms, pms_type=pms_type))
    await db.commit()


# --- resolution -------------------------------------------------------------------

@pytest.mark.asyncio
async def test_known_hotel_resolves_both_ids_separately(db):
    await _hotel(db, "tenant_sandbox", pms="PAR")
    t = await resolve_by_tenant(db, "tenant_sandbox")
    assert (t.tenant_id, t.pms_property_id, t.pms_type) == ("tenant_sandbox", "PAR", "apaleo")
    back = await resolve_by_pms_property(db, "PAR")
    assert back.tenant_id == "tenant_sandbox"


@pytest.mark.asyncio
async def test_unknown_hotel_or_property_is_a_typed_error(db):
    with pytest.raises(PmsIdentityError) as e:
        await resolve_by_tenant(db, "nope")
    assert e.value.reason == "unknown_tenant"
    with pytest.raises(PmsIdentityError) as e:
        await resolve_by_pms_property(db, "XYZ")
    assert e.value.reason == "unknown_pms_property"


@pytest.mark.asyncio
async def test_unlinked_hotel_never_falls_back_to_its_tenant_id(db):
    await _hotel(db, "h1", pms=None)
    with pytest.raises(PmsIdentityError) as e:
        await resolve_by_tenant(db, "h1")
    assert e.value.reason == "pms_not_linked"
    mock = await resolve_by_tenant(db, "h1", allow_unlinked_mock=True)
    assert mock.pms_property_id == "mock-property" and mock.pms_property_id != "h1"


@pytest.mark.asyncio
async def test_two_hotels_two_properties_and_pms_type_is_respected(db):
    await _hotel(db, "h1", pms="PAR")
    await _hotel(db, "h2", pms="LON")
    await _hotel(db, "h3", pms="PAR", pms_type="mews")
    assert (await resolve_by_pms_property(db, "LON")).tenant_id == "h2"
    assert (await resolve_by_pms_property(db, "PAR", "apaleo")).tenant_id == "h1"
    assert (await resolve_by_pms_property(db, "PAR", "mews")).tenant_id == "h3"


# --- sync: PMS id outward, tenant id inward ----------------------------------------

class _RecordingAdapter:
    def __init__(self):
        self.calls = []

    async def get_occupancy(self, property_id, target_date):
        self.calls.append(property_id)
        return 70

    async def get_revenue(self, property_id, target_date, category="Total"):
        self.calls.append(property_id)
        return 1200.0


@pytest.mark.asyncio
async def test_sync_calls_the_pms_with_its_id_and_stores_the_tenant_id():
    from app.services.pms_sync import PMSSyncService

    adapter = _RecordingAdapter()
    service = PMSSyncService(adapter)
    stored = []

    class _Session:
        async def __aenter__(self):
            return self

        async def __aexit__(self, *a):
            return False

        def add(self, row):
            stored.append(row)

        async def commit(self):
            return None

    with (
        patch("app.services.pms_sync.AsyncSessionLocal", lambda: _Session()),
        patch.object(service, "_trigger_captation_recalculation", new_callable=AsyncMock) as recalc,
        patch("app.services.ops_dispatcher.dispatch_report", new_callable=AsyncMock),
        patch("app.integrations.obsidian.VAULT_FOLDERS", {"sync_logs": "logs"}, create=True),
    ):
        out = await service.sync_daily_data(PmsTarget("tenant_sandbox", "apaleo", "PAR"), date(2026, 10, 1))

    assert adapter.calls == ["PAR", "PAR"]                      # outward: the PMS's own id
    assert stored[0].tenant_id == "tenant_sandbox"              # inward: Aetherix's key
    recalc.assert_awaited_once_with("tenant_sandbox")
    assert out["property_id"] == "tenant_sandbox"


@pytest.mark.asyncio
async def test_sync_refuses_a_bare_string():
    from app.services.pms_sync import MockPMSAdapter, PMSSyncService

    with pytest.raises(TypeError):
        await PMSSyncService(MockPMSAdapter()).sync_daily_data("PAR", date(2026, 10, 1))


def test_target_from_profile_keeps_ids_apart():
    class P:
        tenant_id, pms_property_id, pms_type, property_name = "h1", "PAR", "apaleo", "Hôtel"

    t = target_from_profile(P())
    assert t.tenant_id == "h1" and t.pms_property_id == "PAR"

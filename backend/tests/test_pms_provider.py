"""Vendor-neutral PMS layer — HOS-280, true-or-absent figures — HOS-352
(Décisions #28, #33, #43, ADR-0006 §9).

A PMS figure is what the PMS reported, or absent with a typed status; never
80, never 0.0, never total revenue standing in for F&B. Occupancy is two room
counts everywhere, and the REST and MCP transports map the same report the
same way.
"""
from __future__ import annotations

from datetime import date
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.providers.pms.apaleo_adapter import (
    ApaleoPMSAdapter,
    map_performance_report,
    map_stay_record,
)
from app.providers.pms.apaleo_mcp_adapter import ApaleoMCPAdapter
from app.providers.pms.base import (
    NormalizedOccupancy,
    NormalizedRevenue,
    PMSDataStatus,
    PMSProvider,
    PMSProviderName,
)
from app.providers.pms.factory import get_pms_provider
from app.providers.pms.mock_adapter import MockPMSAdapter
from app.services.pms_identity import PmsIdentityError, PmsTarget
from app.services.pms_sync import PMSAdapter, PMSSyncService

DAY = date(2026, 10, 17)
APALEO = PMSProviderName.APALEO

# Shape of the sandbox property-performance payload (probed 18/10/2026), values changed.
REPORT = {
    "houseCount": 120, "soldCount": 90, "outOfOrderCount": 0, "occupancyPercentage": 75.0,
    "netFoodAndBeveragesRevenue": {"amount": 1840.5, "currency": "EUR"},
    "grossFoodAndBeveragesRevenue": {"amount": 2024.55, "currency": "EUR"},
    "netAccommodationRevenue": {"amount": 9100.0, "currency": "EUR"},
    "grossUnitRevenue": {"amount": 10500.0, "currency": "EUR"},
}


# --- protocol, factory, dataclass invariants ------------------------------------------

def test_every_adapter_implements_the_canonical_protocol_and_the_legacy_abc():
    for adapter in (ApaleoPMSAdapter("id", "secret"), ApaleoMCPAdapter(mcp_client=MagicMock(is_configured=False)),
                    MockPMSAdapter()):
        assert isinstance(adapter, PMSProvider)
        assert isinstance(adapter, PMSAdapter)
        assert not hasattr(adapter, "get_occupancy") and not hasattr(adapter, "get_revenue")


def test_factory_is_per_pms_type_and_refuses_a_pms_without_adapter():
    assert get_pms_provider("apaleo", "rest") is get_pms_provider("apaleo", "rest")
    assert get_pms_provider("apaleo", "mcp").transport == "mcp"
    with pytest.raises(PmsIdentityError) as e:
        get_pms_provider("mews", "rest")
    assert e.value.reason == "pms_not_supported"


def test_a_value_and_its_status_cannot_disagree():
    with pytest.raises(ValueError):
        NormalizedOccupancy("PAR", DAY, APALEO, PMSDataStatus.PMS_ERROR, rooms_sold=80, rooms_available=100)
    with pytest.raises(ValueError):
        NormalizedOccupancy("PAR", DAY, APALEO, PMSDataStatus.OK, rooms_sold=80)   # no denominator
    with pytest.raises(ValueError):
        NormalizedRevenue("PAR", DAY, APALEO, PMSDataStatus.NOT_CONFIGURED, amount=0.0)
    with pytest.raises(ValueError):
        NormalizedRevenue("PAR", DAY, APALEO, PMSDataStatus.OK)


# --- pure mappings -------------------------------------------------------------------

def test_stay_record_maps_to_a_canonical_reservation():
    r = map_stay_record({"id": "RES-1", "arrival": "2026-10-17T15:00:00+02:00", "departure": "2026-10-19",
                         "adults": 2, "children": 1, "status": "Confirmed", "guest_name": "x"})
    assert (r.vendor_reservation_id, r.arrival, r.departure, r.guests, r.status) == (
        "RES-1", date(2026, 10, 17), date(2026, 10, 19), 3, "Confirmed")
    assert r.provider == APALEO and "guest_name" in r.raw_fields


def test_children_as_a_list_of_ages_counts_children():
    assert map_stay_record({"arrival": "2026-10-17", "adults": 2, "children": [4, 7]}).children == 2


def test_performance_report_maps_to_room_counts_and_net_fb_revenue():
    occ, rev = map_performance_report(REPORT, "PAR", DAY)
    assert (occ.status, occ.rooms_sold, occ.rooms_available, occ.rate) == (PMSDataStatus.OK, 90, 120, 0.75)
    assert (rev.status, rev.amount, rev.currency) == (PMSDataStatus.OK, 1840.5, "EUR")


def test_out_of_order_rooms_are_not_available():
    occ, _ = map_performance_report({**REPORT, "outOfOrderCount": 20}, "PAR", DAY)
    assert (occ.rooms_sold, occ.rooms_available) == (90, 100)


def test_zero_rooms_sold_is_a_real_figure():
    """Sandbox reality: 0 sold out of 103 is what the PMS says, not a gap."""
    occ, _ = map_performance_report({"houseCount": 103, "soldCount": 0}, "BER", DAY)
    assert (occ.status, occ.rooms_sold, occ.rate) == (PMSDataStatus.OK, 0, 0.0)


@pytest.mark.parametrize("report", [{}, {"houseCount": 0, "soldCount": 0}, {"occupancyPercentage": 80.0},
                                    {"houseCount": "120", "soldCount": 90}, None])
def test_no_usable_room_counts_is_no_data_never_a_default(report):
    occ, rev = map_performance_report(report, "PAR", DAY)
    assert occ.status == PMSDataStatus.NO_DATA and occ.rooms_sold is None and occ.rate is None


def test_fb_revenue_never_falls_back_to_another_revenue_line():
    report = {k: v for k, v in REPORT.items() if k != "netFoodAndBeveragesRevenue"}
    _, rev = map_performance_report(report, "PAR", DAY)
    assert rev.status == PMSDataStatus.NO_DATA and rev.amount is None


# --- MCP adapter ---------------------------------------------------------------------

def _mcp(payload=None, configured=True, fail=False):
    client = MagicMock(is_configured=configured)

    async def call_tool(name, args):
        if fail:
            raise RuntimeError("down")
        assert name == "ListPropertyPerformanceReport"
        return payload

    client.call_tool = call_tool
    return ApaleoMCPAdapter(mcp_client=client)


@pytest.mark.asyncio
@pytest.mark.parametrize("adapter, status", [
    (_mcp(configured=False), PMSDataStatus.NOT_CONFIGURED),
    (_mcp(fail=True), PMSDataStatus.PMS_ERROR),
    (_mcp({"message": "bad request", "status_code": 422}), PMSDataStatus.PMS_ERROR),
    (_mcp({"data": {"houseCount": 0, "soldCount": 0}}), PMSDataStatus.NO_DATA),
])
async def test_mcp_never_invents_80_or_0(adapter, status):
    occ = await adapter.fetch_occupancy("PAR", DAY)
    rev = await adapter.fetch_fb_revenue("PAR", DAY)
    assert occ.status == status and occ.rooms_sold is None
    if status != PMSDataStatus.NO_DATA:
        assert rev.status == status and rev.amount is None


@pytest.mark.asyncio
async def test_mcp_reservations_are_canonical():
    client = MagicMock(is_configured=True)
    client.call_tool = AsyncMock(return_value={"data": {"reservations": [
        {"id": "R1", "arrival": "2026-10-17T14:00:00Z", "adults": 2, "children": 0, "status": "Confirmed"}]}})
    (r,) = await ApaleoMCPAdapter(mcp_client=client).fetch_reservations("PAR", DAY, DAY)
    assert (r.vendor_reservation_id, r.arrival, r.guests) == ("R1", DAY, 2)


# --- REST and MCP agree on the same day -----------------------------------------------------

def _rest(report, status_code=200):
    class _Client:
        async def __aenter__(self):
            return self

        async def __aexit__(self, *a):
            return False

        async def get(self, url, params=None, headers=None):
            assert url.endswith("/reports/v1/reports/property-performance")
            r = MagicMock(status_code=status_code)
            r.json.return_value = report
            return r

    a = ApaleoPMSAdapter("id", "secret")
    a.access_token, a.token_expiry = "t", 10**12
    return a, patch("app.providers.pms.apaleo_adapter.httpx.AsyncClient", lambda *a, **k: _Client())


@pytest.mark.asyncio
async def test_rest_and_mcp_give_the_same_figures_for_the_same_day():
    rest, http = _rest(REPORT)
    mcp = _mcp({"data": REPORT})
    with http:
        rest_figures = (await rest.fetch_occupancy("PAR", DAY), await rest.fetch_fb_revenue("PAR", DAY))
    mcp_figures = (await mcp.fetch_occupancy("PAR", DAY), await mcp.fetch_fb_revenue("PAR", DAY))
    assert rest_figures == mcp_figures


# --- the sync stores true figures or NULL with the reason ----------------------------------

class _Session:
    def __init__(self, stored):
        self.stored = stored

    async def __aenter__(self):
        return self

    async def __aexit__(self, *a):
        return False

    def add(self, row):
        self.stored.append(row)

    async def commit(self):
        return None


async def _sync(adapter):
    stored = []
    service = PMSSyncService(adapter)
    with (
        patch("app.services.pms_sync.AsyncSessionLocal", lambda: _Session(stored)),
        patch.object(service, "_trigger_captation_recalculation", new_callable=AsyncMock),
        patch("app.services.ops_dispatcher.dispatch_report", new_callable=AsyncMock) as report,
        patch("app.integrations.obsidian.VAULT_FOLDERS", {"sync_logs": "logs"}, create=True),
    ):
        out = await service.sync_daily_data(PmsTarget("pilot_hotel", "apaleo", "PAR"), DAY)
    return stored[0], out, report.await_args.kwargs["content"]


@pytest.mark.asyncio
async def test_sync_stores_room_counts_and_net_fb_revenue():
    row, out, report = await _sync(_mcp({"data": REPORT}))
    assert (row.rooms_sold, row.rooms_available, row.occupancy_status) == (90, 120, "ok")
    assert (row.fb_revenue, row.fb_revenue_currency, row.fb_revenue_status) == (1840.5, "EUR", "ok")
    assert row.occupancy is None and row.status == "success"
    assert out["occupancy_rate"] == 75
    assert "90 / 120 rooms (75%)" in report


@pytest.mark.asyncio
@pytest.mark.parametrize("adapter, status", [
    (_mcp(configured=False), "not_configured"),
    (_mcp(fail=True), "pms_error"),
    (_mcp({"data": {}}), "no_data"),
])
async def test_sync_stores_null_and_the_reason_never_80_or_0(adapter, status):
    row, out, report = await _sync(adapter)
    assert row.rooms_sold is None and row.rooms_available is None and row.fb_revenue is None
    assert row.occupancy is None
    assert row.occupancy_status == row.fb_revenue_status == status
    assert row.status == "incomplete"
    assert out["occupancy_rate"] is None
    assert f"absent ({status})" in report


@pytest.mark.asyncio
async def test_sync_records_an_adapter_that_raises_as_a_pms_error():
    class _Raising:
        provider_name = APALEO

        async def fetch_occupancy(self, *a):
            raise RuntimeError("socket closed")

        async def fetch_fb_revenue(self, *a):
            raise RuntimeError("socket closed")

    row, _, _ = await _sync(_Raising())
    assert row.occupancy_status == row.fb_revenue_status == "pms_error"
    assert row.error_message == "socket closed"


@pytest.mark.asyncio
async def test_mock_figures_are_stored_as_fixtures():
    row, _, _ = await _sync(MockPMSAdapter())
    assert row.occupancy_status == row.fb_revenue_status == "fixture"


# --- golden scenarios (eval layer pms_input, HOS-352) ---------------------------------------

def _golden():
    import json
    from pathlib import Path

    path = Path(__file__).resolve().parents[2] / "eval" / "golden_dataset.jsonl"
    rows = (json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip())
    return [r for r in rows if r["layer"] == "pms_input"]


_PMS_GOLDEN = _golden()


def test_pms_input_golden_scenarios_exist():
    assert len(_PMS_GOLDEN) >= 4


@pytest.mark.asyncio
@pytest.mark.parametrize("scenario", _PMS_GOLDEN, ids=[s["id"] for s in _PMS_GOLDEN])
async def test_pms_input_golden_scenarios(scenario):
    """PMS report → stored sync row → captation query, all production code.
    The pms_input layer has no eval runner; these golden rows are graded here."""
    from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
    from sqlalchemy.pool import StaticPool

    from app.db.models import Base
    from app.services.captation_service import CaptationService

    exp = scenario["expected"]
    row, _, _ = await _sync(_mcp({"data": scenario["input"]["report"]}))
    assert (row.occupancy_status, row.rooms_sold, row.rooms_available) == (
        exp["occupancy_status"], exp["rooms_sold"], exp["rooms_available"])
    assert (row.fb_revenue_status, row.fb_revenue) == (exp["fb_revenue_status"], exp["fb_revenue"])
    if "currency" in exp:
        assert row.fb_revenue_currency == exp["currency"]
    assert row.occupancy is None   # the legacy mixed-unit column is never written

    engine = create_async_engine("sqlite+aiosqlite:///:memory:", poolclass=StaticPool)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    async with async_sessionmaker(engine, expire_on_commit=False)() as db:
        db.add(row)
        await db.commit()
        used = await CaptationService()._load_sync_logs(row.tenant_id, db)
    await engine.dispose()
    assert bool(used) is exp["feeds_captation"]
    if "captation_rate" in exp:
        assert CaptationService()._to_dataframe(used)["captation_rate"].iloc[0] == pytest.approx(exp["captation_rate"])

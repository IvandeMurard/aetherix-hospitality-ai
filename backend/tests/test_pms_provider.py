"""Vendor-neutral PMS layer — HOS-280 (Décision #28, ADR-0006 §9).

Mapping of Apaleo payloads to the canonical dataclasses, honest labels
(unit, scope, placeholder), the factory, and the non-regression rule: the
values the sync stores are identical to what the legacy adapter methods return.
"""
from __future__ import annotations

from datetime import date
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.providers.pms.apaleo_adapter import ApaleoPMSAdapter, map_stay_record, revenue_from_items
from app.providers.pms.apaleo_mcp_adapter import ApaleoMCPAdapter
from app.providers.pms.base import (
    OccupancyUnit, PMSProvider, PMSProviderName, RevenueScope,
)
from app.providers.pms.factory import get_pms_provider
from app.providers.pms.mock_adapter import MockPMSAdapter
from app.services.pms_identity import PmsIdentityError, PmsTarget
from app.services.pms_sync import PMSAdapter, PMSSyncService

DAY = date(2026, 10, 17)


# --- protocol and factory --------------------------------------------------------------

def test_every_adapter_implements_the_canonical_protocol_and_the_legacy_abc():
    for adapter in (ApaleoPMSAdapter("id", "secret"), ApaleoMCPAdapter(mcp_client=MagicMock(is_configured=False)),
                    MockPMSAdapter()):
        assert isinstance(adapter, PMSProvider)
        assert isinstance(adapter, PMSAdapter)


def test_factory_is_per_pms_type_and_refuses_a_pms_without_adapter():
    assert get_pms_provider("apaleo", "rest") is get_pms_provider("apaleo", "rest")
    assert get_pms_provider("apaleo", "mcp").transport == "mcp"
    with pytest.raises(PmsIdentityError) as e:
        get_pms_provider("mews", "rest")
    assert e.value.reason == "pms_not_supported"


# --- pure mappings -------------------------------------------------------------------

def test_stay_record_maps_to_a_canonical_reservation():
    r = map_stay_record({"id": "RES-1", "arrival": "2026-10-17T15:00:00+02:00", "departure": "2026-10-19",
                         "adults": 2, "children": 1, "status": "Confirmed", "guest_name": "x"})
    assert (r.vendor_reservation_id, r.arrival, r.departure, r.guests, r.status) == (
        "RES-1", date(2026, 10, 17), date(2026, 10, 19), 3, "Confirmed")
    assert r.provider == PMSProviderName.APALEO and "guest_name" in r.raw_fields


def test_children_as_a_list_of_ages_counts_children():
    assert map_stay_record({"arrival": "2026-10-17", "adults": 2, "children": [4, 7]}).children == 2


def test_revenue_rule_is_unchanged_and_now_labelled():
    items = [{"category": "F&B", "amount": 1200.5}, {"category": "Rooms", "amount": 5000.0}]
    assert revenue_from_items(items, "F&B") == (1200.5, RevenueScope.CATEGORY)
    assert revenue_from_items([{"category": "Rooms", "amount": 5000.0}], "F&B") == (5000.0, RevenueScope.TOTAL_FALLBACK)


# --- MCP adapter: values unchanged, placeholders flagged ---------------------------------

def _mcp(payloads=None, configured=True, fail=False):
    client = MagicMock(is_configured=configured)

    async def call_tool(name, args):
        if fail:
            raise RuntimeError("down")
        return payloads[name]

    client.call_tool = call_tool
    return ApaleoMCPAdapter(mcp_client=client)


@pytest.mark.asyncio
async def test_mcp_occupancy_is_a_percentage_with_rooms():
    a = _mcp({"ListPropertyPerformanceReport": {"data": {"houseCount": 120, "soldCount": 90}}})
    occ = await a.fetch_occupancy("PAR", DAY)
    assert (occ.value, occ.unit, occ.rooms_sold, occ.rooms_available, occ.is_placeholder) == (
        75, OccupancyUnit.PERCENT, 90, 120, False)
    assert await a.get_occupancy("PAR", DAY) == 75


@pytest.mark.asyncio
@pytest.mark.parametrize("adapter", [
    _mcp(configured=False), _mcp(fail=True),
    _mcp({"ListPropertyPerformanceReport": {"data": {"houseCount": 0, "soldCount": 0}}}),
])
async def test_mcp_placeholder_80_is_kept_but_flagged(adapter):
    occ = await adapter.fetch_occupancy("PAR", DAY)
    assert occ.value == 80 and occ.is_placeholder is True
    assert await adapter.get_occupancy("PAR", DAY) == 80


@pytest.mark.asyncio
async def test_mcp_revenue_ignores_category_and_says_so():
    a = _mcp({"ListRevenuesReport": {"data": [{"grossAmount": {"amount": 100.0}}, {"grossAmount": {"amount": 50.5}}]}})
    rev = await a.fetch_revenue("PAR", DAY, "F&B")
    assert (rev.amount, rev.scope, rev.is_placeholder) == (150.5, RevenueScope.ALL_REVENUE, False)
    unconfigured = await _mcp(configured=False).fetch_revenue("PAR", DAY)
    assert (unconfigured.amount, unconfigured.is_placeholder) == (0.0, True)


@pytest.mark.asyncio
async def test_mcp_reservations_are_canonical():
    a = _mcp({"ListReservations": {"data": {"reservations": [
        {"id": "R1", "arrival": "2026-10-17T14:00:00Z", "adults": 2, "children": 0, "status": "Confirmed"}]}}})
    (r,) = await a.fetch_reservations("PAR", DAY, DAY)
    assert (r.vendor_reservation_id, r.arrival, r.guests) == ("R1", DAY, 2)


# --- non-regression: the sync stores exactly the legacy values -----------------------------

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


async def _sync_values(adapter):
    stored = []
    service = PMSSyncService(adapter)
    with (
        patch("app.services.pms_sync.AsyncSessionLocal", lambda: _Session(stored)),
        patch.object(service, "_trigger_captation_recalculation", new_callable=AsyncMock),
        patch("app.services.ops_dispatcher.dispatch_report", new_callable=AsyncMock),
        patch("app.integrations.obsidian.VAULT_FOLDERS", {"sync_logs": "logs"}, create=True),
    ):
        await service.sync_daily_data(PmsTarget("pilot_hotel", "apaleo", "pilot_hotel"), DAY)
    return stored[0].occupancy, stored[0].fb_revenue


@pytest.mark.asyncio
@pytest.mark.parametrize("make", [
    lambda: MockPMSAdapter(),
    lambda: _mcp({"ListPropertyPerformanceReport": {"data": {"houseCount": 120, "soldCount": 90}},
                  "ListRevenuesReport": {"data": [{"grossAmount": {"amount": 321.5}}]}}),
    lambda: _mcp(configured=False),
])
async def test_sync_log_values_are_identical_to_the_legacy_methods(make):
    legacy = make()
    expected = (await legacy.get_occupancy("pilot_hotel", DAY), await legacy.get_revenue("pilot_hotel", DAY, "F&B"))
    assert await _sync_values(make()) == expected


@pytest.mark.asyncio
async def test_rest_sync_values_are_identical_to_the_legacy_methods():
    def response(json_body):
        r = MagicMock(status_code=200)
        r.json.return_value = json_body
        return r

    bodies = {
        "/booking/v1/metrics/occupancy": {"occupancy": 72},
        "/finance/v1/metrics/revenue": {"revenue": [{"category": "F&B", "amount": 980.0},
                                                    {"category": "Rooms", "amount": 4000.0}]},
    }

    class _Client:
        async def __aenter__(self):
            return self

        async def __aexit__(self, *a):
            return False

        async def get(self, url, params=None, headers=None):
            return response(next(v for k, v in bodies.items() if url.endswith(k)))

    def make():
        a = ApaleoPMSAdapter("id", "secret")
        a.access_token, a.token_expiry = "t", 10**12
        return a

    with patch("app.providers.pms.apaleo_adapter.httpx.AsyncClient", lambda *a, **k: _Client()):
        legacy = make()
        expected = (await legacy.get_occupancy("PAR", DAY), await legacy.get_revenue("PAR", DAY, "F&B"))
        assert expected == (72, 980.0)
        assert await _sync_values(make()) == expected
        occ = await make().fetch_occupancy("PAR", DAY)
        assert occ.unit == OccupancyUnit.AS_REPORTED and not occ.is_placeholder

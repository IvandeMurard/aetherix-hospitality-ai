"""HOS-211 — `VAULT_FOLDERS` is defined and the ops-dispatch paths that consume
it no longer ImportError.

Latent bug: `VAULT_FOLDERS` was imported in four places (ops_dispatcher ×2,
pms_sync, reporting_service) but never defined in `obsidian.py`. The
`reporting_service._dispatch_ops` import sat at method top-level (outside any
try/except), so `GET /reports/weekly` raised `ImportError` → 500. The
ops_dispatcher imports were inside try/except and failed silently instead.
"""
from __future__ import annotations

import pytest


def test_vault_folders_defined_with_required_keys():
    from app.integrations.obsidian import VAULT_FOLDERS

    assert {"reports", "alerts", "sync_logs"} <= set(VAULT_FOLDERS)
    assert all(isinstance(v, str) and v for v in VAULT_FOLDERS.values())


@pytest.mark.asyncio
async def test_dispatch_report_writes_note_to_vault(tmp_path, monkeypatch):
    """dispatch_report resolves VAULT_FOLDERS['reports'] and writes a note."""
    monkeypatch.setenv("OBSIDIAN_VAULT_PATH", str(tmp_path))
    from app.integrations.obsidian import VAULT_FOLDERS
    from app.services.ops_dispatcher import dispatch_report

    await dispatch_report(title="HOS-211 smoke", content="ok")

    notes = list((tmp_path / VAULT_FOLDERS["reports"]).glob("*.md"))
    assert len(notes) == 1


@pytest.mark.asyncio
async def test_dispatch_ops_is_fire_and_forget_and_trips_alert():
    """HOS-248 AC5 — the HOS-211 path (`reporting_service._dispatch_ops`) must
    never bubble an exception to the caller (no more `/reports/weekly` 500) and
    must trip a typed ops alert instead of failing silently."""
    from unittest.mock import AsyncMock, patch

    from app.services.reporting_service import ReportingService

    result = {
        "tenant_id": "h1",
        "period": "2026-06-01 to 2026-06-07",
        "metrics": {"mape": 10.0, "accuracy": 90.0, "total_covers": 100},
        "financial_impact": {"estimated_savings_gbp": 100.0, "roi_multiplier": 2.0},
    }
    trip = AsyncMock()
    with (
        patch(
            "app.services.ops_dispatcher.dispatch_report",
            AsyncMock(side_effect=RuntimeError("obsidian down")),
        ),
        patch("app.workers.heartbeat.record_trip", trip),
    ):
        # Must NOT raise despite the underlying failure.
        await ReportingService()._dispatch_ops(result, mape=10.0)

    trip.assert_awaited_once()
    assert trip.await_args.args[0] == "reporting_service"

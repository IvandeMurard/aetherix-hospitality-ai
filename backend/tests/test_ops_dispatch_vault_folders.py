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

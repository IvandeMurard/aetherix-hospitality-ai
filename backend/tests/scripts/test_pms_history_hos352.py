"""HOS-352 AC5 — correction plan for pre-HOS-352 PMS rows (pure logic, no DB)."""
from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from types import SimpleNamespace as Row

_SCRIPT = Path(__file__).resolve().parents[3] / "scripts" / "ops" / "pms_history_hos352.py"
_spec = importlib.util.spec_from_file_location("pms_history_hos352", _SCRIPT)
plan_mod = importlib.util.module_from_spec(_spec)
sys.modules["pms_history_hos352"] = plan_mod
_spec.loader.exec_module(plan_mod)


def _rows(tenant, total, legacy, usable, absent=0):
    return Row(tenant_id=tenant, total=total, legacy=legacy, usable=usable, absent_or_fixture=absent)


def _baseline(tenant, avg=20.0, points=30):
    return Row(tenant_id=tenant, avg_fb_revenue_per_room=avg, data_points_count=points, computed_at="2026-09-01")


def test_a_baseline_built_only_on_legacy_rows_is_deleted():
    (e,) = plan_mod.build_plan([_rows("sandbox", 40, 40, 0)], [_baseline("sandbox")])
    assert e["action"] == "delete_baseline"


def test_a_baseline_with_enough_pms_reported_days_is_recomputed():
    n = plan_mod.MIN_DATA_POINTS
    (e,) = plan_mod.build_plan([_rows("pilot", 40, 10, n, 2)], [_baseline("pilot")])
    assert e["action"] == "recompute_baseline"


def test_legacy_sync_rows_are_kept_and_counted_never_deleted():
    plan = plan_mod.build_plan([_rows("a", 12, 12, 0), _rows("b", 3, 3, 0)], [])
    assert [e["action"] for e in plan] == ["none", "none"]
    assert "legacy sync rows kept: 15" in plan_mod.render(plan)


def test_a_baseline_without_any_sync_row_is_deleted():
    (e,) = plan_mod.build_plan([], [_baseline("orphan")])
    assert e["action"] == "delete_baseline"


def test_apply_requires_confirm(monkeypatch):
    monkeypatch.setattr(sys, "argv", ["x", "--apply"])
    assert plan_mod.main() == 2

#!/usr/bin/env python3
"""Historical PMS rows after HOS-352 — correction plan, dry-run by default.

Before HOS-352, ``pms_sync_logs`` could hold an invented occupancy (80) or
revenue (0.0), an occupancy in two different units, and total revenue in
``fb_revenue``. ``captation_baselines`` was computed from those rows.

What this plan does, per tenant:

* ``pms_sync_logs`` rows written before HOS-352 (no ``occupancy_status``) are
  **left in place**. Nothing reads them any more: captation selects only rows
  whose two figures have status ``ok`` (captation_service._load_sync_logs),
  and the dashboard derives occupancy from room counts these rows lack. They
  stay as the record of what was synced, labelled by the column comments of
  migration 20261018170000. Deleting them would remove history and fix nothing.
* a ``captation_baselines`` row is **deleted** when the tenant has fewer than
  ``MIN_DATA_POINTS`` PMS-reported days: it can only have been computed from
  pre-HOS-352 rows. Anomaly detection then uses its documented cold-start
  value until real days accumulate, instead of a baseline built on invented
  or mislabelled figures.
* otherwise the baseline is **recomputed** from the PMS-reported days only.

  # See the plan — default, no write
  python scripts/ops/pms_history_hos352.py

  # Apply it — requires --confirm on top of --apply
  python scripts/ops/pms_history_hos352.py --apply --confirm

Exit codes: 0 success · 2 usage error · 3 --apply before migration 20261018170000.
"""
from __future__ import annotations

import argparse
import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "backend"))
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sqlalchemy import text  # noqa: E402

from app.services.captation_service import (  # noqa: E402
    MIN_DATA_POINTS,
    CaptationService,
)

_ROWS = text("""
    SELECT tenant_id,
           count(*)                                                          AS total,
           count(*) FILTER (WHERE occupancy_status IS NULL)                  AS legacy,
           count(*) FILTER (WHERE occupancy_status = 'ok' AND fb_revenue_status = 'ok'
                              AND rooms_sold > 0 AND fb_revenue IS NOT NULL) AS usable,
           count(*) FILTER (WHERE occupancy_status IS NOT NULL
                              AND NOT (occupancy_status = 'ok' AND fb_revenue_status = 'ok')) AS absent_or_fixture
    FROM pms_sync_logs
    GROUP BY tenant_id
""")
_ROWS_PRE_MIGRATION = text("""
    SELECT tenant_id, count(*) AS total, count(*) AS legacy, 0 AS usable, 0 AS absent_or_fixture
    FROM pms_sync_logs
    GROUP BY tenant_id
""")
_BASELINES = text("""
    SELECT tenant_id, avg_fb_revenue_per_room, data_points_count, computed_at
    FROM captation_baselines
""")
_HAS_COLUMN = text("""
    SELECT 1 FROM information_schema.columns
    WHERE table_name = 'pms_sync_logs' AND column_name = 'occupancy_status'
""")


def build_plan(rows: list, baselines: list) -> list[dict]:
    """One entry per tenant seen in either table."""
    by_tenant: dict[str, dict] = {}
    for r in rows:
        by_tenant[r.tenant_id] = {"tenant_id": r.tenant_id, "total": r.total, "legacy": r.legacy,
                                  "usable": r.usable, "absent_or_fixture": r.absent_or_fixture, "baseline": None}
    for b in baselines:
        entry = by_tenant.setdefault(b.tenant_id, {"tenant_id": b.tenant_id, "total": 0, "legacy": 0,
                                                   "usable": 0, "absent_or_fixture": 0, "baseline": None})
        entry["baseline"] = {"avg": b.avg_fb_revenue_per_room, "points": b.data_points_count,
                             "computed_at": str(b.computed_at)}
    for e in by_tenant.values():
        if e["baseline"] is None:
            e["action"] = "none"
        elif e["usable"] < MIN_DATA_POINTS:
            e["action"] = "delete_baseline"
        else:
            e["action"] = "recompute_baseline"
    return sorted(by_tenant.values(), key=lambda e: e["tenant_id"])


def render(plan: list[dict]) -> str:
    lines = ["tenant | sync rows | legacy (kept, unread) | PMS-reported usable | absent/fixture | baseline | action"]
    for e in plan:
        b = e["baseline"]
        baseline = "—" if b is None else f"{b['avg']:.2f}/room, {b['points']} pts"
        lines.append(f"{e['tenant_id']} | {e['total']} | {e['legacy']} | {e['usable']} | "
                     f"{e['absent_or_fixture']} | {baseline} | {e['action']}")
    counts = {a: sum(1 for e in plan if e["action"] == a) for a in ("delete_baseline", "recompute_baseline")}
    lines.append(f"\nlegacy sync rows kept: {sum(e['legacy'] for e in plan)} · baselines to delete: "
                 f"{counts['delete_baseline']} · to recompute: {counts['recompute_baseline']}")
    return "\n".join(lines)


async def _run(apply: bool) -> int:
    from app.db.session import AsyncSessionLocal  # noqa: PLC0415 — after load_env()

    async with AsyncSessionLocal() as session:
        migrated = (await session.execute(_HAS_COLUMN)).first() is not None
        rows = (await session.execute(_ROWS if migrated else _ROWS_PRE_MIGRATION)).all()
        plan = build_plan(rows, (await session.execute(_BASELINES)).all())
        if not migrated:
            print("Migration 20261018170000 not applied yet: every row is pre-HOS-352.\n")
        print(render(plan))
        if apply and not migrated:
            print("\nApply the migration first.", file=sys.stderr)
            return 3
        if not apply:
            print("\nDry-run: nothing written. --apply --confirm to apply.")
            return 0
        for e in plan:
            if e["action"] == "delete_baseline":
                await session.execute(text("DELETE FROM captation_baselines WHERE tenant_id = :t"),
                                      {"t": e["tenant_id"]})
                await session.commit()
            elif e["action"] == "recompute_baseline":
                await CaptationService().calculate_baseline(e["tenant_id"], session)
        print("\nApplied.")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--apply", action="store_true", help="apply the plan (needs --confirm)")
    parser.add_argument("--confirm", action="store_true", help="second lock for --apply")
    args = parser.parse_args()
    if args.apply != args.confirm:
        print("--apply and --confirm go together.", file=sys.stderr)
        return 2
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8", errors="replace")
    from _env_loader import load_env  # noqa: PLC0415

    load_env()
    return asyncio.run(_run(args.apply))


if __name__ == "__main__":
    sys.exit(main())

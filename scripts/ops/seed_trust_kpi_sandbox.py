"""seed_trust_kpi_sandbox.py — HOS-190 AC6 fixture seed.

Seeds the sandbox tenant (`tenant_sandbox`) with 5 `followed` + 2 `rejected`
manager-feedback rows in `operational_memory` plus 7 matching `agent_action_log`
rows, all dated *yesterday* so the 02:30 UTC `kpi_aggregator` worker picks them
up on its next run.

Naming mapping (per backend/app/mcp_server.py:259 feedback_map):
    public outcome   →   internal manager_feedback
    accepted             followed
    modified             neutral
    rejected             rejected

Expected post-run state:
    kpi_daily(tenant_id='tenant_sandbox', kpi_date=yesterday,
              kpi_name='recommendation_acceptance_rate')
    value ≈ 0.714  (5 followed / 7 total)
    numerator = 5
    denominator = 7

Usage:
    cd backend
    python ../scripts/ops/seed_trust_kpi_sandbox.py
    # then either wait for the 02:30 UTC cron, or run the worker in-process:
    python -c "import asyncio; from app.workers.kpi_aggregator import run_kpi_aggregation; asyncio.run(run_kpi_aggregation())"

Idempotency:
    Rerunning is safe — fixtures are tagged via a constant request_id prefix
    (`hos190-seed-`) and an upsert pattern on (tenant_id, kpi_date, kpi_name)
    in the kpi_daily worker handles repeats.

Cleanup (when retiring the seed):
    DELETE FROM operational_memory WHERE request_id LIKE 'hos190-seed-%';
    DELETE FROM agent_action_log    WHERE request_id LIKE 'hos190-seed-%';
    DELETE FROM kpi_daily           WHERE tenant_id = 'tenant_sandbox';
"""
from __future__ import annotations

import asyncio
import logging
import sys
import uuid
from datetime import date, datetime, time, timedelta, timezone

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger("seed_trust_kpi_sandbox")

TENANT_ID = "tenant_sandbox"
TOOL_NAME = "get_recommendations_with_memory_context"
REQUEST_ID_PREFIX = "hos190-seed-"

# 5 followed + 2 rejected — produces rate = 5/7 = 0.714
FIXTURES: list[tuple[str, str]] = [
    ("followed", "Manager confirmed staffing recommendation +1 server for CL night."),
    ("followed", "Manager followed reduced prep guidance — saved ~€60 food cost."),
    ("followed", "Manager kept recommended 6 servers — actuals 71 covers (forecast 74)."),
    ("followed", "Brunch staffing +1 host followed — Saturday peak handled smoothly."),
    ("followed", "Dinner mise en place per forecast — minimal waste reported."),
    ("rejected", "Manager kept 5 servers — disagreed with CL impact, actuals matched plan."),
    ("rejected", "Manager ignored walk-in spike alert — relied on bookings only."),
]


async def main() -> int:
    try:
        from app.db.models import AgentActionLog, OperationalMemory
        from app.db.session import AsyncSessionLocal
    except ImportError as exc:
        log.error(
            "Cannot import app modules — run from `backend/` with the project's "
            "venv activated. Original: %s",
            exc,
        )
        return 2

    yesterday = date.today() - timedelta(days=1)
    # Spread the rows across the day so they cluster under a single kpi_date
    base_ts = datetime.combine(yesterday, time(12, 0), tzinfo=timezone.utc)

    inserted = 0
    async with AsyncSessionLocal() as session:
        for idx, (feedback, reflection) in enumerate(FIXTURES):
            request_id = f"{REQUEST_ID_PREFIX}{idx}"
            ts = base_ts + timedelta(minutes=idx * 5)

            mem = OperationalMemory(
                id=uuid.uuid4(),
                hotel_id=TENANT_ID,
                session_id=f"sandbox-session-{idx}",
                reflection=reflection,
                reco_json={"hos190_seed": True, "index": idx},
                manager_feedback=feedback,
                outcome=None,
                memory_type="feedback",
                tags=["hos190", "sandbox-seed"],
                embedding=None,
                embedding_pending=False,
                request_id=request_id,
                created_at=ts,
            )

            log_row = AgentActionLog(
                id=uuid.uuid4(),
                created_at=ts,
                hotel_id=TENANT_ID,
                tool_name=TOOL_NAME,
                scopes=["memory:read", "predict"],
                status="ok",
                latency_ms=180,
                request_id=request_id,
            )

            session.add(mem)
            session.add(log_row)
            inserted += 1

        await session.commit()

    log.info(
        "Seeded %d operational_memory + %d agent_action_log rows for tenant=%s on %s",
        inserted, inserted, TENANT_ID, yesterday.isoformat(),
    )
    log.info(
        "Next: refresh the MV and run the aggregator → "
        "`python -c \"import asyncio; from app.workers.kpi_aggregator import "
        "run_kpi_aggregation; asyncio.run(run_kpi_aggregation())\"`"
    )
    log.info(
        "Verify with: SELECT * FROM kpi_daily WHERE tenant_id='%s' AND kpi_date='%s';",
        TENANT_ID, yesterday.isoformat(),
    )
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))

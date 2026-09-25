"""Weekly learning pass — proposes, never applies (ADR-0007 §18.5, Décision #40).

Every Monday (RECEIPT_TIMEZONE, 03:40), for each active hotel:

* arm C: calibration of the risk statements the hotel received (did "≈25 %"
  happen about 1 in 4?) per task class × decider × calibration version, and
  coverage of the stored intervals on realised covers;
* arm B: a typed trip (``agent_action_log``, ``tool_name =
  "learning.risk_calibration"``, ``error_code = risk_statement_miscalibrated``)
  and an ops anomaly for every miscalibrated group (from n ≥ 30);
* proposals in ``learning_items``: a realised recalibration (canary + freeze
  rule passed), cost / constraint updates (human decisions only), routed
  reasons to review. Nothing is applied: approval is a named person's act
  (``learning_store.decide``).

A failure for one hotel is logged and does not stop the others.
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Optional

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from sqlalchemy import select

from app.core import config
from app.db.models import AgentActionLog, RestaurantProfile
from app.db.session import AsyncSessionLocal
from app.services import learning_store

logger = logging.getLogger(__name__)

TRIP_TOOL = "learning.risk_calibration"


async def _record_alerts(tenant_id: str, alerts: list[dict]) -> None:
    if not alerts:
        return
    try:
        async with AsyncSessionLocal() as db:
            for a in alerts:
                db.add(AgentActionLog(
                    hotel_id=tenant_id, tool_name=TRIP_TOOL, status="tool_error",
                    error_code=a["reason"], payload={"kind": "trip", **a}, request_id="",
                ))
            await db.commit()
    except Exception as exc:  # noqa: BLE001
        logger.warning("learning_loop: agent_action_log write failed: %s", exc)
    try:
        from app.services.ops_dispatcher import dispatch_anomaly

        await dispatch_anomaly(
            title=f"risk statements miscalibrated: {tenant_id} ({len(alerts)} group(s))",
            detail="\n".join(
                f"{a['group']}: stated {a['mean_stated']} vs observed {a['observed']} "
                f"(n={a['n']}, independent actuals={a['independent_actuals']})"
                for a in alerts
            ),
            tags=["learning_loop", "risk_statement_miscalibrated", tenant_id],
        )
    except Exception as exc:  # noqa: BLE001
        logger.warning("learning_loop: ops alert failed: %s", exc)


async def run_learning_pass(now: Optional[datetime] = None) -> dict[str, dict]:
    now = now or datetime.now(timezone.utc)
    results: dict[str, dict] = {}
    async with AsyncSessionLocal() as db:
        tenants = (await db.execute(
            select(RestaurantProfile.tenant_id).where(RestaurantProfile.is_active.is_(True))
        )).scalars().all()
    for tenant_id in tenants:
        try:
            async with AsyncSessionLocal() as db:
                out = await learning_store.run_pass(db, tenant_id, now=now)
                await db.commit()
            await _record_alerts(tenant_id, out["alerts"])
            results[tenant_id] = {
                "rows": out["rows"], "alerts": len(out["alerts"]),
                "items_created": len(out["items_created"]),
                "calibration_proposal": out["calibration_proposal"]["reason"],
            }
            logger.info("learning_loop tenant=%s %s", tenant_id, results[tenant_id])
        except Exception:  # noqa: BLE001 — one hotel never stops the others
            logger.exception("learning_loop: pass failed for tenant=%s", tenant_id)
            results[tenant_id] = {"error": True}
    return results


def register_learning_loop_job(scheduler: AsyncIOScheduler) -> None:
    scheduler.add_job(
        run_learning_pass,
        trigger="cron",
        day_of_week="mon",
        hour=3,
        minute=40,
        timezone=config.RECEIPT_TIMEZONE,
        id="learning_loop",
        replace_existing=True,
        misfire_grace_time=3600,
    )

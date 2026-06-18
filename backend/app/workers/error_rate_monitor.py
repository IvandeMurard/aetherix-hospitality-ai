"""Epic 12 G-2 (HOS-249) — ops alerting on agent error-rate / LLM-timeout spikes.

``agent_action_log`` is a passive register: it records every served tool call
but never *alerts*. This monitor turns it into an alarm. On a fixed cadence it
evaluates a rolling window and trips an ops alert when any of three signals
breaches a config-driven threshold:

  1. **non-ok rate** (AC1) — fraction of rows with ``status != "ok"`` over the
     window, evaluated only once the window holds ≥ MIN_SAMPLES rows (a single
     error out of two calls is not a spike).
  2. **tool failures** (AC2) — absolute count of ``status="tool_error"`` rows.
  3. **LLM timeouts** (AC2) — absolute count of rows whose ``error_code`` matches
     the configured timeout substring (providers tag transient timeouts there).

Every trip is logged to ``agent_action_log`` with a typed reason (AC4 / NFR2)
and routed to ops via ``ops_dispatcher.dispatch_anomaly`` (Linear sink — SM
session 18/06, no Slack). Repeat alerts for the same metric are debounced
(AC3). All writes are fire-and-forget: the monitor never breaks itself.

Thresholds live in ``app.core.config`` and are documented in
``eval/FAILURE_THRESHOLDS.md`` (AC5).
"""
from __future__ import annotations

import logging
import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Optional

from sqlalchemy import case, func, select

from app.core import config
from app.db.models import AgentActionLog
from app.db.session import AsyncSessionLocal

logger = logging.getLogger(__name__)

# Sentinel hotel_id for system-level (non-tenant) rows. agent_action_log.hotel_id
# is NOT NULL, so monitor events use this rather than None (mirrors heartbeat).
SYSTEM_HOTEL_ID = "_system"

# Typed trip reasons (AC4 / NFR2). Stored in agent_action_log.error_code.
REASON_ERROR_RATE = "error_rate_spike"        # non-ok fraction over window too high
REASON_TOOL_FAILURES = "tool_failure_spike"   # too many tool_error rows
REASON_LLM_TIMEOUTS = "llm_timeout_spike"     # too many LLM/transient timeouts

# agent_action_log.tool_name for this monitor's own trip rows.
MONITOR_TOOL = "monitor.error_rate"

# In-memory debounce: last alert time per reason. Resets on process restart (an
# extra alert after a restart is acceptable; avoids per-poll flood otherwise).
_last_alerted: dict[str, datetime] = {}


@dataclass(frozen=True)
class WindowStats:
    """Aggregated agent_action_log counts over the rolling window."""

    total: int
    non_ok: int
    tool_errors: int
    llm_timeouts: int

    @property
    def non_ok_rate(self) -> float:
        return (self.non_ok / self.total) if self.total else 0.0


async def _gather_window_stats(db, cutoff: datetime) -> WindowStats:
    """One aggregate query over the window. Counts are computed DB-side so the
    monitor never materialises the full row set (NFR-friendly at scale)."""
    timeout_like = f"%{config.ERROR_RATE_TIMEOUT_ERROR_SUBSTR}%"
    # Exclude the monitor's own trip rows (tool_name "monitor.error_rate") so a
    # past alert can't inflate the next window into a feedback loop.
    stmt = select(
        func.count().label("total"),
        func.sum(case((AgentActionLog.status != "ok", 1), else_=0)).label("non_ok"),
        func.sum(case((AgentActionLog.status == "tool_error", 1), else_=0)).label("tool_errors"),
        func.sum(
            case((AgentActionLog.error_code.ilike(timeout_like), 1), else_=0)
        ).label("llm_timeouts"),
    ).where(
        AgentActionLog.created_at >= cutoff,
        AgentActionLog.tool_name != MONITOR_TOOL,
    )
    row = (await db.execute(stmt)).one()
    return WindowStats(
        total=int(row.total or 0),
        non_ok=int(row.non_ok or 0),
        tool_errors=int(row.tool_errors or 0),
        llm_timeouts=int(row.llm_timeouts or 0),
    )


# agent_action_log.tool_name for this monitor's own trip rows.
MONITOR_TOOL = "monitor.error_rate"


def evaluate(stats: WindowStats) -> list[tuple[str, str]]:
    """Pure threshold check. Returns a list of (reason, detail) breaches.

    The rate check is gated on MIN_SAMPLES; the two count checks fire regardless
    of volume (an absolute spike of failures is meaningful even at low traffic).
    """
    breaches: list[tuple[str, str]] = []

    if (
        stats.total >= config.ERROR_RATE_MIN_SAMPLES
        and stats.non_ok_rate > config.ERROR_RATE_NONOK_THRESHOLD
    ):
        breaches.append((
            REASON_ERROR_RATE,
            (
                f"non-ok rate {stats.non_ok_rate:.0%} ({stats.non_ok}/{stats.total}) "
                f"over last {config.ERROR_RATE_WINDOW_MIN} min exceeds threshold "
                f"{config.ERROR_RATE_NONOK_THRESHOLD:.0%}."
            ),
        ))

    if stats.tool_errors > config.ERROR_RATE_TOOL_FAILURE_THRESHOLD:
        breaches.append((
            REASON_TOOL_FAILURES,
            (
                f"{stats.tool_errors} tool failures over last "
                f"{config.ERROR_RATE_WINDOW_MIN} min exceeds threshold "
                f"{config.ERROR_RATE_TOOL_FAILURE_THRESHOLD}."
            ),
        ))

    if stats.llm_timeouts > config.ERROR_RATE_LLM_TIMEOUT_THRESHOLD:
        breaches.append((
            REASON_LLM_TIMEOUTS,
            (
                f"{stats.llm_timeouts} LLM timeouts over last "
                f"{config.ERROR_RATE_WINDOW_MIN} min exceeds threshold "
                f"{config.ERROR_RATE_LLM_TIMEOUT_THRESHOLD}."
            ),
        ))

    return breaches


def _should_alert(reason: str) -> bool:
    """Debounce repeat alerts for the same metric within the cooldown (AC3)."""
    now = datetime.utcnow()
    last = _last_alerted.get(reason)
    cooldown = config.ERROR_RATE_ALERT_COOLDOWN_MIN
    if last is not None and (now - last).total_seconds() / 60 < cooldown:
        return False
    _last_alerted[reason] = now
    return True


async def _write_trip_row(reason: str, detail: str) -> None:
    """Fire-and-forget typed trip row in agent_action_log (AC4). Never raises."""
    try:
        async with AsyncSessionLocal() as db:
            db.add(
                AgentActionLog(
                    hotel_id=SYSTEM_HOTEL_ID,
                    tool_name=MONITOR_TOOL,
                    status="tool_error",
                    error_code=reason,
                    payload={"kind": "trip", "reason": reason, "detail": detail},
                    request_id="",
                )
            )
            await db.commit()
    except Exception as exc:  # noqa: BLE001
        logger.warning("error_rate_monitor: agent_action_log write failed (%s): %s", reason, exc)


async def record_trip(reason: str, detail: str, *, debounce: bool = True) -> bool:
    """Log a typed trip + raise an ops alert (Linear, anomaly priority).

    Returns True when an alert was emitted, False when suppressed by debounce.
    """
    if debounce and not _should_alert(reason):
        logger.debug("error_rate_monitor: trip suppressed by debounce reason=%s", reason)
        return False

    await _write_trip_row(reason, detail)

    try:
        from app.services.ops_dispatcher import dispatch_anomaly

        await dispatch_anomaly(
            title=f"agent reliability: {reason}",
            detail=detail,
            tags=["error_rate_monitor", reason],
        )
    except Exception as exc:  # noqa: BLE001
        logger.warning("error_rate_monitor: dispatch_anomaly failed for %s: %s", reason, exc)

    logger.warning("error_rate_monitor: TRIP reason=%s — %s", reason, detail)
    return True


async def _run_error_rate_monitor_job() -> None:
    """Entry point: aggregate the window and trip on each breach (AC1/AC2)."""
    job_id = str(uuid.uuid4())[:8]
    cutoff = datetime.utcnow() - timedelta(minutes=config.ERROR_RATE_WINDOW_MIN)
    logger.info("error_rate_monitor: started job_id=%s", job_id)

    try:
        async with AsyncSessionLocal() as db:
            stats = await _gather_window_stats(db, cutoff)
        for reason, detail in evaluate(stats):
            await record_trip(reason, detail)
        logger.info(
            "error_rate_monitor: complete job_id=%s total=%d non_ok=%d tool_err=%d timeouts=%d",
            job_id, stats.total, stats.non_ok, stats.tool_errors, stats.llm_timeouts,
        )
    except Exception as exc:
        logger.exception("error_rate_monitor: fatal error job_id=%s", job_id)
        try:
            from app.services.ops_dispatcher import dispatch_error

            await dispatch_error(
                title="error_rate_monitor job failed",
                detail=f"Agent reliability monitor failed. job_id={job_id}. Error: {exc!r}",
                tags=["error_rate_monitor", "worker"],
            )
        except Exception as inner:  # noqa: BLE001
            logger.warning("error_rate_monitor: dispatch_error failed: %s", inner)
        raise


def _monitor_cron_minute(interval_min: int) -> str:
    """Cron minute step for the poll cadence. Guards the same 0–59 limit as the
    heartbeat monitor (HOS-212): an interval ≥ 60 is clamped to a 30-min poll so
    registration never raises (this monitor's window is the real cadence knob)."""
    if interval_min < 1:
        interval_min = 1
    if interval_min >= 60:
        return "*/30"
    return f"*/{interval_min}"


def register_error_rate_monitor_job(scheduler) -> None:
    """Register the rolling-window error-rate monitor on the shared scheduler."""
    scheduler.add_job(
        _run_error_rate_monitor_job,
        trigger="cron",
        minute=_monitor_cron_minute(config.ERROR_RATE_MONITOR_INTERVAL_MIN),
        id="error_rate_monitor",
        replace_existing=True,
        misfire_grace_time=60,
    )
    logger.info(
        "error_rate_monitor: cron job registered (interval %d min, window %d min)",
        config.ERROR_RATE_MONITOR_INTERVAL_MIN,
        config.ERROR_RATE_WINDOW_MIN,
    )

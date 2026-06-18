"""Epic 12 G-1 (HOS-248) — Heartbeat / dead-man's switch for scheduled jobs.

Scheduled paths (Daily Receipt, Weekly Digest, dispatch_worker) used to *record*
but not *alert*: a cron that errors or never fires was silent. This module closes
that gap with two mechanisms:

  1. **Heartbeat** — each scheduled job calls `record_heartbeat(job)` on a
     successful run, persisting a queryable "last good run" marker in
     `agent_action_log` (status="ok", tool_name="scheduler.<job>"). No new table
     (HOS-248: migration not required).

  2. **Dead-man's switch** — `heartbeat_monitor` polls every
     HEARTBEAT_MONITOR_INTERVAL_MIN and trips an ops alert when a job's last
     heartbeat is older than its configured window (config-driven, no redeploy).

Every trip is logged to `agent_action_log` with a typed reason (AC3) and routed
to ops via `ops_dispatcher.dispatch_error` (Linear sink — already wired, mirror
Obsidian included). All writes are fire-and-forget: instrumentation never breaks
the job it observes.

Sink decision (SM session 18/06): Linear via ops_dispatcher. No Slack.
"""
from __future__ import annotations

import logging
import uuid
from datetime import datetime
from typing import Optional

from sqlalchemy import func, select

from app.core import config
from app.db.models import AgentActionLog
from app.db.session import AsyncSessionLocal

logger = logging.getLogger(__name__)

# Sentinel hotel_id for system-level (non-tenant) rows. agent_action_log.hotel_id
# is NOT NULL, so scheduler events use this rather than None.
SYSTEM_HOTEL_ID = "_system"

# Typed trip reasons (AC3 / NFR2 Epic 12). Stored in agent_action_log.error_code.
REASON_JOB_ERROR = "job_error"                 # a run raised / failed
REASON_DEAD_MAN = "dead_man_timeout"           # a run never fired within its window
REASON_PARTIAL = "partial_hotel_failures"      # run completed but N per-hotel failures

# In-memory debounce: last alert time per (job, reason). Resets on process restart
# (an extra alert after a restart is acceptable; avoids per-poll flood otherwise).
_last_alerted: dict[tuple[str, str], datetime] = {}


def _window_min(job_name: str) -> Optional[int]:
    """Max tolerated gap (minutes) since last good run for a monitored job.

    Read from config at call-time so env-driven retuning needs no redeploy
    and tests can monkeypatch config attributes.
    """
    return {
        "receipt_dispatcher": config.HEARTBEAT_WINDOW_RECEIPT_DISPATCHER_MIN,
        "weekly_digest": config.HEARTBEAT_WINDOW_WEEKLY_DIGEST_MIN,
        "dispatch_worker": config.HEARTBEAT_WINDOW_DISPATCH_WORKER_MIN,
    }.get(job_name)


def monitored_jobs() -> tuple[str, ...]:
    """Job ids covered by the dead-man's switch."""
    return ("receipt_dispatcher", "weekly_digest", "dispatch_worker")


async def _write_log_row(
    tool_name: str,
    status: str,
    error_code: Optional[str] = None,
    payload: Optional[dict] = None,
) -> None:
    """Fire-and-forget insert into agent_action_log. Never raises."""
    try:
        async with AsyncSessionLocal() as db:
            db.add(
                AgentActionLog(
                    hotel_id=SYSTEM_HOTEL_ID,
                    tool_name=tool_name,
                    status=status,
                    error_code=error_code,
                    payload=payload,
                    request_id="",
                )
            )
            await db.commit()
    except Exception as exc:  # noqa: BLE001
        logger.warning("heartbeat: agent_action_log write failed (%s): %s", tool_name, exc)


async def record_heartbeat(job_name: str) -> None:
    """Persist a 'last good run' marker for a scheduled job (T1)."""
    await _write_log_row(
        tool_name=f"scheduler.{job_name}",
        status="ok",
        payload={"kind": "heartbeat", "job": job_name},
    )
    logger.debug("heartbeat: recorded for job=%s", job_name)


def _should_alert(job_name: str, reason: str) -> bool:
    """Debounce repeat alerts for the same (job, reason) within the cooldown."""
    now = datetime.utcnow()
    key = (job_name, reason)
    last = _last_alerted.get(key)
    cooldown = config.HEARTBEAT_ALERT_COOLDOWN_MIN
    if last is not None and (now - last).total_seconds() / 60 < cooldown:
        return False
    _last_alerted[key] = now
    return True


async def record_trip(
    job_name: str,
    reason: str,
    detail: str,
    *,
    debounce: bool = True,
) -> bool:
    """Log a typed trip + raise an ops alert (Linear). Fire-and-forget.

    Returns True when an alert was emitted, False when suppressed by debounce.
    """
    if debounce and not _should_alert(job_name, reason):
        logger.debug("heartbeat: trip suppressed by debounce job=%s reason=%s", job_name, reason)
        return False

    await _write_log_row(
        tool_name=f"scheduler.{job_name}",
        status="tool_error",
        error_code=reason,
        payload={"kind": "trip", "job": job_name, "reason": reason, "detail": detail},
    )

    try:
        from app.services.ops_dispatcher import dispatch_error

        await dispatch_error(
            title=f"scheduler trip: {job_name} [{reason}]",
            detail=detail,
            tags=["heartbeat", job_name, reason],
        )
    except Exception as exc:  # noqa: BLE001
        logger.warning("heartbeat: dispatch_error failed for %s: %s", job_name, exc)

    logger.warning("heartbeat: TRIP job=%s reason=%s — %s", job_name, reason, detail)
    return True


async def _last_heartbeat_at(db, job_name: str) -> Optional[datetime]:
    """Timestamp of the most recent successful heartbeat for a job, or None."""
    result = await db.execute(
        select(func.max(AgentActionLog.created_at)).where(
            AgentActionLog.tool_name == f"scheduler.{job_name}",
            AgentActionLog.status == "ok",
        )
    )
    return result.scalar_one_or_none()


async def _run_heartbeat_monitor_job() -> None:
    """Entry point: poll monitored jobs and trip on stale heartbeats (T2/AC2)."""
    job_id = str(uuid.uuid4())[:8]
    now = datetime.utcnow()
    logger.info("heartbeat_monitor: started job_id=%s", job_id)

    try:
        async with AsyncSessionLocal() as db:
            for job_name in monitored_jobs():
                window = _window_min(job_name)
                if window is None:
                    continue
                last = await _last_heartbeat_at(db, job_name)
                if last is None:
                    # No heartbeat ever recorded — skip to avoid false alarms on a
                    # fresh deploy before the first scheduled run lands.
                    continue
                # agent_action_log.created_at may be tz-aware (Postgres) or naive
                # (SQLite default). Normalise to naive-UTC for the gap comparison.
                last_naive = last.replace(tzinfo=None) if last.tzinfo else last
                gap_min = (now - last_naive).total_seconds() / 60
                if gap_min > window:
                    await record_trip(
                        job_name,
                        REASON_DEAD_MAN,
                        (
                            f"No successful run of '{job_name}' for {gap_min:.0f} min "
                            f"(window {window} min). Dead-man's switch tripped."
                        ),
                    )
        logger.info("heartbeat_monitor: complete job_id=%s", job_id)
    except Exception as exc:
        logger.exception("heartbeat_monitor: fatal error job_id=%s", job_id)
        try:
            from app.services.ops_dispatcher import dispatch_error

            await dispatch_error(
                title="heartbeat_monitor job failed",
                detail=f"Dead-man's switch monitor failed. job_id={job_id}. Error: {exc!r}",
                tags=["heartbeat_monitor", "worker"],
            )
        except Exception as inner:  # noqa: BLE001
            logger.warning("heartbeat_monitor: dispatch_error failed: %s", inner)
        raise


def register_heartbeat_monitor_job(scheduler) -> None:
    """Register the dead-man's-switch monitor on the shared scheduler.

    Fires every HEARTBEAT_MONITOR_INTERVAL_MIN minutes.
    """
    scheduler.add_job(
        _run_heartbeat_monitor_job,
        trigger="cron",
        minute=f"*/{config.HEARTBEAT_MONITOR_INTERVAL_MIN}",
        id="heartbeat_monitor",
        replace_existing=True,
        misfire_grace_time=60,
    )
    logger.info(
        "heartbeat_monitor: cron job registered (every %d min)",
        config.HEARTBEAT_MONITOR_INTERVAL_MIN,
    )

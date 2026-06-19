"""Epic 12 G-1 (HOS-248) — Heartbeat / dead-man's switch for scheduled jobs.

Scheduled paths (Daily Receipt, Weekly Digest, dispatch_worker) used to *record*
but not *alert*: a cron that errors or never fires was silent. This module closes
that gap with two mechanisms:

  1. **Heartbeat** — each scheduled job calls `record_heartbeat(job)` on a
     successful run, persisting a queryable "last good run" marker
     (event_type="heartbeat") in the dedicated `scheduler_event` table.

  2. **Dead-man's switch** — `heartbeat_monitor` polls every
     HEARTBEAT_MONITOR_INTERVAL_MIN and trips an ops alert when a job's last
     heartbeat is older than its configured window (config-driven, no redeploy).

Every trip is logged to `scheduler_event` (event_type="trip") with a typed reason
(AC3) and routed to ops via `ops_dispatcher.dispatch_error` (Linear sink — already
wired, mirror Obsidian included). All writes are fire-and-forget: instrumentation
never breaks the job it observes.

Storage (HOS-271): this telemetry lives in its own `scheduler_event` table, NOT in
`agent_action_log` (the per-MCP-tool-call billing + metering meter, ADR-0003 D1).
A ~2-min dispatch_worker heartbeat would otherwise inject ~720 rows/day/env into
the billing meter — `status='ok'` colliding with the tool-call enum and
`hotel_id='_system'` polluting every `GROUP BY hotel_id` rollup.

Sink decision (SM session 18/06): Linear via ops_dispatcher. No Slack.
"""
from __future__ import annotations

import logging
import uuid
from datetime import datetime
from typing import Optional

from sqlalchemy import func, select

from app.core import config
from app.db.models import SchedulerEvent
from app.db.session import AsyncSessionLocal

logger = logging.getLogger(__name__)

# scheduler_event.event_type discriminator.
EVENT_HEARTBEAT = "heartbeat"   # a successful "last good run" marker
EVENT_TRIP = "trip"             # a dead-man / job-error / partial-failure alert

# Typed trip reasons (AC3 / NFR2 Epic 12). Stored in scheduler_event.reason.
REASON_JOB_ERROR = "job_error"                 # a run raised / failed
REASON_DEAD_MAN = "dead_man_timeout"           # a run never fired within its window
REASON_PARTIAL = "partial_hotel_failures"      # run completed but N per-hotel failures

# In-memory debounce: last alert time per (job, reason). Resets on process restart
# (an extra alert after a restart is acceptable; avoids per-poll flood otherwise).
_last_alerted: dict[tuple[str, str], datetime] = {}


# ─── Monitored-jobs registry (HOS-273) ───────────────────────────────────────
# Single source of truth for the dead-man's switch. Previously the set of
# monitored jobs lived in THREE parallel places that had to stay in sync (the
# config vars, the _window_min() dict, and the monitored_jobs() tuple) and each
# call site hardcoded its own job string — so a new dispatcher could record a
# heartbeat that nothing ever polled (silent monitoring gap). Now: one entry in
# _MONITORED_JOBS registers a job, and both monitored_jobs() and _window_min()
# derive from it. Call sites import the JOB_* constants instead of literals.

# Job-name constants — call sites reference these, never a bare string, so a typo
# can't silently desync a heartbeat from the registry.
JOB_RECEIPT_DISPATCHER = "receipt_dispatcher"
JOB_WEEKLY_DIGEST = "weekly_digest"
JOB_DISPATCH_WORKER = "dispatch_worker"

# job_name → name of the config attribute holding its max tolerated gap (minutes).
# The attribute is resolved via getattr at call-time (not captured here) so that
# env-driven retuning needs no redeploy and tests can monkeypatch config. Adding a
# monitored job = one line here + its HEARTBEAT_WINDOW_* config var. Nothing else.
_MONITORED_JOBS: dict[str, str] = {
    JOB_RECEIPT_DISPATCHER: "HEARTBEAT_WINDOW_RECEIPT_DISPATCHER_MIN",
    JOB_WEEKLY_DIGEST: "HEARTBEAT_WINDOW_WEEKLY_DIGEST_MIN",
    JOB_DISPATCH_WORKER: "HEARTBEAT_WINDOW_DISPATCH_WORKER_MIN",
}


def _window_min(job_name: str) -> Optional[int]:
    """Max tolerated gap (minutes) since last good run for a monitored job.

    Resolved from the single _MONITORED_JOBS registry → config at call-time so
    env-driven retuning needs no redeploy and tests can monkeypatch config.
    Returns None for an unregistered job (the monitor then skips it).
    """
    attr = _MONITORED_JOBS.get(job_name)
    if attr is None:
        return None
    return getattr(config, attr, None)


def monitored_jobs() -> tuple[str, ...]:
    """Job ids covered by the dead-man's switch (derived from the registry)."""
    return tuple(_MONITORED_JOBS)


async def _write_event(
    job_name: str,
    event_type: str,
    *,
    reason: Optional[str] = None,
    detail: Optional[str] = None,
) -> None:
    """Fire-and-forget insert into scheduler_event. Never raises."""
    try:
        async with AsyncSessionLocal() as db:
            db.add(
                SchedulerEvent(
                    job_name=job_name,
                    event_type=event_type,
                    reason=reason,
                    detail=detail,
                )
            )
            await db.commit()
    except Exception as exc:  # noqa: BLE001
        logger.warning("heartbeat: scheduler_event write failed (%s/%s): %s", job_name, event_type, exc)


async def record_heartbeat(job_name: str) -> None:
    """Persist a 'last good run' marker for a scheduled job (T1).

    A heartbeat for a job absent from the _MONITORED_JOBS registry would never be
    polled by the dead-man's switch — exactly the silent-monitoring-gap class this
    Epic exists to prevent (HOS-273). Warn loudly rather than fail open. The marker
    is still written (it is harmless and observable), but ops gets a signal that the
    registry needs an entry.
    """
    if job_name not in _MONITORED_JOBS:
        logger.warning(
            "heartbeat: record_heartbeat('%s') for a job NOT in _MONITORED_JOBS — "
            "the dead-man's switch will never watch it. Add it to the registry.",
            job_name,
        )
    await _write_event(job_name, EVENT_HEARTBEAT)
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

    await _write_event(job_name, EVENT_TRIP, reason=reason, detail=detail)

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
    """Timestamp of the most recent successful heartbeat for a job, or None.

    Hits the dedicated scheduler_event table via idx_scheduler_event_job_type_created
    (job_name, event_type, created_at) — no longer an unindexed scan over the
    high-write billing meter.
    """
    result = await db.execute(
        select(func.max(SchedulerEvent.created_at)).where(
            SchedulerEvent.job_name == job_name,
            SchedulerEvent.event_type == EVENT_HEARTBEAT,
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


def _monitor_cron_trigger_kwargs(interval_min: int) -> dict:
    """Build APScheduler cron kwargs for the monitor poll cadence.

    QA-S4 follow-up (HOS-212): APScheduler's cron ``minute`` field only accepts
    0–59, so ``minute="*/N"`` with ``N >= 60`` raises ValueError at registration
    and the dead-man's switch never starts (a silent monitoring gap — the exact
    failure this Epic exists to prevent). Guard it: an interval ≥ 60 min is
    expressed as an hour-stepped cron instead (every ``N // 60`` hours, on the
    hour). Sub-minute / non-positive values floor to 1 min.
    """
    if interval_min < 1:
        interval_min = 1
    if interval_min < 60:
        return {"minute": f"*/{interval_min}"}
    # >= 60 min: step on the hour field. APScheduler's hour range is 0–23, so the
    # step value itself must stay ≤ 23 — cap there so an oversized config yields a
    # valid (~daily) poll rather than crashing registration.
    hours = min(max(interval_min // 60, 1), 23)
    return {"hour": f"*/{hours}", "minute": "0"}


def register_heartbeat_monitor_job(scheduler) -> None:
    """Register the dead-man's-switch monitor on the shared scheduler.

    Fires every HEARTBEAT_MONITOR_INTERVAL_MIN minutes (or every N hours when the
    configured interval is ≥ 60 min — see _monitor_cron_trigger_kwargs).
    """
    scheduler.add_job(
        _run_heartbeat_monitor_job,
        trigger="cron",
        id="heartbeat_monitor",
        replace_existing=True,
        misfire_grace_time=60,
        **_monitor_cron_trigger_kwargs(config.HEARTBEAT_MONITOR_INTERVAL_MIN),
    )
    logger.info(
        "heartbeat_monitor: cron job registered (interval %d min)",
        config.HEARTBEAT_MONITOR_INTERVAL_MIN,
    )

# Heartbeat / Dead-man's Switch Thresholds — "The Contract"

> **Source of truth** for when a scheduled job is considered *silently dead* and
> must raise an ops alert. Created by **HOS-248** (Epic 12 G-1). Sibling of
> `eval/FAILURE_THRESHOLDS.md`.
>
> **All thresholds are config-driven (env vars) — no redeploy needed to retune.**
> Defaults live in `backend/app/core/config.py`. Changing a default is an
> explicit decision — requires a PR + a CLAUDE.md trace.

---

## What is monitored

`backend/app/workers/heartbeat.py` runs a dead-man's-switch monitor
(`heartbeat_monitor`) on the shared APScheduler. Each scheduled dispatcher writes
a **heartbeat** (a `agent_action_log` row, `status="ok"`,
`tool_name="scheduler.<job>"`) on every successful run. The monitor trips an ops
alert (Linear, via `ops_dispatcher.dispatch_error`) when the gap since the last
heartbeat exceeds the job's window.

| Job id | Cadence | Window env var | Default | Rationale |
|---|---|---|---|---|
| `receipt_dispatcher` | daily @ `RECEIPT_DISPATCH_HOUR` | `HEARTBEAT_WINDOW_RECEIPT_DISPATCHER_MIN` | `1560` (26 h) | 24 h cadence + 2 h grace |
| `weekly_digest` | Sundays @ `RECEIPT_DISPATCH_HOUR` | `HEARTBEAT_WINDOW_WEEKLY_DIGEST_MIN` | `11520` (8 d) | 7 d cadence + 1 d grace |
| `dispatch_worker` | every 2 min | `HEARTBEAT_WINDOW_DISPATCH_WORKER_MIN` | `15` (min) | 2 min cadence + grace; keeps NFR2 (≤ 3 min delivery) observable |

> **Adding a monitored job (HOS-273):** the rows above are backed by a single
> registry — `_MONITORED_JOBS` in `heartbeat.py` maps each `job id` → its window
> env var. Add a job = one entry there + the matching `HEARTBEAT_WINDOW_*` default
> in `config.py` + a row here; `monitored_jobs()` and the window lookup derive from
> that registry, and call sites use the `JOB_*` constants (no bare strings). A
> heartbeat recorded for a job missing from the registry logs a loud warning.

| Monitor knob | Env var | Default | Notes |
|---|---|---|---|
| Poll interval | `HEARTBEAT_MONITOR_INTERVAL_MIN` | `15` (min) | How often the dead-man check runs |
| Alert debounce | `HEARTBEAT_ALERT_COOLDOWN_MIN` | `60` (min) | Suppresses repeat alerts for the same (job, reason) while it stays down |

---

## Typed trip reasons (AC3 / NFR2)

Every trip writes an `agent_action_log` row (`status="tool_error"`,
`error_code=<reason>`, `hotel_id="_system"`) **and** raises a Linear alert.

| Reason (`error_code`) | Meaning | Raised by |
|---|---|---|
| `job_error` | A run raised / failed | `reporting_service._dispatch_ops` (HOS-211 path) and other instrumented paths |
| `dead_man_timeout` | A run never fired within its window | `heartbeat_monitor` |
| `partial_hotel_failures` | Run completed but ≥ 1 per-hotel dispatch failed | `receipt_dispatcher`, `weekly_digest` |

---

## Detection-latency guarantees

- **Errors (AC1)**: per-hotel failures and fatal job errors alert at the end of
  the run (existing `dispatch_error` on fatal + new aggregated trip on partial).
- **Non-firing jobs (AC2)**: detected within at most `window + monitor_interval`
  (e.g. `dispatch_worker`: 15 min window + ≤ 15 min poll).

## Known limitation

If a job has **never** produced a heartbeat (e.g. brand-new deploy, before the
first scheduled run), the monitor skips it rather than alerting — this avoids
false alarms on cold start. Coverage begins after the first successful run.

"""Application-level configuration constants for Aetherix backend.

Values here are the system defaults; individual properties can override
avg_spend_per_cover and staff_hourly_rate via the properties table
(added in migration 20260323100000_add_roi_config_to_properties.sql).

[Source: story 3.3b AC 7]
"""
from __future__ import annotations

import os as _os

# ---------------------------------------------------------------------------
# ROI Calculator defaults  (Story 3.3b)
# ---------------------------------------------------------------------------

#: Default average revenue per cover (£) used when the property has no
#: per-property override set.
DEFAULT_AVG_SPEND_PER_COVER: float = 40.0

#: Default hourly cost per additional front-of-house staff member (£).
DEFAULT_STAFF_HOURLY_RATE: float = 14.0

#: Default captation rate — fraction of the excess demand that the property
#: is expected to capture when fully staffed.
DEFAULT_CAPTATION_RATE: float = 0.7

# ─── Twilio (SMS + WhatsApp) ─────────────────────────────────────────────────
TWILIO_ACCOUNT_SID: str = _os.getenv("TWILIO_ACCOUNT_SID", "")
TWILIO_AUTH_TOKEN: str = _os.getenv("TWILIO_AUTH_TOKEN", "")
TWILIO_FROM_NUMBER: str = _os.getenv("TWILIO_FROM_NUMBER", "")   # E.164 e.g. +15005550006
TWILIO_WHATSAPP_FROM: str = _os.getenv("TWILIO_WHATSAPP_FROM", "")  # whatsapp:+14155238886

# ─── SendGrid (Email) ────────────────────────────────────────────────────────
SENDGRID_API_KEY: str = _os.getenv("SENDGRID_API_KEY", "")
SENDGRID_FROM_EMAIL: str = _os.getenv("SENDGRID_FROM_EMAIL", "noreply@aetherix.io")

# ─── Story 4.3 (HOS-26): Twilio Inbound Webhook ──────────────────────────────
# Set to "true" in CI / test environments to bypass HMAC-SHA1 signature
# validation on POST /webhooks/twilio/inbound.
TWILIO_SKIP_SIGNATURE_VALIDATION: bool = (
    _os.getenv("TWILIO_SKIP_SIGNATURE_VALIDATION", "false").lower() == "true"
)

# Public base URL used to reconstruct the HMAC-signed URL behind a reverse proxy.
# Example: "https://api.aetherix.com"
# When set, overrides X-Forwarded-Proto / X-Forwarded-Host header inference.
TWILIO_WEBHOOK_BASE_URL: str = _os.getenv("TWILIO_WEBHOOK_BASE_URL", "")

# ─── Phase 2 Receipts (P2-3) ─────────────────────────────────────────────────
# Hour (0–23) at which the daily Receipt is dispatched, in RECEIPT_TIMEZONE.
RECEIPT_DISPATCH_HOUR: int = int(_os.getenv("RECEIPT_DISPATCH_HOUR", "18"))
# IANA timezone name for receipt dispatch scheduling (e.g. "Europe/Paris").
RECEIPT_TIMEZONE: str = _os.getenv("RECEIPT_TIMEZONE", "UTC")
# Base URL of the frontend — used to build deep links in WhatsApp messages.
FRONTEND_BASE_URL: str = _os.getenv("FRONTEND_BASE_URL", "http://localhost:3000")

# ─── Epic 12 G-1 — Heartbeat / dead-man's switch (HOS-248) ───────────────────
# All values are config-driven (env vars) — no redeploy needed to retune.
# Thresholds are documented in eval/HEARTBEAT_THRESHOLDS.md ("the contract").
# How often the dead-man's-switch monitor polls for stale scheduled jobs (min).
HEARTBEAT_MONITOR_INTERVAL_MIN: int = int(_os.getenv("HEARTBEAT_MONITOR_INTERVAL_MIN", "15"))
# Debounce: suppress repeat alerts for the same job within this cooldown (min).
HEARTBEAT_ALERT_COOLDOWN_MIN: int = int(_os.getenv("HEARTBEAT_ALERT_COOLDOWN_MIN", "60"))
# Max tolerated gap since the last *successful* run, per scheduled job (minutes).
# receipt_dispatcher fires daily → 26h (24h cadence + 2h grace).
HEARTBEAT_WINDOW_RECEIPT_DISPATCHER_MIN: int = int(
    _os.getenv("HEARTBEAT_WINDOW_RECEIPT_DISPATCHER_MIN", "1560")
)
# weekly_digest fires every Sunday → 8 days (7d cadence + 1d grace).
HEARTBEAT_WINDOW_WEEKLY_DIGEST_MIN: int = int(
    _os.getenv("HEARTBEAT_WINDOW_WEEKLY_DIGEST_MIN", "11520")
)
# dispatch_worker fires every 2 min → 15 min (cadence + ample grace for NFR2).
HEARTBEAT_WINDOW_DISPATCH_WORKER_MIN: int = int(
    _os.getenv("HEARTBEAT_WINDOW_DISPATCH_WORKER_MIN", "15")
)

# ─── Epic 12 G-3 — Feedback→training input bounds (HOS-250) ───────────────────
# Guards the manager-reported actual_covers before it is persisted / retrained.
# Documented in eval/FAILURE_THRESHOLDS.md. All config-driven (no redeploy).
# Policy on an implausible value: "reject" (default, hard pre-pilot guard — value
# is not ingested) or "flag" (ingested but tagged for downstream exclusion).
FEEDBACK_BOUNDS_POLICY: str = _os.getenv("FEEDBACK_BOUNDS_POLICY", "reject").lower()
# Minimum plausible covers; values below are implausible (typo / faulty sensor).
FEEDBACK_COVERS_MIN: float = float(_os.getenv("FEEDBACK_COVERS_MIN", "1"))
# Capacity ceiling = total_seats × (sum of daily turns) × this multiplier.
FEEDBACK_COVERS_CAPACITY_MULTIPLIER: float = float(
    _os.getenv("FEEDBACK_COVERS_CAPACITY_MULTIPLIER", "1.5")
)
# Fallback daily turns when a property's seats are known but its turn config is
# missing (NULL turns on an incompletely-onboarded / migrated profile). Keeps the
# capacity ceiling enforceable instead of silently bypassed on a falsy turns_sum.
FEEDBACK_COVERS_DEFAULT_TURNS: float = float(
    _os.getenv("FEEDBACK_COVERS_DEFAULT_TURNS", "3")
)
# Soft historical sanity: covers above (historical max × this) are flagged — never
# rejected (a genuine surge can exceed history while staying within capacity).
FEEDBACK_HISTORICAL_MULTIPLIER: float = float(
    _os.getenv("FEEDBACK_HISTORICAL_MULTIPLIER", "3.0")
)

# ─── Epic 12 G-2 — Agent error-rate / LLM-timeout alerting (HOS-249) ──────────
# Turns agent_action_log from a passive record into an alarm: a rolling-window
# monitor trips an ops alert (Linear, dispatch_anomaly) when the non-ok rate,
# tool-failure count or LLM-timeout count breaches a config-driven threshold.
# Documented in eval/FAILURE_THRESHOLDS.md. All config-driven (no redeploy).
# How often the rolling-window monitor polls (minutes).
ERROR_RATE_MONITOR_INTERVAL_MIN: int = int(_os.getenv("ERROR_RATE_MONITOR_INTERVAL_MIN", "15"))
# Width of the rolling window evaluated on each poll (minutes).
ERROR_RATE_WINDOW_MIN: int = int(_os.getenv("ERROR_RATE_WINDOW_MIN", "60"))
# Minimum number of rows in the window before the *rate* check is evaluated —
# avoids false alarms when volume is tiny (1 error out of 2 calls != a spike).
ERROR_RATE_MIN_SAMPLES: int = int(_os.getenv("ERROR_RATE_MIN_SAMPLES", "20"))
# AC1: non-ok fraction (status != "ok") over the window above this → alert.
ERROR_RATE_NONOK_THRESHOLD: float = float(_os.getenv("ERROR_RATE_NONOK_THRESHOLD", "0.20"))
# AC2: absolute count of tool failures (status="tool_error") over the window.
ERROR_RATE_TOOL_FAILURE_THRESHOLD: int = int(_os.getenv("ERROR_RATE_TOOL_FAILURE_THRESHOLD", "10"))
# AC2: absolute count of LLM timeouts over the window (error_code matches the
# substring below — providers tag transient timeouts there).
ERROR_RATE_LLM_TIMEOUT_THRESHOLD: int = int(_os.getenv("ERROR_RATE_LLM_TIMEOUT_THRESHOLD", "5"))
# Case-insensitive substring identifying an LLM/transient timeout error_code.
ERROR_RATE_TIMEOUT_ERROR_SUBSTR: str = _os.getenv("ERROR_RATE_TIMEOUT_ERROR_SUBSTR", "timeout")
# AC3: suppress repeat alerts for the same metric within this cooldown (minutes).
ERROR_RATE_ALERT_COOLDOWN_MIN: int = int(_os.getenv("ERROR_RATE_ALERT_COOLDOWN_MIN", "60"))

# ─── Epic 12 G-4 — Confidence-tiered forecast guardrail at dispatch (HOS-251) ─
# Generalizes the ADR-0005 cold-start auto-disable (degrade, not extinguish) to
# the dispatch path. NEVER blanks a recommendation (Décision #6 HITL-always):
#   • Tier 1 — confidence < WARN: the recommendation is dispatched anyway, tagged
#     with a confidence caveat (AgentAbstention flag carrier — HOS-206).
#   • Tier 2 — confidence < CATASTROPHE *or* live MAPE > MAPE_CATASTROPHE: fall
#     back to a simpler baseline (tagged as such), recommendation still delivered.
# Documented in eval/FAILURE_THRESHOLDS.md. All config-driven (no redeploy).
FORECAST_CONFIDENCE_WARN: float = float(_os.getenv("FORECAST_CONFIDENCE_WARN", "0.6"))
# Catastrophe floor — below the Prophet confidence floor (0.5) by default, so the
# catastrophic tier is driven mainly by the live-MAPE breach below, not by the
# discrete confidence score alone.
FORECAST_CONFIDENCE_CATASTROPHE: float = float(_os.getenv("FORECAST_CONFIDENCE_CATASTROPHE", "0.4"))
# Live rolling MAPE (%) above which the forecast is treated as catastrophic —
# "well beyond" the 25% cold-start auto-disable ceiling (ADR-0005 / HOS-251).
FORECAST_MAPE_CATASTROPHE: float = float(_os.getenv("FORECAST_MAPE_CATASTROPHE", "35"))
# Tier-2 baseline prior used when the caller supplies no historical baseline in
# context (`baseline_covers` / `recent_avg_covers`). 0 = disabled → degrade to the
# Prophet point estimate, still tagged baseline (never silent). A richer trailing
# baseline is a follow-up once live-MAPE telemetry (EVAL-3/5) is wired in.
FORECAST_BASELINE_DEFAULT_COVERS: float = float(_os.getenv("FORECAST_BASELINE_DEFAULT_COVERS", "0"))

# ─── Demo Mode ────────────────────────────────────────────────────────────────
# When true: enables SSE demo board (/demo/stream), emits pipeline stage events,
# and loads synthetic Prophet training data from demo_data/prophet_training.json.
# All demo_emit() calls are no-ops when false.
DEMO_MODE: bool = _os.getenv("DEMO_MODE", "false").lower() == "true"

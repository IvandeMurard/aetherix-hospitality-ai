# Runbook — LLM fallback canary (HOS-282)

**What it protects.** `get_llm_provider()` returns a `FallbackLLMProvider`: Claude
primary → Gemini fallback on transient (5xx / timeout / network) errors. The
fallback almost never runs in prod, so an expired/rotated Gemini key, a lapsed
quota, or an SDK-contract drift stays invisible until a real Claude outage — the
one moment it must work. The canary exercises Gemini directly to catch that rot
early.

**Signals.**
- **Boot health-check** (`main.py` lifespan → `FallbackLLMProvider.check_fallback_health()`):
  fires on every deploy when `GEMINI_API_KEY` is set. A failure logs
  `WARNING FallbackLLMProvider: fallback gemini/… health-check FAILED …`.
- **Integration canary** (`tests/providers/test_fallback_provider_integration.py`,
  `-m integration`): nightly + on-demand real Gemini call.

**When the canary fails — do this:**
1. **Confirm** it's the fallback, not the primary: the WARNING names `gemini/…`.
   Re-run locally: `GEMINI_API_KEY=… uv run --project backend pytest backend/tests/providers/test_fallback_provider_integration.py -m integration`.
2. **Triage the cause** from the logged exception:
   - `RuntimeError: GEMINI_API_KEY not set` → the secret is missing on Fly.
   - HTTP 401/403 / auth error → key revoked or rotated out from under us.
   - HTTP 429 / quota → billing/quota lapsed.
   - Empty response / safety block → model or SDK contract drift.
3. **Rotate / restore the key** per the provider secrets runbook (SEC-6, HOS-116):
   regenerate the Gemini key in Google AI Studio, then
   `fly secrets set GEMINI_API_KEY=… -a <app>` (triggers a redeploy; the boot
   canary re-verifies automatically).
4. **Verify** the next boot logs `health-check OK`, or re-run the integration test.

**Escalation.** A down fallback is not a customer-facing outage on its own
(Claude is still serving), so it is a **WARNING**, not a page. But do not let it
sit: an unaddressed fallure means no parachute during the next Claude incident.
Related alerting: HOS-249 (agent error-rate / LLM-timeout spikes).

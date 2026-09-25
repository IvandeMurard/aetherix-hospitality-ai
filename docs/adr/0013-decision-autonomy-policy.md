# ADR 0013 — Host-agent autonomy as versioned decision policy

> **Status**: **Proposed — for Ivan (PO) to decide. Nothing here is enabled.** · **Date**: 2026-09-24 · **Author**: Claude Code session (Architect)
> **Would amend**: CLAUDE.md Décision #6 ("Pas d'auto-actions, Phase MVP")
> **Builds on**: ADR-0007 §17 (decision provenance, reason contract, policy seam — Décision #39) · ADR-0007 §13 (three eval arms) · ADR-0009 (runtime guardrails) · ADR-0004 (orchestrator separation) · Décision #20 (Anima DPIA gate)
> **Implemented today**: only the seam, with the default policy (`backend/app/services/decision_policy.py`). No policy store, no autonomous path.

---

## 1. Context

Aetherix is meant to be sold white-label / headless, inside a hotel's existing
tools. The party that accepts or rejects a recommendation can then be the host
platform's agent, via MCP. Since ADR-0007 §17.4 every decision records who
decided (`decided_by`) and why (structured reason); a host agent deciding on
its own (`host_agent_autonomous`) is refused, because Décision #6 forbids
auto-actions.

Some clients will want the opposite for some tasks: the host agent accepting or
rejecting on its own, to spare the manager a manual validation. Ivan wants to
switch this per client and per scope quickly (day one, month 1, month 6) —
e.g. staffing: human validation; food-waste recommendations: autonomous —
without a code change.

Décision #6 was taken for the MVP on a market signal (63 % of managers want
human control). It is not wrong; it is a default. This ADR proposes how to make
it a **per-tenant, per-scope default that can be relaxed under conditions**,
without weakening it where it matters.

## 2. Decision (proposed)

Autonomy is a **client option**, off by default, expressed as **versioned
configuration** evaluated at **one seam**, gated by **reversibility, cost and
measured quality** of the scope.

### 2.1 Permission ladder (by reversibility and cost)

| Level | What a host agent may do alone | Candidate scopes | Eligible? |
|---|---|---|---|
| L0 — human validation | nothing; relays human decisions only | every scope (default) | always |
| L1 — autonomous within a bounded delta | accept/reject a recommendation whose effect is reversible the same day and capped (e.g. prep quantities within ± X % of the baseline, food-waste actions such as reducing a batch) | prep quantities, food-waste actions | only if §2.4 gates pass |
| L2 — autonomous with notification | as L1, larger delta, manager notified after the fact | none proposed today | not before L1 has run and been sampled |
| Never | anything irreversible or contractual: shifts published to staff, hiring/cancelling agency staff, supplier orders past their cut-off, anything touching guest data | staffing headcount changes, supplier commitments, Anima-derived actions | never, whatever the client asks |

Staffing recommendations (the only task class in the product today) stay L0:
a published shift is a commitment to a person.

### 2.2 Policy as versioned configuration

A policy row per **tenant × task class** (optionally × site/outlet):

| Field | Meaning |
|---|---|
| `tenant_id`, `task_class`, `site_id?` | scope |
| `mode` | `human_validation` \| `autonomous_within_bounds` |
| `bounds` | typed, per task class (e.g. `max_delta_pct`, `max_amount` in `CURRENCY`, allowed `reason_code`s) |
| `caps` | max autonomous decisions per day / per week; max cumulative delta |
| `sample_rate` | share of autonomous decisions sent to a human for review (§2.6) |
| `version` | monotonic, immutable once effective |
| `effective_from` | never retroactive; `effective_to` set when superseded |
| `approved_by` | the client-side approver (named person) **and** the Aetherix-side approver |
| `requested_by`, `request_ref` | who asked, and where (contract annex, ticket) |
| `eval_evidence` | the arm-A run id that made the scope eligible (§2.4) |

Rows are append-only. Changing a policy = inserting version *n+1* with a new
`effective_from`; version *n* gets `effective_to`. An audit log records every
insert, approval and kill switch (who, when, from which surface).

Default when no row exists: **human validation everywhere** (what
`decision_policy.default_policy` returns today).

### 2.3 One seam

`decision_policy.authorize_decision(tenant, decided_by, task_class, at)` is
already the only place both write paths (WhatsApp, MCP) ask whether a decision
may be recorded. The policy store would be read there and nowhere else. The
policy version in force is stored on every decision
(`staffing_recommendations.decision_policy_version`, already written).

### 2.4 Eligibility of a scope: the eval gate decides, the client opts in

A scope may carry `autonomous_within_bounds` only if:

1. **Arm A** — the task class has its own golden set and thresholds in
   `eval/FAILURE_THRESHOLDS.md`, and the latest real-model run passes them
   (Décision #35 D3: *qualify automatically, promote manually*). No
   per-scope thresholds → not eligible. A parser-quality number that was never
   measured (the situation on 24/09/2026) makes nothing eligible.
2. **Arm C** — the scope has at least N human-decided recommendations with
   measured outcomes, and the human override rate on that scope is below a
   threshold fixed before looking at the data (HOS-316 protocol).
3. **Arm B** — the runtime guardrails for the scope exist (ADR-0009 pattern:
   bounds, caps, circuit-breaker) and trip with typed reasons.
4. The client asks for it, in writing, with a named approver.
5. **Point of no return (input, added 25/09/2026, ADR-0007 §18.1).** Each task
   class has a commit point relative to service start and a list of corrective
   actions still possible before it (`backend/app/services/task_classes.py`,
   `autonomy_eligibility_facts`). A scope is a **better** candidate when it has
   a correction window (a commit point before service, with corrective actions
   before it) **or** a bounded downside (the worst case of a wrong decision has
   a known ceiling). This is an input to the ranking of candidates, not a gate:
   it never makes a scope eligible on its own, and conditions 1–4 still apply.
   Commit offsets are catalog **defaults (assumptions)** until the hotel sets
   its own. Facts today: `staffing.add` (commit = extra shift confirmed,
   default 24 h before service) and `staffing.reduce` (commit = staff notified,
   default 72 h) have a correction window and a bounded downside, but are not
   reversible after commit — consistent with §2.1 keeping staffing at L0;
   `food_prep.batch` (commit = prep starts, default 4 h) has both and is the
   natural L1 candidate, but the product does not recommend it (food-waste
   tracking is an open decision).

The gate makes a scope *eligible*; enabling it stays a human act on both sides.

### 2.5 Approval, change, in-flight recommendations

- **Approval of a policy change:** client approver + Aetherix approver, both
  recorded; a relaxation (towards autonomy) needs both, a tightening (towards
  human validation) needs either.
- **Recommendations in flight** when a policy changes: evaluated under the
  policy **in force when the decision arrives**, never when the recommendation
  was issued; but a relaxation never applies to recommendations issued before
  its `effective_from` (conservative both ways). Pending confirmations are
  unaffected.
- **Kill switch per tenant** (and a global one): one call sets every scope of
  the tenant back to human validation immediately, logged; no approval needed
  to tighten.

### 2.6 Autonomous decisions: flagged, excluded, sampled

- Recorded with `decided_by = host_agent_autonomous`,
  `decision_source = host_agent`, the policy version, the structured reason
  (`reason_source = agent_inferred`, already enforced).
- **Excluded from every human-trust metric** (acceptance rate, override rate,
  response time) — already the rule in `decision_recap` (ADR-0007 §17.6) — and
  never ground truth for arm C or training (ADR-0007 §17.5).
- **Periodic human sampling:** `sample_rate` of autonomous decisions (and all of
  them for the first K after enablement) are shown to the manager in the recap
  for a yes/no audit; a disagreement rate above a pre-set threshold trips the
  kill switch for that scope.
- **Caps:** exceeding a cap falls back to human validation for the rest of the
  period, with a typed guardrail trip (NFR2).

### 2.7 Metrics and baselines across a policy change

Every metric is split by `decided_by` and by `decision_policy_version`. A
baseline is never compared across versions without saying so; a change of
policy starts a new baseline period. The recap shows autonomous decisions on a
separate line (already implemented: "Décisions d'agent autonome : n (exclues
des taux de confiance)").

## 3. Serving other agents of the architecture (design note, 3e)

Typed records Aetherix could expose **read-only** via MCP to other nodes
(Orchestrateur, Tacet, Anima, Peritia), under the same token-bound tenant
isolation as today:

| Record | Content | Could serve | Boundary |
|---|---|---|---|
| Decision | recommendation id, task class, decision, `decided_by`, `decision_source`, policy version, timestamps | Orchestrateur (who decides what, where autonomy is on) | tenant-scoped; no free text by default |
| Reason | `reason_code`, `reason_source`, evidence sources (not details) | Orchestrateur, Peritia (house know-how: "we never go below 3 servers on Friday" is a `decision_rule` reason) | `reason_detail` is free text that can name staff: excluded unless a separate purpose and DSAR scope are defined |
| Outcome | predicted vs actual covers, source (`manager_feedback` / POS / PMS) | Tacet (does environmental risk explain error?), Orchestrateur | aggregated per service, no person |

Not exposed, ever: anything that would let a guest be singled out. **Anima is
DPIA-gated (Décision #20): no guest data crosses in either direction** until
its 13 blocking measures are met; F&B decision records are operational data
about the hotel, not about guests, and must stay so. Tacet and the
Orchestrateur receive signals under the Signal Contract (ADR-0012,
`fnb.*` namespace); a decision record is not a `SignalComposite` and carries no
actionable field for another node (ADR-0004 D5). No implementation.

## 4. Consequences

- **If accepted:** Décision #6 is amended from "no auto-actions" to "no
  auto-actions except scopes that passed §2.4 and were enabled by both sides,
  within bounds, capped, sampled, killable". Build order: policy store + audit
  log + kill switch → per-scope golden sets and thresholds → one L1 scope in
  shadow mode (autonomous decision computed, not applied, compared to the human
  one) → only then enablement for a client.
- **If rejected:** nothing changes; the seam stays with its single default and
  the refusal of `host_agent_autonomous` stays.
- **Public claim:** until built and gated, autonomy is **Design** on every
  surface (Décision #33). "Human-in-the-loop" remains the true statement.

## 5. Open questions for the PO

1. Accept the ladder of §2.1, in particular "staffing headcount = never"?
2. Two-sided approval for relaxations — acceptable commercially?
3. Values of N, thresholds and `sample_rate` (to be fixed before any data,
   HOS-316 protocol).
4. Is the task class "prep quantities / food-waste action" worth building at
   all before a design partner asks for it? (Food-waste tracking is itself an
   open decision.)

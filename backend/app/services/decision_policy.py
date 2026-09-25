"""Decision policy — the single seam where a recommendation's decision path is
chosen (ADR-0013, status: proposed; Décision #6).

Today there is exactly one policy: **human validation everywhere**
(``DEFAULT_POLICY``). A host agent may relay a human's decision
(``human_via_host``); a decision the host agent takes on its own
(``host_agent_autonomous``) is refused with a typed error and nothing is
written. No autonomous path is enabled.

This module exists so that, if Ivan accepts ADR-0013, autonomy per tenant ×
task class becomes versioned configuration evaluated here — not code spread
across the WhatsApp route, the MCP tool and the dispatcher. Every recorded
decision stores ``policy.version`` (``staffing_recommendations
.decision_policy_version``), so metrics and baselines can be split before and
after any future policy change.

Every write path that records a decision calls ``authorize_decision`` first:
``InboundDecisionService._record_or_explain`` (WhatsApp) and
``mcp_server.tool_submit_feedback_to_memory`` (MCP).
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import Optional

from app.services.decision_provenance import DecidedBy


class TaskClass(str, Enum):
    """Kinds of recommendation a policy can be scoped to. Only ``staffing``
    exists in the product today; ADR-0013 names the candidates (prep
    quantities, food-waste actions) without implementing them."""

    staffing = "staffing"


class DecisionMode(str, Enum):
    human_validation = "human_validation"
    # Designed in ADR-0013, not implemented: no code path accepts it.
    autonomous_within_bounds = "autonomous_within_bounds"


@dataclass(frozen=True)
class DecisionPolicy:
    tenant_id: Optional[str]          # None = the default for every tenant
    task_class: TaskClass
    mode: DecisionMode
    version: str
    effective_from: Optional[datetime]
    approved_by: str


DEFAULT_POLICY_VERSION = "default-human-validation-v1"


def default_policy(task_class: TaskClass = TaskClass.staffing) -> DecisionPolicy:
    return DecisionPolicy(
        tenant_id=None,
        task_class=task_class,
        mode=DecisionMode.human_validation,
        version=DEFAULT_POLICY_VERSION,
        effective_from=None,
        approved_by="Décision #6",
    )


def resolve_policy(
    tenant_id: str, task_class: TaskClass = TaskClass.staffing, at: Optional[datetime] = None
) -> DecisionPolicy:
    """The policy in force for ``tenant_id`` × ``task_class`` at ``at``.

    No policy store exists: every tenant gets the default. ADR-0013 §3 designs
    the store (versioned rows, effective date, approver, audit trail); until it
    is accepted and built, this function is the only place that would read it.
    """
    return default_policy(task_class)


class DecisionNotPermitted(Exception):
    """Typed refusal (→ MCP 403 ``autonomy_not_permitted``)."""

    def __init__(self, code: str, detail: str, policy: DecisionPolicy):
        self.code = code
        self.detail = detail
        self.policy = policy
        super().__init__(f"{code}: {detail}")


def authorize_decision(
    tenant_id: str,
    decided_by: str,
    task_class: TaskClass = TaskClass.staffing,
    at: Optional[datetime] = None,
) -> DecisionPolicy:
    """Return the policy under which this decision may be recorded, or raise
    ``DecisionNotPermitted``.

    * human deciders → allowed under every policy;
    * ``host_agent_autonomous`` → allowed only under an autonomous policy for
      that scope, which cannot exist today → refused;
    * ``timeout`` → reserved, refused (no default action on expiry).
    """
    policy = resolve_policy(tenant_id, task_class, at)
    if decided_by in (DecidedBy.human_whatsapp.value, DecidedBy.human_via_host.value):
        return policy
    if decided_by == DecidedBy.host_agent_autonomous.value:
        if policy.mode == DecisionMode.autonomous_within_bounds:  # pragma: no cover — unreachable today
            return policy
        raise DecisionNotPermitted(
            "autonomy_not_permitted",
            f"policy {policy.version} requires human validation for "
            f"{task_class.value}; an autonomous host-agent decision is not recorded "
            "(Décision #6, ADR-0013 proposed)",
            policy,
        )
    raise DecisionNotPermitted(
        "decider_not_permitted", f"decided_by={decided_by!r} cannot record a decision", policy
    )

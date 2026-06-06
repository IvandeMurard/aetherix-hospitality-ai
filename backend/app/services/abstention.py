"""AgentAbstention sentinel — the agent's "I don't know" contract.

EVAL-2 (HOS-206), ADR-0007 §D6.a. A model/service that cannot responsibly
answer returns an ``AgentAbstention`` instead of a result. Callers distinguish
it with ``isinstance(...)`` or its falsy ``__bool__`` (``if result:``); there is
**no automatic cascade** (D6.b) — each layer decides how to degrade.

Manager-facing copy is NEVER the raw ``reason`` code — it is resolved through
``app.i18n.abstention_messages`` (PM caveat 04/06, BLOCKING).
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal

AbstentionReason = Literal[
    "cold_start_no_cohort",           # forecast — new property, no cohort match
    "cold_start_meta_learner_drift",  # forecast — meta-learner auto-disabled (D5)
    "confidence_below_threshold",     # recommendation — confidence < 0.5
    "parser_low_confidence",          # parser — intent confidence < 0.6 (Décision #15)
    "data_quality_alert",             # any — PMS sync stale / weather missing
    "drift_detected_high",            # any — distribution shift FAIL (D5)
    "ood_unsupported_input",          # parser — unsupported language / anomalous payload
]

AbstentionLayer = Literal["forecast", "recommendation", "receipt", "parser"]

# Runtime-iterable tuple of the 7 reasons (a typing.Literal can't be iterated).
# Single source of truth for the i18n mapping + its blocking coverage test.
ABSTENTION_REASONS: tuple[str, ...] = (
    "cold_start_no_cohort",
    "cold_start_meta_learner_drift",
    "confidence_below_threshold",
    "parser_low_confidence",
    "data_quality_alert",
    "drift_detected_high",
    "ood_unsupported_input",
)


@dataclass(frozen=True)
class AgentAbstention:
    """Sentinel returned in place of a result when the agent abstains.

    ``context`` is serialized to ``agent_action_log.abstention_context`` (JSONB).
    ``human_message`` is the localized manager-facing string (resolved upstream
    via the i18n mapping) — never the raw ``reason`` code.
    """

    reason: AbstentionReason
    layer: AbstentionLayer
    context: dict = field(default_factory=dict)
    human_message: str = ""

    def __bool__(self) -> bool:
        # `if result:` treats an abstention as "no usable result".
        return False

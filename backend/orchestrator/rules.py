"""Hotel business rules for the orchestrator (ADR-0004 · HOS-184).

Pure functions — no LLM, no DB, no network. These rules encode per-hotel
operational policies (e.g. "never lower price by more than X%", "VIP guests
get silent upgrades when noise > Y dB"). The orchestrator queries these
before deciding which MCP tool to call and how.

Phase 3 PR-A: skeleton. Phase 3 PR-B will add concrete rules as the
AetherixEngine logic is migrated and the first business rules surface.
Phase 4: per-hotel rule packs, loaded via config.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional


@dataclass(frozen=True)
class RuleSet:
    """Per-hotel policy parameters.

    Phase 4: populated from a hotel config table; Phase 3: hardcoded defaults.
    """

    # Confidence threshold below which the orchestrator should request more
    # memory context before producing a recommendation.
    min_forecast_confidence: float = 0.6

    # Top-similarity threshold below which the orchestrator should expand
    # the memory recall window (k_memory) before forecasting.
    min_memory_similarity: float = 0.7

    # Max staffing delta (vs baseline) the orchestrator may recommend without
    # explicit manager confirmation.
    max_staffing_delta_pct: float = 0.25


DEFAULT_RULESET = RuleSet()


def select_recall_k(top_similarity: Optional[float], rules: RuleSet = DEFAULT_RULESET) -> int:
    """Decide k_memory for the next recall call based on similarity score.

    If the first recall returned weak signals (similarity below threshold),
    widen the window to gather more historical patterns before forecasting.
    """
    if top_similarity is None or top_similarity < rules.min_memory_similarity:
        return 10
    return 5

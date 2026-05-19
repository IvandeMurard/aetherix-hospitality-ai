"""Aetherix Orchestrator — Phase 3 proto-orchestrator (ADR-0004 · HOS-184).

Architecture rules enforced by CI (tests/orchestrator/test_agent.py):
  - Zero imports from ``app.*`` — all services are constructor-injected.
  - ``app/services/aetherix_engine.py`` delegates here; reverse is forbidden.
  - Phase 4: this module moves to its own repo and calls services exclusively
    via MCP tool calls (no Python imports at all).
"""
from __future__ import annotations

import logging
from datetime import date
from typing import Any, Callable, Optional

logger = logging.getLogger(__name__)


class OrchestratorAgent:
    """Proto-orchestrator: coordinates F&B execution-node services.

    All dependencies are injected so this module stays free of ``app.*``
    imports (ADR-0004 isolation boundary). The agentic routing / retry /
    feedback-loop logic will be built here in Phase 3; for now the happy
    path is a straight pipeline identical to the old AetherixEngine.
    """

    def __init__(
        self,
        forecaster: Any,
        rag: Any,
        reasoner: Any,
        staffer: Any,
        memory: Any,
        profile_loader: Callable[[str], Any],
        constitution_builder: Optional[Callable[[Any, dict[str, Any]], Optional[str]]] = None,
    ) -> None:
        self._forecaster = forecaster
        self._rag = rag
        self._reasoner = reasoner
        self._staffer = staffer
        self._memory = memory
        self._profile_loader = profile_loader
        self._constitution_builder = constitution_builder

    async def get_forecast(
        self,
        tenant_id: str,
        target_date: date,
        service_type: str,
        context: dict[str, Any],
    ) -> dict[str, Any]:
        """Hybrid F&B orchestration: Prophet + RAG + Memory + Reasoning.

        Returns a dict with keys: tenant_id, date, service_type, prediction,
        reasoning, reasoning_detail, staffing_recommendation, historical_patterns.
        """
        # 1. Prediction (Prophet)
        forecast = await self._forecaster.predict(
            target_date, features=context.get("regressors")
        )
        predicted_covers = forecast.predicted
        confidence = forecast.confidence
        is_mock = forecast.is_mock

        # 2. RAG (Historical Patterns)
        context_query = self._rag.build_context_string(target_date, service_type, context)
        patterns = await self._rag.find_similar_patterns(context_query, service_type)

        # 3. Memory Retrieval
        memory_context = await self._memory.get_relevant_context(tenant_id, context_query)

        # 4. Agent Constitution — build system prompt if profile available
        system_prompt: Optional[str] = None
        try:
            profile = await self._profile_loader(tenant_id)
            if profile is not None and self._constitution_builder is not None:
                similar_text = (
                    "\n".join(
                        f"- {p['payload'].get('pattern_text', '')} "
                        f"({p['payload'].get('outcome_description', '')})"
                        for p in patterns[:3]
                    )
                    if patterns
                    else ""
                )
                system_prompt = self._constitution_builder(
                    profile,
                    {
                        "date": target_date.isoformat(),
                        "covers": predicted_covers,
                        "confidence": int(confidence * 100),
                        "similar_nights": similar_text,
                    },
                )
        except Exception as exc:
            logger.warning("constitution/profile failed (non-fatal): %s", exc)

        # 5. Reasoning (Claude)
        reasoning = await self._reasoner.generate_explanation(
            predicted_covers,
            confidence,
            target_date,
            service_type,
            context,
            patterns,
            memory_context,
            is_mock=is_mock,
            system_prompt=system_prompt,
        )

        # 6. Staffing
        staffing = await self._staffer.calculate_recommendation(predicted_covers)

        return {
            "tenant_id": tenant_id,
            "date": target_date.isoformat(),
            "service_type": service_type,
            "prediction": {
                "covers": predicted_covers,
                "confidence": confidence,
                "is_mock": is_mock,
                "range_min": forecast.lower,
                "range_max": forecast.upper,
            },
            "reasoning": reasoning["summary"],
            "reasoning_detail": reasoning,
            "staffing_recommendation": staffing,
            "historical_patterns": patterns,
        }

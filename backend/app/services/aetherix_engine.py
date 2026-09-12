import logging
from datetime import date
from pathlib import Path
from typing import Any, Dict, Optional

from sqlalchemy.future import select

from app.db.models import RecommendationCache, RestaurantProfile
from app.db.session import AsyncSessionLocal
from app.providers.factory import get_embedding_provider
from app.services.agent_constitution import AgentConstitutionService
from app.services.memory_service import MemoryService
from app.services.prediction_engine import PredictionEngine
from app.services.rag_service import RAGService
from app.services.reasoning_service import ReasoningService
from app.services.staffing_service import StaffingService
from orchestrator.agent import OrchestratorAgent

logger = logging.getLogger(__name__)

# Persisted Prophet model (written by POST /api/v1/predictions/train). Kept in sync
# with predictions.py::_MODEL_PATH — both resolve to backend/data/demo/prophet_model.json.
_DEMO_MODEL_PATH = str(Path(__file__).resolve().parents[2] / "data" / "demo" / "prophet_model.json")


class AetherixEngine:
    """F&B execution node — delegates orchestration to OrchestratorAgent (ADR-0004).

    Responsibilities kept here (app/ concerns):
      - Provider / service instantiation (imports from app.*)
      - RecommendationCache persistence
    """

    def __init__(self):
        forecaster = PredictionEngine()
        # Restart-resilience (Décision #13): reload the persisted Prophet model if
        # present so is_mock=False survives process restarts. Non-fatal on failure.
        try:
            forecaster.load_model(_DEMO_MODEL_PATH)
            if forecaster.is_trained:
                logger.info("Prophet model reloaded from %s", _DEMO_MODEL_PATH)
        except Exception:
            logger.warning("Prophet model reload skipped (non-fatal)", exc_info=True)
        rag = RAGService()
        reasoner = ReasoningService()
        staffer = StaffingService()
        memory = MemoryService()
        # Same factory MemoryService and the MCP surface use, so recall scores
        # are comparable across all three rather than merely similar.
        self._embedding = get_embedding_provider()
        constitution_svc = AgentConstitutionService()

        # Exposed so POST /api/v1/predictions/train can (re)train the live singleton
        # (the OrchestratorAgent below shares this exact instance by reference).
        self.forecaster = forecaster
        # Kept for the Epic 12 G-4 dispatch guardrail: a Tier-2 fallback recomputes
        # staffing on the baseline covers (same instance the orchestrator uses).
        self._staffer = staffer

        self._agent = OrchestratorAgent(
            forecaster=forecaster,
            rag=rag,
            reasoner=reasoner,
            staffer=staffer,
            memory=memory,
            profile_loader=self._load_profile,
            constitution_builder=constitution_svc.build_system_prompt,
            memory_recall=self._recall_memory,
        )

    async def _recall_memory(self, tenant_id: str, query: str, k: int) -> list:
        """Structured recall adapter for the orchestrator's agentic loop (HOS-189).

        The orchestrator needs per-hit similarity to decide whether to widen its
        recall, and ``MemoryService.get_relevant_context`` returns flat text. This
        binds the same path ``mcp_server.tool_recall_memory`` uses — embed, then
        ``MemoryRecallService.recall`` — so both surfaces score memory identically.

        Lives here rather than in ``orchestrator/`` because it needs a session and
        an embedding provider, and ADR-0004 forbids ``app.*`` imports over there.
        Returns ``list[MemoryHit]``; the orchestrator reads only ``.similarity``
        and ``.reflection`` and never imports the type.
        """
        from app.services.memory_recall_service import MemoryRecallService

        query_vec = await self._embedding.embed(query)
        async with AsyncSessionLocal() as db:
            return await MemoryRecallService(db).recall(tenant_id, query_vec, k=k)

    async def _load_profile(self, tenant_id: str) -> Optional[RestaurantProfile]:
        async with AsyncSessionLocal() as db:
            result = await db.execute(
                select(RestaurantProfile).where(RestaurantProfile.tenant_id == tenant_id)
            )
            return result.scalars().first()

    async def get_forecast(self, tenant_id: str, target_date: date, service_type: str, context: Dict[str, Any]) -> Dict[str, Any]:
        """Delegate to OrchestratorAgent, apply the runtime guardrail, then cache."""
        result = await self._agent.get_forecast(tenant_id, target_date, service_type, context)
        result = await self._apply_forecast_guardrail(tenant_id, result, context)
        await self._cache_recommendation(tenant_id, target_date, result)
        return result

    async def _apply_forecast_guardrail(
        self, tenant_id: str, result: Dict[str, Any], context: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Epic 12 G-4 (HOS-251) — confidence-tiered guardrail at dispatch.

        Never blanks the recommendation: Tier 1 attaches a confidence caveat,
        Tier 2 swaps in a baseline (and recomputes staffing on it). Non-fatal —
        a guardrail failure must not drop an otherwise-valid recommendation.
        """
        from app.services import forecast_guardrail as fg

        try:
            prediction = result.get("prediction") or {}
            covers = prediction.get("covers")
            confidence = prediction.get("confidence")
            if covers is None or confidence is None:
                return result

            verdict = await fg.apply(
                tenant_id,
                covers,
                confidence,
                context=context,
                live_mape=(context or {}).get("live_mape"),
            )
            if verdict.is_nominal:
                return result

            # Tier 2: deliver the baseline, not the untrustworthy Prophet point —
            # recompute staffing on the baseline covers so the headcount matches.
            if verdict.baseline_used:
                prediction["covers"] = verdict.effective_covers
                prediction["baseline_used"] = True
                result["staffing_recommendation"] = await self._staffer.calculate_recommendation(
                    verdict.effective_covers
                )

            # Surface the manager-facing caveat alongside the delivered number.
            result["forecast_guardrail"] = {
                "tier": verdict.tier,
                "reason": verdict.reason,
                "baseline_used": verdict.baseline_used,
                # AgentAbstention is intentionally falsy (__bool__ → False), so test
                # `is not None` rather than truthiness here.
                "human_message": (
                    verdict.abstention.human_message if verdict.abstention is not None else None
                ),
            }
        except Exception:
            logger.warning("forecast guardrail skipped (non-fatal)", exc_info=True)
        return result

    async def _cache_recommendation(self, tenant_id: str, target_date: date, data: Dict) -> None:
        async with AsyncSessionLocal() as db:
            # Check if exists
            stmt = select(RecommendationCache).where(
                RecommendationCache.tenant_id == tenant_id,
                RecommendationCache.target_date == target_date
            )
            result = await db.execute(stmt)
            existing = result.scalars().first()
            
            if existing:
                existing.prediction_data = data["prediction"]
                existing.reasoning_summary = data["reasoning"]
                existing.staffing_recommendation = data["staffing_recommendation"]
            else:
                new_cache = RecommendationCache(
                    tenant_id=tenant_id,
                    target_date=target_date,
                    prediction_data=data["prediction"],
                    reasoning_summary=data["reasoning"],
                    staffing_recommendation=data["staffing_recommendation"]
                )
                db.add(new_cache)
            
            await db.commit()

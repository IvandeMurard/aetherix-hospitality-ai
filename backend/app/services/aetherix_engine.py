import logging
from datetime import date
from pathlib import Path
from typing import Any, Dict, Optional

from sqlalchemy.future import select

from app.db.models import RecommendationCache, RestaurantProfile
from app.db.session import AsyncSessionLocal
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
        constitution_svc = AgentConstitutionService()

        # Exposed so POST /api/v1/predictions/train can (re)train the live singleton
        # (the OrchestratorAgent below shares this exact instance by reference).
        self.forecaster = forecaster

        self._agent = OrchestratorAgent(
            forecaster=forecaster,
            rag=rag,
            reasoner=reasoner,
            staffer=staffer,
            memory=memory,
            profile_loader=self._load_profile,
            constitution_builder=constitution_svc.build_system_prompt,
        )

    async def _load_profile(self, tenant_id: str) -> Optional[RestaurantProfile]:
        async with AsyncSessionLocal() as db:
            result = await db.execute(
                select(RestaurantProfile).where(RestaurantProfile.tenant_id == tenant_id)
            )
            return result.scalars().first()

    async def get_forecast(self, tenant_id: str, target_date: date, service_type: str, context: Dict[str, Any]) -> Dict[str, Any]:
        """Delegate to OrchestratorAgent, then cache result."""
        result = await self._agent.get_forecast(tenant_id, target_date, service_type, context)
        await self._cache_recommendation(tenant_id, target_date, result)
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

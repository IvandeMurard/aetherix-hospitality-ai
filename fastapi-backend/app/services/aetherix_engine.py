from datetime import date, datetime
from typing import Dict, Any, List, Optional
from app.services.prediction_engine import PredictionEngine
from app.services.rag_service import RAGService
from app.services.reasoning_service import ReasoningService
from app.services.staffing_service import StaffingService
from app.services.memory_service import MemoryService
from app.db.session import AsyncSessionLocal
from app.db.models import RecommendationCache
from sqlalchemy.future import select

class AetherixEngine:
    """
    The Hybrid Hub (Phase 2).
    Orchestrates Prophet (Accuracy) + RAG (Explainability).
    """
    
    def __init__(self):
        self.forecaster = PredictionEngine()
        self.rag = RAGService()
        self.reasoner = ReasoningService()
        self.staffer = StaffingService()
        self.memory = MemoryService()

    async def get_forecast(self, tenant_id: str, target_date: date, service_type: str, context: Dict[str, Any]) -> Dict[str, Any]:
        """Hybrid orchestration logic."""
        # 1. Prediction (Prophet)
        forecast = self.forecaster.predict(target_date, features=context.get('regressors'))
        predicted_covers = forecast.predicted
        confidence = forecast.confidence
        
        # 2. RAG (Historical Patterns)
        context_query = self.rag.build_context_string(target_date, service_type, context)
        patterns = await self.rag.find_similar_patterns(context_query, service_type)
        
        # 3. Memory Retrieval (Interaction History)
        memory_context = await self.memory.get_relevant_context(tenant_id, context_query)
        
        # 4. Reasoning (Claude)
        reasoning = await self.reasoner.generate_explanation(
            predicted_covers, confidence, target_date, service_type, context, patterns, memory_context
        )
        
        # 5. Staffing Recommendation
        staffing = self.staffer.calculate_recommendation(predicted_covers)
        
        result = {
            "tenant_id": tenant_id,
            "date": target_date.isoformat(),
            "service_type": service_type,
            "prediction": {
                "covers": predicted_covers,
                "confidence": confidence
            },
            "reasoning": reasoning["summary"],
            "staffing_recommendation": staffing,
            "historical_patterns": patterns
        }
        
        # 6. Cache for Dashboard/Push
        await self._cache_recommendation(tenant_id, target_date, result)
        
        return result

    async def _cache_recommendation(self, tenant_id: str, target_date: date, data: Dict):
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

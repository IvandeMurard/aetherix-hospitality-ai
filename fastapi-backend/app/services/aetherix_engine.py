from datetime import date, datetime
from typing import Dict, Any
from app.services.prediction_engine import PredictionEngine
from app.services.rag_service import RAGService
from app.services.reasoning_service import ReasoningService
from app.services.staffing_service import StaffingService
from app.services.memory_service import MemoryService
from app.db.session import AsyncSessionLocal
from app.db.models import RecommendationCache

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

    async def get_forecast(self, property_id: str, target_date: date, service_type: str, context: Dict[str, Any]) -> Dict[str, Any]:
        """
        Executes the hybrid prediction flow.
        1. Numerical forecast (Prophet)
        2. Pattern retrieval (RAG)
        3. Logic explanation (Claude)
        4. Staffing calculation
        """
        # 1. Numerical "Source of Truth"
        if not self.forecaster.is_trained:
            # Fallback to a simpler logic if no historical model loaded
            predicted_covers = 145 # Pilot mock
            confidence = 0.85
            range_min, range_max = 135, 155
        else:
            result = self.forecaster.predict(target_date, features=context.get('features'))
            predicted_covers = result.predicted
            confidence = result.confidence
            range_min, range_max = result.lower, result.upper

        # 2. Pattern Retrieval (RAG & Cognitive Memory)
        query_text = self.rag.build_context_string(target_date, service_type, context)
        similar_patterns = await self.rag.find_similar_patterns(query_text, service_type)
        cognitive_context = await self.memory.get_relevant_context(property_id, query_text)

        # 3. AI Explainability (Claude)
        reasoning = await self.reasoner.generate_explanation(
            predicted_covers=predicted_covers,
            confidence=confidence,
            target_date=target_date,
            service_type=service_type,
            context=context,
            similar_patterns=similar_patterns,
            cognitive_context=cognitive_context
        )

        # 4. Actionable Staffing
        staffing = self.staffer.calculate_recommendation(predicted_covers)

        # 5. Cache for Action (Phase 3 2-Way Sync)
        async with AsyncSessionLocal() as session:
            cache_entry = RecommendationCache(
                tenant_id=property_id,
                target_date=target_date,
                prediction_data={
                    "covers": predicted_covers,
                    "confidence": confidence,
                    "interval": [range_min, range_max]
                },
                reasoning_summary=reasoning.get("summary", ""),
                staffing_recommendation=staffing
            )
            session.add(cache_entry)
            await session.commit()

        # Also store in MemoryService for cognitive recall
        await self.memory.cache_recommendation(property_id, {
            "date": target_date.isoformat(),
            "staffing": staffing
        })

        return {
            "prediction": {
                "covers": predicted_covers,
                "confidence": confidence,
                "interval": [range_min, range_max]
            },
            "reasoning": reasoning,
            "staffing": staffing,
            "metadata": {
                "property_id": property_id,
                "date": target_date.isoformat(),
                "service_type": service_type
            }
        }

    async def push_staffing(self, property_id: str) -> Dict[str, Any]:
        """
        Orchestrates the 2-Way Sync by pushing the latest cached recommendation to the PMS.
        """
        latest = await self.memory.get_latest_recommendation(property_id)
        if not latest:
            return {"success": False, "message": "No recent recommendation found to push."}
        
        target_date = date.fromisoformat(latest["date"])
        staffing_deltas = latest["staffing"]["deltas"]
        
        # In a real pilot, we'd use the appropriate adapter (Apaleo)
        from app.services.apaleo_adapter import ApaleoPMSAdapter
        adapter = ApaleoPMSAdapter() 
        
        success = await adapter.update_staffing_in_pms(property_id, target_date, staffing_deltas)
        
        if success:
            return {"success": True, "message": f"Successfully pushed staffing to Apaleo for {target_date}."}
        else:
            return {"success": False, "message": "Failed to push staffing to Apaleo. Check logs."}

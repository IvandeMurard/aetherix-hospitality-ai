import sys
from unittest.mock import MagicMock

# Mock Prophet before importing app services
mock_prophet = MagicMock()
sys.modules["prophet"] = mock_prophet
sys.modules["prophet.serialize"] = MagicMock()

import asyncio
import unittest
from unittest.mock import patch
from datetime import date, timedelta
from app.services.memory_service import MemoryService
from app.services.reporting_service import ReportingService
from app.services.staffing_service import StaffingService
from app.services.aetherix_engine import AetherixEngine

class TestPhase3Suite(unittest.IsolatedAsyncioTestCase):
    
    async def asyncSetUp(self):
        self.engine = AetherixEngine()
        self.reporter = ReportingService()
        self.staffer = StaffingService()

    @patch('httpx.AsyncClient.post')
    @patch('httpx.AsyncClient.get')
    async def test_cognitive_memory_loop(self, mock_get, mock_post):
        """Verify the agent stores and retrieves feedback correctly."""
        # 1. Mock Backboard storage
        mock_post.return_value = MagicMock(status_code=201)
        
        memory = MemoryService()
        memory.api_key = "test_key"
        await memory.learn_from_feedback("pilot_hotel", "test_id", "Forecast too high")
        
        self.assertTrue(mock_post.called)
        
        # 2. Mock context retrieval
        mock_get.return_value = MagicMock(
            status_code=200, 
            json=lambda: {"data": [{"content": "Previous rejection: Forecast too high"}]}
        )
        
        context = await memory.get_relevant_context("pilot_hotel", "forecast")
        self.assertIn("too high", context)

    async def test_reporting_accuracy(self):
        """Verify MAPE and Savings calculations."""
        week_start = date.today()
        metrics = await self.reporter.generate_weekly_metrics("pilot_hotel", week_start)
        
        self.assertEqual(metrics["tenant_id"], "pilot_hotel")
        self.assertGreater(metrics["financial_impact"]["estimated_savings_gbp"], 0)
        self.assertIn("accuracy", metrics["metrics"])

    async def test_staffing_constraints(self):
        """Verify role-ratios and budget warnings."""
        # Case 1: High demand surge (Sommelier check + Budget overflow)
        reco = self.staffer.calculate_recommendation(200) # Very high demand
        
        self.assertEqual(reco["servers"], 12) # 200/18
        self.assertEqual(reco["deltas"]["sommeliers"], 1) # Usual 1 -> 2
        self.assertTrue(any("Budget Alert" in w for w in reco["warnings"]))
        
        # Case 2: Normal demand
        reco_normal = self.staffer.calculate_recommendation(100)
        self.assertEqual(reco_normal["deltas"]["sommeliers"], 0) # Stays at 1

    @patch('app.services.reasoning_service.ReasoningService.generate_explanation')
    async def test_engine_orchestration_with_memory(self, mock_reasoning):
        """Verify Engine passes cognitive context to Reasoning."""
        mock_reasoning.return_value = {"summary": "Learned from past feedback...", "confidence_factors": []}
        
        with patch('app.services.memory_service.MemoryService.get_relevant_context', return_value="Manager said strike nearby"):
            forecast = await self.engine.get_forecast("pilot_hotel", date.today(), "dinner", {})
            
            # Check if generate_explanation was called with the cognitive_context
            args, kwargs = mock_reasoning.call_args
            self.assertEqual(kwargs['cognitive_context'], "Manager said strike nearby")
            self.assertIn("Learned", forecast["reasoning"]["summary"])

if __name__ == '__main__':
    unittest.main()

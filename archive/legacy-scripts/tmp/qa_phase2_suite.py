import asyncio
import sys
import os
from unittest.mock import MagicMock, AsyncMock, patch
from datetime import date

# Add the app directory to sys.path
sys.path.append(os.path.abspath("fastapi-backend"))

# Mock dependencies that might be missing locally
from unittest.mock import MagicMock
sys.modules["prophet"] = MagicMock()
sys.modules["prophet.serialize"] = MagicMock()
sys.modules["pandas"] = MagicMock()
sys.modules["mistralai"] = MagicMock()
sys.modules["qdrant_client"] = MagicMock()
sys.modules["qdrant_client.models"] = MagicMock() # Explicitly mock sub-module
sys.modules["anthropic"] = MagicMock()

from app.services.apaleo_adapter import ApaleoPMSAdapter
from app.services.aetherix_engine import AetherixEngine
from app.services.whatsapp_service import WhatsAppService

async def run_qa_suite():
    print("🧪 --- Phase 2 QA Suite: Starting End-to-End Verification --- 🧪\n")

    # 1. Apaleo Integration Test
    print("🔍 [TEST 1] Apaleo PMS Connection & Authentication...")
    adapter = ApaleoPMSAdapter(client_id="mock_id", client_secret="mock_secret")
    
    with patch("httpx.AsyncClient.post", new_callable=AsyncMock) as mock_post:
        mock_post.return_value = MagicMock(status_code=200, json=lambda: {"access_token": "valid_mock_token"})
        await adapter._authenticate()
        assert adapter.access_token == "valid_mock_token"
        print("✅ Apaleo Authentication PASSED")

    print("\n🔍 [TEST 2] Apaleo Data Fetching (Occupancy)...")
    with patch("httpx.AsyncClient.get", new_callable=AsyncMock) as mock_get:
        mock_get.return_value = MagicMock(status_code=200, json=lambda: {"occupancy": 92})
        occ = await adapter.get_occupancy("pilot_hotel", date.today())
        assert occ == 92
        print(f"✅ Apaleo Occupancy Fetch PASSED (Value: {occ}%)")

    # 2. Hybrid ML Engine Test
    print("\n🔍 [TEST 3] Hybrid ML Engine Orchestration (Prophet + RAG + Reasoning)...")
    engine = AetherixEngine()
    
    # Mocking internal service calls to focus on orchestration
    with patch.object(engine.forecaster, "predict", return_value=MagicMock(predicted=160, confidence=0.88, lower=150, upper=170)):
        with patch.object(engine.rag, "find_similar_patterns", new_callable=AsyncMock) as mock_rag:
            mock_rag.return_value = [{"content": "Similar busy Monday pattern", "score": 0.95}]
            with patch.object(engine.reasoner, "generate_explanation", new_callable=AsyncMock) as mock_reason:
                mock_reason.return_value = {"summary": "High demand expected due to occupancy surge and historical patterns."}
                
                # Ensure is_trained is True so it calls predict()
                engine.forecaster.is_trained = True
                
                forecast = await engine.get_forecast("pilot_hotel", date.today(), "dinner", {})
                
                assert forecast["prediction"]["covers"] == 160
                assert "High demand" in forecast["reasoning"]["summary"]
                print("✅ Hybrid ML Orchestration PASSED")

    # 3. WhatsApp Integration Test
    print("\n🔍 [TEST 4] WhatsApp Ambient Agent Response Formatting...")
    whatsapp = WhatsAppService()
    
    # Simulate intent parsing by patching THE ENGINE INSTANCE INSIDE WhatsAppService
    with patch.object(whatsapp.engine, "get_forecast", new_callable=AsyncMock) as mock_engine_call:
        mock_engine_call.return_value = forecast # Reuse forecast from previous test
        
        response = await whatsapp._generate_response("What is the forecast for today?")
        assert "Demand Forecast" in response
        assert "160" in response
        print("✅ WhatsApp Response Formatting PASSED")

    print("\n✨ --- ALL QA TESTS PASSED --- ✨")

if __name__ == "__main__":
    asyncio.run(run_qa_suite())

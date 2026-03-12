import asyncio
import sys
import os
from unittest.mock import MagicMock, AsyncMock, patch
from datetime import date

# Add the app directory to sys.path
sys.path.append(os.path.abspath("fastapi-backend"))

# Mock dependencies for local execution
from unittest.mock import MagicMock
sys.modules["prophet"] = MagicMock()
sys.modules["prophet.serialize"] = MagicMock()
sys.modules["pandas"] = MagicMock()
sys.modules["mistralai"] = MagicMock()
sys.modules["qdrant_client"] = MagicMock()
sys.modules["qdrant_client.models"] = MagicMock()
sys.modules["anthropic"] = MagicMock()

from app.services.aetherix_engine import AetherixEngine
from app.services.whatsapp_service import WhatsAppService

async def run_pilot_demo():
    print("🌟 --- Aetherix 'Day in the Life' Live Pilot Demo --- 🌟\n")
    
    engine = AetherixEngine()
    whatsapp = WhatsAppService()

    # SCENARIO: Local Concert Surge
    print("📅 [SCENARIO]: Friday, June 12th - Local Music Festival at the Arena.")
    print("🔍 System detected a demand anomaly for the Dinner service.")
    
    event_context = {
        "event": "Music Festival at Arena",
        "expected_attendance": 20000,
        "location_proximity": "0.5 miles",
        "features": {"is_event": 1}
    }

    # 1. Proactive Alert Generation
    print("\n🔔 [STEP 1]: Generating Proactive Ambient Agent Alert...")
    
    with patch.object(engine.forecaster, "predict", return_value=MagicMock(predicted=240, confidence=0.92, lower=220, upper=260)):
        with patch.object(engine.rag, "find_similar_patterns", new_callable=AsyncMock) as mock_rag:
            mock_rag.return_value = [{"content": "June 2024: Similar Arena concert led to 235 covers.", "score": 0.98}]
            with patch.object(engine.reasoner, "generate_explanation", new_callable=AsyncMock) as mock_reason:
                mock_reason.return_value = {
                    "summary": "Urgent: Forecast for tonight spiked to 240 covers (+60% vs normal) due to the Music Festival. Historical data shows similar proximity events always exceed 220 covers."
                }
                
                engine.forecaster.is_trained = True
                forecast = await engine.get_forecast("pilot_hotel", date(2026, 6, 12), "dinner", event_context)
                
                # Format proactive alert
                alert_body = (
                    f"🛑 *High-Demand Alert*\n\n"
                    f"Hi Ivan! Tonight looks unusually busy: *{forecast['prediction']['covers']} covers* expected.\n\n"
                    f"💡 *Staffing Reco:* 12 Servers (+4 needed).\n\n"
                    f"Reply 'Why?' for details."
                )
                
                print(f"📲 [AMBIENT PUSH SENT]:\n---\n{alert_body}\n---")

    # 2. Conversational "Why?" Query
    print("\n💬 [STEP 2]: User replies 'Why?'")
    
    with patch.object(whatsapp.engine, "get_forecast", new_callable=AsyncMock) as mock_engine_call:
        mock_engine_call.return_value = forecast
        
        response = await whatsapp._generate_response("Why?")
        print(f"🤖 [AGENT RESPONSE]:\n---\n{response}\n---")

    print("\n✨ --- Pilot Demo Successfully Simulated --- ✨")

if __name__ == "__main__":
    asyncio.run(run_pilot_demo())

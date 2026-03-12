import asyncio
import sys
import os
from unittest.mock import MagicMock, AsyncMock, patch

# Add the app directory to sys.path
sys.path.append(os.path.abspath("fastapi-backend"))

# Mock dependencies that might be missing locally
from unittest.mock import MagicMock
sys.modules["prophet"] = MagicMock()
sys.modules["prophet.serialize"] = MagicMock()
sys.modules["pandas"] = MagicMock()

from app.services.whatsapp_service import WhatsAppService

async def test_whatsapp_flow():
    print("🚀 Starting WhatsApp Flow Verification...")
    
    # Initialize service
    service = WhatsAppService()
    
    # Mock data representing a Twilio inbound webhook
    mock_data = {
        "From": "whatsapp:+1234567890",
        "Body": "What's the forecast for tonight?",
        "To": "whatsapp:+14155238886"
    }
    
    print(f"📥 Simulating inbound message: '{mock_data['Body']}' from {mock_data['From']}")
    
    # Patch the httpx client and engine to avoid real API calls during logic verification
    with patch("httpx.AsyncClient.post", new_callable=AsyncMock) as mock_post:
        # Configure mock response
        mock_post.return_value = MagicMock(status_code=201)
        
        # Handle the message
        await service.handle_inbound_message(mock_data)
        
        # Verify send_message was called
        print("📤 Verifying outgoing message...")
        assert mock_post.called, "Twilio API was not called!"
        
        # Check call arguments (data)
        call_args = mock_post.call_args[1]["data"]
        print(f"✅ Outgoing message body:\n---\n{call_args['Body']}\n---")
        
        assert "Aetherix Forecast Update" in call_args["Body"] or "Demand Forecast" in call_args["Body"]
        assert "Predicted Covers" in call_args["Body"]
        
    print("\n🚀 Starting Staffing Logic Verification...")
    mock_staff_data = {
        "From": "whatsapp:+1234567890",
        "Body": "Show staffing reco",
    }
    
    with patch("httpx.AsyncClient.post", new_callable=AsyncMock) as mock_post:
        mock_post.return_value = MagicMock(status_code=201)
        await service.handle_inbound_message(mock_staff_data)
        
        call_args = mock_post.call_args[1]["data"]
        print(f"✅ Staffing message body:\n---\n{call_args['Body']}\n---")
        assert "Staffing Suggestion" in call_args["Body"]

    print("\n✨ Verification PASSED!")

if __name__ == "__main__":
    asyncio.run(test_whatsapp_flow())

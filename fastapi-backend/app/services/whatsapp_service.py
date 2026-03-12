import os
import httpx
import logging
from datetime import date
from typing import Dict, Any, Optional
from app.services.aetherix_engine import AetherixEngine

logger = logging.getLogger(__name__)

class WhatsAppService:
    """
    Handles WhatsApp communication via Twilio.
    Phase 2: Ambient Agent experience implementation.
    """
    
    def __init__(self):
        self.account_sid = os.getenv("TWILIO_ACCOUNT_SID", "AC_MOCK_SID")
        self.auth_token = os.getenv("TWILIO_AUTH_TOKEN", "MOCK_TOKEN")
        self.whatsapp_from = os.getenv("TWILIO_WHATSAPP_NUMBER", "whatsapp:+14155238886") # Twilio Sandbox
        self.engine = AetherixEngine()

    async def handle_inbound_message(self, data: Dict[str, Any]):
        """
        Main entry point for inbound messages.
        Data contains Twilio's standard webhook parameters (From, Body, etc).
        """
        sender = data.get("From")
        body = data.get("Body", "").strip()
        
        if not sender or not isinstance(sender, str):
            logger.error("Inbound message missing 'From' field or invalid type.")
            return

        logger.info(f"Received WhatsApp from {sender}: {body}")
        
        # 1. Logic: Determine if it's a forecast request or general query
        # For Phase 2 Pilot, we assume queries are about restaurant demand.
        response_text = await self._generate_response(body)
        
        # 2. Send response back
        await self.send_message(sender, response_text)

    async def _generate_response(self, text: str) -> str:
        """Uses AetherixEngine to generate context-aware F&B responses."""
        query = text.lower()
        
        # 1. Demand Forecast Intent
        if any(w in query for w in ["forecast", "covers", "prediction"]):
            forecast = await self.engine.get_forecast("pilot_hotel", date.today(), "dinner", {})
            p = forecast["prediction"]
            r = forecast["reasoning"]
            
            return (
                f"📊 *Demand Forecast: Dinner Today*\n"
                f"━━━━━━━━━━━━━━━━━━\n"
                f"• *Predicted Covers:* {p['covers']}\n"
                f"• *Confidence:* {int(p['confidence']*100)}%\n"
                f"• *Range:* {p['interval'][0]} - {p['interval'][1]}\n\n"
                f"📝 *Rationale:*\n{r['summary']}"
            )
            
        # 2. Staffing Recommendation Intent
        if any(w in query for w in ["staff", "staffing", "reco"]):
            forecast = await self.engine.get_forecast("pilot_hotel", date.today(), "dinner", {})
            s = forecast["staffing"]
            d = s["deltas"]
            
            delta_str = (
                f"({'+' if d['servers'] >= 0 else ''}{d['servers']} vs usual)"
            )
            
            return (
                f"👥 *Staffing Suggestion*\n"
                f"━━━━━━━━━━━━━━━━━━\n"
                f"• *Servers:* {s['servers']} {delta_str}\n"
                f"• *Kitchen:* {s['kitchen']}\n"
                f"• *Hosts:* {s['hosts']}\n\n"
                f"💡 *Action:* {s['rationale']}"
            )

        # 3. Status/Help Intent
        if any(w in query for w in ["status", "hi", "hello", "help"]):
            return (
                "👋 *Aetherix Ambient Agent*\n"
                "I'm monitoring your operations. You can ask me:\n"
                "• \"What's the forecast for tonight?\"\n"
                "• \"Should I change staffing levels?\"\n"
                "• \"Show covers for today.\""
            )
        
        return "I'm not sure how to help with that yet. Try asking for a 'forecast' or 'staffing' update."

    async def send_message(self, to: str, body: str):
        """Sends a WhatsApp message via Twilio API."""
        url = f"https://api.twilio.com/2010-04-01/Accounts/{self.account_sid}/Messages.json"
        
        auth = (self.account_sid, self.auth_token)
        data = {
            "To": to,
            "From": self.whatsapp_from,
            "Body": body
        }
        
        async with httpx.AsyncClient() as client:
            try:
                response = await client.post(url, data=data, auth=auth)
                if response.status_code != 201:
                    logger.error(f"Twilio error: {response.text}")
                else:
                    logger.info(f"Message sent to {to}")
            except Exception as e:
                logger.error(f"Failed to send Twilio message: {str(e)}")

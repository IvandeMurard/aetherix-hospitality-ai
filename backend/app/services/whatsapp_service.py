import logging
import os
from datetime import date
from typing import Any, Dict, Optional

import httpx
from sqlalchemy.future import select

from app.core.exceptions import NotConfiguredError
from app.db.models import RestaurantProfile
from app.db.session import AsyncSessionLocal
from app.services.aetherix_engine import AetherixEngine
from app.services.memory_service import MemoryService

logger = logging.getLogger(__name__)


class WhatsAppService:
    """
    Handles WhatsApp communication via Twilio.
    Phase 2: Ambient Agent experience implementation.
    """

    def __init__(self):
        account_sid = os.getenv("TWILIO_ACCOUNT_SID")
        auth_token = os.getenv("TWILIO_AUTH_TOKEN")
        whatsapp_number = os.getenv("TWILIO_WHATSAPP_NUMBER")

        if not account_sid:
            raise NotConfiguredError("TWILIO_ACCOUNT_SID is not set")
        if not auth_token:
            raise NotConfiguredError("TWILIO_AUTH_TOKEN is not set")
        if not whatsapp_number:
            raise NotConfiguredError("TWILIO_WHATSAPP_NUMBER is not set")

        self.account_sid = account_sid
        self.auth_token = auth_token
        self.whatsapp_from = whatsapp_number
        self.engine = AetherixEngine()
        self.memory = MemoryService()

    async def _resolve_tenant(self, sender: str) -> Optional[RestaurantProfile]:
        """Look up the RestaurantProfile matching the sender's phone number.

        Args:
            sender: Phone number stripped of the 'whatsapp:' prefix (E.164 format).

        Returns:
            The matching RestaurantProfile, or None if not found.
        """
        async with AsyncSessionLocal() as db:
            result = await db.execute(
                select(RestaurantProfile).where(RestaurantProfile.phone_number == sender)
            )
            return result.scalars().first()

    async def handle_inbound_message(self, data: Dict[str, Any]):
        """
        Main entry point for inbound messages.
        Data contains Twilio's standard webhook parameters (From, Body, etc).
        """
        sender_raw = data.get("From")
        body = data.get("Body", "").strip()

        if not sender_raw or not isinstance(sender_raw, str):
            logger.error("Inbound message missing 'From' field or invalid type.")
            return

        # Strip whatsapp: prefix to get the plain E.164 number for DB lookup
        sender_number = sender_raw.removeprefix("whatsapp:")

        logger.info(f"Received WhatsApp from {sender_raw}: {body}")

        # Verify sender against registered profiles — no side-effects for unknown senders
        profile = await self._resolve_tenant(sender_number)
        if profile is None:
            logger.warning(
                "WhatsApp message from unknown sender %s — ignoring (not in any RestaurantProfile)",
                sender_raw,
            )
            return

        tenant_id = profile.tenant_id

        # 1. Feedback Detection (Phase 3 Learning Loop)
        if any(w in body.lower() for w in ["wrong", "incorrect", "too high", "too low", "no"]):
            await self.memory.learn_from_feedback(tenant_id, "latest_alert", body)
            from app.services.ops_dispatcher import dispatch_anomaly
            await dispatch_anomaly(
                title=f"Manager negative feedback via WhatsApp — {sender_raw}",
                detail=f"Message: {body!r}\n\nThe memory service has stored this for future learning.",
                tags=["feedback", "whatsapp"],
            )
            response_text = "Thank you for the feedback. I've noted this for future forecasts."
        elif body.lower() == "push":
            # 2. 2-Way Sync Action
            result = await self.engine.push_staffing(tenant_id)
            response_text = result["message"]
        else:
            # 3. General logic: Determine if it's a forecast request or general query
            response_text = await self._generate_response(body, tenant_id)

        # 2. Send response back
        await self.send_message(sender_raw, response_text)

    async def _generate_response(self, text: str, tenant_id: str) -> str:
        """Uses AetherixEngine to generate context-aware F&B responses."""
        query = text.lower()

        # 1. Demand Forecast Intent
        if any(w in query for w in ["forecast", "covers", "prediction"]):
            forecast = await self.engine.get_forecast(tenant_id, date.today(), "dinner", {})
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
            forecast = await self.engine.get_forecast(tenant_id, date.today(), "dinner", {})
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
                "• \"Show covers for today.\"\n"
                "• \"PUSH\" (to sync the latest recommendation with Apaleo)"
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

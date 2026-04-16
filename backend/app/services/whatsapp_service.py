import asyncio
import logging
import os
from datetime import date
from typing import Any, Dict, Optional

import httpx
from sqlalchemy.future import select

from app.core.demo_events import demo_emit
from app.core.exceptions import NotConfiguredError
from app.db.models import RestaurantProfile
from app.db.session import AsyncSessionLocal
from app.providers.factory import get_llm_provider
from app.services.aetherix_engine import AetherixEngine
from app.services.memory_service import MemoryService

logger = logging.getLogger(__name__)


class WhatsAppService:
    """
    Handles WhatsApp communication via Twilio.
    Phase 2: Ambient Agent experience implementation.
    """

    def __init__(self):
        self.account_sid = os.getenv("TWILIO_ACCOUNT_SID")
        self.auth_token = os.getenv("TWILIO_AUTH_TOKEN")
        self.whatsapp_from = os.getenv("TWILIO_WHATSAPP_NUMBER")
        self.engine = AetherixEngine()
        self.memory = MemoryService()
        self._llm = get_llm_provider()

    def _assert_configured(self) -> None:
        """Raise NotConfiguredError if Twilio credentials are missing."""
        if not self.account_sid:
            raise NotConfiguredError("TWILIO_ACCOUNT_SID is not set")
        if not self.auth_token:
            raise NotConfiguredError("TWILIO_AUTH_TOKEN is not set")
        if not self.whatsapp_from:
            raise NotConfiguredError("TWILIO_WHATSAPP_NUMBER is not set")

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
            # 2-Way Sync — Apaleo write not yet active (Decision #7: read-only Phase 0)
            response_text = (
                "⚠️ Apaleo staffing sync is not yet active in this phase.\n"
                "Your latest recommendation is ready — reply 'staffing' to review it."
            )
        else:
            # 3. General query — delegated to LLM with agent constitution
            response_text = await self._generate_response(body, tenant_id, profile)

        # 2. Send response back
        await self.send_message(sender_raw, response_text)

    async def _generate_response(
        self, text: str, tenant_id: str, profile: RestaurantProfile
    ) -> str:
        """Generates a context-aware F&B response via single LLM call.

        Loads the latest forecast to ground the agent constitution system prompt,
        then delegates intent understanding entirely to the LLM (Claude).
        """
        from app.services.agent_constitution import AgentConstitutionService

        # 1. Load latest forecast for context injection into the system prompt
        try:
            forecast = await self.engine.get_forecast(tenant_id, date.today(), "dinner", {})
            prediction = forecast.get("prediction", {})
            patterns = forecast.get("historical_patterns", [])
            similar_text = "\n".join(
                f"- {p['payload'].get('pattern_text', '')} ({p['payload'].get('outcome_description', '')})"
                for p in patterns[:3]
                if "payload" in p
            ) if patterns else ""
            forecast_context = {
                "date": date.today().isoformat(),
                "covers": prediction.get("covers", "—"),
                "confidence": int(prediction.get("confidence", 0) * 100),
                "similar_nights": similar_text,
                "staffing": forecast.get("staffing_recommendation", {}),
            }
        except Exception as exc:
            logger.warning("WhatsApp: failed to load forecast for context: %s", exc)
            forecast_context = {"date": date.today().isoformat()}

        # 2. Build agent constitution system prompt
        try:
            system_prompt = AgentConstitutionService().build_system_prompt(
                profile=profile,
                forecast_context=forecast_context,
            )
        except Exception as exc:
            logger.warning("WhatsApp: AgentConstitutionService failed: %s", exc)
            system_prompt = None

        # 3. Single LLM call — intent understanding delegated to Claude
        try:
            llm_kwargs: Dict = {
                "messages": [{"role": "user", "content": text}],
                "max_tokens": 400,
                "temperature": 0.3,
            }
            if system_prompt is not None:
                llm_kwargs["system"] = system_prompt
            return await self._llm.complete(**llm_kwargs)
        except Exception as exc:
            logger.error("WhatsApp: LLM call failed: %s", exc)
            return (
                "I'm having trouble processing your request right now. "
                "Please try again in a moment."
            )

    async def send_message(self, to: str, body: str):
        """Sends a WhatsApp message via Twilio API."""
        self._assert_configured()
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
                    # Demo board: highlight WhatsApp/Twilio node after delivery
                    asyncio.create_task(demo_emit("whatsapp"))
            except Exception as e:
                logger.error(f"Failed to send Twilio message: {str(e)}")

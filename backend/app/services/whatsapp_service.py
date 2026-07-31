import asyncio
import logging
import os
from datetime import date
from typing import Any, Dict, Optional

import httpx
from sqlalchemy.future import select

from app.core.config import DEMO_MODE
from app.core.demo_events import demo_emit
from app.core.exceptions import NotConfiguredError
from app.db.models import AgentActionLog, RestaurantProfile
from app.db.session import AsyncSessionLocal
from app.core.observability import guardrail_trip, span as obs_span
from app.providers.factory import get_llm_provider
from app.services.aetherix_engine import AetherixEngine
from app.services.memory_service import MemoryService

logger = logging.getLogger(__name__)

# HOS-303 — typed trip reason (NFR2, ADR-0009): the untrained-model mock
# forecast must never ground a manager-facing reply outside DEMO_MODE.
MOCK_FORECAST_TOOL = "mock_forecast_guardrail"
REASON_MOCK_FORECAST = "mock_forecast_suppressed"


def evaluate_mock_suppression(
    is_mock: bool, demo_mode: bool | None = None
) -> tuple[str, str] | None:
    """Trip when an untrained-model forecast would reach a manager (HOS-303).

    Pure predicate extracted for the `guardrail` eval layer (HOS-321). In
    DEMO_MODE the numbers are allowed through but visibly marked, so no trip:
    the guardrail protects the *manager-facing* path, not the demo path.
    """
    demo = DEMO_MODE if demo_mode is None else demo_mode
    if not is_mock or demo:
        return None
    return (
        REASON_MOCK_FORECAST,
        "prediction.is_mock=True outside DEMO_MODE; covers withheld from reply.",
    )


async def _record_mock_forecast_trip(hotel_id: str) -> None:
    """Log one typed trip row when mock covers are withheld from a reply."""
    try:
        async with AsyncSessionLocal() as db:
            db.add(
                AgentActionLog(
                    hotel_id=hotel_id or "_system",
                    tool_name=MOCK_FORECAST_TOOL,
                    status="tool_error",
                    error_code=REASON_MOCK_FORECAST,
                    payload={
                        "kind": "trip",
                        "reason": REASON_MOCK_FORECAST,
                        "detail": (
                            "prediction.is_mock=True outside DEMO_MODE; "
                            "covers/staffing withheld from LLM context"
                        ),
                    },
                    request_id="",
                )
            )
            await db.commit()
    except Exception as exc:  # noqa: BLE001
        logger.warning("mock_forecast_guardrail: agent_action_log write failed: %s", exc)
    guardrail_trip(MOCK_FORECAST_TOOL, hotel_id, REASON_MOCK_FORECAST)
    logger.warning("mock_forecast_guardrail: TRIP hotel_id=%s", hotel_id)


def _mask_number(raw: Optional[str]) -> str:
    """Mask a phone / WhatsApp identifier for logs (Q2-03 / finding 8.5, HOS-289).

    Keeps the ``whatsapp:`` prefix + last 2 digits so lines stay debuggable
    without persisting a full E.164 number (PII) to application logs.
    """
    if not raw or not isinstance(raw, str):
        return "<none>"
    prefix = "whatsapp:" if raw.startswith("whatsapp:") else ""
    digits = "".join(ch for ch in raw if ch.isdigit())
    tail = digits[-2:] if len(digits) >= 2 else digits
    return f"{prefix}***{tail}"


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

        # Q2-03 (HOS-289): never log the message body or a full number (PII).
        logger.info(
            "Received WhatsApp from %s (%d chars)", _mask_number(sender_raw), len(body)
        )

        # Verify sender against registered profiles — no side-effects for unknown senders
        profile = await self._resolve_tenant(sender_number)
        if profile is None:
            logger.warning(
                "WhatsApp message from unknown sender %s — ignoring (not in any RestaurantProfile)",
                _mask_number(sender_raw),
            )
            return

        tenant_id = profile.tenant_id  # convention-ok: used as str slug for memory/ops calls

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
            if evaluate_mock_suppression(bool(prediction.get("is_mock"))):
                # HOS-303: the model is not trained — the hardcoded fallback
                # covers must never reach a manager. Typed trip + date-only
                # context (same minimal shape as the forecast-failure path).
                await _record_mock_forecast_trip(tenant_id)
                forecast_context = {"date": date.today().isoformat()}
            else:
                patterns = forecast.get("historical_patterns", [])
                similar_text = "\n".join(
                    f"- {p['payload'].get('pattern_text', '')} ({p['payload'].get('outcome_description', '')})"
                    for p in patterns[:3]
                    if "payload" in p
                ) if patterns else ""
                covers = prediction.get("covers", "—")
                if prediction.get("is_mock"):
                    # DEMO_MODE: numbers allowed but visibly marked (AC2).
                    covers = f"{covers} (demo data — model not trained)"
                forecast_context = {
                    "date": date.today().isoformat(),
                    "covers": covers,
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
                with obs_span("whatsapp.send", to=_mask_number(to), body_chars=len(body)):
                    response = await client.post(url, data=data, auth=auth)
                if response.status_code != 201:
                    logger.error(f"Twilio error: {response.text}")
                else:
                    logger.info("Message sent to %s", _mask_number(to))
                    # Demo board: highlight WhatsApp/Twilio node after delivery
                    asyncio.create_task(demo_emit("whatsapp"))
            except Exception as e:
                logger.error(f"Failed to send Twilio message: {str(e)}")

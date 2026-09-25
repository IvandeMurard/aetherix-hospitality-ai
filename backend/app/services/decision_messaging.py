"""Outbound decision messages — buttons behind a flag, text always as fallback.

ADR-0007 §16.4 (Décision #38). Two quick-reply sets, fixed payload IDs
(``manager_decision.BUTTON_*``):

* ``decision`` — Accepter / Refuser / Corriger, attached to the staffing
  recommendation. Business-initiated → needs a WhatsApp-**approved** Content
  template (``TWILIO_CONTENT_SID_DECISION_{FR,EN}``). Pending ops step.
* ``confirm``  — Oui / Non, attached to a HITL confirmation. Sent as a reply
  inside the 24 h customer-service window → a saved (unapproved) template is
  enough (``TWILIO_CONTENT_SID_CONFIRM_{FR,EN}``), max 3 buttons.

Buttons are used only when ``WHATSAPP_DECISION_BUTTONS`` is on AND the Content
SID for the set and locale is configured; any failure of the Content send falls
back to the same text with an explicit "Reply ACCEPT / REJECT / CORRECT" hint.
The text path never depends on buttons.
"""
from __future__ import annotations

import logging
from typing import Optional

from app.core import config
from app.services.manager_decision import text_for

logger = logging.getLogger(__name__)


def content_sid(kind: str, locale: Optional[str] = "fr") -> str:
    en = (locale or "").lower().startswith("en")
    return {
        ("decision", False): config.TWILIO_CONTENT_SID_DECISION_FR,
        ("decision", True): config.TWILIO_CONTENT_SID_DECISION_EN,
        ("confirm", False): config.TWILIO_CONTENT_SID_CONFIRM_FR,
        ("confirm", True): config.TWILIO_CONTENT_SID_CONFIRM_EN,
    }.get((kind, en), "")


def buttons_available(kind: Optional[str], locale: Optional[str] = "fr") -> bool:
    return bool(kind) and config.WHATSAPP_DECISION_BUTTONS and bool(content_sid(kind, locale))


def text_fallback(text: str, kind: Optional[str], locale: Optional[str] = "fr") -> str:
    """The text a manager gets when buttons are not used: the hint tells them
    which exact keywords the deterministic fast path understands."""
    if kind == "decision":
        return f"{text}\n{text_for('decision_text_hint', locale)}"
    return text  # confirmation copy already ends with "Répondez OUI ou NON."


async def send_with_buttons(
    client, to: str, text: str, kind: Optional[str], locale: Optional[str] = "fr"
) -> str:
    """Send ``text`` with the ``kind`` quick-reply set when available, else as
    plain text. Returns the Twilio message SID."""
    if buttons_available(kind, locale):
        try:
            return await client.send_whatsapp_content(to, content_sid(kind, locale), {"1": text})
        except Exception as exc:  # noqa: BLE001 — any Content failure → text
            logger.warning(
                "decision_messaging: content send failed kind=%s (%r) — falling back to text",
                kind, exc,
            )
    return await client.send_whatsapp(to, text_fallback(text, kind, locale))

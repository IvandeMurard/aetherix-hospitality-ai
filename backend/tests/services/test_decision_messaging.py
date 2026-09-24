"""Décision #38 / ADR-0007 §16.4 — quick-reply buttons behind a flag, text fallback.

What is proven here: the outbound request shape (ContentSid + ContentVariables),
the flag / missing-SID / Content-failure fallbacks to text, and (in
test_inbound_decision.py) the inbound payload handling. What is NOT proven:
that WhatsApp approves the template or renders the buttons — that needs the
ops step in ADR-0007 §16.4 and a live number.
"""
from __future__ import annotations

import json
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

from app.core import config
from app.integrations.twilio_client import TwilioClient
from app.services import alert_dispatcher
from app.services.decision_messaging import send_with_buttons, text_fallback


def _client():
    c = MagicMock()
    c.send_whatsapp = AsyncMock(return_value="SMtext")
    c.send_whatsapp_content = AsyncMock(return_value="SMcontent")
    return c


@pytest.fixture
def buttons_on(monkeypatch):
    monkeypatch.setattr(config, "WHATSAPP_DECISION_BUTTONS", True)
    monkeypatch.setattr(config, "TWILIO_CONTENT_SID_DECISION_FR", "HXdecisionfr")
    monkeypatch.setattr(config, "TWILIO_CONTENT_SID_CONFIRM_FR", "HXconfirmfr")


@pytest.mark.asyncio
async def test_flag_off_sends_text_with_keyword_hint(monkeypatch):
    monkeypatch.setattr(config, "WHATSAPP_DECISION_BUTTONS", False)
    c = _client()
    await send_with_buttons(c, "+33600000001", "Ajouter 2 serveurs.", "decision")
    c.send_whatsapp_content.assert_not_awaited()
    body = c.send_whatsapp.await_args.args[1]
    assert body.startswith("Ajouter 2 serveurs.") and "ACCEPTER, REFUSER ou CORRIGER" in body


@pytest.mark.asyncio
async def test_flag_on_sends_content_template(buttons_on):
    c = _client()
    sid = await send_with_buttons(c, "+33600000001", "Ajouter 2 serveurs.", "decision")
    assert sid == "SMcontent"
    c.send_whatsapp_content.assert_awaited_once_with(
        "+33600000001", "HXdecisionfr", {"1": "Ajouter 2 serveurs."}
    )
    c.send_whatsapp.assert_not_awaited()


@pytest.mark.asyncio
async def test_missing_content_sid_falls_back_to_text(buttons_on, monkeypatch):
    monkeypatch.setattr(config, "TWILIO_CONTENT_SID_CONFIRM_FR", "")
    c = _client()
    await send_with_buttons(c, "+33600000001", "Je note un refus ?", "confirm")
    c.send_whatsapp_content.assert_not_awaited()
    c.send_whatsapp.assert_awaited_once()


@pytest.mark.asyncio
async def test_content_failure_falls_back_to_text(buttons_on):
    # e.g. Twilio 63016 / template not approved yet.
    c = _client()
    c.send_whatsapp_content = AsyncMock(side_effect=RuntimeError("63016"))
    sid = await send_with_buttons(c, "+33600000001", "Ajouter 2 serveurs.", "decision")
    assert sid == "SMtext"
    assert "ACCEPTER" in c.send_whatsapp.await_args.args[1]


def test_confirmation_text_fallback_is_unchanged():
    assert text_fallback("Je note un refus, c'est bien ça ? Répondez OUI ou NON.", "confirm") \
        == "Je note un refus, c'est bien ça ? Répondez OUI ou NON."


@pytest.mark.asyncio
async def test_twilio_content_request_shape():
    client = TwilioClient(account_sid="AC1", auth_token="tok", whatsapp_from="whatsapp:+14155238886")
    captured = {}

    async def _post(self, url, data=None, auth=None):
        captured.update(data)
        return httpx.Response(201, json={"sid": "SM1"}, request=httpx.Request("POST", url))

    with patch.object(httpx.AsyncClient, "post", _post):
        sid = await client.send_whatsapp_content("+33600000001", "HXabc", {"1": "Ajouter 2 serveurs"})
    assert sid == "SM1"
    assert captured["To"] == "whatsapp:+33600000001"
    assert captured["ContentSid"] == "HXabc"
    assert json.loads(captured["ContentVariables"]) == {"1": "Ajouter 2 serveurs"}
    assert "Body" not in captured


@pytest.mark.asyncio
async def test_dispatcher_uses_buttons_only_when_enabled(buttons_on):
    c = _client()
    await alert_dispatcher.AlertDispatcherService._send_whatsapp_decision(c, "+33600000001", "msg")
    c.send_whatsapp_content.assert_awaited_once()


@pytest.mark.asyncio
async def test_dispatcher_text_path_unchanged_when_flag_off(monkeypatch):
    monkeypatch.setattr(config, "WHATSAPP_DECISION_BUTTONS", False)
    c = _client()
    await alert_dispatcher.AlertDispatcherService._send_whatsapp_decision(c, "+33600000001", "msg")
    c.send_whatsapp.assert_awaited_once_with(to="+33600000001", body="msg")

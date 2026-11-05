"""Tout TwiML renvoyé au webhook Twilio doit être du XML bien formé.

Régression du 05/11/2026 : « F&B » écrit tel quel dans la réponse « pas de contexte » faisait
échouer Twilio (erreur 12200 : « The reference to entity "B" must end with the ';' delimiter »).
L'expéditeur inconnu ne recevait alors aucune réponse, sans erreur visible côté serveur.
"""
from __future__ import annotations

import xml.etree.ElementTree as ET

import pytest

from app.api.routes import twilio_inbound as ti


@pytest.mark.parametrize(
    "name",
    ["_TWIML_EMPTY", "_TWIML_QUERY_ACK", "_TWIML_QUERY_NO_CONTEXT"],
)
def test_static_twiml_is_well_formed(name: str) -> None:
    root = ET.fromstring(getattr(ti, name))
    assert root.tag == "Response"


def test_no_context_reply_keeps_the_ampersand() -> None:
    root = ET.fromstring(ti._TWIML_QUERY_NO_CONTEXT)
    assert "F&B" in root.findtext("Message")


def test_dynamic_twiml_escapes_special_characters() -> None:
    root = ET.fromstring(ti._twiml_message("F&B <urgent> \"ok\" & 'ok'"))
    assert root.findtext("Message") == "F&B <urgent> \"ok\" & 'ok'"

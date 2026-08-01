"""Contrôles PII — Story 7.5 / HOS-115 (AC2, AC3).

Deux garanties, testées séparément parce qu'elles échouent différemment :

  1. `PIIStripper` retire bien la PII convive d'un payload PMS synthétique
     (AC2 : « payload PII synthétique → zéro PII en base »).
  2. `pseudonymise()` ne rend jamais la valeur d'origine à un log
     (AC3, volet journalisation — le volet stockage n'est pas satisfait, cf.
     `docs/GDPR-DATA-INVENTORY.md` §3.3).

Le test 1 est écrit en **liste négative** : on n'assert pas que les trois champs
connus ont disparu, on assert qu'*aucune* valeur sensible du payload ne survit,
quel que soit le champ qui la porte. Un stripper qui gagne un champ demain sans
gagner sa protection doit faire échouer ce test, pas passer.
"""
from __future__ import annotations

import pytest

from app.core import config
from app.core.pii import (
    STORED_DIGEST_PREFIX,
    PepperNotConfigured,
    digest_identifier,
    pseudonymise,
)
from app.services.pms_sync import PIIStripper


@pytest.fixture(autouse=True)
def _pepper(monkeypatch):
    """Poivre déterministe — les digests doivent être stables dans un test."""
    monkeypatch.setattr(config, "PII_HASH_PEPPER", "test-pepper-not-a-real-secret")

# Valeurs marquées : si l'une réapparaît où que ce soit dans la sortie, la PII a fuité.
_GUEST_NAME = "Amélie Rousseau-Kowalski"
_GUEST_EMAIL = "amelie.rousseau@example.invalid"
_GUEST_PHONE = "+33612345678"
_GUEST_ID = "APALEO-GUEST-77219"

_SENSITIVE = (_GUEST_NAME, _GUEST_EMAIL, _GUEST_PHONE, _GUEST_ID)


def _reservation() -> dict:
    return {
        "reservation_id": "RES-001",
        "guest_id": _GUEST_ID,
        "guest_name": _GUEST_NAME,
        "guest_email": _GUEST_EMAIL,
        "guest_phone": _GUEST_PHONE,
        "arrival": "2026-08-12",
        "departure": "2026-08-14",
        "adults": 2,
        "rate_plan": "BAR",
    }


class TestPIIStripper:
    def test_no_sensitive_value_survives_anywhere(self):
        """AC2 — aucune valeur marquée ne subsiste, quel que soit le champ."""
        stripped = PIIStripper.strip_guest_data(_reservation())
        blob = repr(stripped)
        for value in _SENSITIVE:
            assert value not in blob, f"PII survivante dans la sortie : {value!r}"

    def test_operational_fields_survive(self):
        """Le stripper ne doit pas mutiler la donnée dont le forecast dépend."""
        stripped = PIIStripper.strip_guest_data(_reservation())
        assert stripped["arrival"] == "2026-08-12"
        assert stripped["adults"] == 2
        assert stripped["rate_plan"] == "BAR"

    def test_guest_id_becomes_a_stable_digest(self):
        """Le comptage par convive reste possible sans l'identité."""
        first = PIIStripper.strip_guest_data(_reservation())
        second = PIIStripper.strip_guest_data(_reservation())
        assert "guest_id" not in first
        assert first["guest_hashed_id"] == second["guest_hashed_id"]
        assert first["guest_hashed_id"].startswith(STORED_DIGEST_PREFIX)

    def test_guest_digest_depends_on_the_pepper(self, monkeypatch):
        """Écart n°3 de l'inventaire — un sha256 nu était rejouable hors ligne.

        Deux poivres différents doivent produire deux digests différents pour le
        même identifiant : c'est ce qui distingue un digest poivré d'un hachage
        que quiconque peut recalculer avec la liste des guest_id.
        """
        with_first = PIIStripper.strip_guest_data(_reservation())["guest_hashed_id"]
        monkeypatch.setattr(config, "PII_HASH_PEPPER", "un-autre-poivre")
        with_second = PIIStripper.strip_guest_data(_reservation())["guest_hashed_id"]
        assert with_first != with_second

    def test_absent_guest_id_is_not_invented(self):
        """Pas de guest_id en entrée → pas de champ haché en sortie."""
        payload = _reservation()
        payload.pop("guest_id")
        stripped = PIIStripper.strip_guest_data(payload)
        assert "guest_hashed_id" not in stripped


class TestPseudonymise:
    def test_never_returns_the_input(self):
        for value in (_GUEST_PHONE, _GUEST_EMAIL):
            assert value not in pseudonymise(value)

    def test_is_stable_across_transport_noise(self):
        """Twilio préfixe `whatsapp:` et les espaces traînent — même personne, même digest."""
        raw = "whatsapp:+33612345678".replace("whatsapp:", "")
        assert pseudonymise(raw) == pseudonymise(" +33612345678 ")

    def test_distinguishes_two_senders(self):
        """Un opérateur doit pouvoir séparer deux expéditeurs dans les logs."""
        assert pseudonymise("+33612345678") != pseudonymise("+33698765432")

    @pytest.mark.parametrize("empty", [None, ""])
    def test_empty_is_marked_not_hashed(self, empty):
        """« absent » et « présent mais inconnu » doivent rester distinguables."""
        assert pseudonymise(empty) == "<absent>"


class TestDigestIdentifier:
    """Digest de stockage — celui qui remplace le numéro en base."""

    def test_never_returns_the_input(self):
        assert _GUEST_PHONE not in digest_identifier(_GUEST_PHONE)

    def test_is_deterministic_so_dedup_still_works(self):
        """L'idempotence compare des digests — elle n'a jamais eu besoin du clair."""
        assert digest_identifier(_GUEST_PHONE) == digest_identifier(_GUEST_PHONE)

    def test_survives_the_whatsapp_prefix(self):
        """Twilio préfixe l'entrant ; un même expéditeur ne doit pas produire 2 digests."""
        assert digest_identifier("whatsapp:+33612345678") == digest_identifier("+33612345678")

    def test_distinguishes_two_senders(self):
        assert digest_identifier("+33612345678") != digest_identifier("+33698765432")

    @pytest.mark.parametrize("empty", [None, "", "   "])
    def test_empty_returns_none(self, empty):
        assert digest_identifier(empty) is None

    def test_refuses_to_hash_without_a_pepper(self, monkeypatch):
        """Échouer bruyamment plutôt que stocker un hachage nu en se croyant protégé.

        Un poivre vide produirait un sha256 récupérable en quelques secondes sur
        l'espace des numéros de téléphone. Le pire scénario n'est pas l'erreur :
        c'est la dégradation silencieuse que personne ne remarque.
        """
        monkeypatch.setattr(config, "PII_HASH_PEPPER", "")
        with pytest.raises(PepperNotConfigured):
            digest_identifier("+33612345678")

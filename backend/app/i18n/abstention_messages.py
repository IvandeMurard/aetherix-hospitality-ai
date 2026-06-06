"""Manager-facing abstention copy — FR/EN (HOS-206 / ADR-0007 §D6.d).

**PM caveat (04/06, BLOCKING):** a hotel manager must NEVER see a raw reason
code (`cold_start_no_cohort`, …). Every reason maps to a localized, OQ4-toned
string here. Coverage is enforced by ``tests/i18n/test_abstention_messages.py``.

Locale: ``RestaurantProfile`` has no ``locale`` column yet, so resolution
defaults to French (the pilot property). Adding a ``locale`` column for EN
properties is a follow-up; `get(locale)` already supports `"en"`.
"""
from __future__ import annotations

from dataclasses import dataclass

from app.services.abstention import ABSTENTION_REASONS

DEFAULT_LOCALE = "fr"


@dataclass(frozen=True)
class LocalizedMessages:
    fr: str
    en: str

    def get(self, locale: str | None = DEFAULT_LOCALE) -> str:
        return self.en if (locale or "").lower().startswith("en") else self.fr


# 7 reasons × {fr, en} = 14 manager-facing strings. No raw codes (enforced).
_MESSAGES: dict[str, dict[str, str]] = {
    "cold_start_no_cohort": {
        "fr": "Aetherix manque encore d'historique comparable pour cet établissement — pas de recommandation fiable aujourd'hui.",
        "en": "Aetherix doesn't yet have enough comparable history for this property — no reliable recommendation today.",
    },
    "cold_start_meta_learner_drift": {
        "fr": "Le modèle d'amorçage a été suspendu (données récentes trop instables) — Aetherix préfère s'abstenir aujourd'hui.",
        "en": "The cold-start model has been paused (recent data too unstable) — Aetherix is holding back today.",
    },
    "confidence_below_threshold": {
        "fr": "Confiance insuffisante pour recommander un staffing aujourd'hui — suggestion : maintenir le staffing standard.",
        "en": "Not confident enough to recommend staffing today — suggestion: keep standard staffing.",
    },
    "parser_low_confidence": {
        "fr": "Message non compris avec certitude. Pouvez-vous reformuler le nombre de couverts ?",
        "en": "I'm not sure I understood. Could you restate the number of covers?",
    },
    "data_quality_alert": {
        "fr": "Données incomplètes ce matin (synchronisation PMS ou météo manquante) — recommandation suspendue par prudence.",
        "en": "Incomplete data this morning (PMS sync or weather missing) — recommendation held back as a precaution.",
    },
    "drift_detected_high": {
        "fr": "Les données récentes divergent nettement de l'historique — Aetherix recommande de vérifier les chiffres ce soir.",
        "en": "Recent data diverges sharply from history — Aetherix recommends double-checking tonight's figures.",
    },
    "ood_unsupported_input": {
        "fr": "Aetherix ne peut traiter cette demande pour le moment — merci de répondre en français ou en anglais.",
        "en": "Aetherix can't process this request right now — please reply in French or English.",
    },
}


def messages_for_reason(reason: str) -> LocalizedMessages:
    """Return the FR/EN copy for an abstention reason. Raises KeyError if unknown."""
    m = _MESSAGES[reason]
    return LocalizedMessages(fr=m["fr"], en=m["en"])


def localized_message(reason: str, locale: str | None = DEFAULT_LOCALE) -> str:
    """Resolve a single manager-facing string for `reason` in `locale` (default FR)."""
    return messages_for_reason(reason).get(locale)


# Fail fast at import if the mapping ever drifts from the reason set.
assert set(_MESSAGES) == set(ABSTENTION_REASONS), (
    "abstention_messages out of sync with AbstentionReason"
)

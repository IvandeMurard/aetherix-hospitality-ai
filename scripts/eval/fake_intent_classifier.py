"""Deterministic inbound-intent classifier for CI eval (HOS-208 / EVAL-4).

Analogue of `FakeEmbeddingProvider` (ADR-0002 D11): a deterministic stand-in for
the Haiku parser so the parser eval is reproducible in CI without hitting the
Anthropic API (R4 mitigation). The real-quality signal comes from the nightly
`EVAL_PARSER_BACKEND=real` run, not the PR gate.

Classifies a manager reply into the feedback-loop taxonomy
``accepted | rejected | modified`` with simple, deterministic rules that resolve
the curated golden scenarios correctly (so the pipeline runs green in CI).

Placed under `scripts/eval/` (not `backend/tests/`) because it is an
eval-*runtime* component consumed by `eval_parser.py` in CI — not merely a unit
fixture. (Deviation from the ticket's suggested path, for importability.)
"""
from __future__ import annotations

import re

Intent = str  # "accepted" | "rejected" | "modified"

INTENTS: tuple[str, str, str] = ("accepted", "rejected", "modified")

# A numeric correction or covers/pax keyword ⇒ the manager is changing a number.
_MODIFIED_KEYWORDS = ("covers", "pax", "couvert", "au lieu", "instead", "make it")
# Explicit disagreement markers (word-level for short tokens to avoid substring
# false positives like "no" inside "nous").
_NEG_WORDS = {"non", "no", "nope", "nan"}
_NEG_PHRASES = ("pas d'accord", "won't", "wont", "ignore", "🙄")


class FakeIntentClassifier:
    """Deterministic rule-based classifier (same input → same label, always)."""

    def classify(self, message: str, language: str = "fr") -> Intent:
        low = message.lower()
        if re.search(r"\d", message) or any(k in low for k in _MODIFIED_KEYWORDS):
            return "modified"
        tokens = set(re.findall(r"[a-zà-ÿ']+", low))
        if tokens & _NEG_WORDS or any(p in low or p in message for p in _NEG_PHRASES):
            return "rejected"
        return "accepted"

    # Callable form so eval_parser can treat any backend as `fn(message, lang)`.
    def __call__(self, message: str, language: str = "fr") -> Intent:
        return self.classify(message, language)

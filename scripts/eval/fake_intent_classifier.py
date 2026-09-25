"""Deterministic keyword heuristic for the parser eval's PLUMBING CHECK (HOS-208).

What this is: a stand-in that lets the parser eval pipeline (load → classify →
metrics → report) run in CI with no API call. Its rules were written to resolve
the original ``dev`` golden cases, so its agreement with those labels is
circular by construction and measures nothing about the production parser or
the model. It is never a quality signal and is never frozen as a baseline
(ADR-0007 §15).

Where the real signal lives: ``EVAL_PARSER_BACKEND=real``, which grades the
production path with the model in the loop — opt-in via
``.github/workflows/eval-parser-real.yml``. Until that workflow has run with an
API key, parser model quality is **not measured**.

Frozen: do not tune these rules to the ``heldout`` cases. Doing so would only
re-create the circularity on a larger set.

Classifies a manager reply into ``accepted | rejected | modified``.

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

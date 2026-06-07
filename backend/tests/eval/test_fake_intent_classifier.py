"""HOS-208 (EVAL-4) — FakeIntentClassifier determinism + golden-set correctness."""
from __future__ import annotations

import pytest

from scripts.eval.fake_intent_classifier import INTENTS, FakeIntentClassifier

_C = FakeIntentClassifier()


@pytest.mark.parametrize(
    "message",
    ["ok merci", "non merci", "covers: 80", "👍", "nope, ignore that", "random text"],
)
def test_deterministic_100_runs(message):
    labels = {_C.classify(message) for _ in range(100)}
    assert len(labels) == 1  # same input → same label, always


@pytest.mark.parametrize(
    "message,expected",
    [
        ("ok merci", "accepted"),
        ("sounds good, will do", "accepted"),
        ("👍", "accepted"),
        ("non, pas d'accord avec ça", "rejected"),
        ("no, we won't be doing that tonight", "rejected"),
        ("nope, ignore that", "rejected"),
        ("génial, encore vos chiffres parfaits 🙄", "rejected"),
        ("covers: 80", "modified"),
        ("120 pax tonight", "modified"),
        ("plutôt 4 au lieu de 5 👀", "modified"),
    ],
)
def test_known_labels(message, expected):
    assert _C.classify(message) == expected


@pytest.mark.parametrize("message", ["", "hello there", "???"])
def test_label_always_in_taxonomy(message):
    assert _C.classify(message) in INTENTS

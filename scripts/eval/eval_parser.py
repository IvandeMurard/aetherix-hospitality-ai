"""Inbound-parser accuracy eval — EVAL-4 (HOS-208), ADR-0007 §5.c.

Runs an intent classifier over the `parser_intent` golden scenarios and reports
global accuracy + per-intent precision/recall + a 3×3 confusion matrix.

Backend (env `EVAL_PARSER_BACKEND`):
  - `fake` (CI default) — deterministic `FakeIntentClassifier` (reproducible, no API).
  - `real` (nightly only) — wraps `ReceiptsService.parse_inbound` (Haiku) + maps its
    intents to the eval taxonomy. Not run on PRs (R4).

The pure `compute_parser_metrics` is separated from any classifier so it unit-tests
deterministically.
"""
from __future__ import annotations

import os
from pathlib import Path
from typing import Callable

from .fake_intent_classifier import INTENTS, FakeIntentClassifier
from .loader import DEFAULT_DATASET, load_scenarios

ClassifyFn = Callable[[str, str], str]


def compute_parser_metrics(scenarios: list[dict], classify: ClassifyFn) -> dict:
    """Pure metrics: accuracy, per-intent precision/recall/support, confusion matrix.

    Each scenario's `expected.intent` is the ground truth; `input.message` /
    `input.language` feed the classifier.
    """
    # confusion[true][pred] = count
    confusion: dict[str, dict[str, int]] = {t: {p: 0 for p in INTENTS} for t in INTENTS}
    correct = 0
    total = 0

    for sc in scenarios:
        expected = sc.get("expected", {}).get("intent")
        if expected not in INTENTS:
            continue  # skip non-classification scenarios (e.g. abstention/ood)
        message = sc.get("input", {}).get("message", "")
        language = sc.get("input", {}).get("language", "fr")
        predicted = classify(message, language)
        if predicted not in INTENTS:
            predicted = "accepted"  # defensive — keep the matrix well-formed
        confusion[expected][predicted] += 1
        total += 1
        if predicted == expected:
            correct += 1

    per_intent: dict[str, dict] = {}
    for intent in INTENTS:
        tp = confusion[intent][intent]
        fp = sum(confusion[t][intent] for t in INTENTS if t != intent)
        fn = sum(confusion[intent][p] for p in INTENTS if p != intent)
        support = sum(confusion[intent].values())
        precision = round(tp / (tp + fp), 4) if (tp + fp) else None
        recall = round(tp / (tp + fn), 4) if (tp + fn) else None
        per_intent[intent] = {
            "precision": precision,
            "recall": recall,
            "support": support,
        }

    return {
        "layer": "parser",
        "accuracy": round(correct / total, 4) if total else None,
        "n": total,
        "per_intent": per_intent,
        "confusion_matrix": confusion,
        "backend": os.environ.get("EVAL_PARSER_BACKEND", "fake"),
    }


def _real_classifier() -> ClassifyFn:
    """Nightly-only: wrap parse_inbound (Haiku) + map to the eval taxonomy."""
    import asyncio

    from app.providers.factory import get_llm_provider
    from app.services.receipts import ReceiptsService

    service = ReceiptsService(db=None, llm=get_llm_provider())  # parse_inbound never touches db
    fallback = FakeIntentClassifier()

    def classify(message: str, language: str = "fr") -> str:
        feedback = asyncio.run(service.parse_inbound(message))
        if feedback.intent == "structured_correction":
            return "modified"
        if feedback.intent == "acknowledge":
            return "accepted"
        # free_form has no rejected/accepted distinction → reuse the deterministic
        # heuristic to disambiguate (nightly signal only).
        return fallback.classify(message, language)

    return classify


def get_classifier(backend: str | None = None) -> ClassifyFn:
    backend = backend or os.environ.get("EVAL_PARSER_BACKEND", "fake")
    if backend == "real":
        return _real_classifier()
    return FakeIntentClassifier()


def run(dataset: Path = DEFAULT_DATASET, seed: int = 42) -> dict:
    """Load parser_intent scenarios, classify, compute metrics."""
    scenarios = [
        s for s in load_scenarios(dataset, layer="parser")
        if s.get("category") == "parser_intent"
    ]
    if not scenarios:
        raise SystemExit("[eval_parser] no parser_intent scenarios in dataset")
    return compute_parser_metrics(scenarios, get_classifier())

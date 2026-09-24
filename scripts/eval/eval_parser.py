"""Inbound-parser eval — EVAL-4 (HOS-208), ADR-0007 §5.c, amended §15.

Grades how a manager's WhatsApp reply becomes a recorded feedback outcome
(``accepted | rejected | modified``) and reports accuracy, per-intent
precision/recall and a confusion matrix, split by dataset split (``dev`` = the
original cases, ``heldout`` = adversarial cases never used to tune anything).

Backends (env ``EVAL_PARSER_BACKEND``):

* ``fake`` (CI default) — **pipeline/plumbing check only.** A keyword heuristic
  (`FakeIntentClassifier`) whose rules were written against the ``dev`` cases.
  Its agreement with the labels measures nothing about the production parser or
  the model; the result carries ``quality_signal: false`` and no baseline is
  compared. It proves the eval pipeline runs end to end.
* ``real`` (opt-in: ``.github/workflows/eval-parser-real.yml``) — grades the
  **production path**, model included, with no fallback inside it:
  ``action_logger.parse_action`` (exact ``accept``/``reject``) →
  ``ReceiptsService.parse_inbound`` (ack regex → covers regex → model) →
  ``receipts.outcome_for_feedback`` — the same three calls, in the same order,
  as ``api/routes/twilio_inbound.py``. The model is the primary provider only
  (no silent Gemini failover). A model error or an answer outside the taxonomy
  is a typed ``error`` prediction and counts as a miss — never a guess.
  Without ``ANTHROPIC_API_KEY`` the run raises `ParserEvalNotMeasured` and the
  runner exits 2 (ERROR): *not measured*, never PASS.

Both backends also report the **production-path ceiling**: the best accuracy the
production path can reach whatever the model answers, computed by running the
production code with a stub model (no API call). A reply that reaches the model
can only end up ``modified`` or ``not_recorded``, so the ceiling is a property of
the code, not of the model.

`compute_parser_metrics` is pure and unit-tested deterministically.
"""
from __future__ import annotations

import asyncio
import os
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

from .fake_intent_classifier import INTENTS, FakeIntentClassifier
from .loader import DEFAULT_DATASET, load_scenarios

# `backend/` on the path so the production modules import (same as eval_guardrail).
_BACKEND = Path(__file__).resolve().parent.parent.parent / "backend"
if str(_BACKEND) not in sys.path:
    sys.path.insert(0, str(_BACKEND))

# Predictions can fall outside the 3 ground-truth intents:
#   not_recorded — production writes no outcome (acknowledge path)
#   error        — model call failed or answered outside the taxonomy (real only)
PREDICTED_LABELS: tuple[str, ...] = (*INTENTS, "not_recorded", "error")

# FAILURE_THRESHOLDS.md — "Inbound parser": accuracy < 90% or per-intent
# precision < 0.85 is unacceptable. Applied to the real backend only.
ACCURACY_MIN = 0.90
PRECISION_MIN = 0.85

# Outcomes a reply can still reach once it is handed to the model: the route
# records nothing for `acknowledge` and "modified" for every other intent.
_MODEL_REACHABLE = frozenset({"modified", "not_recorded"})


class ParserEvalNotMeasured(RuntimeError):
    """The real backend could not run (e.g. no API key). Exit 2 — not measured."""


@dataclass(frozen=True)
class Prediction:
    label: str                 # one of PREDICTED_LABELS
    stage: str                 # which step decided (action_keyword, ack_regex, …)
    error: str | None = None   # typed reason when label == "error"


PredictFn = Callable[[str, str], Prediction]


def _split(scenario: dict) -> str:
    return scenario.get("split", "dev")


def compute_parser_metrics(
    scenarios: list[dict], predict: Callable[[str, str], Prediction | str]
) -> dict:
    """Pure metrics: accuracy, per-intent precision/recall/support, confusion
    matrix (rows = expected intent, cols = PREDICTED_LABELS), per-split accuracy
    and per-case detail.

    `predict` may return a bare label (legacy classifiers) or a `Prediction`.
    An unknown label is recorded as ``error`` — never coerced to an intent.
    """
    confusion: dict[str, dict[str, int]] = {t: {p: 0 for p in PREDICTED_LABELS} for t in INTENTS}
    split_totals: dict[str, list[int]] = {}
    stages: dict[str, int] = {}
    cases: list[dict] = []
    correct = total = 0

    for sc in scenarios:
        expected = sc.get("expected", {}).get("intent")
        if expected not in INTENTS:
            continue  # skip non-classification scenarios (e.g. abstention/ood)
        message = sc.get("input", {}).get("message", "")
        language = sc.get("input", {}).get("language", "fr")
        raw = predict(message, language)
        pred = raw if isinstance(raw, Prediction) else Prediction(label=raw, stage="classifier")
        if pred.label not in PREDICTED_LABELS:
            pred = Prediction(label="error", stage=pred.stage, error=f"unknown_label:{pred.label}")

        confusion[expected][pred.label] += 1
        hit = pred.label == expected
        total += 1
        correct += hit
        split = _split(sc)
        split_totals.setdefault(split, [0, 0])
        split_totals[split][0] += hit
        split_totals[split][1] += 1
        stages[pred.stage] = stages.get(pred.stage, 0) + 1
        cases.append({
            "id": sc.get("id"),
            "split": split,
            "expected": expected,
            "predicted": pred.label,
            "stage": pred.stage,
            "error": pred.error,
            "ok": hit,
        })

    per_intent: dict[str, dict] = {}
    for intent in INTENTS:
        tp = confusion[intent][intent]
        fp = sum(confusion[t][intent] for t in INTENTS if t != intent)
        fn = sum(confusion[intent][p] for p in PREDICTED_LABELS if p != intent)
        per_intent[intent] = {
            "precision": round(tp / (tp + fp), 4) if (tp + fp) else None,
            "recall": round(tp / (tp + fn), 4) if (tp + fn) else None,
            "support": sum(confusion[intent].values()),
        }

    return {
        "layer": "parser",
        "accuracy": round(correct / total, 4) if total else None,
        "n": total,
        "per_split": {
            s: {"accuracy": round(c / n, 4) if n else None, "n": n}
            for s, (c, n) in sorted(split_totals.items())
        },
        "per_intent": per_intent,
        "confusion_matrix": confusion,
        "n_errors": sum(1 for c in cases if c["predicted"] == "error"),
        "decided_by": dict(sorted(stages.items())),
        "cases": cases,
    }


def threshold_breaches(result: dict) -> list[str]:
    """FAILURE_THRESHOLDS.md contract, applied to a real-backend result.

    An intent the path never predicts has no precision: that is a breach (the
    contract cannot be shown to hold), not a pass.
    """
    breaches: list[str] = []
    acc = result.get("accuracy")
    if acc is None or acc < ACCURACY_MIN:
        breaches.append(f"accuracy {acc} < {ACCURACY_MIN}")
    for intent, m in result.get("per_intent", {}).items():
        p = m.get("precision")
        if p is None:
            breaches.append(f"{intent}: never predicted (precision undefined)")
        elif p < PRECISION_MIN:
            breaches.append(f"{intent}: precision {p} < {PRECISION_MIN}")
    return breaches


# ---------------------------------------------------------------------------
# Production path
# ---------------------------------------------------------------------------

class _RecordingLLM:
    """Pass-through wrapper: counts calls and records the sampling settings the
    production code actually used. Never alters a request or a response."""

    def __init__(self, inner) -> None:
        self._inner = inner
        self.calls = 0
        self.temperatures: set[float] = set()
        self.tiers: set[str] = set()

    async def complete(self, messages, max_tokens=500, temperature=0.3, system=None, tier="reasoning"):
        self.calls += 1
        self.temperatures.add(temperature)
        self.tiers.add(tier)
        return await self._inner.complete(
            messages=messages, max_tokens=max_tokens, temperature=temperature,
            system=system, tier=tier,
        )

    @property
    def model_id(self) -> str:
        return getattr(self._inner, "model_id", "unknown")


class _StubLLM:
    """No-API stand-in used only to find which replies reach the model."""

    model_id = "stub/no-call"

    async def complete(self, *args, **kwargs) -> str:
        raise RuntimeError("stub model — reachability probe only")


async def _production_prediction(service, message: str) -> Prediction:
    """The route's decision sequence (`api/routes/twilio_inbound.py`), unchanged."""
    from app.schemas.webhook import ActionType
    from app.services.action_logger import parse_action
    from app.services.receipts import outcome_for_feedback

    action = parse_action(message)
    if action == ActionType.accept:
        return Prediction("accepted", "action_keyword")
    if action == ActionType.reject:
        return Prediction("rejected", "action_keyword")

    feedback = await service.parse_inbound(message)
    if feedback.source in ("llm_error", "llm_unmappable"):
        # Production would record "modified" here; the eval refuses to count a
        # fallback as the model's answer.
        return Prediction("error", feedback.source, error=feedback.source)
    outcome = outcome_for_feedback(feedback)
    return Prediction(outcome or "not_recorded", feedback.source)


def _run_production(scenarios: list[dict], llm) -> list[Prediction]:
    """Run the production path over every classification scenario in one loop."""
    from app.services.receipts import ReceiptsService

    service = ReceiptsService(db=None, llm=llm)  # parse_inbound never touches db
    messages = [
        s.get("input", {}).get("message", "")
        for s in scenarios
        if s.get("expected", {}).get("intent") in INTENTS
    ]

    async def _all() -> list[Prediction]:
        return [await _production_prediction(service, m) for m in messages]

    return asyncio.run(_all())


def _replay(predictions: list[Prediction]) -> PredictFn:
    it = iter(predictions)
    return lambda message, language="fr": next(it)


def production_path_ceiling(scenarios: list[dict]) -> dict:
    """Best accuracy reachable by the production path, whatever the model says.

    Runs the production code with `_StubLLM`. A reply decided before the model
    (keyword / regex) has one possible outcome; a reply that reaches the model
    can only become ``modified`` or ``not_recorded``. No API call is made.
    """
    import logging

    stub = _StubLLM()
    # The stub raising is expected; keep parse_inbound's exception log quiet.
    receipts_logger = logging.getLogger("app.services.receipts")
    previous = receipts_logger.level
    receipts_logger.setLevel(logging.CRITICAL)
    try:
        preds = _run_production(scenarios, stub)
    finally:
        receipts_logger.setLevel(previous)

    reachable_hits = 0
    reaches_model = 0
    per_intent_reachable = {i: 0 for i in INTENTS}
    labelled = [s for s in scenarios if s.get("expected", {}).get("intent") in INTENTS]
    for sc, pred in zip(labelled, preds):
        expected = sc["expected"]["intent"]
        if pred.stage.startswith("llm"):
            reaches_model += 1
            ok = expected in _MODEL_REACHABLE
        else:
            ok = pred.label == expected
        reachable_hits += ok
        per_intent_reachable[expected] += ok
    n = len(labelled)
    return {
        "max_accuracy": round(reachable_hits / n, 4) if n else None,
        "n": n,
        "reaches_model": reaches_model,
        "decided_before_model": n - reaches_model,
        "max_recall": {
            i: (round(per_intent_reachable[i] / c, 4) if (c := sum(
                1 for s in labelled if s["expected"]["intent"] == i)) else None)
            for i in INTENTS
        },
    }


def _real_backend(scenarios: list[dict]) -> tuple[list[Prediction], dict]:
    key = os.environ.get("ANTHROPIC_API_KEY", "")
    if not key:
        raise ParserEvalNotMeasured(
            "ANTHROPIC_API_KEY is not set — the real parser eval was NOT MEASURED."
        )
    from app.providers.factory import get_llm_provider

    # Fresh provider per run: the cached one holds an HTTP client bound to the
    # event loop of the previous run. Primary only: a Gemini failover would silently change the model under test.
    build = getattr(get_llm_provider, "__wrapped__", get_llm_provider)  # bypass lru_cache
    provider = build()
    primary = getattr(provider, "primary", provider)
    llm = _RecordingLLM(primary)
    preds = _run_production(scenarios, llm)
    meta = {
        "provider": llm.model_id,
        "fast_model": getattr(primary, "_fast_model", None),
        "tiers": sorted(llm.tiers),
        "temperatures": sorted(llm.temperatures),
        "llm_calls": llm.calls,
    }
    return preds, meta


def run(dataset: Path = DEFAULT_DATASET, seed: int = 42, runs: int = 1) -> dict:
    """Load parser_intent scenarios and evaluate them with the selected backend.

    `runs` > 1 (real backend) repeats the whole evaluation to measure run-to-run
    variance — the canary required before freezing a real baseline.
    """
    backend = os.environ.get("EVAL_PARSER_BACKEND", "fake")
    scenarios = [
        s for s in load_scenarios(dataset, layer="parser")
        if s.get("category") == "parser_intent"
    ]
    if not scenarios:
        raise SystemExit("[eval_parser] no parser_intent scenarios in dataset")

    ceiling = production_path_ceiling(scenarios)

    if backend == "real":
        runs_out: list[dict] = []
        meta: dict = {}
        for _ in range(max(1, runs)):
            preds, meta = _real_backend(scenarios)
            runs_out.append(compute_parser_metrics(scenarios, _replay(preds)))
        result = runs_out[0]
        accuracies = [r["accuracy"] for r in runs_out]
        signatures = [[c["predicted"] for c in r["cases"]] for r in runs_out]
        result.update({
            "backend": "real",
            "measures": "production_path_model_included",
            "quality_signal": True,
            "model": meta,
            "canary": {
                "runs": len(runs_out),
                "accuracies": accuracies,
                "variance_pp": round((max(accuracies) - min(accuracies)) * 100, 2),
                "identical_predictions": all(s == signatures[0] for s in signatures),
            },
            "thresholds": {
                "accuracy_min": ACCURACY_MIN,
                "precision_min": PRECISION_MIN,
                "breaches": threshold_breaches(result),
            },
        })
    elif backend == "fake":
        fake = FakeIntentClassifier()
        result = compute_parser_metrics(
            scenarios, lambda m, lang="fr": Prediction(fake(m, lang), "fake_heuristic")
        )
        result.update({
            "backend": "fake",
            "measures": "pipeline_plumbing_only",
            "quality_signal": False,
        })
    else:
        raise ParserEvalNotMeasured(f"unknown EVAL_PARSER_BACKEND={backend!r}")

    result["production_path_ceiling"] = ceiling
    return result

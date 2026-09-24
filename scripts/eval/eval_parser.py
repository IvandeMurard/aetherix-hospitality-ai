"""Inbound-parser eval — EVAL-4 (HOS-208), ADR-0007 §5.c, amended §15 and §16.

Grades how a manager's WhatsApp reply becomes a recorded **decision**
(``accepted | rejected | modified``), a **confirmation request** (nothing
written until the manager confirms, Décision #6), or nothing.

Since §16 (Décision #38) most short replies are decided **before** the model,
deterministically: exact FR/EN keywords, ambiguous keyword forms (→ confirmation),
bare acknowledgements (rule (b)), covers corrections. Those are code, unit-tested
form by form; the eval reports them as a **deterministic block** (a regression
check of the routing, not a quality figure). The **model is graded on the
free-text path only**: replies that reach it.

Backends (env ``EVAL_PARSER_BACKEND``):

* ``fake`` (CI default) — **pipeline/plumbing check only.** A keyword heuristic
  (`FakeIntentClassifier`) whose rules were written against the ``dev`` cases.
  ``quality_signal: false``, no baseline compared. The deterministic block and the
  ceiling are still computed on the production code (no model involved).
* ``real`` (opt-in: ``.github/workflows/eval-parser-real.yml``) — grades the
  **production path**, model included, no fallback:
  ``action_logger.parse_action`` → ``ReceiptsService.parse_inbound`` →
  ``receipts.resolve_feedback``, the same calls as ``api/routes/twilio_inbound.py``.
  Primary provider only. A model error or a schema failure is a typed ``error``.
  Without ``ANTHROPIC_API_KEY`` the run raises `ParserEvalNotMeasured` → exit 2.

Model-graded metrics (real backend, cases that reach the model):

* ``accuracy`` — the decision the path lands on (written, or proposed for
  confirmation) equals the label. ``none`` / error = miss.
* ``auto_write`` — decisions written **without** confirmation (confidence ≥
  ``DECISION_CONFIDENCE_THRESHOLD``) and their precision: the harmful error.
* ``confirmation_rate`` — share sent to confirmation (manager interruption cost).
* ``confirmation_trigger`` — ``parser_confirmation`` cases (genuinely two-reading
  replies): any auto-write is a breach; a confirmation or no decision passes.

Evaluation context: every case is graded as a reply to exactly one pending
recommendation, inside the response window (``EVAL_CONTEXT``). Rule (b) then
records ``accepted`` for a bare acknowledgement; its other branches are unit-tested.

`compute_parser_metrics` is pure and unit-tested deterministically.
"""
from __future__ import annotations

import asyncio
import os
import sys
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Callable

from .fake_intent_classifier import INTENTS, FakeIntentClassifier
from .loader import DEFAULT_DATASET, load_scenarios

# `backend/` on the path so the production modules import (same as eval_guardrail).
_BACKEND = Path(__file__).resolve().parent.parent.parent / "backend"
if str(_BACKEND) not in sys.path:
    sys.path.insert(0, str(_BACKEND))

# Predictions can fall outside the 3 decisions:
#   not_recorded — the path writes no decision and asks nothing
#   error        — model call failed or its answer failed the schema (real only)
PREDICTED_LABELS: tuple[str, ...] = (*INTENTS, "not_recorded", "error")

# FAILURE_THRESHOLDS.md — "Inbound parser". Applied to the real backend only.
ACCURACY_MIN = 0.90
PRECISION_MIN = 0.85

_MODEL_STAGES = ("llm", "llm_error", "llm_unmappable")

_NOW = datetime(2026, 9, 24, 12, 0, tzinfo=timezone.utc)


def _eval_context():
    from app.services.manager_decision import PendingContext

    # One pending recommendation, dispatched an hour ago (inside the window),
    # proposing a change (add/remove staff — the usual case). The golden
    # replies answer such a recommendation (ADR-0007 §17.8).
    return PendingContext(pending_count=1, latest_dispatched_at=_NOW - timedelta(hours=1), now=_NOW,
                          latest_proposes_change=True)


class ParserEvalNotMeasured(RuntimeError):
    """The real backend could not run (e.g. no API key). Exit 2 — not measured."""


@dataclass(frozen=True)
class Prediction:
    label: str                 # decision landed on (written or proposed), or not_recorded / error
    stage: str                 # which step decided (keyword, bare_ack, covers_regex, llm, …)
    error: str | None = None   # typed reason when label == "error"
    action: str = "record"     # record | confirm | none | error


PredictFn = Callable[[str, str], Prediction]


def _split(scenario: dict) -> str:
    return scenario.get("split", "dev")


def expected_decision(scenario: dict) -> str | None:
    exp = scenario.get("expected", {})
    return exp.get("decision", exp.get("intent"))


def _is_labelled(scenario: dict) -> bool:
    return scenario.get("category") == "parser_intent" and expected_decision(scenario) in INTENTS


def compute_parser_metrics(
    scenarios: list[dict], predict: Callable[[str, str], Prediction | str]
) -> dict:
    """Pure metrics: accuracy, per-decision precision/recall/support, confusion
    matrix (rows = expected decision, cols = PREDICTED_LABELS), per-split accuracy,
    auto-write precision and confirmation rate, and per-case detail.

    `predict` may return a bare label (legacy classifiers) or a `Prediction`.
    An unknown label is recorded as ``error`` — never coerced to a decision.
    """
    confusion: dict[str, dict[str, int]] = {t: {p: 0 for p in PREDICTED_LABELS} for t in INTENTS}
    split_totals: dict[str, list[int]] = {}
    stages: dict[str, int] = {}
    cases: list[dict] = []
    correct = total = 0
    written: dict[str, list[int]] = {t: [0, 0] for t in INTENTS}  # decision → [correct, n]
    confirmations = 0

    for sc in scenarios:
        expected = expected_decision(sc)
        if expected not in INTENTS or sc.get("category", "parser_intent") != "parser_intent":
            continue  # skip non-classification scenarios (abstention/ood, confirmation set)
        message = sc.get("input", {}).get("message", "")
        language = sc.get("input", {}).get("language", "fr")
        raw = predict(message, language)
        pred = raw if isinstance(raw, Prediction) else Prediction(label=raw, stage="classifier")
        if pred.label not in PREDICTED_LABELS:
            pred = Prediction(label="error", stage=pred.stage, error=f"unknown_label:{pred.label}",
                              action="error")

        confusion[expected][pred.label] += 1
        hit = pred.label == expected
        total += 1
        correct += hit
        if pred.action == "record" and pred.label in INTENTS:
            written[pred.label][0] += hit
            written[pred.label][1] += 1
        if pred.action == "confirm":
            confirmations += 1
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
            "action": pred.action,
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

    n_written = sum(n for _, n in written.values())
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
        "auto_write": {
            "n_written": n_written,
            "precision": (round(sum(c for c, _ in written.values()) / n_written, 4)
                          if n_written else None),
            "per_decision_precision": {
                d: (round(c / n, 4) if n else None) for d, (c, n) in written.items()
            },
        },
        "confirmation_rate": round(confirmations / total, 4) if total else None,
        "n_errors": sum(1 for c in cases if c["predicted"] == "error"),
        "decided_by": dict(sorted(stages.items())),
        "cases": cases,
    }


def threshold_breaches(result: dict) -> list[str]:
    """FAILURE_THRESHOLDS.md contract, applied to a real-backend result.

    * decision accuracy on the model-graded cases >= ACCURACY_MIN;
    * per-decision precision >= PRECISION_MIN — a decision the path never lands
      on has no precision: breach (the contract cannot be shown to hold);
    * per-decision precision of AUTO-WRITTEN decisions >= PRECISION_MIN (a
      decision never auto-written is safe: everything was confirmed);
    * confirmation trigger: zero auto-writes on ``parser_confirmation`` cases.
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
    for d, p in ((result.get("auto_write") or {}).get("per_decision_precision") or {}).items():
        if p is not None and p < PRECISION_MIN:
            breaches.append(f"{d}: auto-write precision {p} < {PRECISION_MIN}")
    trig = result.get("confirmation_trigger") or {}
    if trig.get("auto_written"):
        breaches.append(
            f"confirmation trigger: {trig['auto_written']} low-confidence case(s) written "
            "without confirmation"
        )
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
    """The route's decision sequence (`api/routes/twilio_inbound.py`), in order:
    exact keyword → bare ack / covers regex / model → `resolve_feedback`."""
    from app.schemas.webhook import ActionType
    from app.services.action_logger import parse_action
    from app.services.manager_decision import match_keyword, resolve_keyword
    from app.services.receipts import resolve_feedback

    ctx = _eval_context()
    action = parse_action(message)
    if action != ActionType.unknown:
        res = resolve_keyword(match_keyword(message), ctx)
        stage = "keyword_ambiguous" if res.action == "confirm" else "keyword"
        return Prediction(res.decision or "not_recorded", stage, action=res.action)

    feedback = await service.parse_inbound(message)
    if feedback.source in ("llm_error", "llm_unmappable"):
        return Prediction("error", feedback.source, error=feedback.source, action="error")
    res = resolve_feedback(feedback, ctx)
    stage = {"ack_regex": "bare_ack"}.get(feedback.source, feedback.source)
    if res.action == "none":
        return Prediction("not_recorded", stage, action="none")
    return Prediction(res.decision, stage, action=res.action)


def _run_production(scenarios: list[dict], llm) -> list[Prediction]:
    """Run the production path over the given scenarios' messages, in order."""
    from app.services.receipts import ReceiptsService

    service = ReceiptsService(db=None, llm=llm)  # parse_inbound never touches db
    messages = [s.get("input", {}).get("message", "") for s in scenarios]

    async def _all() -> list[Prediction]:
        return [await _production_prediction(service, m) for m in messages]

    return asyncio.run(_all())


def _replay(predictions: list[Prediction]) -> PredictFn:
    it = iter(predictions)
    return lambda message, language="fr": next(it)


def _quiet_stub_run(scenarios: list[dict]) -> list[Prediction]:
    import logging

    # The stub raising is expected; keep parse_inbound's exception log quiet.
    receipts_logger = logging.getLogger("app.services.receipts")
    previous = receipts_logger.level
    receipts_logger.setLevel(logging.CRITICAL)
    try:
        return _run_production(scenarios, _StubLLM())
    finally:
        receipts_logger.setLevel(previous)


def deterministic_block(scenarios: list[dict]) -> dict:
    """Cases decided before the model (keyword, ambiguous keyword, bare ack,
    covers regex), run on the production code with no API call. A code check:
    each disagreement is a routing regression or a label to revisit."""
    labelled = [s for s in scenarios if _is_labelled(s)]
    preds = _quiet_stub_run(labelled)
    rows = []
    for sc, p in zip(labelled, preds):
        if p.stage in _MODEL_STAGES:
            continue
        rows.append({"id": sc.get("id"), "expected": expected_decision(sc), "predicted": p.label,
                     "action": p.action, "stage": p.stage,
                     "expected_path": sc.get("expected", {}).get("path"),
                     "ok": p.label == expected_decision(sc)})
    by_stage: dict[str, int] = {}
    for r in rows:
        by_stage[r["stage"]] = by_stage.get(r["stage"], 0) + 1
    return {
        "n": len(rows),
        "agree": sum(r["ok"] for r in rows),
        "by_stage": dict(sorted(by_stage.items())),
        "confirmations": sum(r["action"] == "confirm" for r in rows),
        "disagreements": [r for r in rows if not r["ok"]],
        "cases": rows,
    }


def model_graded_ids(scenarios: list[dict]) -> set[str]:
    labelled = [s for s in scenarios if _is_labelled(s)]
    preds = _quiet_stub_run(labelled)
    return {sc.get("id") for sc, p in zip(labelled, preds) if p.stage in _MODEL_STAGES}


def production_path_ceiling(scenarios: list[dict]) -> dict:
    """Best accuracy reachable by the production path, whatever the model says.

    Since §16 the model can land on any decision, so a reply that reaches it is
    reachable; a reply decided before it has one possible outcome. No API call.
    """
    labelled = [s for s in scenarios if _is_labelled(s)]
    preds = _quiet_stub_run(labelled)
    reachable_hits = reaches_model = 0
    per_intent_reachable = {i: 0 for i in INTENTS}
    for sc, pred in zip(labelled, preds):
        expected = expected_decision(sc)
        if pred.stage in _MODEL_STAGES:
            reaches_model += 1
            ok = True
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
                1 for s in labelled if expected_decision(s) == i)) else None)
            for i in INTENTS
        },
    }


def confirmation_trigger(scenarios: list[dict], preds: list[Prediction]) -> dict:
    """``parser_confirmation`` cases: a write without confirmation is a failure;
    a confirmation or no decision passes."""
    rows = []
    for sc, p in zip(scenarios, preds):
        rows.append({"id": sc.get("id"), "action": p.action, "predicted": p.label,
                     "stage": p.stage, "ok": p.action != "record"})
    return {
        "n": len(rows),
        "auto_written": sum(not r["ok"] for r in rows),
        "confirmed_or_none": sum(r["ok"] for r in rows),
        "cases": rows,
    }


def _real_llm():
    key = os.environ.get("ANTHROPIC_API_KEY", "")
    if not key:
        raise ParserEvalNotMeasured(
            "ANTHROPIC_API_KEY is not set — the real parser eval was NOT MEASURED."
        )
    from app.providers.factory import get_llm_provider

    # Fresh provider per run: the cached one holds an HTTP client bound to the
    # event loop of the previous run. Primary only: a Gemini failover would
    # silently change the model under test.
    build = getattr(get_llm_provider, "__wrapped__", get_llm_provider)  # bypass lru_cache
    provider = build()
    primary = getattr(provider, "primary", provider)
    return _RecordingLLM(primary), primary


def run(dataset: Path = DEFAULT_DATASET, seed: int = 42, runs: int = 1) -> dict:
    """Load parser scenarios and evaluate them with the selected backend.

    `runs` > 1 (real backend) repeats the whole evaluation to measure run-to-run
    variance — the canary required before freezing a real baseline.
    """
    backend = os.environ.get("EVAL_PARSER_BACKEND", "fake")
    all_parser = load_scenarios(dataset, layer="parser")
    scenarios = [s for s in all_parser if s.get("category") == "parser_intent"]
    trigger_set = [s for s in all_parser if s.get("category") == "parser_confirmation"]
    if not scenarios:
        raise SystemExit("[eval_parser] no parser_intent scenarios in dataset")

    ceiling = production_path_ceiling(scenarios)
    deterministic = deterministic_block(scenarios)

    if backend == "real":
        graded_ids = model_graded_ids(scenarios)
        graded = [s for s in scenarios if s.get("id") in graded_ids]
        runs_out: list[dict] = []
        meta: dict = {}
        for _ in range(max(1, runs)):
            llm, primary = _real_llm()
            preds = _run_production(graded + trigger_set, llm)
            graded_preds, trigger_preds = preds[:len(graded)], preds[len(graded):]
            r = compute_parser_metrics(graded, _replay(graded_preds))
            r["confirmation_trigger"] = confirmation_trigger(trigger_set, trigger_preds)
            runs_out.append(r)
            meta = {
                "provider": llm.model_id,
                "fast_model": getattr(primary, "_fast_model", None),
                "tiers": sorted(llm.tiers),
                "temperatures": sorted(llm.temperatures),
                "llm_calls": llm.calls,
            }
        result = runs_out[0]
        accuracies = [r["accuracy"] for r in runs_out]
        signatures = [
            [(c["predicted"], c["action"]) for c in r["cases"]]
            + [(c["predicted"], c["action"]) for c in r["confirmation_trigger"]["cases"]]
            for r in runs_out
        ]
        result.update({
            "backend": "real",
            "measures": "free_text_path_model_included",
            "quality_signal": True,
            "model": meta,
            "canary": {
                "runs": len(runs_out),
                "accuracies": accuracies,
                "variance_pp": round((max(accuracies) - min(accuracies)) * 100, 2)
                if None not in accuracies else None,
                "identical_predictions": all(s == signatures[0] for s in signatures),
            },
        })
        result["thresholds"] = {
            "accuracy_min": ACCURACY_MIN,
            "precision_min": PRECISION_MIN,
            "breaches": threshold_breaches(result),
        }
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
    result["deterministic"] = {k: v for k, v in deterministic.items() if k != "cases"}
    result["n_confirmation_trigger_cases"] = len(trigger_set)
    return result

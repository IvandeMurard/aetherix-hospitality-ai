"""Inbound-parser accuracy eval — EVAL-4 (HOS-208), ADR-0007 §5.c.

Runs an intent classifier over the `parser_intent` golden scenarios and reports
global accuracy + per-intent precision/recall + a 3×3 confusion matrix.

Backend (env `EVAL_PARSER_BACKEND`):
  - `fake` (CI default) — deterministic `FakeIntentClassifier` (reproducible, no API).
  - `real` — runs `ReceiptsService.parse_inbound` against ONE pinned provider/model
    (HOS-337, Décision #35 D3). Never on PRs: it costs API calls and needs keys.

`real` requires `EVAL_PARSER_TARGET=<provider>:<exact model id>`, e.g.
`claude:claude-haiku-4-5-20251001` or `gemini:gemini-2.0-flash`. The model is an
exact identifier, not a tier: a run must be reproducible, and a remapped tier
would silently change what is measured. The target provider is called directly,
never through `FallbackLLMProvider` — a failover mid-run would mix two models
into one score.

`parse_inbound` only reaches the LLM on its third pass (two regex passes come
first), and a `free_form` answer is disambiguated by the deterministic
heuristic. So end-to-end accuracy mostly measures the pipeline, not the model.
Each `real` run therefore records who decided each case (`decided_by`) and the
accuracy on the cases the LLM actually decided — that subset is the only part
of the score that can differ between two providers.

The pure `compute_parser_metrics` is separated from any classifier so it unit-tests
deterministically.
"""
from __future__ import annotations

import hashlib
import json
import logging
import os
import sys
from pathlib import Path
from typing import Callable

from .fake_intent_classifier import INTENTS, FakeIntentClassifier
from .loader import DEFAULT_DATASET, load_scenarios

ClassifyFn = Callable[[str, str], str]

TARGET_ENV = "EVAL_PARSER_TARGET"
PROVIDERS = ("claude", "gemini")

# Who decided a case in a `real` run.
SOURCE_REGEX = "regex"  # pass 1/2 of parse_inbound — the LLM was never called
SOURCE_LLM = "llm"  # the LLM returned an intent that maps directly
SOURCE_LLM_FREE_FORM = "llm_free_form_heuristic"  # LLM said free_form → heuristic
SOURCE_LLM_FAILED = "llm_failed"  # API error or unparseable output → default
SOURCES = (SOURCE_REGEX, SOURCE_LLM, SOURCE_LLM_FREE_FORM, SOURCE_LLM_FAILED)

_BACKEND = Path(__file__).resolve().parent.parent.parent / "backend"


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


def parse_target(spec: str) -> tuple[str, str]:
    """`"claude:claude-haiku-4-5-20251001"` → `("claude", "claude-haiku-4-5-20251001")`."""
    provider, sep, model = spec.strip().partition(":")
    if not sep or provider not in PROVIDERS or not model:
        raise SystemExit(
            f"[eval_parser] invalid {TARGET_ENV}={spec!r} — expected "
            f"<provider>:<exact model id> with provider in {PROVIDERS}"
        )
    return provider, model


def dataset_version(scenarios: list[dict]) -> str:
    """Content hash of the scenarios a run scored (12 hex chars).

    Stand-in for the dataset content version of HOS-339: a baseline is only
    comparable to a run over the exact same cases, so any edit to them must
    change the key the baseline is stored under.
    """
    canonical = json.dumps(
        sorted(scenarios, key=lambda s: s.get("id", "")),
        sort_keys=True,
        ensure_ascii=False,
    )
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()[:12]


class _CountingProvider:
    """Wraps the pinned provider to count calls, so each case knows whether the
    LLM was reached at all (parse_inbound does not say which pass decided)."""

    def __init__(self, inner) -> None:
        self._inner = inner
        self.calls = 0

    async def complete(self, **kwargs) -> str:
        self.calls += 1
        return await self._inner.complete(**kwargs)

    @property
    def model_id(self) -> str:
        return self._inner.model_id


class _FailureCounter(logging.Handler):
    """Counts parse_inbound's own "classifier failed" log — it covers both an
    API error and an unparseable answer, which parse_inbound swallows."""

    def __init__(self) -> None:
        super().__init__(level=logging.ERROR)
        self.failures = 0

    def emit(self, record: logging.LogRecord) -> None:
        if "classifier failed" in record.getMessage():
            self.failures += 1


def _build_provider(provider: str, model: str):
    if str(_BACKEND) not in sys.path:
        sys.path.insert(0, str(_BACKEND))
    key_env = {"claude": "ANTHROPIC_API_KEY", "gemini": "GEMINI_API_KEY"}[provider]
    key = os.environ.get(key_env, "")
    if not key:
        raise SystemExit(f"[eval_parser] {key_env} not set — cannot run target {provider}:{model}")
    # Both tiers pinned to the same exact model: whatever tier parse_inbound
    # asks for, this run measures `model` and nothing else.
    if provider == "claude":
        from app.providers.claude_provider import ClaudeProvider

        return ClaudeProvider(api_key=key, model=model, fast_model=model)
    from app.providers.gemini_provider import GeminiProvider

    return GeminiProvider(api_key=key, model=model, fast_model=model)


class RealClassifier:
    """`parse_inbound` on one pinned provider, recording who decided each case."""

    def __init__(self, target: str) -> None:
        import asyncio

        provider, model = parse_target(target)
        self.target = f"{provider}:{model}"
        self._provider = _CountingProvider(_build_provider(provider, model))

        from app.services.receipts import ReceiptsService

        self._service = ReceiptsService(db=None, llm=self._provider)  # parse_inbound never touches db
        self._heuristic = FakeIntentClassifier()
        self._failures = _FailureCounter()
        logging.getLogger("app.services.receipts").addHandler(self._failures)
        # One loop for the whole run: the SDK clients keep connections bound to it.
        self._loop = asyncio.new_event_loop()
        self.log: list[dict] = []

    def __call__(self, message: str, language: str = "fr") -> str:
        return self.classify(message, language)

    def classify(self, message: str, language: str = "fr") -> str:
        calls, failures = self._provider.calls, self._failures.failures
        feedback = self._loop.run_until_complete(self._service.parse_inbound(message))
        reached_llm = self._provider.calls > calls
        failed = self._failures.failures > failures

        if feedback.intent == "structured_correction":
            predicted = "modified"
        elif feedback.intent == "acknowledge":
            predicted = "accepted"
        else:
            # free_form has no rejected/accepted distinction → the deterministic
            # heuristic disambiguates.
            predicted = self._heuristic.classify(message, language)

        if not reached_llm:
            source = SOURCE_REGEX
        elif failed:
            source = SOURCE_LLM_FAILED
        elif feedback.intent == "free_form":
            source = SOURCE_LLM_FREE_FORM
        else:
            source = SOURCE_LLM
        self.log.append({"message": message, "source": source, "predicted": predicted})
        return predicted


def decision_breakdown(scenarios: list[dict], log: list[dict]) -> dict:
    """Per-source counts and accuracy, joining the classifier log to ground truth.

    `accuracy_llm_decided` is the comparable number between two providers: it
    only covers cases where the LLM's own answer set the prediction.
    `llm_failure_rate` is the other one: a failed call falls back to free_form,
    the heuristic then answers, and accuracy does not move.
    """
    expected_by_message = {
        sc.get("input", {}).get("message", ""): sc.get("expected", {}).get("intent")
        for sc in scenarios
        if sc.get("expected", {}).get("intent") in INTENTS
    }
    counts = {s: 0 for s in SOURCES}
    correct = {s: 0 for s in SOURCES}
    for entry in log:
        src = entry["source"]
        counts[src] += 1
        if entry["predicted"] == expected_by_message.get(entry["message"]):
            correct[src] += 1
    llm_n = counts[SOURCE_LLM]
    reached = counts[SOURCE_LLM] + counts[SOURCE_LLM_FREE_FORM] + counts[SOURCE_LLM_FAILED]
    return {
        "decided_by": counts,
        "accuracy_by_source": {
            s: round(correct[s] / counts[s], 4) if counts[s] else None for s in SOURCES
        },
        "accuracy_llm_decided": round(correct[SOURCE_LLM] / llm_n, 4) if llm_n else None,
        "llm_decided_n": llm_n,
        # A failure is rescued by the heuristic, so it never lowers accuracy:
        # it has to be read as a rate of its own.
        "llm_failure_rate": round(counts[SOURCE_LLM_FAILED] / reached, 4) if reached else None,
    }


def get_classifier(backend: str | None = None, target: str | None = None) -> ClassifyFn:
    backend = backend or os.environ.get("EVAL_PARSER_BACKEND", "fake")
    if backend == "real":
        target = target or os.environ.get(TARGET_ENV)
        if not target:
            raise SystemExit(
                f"[eval_parser] backend=real needs {TARGET_ENV}=<provider>:<exact model id>"
            )
        return RealClassifier(target)
    return FakeIntentClassifier()


def run(dataset: Path = DEFAULT_DATASET, seed: int = 42) -> dict:
    """Load parser_intent scenarios, classify, compute metrics."""
    scenarios = [
        s for s in load_scenarios(dataset, layer="parser")
        if s.get("category") == "parser_intent"
    ]
    if not scenarios:
        raise SystemExit("[eval_parser] no parser_intent scenarios in dataset")
    classifier = get_classifier()
    result = compute_parser_metrics(scenarios, classifier)
    if isinstance(classifier, RealClassifier):
        result["target"] = classifier.target
        result["dataset_version"] = dataset_version(scenarios)
        result.update(decision_breakdown(scenarios, classifier.log))
    return result

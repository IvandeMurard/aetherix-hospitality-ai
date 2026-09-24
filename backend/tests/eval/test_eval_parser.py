"""HOS-208 (EVAL-4) + ADR-0007 §15 — parser eval grades the production path.

No network: the real backend is exercised with a scripted provider standing in
for the model, so these tests pin the *plumbing* of the real path (routing,
typed errors, canary, no-key contract), never a model number.
"""
from __future__ import annotations

import json
import sys

import pytest

from scripts.eval import baselines, eval_parser, reporter, run_all
from scripts.eval.eval_parser import (
    Prediction,
    ParserEvalNotMeasured,
    compute_parser_metrics,
    production_path_ceiling,
    run,
    threshold_breaches,
)
from scripts.eval.fake_intent_classifier import FakeIntentClassifier


def _sc(sid: str, intent: str, message: str, split: str | None = None) -> dict:
    row = {
        "id": sid,
        "category": "parser_intent",
        "layer": "parser",
        "input": {"message": message, "language": "fr"},
        "expected": {"intent": intent},
    }
    if split:
        row["split"] = split
    return row


class _ScriptedLLM:
    """Stands in for the model: answers per reply from a script, or raises."""

    model_id = "scripted/test"
    _fast_model = "scripted-fast"

    def __init__(self, script: dict[str, str | Exception]):
        self.script = script
        self.calls = 0

    async def complete(self, messages, max_tokens=500, temperature=0.3, system=None, tier="reasoning"):
        self.calls += 1
        reply = messages[0]["content"].removeprefix("Manager reply: ")
        answer = self.script.get(reply, '{"intent": "free_form", "confidence": 0.9}')
        if isinstance(answer, Exception):
            raise answer
        return answer


# ---------------------------------------------------------------------------
# Pure metrics
# ---------------------------------------------------------------------------

def test_confusion_matrix_and_accuracy():
    scenarios = [
        _sc("a", "accepted", "ok merci"),            # fake → accepted ✓
        _sc("b", "rejected", "non, pas d'accord"),   # fake → rejected ✓
        _sc("c", "modified", "covers: 80"),          # fake → modified ✓
        _sc("d", "accepted", "non merci"),           # fake → rejected ✗ (true accepted)
    ]
    r = compute_parser_metrics(scenarios, FakeIntentClassifier())

    assert r["n"] == 4
    assert r["accuracy"] == 0.75  # 3 / 4
    cm = r["confusion_matrix"]
    assert cm["accepted"]["accepted"] == 1
    assert cm["accepted"]["rejected"] == 1     # the misclassified "non merci"
    assert cm["rejected"]["rejected"] == 1
    assert cm["modified"]["modified"] == 1
    assert r["per_intent"]["modified"]["precision"] == 1.0
    assert r["per_intent"]["accepted"]["recall"] == 0.5  # 1 of 2 true-accepted caught


def test_skips_non_classification_scenarios():
    scenarios = [
        _sc("a", "accepted", "ok merci"),
        {"id": "ood", "category": "ood_edge", "layer": "parser",
         "input": {"message": "こんにちは"}, "expected": {"abstention": True}},
    ]
    r = compute_parser_metrics(scenarios, FakeIntentClassifier())
    assert r["n"] == 1  # the abstention/ood scenario is excluded


def test_unknown_label_is_a_typed_error_not_a_guess():
    # The old runner coerced any unknown label to "accepted". Never again.
    r = compute_parser_metrics([_sc("a", "accepted", "x")], lambda m, lang="fr": "banana")
    assert r["accuracy"] == 0.0
    assert r["confusion_matrix"]["accepted"]["error"] == 1
    assert r["cases"][0]["error"] == "unknown_label:banana"


def test_per_split_accuracy():
    scenarios = [_sc("a", "accepted", "ok"), _sc("b", "accepted", "x", split="heldout")]
    r = compute_parser_metrics(
        scenarios, lambda m, lang="fr": Prediction("accepted" if m == "ok" else "rejected", "t")
    )
    assert r["per_split"] == {"dev": {"accuracy": 1.0, "n": 1}, "heldout": {"accuracy": 0.0, "n": 1}}


def test_never_predicted_intent_breaches_contract():
    r = compute_parser_metrics(
        [_sc("a", "modified", "x"), _sc("b", "rejected", "y")],
        lambda m, lang="fr": Prediction("modified", "t"),
    )
    breaches = threshold_breaches(r)
    assert any("rejected: never predicted" in b for b in breaches)
    assert any(b.startswith("accuracy") for b in breaches)


# ---------------------------------------------------------------------------
# Fake backend = plumbing only
# ---------------------------------------------------------------------------

def test_fake_run_is_labelled_plumbing_and_not_quality(monkeypatch):
    monkeypatch.delenv("EVAL_PARSER_BACKEND", raising=False)
    r = run()
    assert r["backend"] == "fake"
    assert r["quality_signal"] is False
    assert r["measures"] == "pipeline_plumbing_only"
    # The circularity, made visible: rules written on `dev` resolve `dev`.
    assert r["per_split"]["dev"]["accuracy"] == 1.0
    assert r["per_split"]["heldout"]["n"] >= 30


def test_heldout_split_is_stratified_per_intent(monkeypatch):
    monkeypatch.delenv("EVAL_PARSER_BACKEND", raising=False)
    r = run()
    heldout = [c for c in r["cases"] if c["split"] == "heldout"]
    for intent in ("accepted", "rejected", "modified"):
        assert sum(c["expected"] == intent for c in heldout) >= 10


def test_fake_result_never_regresses_nor_has_baseline():
    diff = baselines.diff_parser({"backend": "fake", "accuracy": 0.1}, {"backend": "real", "accuracy": 0.9})
    assert diff == {"has_baseline": False, "regressed": False,
                    "accuracy_delta_pp": None, "plumbing_only": True}


def test_fake_result_is_never_frozen_as_baseline():
    assert "plumbing" in baselines.parser_baseline_freeze_refusal({"backend": "fake"})


def test_fake_report_has_no_accuracy_headline(monkeypatch):
    monkeypatch.delenv("EVAL_PARSER_BACKEND", raising=False)
    r = run()
    md = reporter.render_markdown(r, baselines.diff_parser(r, None))
    head = "\n".join(md.splitlines()[:4])
    assert "PLUMBING CHECK" in head
    assert "Not a model-quality measurement" in head
    assert "**Accuracy**" not in md


# ---------------------------------------------------------------------------
# Production path (what the real backend grades)
# ---------------------------------------------------------------------------

def test_production_path_routing_and_typed_errors():
    llm = _ScriptedLLM({
        "noted, see you later": '{"intent": "acknowledge", "confidence": 0.9}',
        "we will see": '{"intent": "free_form", "confidence": 0.9}',
        "boom": RuntimeError("api down"),
        "garbage": "not json at all",
        "invented": '{"intent": "rejected", "confidence": 0.99}',
    })
    scenarios = [
        _sc("kw-a", "accepted", "Accept"),
        _sc("kw-r", "rejected", " reject "),
        _sc("ack", "accepted", "👍"),
        _sc("cov", "modified", "covers: 80"),
        _sc("llm-ack", "accepted", "noted, see you later"),
        _sc("llm-ff", "modified", "we will see"),
        _sc("err", "modified", "boom"),
        _sc("bad", "modified", "garbage"),
        _sc("unmap", "rejected", "invented"),
    ]
    preds = eval_parser._run_production(scenarios, llm)
    got = {sc["id"]: (p.label, p.stage) for sc, p in zip(scenarios, preds)}

    assert got["kw-a"] == ("accepted", "action_keyword")
    assert got["kw-r"] == ("rejected", "action_keyword")
    assert got["ack"] == ("not_recorded", "ack_regex")
    assert got["cov"] == ("modified", "covers_regex")
    assert got["llm-ack"] == ("not_recorded", "llm")
    assert got["llm-ff"] == ("modified", "llm")
    # Failures of the model are typed errors — production would record
    # "modified" here, the eval refuses to count that fallback as an answer.
    assert got["err"] == ("error", "llm_error")
    assert got["bad"] == ("error", "llm_error")
    assert got["unmap"] == ("error", "llm_unmappable")
    assert llm.calls == 5  # keywords and regexes never reach the model


def test_production_path_ceiling_is_model_independent():
    scenarios = [
        _sc("a", "accepted", "ça marche"),   # reaches model → best case not_recorded/modified
        _sc("b", "rejected", "reject"),      # keyword → rejected ✓
        _sc("c", "modified", "covers: 80"),  # regex → modified ✓
        _sc("d", "modified", "plutôt 40"),   # reaches model → modified reachable ✓
    ]
    c = production_path_ceiling(scenarios)
    assert c["max_accuracy"] == 0.75
    assert c["reaches_model"] == 2
    assert c["max_recall"]["accepted"] == 0.0


def test_real_backend_without_key_is_not_measured(monkeypatch):
    monkeypatch.setenv("EVAL_PARSER_BACKEND", "real")
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    with pytest.raises(ParserEvalNotMeasured):
        run()


def test_run_all_exits_2_when_not_measured(monkeypatch, tmp_path):
    monkeypatch.setenv("EVAL_PARSER_BACKEND", "real")
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    md = tmp_path / "r.md"
    monkeypatch.setattr(sys, "argv", ["run_all", "--layers", "parser", "--strict", "--md-out", str(md)])
    assert run_all.main() == 2
    assert not md.exists()  # no report that could be mistaken for a result


def _patch_provider(monkeypatch, llm):
    class _Composite:
        primary = llm

    import app.providers.factory as factory

    monkeypatch.setattr(factory, "get_llm_provider", lambda: _Composite())
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key-not-used")
    monkeypatch.setenv("EVAL_PARSER_BACKEND", "real")


def test_real_backend_uses_primary_and_reports_canary(monkeypatch):
    llm = _ScriptedLLM({})
    _patch_provider(monkeypatch, llm)
    r = run(runs=3)
    assert r["backend"] == "real" and r["quality_signal"] is True
    assert r["model"]["provider"] == "scripted/test"
    assert r["model"]["temperatures"] == [0.0]  # the production temperature
    assert r["canary"]["runs"] == 3
    assert r["canary"]["identical_predictions"] is True
    assert r["canary"]["variance_pp"] == 0.0
    # Free text can never record accepted/rejected on this path (ADR-0007 §15).
    assert r["accuracy"] <= r["production_path_ceiling"]["max_accuracy"]
    assert r["thresholds"]["breaches"]
    assert baselines.parser_baseline_freeze_refusal(r) is None


def test_real_baseline_refused_on_single_run_or_disagreeing_runs():
    base = {"backend": "real", "canary": {"runs": 1, "variance_pp": 0.0, "identical_predictions": True}}
    assert "3 runs" in baselines.parser_baseline_freeze_refusal(base)
    base["canary"] = {"runs": 3, "variance_pp": 2.13, "identical_predictions": False}
    assert "disagree" in baselines.parser_baseline_freeze_refusal(base)


def test_real_diff_ignores_non_real_baseline_and_flags_threshold():
    result = {"backend": "real", "accuracy": 0.4, "thresholds": {"breaches": ["accuracy 0.4 < 0.9"]}}
    diff = baselines.diff_parser(result, {"backend": "fake", "accuracy": 1.0})
    assert diff["has_baseline"] is False and diff["below_threshold"] is True
    diff = baselines.diff_parser(result, {"backend": "real", "accuracy": 0.5})
    assert diff["regressed"] is True and diff["accuracy_delta_pp"] == -10.0


def test_no_fake_parser_baseline_is_committed():
    path = baselines.baseline_path("parser")
    if path.exists():  # a real baseline may be committed later — never a fake one
        assert json.loads(path.read_text(encoding="utf-8")).get("backend") == "real"

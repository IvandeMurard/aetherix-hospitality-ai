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


def _sc(sid: str, intent: str, message: str, split: str | None = None, proposal: str = "add") -> dict:
    row = {
        "id": sid,
        "category": "parser_intent",
        "layer": "parser",
        "input": {"message": message, "language": "fr", "proposal": {"kind": proposal}},
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
        # The reply is the last line, after the proposal line (ADR-0007 §19).
        reply = messages[0]["content"].rsplit("Manager reply: ", 1)[-1]
        answer = self.script.get(reply, '{"stance": "counter_value", "confidence": 0.9}')
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
        "noted, see you later": '{"stance": "none", "confidence": 0.9}',
        "sounds good, will do": '{"stance": "adopt_proposal", "confidence": 0.95}',
        "hmm not sure": '{"stance": "decline_proposal", "confidence": 0.5}',
        "we will see": '{"stance": "counter_value", "confidence": 0.9}',
        "we stay as planned": '{"stance": "keep_current", "confidence": 0.95}',
        "boom": RuntimeError("api down"),
        "garbage": "not json at all",
        "invented": '{"decision": "rejected", "confidence": 0.99}',   # §16 schema: no stance
    })
    scenarios = [
        _sc("kw-a", "accepted", "Accept"),
        _sc("kw-oui", "accepted", "oui"),
        _sc("kw-r", "rejected", " refusé "),
        _sc("decl", "rejected", "non merci"),
        _sc("decl-keep", "accepted", "non merci on garde tel quel", proposal="no_change"),
        _sc("need-add", "rejected", "pas besoin"),
        _sc("need-red", "rejected", "pas besoin", proposal="reduce"),
        _sc("amb", "rejected", "bof"),
        _sc("ack", "accepted", "👍"),
        _sc("cov", "modified", "covers: 80"),
        _sc("llm-none", "accepted", "noted, see you later"),
        _sc("llm-auto", "accepted", "sounds good, will do"),
        _sc("llm-low", "rejected", "hmm not sure"),
        _sc("llm-mod", "modified", "we will see"),
        _sc("llm-keep-add", "rejected", "we stay as planned"),
        _sc("llm-keep-none", "accepted", "we stay as planned", proposal="no_change"),
        _sc("err", "modified", "boom"),
        _sc("bad", "modified", "garbage"),
        _sc("unmap", "rejected", "invented"),
    ]
    preds = eval_parser._run_production(scenarios, llm)
    got = {sc["id"]: (p.label, p.stage, p.action) for sc, p in zip(scenarios, preds)}

    assert got["kw-a"] == ("accepted", "keyword", "record")
    assert got["kw-oui"] == ("accepted", "keyword", "record")
    assert got["kw-r"] == ("rejected", "keyword", "record")
    # "No thanks" to a recommendation adding staff → rejected (§17.8, §19).
    assert got["decl"] == ("rejected", "keyword", "record")
    # Keep current, composed from the lexicon, to a no-change proposal → accepted.
    assert got["decl-keep"] == ("accepted", "keyword", "record")
    # "Pas besoin": rejects ADD, two readings for REDUCE (§19).
    assert got["need-add"] == ("rejected", "keyword", "record")
    assert got["need-red"] == ("rejected", "keyword_ambiguous", "confirm")
    # Two readings → confirmation, never a write.
    assert got["amb"] == ("rejected", "keyword_ambiguous", "confirm")
    # Bare ack, one pending recommendation inside the window (EVAL_CONTEXT) → rule (b).
    assert got["ack"] == ("accepted", "bare_ack", "record")
    assert got["cov"] == ("modified", "covers_regex", "record")
    assert got["llm-none"] == ("not_recorded", "llm", "none")
    assert got["llm-auto"] == ("accepted", "llm", "record")
    # Low confidence → the decision is proposed for confirmation, not written.
    assert got["llm-low"] == ("rejected", "llm", "confirm")
    assert got["llm-mod"] == ("modified", "llm", "record")
    # Same model stance, different proposal, different decision (§19).
    assert got["llm-keep-add"] == ("rejected", "llm", "record")
    assert got["llm-keep-none"] == ("accepted", "llm", "record")
    # Model failures are typed errors — never a decision.
    assert got["err"] == ("error", "llm_error", "error")
    assert got["bad"] == ("error", "llm_unmappable", "error")
    assert got["unmap"] == ("error", "llm_unmappable", "error")
    assert llm.calls == 9  # keywords and regexes never reach the model


def test_auto_write_precision_and_confirmation_rate():
    scenarios = [_sc("a", "accepted", "x1"), _sc("b", "rejected", "x2"),
                 _sc("c", "rejected", "x3"), _sc("d", "modified", "x4")]
    preds = {
        "x1": Prediction("accepted", "llm", action="record"),
        "x2": Prediction("accepted", "llm", action="record"),   # wrong auto-write
        "x3": Prediction("rejected", "llm", action="confirm"),  # right, confirmed
        "x4": Prediction("modified", "llm", action="record"),
    }
    r = compute_parser_metrics(scenarios, lambda m, lang="fr": preds[m])
    assert r["accuracy"] == 0.75
    assert r["auto_write"]["n_written"] == 3
    assert r["auto_write"]["per_decision_precision"]["accepted"] == 0.5
    assert r["auto_write"]["per_decision_precision"]["rejected"] is None
    assert r["confirmation_rate"] == 0.25
    assert any("accepted: auto-write precision 0.5" in b for b in threshold_breaches(r))


def test_confirmation_trigger_write_is_a_breach():
    trig = eval_parser.confirmation_trigger(
        [{"id": "t1"}, {"id": "t2"}, {"id": "t3"}],
        [Prediction("rejected", "llm", action="confirm"),
         Prediction("not_recorded", "llm", action="none"),
         Prediction("accepted", "llm", action="record")],
    )
    assert trig["auto_written"] == 1 and trig["confirmed_or_none"] == 2
    breaches = threshold_breaches({"accuracy": 1.0, "per_intent": {}, "confirmation_trigger": trig})
    assert breaches == ["confirmation trigger: 1 low-confidence case(s) written without confirmation"]


def test_production_path_ceiling_is_model_independent():
    scenarios = [
        _sc("a", "accepted", "ça marche"),   # reaches model → reachable
        _sc("b", "rejected", "reject"),      # keyword → rejected ✓
        _sc("c", "modified", "covers: 80"),  # regex → modified ✓
        _sc("d", "accepted", "non"),         # keyword → rejected ✗ (label disagrees)
    ]
    c = production_path_ceiling(scenarios)
    assert c["max_accuracy"] == 0.75
    assert c["reaches_model"] == 1
    assert c["max_recall"]["accepted"] == 0.5


def test_dataset_deterministic_block_agrees_with_labels():
    """Every golden reply decided before the model lands on its label, and on
    the path the dataset annotates. A code check, not a quality figure."""
    from scripts.eval.loader import load_scenarios

    scenarios = [s for s in load_scenarios(layer="parser") if s["category"] == "parser_intent"]
    block = eval_parser.deterministic_block(scenarios)
    assert block["n"] >= 10
    assert block["disagreements"] == []
    stage_to_path = {"keyword": "keyword", "keyword_ambiguous": "keyword_ambiguous",
                     "bare_ack": "bare_ack", "covers_regex": "correction_pattern"}
    for case in block["cases"]:
        assert stage_to_path[case["stage"]] == case["expected_path"], case["id"]
    graded = eval_parser.model_graded_ids(scenarios)
    for s in scenarios:
        assert (s["id"] in graded) == (s["expected"]["path"] == "model"), s["id"]


def test_dataset_has_confirmation_trigger_cases():
    from scripts.eval.loader import load_scenarios

    trig = [s for s in load_scenarios(layer="parser") if s["category"] == "parser_confirmation"]
    assert len(trig) >= 10
    assert all(s["expected"]["requires_confirmation"] is True for s in trig)
    from app.schemas.webhook import ActionType
    from app.services.action_logger import parse_action
    from app.services.manager_decision import is_bare_ack

    by_path = {"model": [], "keyword_ambiguous": []}
    for s in trig:
        by_path[s["expected"]["path"]].append(s)
    # Model-path cases must reach the model: a keyword would decide them without it.
    assert len(by_path["model"]) >= 10
    for s in by_path["model"]:
        msg = s["input"]["message"]
        assert parse_action(msg) == ActionType.unknown and not is_bare_ack(msg), s["id"]
    # Deterministic two-reading cases (ADR-0007 §19): confirmation with no model call.
    preds = eval_parser._quiet_stub_run(by_path["keyword_ambiguous"])
    for s, p in zip(by_path["keyword_ambiguous"], preds):
        assert (p.stage, p.action) == ("keyword_ambiguous", "confirm"), s["id"]


def test_every_proposal_kind_has_graded_cases():
    """ADR-0007 §19: the golden set answers add, reduce and no-change proposals,
    on the deterministic path and on the model path."""
    from scripts.eval.loader import load_scenarios

    scenarios = [s for s in load_scenarios(layer="parser") if s["category"] == "parser_intent"]
    for kind in ("add", "reduce", "no_change"):
        cases = [s for s in scenarios if s["input"]["proposal"]["kind"] == kind]
        paths = {s["expected"]["path"] for s in cases}
        assert "model" in paths and "keyword" in paths, kind
        assert {"fr", "en"} <= {s["input"]["language"] for s in cases}, kind


def test_per_proposal_accuracy_is_reported():
    scenarios = [_sc("a", "accepted", "oui"), _sc("b", "rejected", "tel quel", proposal="reduce"),
                 _sc("c", "accepted", "tel quel", proposal="no_change")]
    preds = eval_parser._quiet_stub_run(scenarios)
    r = compute_parser_metrics(scenarios, eval_parser._replay(preds))
    assert r["per_proposal"] == {"add": {"accuracy": 1.0, "n": 1},
                                 "no_change": {"accuracy": 1.0, "n": 1},
                                 "reduce": {"accuracy": 1.0, "n": 1}}


def test_real_backend_without_key_is_not_measured(monkeypatch):
    monkeypatch.setenv("EVAL_PARSER_BACKEND", "real")
    monkeypatch.setenv("EVAL_PARSER_TARGET", "claude:claude-haiku-4-5-20251001")
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
    """The pinned target (HOS-337) resolves to the scripted model, never the failover."""
    from scripts.eval import eval_parser

    monkeypatch.setattr(eval_parser, "_build_provider", lambda provider, model: llm)
    monkeypatch.setenv("EVAL_PARSER_TARGET", "claude:scripted-test-model")
    monkeypatch.setenv("EVAL_PARSER_BACKEND", "real")


def test_real_backend_uses_pinned_target_and_reports_canary(monkeypatch):
    llm = _ScriptedLLM({})  # every model reply → modified @ 0.9
    _patch_provider(monkeypatch, llm)
    r = run(runs=3)
    assert r["backend"] == "real" and r["quality_signal"] is True
    assert r["measures"] == "free_text_path_model_included"
    assert r["model"]["provider"] == "scripted/test"
    assert r["target"] == "claude:scripted-test-model"
    assert r["model"]["temperatures"] == [0.0]  # the production temperature
    assert r["canary"]["runs"] == 3
    assert r["canary"]["identical_predictions"] is True
    assert r["canary"]["variance_pp"] == 0.0
    # Only free-text cases are model-graded; deterministic ones are reported apart.
    assert r["n"] == r["production_path_ceiling"]["reaches_model"]
    assert all(c["stage"] == "llm" for c in r["cases"])
    assert r["deterministic"]["disagreements"] == []
    # A model that answers "counter_value" to everything auto-writes every trigger
    # case it sees; the deterministic two-reading cases (§19) never reach it and
    # are confirmed whatever the model says.
    trig_cases = r["confirmation_trigger"]["cases"]
    model_seen = [c for c in trig_cases if c["stage"] == "llm"]
    assert r["confirmation_trigger"]["auto_written"] == len(model_seen) > 0
    assert all(c["action"] == "confirm" for c in trig_cases if c["stage"] == "keyword_ambiguous")
    assert any(b.startswith("confirmation trigger") for b in r["thresholds"]["breaches"])
    assert baselines.parser_baseline_freeze_refusal(r) is None


def test_real_backend_low_confidence_model_passes_trigger(monkeypatch):
    class _Unsure(_ScriptedLLM):
        async def complete(self, *a, **k):
            self.calls += 1
            return '{"stance": "decline_proposal", "confidence": 0.4}'

    _patch_provider(monkeypatch, _Unsure({}))
    r = run(runs=1)
    assert r["confirmation_trigger"]["auto_written"] == 0
    assert r["auto_write"]["n_written"] == 0
    assert r["confirmation_rate"] == 1.0
    md = reporter.render_markdown(r, baselines.diff_parser(r, None))
    assert "Confirmation trigger" in md and "Deterministic path" in md


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

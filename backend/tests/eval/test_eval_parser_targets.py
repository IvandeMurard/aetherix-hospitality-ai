"""HOS-337 (Décision #35 D3) — real-LLM parser runs against a pinned target.

No network: the provider is replaced by a stub. What is tested is the harness —
target parsing, the refusal to run without a target or a key, the per-target
fields compared across providers, per-(target, dataset) baselines, and the
refusal to compare runs over different cases.

Merged with the production-path eval (ADR-0007 §15-§16): the graded path is the
route's own sequence with a schema-validated model answer, so there is no
free_form heuristic left to attribute; a model error or an answer that fails the
schema is a miss, and is also read as the model failure rate.
"""
from __future__ import annotations

import json

import pytest
from scripts.eval import baselines, eval_parser
from scripts.eval.compare_parser_targets import compare
from scripts.eval.eval_parser import (
    ParserEvalNotMeasured,
    dataset_version,
    parse_target,
    target_breakdown,
)


class _StubProvider:
    """Answers every model call with one canned reply (or raises)."""

    model_id = "stub/pinned"
    _fast_model = "pinned-model"

    def __init__(self, reply: str | Exception) -> None:
        self._reply = reply
        self.calls = 0

    async def complete(self, *args, **kwargs) -> str:
        self.calls += 1
        if isinstance(self._reply, Exception):
            raise self._reply
        return self._reply


def _real_env(monkeypatch, stub: _StubProvider) -> None:
    monkeypatch.setenv("EVAL_PARSER_BACKEND", "real")
    monkeypatch.setenv("EVAL_PARSER_TARGET", "claude:pinned-model")
    monkeypatch.setattr(eval_parser, "_build_provider", lambda provider, model: stub)


# ─── target spec ──────────────────────────────────────────────────────────────

def test_parse_target_accepts_exact_model_ids():
    assert parse_target("claude:claude-haiku-4-5-20251001") == ("claude", "claude-haiku-4-5-20251001")
    assert parse_target("gemini:gemini-2.0-flash") == ("gemini", "gemini-2.0-flash")


@pytest.mark.parametrize("spec", ["claude", "openai:gpt", "claude:", ":model", "gemini"])
def test_parse_target_rejects_malformed_or_unknown(spec):
    with pytest.raises(SystemExit):
        parse_target(spec)


def test_real_backend_without_target_is_not_measured(monkeypatch):
    monkeypatch.setenv("EVAL_PARSER_BACKEND", "real")
    monkeypatch.delenv("EVAL_PARSER_TARGET", raising=False)
    with pytest.raises(ParserEvalNotMeasured):
        eval_parser.run()


def test_missing_api_key_is_not_measured(monkeypatch):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    with pytest.raises(ParserEvalNotMeasured):
        eval_parser._build_provider("claude", "claude-haiku-4-5-20251001")
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    with pytest.raises(ParserEvalNotMeasured):
        eval_parser._build_provider("gemini", "gemini-2.0-flash")


def test_pinned_provider_maps_both_tiers_to_the_exact_model(monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-test")
    p = eval_parser._build_provider("claude", "claude-haiku-4-5-20251001")
    assert p._model == p._fast_model == "claude-haiku-4-5-20251001"


# ─── end to end on a stub target ──────────────────────────────────────────────

def test_real_run_records_target_dataset_version_and_failure_rate(monkeypatch):
    reply = json.dumps({"decision": "accepted", "confidence": 0.95, "intent": "free_form"})
    stub = _StubProvider(reply)
    _real_env(monkeypatch, stub)

    result = eval_parser.run()

    assert result["target"] == "claude:pinned-model"
    assert len(result["dataset_version"]) == 12
    assert stub.calls > 0
    assert result["llm_decided_n"] == result["n"]
    assert result["accuracy_llm_decided"] == result["accuracy"]
    assert result["llm_failure_rate"] == 0.0


def test_a_model_that_cannot_answer_shows_in_the_failure_rate(monkeypatch):
    _real_env(monkeypatch, _StubProvider("not json at all"))

    result = eval_parser.run()

    assert result["llm_failure_rate"] == 1.0
    assert result["accuracy"] == 0.0  # nothing rescues a failed answer


# ─── breakdown, dataset version, baselines ────────────────────────────────────

def test_target_breakdown_counts_steps_and_failures():
    result = {
        "n": 4,
        "accuracy": 0.5,
        "cases": [
            {"stage": "llm", "ok": True},
            {"stage": "llm", "ok": True},
            {"stage": "llm_error", "ok": False},
            {"stage": "llm_unmappable", "ok": False},
        ],
    }
    b = target_breakdown(result)
    assert b["decided_by"] == {"llm": 2, "llm_error": 1, "llm_unmappable": 1}
    assert b["accuracy_by_source"]["llm"] == 1.0
    assert b["accuracy_llm_decided"] == 0.5
    assert b["llm_decided_n"] == 4
    assert b["llm_failure_rate"] == 0.5


def test_dataset_version_ignores_order_but_not_content():
    a = {"id": "a", "input": {"message": "ok"}}
    b = {"id": "b", "input": {"message": "non"}}
    edited = {"id": "b", "input": {"message": "non merci"}}
    assert dataset_version([a, b]) == dataset_version([b, a])
    assert dataset_version([a, b]) != dataset_version([a, edited])


def test_target_baselines_are_keyed_by_target_and_dataset_version():
    claude = baselines.parser_target_baseline_path("claude:haiku-x", "abc123")
    gemini = baselines.parser_target_baseline_path("gemini:flash-y", "abc123")
    other_ds = baselines.parser_target_baseline_path("claude:haiku-x", "def456")
    assert len({claude, gemini, other_ds}) == 3
    assert claude != baselines.baseline_path("parser")  # never the fake gate's baseline
    assert ":" not in claude.name


# ─── comparison ───────────────────────────────────────────────────────────────

def _run(target: str, version: str, acc: float, n: int, failure: float) -> dict:
    return {
        "target": target,
        "dataset_version": version,
        "accuracy_llm_decided": acc,
        "llm_decided_n": n,
        "llm_failure_rate": failure,
        "auto_write": {"precision": 1.0},
        "confirmation_rate": 0.2,
        "decided_by": {"llm": n},
    }


def test_compare_refuses_mixed_dataset_versions():
    with pytest.raises(SystemExit):
        compare([_run("claude:a", "v1", 1.0, 10, 0.0), _run("gemini:b", "v2", 0.5, 10, 0.1)])


def test_compare_reports_the_gap_and_warns_on_thin_subset():
    table = compare([_run("claude:a", "v1", 1.0, 3, 0.0), _run("gemini:b", "v1", 0.5, 3, 0.5)])
    assert "`claude:a`" in table and "`gemini:b`" in table
    assert "100.0%" in table and "50.0%" in table
    assert "too few to conclude" in table

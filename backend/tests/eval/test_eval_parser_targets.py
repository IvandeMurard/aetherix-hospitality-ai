"""HOS-337 (Décision #35 D3) — real-LLM parser runs against a pinned target.

No network: the provider is replaced by a stub. What is tested is the harness —
target parsing, who-decided-what attribution, per-(target, dataset) baselines,
and the refusal to compare runs over different cases.
"""
from __future__ import annotations

import json

import pytest
from scripts.eval import baselines, eval_parser
from scripts.eval.compare_parser_targets import compare
from scripts.eval.eval_parser import (
    SOURCE_LLM,
    SOURCE_LLM_FAILED,
    SOURCE_LLM_FREE_FORM,
    SOURCE_REGEX,
    RealClassifier,
    dataset_version,
    decision_breakdown,
    parse_target,
)


class _StubProvider:
    """Answers the pass-3 classifier with a canned reply per message."""

    model_id = "stub/pinned"

    def __init__(self, replies: dict[str, str]) -> None:
        self._replies = replies
        self.seen: list[str] = []

    async def complete(self, messages, **kwargs) -> str:
        text = messages[0]["content"]
        self.seen.append(text)
        for needle, reply in self._replies.items():
            if needle in text:
                return reply
        return "not json at all"


def _reply(intent: str) -> str:
    return json.dumps(
        {"intent": intent, "confidence": 0.9, "outcome": "modified", "actual_value": None, "notes": ""}
    )


def _classifier(monkeypatch, replies: dict[str, str]) -> tuple[RealClassifier, _StubProvider]:
    stub = _StubProvider(replies)
    monkeypatch.setattr(eval_parser, "_build_provider", lambda provider, model: stub)
    return RealClassifier("claude:pinned-model"), stub


# ─── target spec ──────────────────────────────────────────────────────────────


def test_parse_target_accepts_exact_model_ids():
    assert parse_target("claude:claude-haiku-4-5-20251001") == ("claude", "claude-haiku-4-5-20251001")
    assert parse_target("gemini:gemini-2.0-flash") == ("gemini", "gemini-2.0-flash")


@pytest.mark.parametrize("spec", ["claude", "claude:", "openai:gpt-x", ":model", "fast"])
def test_parse_target_rejects_malformed_or_unknown(spec):
    with pytest.raises(SystemExit):
        parse_target(spec)


def test_real_backend_without_target_fails_loudly(monkeypatch):
    monkeypatch.delenv(eval_parser.TARGET_ENV, raising=False)
    with pytest.raises(SystemExit, match="EVAL_PARSER_TARGET"):
        eval_parser.get_classifier(backend="real")


def test_missing_api_key_fails_instead_of_skipping(monkeypatch):
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    with pytest.raises(SystemExit, match="GEMINI_API_KEY"):
        eval_parser._build_provider("gemini", "gemini-2.0-flash")


def test_pinned_provider_maps_both_tiers_to_the_exact_model(monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-test")
    p = eval_parser._build_provider("claude", "claude-haiku-4-5-20251001")
    assert p._model == p._fast_model == "claude-haiku-4-5-20251001"


# ─── who decided each case ────────────────────────────────────────────────────


def test_regex_cases_never_reach_the_llm(monkeypatch):
    clf, stub = _classifier(monkeypatch, {})
    clf.classify("👍", "fr")  # pass 1 (acknowledge regex)
    clf.classify("covers: 80", "fr")  # pass 2 (covers regex)
    assert stub.seen == []
    assert [e["source"] for e in clf.log] == [SOURCE_REGEX, SOURCE_REGEX]


def test_llm_sources_are_attributed(monkeypatch):
    clf, stub = _classifier(
        monkeypatch,
        {
            "on attend beaucoup de monde": _reply("structured_correction"),
            "mariage prévu samedi": _reply("free_form"),
        },
    )
    assert clf.classify("on attend beaucoup de monde demain", "fr") == "modified"
    clf.classify("mariage prévu samedi soir", "fr")
    clf.classify("réponse que le stub ne sait pas parser", "fr")
    assert len(stub.seen) == 3
    assert [e["source"] for e in clf.log] == [SOURCE_LLM, SOURCE_LLM_FREE_FORM, SOURCE_LLM_FAILED]


def test_provider_error_counts_as_llm_failed(monkeypatch):
    class _Down:
        model_id = "stub/down"

        async def complete(self, **kwargs):
            raise RuntimeError("503")

    monkeypatch.setattr(eval_parser, "_build_provider", lambda provider, model: _Down())
    clf = RealClassifier("gemini:pinned-model")
    clf.classify("on attend beaucoup de monde demain", "fr")
    assert clf.log[-1]["source"] == SOURCE_LLM_FAILED


def test_decision_breakdown_scores_llm_decided_cases_only():
    scenarios = [
        {"input": {"message": "a"}, "expected": {"intent": "modified"}},
        {"input": {"message": "b"}, "expected": {"intent": "accepted"}},
        {"input": {"message": "c"}, "expected": {"intent": "rejected"}},
    ]
    log = [
        {"message": "a", "source": SOURCE_LLM, "predicted": "modified"},
        {"message": "b", "source": SOURCE_LLM, "predicted": "modified"},
        {"message": "c", "source": SOURCE_REGEX, "predicted": "rejected"},
    ]
    b = decision_breakdown(scenarios, log)
    assert b["decided_by"][SOURCE_LLM] == 2
    assert b["decided_by"][SOURCE_REGEX] == 1
    assert b["llm_decided_n"] == 2
    assert b["accuracy_llm_decided"] == 0.5  # the regex hit does not inflate it
    assert b["llm_failure_rate"] == 0.0


def test_failures_are_visible_even_when_accuracy_is_unchanged():
    """A failed call is rescued by the heuristic: accuracy stays put, so the
    failure rate is the only signal of a provider that cannot answer."""
    scenarios = [{"input": {"message": m}, "expected": {"intent": "rejected"}} for m in "ab"]
    log = [
        {"message": "a", "source": SOURCE_LLM_FAILED, "predicted": "rejected"},
        {"message": "b", "source": SOURCE_LLM_FREE_FORM, "predicted": "rejected"},
    ]
    b = decision_breakdown(scenarios, log)
    assert b["accuracy_by_source"][SOURCE_LLM_FAILED] == 1.0
    assert b["llm_failure_rate"] == 0.5


# ─── baselines and comparison ─────────────────────────────────────────────────


def test_dataset_version_ignores_order_but_not_content():
    a = {"id": "1", "input": {"message": "x"}}
    b = {"id": "2", "input": {"message": "y"}}
    assert dataset_version([a, b]) == dataset_version([b, a])
    edited = {"id": "2", "input": {"message": "y!"}}
    assert dataset_version([a, b]) != dataset_version([a, edited])


def test_target_baselines_are_keyed_by_target_and_dataset_version():
    claude = baselines.parser_target_baseline_path("claude:claude-haiku-4-5-20251001", "abc123")
    gemini = baselines.parser_target_baseline_path("gemini:gemini-2.0-flash", "abc123")
    other_ds = baselines.parser_target_baseline_path("claude:claude-haiku-4-5-20251001", "def456")
    assert len({claude, gemini, other_ds}) == 3
    assert claude != baselines.baseline_path("parser")  # never the fake gate's baseline
    assert ":" not in claude.name


def _run(target: str, version: str, llm_acc: float | None, llm_n: int) -> dict:
    counts = {s: 0 for s in eval_parser.SOURCES}
    counts[SOURCE_LLM] = llm_n
    return {
        "target": target,
        "dataset_version": version,
        "accuracy": 0.9,
        "accuracy_llm_decided": llm_acc,
        "llm_decided_n": llm_n,
        "decided_by": counts,
        "llm_failure_rate": 0.0,
    }


def test_compare_refuses_mixed_dataset_versions():
    with pytest.raises(SystemExit, match="not comparable"):
        compare([_run("claude:a", "v1", 1.0, 6), _run("gemini:b", "v2", 0.5, 6)])


def test_compare_reports_the_gap_and_warns_on_thin_llm_subset():
    table = compare([_run("claude:a", "v1", 1.0, 6), _run("gemini:b", "v1", 0.5, 2)])
    assert "`claude:a`" in table and "`gemini:b`" in table
    assert "100.0%" in table and "50.0%" in table
    assert "too few to conclude" in table

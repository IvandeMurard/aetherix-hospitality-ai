"""HOS-320 (Story 16.18) — hygiene_architecturale unit tests.

Each detector is exercised against a synthetic repo built in tmp_path, so the
tests assert detector *logic* rather than the current state of the real repo
(which changes every time drift is fixed). No network, no secrets.
"""
from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest

_SCRIPT = Path(__file__).resolve().parents[3] / "scripts" / "ops" / "hygiene_architecturale.py"
_spec = importlib.util.spec_from_file_location("hygiene_architecturale", _SCRIPT)
hygiene = importlib.util.module_from_spec(_spec)
# Register before exec: @dataclass resolves annotations via sys.modules[__module__].
sys.modules["hygiene_architecturale"] = hygiene
_spec.loader.exec_module(hygiene)


@pytest.fixture
def fake_repo(tmp_path, monkeypatch):
    """Point the module at a throwaway repo root."""
    monkeypatch.setattr(hygiene, "_ROOT", tmp_path)
    return tmp_path


def _write(root: Path, rel: str, content: str) -> None:
    path = root / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def _titles(result) -> str:
    return " ".join(f.title for f in result.findings)


# ─── D1 · Harness drift ───────────────────────────────────────────────────────


def test_d1_identical_harnesses_are_clean(fake_repo):
    body = "# CLAUDE.md — Aetherix\n\n| IA | Claude Sonnet |\n"
    _write(fake_repo, "CLAUDE.md", body)
    _write(fake_repo, "AGENTS.md", body.replace("CLAUDE.md", "AGENTS.md"))

    result = hygiene.Result()
    hygiene.detect_harness_drift(result)

    assert result.drift == []


def test_d1_detects_corrupted_find_replace(fake_repo):
    """The real-world case: `claude-sonnet-4-6` rewritten to a bogus model id."""
    _write(fake_repo, "CLAUDE.md", '# CLAUDE.md\n\nLLM_MODEL — "claude-sonnet-4-6"\n')
    _write(fake_repo, "AGENTS.md", '# AGENTS.md\n\nLLM_MODEL — "Codex-sonnet-4-6"\n')

    result = hygiene.Result()
    hygiene.detect_harness_drift(result)

    assert len(result.drift) == 1
    assert "Codex-sonnet-4-6" in result.drift[0].detail


def test_d1_skips_when_a_harness_file_is_absent(fake_repo):
    _write(fake_repo, "CLAUDE.md", "# CLAUDE.md\n")

    result = hygiene.Result()
    hygiene.detect_harness_drift(result)

    assert result.drift == []
    assert any("AGENTS.md" in s for s in result.skipped)


# ─── D2 · Doc → code ──────────────────────────────────────────────────────────


def test_d2_flags_path_that_does_not_exist(fake_repo, monkeypatch):
    monkeypatch.setattr(hygiene, "DOC_SOURCES", ["CLAUDE.md"])
    monkeypatch.setattr(hygiene, "PLANNED_PATHS", {})
    _write(fake_repo, "CLAUDE.md", "Voir `docs/secrets_handling.md` pour la rotation.")

    result = hygiene.Result()
    hygiene.detect_doc_paths(result)

    assert len(result.drift) == 1
    assert "docs/secrets_handling.md" in result.drift[0].title


def test_d2_accepts_existing_path_and_ignores_prose(fake_repo, monkeypatch):
    monkeypatch.setattr(hygiene, "DOC_SOURCES", ["CLAUDE.md"])
    _write(fake_repo, "docs/real.md", "x")
    _write(fake_repo, "CLAUDE.md", "Voir `docs/real.md` et `LLMProvider` et `https://example.com`.")

    result = hygiene.Result()
    hygiene.detect_doc_paths(result)

    assert result.findings == []


def test_d2_ignores_glob_patterns(fake_repo, monkeypatch):
    monkeypatch.setattr(hygiene, "DOC_SOURCES", ["CLAUDE.md"])
    _write(fake_repo, "CLAUDE.md", "Gates dans `scripts/eval/*.py` et `docs/adr/000X-*.md`.")

    result = hygiene.Result()
    hygiene.detect_doc_paths(result)

    assert result.findings == []


def test_d2_planned_paths_are_info_not_drift(fake_repo, monkeypatch):
    """Doc describing unbuilt code is a dated intention, not a stale reference."""
    monkeypatch.setattr(hygiene, "DOC_SOURCES", ["CLAUDE.md"])
    monkeypatch.setattr(
        hygiene, "PLANNED_PATHS", {"backend/app/providers/pos/": "POS — ADR-0006, Phase 4"}
    )
    _write(fake_repo, "CLAUDE.md", "Adapters POS dans `backend/app/providers/pos/`.")

    result = hygiene.Result()
    hygiene.detect_doc_paths(result)

    assert result.drift == []
    assert len(result.info) == 1
    assert "Phase 4" in result.info[0].detail


# ─── D3 · Env sync ────────────────────────────────────────────────────────────


def _env_doc(*names: str) -> str:
    lines = "\n".join(f"{n}     — description" for n in names)
    return f"# CLAUDE.md\n\n## Variables d'environnement\n\n```\n{lines}\n```\n\n---\n\n## Suite\n"


def test_d3_flags_documented_but_undeclared_var(fake_repo):
    _write(fake_repo, "backend/.env.example", "ANTHROPIC_API_KEY=sk-ant-...\n")
    _write(fake_repo, "CLAUDE.md", _env_doc("ANTHROPIC_API_KEY", "LOGFIRE_TOKEN"))

    result = hygiene.Result()
    hygiene.detect_env_sync(result)

    assert len(result.drift) == 1
    assert "LOGFIRE_TOKEN" in result.drift[0].title


def test_d3_undocumented_var_is_info_only(fake_repo):
    """`.env.example` is exhaustive; CLAUDE.md documents a curated subset."""
    _write(fake_repo, "backend/.env.example", "ANTHROPIC_API_KEY=x\nMAIL_SERVER=mailhog\n")
    _write(fake_repo, "CLAUDE.md", _env_doc("ANTHROPIC_API_KEY"))

    result = hygiene.Result()
    hygiene.detect_env_sync(result)

    assert result.drift == []
    assert len(result.info) == 1
    assert "MAIL_SERVER" in result.info[0].detail


def test_d3_skips_when_env_section_missing(fake_repo):
    _write(fake_repo, "backend/.env.example", "ANTHROPIC_API_KEY=x\n")
    _write(fake_repo, "CLAUDE.md", "# CLAUDE.md\n\nPas de section env.\n")

    result = hygiene.Result()
    hygiene.detect_env_sync(result)

    assert result.drift == []
    assert result.skipped


# ─── D4 · Eval gaps ───────────────────────────────────────────────────────────


def test_d4_flags_reason_absent_from_dataset(fake_repo):
    _write(fake_repo, "backend/app/services/guard.py", 'REASON_BUDGET = "labor_budget_exceeded"\n')
    _write(fake_repo, "eval/golden_dataset.jsonl", '{"id":"fcst-001","category":"normal_day"}\n')

    result = hygiene.Result()
    hygiene.detect_eval_gaps(result)

    assert len(result.drift) == 1
    assert "labor_budget_exceeded" in result.drift[0].title
    assert "backend/app/services/guard.py" in result.drift[0].detail


def test_d4_covered_reason_is_clean(fake_repo):
    _write(fake_repo, "backend/app/services/guard.py", 'REASON_TIER1 = "confidence_below_threshold"\n')
    _write(
        fake_repo,
        "eval/golden_dataset.jsonl",
        '{"id":"g-001","failure_trigger":"confidence_below_threshold"}\n',
    )

    result = hygiene.Result()
    hygiene.detect_eval_gaps(result)

    assert result.findings == []


def test_d4_matches_reason_constants_containing_digits(fake_repo):
    """`REASON_TIER1` must parse — a `[A-Z_]`-only pattern would silently skip it."""
    _write(fake_repo, "backend/app/services/guard.py", 'REASON_TIER2 = "cold_start_drift"\n')
    _write(fake_repo, "eval/golden_dataset.jsonl", "{}\n")

    result = hygiene.Result()
    hygiene.detect_eval_gaps(result)

    assert len(result.drift) == 1
    assert "cold_start_drift" in result.drift[0].title


def test_d4_skips_pycache(fake_repo):
    _write(fake_repo, "backend/app/services/__pycache__/guard.py", 'REASON_X = "ghost_reason"\n')
    _write(fake_repo, "eval/golden_dataset.jsonl", "{}\n")

    result = hygiene.Result()
    hygiene.detect_eval_gaps(result)

    assert result.findings == []


# ─── Report ───────────────────────────────────────────────────────────────────


def test_report_states_clean_when_no_drift():
    report = hygiene.render_report(hygiene.Result(), "2026-07-26")

    assert "Aucun drift détecté" in report
    assert "drift_count: 0" in report


def test_report_lists_every_detector_and_counts_drift():
    result = hygiene.Result()
    result.findings.append(hygiene.Finding("D2", "chemin cassé", "detail"))
    result.findings.append(hygiene.Finding("D3", "var non déclarée", "detail", severity="info"))

    report = hygiene.render_report(result, "2026-07-26")

    assert "drift_count: 1" in report
    for code, label, _ in hygiene.DETECTORS:
        assert f"## {code} · {label}" in report
    assert "chemin cassé" in report

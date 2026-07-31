"""HOS-320 (Story 16.18) — hygiene_architecturale unit tests.

Each detector is exercised against a synthetic repo built in tmp_path, so the
tests assert detector *logic* rather than the current state of the real repo
(which changes every time drift is fixed). No network, no secrets.
"""
from __future__ import annotations

import importlib.util
import json
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


def test_d1_missing_harness_file_is_drift_not_skip(fake_repo):
    """The CI false negative: AGENTS.md untracked made D1 report "clean"."""
    _write(fake_repo, "CLAUDE.md", "# CLAUDE.md\n")

    result = hygiene.Result()
    hygiene.detect_harness_drift(result)

    assert result.skipped == []
    assert len(result.drift) == 1
    assert "AGENTS.md" in result.drift[0].title
    assert "introuvable" in result.drift[0].title


def test_d1_missing_canonical_is_drift_too(fake_repo):
    _write(fake_repo, "AGENTS.md", "# AGENTS.md\n")

    result = hygiene.Result()
    hygiene.detect_harness_drift(result)

    assert result.skipped == []
    assert len(result.drift) == 1
    assert "CLAUDE.md" in result.drift[0].title


def test_d1_exception_suppresses_a_justified_divergence(fake_repo, monkeypatch):
    monkeypatch.setattr(
        hygiene, "HARNESS_EXCEPTIONS", {r"^\*\*BMad modes\*\*": "conventions propres à chaque harness"}
    )
    _write(fake_repo, "CLAUDE.md", "# CLAUDE.md\n\n**BMad modes** — Claude\ncommun\n")
    _write(fake_repo, "AGENTS.md", "# AGENTS.md\n\n**BMad modes** — Codex\ncommun\n")

    result = hygiene.Result()
    hygiene.detect_harness_drift(result)

    assert result.drift == []


def test_d1_exception_does_not_mask_other_drift(fake_repo, monkeypatch):
    monkeypatch.setattr(hygiene, "HARNESS_EXCEPTIONS", {r"^\*\*BMad modes\*\*": "justifié"})
    _write(fake_repo, "CLAUDE.md", "# CLAUDE.md\n\n**BMad modes** — Claude\nLLM_MODEL claude-sonnet-4-6\n")
    _write(fake_repo, "AGENTS.md", "# AGENTS.md\n\n**BMad modes** — Codex\nLLM_MODEL Codex-sonnet-4-6\n")

    result = hygiene.Result()
    hygiene.detect_harness_drift(result)

    assert len(result.drift) == 1
    assert "Codex-sonnet-4-6" in result.drift[0].detail
    assert "BMad" not in result.drift[0].detail


def test_d1_stale_exception_is_reported(fake_repo, monkeypatch):
    """An exception matching nothing is an unkept promise — same rule as PLANNED_PATHS."""
    monkeypatch.setattr(hygiene, "HARNESS_EXCEPTIONS", {r"^ZZZ jamais présent": "obsolète"})
    body = "# CLAUDE.md\n\ncommun\n"
    _write(fake_repo, "CLAUDE.md", body)
    _write(fake_repo, "AGENTS.md", body.replace("CLAUDE.md", "AGENTS.md"))

    result = hygiene.Result()
    hygiene.detect_harness_drift(result)

    assert result.drift == []
    assert len(result.info) == 1
    assert "périmée" in result.info[0].title


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


def test_d2_resolves_paths_carrying_line_anchors(fake_repo, monkeypatch):
    """`file.py:128` and `file.py:128,141` are ordinary citation forms."""
    monkeypatch.setattr(hygiene, "DOC_SOURCES", ["CLAUDE.md"])
    _write(fake_repo, "backend/app/core/config.py", "x")
    _write(fake_repo, "CLAUDE.md", "Voir `backend/app/core/config.py:128,141` et `backend/app/core/config.py:12`.")

    result = hygiene.Result()
    hygiene.detect_doc_paths(result)

    assert result.findings == []


def test_d2_line_anchor_on_missing_file_still_flags(fake_repo, monkeypatch):
    monkeypatch.setattr(hygiene, "DOC_SOURCES", ["CLAUDE.md"])
    monkeypatch.setattr(hygiene, "PLANNED_PATHS", {})
    _write(fake_repo, "CLAUDE.md", "Voir `backend/app/ghost.py:42`.")

    result = hygiene.Result()
    hygiene.detect_doc_paths(result)

    assert len(result.drift) == 1
    assert "backend/app/ghost.py" in result.drift[0].title


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


def _env_doc_table(*names):
    """The shape the extracted doc uses since 30/07 (Markdown table)."""
    rows = "\n".join("| `%s` | description |" % n for n in names)
    return "# Variables\n\n| Variable | Role |\n|---|---|\n" + rows + "\n"


def _env_doc_block(*names):
    """The original shape (`VAR - description` in a code block). Still supported."""
    lines = "\n".join("%s     — description" % n for n in names)
    return "# Variables\n\n```\n" + lines + "\n```\n"


def test_d3_flags_documented_but_undeclared_var(fake_repo):
    _write(fake_repo, "backend/.env.example", "ANTHROPIC_API_KEY=sk-ant-...\n")
    _write(fake_repo, hygiene.ENV_DOC, _env_doc_table("ANTHROPIC_API_KEY", "LOGFIRE_TOKEN"))

    result = hygiene.Result()
    hygiene.detect_env_sync(result)

    assert len(result.drift) == 1
    assert "LOGFIRE_TOKEN" in result.drift[0].title


def test_d3_undocumented_var_is_info_only(fake_repo):
    """`.env.example` is exhaustive; the doc carries a curated subset."""
    _write(fake_repo, "backend/.env.example", "ANTHROPIC_API_KEY=x\nMAIL_SERVER=mailhog\n")
    _write(fake_repo, hygiene.ENV_DOC, _env_doc_table("ANTHROPIC_API_KEY"))

    result = hygiene.Result()
    hygiene.detect_env_sync(result)

    assert result.drift == []
    assert len(result.info) == 1
    assert "MAIL_SERVER" in result.info[0].detail


def test_d3_still_reads_the_legacy_code_block_shape(fake_repo):
    """The doc moved out of CLAUDE.md on 30/07; both shapes must keep parsing."""
    _write(fake_repo, "backend/.env.example", "ANTHROPIC_API_KEY=x\nLOGFIRE_TOKEN=y\n")
    _write(fake_repo, hygiene.ENV_DOC, _env_doc_block("ANTHROPIC_API_KEY", "LOGFIRE_TOKEN"))

    result = hygiene.Result()
    hygiene.detect_env_sync(result)

    assert result.drift == []


def test_d3_unreadable_doc_is_drift_not_silence(fake_repo):
    """Zero parsed variables must shout.

    Extracting the section on 30/07 without repointing D3 would have left it
    reading an empty heading and reporting every var as 'undocumented' info -
    a detector that sees nothing while printing clean.
    """
    _write(fake_repo, "backend/.env.example", "ANTHROPIC_API_KEY=x\n")
    _write(fake_repo, hygiene.ENV_DOC, "# Variables\n\nAucune variable ici.\n")

    result = hygiene.Result()
    hygiene.detect_env_sync(result)

    assert len(result.drift) == 1
    assert "aveugle" in result.drift[0].detail


def test_d3_skips_when_doc_missing(fake_repo):
    _write(fake_repo, "backend/.env.example", "ANTHROPIC_API_KEY=x\n")

    result = hygiene.Result()
    hygiene.detect_env_sync(result)

    assert result.drift == []
    assert result.skipped


# ─── D5 · Plafond de lignes ───────────────────────────────────────────────────


def _sized_doc(limit, lines):
    head = "> **Regle.** plafond dur %d lignes\n" % limit
    return head + "\n".join("ligne %d" % i for i in range(lines - 1)) + "\n"


def _only_claude(monkeypatch):
    monkeypatch.setattr(hygiene, "DOC_SIZE_LIMITS", ["CLAUDE.md"])


def test_d5_under_the_ceiling_is_clean(fake_repo, monkeypatch):
    _only_claude(monkeypatch)
    _write(fake_repo, "CLAUDE.md", _sized_doc(170, 50))

    result = hygiene.Result()
    hygiene.detect_doc_size(result)

    assert result.findings == []


def test_d5_flags_overflow_with_the_delta(fake_repo, monkeypatch):
    _only_claude(monkeypatch)
    _write(fake_repo, "CLAUDE.md", _sized_doc(150, 196))

    result = hygiene.Result()
    hygiene.detect_doc_size(result)

    assert len(result.drift) == 1
    assert "196" in result.drift[0].title and "150" in result.drift[0].title
    assert "+46" in result.drift[0].detail


def test_d5_ceiling_is_read_from_the_file_not_hardcoded(fake_repo, monkeypatch):
    """Raising the declared ceiling must be enough to clear the finding.

    A limit duplicated in this script and in the doc is exactly the divergence
    D6 exists to catch - so D5 must never hold its own copy.
    """
    _only_claude(monkeypatch)
    _write(fake_repo, "CLAUDE.md", _sized_doc(400, 196))

    result = hygiene.Result()
    hygiene.detect_doc_size(result)

    assert result.findings == []


def test_d5_missing_declaration_is_drift(fake_repo, monkeypatch):
    _only_claude(monkeypatch)
    _write(fake_repo, "CLAUDE.md", "# Sans regle de plafond\n")

    result = hygiene.Result()
    hygiene.detect_doc_size(result)

    assert len(result.drift) == 1
    assert "plafond" in result.drift[0].title


# ─── D6 · Coherence des comptes ───────────────────────────────────────────────


def _decisions(n):
    return "\n".join("### %d — Decision %d\n\nDetail.\n" % (i, i) for i in range(1, n + 1))


def test_d6_matching_count_is_clean(fake_repo):
    _write(fake_repo, "docs/context/decisions-architecturales.md", _decisions(29))
    _write(fake_repo, "CLAUDE.md", "Index des 29 decisions architecturales.\n")

    result = hygiene.Result()
    hygiene.detect_count_coherence(result)

    assert result.findings == []


def test_d6_flags_every_stale_claim(fake_repo):
    """The real case, 31/07: three figures live for the same set."""
    _write(
        fake_repo,
        "docs/context/decisions-architecturales.md",
        "Detail des 24 décisions.\n" + _decisions(29),
    )
    _write(fake_repo, "AGENTS.md", "24 décisions architecturales\n")
    _write(fake_repo, "docs/INDEX.md", "detail des 31 décisions\n")

    result = hygiene.Result()
    hygiene.detect_count_coherence(result)

    assert len(result.drift) == 3
    assert all("29" in f.title for f in result.drift)


def test_d6_blind_when_entry_pattern_matches_nothing(fake_repo):
    _write(fake_repo, "docs/context/decisions-architecturales.md", "Aucune section au format attendu.\n")

    result = hygiene.Result()
    hygiene.detect_count_coherence(result)

    assert len(result.drift) == 1
    assert "aveugle" in result.drift[0].detail


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


def test_detectors_flag_runs_only_the_selected_one(fake_repo, monkeypatch, capsys):
    """The blocking PR gate runs `--detectors D1`; D2/D3/D4 must stay silent."""
    _write(fake_repo, "CLAUDE.md", "# CLAUDE.md\n\nVoir `docs/ghost.md`.\n")
    _write(fake_repo, "AGENTS.md", "# AGENTS.md\n\nVoir `docs/ghost.md`.\n")
    monkeypatch.setattr(sys, "argv", ["hygiene", "--detectors", "D1", "--json"])

    assert hygiene.main() == 0  # D2 would have flagged docs/ghost.md

    payload = json.loads(capsys.readouterr().out)
    assert payload["drift_count"] == 0
    assert {f["detector"] for f in payload["findings"]} <= {"D1"}


def test_detectors_flag_still_fails_on_selected_drift(fake_repo, monkeypatch):
    _write(fake_repo, "CLAUDE.md", '# CLAUDE.md\n\nLLM_MODEL "claude-sonnet-4-6"\n')
    _write(fake_repo, "AGENTS.md", '# AGENTS.md\n\nLLM_MODEL "Codex-sonnet-4-6"\n')
    monkeypatch.setattr(sys, "argv", ["hygiene", "--detectors", "D1", "--json"])

    assert hygiene.main() == 1


def test_unknown_detector_code_is_an_error_not_a_silent_pass(monkeypatch):
    """A typo in the CI invocation must not look like a green run."""
    monkeypatch.setattr(sys, "argv", ["hygiene", "--detectors", "D9"])

    assert hygiene.main() == 2


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

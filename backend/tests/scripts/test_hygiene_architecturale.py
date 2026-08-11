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


def _iso_days_ago(days: int) -> str:
    import datetime as _dt
    when = _dt.datetime.now(_dt.timezone.utc) - _dt.timedelta(days=days)
    return when.strftime("%Y-%m-%dT%H:%M:%SZ")


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


# ─── D7 · Honnetete metriques ─────────────────────────────────────────────────


def test_d7_flags_the_bare_synthetic_mape(fake_repo):
    """The failure this detector exists for: the number, alone, as evidence."""
    _write(fake_repo, "README.md", "**Forecast accuracy:** 15.09% MAPE on J+1 covers.\n")

    result = hygiene.Result()
    hygiene.detect_metric_honesty(result)

    assert len(result.drift) == 1
    assert "README.md:1" in result.drift[0].title


def test_d7_accepts_a_qualified_occurrence(fake_repo):
    _write(
        fake_repo,
        "README.md",
        "MAPE 15.09% on a synthetic dataset — internal non-regression gate only.\n",
    )

    result = hygiene.Result()
    hygiene.detect_metric_honesty(result)

    assert result.findings == []


def test_d7_accepts_the_comma_decimal_form(fake_repo):
    """French prose writes 15,09 — the same claim must not slip through."""
    _write(fake_repo, "docs/pitch.md", "Notre MAPE J+1 de 15,09 % nous place au niveau du marché.\n")
    _write(fake_repo, "docs/ok.md", "Le 15,09 % est circulaire : il ne prouve rien.\n")

    result = hygiene.Result()
    hygiene.detect_metric_honesty(result)

    assert [f.title.split("`")[1] for f in result.drift] == ["docs/pitch.md:1"]


def test_d7_qualifier_counts_across_the_window_not_the_line(fake_repo):
    """A table row cannot hold its own caveat; the surrounding block may."""
    _write(
        fake_repo,
        "docs/kit.md",
        "> Chiffre synthétique, sans valeur probante.\n\n| MAPE J+1 | 15.09% |\n",
    )

    result = hygiene.Result()
    hygiene.detect_metric_honesty(result)

    assert result.findings == []


def test_d7_window_does_not_stretch_to_a_distant_caveat(fake_repo):
    _write(
        fake_repo,
        "docs/kit.md",
        "> Chiffre synthétique.\n\n\n\n| MAPE J+1 | 15.09% |\n",
    )

    result = hygiene.Result()
    hygiene.detect_metric_honesty(result)

    assert len(result.drift) == 1


def test_d7_skips_the_documented_exceptions(fake_repo, monkeypatch):
    monkeypatch.setattr(hygiene, "METRIC_CLAIM_EXCEPTIONS", {"docs/adr/": "enregistrement daté"})
    _write(fake_repo, "docs/adr/0007-eval.md", "Le MAPE 15.09% est une mesure ponctuelle.\n")

    result = hygiene.Result()
    hygiene.detect_metric_honesty(result)

    assert result.findings == []


def test_d7_reports_when_it_scanned_nothing(fake_repo):
    """An empty scan is a blind run, not a clean one."""
    result = hygiene.Result()
    hygiene.detect_metric_honesty(result)

    assert result.findings == []
    assert any("D7" in s for s in result.skipped)


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
    """A typo in the CI invocation must not look like a green run.

    The placeholder is deliberately far from the real range: this test used to
    say "D9", which stopped testing anything the day D9 shipped (HOS-324) and
    failed instead. A sentinel that a future story can claim is not a sentinel.
    """
    monkeypatch.setattr(sys, "argv", ["hygiene", "--detectors", "D99"])

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


# ─── D9 · Branches et PRs orphelines ──────────────────────────────────────────
#
# `_gh` is monkeypatched in every case: the suite must never touch the network,
# and a detector whose tests need credentials would only run on one machine.


def _fake_forge(monkeypatch, branches, prs, repos=("owner/repo",), default="main"):
    """Route the three `gh` calls D9 makes to canned payloads."""
    monkeypatch.setattr(hygiene, "WATCHED_REPOS", list(repos))
    monkeypatch.setattr(hygiene.shutil, "which", lambda _: "/usr/bin/gh")

    def fake_gh(args):
        if args[0] == "api" and args[1].endswith("/branches"):
            return branches
        if args[0] == "api":
            return {"default_branch": default}
        return prs

    monkeypatch.setattr(hygiene, "_gh", fake_gh)


def _pr(number, state, head, *, updated="2099-01-01T00:00:00Z", mergeable="MERGEABLE"):
    return {
        "number": number,
        "state": state,
        "headRefName": head,
        "updatedAt": updated,
        "mergeable": mergeable,
        "title": f"PR {number}",
        "isDraft": False,
    }


def test_d9_branch_without_any_pr_is_drift(monkeypatch):
    """The Story 16.20 case: work pushed, never submitted, invisible."""
    _fake_forge(monkeypatch, ["main", "chore/hos-hygiene-conventions-docs"], [])

    result = hygiene.Result()
    hygiene.detect_orphan_branches(result)

    assert len(result.drift) == 1
    assert "poussée sans aucune PR" in _titles(result)


def test_d9_default_branch_is_never_reported(monkeypatch):
    _fake_forge(monkeypatch, ["main"], [])

    result = hygiene.Result()
    hygiene.detect_orphan_branches(result)

    assert result.findings == []


def test_d9_excepted_branches_are_ignored(monkeypatch):
    _fake_forge(monkeypatch, ["main", "dependabot/pip/urllib3-2.0.0"], [])

    result = hygiene.Result()
    hygiene.detect_orphan_branches(result)

    assert result.findings == []


def test_d9_conflicting_open_pr_is_drift(monkeypatch):
    """The meta-repo PR #1 case: superseded, conflicting, open on the public README."""
    _fake_forge(
        monkeypatch,
        ["main", "feature/x"],
        [_pr(1, "OPEN", "feature/x", mergeable="CONFLICTING")],
    )

    result = hygiene.Result()
    hygiene.detect_orphan_branches(result)

    assert len(result.drift) == 1
    assert "stagne" in _titles(result)
    assert "en conflit" in result.drift[0].detail


def test_d9_stale_open_pr_is_drift(monkeypatch):
    _fake_forge(
        monkeypatch,
        ["main", "feature/x"],
        [_pr(2, "OPEN", "feature/x", updated="2020-01-01T00:00:00Z")],
    )

    result = hygiene.Result()
    hygiene.detect_orphan_branches(result)

    assert len(result.drift) == 1
    assert "n'a pas bougé" in result.drift[0].detail


def test_d9_healthy_open_pr_is_clean(monkeypatch):
    _fake_forge(monkeypatch, ["main", "feature/x"], [_pr(3, "OPEN", "feature/x")])

    result = hygiene.Result()
    hygiene.detect_orphan_branches(result)

    assert result.findings == []


def test_d9_branch_surviving_merged_pr_is_info_not_drift(monkeypatch):
    """Cruft must not fail a report — a detector that shouts stops being read."""
    _fake_forge(monkeypatch, ["main", "feature/done"], [_pr(4, "MERGED", "feature/done")])

    result = hygiene.Result()
    hygiene.detect_orphan_branches(result)

    assert result.drift == []
    assert len(result.info) == 1
    assert "survit à ses PRs" in _titles(result)


def test_d9_without_gh_records_a_skip_never_clean(monkeypatch):
    """AC5: a blind detector says so. Reporting clean here is the false negative."""
    monkeypatch.setattr(hygiene.shutil, "which", lambda _: None)

    result = hygiene.Result()
    hygiene.detect_orphan_branches(result)

    assert result.findings == []
    assert len(result.skipped) == 1
    assert "gh" in result.skipped[0]


def test_d9_unreachable_repo_records_a_skip(monkeypatch):
    """An unauthenticated or rate-limited call must not read as "no orphans"."""
    monkeypatch.setattr(hygiene, "WATCHED_REPOS", ["owner/repo"])
    monkeypatch.setattr(hygiene.shutil, "which", lambda _: "/usr/bin/gh")
    monkeypatch.setattr(hygiene, "_gh", lambda args: None)

    result = hygiene.Result()
    hygiene.detect_orphan_branches(result)

    assert result.findings == []
    assert any("inaccessible" in s for s in result.skipped)
    assert any("aveugle" in s for s in result.skipped)


def test_d9_watches_more_than_the_current_repo(monkeypatch):
    """AC4: the costly incident was on the meta-repo, not here."""
    assert len(hygiene.WATCHED_REPOS) >= 2
    assert any("hospitality-agentic-mesh" in r for r in hygiene.WATCHED_REPOS)


# ─── D10 · Cron d'hygiène en vie ──────────────────────────────────────────────


def _fake_runs(monkeypatch, payload):
    monkeypatch.setattr(hygiene.shutil, "which", lambda _: "/usr/bin/gh")
    monkeypatch.setattr(hygiene, "_gh", lambda args: payload)


def test_d10_recent_run_is_clean(monkeypatch):
    _fake_runs(monkeypatch, [{"created_at": _iso_days_ago(2), "html_url": "u"}])

    result = hygiene.Result()
    hygiene.detect_cron_liveness(result)

    assert result.findings == []


def test_d10_silent_cron_is_drift(monkeypatch):
    """Silence from a reporting job is not evidence of a clean week."""
    _fake_runs(monkeypatch, [{"created_at": _iso_days_ago(40), "html_url": "u"}])

    result = hygiene.Result()
    hygiene.detect_cron_liveness(result)

    assert len(result.drift) == 1
    assert "muet depuis 40 jours" in result.drift[0].title


def test_d10_workflow_that_never_succeeded_is_drift(monkeypatch):
    _fake_runs(monkeypatch, [])

    result = hygiene.Result()
    hygiene.detect_cron_liveness(result)

    assert len(result.drift) == 1
    assert "aucun run réussi" in result.drift[0].title


def test_d10_unreadable_state_records_a_skip(monkeypatch):
    """Same rule as D9: no verdict is not a clean verdict."""
    monkeypatch.setattr(hygiene.shutil, "which", lambda _: "/usr/bin/gh")
    monkeypatch.setattr(hygiene, "_gh", lambda args: None)

    result = hygiene.Result()
    hygiene.detect_cron_liveness(result)

    assert result.findings == []
    assert any("illisible" in s for s in result.skipped)


# ─── D11 · CI de main au rouge ────────────────────────────────────────────────


def test_d11_green_main_is_clean(monkeypatch):
    _fake_runs(
        monkeypatch,
        [{"created_at": _iso_days_ago(9), "conclusion": "success", "html_url": "u"}],
    )

    result = hygiene.Result()
    hygiene.detect_red_main(result)

    assert result.findings == []


def test_d11_fresh_red_is_not_yet_drift(monkeypatch):
    """A red caught and fixed the same day is normal operation, not drift."""
    _fake_runs(
        monkeypatch,
        [{"created_at": _iso_days_ago(1), "conclusion": "failure", "html_url": "u"}],
    )

    result = hygiene.Result()
    hygiene.detect_red_main(result)

    assert result.findings == []


def test_d11_installed_red_is_drift(monkeypatch):
    """The 2026-08-05 incident: red for six days, four PRs merged on top."""
    _fake_runs(
        monkeypatch,
        [{"created_at": _iso_days_ago(6), "conclusion": "failure", "html_url": "u"}],
    )

    result = hygiene.Result()
    hygiene.detect_red_main(result)

    assert len(result.drift) == 1
    assert "rouge depuis 6 jours" in result.drift[0].title


def test_d11_non_failure_conclusions_still_count(monkeypatch):
    """`cancelled` and `timed_out` leave main just as unverified as `failure`."""
    _fake_runs(
        monkeypatch,
        [{"created_at": _iso_days_ago(5), "conclusion": "timed_out", "html_url": "u"}],
    )

    result = hygiene.Result()
    hygiene.detect_red_main(result)

    assert len(result.drift) == 1


def test_d11_unreadable_state_records_a_skip(monkeypatch):
    """Same rule as D9/D10: no verdict is not a clean verdict."""
    monkeypatch.setattr(hygiene.shutil, "which", lambda _: "/usr/bin/gh")
    monkeypatch.setattr(hygiene, "_gh", lambda args: None)

    result = hygiene.Result()
    hygiene.detect_red_main(result)

    assert result.findings == []
    assert any("illisible" in s for s in result.skipped)


def test_d11_stays_out_of_the_blocking_subset():
    """Enforcement gap is not the current author's fault — same posture as D10."""
    blocking = {"D1", "D5", "D6"}
    assert "D11" not in blocking


# ─── --fix · resynchronisation du harnais ─────────────────────────────────────


def test_fix_regenerates_the_derived_harness(fake_repo):
    _write(fake_repo, "CLAUDE.md", "# CLAUDE.md\n\nVoir `CLAUDE.md` §X.\n")
    _write(fake_repo, "AGENTS.md", "# AGENTS.md\n\nversion périmée\n")

    assert hygiene.fix_harness() == 0

    produced = (fake_repo / "AGENTS.md").read_text(encoding="utf-8")
    assert produced == "# AGENTS.md\n\nVoir `AGENTS.md` §X.\n"


def test_fix_is_idempotent(fake_repo):
    body = "# CLAUDE.md\n\ncontenu\n"
    _write(fake_repo, "CLAUDE.md", body)
    _write(fake_repo, "AGENTS.md", body.replace("CLAUDE.md", "AGENTS.md"))

    assert hygiene.fix_harness() == 0
    once = (fake_repo / "AGENTS.md").read_text(encoding="utf-8")
    assert hygiene.fix_harness() == 0
    assert (fake_repo / "AGENTS.md").read_text(encoding="utf-8") == once


def test_fix_output_satisfies_d1(fake_repo):
    """The fix must actually close the gate it exists to close."""
    _write(fake_repo, "CLAUDE.md", "# CLAUDE.md\n\nLLM — `claude-sonnet-4-6`\n")
    _write(fake_repo, "AGENTS.md", "# AGENTS.md\n\nLLM — `Codex-sonnet-4-6`\n")

    hygiene.fix_harness()

    result = hygiene.Result()
    hygiene.detect_harness_drift(result)
    assert result.drift == []


def test_fix_without_canonical_is_an_error(fake_repo):
    assert hygiene.fix_harness() == 2


# ─── Exclusion de scan ────────────────────────────────────────────────────────


def test_scan_excludes_nested_worktrees_and_vendor_trees():
    assert hygiene._scan_excluded(".claude/worktrees/x/docs/a.md")
    assert hygiene._scan_excluded(".git/COMMIT_EDITMSG")
    assert hygiene._scan_excluded("backend/.venv/lib/x.md")
    assert hygiene._scan_excluded("ui/node_modules/pkg/readme.md")
    assert not hygiene._scan_excluded("docs/context/moat.md")


def test_d7_ignores_a_stale_worktree_copy(fake_repo, monkeypatch):
    """A dead copy of the repo must not be able to fail a detector."""
    monkeypatch.setattr(hygiene, "METRIC_CLAIM_EXCEPTIONS", {})
    _write(fake_repo, ".claude/worktrees/old/docs/pitch.md", "MAPE 15.09% en production\n")

    result = hygiene.Result()
    hygiene.detect_metric_honesty(result)

    assert result.findings == []


# ─── D6 · deuxième famille — chiffres issus d'un artefact ─────────────────────
#
# The 2026-08-02 bug: 829 (the dataset) published as the benchmark sample (30),
# on five surfaces at once, while the JSON next to them said n_stores: 30.


def _benchmark_repo(root: Path, doc: str, *, n_stores: int = 30, scored: int = 1193) -> None:
    _write(
        root,
        hygiene.FIGURE_SOURCE,
        json.dumps({"protocol": {"n_stores": n_stores, "scored_points": scored}}),
    )
    _write(root, "docs/claim.md", doc)


def test_d6_flags_the_dataset_size_passed_off_as_the_sample(fake_repo):
    _benchmark_repo(fake_repo, "On 829 real restaurants (Kaggle Recruit), Prophet wins.\n")

    result = hygiene.Result()
    hygiene._check_figure_claims(result)

    assert len(result.drift) == 1
    assert "829 restaurants du benchmark" in result.drift[0].title
    assert "30" in result.drift[0].title


def test_d6_accepts_the_dataset_size_when_named_as_such(fake_repo):
    """State the role and the number is correct — same escape valve as D7/D8."""
    _benchmark_repo(
        fake_repo,
        "Benchmark Recruit : 30 restaurants tirés d'un dataset de 829 restaurants.\n",
    )

    result = hygiene.Result()
    hygiene._check_figure_claims(result)

    assert result.findings == []


def test_d6_ignores_restaurant_counts_outside_the_benchmark(fake_repo):
    """Scope, not just matching: scale scenarios and pricing tiers are not claims."""
    _benchmark_repo(fake_repo, "Scale scenarios modeled (1 -> 50 -> 500 restaurants).\n")

    result = hygiene.Result()
    hygiene._check_figure_claims(result)

    assert result.findings == []


def test_d6_flags_a_stale_scored_points_figure(fake_repo):
    """The real recurring risk: the benchmark is rerun and the prose is not."""
    _benchmark_repo(fake_repo, "Benchmark Recruit : 900 points scorés par modèle.\n")

    result = hygiene.Result()
    hygiene._check_figure_claims(result)

    assert len(result.drift) == 1
    assert "points scorés" in result.drift[0].title


def test_d6_accepts_a_floor_rather_than_a_result(fake_repo):
    """"≥ 300 points scorés" specifies a future run, not what HOS-307 produced."""
    _benchmark_repo(fake_repo, "Protocole HOS-308, benchmark : ≥ 300 points scorés.\n")

    result = hygiene.Result()
    hygiene._check_figure_claims(result)

    assert result.findings == []


def test_d6_leaves_archived_and_local_only_trees_alone(fake_repo):
    _write(
        fake_repo,
        hygiene.FIGURE_SOURCE,
        json.dumps({"protocol": {"n_stores": 30, "scored_points": 1193}}),
    )
    _write(fake_repo, "docs/_archive/old.md", "Benchmark Recruit sur 829 restaurants.\n")

    result = hygiene.Result()
    hygiene._check_figure_claims(result)

    assert result.findings == []


def test_d6_missing_benchmark_source_is_a_skip_not_clean(fake_repo):
    _write(fake_repo, "docs/claim.md", "Benchmark Recruit sur 829 restaurants.\n")

    result = hygiene.Result()
    hygiene._check_figure_claims(result)

    assert result.findings == []
    assert any(hygiene.FIGURE_SOURCE in s for s in result.skipped)


def test_d6_still_checks_counts(fake_repo, monkeypatch):
    """The first family must survive the second."""
    monkeypatch.setattr(hygiene, "FIGURE_CLAIMS", ())
    monkeypatch.setattr(
        hygiene,
        "COUNT_CLAIMS",
        [{
            "label": "décisions",
            "claim": __import__("re").compile(r"(\d+)\s+décisions"),
            "scanned": ["CLAUDE.md"],
            "source": "src.md",
            "entry": __import__("re").compile(r"^### \d+ — ", __import__("re").MULTILINE),
        }],
    )
    _write(fake_repo, "src.md", "### 1 — a\n### 2 — b\n")
    _write(fake_repo, "CLAUDE.md", "Le projet compte 7 décisions.\n")
    _write(fake_repo, hygiene.FIGURE_SOURCE, json.dumps({"protocol": {}}))

    result = hygiene.Result()
    hygiene.detect_count_coherence(result)

    assert len(result.drift) == 1
    assert "annonce 7 décisions" in result.drift[0].title

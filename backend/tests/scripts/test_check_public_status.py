"""check_public_status — the gate on what the public meta-repo may say about Aetherix.

Pure: `validate` gets the parsed data, an `exists` seam and a fixed `today`.
No file system beyond the real public-status.yml smoke test at the end.
"""
from __future__ import annotations

import copy
import importlib.util
import sys
from datetime import date
from pathlib import Path

import pytest

_REPO = Path(__file__).resolve().parents[3]
_spec = importlib.util.spec_from_file_location(
    "check_public_status", _REPO / "scripts" / "ci" / "check_public_status.py"
)
gate = importlib.util.module_from_spec(_spec)
sys.modules[_spec.name] = gate  # dataclasses resolve their module by name
_spec.loader.exec_module(gate)

TODAY = date(2026, 9, 25)
EXISTING = {"backend/app/main.py", "docs/adr/0013-decision-autonomy-policy.md"}


def _exists(path: str) -> bool:
    return path in EXISTING


def _entry(**overrides) -> dict:
    entry = {
        "id": "decision-recap",
        "name": "Decision recap",
        "status": "Built",
        "deployed": "unknown",
        "description": "Deterministic recap of recent decisions and outcomes.",
        "verified_on": date(2026, 9, 25),
        "evidence": ["backend/app/main.py"],
    }
    entry.update(overrides)
    return entry


def _doc(*entries, **top) -> dict:
    doc = {"schema_version": 1, "max_age_days": 60, "entries": list(entries) or [_entry()]}
    doc.update(top)
    return doc


def _run(doc, **kw):
    return gate.validate(doc, _exists, TODAY, **kw)


# --- happy path ------------------------------------------------------------

def test_valid_document_passes():
    report = _run(_doc())
    assert report.ok, report.errors
    assert report.warnings == []


def test_verified_on_accepts_iso_string():
    assert _run(_doc(_entry(verified_on="2026-09-01"))).ok


# --- schema ----------------------------------------------------------------

@pytest.mark.parametrize("doc", [None, [], "x"])
def test_top_level_must_be_mapping(doc):
    assert not _run(doc).ok


def test_schema_version_required():
    assert not _run(_doc(schema_version=2)).ok


def test_unknown_top_level_key_rejected():
    assert not _run(_doc(owner="someone")).ok


def test_empty_entries_rejected():
    assert not _run({"schema_version": 1, "entries": []}).ok


def test_unknown_entry_key_rejected():
    """A stray field could carry private text into the file unchecked."""
    report = _run(_doc(_entry(internal_note="see HOS-12")))
    assert any("unknown key" in e for e in report.errors)


@pytest.mark.parametrize("key", ["id", "name", "status", "deployed", "description", "verified_on"])
def test_required_keys(key):
    entry = _entry()
    del entry[key]
    assert not _run(_doc(entry)).ok


def test_id_must_be_kebab_case():
    assert not _run(_doc(_entry(id="Decision_Recap"))).ok


def test_duplicate_ids_rejected():
    report = _run(_doc(_entry(), _entry(name="Other")))
    assert any("duplicate id" in e for e in report.errors)


def test_description_must_be_one_line():
    assert not _run(_doc(_entry(description="line one\nline two"))).ok


def test_description_length_capped():
    assert not _run(_doc(_entry(description="x " * 200))).ok


# --- statuses and deployed ---------------------------------------------------

@pytest.mark.parametrize("status", gate.ALLOWED_STATUSES)
def test_every_allowed_status_accepted(status):
    evidence = ["backend/app/main.py"]
    deployed = "unknown" if status in gate.LIVE_CAPABLE_STATUSES else False
    assert _run(_doc(_entry(status=status, evidence=evidence, deployed=deployed))).ok


@pytest.mark.parametrize("status", ["Built (PoC)", "Live", "built", "Done"])
def test_unknown_status_rejected(status):
    assert not _run(_doc(_entry(status=status))).ok


@pytest.mark.parametrize("value", [True, False, "unknown", "n/a"])
def test_deployed_values_accepted(value):
    assert _run(_doc(_entry(deployed=value))).ok


@pytest.mark.parametrize("value", ["yes", "live", 1, 0, None])
def test_deployed_other_values_rejected(value):
    assert not _run(_doc(_entry(deployed=value))).ok


@pytest.mark.parametrize("status", ["Design", "Research", "Synthetic PoC", "In progress"])
def test_live_only_for_running_statuses(status):
    """'Live' next to a Design item would be a claim the code cannot back."""
    assert not _run(_doc(_entry(status=status, deployed=True))).ok


# --- evidence ----------------------------------------------------------------

def test_built_requires_evidence():
    report = _run(_doc(_entry(evidence=[])))
    assert any("requires at least one evidence" in e for e in report.errors)


def test_built_requires_every_evidence_path_to_exist():
    report = _run(_doc(_entry(evidence=["backend/app/main.py", "backend/app/gone.py"])))
    assert any("gone.py" in e for e in report.errors)


def test_missing_evidence_for_non_built_is_a_warning():
    report = _run(_doc(_entry(status="Design", deployed=False, evidence=["docs/adr/9999.md"])))
    assert report.ok
    assert any("9999.md" in w for w in report.warnings)


def test_non_built_may_have_no_evidence():
    entry = _entry(status="Research", deployed=False)
    del entry["evidence"]
    assert _run(_doc(entry)).ok


@pytest.mark.parametrize("path", ["/etc/passwd", "../other-repo/x.py", "backend\\app\\main.py"])
def test_evidence_must_be_repo_relative(path):
    assert not _run(_doc(_entry(evidence=[path]))).ok


def test_evidence_paths_are_not_leak_checked():
    """Evidence is internal by design and never rendered."""
    assert _run(_doc(_entry(evidence=["backend/app/main.py"]))).ok


# --- freshness -----------------------------------------------------------------

def test_stale_verified_on_is_a_warning_not_an_error():
    report = _run(_doc(_entry(verified_on=date(2026, 6, 1))))
    assert report.ok
    assert any("days old" in w for w in report.warnings)


def test_max_age_override():
    report = _run(_doc(_entry(verified_on=date(2026, 9, 1))), max_age_days=10)
    assert any("days old" in w for w in report.warnings)


def test_future_verified_on_rejected():
    assert not _run(_doc(_entry(verified_on=date(2026, 10, 1)))).ok


def test_invalid_verified_on_rejected():
    assert not _run(_doc(_entry(verified_on="last week"))).ok


@pytest.mark.parametrize("value", [0, -1, "60", True])
def test_max_age_days_must_be_positive_int(value):
    assert not _run(_doc(max_age_days=value)).ok


# --- leak denylist -------------------------------------------------------------

@pytest.mark.parametrize(
    "text",
    [
        "Implements ADR-0012.",
        "See adr 0012 for details.",
        "Follows the Signal Contract.",
        "Uses the signal-contract vocabulary.",
        "Shipped in HOS-123.",
        "Closes hos-7.",
        "As tranched by Décision #38.",
        "See Decision #41.",
        "Per decision n° 12.",
        "Detailed in §18.4.",
        "Code in aetherix-hospitality-ai.",
        "Lives in backend/app/services.",
        "See docs/context/learning-loop.md.",
        "Migration in supabase/migrations.",
        "Configured through the .env file.",
        "Try it at aetherix-backend.fly.dev.",
        "Contact someone@example.com.",
        "Key sk-ant-abcdefghijklmnopqrstuv.",
        "Token ghp_abcdefghijklmnopqrstuvwxyz0123.",
        "Account AC0123456789abcdef0123456789abcdef.",
        "api_key=abc123",
        "Blob aGVsbG8gd29ybGQgaGVsbG8gd29ybGQgaGVsbG8gd29ybGQ=",
    ],
)
def test_leaks_are_rejected_in_description(text):
    report = _run(_doc(_entry(description=text)))
    assert any("would leak" in e for e in report.errors), text


@pytest.mark.parametrize("field", ["id", "name", "description"])
def test_leak_check_covers_every_public_field(field):
    value = "hos-12" if field == "id" else "Recap (HOS-12)"
    report = _run(_doc(_entry(**{field: value})))
    assert any("would leak" in e for e in report.errors)


@pytest.mark.parametrize(
    "text",
    [
        "Offline evals block a merge on regression.",
        "Deterministic recap, no model, no estimated money.",
        "Tested on constructed data; nothing learned from real outcomes yet.",
        "Accept / reject buttons, waiting for messaging template approval.",
        "Benchmarked on real public restaurant data (level on the median).",
        "Uses an MCP server and a host agent; GPT-4 class models are not required.",
    ],
)
def test_plain_public_prose_is_not_flagged(text):
    assert gate.find_leaks(text) == []


# --- the real file ---------------------------------------------------------------

def test_repository_public_status_file_is_valid():
    """The committed file must pass — evidence resolved against the real repo."""
    data = gate.load(_REPO / "public-status.yml")
    report = gate.validate(copy.deepcopy(data), lambda p: (_REPO / p).exists(), date.today())
    assert report.ok, report.errors


def test_main_exit_codes(tmp_path):
    good = _REPO / "public-status.yml"
    assert gate.main(["--file", str(good), "--root", str(_REPO)]) == 0

    bad = tmp_path / "bad.yml"
    bad.write_text("schema_version: 1\nentries:\n  - id: x\n", encoding="utf-8")
    assert gate.main(["--file", str(bad), "--root", str(_REPO), "--today", "2026-09-25"]) == 1

    broken = tmp_path / "broken.yml"
    broken.write_text("entries: [unclosed\n", encoding="utf-8")
    assert gate.main(["--file", str(broken)]) == 2
    assert gate.main(["--file", str(tmp_path / "missing.yml")]) == 2

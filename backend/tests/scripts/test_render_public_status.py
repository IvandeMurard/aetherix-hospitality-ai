"""render_public_status — deterministic Markdown block + marker replacement."""
from __future__ import annotations

import importlib.util
import sys
from datetime import date
from pathlib import Path

import pytest

_REPO = Path(__file__).resolve().parents[3]
_SCRIPTS = _REPO / "scripts" / "ci"


def _load(name: str):
    spec = importlib.util.spec_from_file_location(name, _SCRIPTS / f"{name}.py")
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


gate = _load("check_public_status")
renderer = _load("render_public_status")


def _entry(**overrides) -> dict:
    entry = {
        "id": "decision-recap",
        "name": "Decision recap",
        "status": "Built",
        "deployed": "unknown",
        "description": "Deterministic recap of recent decisions and outcomes.",
        "verified_on": date(2026, 9, 25),
        "evidence": ["backend/app/services/decision_recap.py"],
    }
    entry.update(overrides)
    return entry


def _doc(*entries) -> dict:
    return {"schema_version": 1, "entries": list(entries) or [_entry()]}


README = f"""# Meta repo

Hand-written vision text.

{renderer.START_MARKER}
old generated table
{renderer.END_MARKER}

More hand-written text.
"""


# --- render ------------------------------------------------------------------

def test_render_is_deterministic():
    doc = _doc(_entry(), _entry(id="b", name="B", status="Design", deployed=False))
    assert renderer.render(doc) == renderer.render(doc)


def test_render_keeps_file_order_and_columns():
    doc = _doc(_entry(name="Zeta"), _entry(id="a", name="Alpha"))
    block = renderer.render(doc)
    assert "| Capability | Status | What it does | Live? |" in block
    assert block.index("Zeta") < block.index("Alpha")


@pytest.mark.parametrize(
    "deployed,label",
    [(True, "Yes"), (False, "No"), ("unknown", "Not verified"), ("n/a", "—")],
)
def test_live_column(deployed, label):
    row = [line for line in renderer.render(_doc(_entry(deployed=deployed))).splitlines() if "Decision recap" in line][0]
    assert row.endswith(f"| {label} |")


def test_live_yes_only_for_true():
    for deployed in (False, "unknown", "n/a"):
        assert "| Yes |" not in renderer.render(_doc(_entry(deployed=deployed)))


def test_evidence_and_id_are_never_rendered():
    block = renderer.render(_doc(_entry(id="secret-id-xyz")))
    assert "decision_recap.py" not in block
    assert "backend/" not in block
    assert "secret-id-xyz" not in block


def test_pipes_and_whitespace_escaped():
    block = renderer.render(_doc(_entry(description="a | b\n  c")))
    assert "a \\| b c" in block


def test_footnote_states_built_is_not_deployed_and_oldest_date():
    doc = _doc(_entry(verified_on=date(2026, 9, 1)), _entry(id="b", verified_on="2026-09-20"))
    block = renderer.render(doc)
    assert "does not by itself mean deployed or used" in block
    assert "Oldest entry verified on 2026-09-01." in block


def test_render_refuses_a_leaking_block():
    """Second line of defence: validate() would already reject this entry."""
    with pytest.raises(ValueError, match="leak"):
        renderer.render(_doc(_entry(description="See HOS-12.")))


# --- replace_block -----------------------------------------------------------

def test_replace_block_keeps_markers_and_surrounding_text():
    out = renderer.replace_block(README, "NEW\n")
    assert "old generated table" not in out
    assert f"{renderer.START_MARKER}\nNEW\n{renderer.END_MARKER}" in out
    assert out.startswith("# Meta repo\n\nHand-written vision text.")
    assert out.endswith("More hand-written text.\n")


def test_replace_block_is_idempotent():
    once = renderer.replace_block(README, "NEW\n")
    assert renderer.replace_block(once, "NEW\n") == once


@pytest.mark.parametrize(
    "document",
    [
        "no markers at all",
        f"{renderer.START_MARKER} only start",
        f"only end {renderer.END_MARKER}",
        f"{renderer.END_MARKER} reversed {renderer.START_MARKER}",
        f"{renderer.START_MARKER}{renderer.END_MARKER}{renderer.START_MARKER}{renderer.END_MARKER}",
    ],
)
def test_replace_block_rejects_bad_markers(document):
    with pytest.raises(renderer.MarkerError):
        renderer.replace_block(document, "NEW\n")


# --- CLI ---------------------------------------------------------------------

def test_cli_apply_reports_changed_then_unchanged(tmp_path, capsys):
    readme = tmp_path / "README.md"
    readme.write_text(README, encoding="utf-8")
    assert renderer.main(["--apply", str(readme)]) == 0
    assert capsys.readouterr().out.strip() == "changed"
    assert renderer.main(["--apply", str(readme)]) == 0
    assert capsys.readouterr().out.strip() == "unchanged"
    assert "More hand-written text." in readme.read_text(encoding="utf-8")


def test_cli_apply_without_markers_exits_3(tmp_path):
    readme = tmp_path / "README.md"
    readme.write_text("# no markers\n", encoding="utf-8")
    assert renderer.main(["--apply", str(readme)]) == 3
    assert readme.read_text(encoding="utf-8") == "# no markers\n"


def test_cli_refuses_invalid_file(tmp_path):
    bad = tmp_path / "bad.yml"
    bad.write_text("schema_version: 1\nentries:\n  - id: x\n", encoding="utf-8")
    assert renderer.main(["--file", str(bad), "--out", str(tmp_path / "o.md")]) == 1
    assert not (tmp_path / "o.md").exists()


def test_cli_renders_the_repository_file(tmp_path):
    out = tmp_path / "block.md"
    assert renderer.main(["--out", str(out)]) == 0
    block = out.read_text(encoding="utf-8")
    assert gate.find_leaks(block) == []
    assert block.count("\n| ") >= 2

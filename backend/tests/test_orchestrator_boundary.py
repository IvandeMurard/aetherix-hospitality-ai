"""Tests for the orchestrator boundary checker (ADR-0004 · HOS-184 PR-A).

Verifies that `scripts/ci/check_orchestrator_boundary.py` actually rejects
violating imports — the rule is meaningful only if the enforcement works.
"""
from __future__ import annotations

import importlib.util
import sys
import textwrap
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPT_PATH = REPO_ROOT / "scripts" / "ci" / "check_orchestrator_boundary.py"


def _load_checker():
    """Import the standalone script as a module so we can call _check_file directly."""
    spec = importlib.util.spec_from_file_location("orch_boundary_check", SCRIPT_PATH)
    if spec is None or spec.loader is None:
        pytest.skip(f"cannot load {SCRIPT_PATH}")
    module = importlib.util.module_from_spec(spec)
    sys.modules["orch_boundary_check"] = module
    spec.loader.exec_module(module)
    return module


checker = _load_checker()


class TestForbiddenImportDetection:
    """Each forbidden prefix from ADR-0004 must raise a violation."""

    def test_detects_from_app_services(self, tmp_path: Path):
        f = tmp_path / "bad.py"
        f.write_text("from app.services.prediction_engine import PredictionEngine\n")
        violations = checker._check_file(f)
        assert len(violations) == 1
        assert "app.services.prediction_engine" in violations[0]

    def test_detects_from_app_services_nested(self, tmp_path: Path):
        f = tmp_path / "bad.py"
        f.write_text("from app.services.memory.recall import MemoryRecallService\n")
        violations = checker._check_file(f)
        assert len(violations) == 1

    def test_detects_from_app_db_models(self, tmp_path: Path):
        f = tmp_path / "bad.py"
        f.write_text("from app.db.models import OperationalMemory\n")
        violations = checker._check_file(f)
        assert len(violations) == 1
        assert "app.db.models" in violations[0]

    def test_detects_from_app_db_session(self, tmp_path: Path):
        f = tmp_path / "bad.py"
        f.write_text("from app.db.session import get_db\n")
        violations = checker._check_file(f)
        assert len(violations) == 1

    def test_detects_from_app_api(self, tmp_path: Path):
        f = tmp_path / "bad.py"
        f.write_text("from app.api.routes import mcp\n")
        violations = checker._check_file(f)
        assert len(violations) == 1

    def test_detects_bare_import_app_services(self, tmp_path: Path):
        f = tmp_path / "bad.py"
        f.write_text("import app.services.prediction_engine\n")
        violations = checker._check_file(f)
        assert len(violations) == 1


class TestAllowedImports:
    """Allowed imports must NOT trigger violations."""

    def test_allows_app_providers(self, tmp_path: Path):
        f = tmp_path / "good.py"
        f.write_text("from app.providers.factory import build_llm_provider\n")
        assert checker._check_file(f) == []

    def test_allows_app_mcp_core(self, tmp_path: Path):
        f = tmp_path / "good.py"
        f.write_text("from app.mcp_core import sanitize_notes, MCPAuthError\n")
        assert checker._check_file(f) == []

    def test_allows_stdlib(self, tmp_path: Path):
        f = tmp_path / "good.py"
        f.write_text("import logging\nfrom dataclasses import dataclass\n")
        assert checker._check_file(f) == []

    def test_allows_third_party(self, tmp_path: Path):
        f = tmp_path / "good.py"
        f.write_text("import httpx\nfrom anthropic import Anthropic\n")
        assert checker._check_file(f) == []

    def test_allows_intra_orchestrator(self, tmp_path: Path):
        f = tmp_path / "good.py"
        f.write_text("from orchestrator.rules import RuleSet\n")
        assert checker._check_file(f) == []


class TestCurrentOrchestratorIsClean:
    """The actual orchestrator/ module must currently pass the boundary check.

    Regression guard: if any future change introduces a forbidden import,
    this test fails fast in unit-tests before reaching CI.
    """

    def test_existing_orchestrator_module_clean(self):
        orch_dir = REPO_ROOT / "backend" / "orchestrator"
        if not orch_dir.exists():
            pytest.skip("orchestrator/ not present")

        all_violations: list[str] = []
        for py in orch_dir.rglob("*.py"):
            all_violations.extend(checker._check_file(py))

        assert all_violations == [], (
            "orchestrator/ has forbidden imports:\n" + "\n".join(all_violations)
        )


class TestMixedFileReportsAllViolations:
    """A file with multiple bad imports should surface every one."""

    def test_multiple_violations_in_one_file(self, tmp_path: Path):
        f = tmp_path / "bad.py"
        f.write_text(textwrap.dedent("""
            from app.services.prediction_engine import PredictionEngine
            from app.db.session import get_db
            from app.providers.factory import build_llm_provider  # allowed
            from app.api.routes import mcp
        """).strip())
        violations = checker._check_file(f)
        assert len(violations) == 3  # the providers line is allowed

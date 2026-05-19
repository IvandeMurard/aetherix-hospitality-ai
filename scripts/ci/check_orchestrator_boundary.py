#!/usr/bin/env python3
"""
Orchestrator boundary checker — ADR-0004 · HOS-184.

Enforces the architectural rule that `backend/orchestrator/` must not import
from `app.services.*`, `app.db.models`, or `app.db.session`. The orchestrator
must reach Aetherix execution-node capabilities through MCP calls only.

Why
---
The orchestrator is a bounded context separate from Aetherix. Any direct
Python import from `app.services` would recreate the monolithic coupling that
ADR-0004 explicitly dismantles, and would block the Phase 4 split where
`orchestrator/` moves to its own repo and calls Aetherix over HTTP MCP.

Usage
-----
  python scripts/ci/check_orchestrator_boundary.py

Exit codes
----------
  0   No violations
  1   Forbidden import detected
  2   Script error (parse failure, etc.)

Allowed imports inside orchestrator/:
  - Standard library
  - Third-party packages (anthropic, httpx, etc.)
  - app.providers.*  (LLM/Embedding infra singletons)
  - app.mcp_core     (shared MCP primitives — sanitizers, auth errors)
  - orchestrator.*   (intra-package)

Forbidden:
  - app.services.*   (would defeat ADR-0004 bounded context)
  - app.db.models    (orchestrator is stateless; data lives in execution nodes)
  - app.db.session   (same)
  - app.api.*        (orchestrator does not own HTTP routes)
"""
from __future__ import annotations

import ast
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
ORCH_DIR = REPO_ROOT / "backend" / "orchestrator"

# Module prefixes that orchestrator/ may NEVER import from.
FORBIDDEN_PREFIXES = (
    "app.services",
    "app.db.models",
    "app.db.session",
    "app.api",
)

# Module prefixes that ARE allowed (informational — checked positively below
# only to surface unexpected `app.*` imports for human review).
ALLOWED_APP_PREFIXES = (
    "app.providers",
    "app.mcp_core",
)


def _module_name(node: ast.AST) -> str | None:
    """Return the dotted module name for an Import / ImportFrom node, or None."""
    if isinstance(node, ast.ImportFrom):
        return node.module or ""
    if isinstance(node, ast.Import):
        # Multi-target imports `import a, b` — we treat each alias separately
        # in the caller; this function returns the first for the simple cases.
        return node.names[0].name if node.names else None
    return None


def _check_file(path: Path) -> list[str]:
    """Return a list of human-readable violation messages for one .py file."""
    violations: list[str] = []
    try:
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    except SyntaxError as exc:
        return [f"{path}: syntax error — {exc}"]

    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom):
            mod = node.module or ""
            for prefix in FORBIDDEN_PREFIXES:
                if mod == prefix or mod.startswith(prefix + "."):
                    violations.append(
                        f"{path}:{node.lineno} — forbidden import: `from {mod} import ...`"
                        f"\n  Reason: orchestrator/ must not import from `{prefix}*` (ADR-0004)."
                        f"\n  Fix: call the corresponding Aetherix MCP tool instead."
                    )
        elif isinstance(node, ast.Import):
            for alias in node.names:
                mod = alias.name
                for prefix in FORBIDDEN_PREFIXES:
                    if mod == prefix or mod.startswith(prefix + "."):
                        violations.append(
                            f"{path}:{node.lineno} — forbidden import: `import {mod}`"
                            f"\n  Reason: orchestrator/ must not import from `{prefix}*` (ADR-0004)."
                            f"\n  Fix: call the corresponding Aetherix MCP tool instead."
                        )

    return violations


def main() -> int:
    if not ORCH_DIR.exists():
        print(f"[boundary-check] orchestrator/ not found at {ORCH_DIR} — skipping.")
        return 0

    py_files = sorted(ORCH_DIR.rglob("*.py"))
    if not py_files:
        print(f"[boundary-check] no .py files under {ORCH_DIR} — nothing to check.")
        return 0

    all_violations: list[str] = []
    for py in py_files:
        all_violations.extend(_check_file(py))

    if all_violations:
        print("[boundary-check] FAIL: orchestrator boundary violations:\n")
        for v in all_violations:
            print(f"  - {v}\n")
        print(
            "  The orchestrator must reach Aetherix capabilities through MCP\n"
            "  calls (HTTP or in-process dispatch), never through direct\n"
            "  Python imports from app.services / app.db / app.api.\n"
            "  See docs/adr/0004-orchestrator-separation.md."
        )
        return 1

    print(f"[boundary-check] OK: {len(py_files)} file(s) clean - no forbidden imports.")
    return 0


if __name__ == "__main__":
    sys.exit(main())

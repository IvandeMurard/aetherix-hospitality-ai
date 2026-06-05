"""EVAL-0 (HOS-204) — golden dataset validity + prompt-extraction shim.

- AC9: extracting `_SYSTEM_PROMPT_TEMPLATE` to `app.prompts.constitution` keeps
  the `app.services.agent_constitution` reference working with no circular import.
- Test plan: `validate_dataset.py` passes on the committed dataset (exit 0).
"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[3]  # backend/tests/eval/ -> repo root


def test_constitution_shim_no_circular_import():
    from app.prompts.constitution import _SYSTEM_PROMPT_TEMPLATE as from_prompts
    from app.services.agent_constitution import _SYSTEM_PROMPT_TEMPLATE as from_service

    # Same object via the shim — no copy, no circular import.
    assert from_service is from_prompts
    assert "Aetherix" in from_service
    assert "{hotel_name}" in from_service


def test_agent_constitution_still_renders():
    """The shimmed template still formats end-to-end (no breaking change)."""
    from types import SimpleNamespace

    from app.services.agent_constitution import AgentConstitutionService

    profile = SimpleNamespace(
        property_name="Demo Hotel",
        outlet_name="Le Restaurant",
        total_seats=80,
        manager_name="Ivan",
        agent_tone_profile="luxury",
    )
    prompt = AgentConstitutionService().build_system_prompt(profile, {"covers": 92})
    assert "Demo Hotel" in prompt
    assert "92 covers" in prompt


def test_golden_dataset_validates():
    """The committed golden dataset passes scripts/eval/validate_dataset.py."""
    script = _REPO_ROOT / "scripts" / "eval" / "validate_dataset.py"
    result = subprocess.run(
        [sys.executable, str(script)],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stdout + result.stderr

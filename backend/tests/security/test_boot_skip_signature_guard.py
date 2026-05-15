"""Boot-time guard: TWILIO_SKIP_SIGNATURE_VALIDATION forbidden in production (HOS-112 AC1).

The guard lives in _validate_startup_env() in app/main.py.
Uses explicit env dicts (hermetic) — no monkeypatching of os.environ.

Coverage:
- APP_ENV=production + SKIP=true  → boot fail (SystemExit)
- APP_ENV=production + SKIP=false → boot ok
- APP_ENV=staging    + SKIP=true  → boot ok (allowed in staging)
- APP_ENV=production + SKIP unset → boot ok
"""
from __future__ import annotations

import pytest


def _validate():
    from app.main import _validate_startup_env
    return _validate_startup_env


class TestBootSkipSignatureGuard:
    # All envs include a valid AUTH_SECRET so the guard under test is isolated.
    _BASE_ENV = {"AUTH_SECRET": "a" * 32}

    def test_production_with_skip_true_raises(self):
        env = {
            **self._BASE_ENV,
            "APP_ENV": "production",
            "TWILIO_SKIP_SIGNATURE_VALIDATION": "true",
        }
        with pytest.raises(SystemExit, match="TWILIO_SKIP_SIGNATURE_VALIDATION"):
            _validate()(env=env)

    def test_production_with_skip_false_passes(self):
        env = {
            **self._BASE_ENV,
            "APP_ENV": "production",
            "TWILIO_SKIP_SIGNATURE_VALIDATION": "false",
        }
        _validate()(env=env)  # must not raise

    def test_staging_with_skip_true_passes(self):
        env = {
            **self._BASE_ENV,
            "APP_ENV": "staging",
            "TWILIO_SKIP_SIGNATURE_VALIDATION": "true",
        }
        _validate()(env=env)  # must not raise

    def test_production_with_skip_unset_passes(self):
        env = {
            **self._BASE_ENV,
            "APP_ENV": "production",
            # TWILIO_SKIP_SIGNATURE_VALIDATION deliberately absent
        }
        _validate()(env=env)  # must not raise

"""Pytest configuration — HOS-162.

AC5: isolated test environment (no Supabase prod/staging, skip real-key tests in CI).
AC9: xfail infrastructure for known-broken tests pre-Epic-9.
"""
from __future__ import annotations

import os

import pytest

# ---------------------------------------------------------------------------
# Custom markers (AC5 + AC9)
# ---------------------------------------------------------------------------

def pytest_configure(config: pytest.Config) -> None:
    config.addinivalue_line(
        "markers",
        "requires_real_keys: skip in standard CI — needs live API credentials. "
        "Run with REAL_KEYS=1 or via the ci-integration workflow.",
    )


# ---------------------------------------------------------------------------
# AC5 — skip requires_real_keys tests unless REAL_KEYS=1
# ---------------------------------------------------------------------------

@pytest.fixture(autouse=True)
def _skip_real_keys(request: pytest.FixtureRequest) -> None:
    if request.node.get_closest_marker("requires_real_keys"):
        if not os.environ.get("REAL_KEYS"):
            pytest.skip(
                "requires real API keys — set REAL_KEYS=1 or trigger ci-integration workflow"
            )


# ---------------------------------------------------------------------------
# AC5 — CI-safe env defaults for all tests
# ---------------------------------------------------------------------------

@pytest.fixture(autouse=True)
def _ci_env_defaults(monkeypatch: pytest.MonkeyPatch) -> None:
    """Ensure safe defaults for env vars read at import/request time."""
    if not os.environ.get("TWILIO_SKIP_SIGNATURE_VALIDATION"):
        monkeypatch.setenv("TWILIO_SKIP_SIGNATURE_VALIDATION", "true")


# Provider/integration constructors typically use `arg or os.getenv("KEY", "")`,
# so an env var leaking from CI or a local .env makes tests that pass "" non-hermetic.
# Clear these per-test so empty-arg behaviour is deterministic.
_HERMETIC_ENV_VARS = (
    "ANTHROPIC_API_KEY",
    "MISTRAL_API_KEY",
    "GEMINI_API_KEY",
    "APALEO_CLIENT_ID",
    "APALEO_CLIENT_SECRET",
    "APALEO_MCP_SERVER_URL",
    "COMPOSIO_API_KEY",
    "COMPOSIO_USER_ID",
    "COMPOSIO_MCP_URL",
)


@pytest.fixture(autouse=True)
def _hermetic_secret_env(monkeypatch: pytest.MonkeyPatch) -> None:
    for var in _HERMETIC_ENV_VARS:
        monkeypatch.delenv(var, raising=False)

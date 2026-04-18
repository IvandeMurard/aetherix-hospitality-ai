"""Tier-1 tests for Redis-backed rate limiter + fail-open fallback (ADR 0003 D6).

All tests run without Redis installed — the fail-open path IS the default in
dev/test environments, and mocked Redis covers the happy + transient-failure
paths.
"""
from __future__ import annotations

import os
from unittest.mock import AsyncMock, patch

import pytest

from app.mcp_core import MCPAuthError, _LOCAL_BUCKETS
from app.services import rate_limit as rl


@pytest.fixture(autouse=True)
def _reset_state():
    """Clean per-test state — local buckets + module-level Redis singleton."""
    _LOCAL_BUCKETS.clear()
    rl._redis_client = None
    rl._redis_available = None
    yield
    _LOCAL_BUCKETS.clear()
    rl._redis_client = None
    rl._redis_available = None


class TestFallbackWhenNoRedis:
    @pytest.mark.asyncio
    async def test_no_redis_url_uses_local_fallback(self, monkeypatch):
        monkeypatch.delenv("REDIS_URL", raising=False)
        used_redis = await rl.check_rate_limit_async("h1", "get_operational_predictions")
        assert used_redis is False
        # Confirms the local bucket was incremented
        assert any("h1" in k for k in _LOCAL_BUCKETS)

    @pytest.mark.asyncio
    async def test_empty_redis_url_uses_local_fallback(self, monkeypatch):
        monkeypatch.setenv("REDIS_URL", "")
        used_redis = await rl.check_rate_limit_async("h1", "get_operational_predictions")
        assert used_redis is False

    @pytest.mark.asyncio
    async def test_local_fallback_enforces_limit(self, monkeypatch):
        monkeypatch.delenv("REDIS_URL", raising=False)
        # submit_feedback_to_memory limit is 20/min
        for _ in range(20):
            await rl.check_rate_limit_async("h_break", "submit_feedback_to_memory")
        with pytest.raises(MCPAuthError) as excinfo:
            await rl.check_rate_limit_async("h_break", "submit_feedback_to_memory")
        assert excinfo.value.status == 429


class TestRedisPath:
    @pytest.mark.asyncio
    async def test_redis_incr_under_limit(self, monkeypatch):
        monkeypatch.setenv("REDIS_URL", "redis://fake:6379")
        fake_client = AsyncMock()
        fake_client.incr = AsyncMock(return_value=5)
        fake_client.expire = AsyncMock(return_value=True)
        with patch.object(rl, "_make_client", return_value=fake_client):
            used_redis = await rl.check_rate_limit_async("h2", "get_operational_predictions")
        assert used_redis is True
        fake_client.incr.assert_called_once()
        # limit=60, count=5 → under

    @pytest.mark.asyncio
    async def test_redis_ttl_set_on_first_hit(self, monkeypatch):
        monkeypatch.setenv("REDIS_URL", "redis://fake:6379")
        fake_client = AsyncMock()
        fake_client.incr = AsyncMock(return_value=1)  # first hit in bucket
        fake_client.expire = AsyncMock(return_value=True)
        with patch.object(rl, "_make_client", return_value=fake_client):
            await rl.check_rate_limit_async("h3", "submit_feedback_to_memory")
        # TTL should be set to ~65s (minute + small buffer)
        fake_client.expire.assert_called_once()
        args = fake_client.expire.call_args[0]
        assert args[1] == 65

    @pytest.mark.asyncio
    async def test_redis_ttl_not_reset_on_subsequent_hits(self, monkeypatch):
        monkeypatch.setenv("REDIS_URL", "redis://fake:6379")
        fake_client = AsyncMock()
        fake_client.incr = AsyncMock(return_value=7)  # not first hit
        fake_client.expire = AsyncMock(return_value=True)
        with patch.object(rl, "_make_client", return_value=fake_client):
            await rl.check_rate_limit_async("h4", "get_operational_predictions")
        fake_client.expire.assert_not_called()

    @pytest.mark.asyncio
    async def test_redis_over_limit_raises_429(self, monkeypatch):
        monkeypatch.setenv("REDIS_URL", "redis://fake:6379")
        fake_client = AsyncMock()
        fake_client.incr = AsyncMock(return_value=61)  # limit=60
        fake_client.expire = AsyncMock(return_value=True)
        with patch.object(rl, "_make_client", return_value=fake_client):
            with pytest.raises(MCPAuthError) as excinfo:
                await rl.check_rate_limit_async("h5", "get_operational_predictions")
        assert excinfo.value.status == 429
        assert excinfo.value.title == "rate_limited"


class TestRedisFailOpen:
    @pytest.mark.asyncio
    async def test_redis_connection_error_falls_open(self, monkeypatch):
        """Redis transient failure → fail-open to local, return False."""
        monkeypatch.setenv("REDIS_URL", "redis://fake:6379")
        fake_client = AsyncMock()
        fake_client.incr = AsyncMock(side_effect=ConnectionError("redis is down"))
        with patch.object(rl, "_make_client", return_value=fake_client):
            used_redis = await rl.check_rate_limit_async("h_fail", "get_operational_predictions")
        assert used_redis is False  # fallback marker
        # Local bucket was incremented as fallback
        assert any("h_fail" in k for k in _LOCAL_BUCKETS)

    @pytest.mark.asyncio
    async def test_redis_timeout_falls_open(self, monkeypatch):
        monkeypatch.setenv("REDIS_URL", "redis://fake:6379")
        fake_client = AsyncMock()
        fake_client.incr = AsyncMock(side_effect=TimeoutError("socket timeout"))
        with patch.object(rl, "_make_client", return_value=fake_client):
            used_redis = await rl.check_rate_limit_async("h_timeout", "submit_feedback_to_memory")
        assert used_redis is False


class TestKeyFormat:
    """ADR D6: ratelimit:{hotel_id}:{tool}:{minute_bucket} — used for ops dashboards."""

    @pytest.mark.asyncio
    async def test_key_format_includes_prefix_and_hotel(self, monkeypatch):
        monkeypatch.setenv("REDIS_URL", "redis://fake:6379")
        captured_keys = []
        fake_client = AsyncMock()

        async def _capture_incr(key):
            captured_keys.append(key)
            return 1

        fake_client.incr = _capture_incr
        fake_client.expire = AsyncMock(return_value=True)
        with patch.object(rl, "_make_client", return_value=fake_client):
            await rl.check_rate_limit_async("hotel_abc", "submit_feedback_to_memory")
        assert len(captured_keys) == 1
        key = captured_keys[0]
        assert key.startswith("ratelimit:")
        assert "hotel_abc" in key
        assert "submit_feedback_to_memory" in key
        # Should have 4 colon-separated parts: prefix:hotel:tool:bucket
        assert key.count(":") == 3

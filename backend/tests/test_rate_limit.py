"""Tier-1 tests for Redis-backed rate limiter + fail-open fallback (ADR 0003 D6).

All tests run without Redis installed — the fail-open path IS the default in
dev/test environments, and mocked Redis covers the happy + transient-failure
paths.
"""
from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.mcp_core import _LOCAL_BUCKETS, MCPAuthError
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


class _PipelineMock:
    """Async context manager mock for redis pipeline (incr/expire are sync queues)."""

    def __init__(self, count=1, execute_side_effect=None):
        self.incr = MagicMock()
        self.expire = MagicMock()
        if execute_side_effect is not None:
            self.execute = AsyncMock(side_effect=execute_side_effect)
        else:
            self.execute = AsyncMock(return_value=[count, True])

    async def __aenter__(self):
        return self

    async def __aexit__(self, *args):
        pass


def _fake_client(count=1, execute_side_effect=None):
    """Return a fake redis client whose pipeline() yields a _PipelineMock."""
    pipe = _PipelineMock(count=count, execute_side_effect=execute_side_effect)
    client = MagicMock()
    client.pipeline = MagicMock(return_value=pipe)
    client._pipe = pipe  # expose for assertions
    return client


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
        client = _fake_client(count=5)
        with patch.object(rl, "_make_client", return_value=client):
            used_redis = await rl.check_rate_limit_async("h2", "get_operational_predictions")
        assert used_redis is True
        client._pipe.incr.assert_called_once()
        # limit=60, count=5 → under

    @pytest.mark.asyncio
    async def test_redis_pipeline_sets_ttl(self, monkeypatch):
        """Pipeline atomically calls expire(key, 65) on every request."""
        monkeypatch.setenv("REDIS_URL", "redis://fake:6379")
        client = _fake_client(count=1)
        with patch.object(rl, "_make_client", return_value=client):
            await rl.check_rate_limit_async("h3", "submit_feedback_to_memory")
        client._pipe.expire.assert_called_once()
        args = client._pipe.expire.call_args[0]
        assert args[1] == 65

    @pytest.mark.asyncio
    async def test_redis_pipeline_atomic_on_subsequent_hits(self, monkeypatch):
        """Pipeline always issues both incr and expire (atomic, no key-leak risk)."""
        monkeypatch.setenv("REDIS_URL", "redis://fake:6379")
        client = _fake_client(count=7)
        with patch.object(rl, "_make_client", return_value=client):
            await rl.check_rate_limit_async("h4", "get_operational_predictions")
        # Both commands queued in the pipeline
        client._pipe.incr.assert_called_once()
        client._pipe.expire.assert_called_once()

    @pytest.mark.asyncio
    async def test_redis_over_limit_raises_429(self, monkeypatch):
        monkeypatch.setenv("REDIS_URL", "redis://fake:6379")
        client = _fake_client(count=61)  # limit=60
        with patch.object(rl, "_make_client", return_value=client):
            with pytest.raises(MCPAuthError) as excinfo:
                await rl.check_rate_limit_async("h5", "get_operational_predictions")
        assert excinfo.value.status == 429
        assert excinfo.value.title == "rate_limited"


class TestRedisFailOpen:
    @pytest.mark.asyncio
    async def test_redis_connection_error_falls_open(self, monkeypatch):
        """Redis transient failure → fail-open to local, return False."""
        monkeypatch.setenv("REDIS_URL", "redis://fake:6379")
        client = _fake_client(execute_side_effect=ConnectionError("redis is down"))
        with patch.object(rl, "_make_client", return_value=client):
            used_redis = await rl.check_rate_limit_async("h_fail", "get_operational_predictions")
        assert used_redis is False  # fallback marker
        # Local bucket was incremented as fallback
        assert any("h_fail" in k for k in _LOCAL_BUCKETS)

    @pytest.mark.asyncio
    async def test_redis_timeout_falls_open(self, monkeypatch):
        monkeypatch.setenv("REDIS_URL", "redis://fake:6379")
        client = _fake_client(execute_side_effect=TimeoutError("socket timeout"))
        with patch.object(rl, "_make_client", return_value=client):
            used_redis = await rl.check_rate_limit_async("h_timeout", "submit_feedback_to_memory")
        assert used_redis is False


class TestKeyFormat:
    """ADR D6: ratelimit:{hotel_id}:{tool}:{minute_bucket} — used for ops dashboards."""

    @pytest.mark.asyncio
    async def test_key_format_includes_prefix_and_hotel(self, monkeypatch):
        monkeypatch.setenv("REDIS_URL", "redis://fake:6379")
        captured_keys = []

        class _CapturePipe:
            def incr(self, key):
                captured_keys.append(key)

            def expire(self, key, ttl):
                pass

            execute = AsyncMock(return_value=[1, True])

            async def __aenter__(self):
                return self

            async def __aexit__(self, *args):
                pass

        client = MagicMock()
        client.pipeline = MagicMock(return_value=_CapturePipe())
        with patch.object(rl, "_make_client", return_value=client):
            await rl.check_rate_limit_async("hotel_abc", "submit_feedback_to_memory")
        assert len(captured_keys) == 1
        key = captured_keys[0]
        assert key.startswith("ratelimit:")
        assert "hotel_abc" in key
        assert "submit_feedback_to_memory" in key
        # Should have 4 colon-separated parts: prefix:hotel:tool:bucket
        assert key.count(":") == 3

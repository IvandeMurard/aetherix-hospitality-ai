"""Tests for HOS-155 — Twilio dispatcher robustness.

Coverage:
1. _get_webhook_url: falls back to raw URL, reads forwarded headers, env-var override
2. timeout: httpx.AsyncClient receives the 10 s Timeout object
3. retry on 5xx: up to _TWILIO_MAX_RETRIES attempts, exponential back-off
4. retry on network error: TransportError retried
5. no retry on 4xx: raises immediately
6. DLQ log on definitive failure: structured logger.error with to/from/body
7. isolated session: _bg_parse_query has no db parameter and opens AsyncSessionLocal
"""
from __future__ import annotations

import inspect
import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.integrations.twilio_client import (
    _TWILIO_MAX_RETRIES,
    _TWILIO_TIMEOUT,
    TwilioClient,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_mock_request(
    path: str = "/webhooks/twilio/inbound",
    headers: dict | None = None,
    scheme: str = "http",
    netloc: str = "127.0.0.1:8000",
    query: str = "",
) -> MagicMock:
    req = MagicMock()
    req.url.path = path
    req.url.query = query
    req.url.scheme = scheme
    req.url.netloc = netloc
    _headers = {k.lower(): v for k, v in (headers or {}).items()}
    req.headers.get = lambda key, default=None: _headers.get(key.lower(), default)
    return req


def _make_twilio_client() -> TwilioClient:
    return TwilioClient(
        account_sid="ACtest",
        auth_token="token",
        from_number="+15005550006",
    )


# ===========================================================================
# 1. _get_webhook_url
# ===========================================================================

class TestGetWebhookUrl:
    def test_falls_back_to_request_url_when_no_headers_no_override(self, monkeypatch):
        monkeypatch.delenv("TWILIO_WEBHOOK_BASE_URL", raising=False)
        from app.api.routes.twilio_inbound import _get_webhook_url

        req = _make_mock_request(scheme="http", netloc="127.0.0.1:8000")
        url = _get_webhook_url(req)

        assert "/webhooks/twilio/inbound" in url
        assert url.startswith("http://")

    def test_uses_x_forwarded_proto_and_host(self, monkeypatch):
        monkeypatch.delenv("TWILIO_WEBHOOK_BASE_URL", raising=False)
        from app.api.routes.twilio_inbound import _get_webhook_url

        req = _make_mock_request(
            scheme="http",
            netloc="127.0.0.1:8000",
            headers={
                "X-Forwarded-Proto": "https",
                "X-Forwarded-Host": "api.aetherix.com",
            },
        )
        url = _get_webhook_url(req)

        assert url.startswith("https://api.aetherix.com")
        assert "/webhooks/twilio/inbound" in url
        assert "127.0.0.1" not in url

    def test_base_url_env_override_takes_precedence_over_headers(self, monkeypatch):
        monkeypatch.setenv("TWILIO_WEBHOOK_BASE_URL", "https://api.aetherix.com")
        from app.api.routes.twilio_inbound import _get_webhook_url

        req = _make_mock_request(
            headers={
                "X-Forwarded-Proto": "http",
                "X-Forwarded-Host": "internal-lb.local",
            },
        )
        url = _get_webhook_url(req)

        assert url.startswith("https://api.aetherix.com")
        assert "internal-lb.local" not in url
        assert "/webhooks/twilio/inbound" in url

    def test_base_url_trailing_slash_stripped(self, monkeypatch):
        monkeypatch.setenv("TWILIO_WEBHOOK_BASE_URL", "https://api.aetherix.com/")
        from app.api.routes.twilio_inbound import _get_webhook_url

        req = _make_mock_request()
        url = _get_webhook_url(req)

        assert "aetherix.com//" not in url
        assert url.startswith("https://api.aetherix.com/")

    def test_query_string_appended(self, monkeypatch):
        monkeypatch.setenv("TWILIO_WEBHOOK_BASE_URL", "https://api.aetherix.com")
        from app.api.routes.twilio_inbound import _get_webhook_url

        req = _make_mock_request(query="foo=bar")
        url = _get_webhook_url(req)

        assert "foo=bar" in url


# ===========================================================================
# 2. Timeout constant
# ===========================================================================

def test_timeout_value_is_10_seconds():
    """_TWILIO_TIMEOUT must have a total timeout of 10 seconds."""
    assert _TWILIO_TIMEOUT.read == 10.0 or _TWILIO_TIMEOUT.connect == 10.0 or str(_TWILIO_TIMEOUT) == "Timeout(timeout=10.0)"


# ===========================================================================
# 3 & 4. Retry on 5xx / network errors
# ===========================================================================

class TestTwilioRetry:
    @pytest.mark.asyncio
    async def test_succeeds_on_first_attempt_no_sleep(self):
        client = _make_twilio_client()
        ok_resp = MagicMock(
            status_code=201,
            json=MagicMock(return_value={"sid": "SM_OK"}),
            text="",
        )

        with patch("httpx.AsyncClient.post", new_callable=AsyncMock, return_value=ok_resp), \
             patch("asyncio.sleep", new_callable=AsyncMock) as mock_sleep:
            sid = await client.send_sms(to="+336", body="test")

        assert sid == "SM_OK"
        mock_sleep.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_retries_on_5xx_and_succeeds_on_second_attempt(self):
        client = _make_twilio_client()
        fail_resp = MagicMock(status_code=503, request=MagicMock())
        ok_resp = MagicMock(
            status_code=201,
            json=MagicMock(return_value={"sid": "SM_RETRY"}),
            text="",
        )

        with patch(
            "httpx.AsyncClient.post",
            new_callable=AsyncMock,
            side_effect=[fail_resp, ok_resp],
        ), patch("asyncio.sleep", new_callable=AsyncMock):
            sid = await client.send_sms(to="+336", body="test")

        assert sid == "SM_RETRY"

    @pytest.mark.asyncio
    async def test_retries_on_transport_error_and_succeeds(self):
        client = _make_twilio_client()
        ok_resp = MagicMock(
            status_code=201,
            json=MagicMock(return_value={"sid": "SM_NET_OK"}),
            text="",
        )

        with patch(
            "httpx.AsyncClient.post",
            new_callable=AsyncMock,
            side_effect=[httpx.ConnectError("timeout"), ok_resp],
        ), patch("asyncio.sleep", new_callable=AsyncMock):
            sid = await client.send_sms(to="+336", body="test")

        assert sid == "SM_NET_OK"

    @pytest.mark.asyncio
    async def test_does_not_retry_on_4xx(self):
        client = _make_twilio_client()
        bad_resp = MagicMock(status_code=400, text="Bad request")
        bad_resp.raise_for_status = MagicMock(
            side_effect=httpx.HTTPStatusError(
                "400", request=MagicMock(), response=bad_resp
            )
        )

        with patch(
            "httpx.AsyncClient.post", new_callable=AsyncMock, return_value=bad_resp
        ), patch("asyncio.sleep", new_callable=AsyncMock) as mock_sleep:
            with pytest.raises(httpx.HTTPStatusError):
                await client.send_sms(to="+336", body="test")

        mock_sleep.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_exponential_backoff_delays(self):
        """sleep(1) after attempt 1, sleep(2) after attempt 2."""
        client = _make_twilio_client()
        fail_resp = MagicMock(status_code=503, request=MagicMock())
        ok_resp = MagicMock(
            status_code=201,
            json=MagicMock(return_value={"sid": "SM_BACKOFF"}),
            text="",
        )

        with patch(
            "httpx.AsyncClient.post",
            new_callable=AsyncMock,
            side_effect=[fail_resp, fail_resp, ok_resp],
        ), patch("asyncio.sleep", new_callable=AsyncMock) as mock_sleep:
            await client.send_sms(to="+336", body="test")

        assert mock_sleep.await_count == 2
        delays = [call.args[0] for call in mock_sleep.await_args_list]
        assert delays == [1, 2]  # 2^0, 2^1

    @pytest.mark.asyncio
    async def test_exactly_max_retries_http_calls_on_5xx(self):
        client = _make_twilio_client()
        fail_resp = MagicMock(status_code=503, request=MagicMock())

        with patch(
            "httpx.AsyncClient.post",
            new_callable=AsyncMock,
            return_value=fail_resp,
        ) as mock_post, patch("asyncio.sleep", new_callable=AsyncMock):
            with pytest.raises(Exception):
                await client.send_sms(to="+336", body="test")

        assert mock_post.await_count == _TWILIO_MAX_RETRIES


# ===========================================================================
# 5. DLQ structured log on definitive failure
# ===========================================================================

class TestTwilioDLQ:
    @pytest.mark.asyncio
    async def test_dlq_log_contains_to_from_body(self, caplog):
        import logging

        client = _make_twilio_client()
        fail_resp = MagicMock(status_code=503, request=MagicMock())

        with caplog.at_level(logging.ERROR, logger="app.integrations.twilio_client"), \
             patch(
                 "httpx.AsyncClient.post",
                 new_callable=AsyncMock,
                 return_value=fail_resp,
             ), \
             patch("asyncio.sleep", new_callable=AsyncMock):
            with pytest.raises(Exception):
                await client.send_sms(to="+33612345678", body="critical alert")

        dlq = [r for r in caplog.records if "twilio_dlq" in r.message]
        assert dlq, "Expected a twilio_dlq ERROR log entry"
        assert "+33612345678" in dlq[0].message
        assert "critical alert" in dlq[0].message

    @pytest.mark.asyncio
    async def test_dlq_exception_is_reraised(self):
        client = _make_twilio_client()
        fail_resp = MagicMock(status_code=503, request=MagicMock())

        with patch(
            "httpx.AsyncClient.post",
            new_callable=AsyncMock,
            return_value=fail_resp,
        ), patch("asyncio.sleep", new_callable=AsyncMock):
            with pytest.raises((httpx.HTTPStatusError, RuntimeError)):
                await client.send_sms(to="+336", body="test")

    @pytest.mark.asyncio
    async def test_network_error_triggers_dlq_after_max_retries(self, caplog):
        import logging

        client = _make_twilio_client()

        with caplog.at_level(logging.ERROR, logger="app.integrations.twilio_client"), \
             patch(
                 "httpx.AsyncClient.post",
                 new_callable=AsyncMock,
                 side_effect=httpx.ConnectError("Network unreachable"),
             ), \
             patch("asyncio.sleep", new_callable=AsyncMock):
            with pytest.raises(httpx.TransportError):
                await client.send_sms(to="+336", body="test")

        dlq = [r for r in caplog.records if "twilio_dlq" in r.message]
        assert dlq


# ===========================================================================
# 6. Isolated session in background task
# ===========================================================================

class TestBgParseQueryIsolatedSession:
    def test_bg_parse_query_has_no_db_parameter(self):
        from app.api.routes.twilio_inbound import _bg_parse_query

        sig = inspect.signature(_bg_parse_query)
        assert "db" not in sig.parameters

    @pytest.mark.asyncio
    async def test_bg_parse_query_opens_asyncsessionlocal(self):
        from app.api.routes.twilio_inbound import _bg_parse_query

        mock_session = AsyncMock()
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock(return_value=False)
        mock_session_factory = MagicMock(return_value=mock_session)

        parse_result = {"status": "stored", "query_id": str(uuid.uuid4())}

        mock_explainer_instance = AsyncMock()
        mock_explainer_instance.generate_and_send = AsyncMock(
            return_value={"status": "sent"}
        )
        mock_explainer_cls = MagicMock(return_value=mock_explainer_instance)

        with patch("app.api.routes.twilio_inbound.AsyncSessionLocal", mock_session_factory), \
             patch("app.api.routes.twilio_inbound.QueryParserService") as MockParser, \
             patch("app.api.routes.twilio_inbound.ExplainabilityService", mock_explainer_cls):
            mock_parser_instance = AsyncMock()
            mock_parser_instance.parse_and_store = AsyncMock(return_value=parse_result)
            MockParser.return_value = mock_parser_instance

            await _bg_parse_query(from_number="+336", body="test question")

        mock_session_factory.assert_called_once()

    def test_route_does_not_forward_request_session_to_bg_task(self, monkeypatch):
        """P2-4: The webhook route must schedule _bg_receipt_feedback without a db kwarg."""
        monkeypatch.setenv("TWILIO_SKIP_SIGNATURE_VALIDATION", "true")
        from app.api.routes.twilio_inbound import router
        from app.db.session import get_db

        app = FastAPI()
        app.include_router(router)

        async def _noop_db():
            yield AsyncMock()

        app.dependency_overrides[get_db] = _noop_db

        with patch("app.api.routes.twilio_inbound._bg_receipt_feedback", new_callable=AsyncMock) as mock_bg, \
             patch("app.api.routes.twilio_inbound.InboundDecisionService.profile_for",
                   new_callable=AsyncMock, return_value=None):
            with TestClient(app) as client:
                resp = client.post(
                    "/webhooks/twilio/inbound",
                    data={"From": "+336", "Body": "hello?", "To": "+14155238886"},
                )

        assert resp.status_code == 200
        # Verify the bg task was scheduled with from_number and body, no db kwarg
        mock_bg.assert_awaited_once()
        call_kwargs = mock_bg.await_args.kwargs
        assert "db" not in call_kwargs

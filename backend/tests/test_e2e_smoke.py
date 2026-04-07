"""End-to-end smoke tests — HOS-42.

Validates that every integration seam in the stack is correctly wired before
MCP activation.  All external network calls (Twilio, Linear, Claude, Apaleo)
are mocked — no real credentials required.

Coverage areas
--------------
1.  Backend health          — GET /health → 200
2.  POST /predict           — structured response, claude_used flag, heuristic fallback
3.  ReasoningService        — heuristic fallback text; Claude path (mocked client)
4.  ExplainabilityService   — generate_and_send full pipeline; fallback when no recommendation
5.  Twilio inbound webhook  — inbound conversational query → query-ack TwiML
6.  TwilioClient            — NotConfiguredError; send_whatsapp prefix; mocked HTTP POST
7.  Linear integration      — create_issue and list_issues hit the right GraphQL endpoint
"""
from __future__ import annotations

import uuid
from datetime import date, datetime, timezone
from typing import AsyncGenerator
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
import pytest_asyncio
from fastapi import FastAPI
from fastapi.testclient import TestClient


# ===========================================================================
# 1. Backend health
# ===========================================================================

class TestHealthEndpoint:
    """The /health endpoint must respond 200 and include status=ok.

    Uses a minimal FastAPI app wrapping the health handler to avoid
    triggering the full startup (APScheduler, DB) in the test environment.
    """

    @staticmethod
    def _make_health_app() -> FastAPI:
        from app.main import health_check
        app = FastAPI()
        app.get("/health")(health_check)
        return app

    def test_health_returns_200(self):
        client = TestClient(self._make_health_app())
        resp = client.get("/health")
        assert resp.status_code == 200

    def test_health_returns_ok_status(self):
        client = TestClient(self._make_health_app())
        resp = client.get("/health")
        assert resp.json().get("status") == "ok"


# ===========================================================================
# 2. POST /api/v1/predictions/predict
# ===========================================================================

def _mock_forecast_result(hotel_id: str = "hotel-001") -> dict:
    return {
        "tenant_id": hotel_id,
        "date": date.today().isoformat(),
        "service_type": "dinner",
        "prediction": {"covers": 45, "confidence": 0.85},
        "reasoning": "Prophet forecasts 45 covers for dinner on Monday with 85% confidence.",
        "reasoning_detail": {
            "summary": "Prophet forecasts 45 covers for dinner on Monday with 85% confidence.",
            "confidence_factors": ["Weather: Clear", "Historical pattern matching"],
            "claude_used": False,
        },
        "staffing_recommendation": {"servers": 4, "kitchen": 3, "hosts": 1},
        "historical_patterns": [],
    }


def _predict_client(monkeypatch) -> TestClient:
    monkeypatch.setenv("TWILIO_SKIP_SIGNATURE_VALIDATION", "true")
    from app.api.routes.predictions import router

    app = FastAPI()
    app.include_router(router)
    return TestClient(app)


class TestPostPredict:
    """Smoke tests for the new MCP-callable POST /predictions/predict endpoint."""

    @pytest.fixture
    def client(self, monkeypatch):
        return _predict_client(monkeypatch)

    def test_predict_returns_200(self, client, monkeypatch):
        with patch(
            "app.api.routes.predictions.engine.get_forecast",
            new_callable=AsyncMock,
            return_value=_mock_forecast_result(),
        ):
            resp = client.post(
                "/predictions/predict",
                json={"hotel_id": "hotel-001", "target_date": date.today().isoformat()},
            )
        assert resp.status_code == 200

    def test_predict_response_has_required_fields(self, client):
        with patch(
            "app.api.routes.predictions.engine.get_forecast",
            new_callable=AsyncMock,
            return_value=_mock_forecast_result(),
        ):
            resp = client.post(
                "/predictions/predict",
                json={"hotel_id": "hotel-001", "target_date": date.today().isoformat()},
            )
        body = resp.json()
        for field in (
            "hotel_id", "target_date", "service_type", "predicted_covers",
            "confidence", "reasoning_summary", "claude_used", "staffing_recommendation",
        ):
            assert field in body, f"Missing field: {field}"

    def test_predict_claude_used_flag_propagates(self, client):
        result = _mock_forecast_result()
        result["reasoning_detail"]["claude_used"] = True
        with patch(
            "app.api.routes.predictions.engine.get_forecast",
            new_callable=AsyncMock,
            return_value=result,
        ):
            resp = client.post(
                "/predictions/predict",
                json={"hotel_id": "hotel-001", "target_date": date.today().isoformat()},
            )
        assert resp.json()["claude_used"] is True

    def test_predict_heuristic_fallback_when_no_reasoning_detail(self, client):
        """When reasoning_detail is absent (legacy engine), falls back gracefully."""
        result = _mock_forecast_result()
        del result["reasoning_detail"]
        with patch(
            "app.api.routes.predictions.engine.get_forecast",
            new_callable=AsyncMock,
            return_value=result,
        ):
            resp = client.post(
                "/predictions/predict",
                json={"hotel_id": "hotel-001", "target_date": date.today().isoformat()},
            )
        body = resp.json()
        assert body["claude_used"] is False
        assert len(body["reasoning_summary"]) > 0

    def test_predict_missing_hotel_id_returns_422(self, client):
        resp = client.post(
            "/predictions/predict",
            json={"target_date": date.today().isoformat()},
        )
        assert resp.status_code == 422

    def test_predict_missing_target_date_returns_422(self, client):
        resp = client.post(
            "/predictions/predict",
            json={"hotel_id": "hotel-001"},
        )
        assert resp.status_code == 422


# ===========================================================================
# 3. ReasoningService — heuristic fallback + Claude path
# ===========================================================================

class TestReasoningService:
    """Smoke: heuristic always returns a non-empty summary; Claude path returns claude_used=True."""

    @pytest.mark.asyncio
    async def test_heuristic_fallback_returns_non_empty_summary(self):
        from app.services.reasoning_service import ReasoningService

        svc = ReasoningService.__new__(ReasoningService)
        svc.claude = None  # simulate missing API key

        result = await svc.generate_explanation(
            predicted_covers=50,
            confidence=0.80,
            target_date=date(2026, 4, 1),
            service_type="lunch",
            context={"weather": {"condition": "Sunny"}, "events": [], "occupancy": 0.75},
            similar_patterns=[],
        )

        assert "summary" in result
        assert len(result["summary"]) > 20
        assert result["claude_used"] is False

    @pytest.mark.asyncio
    async def test_heuristic_includes_predicted_covers(self):
        from app.services.reasoning_service import ReasoningService

        svc = ReasoningService.__new__(ReasoningService)
        svc.claude = None

        result = await svc.generate_explanation(
            predicted_covers=77,
            confidence=0.90,
            target_date=date(2026, 4, 1),
            service_type="dinner",
            context={},
            similar_patterns=[],
        )
        assert "77" in result["summary"]

    @pytest.mark.asyncio
    async def test_claude_path_returns_claude_used_true(self):
        from app.services.reasoning_service import ReasoningService

        mock_llm = MagicMock()
        mock_llm.complete = AsyncMock(
            return_value="Great forecast due to the tech conference nearby."
        )

        svc = ReasoningService(llm=mock_llm)

        result = await svc.generate_explanation(
            predicted_covers=60,
            confidence=0.88,
            target_date=date(2026, 4, 2),
            service_type="dinner",
            context={"weather": {"condition": "Clear"}, "events": [{"name": "Tech Conference"}]},
            similar_patterns=[],
        )

        assert result["claude_used"] is True
        assert "tech conference" in result["summary"].lower() or len(result["summary"]) > 10

    @pytest.mark.asyncio
    async def test_claude_api_error_falls_back_to_heuristic(self):
        from app.services.reasoning_service import ReasoningService

        mock_llm = MagicMock()
        mock_llm.complete = AsyncMock(side_effect=ValueError("API timeout"))

        svc = ReasoningService(llm=mock_llm)

        result = await svc.generate_explanation(
            predicted_covers=40,
            confidence=0.70,
            target_date=date(2026, 4, 3),
            service_type="breakfast",
            context={},
            similar_patterns=[],
        )

        assert result["claude_used"] is False
        assert "fallback_reason" in result
        assert len(result["summary"]) > 10


# ===========================================================================
# 4. ExplainabilityService — full pipeline
# ===========================================================================

def _make_db_session(query=None, recommendation=None, anomaly=None):
    """Build an AsyncSession that returns rows in execute() call order."""
    session = AsyncMock()

    def _make_result(obj):
        r = MagicMock()
        scalars = MagicMock()
        scalars.first.return_value = obj
        r.scalars.return_value = scalars
        return r

    session.execute = AsyncMock(
        side_effect=[
            _make_result(query),
            _make_result(recommendation),
            _make_result(anomaly),
        ]
    )
    session.commit = AsyncMock()
    return session


def _make_query(from_number: str = "+33600000001", recommendation_id=None):
    q = MagicMock()
    q.id = uuid.uuid4()
    q.body = "Why do you recommend 5 extra staff tonight?"
    q.from_number = from_number
    q.recommendation_id = recommendation_id or uuid.uuid4()
    q.status = "pending"
    return q


def _make_recommendation():
    rec = MagicMock()
    rec.id = uuid.uuid4()
    rec.anomaly_id = uuid.uuid4()
    rec.message_text = "Add 5 servers for dinner service."
    rec.triggering_factor = "Tech conference nearby (+25% F&B)"
    rec.recommended_headcount = 5
    rec.window_start = datetime(2026, 4, 1, 18, 0, tzinfo=timezone.utc)
    rec.window_end = datetime(2026, 4, 1, 22, 0, tzinfo=timezone.utc)
    rec.roi_net = 1200.0
    rec.roi_labor_cost = 300.0
    return rec


def _make_anomaly():
    a = MagicMock()
    a.id = uuid.uuid4()
    a.direction = "SURGE"
    a.deviation_pct = 28.5
    a.triggering_factors = ["Tech conference", "Clear weather"]
    return a


class TestExplainabilityService:
    """Smoke: full pipeline from DB fetch to Twilio dispatch."""

    @pytest.mark.asyncio
    async def test_generate_and_send_marks_query_answered(self):
        from app.services.explainability_service import ExplainabilityService

        query = _make_query()
        rec = _make_recommendation()
        anomaly = _make_anomaly()
        session = _make_db_session(query=query, recommendation=rec, anomaly=anomaly)

        svc = ExplainabilityService.__new__(ExplainabilityService)
        mock_msg = MagicMock()
        mock_msg.content = [MagicMock(text="Based on the tech conference, 5 extra servers make sense.")]
        mock_claude = AsyncMock()
        mock_claude.messages.create = AsyncMock(return_value=mock_msg)
        svc._claude = mock_claude

        with patch("app.services.explainability_service._send_twilio_reply", new_callable=AsyncMock) as mock_send:
            result = await svc.generate_and_send(query_id=query.id, session=session)

        assert result["status"] == "sent"
        assert query.status == "answered"
        mock_send.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_generate_and_send_sends_to_correct_number(self):
        from app.services.explainability_service import ExplainabilityService

        query = _make_query(from_number="+33600000099")
        rec = _make_recommendation()
        session = _make_db_session(query=query, recommendation=rec, anomaly=None)

        svc = ExplainabilityService.__new__(ExplainabilityService)
        mock_msg = MagicMock()
        mock_msg.content = [MagicMock(text="Explanation text.")]
        mock_claude = AsyncMock()
        mock_claude.messages.create = AsyncMock(return_value=mock_msg)
        svc._claude = mock_claude

        with patch("app.services.explainability_service._send_twilio_reply", new_callable=AsyncMock) as mock_send:
            await svc.generate_and_send(query_id=query.id, session=session)

        call_args = mock_send.call_args
        assert call_args[0][0] == "+33600000099"

    @pytest.mark.asyncio
    async def test_generate_and_send_fallback_when_no_recommendation(self):
        """When no recommendation is linked, send fallback and mark answered."""
        from app.services.explainability_service import ExplainabilityService

        query = _make_query()
        query.recommendation_id = None
        # Only one execute() result needed (the query itself)
        session = AsyncMock()
        result_mock = MagicMock()
        scalars_mock = MagicMock()
        scalars_mock.first.return_value = query
        result_mock.scalars.return_value = scalars_mock
        session.execute = AsyncMock(return_value=result_mock)
        session.commit = AsyncMock()

        svc = ExplainabilityService.__new__(ExplainabilityService)
        svc._claude = None

        with patch("app.services.explainability_service._send_twilio_reply", new_callable=AsyncMock) as mock_send:
            result = await svc.generate_and_send(query_id=query.id, session=session)

        assert result["status"] == "sent_fallback"
        mock_send.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_generate_and_send_query_not_found_returns_error(self):
        from app.services.explainability_service import ExplainabilityService

        session = AsyncMock()
        result_mock = MagicMock()
        scalars_mock = MagicMock()
        scalars_mock.first.return_value = None
        result_mock.scalars.return_value = scalars_mock
        session.execute = AsyncMock(return_value=result_mock)

        svc = ExplainabilityService.__new__(ExplainabilityService)
        svc._claude = None

        result = await svc.generate_and_send(query_id=uuid.uuid4(), session=session)

        assert result["status"] == "error"
        assert result["reason"] == "query_not_found"


# ===========================================================================
# 5. Twilio inbound webhook — conversational query path
# ===========================================================================

def _webhook_app() -> FastAPI:
    from app.api.routes.webhook import router
    app = FastAPI()
    app.include_router(router)
    return app


async def _noop_db() -> AsyncGenerator:
    session = AsyncMock()
    session.execute = AsyncMock()
    session.commit = AsyncMock()
    yield session


class TestTwilioInboundConversationalPath:
    """Story 5.1/5.2 smoke: unknown body → query-ack TwiML; pipeline is called."""

    @pytest.fixture(autouse=True)
    def skip_signature(self, monkeypatch):
        monkeypatch.setenv("TWILIO_SKIP_SIGNATURE_VALIDATION", "true")

    def test_conversational_query_returns_ack_twiml(self, monkeypatch):
        from app.db.session import get_db

        app = _webhook_app()
        app.dependency_overrides[get_db] = _noop_db

        mock_explainer_instance = AsyncMock()
        mock_explainer_instance.generate_and_send = AsyncMock(
            return_value={"status": "sent"}
        )
        mock_explainer_cls = MagicMock(return_value=mock_explainer_instance)

        with patch("app.api.routes.webhook.QueryParserService") as MockParser, \
             patch("app.api.routes.webhook.ExplainabilityService", mock_explainer_cls):
            mock_parser_instance = AsyncMock()
            mock_parser_instance.parse_and_store = AsyncMock(
                return_value={"status": "stored", "query_id": str(uuid.uuid4())}
            )
            MockParser.return_value = mock_parser_instance

            with TestClient(app) as client:
                resp = client.post(
                    "/webhooks/twilio/inbound",
                    data={"From": "+33600000001", "Body": "Why did you recommend this?", "To": "+14155238886"},
                )

        assert resp.status_code == 200
        assert "application/xml" in resp.headers.get("content-type", "")
        # Should return the query-ack TwiML (not ACCEPT/REJECT)
        assert "looking into it" in resp.text or "Got your question" in resp.text


# ===========================================================================
# 6. TwilioClient integration
# ===========================================================================

class TestTwilioClientSmoke:
    """TwilioClient raises when not configured; prefixes whatsapp: correctly."""

    def test_raises_not_configured_when_no_credentials(self):
        from app.core.exceptions import NotConfiguredError
        from app.integrations.twilio_client import TwilioClient

        client = TwilioClient(account_sid="", auth_token="", from_number="", whatsapp_from="")

        with pytest.raises(NotConfiguredError):
            import asyncio
            asyncio.run(client.send_sms(to="+33600000001", body="test"))

    @pytest.mark.asyncio
    async def test_send_whatsapp_adds_prefix(self):
        from app.integrations.twilio_client import TwilioClient

        client = TwilioClient(
            account_sid="AC_TEST",
            auth_token="TOKEN_TEST",
            from_number="+14155238886",
            whatsapp_from="whatsapp:+14155238886",
        )

        captured = {}

        async def mock_post_message(to, from_, body):
            captured["to"] = to
            return "SM_TEST_SID"

        client._post_message = mock_post_message
        await client.send_whatsapp(to="+33600000001", body="Hello manager")

        assert captured["to"].startswith("whatsapp:")

    @pytest.mark.asyncio
    async def test_send_whatsapp_no_double_prefix(self):
        from app.integrations.twilio_client import TwilioClient

        client = TwilioClient(
            account_sid="AC_TEST",
            auth_token="TOKEN_TEST",
            from_number="+14155238886",
            whatsapp_from="whatsapp:+14155238886",
        )

        captured = {}

        async def mock_post_message(to, from_, body):
            captured["to"] = to
            return "SM_TEST_SID"

        client._post_message = mock_post_message
        await client.send_whatsapp(to="whatsapp:+33600000001", body="Already prefixed")

        assert captured["to"] == "whatsapp:+33600000001"


# ===========================================================================
# 7. Linear integration — GraphQL seam
# ===========================================================================

class TestLinearIntegrationSmoke:
    """create_issue and list_issues hit the correct GraphQL endpoint."""

    @pytest.mark.asyncio
    async def test_create_issue_posts_to_linear_graphql(self, monkeypatch):
        monkeypatch.setenv("LINEAR_API_KEY", "lin_api_test")
        monkeypatch.setenv("LINEAR_TEAM_ID", "team-test-id")

        from app.integrations import linear

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.raise_for_status = MagicMock()
        mock_response.json.return_value = {
            "data": {
                "issueCreate": {
                    "success": True,
                    "issue": {"id": "abc", "identifier": "HOS-99", "title": "Test", "url": "https://linear.app/..."},
                }
            }
        }

        mock_client = AsyncMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        mock_client.post = AsyncMock(return_value=mock_response)

        with patch("app.integrations.linear.httpx.AsyncClient", return_value=mock_client):
            result = await linear.create_issue(title="Smoke test issue", priority=3)

        assert result["success"] is True
        call_json = mock_client.post.call_args.kwargs.get("json") or mock_client.post.call_args[1].get("json")
        assert "mutation" in call_json.get("query", "").lower() or "CreateIssue" in call_json.get("query", "")

    @pytest.mark.asyncio
    async def test_list_issues_returns_nodes(self, monkeypatch):
        monkeypatch.setenv("LINEAR_API_KEY", "lin_api_test")
        monkeypatch.setenv("LINEAR_TEAM_ID", "team-test-id")

        from app.integrations import linear

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.raise_for_status = MagicMock()
        mock_response.json.return_value = {
            "data": {
                "team": {
                    "issues": {
                        "nodes": [
                            {"id": "1", "identifier": "HOS-1", "title": "Story A", "url": "https://linear.app/..."},
                        ]
                    }
                }
            }
        }

        mock_client = AsyncMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        mock_client.post = AsyncMock(return_value=mock_response)

        with patch("app.integrations.linear.httpx.AsyncClient", return_value=mock_client):
            issues = await linear.list_issues(limit=5)

        assert isinstance(issues, list)
        assert issues[0]["identifier"] == "HOS-1"

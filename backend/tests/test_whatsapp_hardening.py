"""Tests for HOS-132 — WhatsApp & alert pipeline production hardening.

Coverage:
- AC4: a question is marked "answered" only once Twilio accepted the reply,
  sent to the manager's number (HOS-357: _bg_question; was generate_and_send)
- AC5: _validate_phone() correctly identifies valid/invalid E.164 numbers
- AC5: alert_dispatcher sets "config_error" on invalid phone (existing — smoke)
- AC6: run_pending() query excludes "config_error" status
"""
from __future__ import annotations

import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.services.alert_dispatcher import _validate_phone

# ===========================================================================
# AC5 — _validate_phone E.164 validation
# ===========================================================================

class TestValidatePhone:
    @pytest.mark.parametrize("number", [
        "+33612345678",
        "+447911123456",
        "+12025551234",
        "+1800555000",   # exactly 8 chars after +
    ])
    def test_valid_e164_numbers_return_true(self, number: str):
        assert _validate_phone(number) is True

    @pytest.mark.parametrize("number", [
        "",
        None,
        "0612345678",       # no leading +
        "+123",             # too short (< 8 chars total)
        "whatsapp:+336",    # prefix not stripped
        "not-a-number",
    ])
    def test_invalid_numbers_return_false(self, number):
        assert _validate_phone(number) is False


# ===========================================================================
# AC4 — a question is marked "answered" only once Twilio accepted the reply
# (HOS-357: the answer is sent by the route's _bg_question, to the manager's
# number — never to the digest stored on conversational_queries)
# ===========================================================================

_NUMBER = "whatsapp:+33612345678"


async def _run_bg_question(sent: bool, stored: dict):
    from app.api.routes import twilio_inbound as webhook
    from app.services.inbound_decision import ReplyPlan

    session = AsyncMock()
    session.__aenter__ = AsyncMock(return_value=session)
    session.__aexit__ = AsyncMock(return_value=False)
    queries = MagicMock()
    queries.parse_and_store = AsyncMock(return_value=stored)
    queries.mark_answered = AsyncMock()
    explainer = MagicMock()
    explainer.explain = AsyncMock(return_value="Concert au Zénith ce soir.")
    plan = ReplyPlan(text="Concert au Zénith ce soir.", result="question_answered")

    with patch.object(webhook, "AsyncSessionLocal", MagicMock(return_value=session)), \
         patch.object(webhook.InboundDecisionService, "profile_for",
                      new_callable=AsyncMock, return_value=MagicMock(manager_locale=None)), \
         patch.object(webhook.InboundDecisionService, "latest_recommendation",
                      new_callable=AsyncMock, return_value=MagicMock()), \
         patch.object(webhook.InboundDecisionService, "handle_question",
                      new_callable=AsyncMock, return_value=plan), \
         patch.object(webhook, "QueryParserService", MagicMock(return_value=queries)), \
         patch.object(webhook, "ExplainabilityService", MagicMock(return_value=explainer)), \
         patch.object(webhook, "_send_plan", new_callable=AsyncMock, return_value=sent) as send:
        await webhook._bg_question(from_number=_NUMBER, body="pourquoi ?")
    return send, queries, explainer


class TestQuestionAnsweredStatus:
    @pytest.mark.asyncio
    async def test_sets_answered_on_twilio_success(self):
        query_id = uuid.uuid4()
        send, queries, _ = await _run_bg_question(
            True, {"status": "stored", "query_id": str(query_id)})
        assert send.await_args.args[0] == _NUMBER   # the number, not a digest
        queries.mark_answered.assert_awaited_once()
        assert queries.mark_answered.await_args.args[0] == query_id

    @pytest.mark.asyncio
    async def test_does_not_set_answered_on_twilio_failure(self):
        _, queries, _ = await _run_bg_question(
            False, {"status": "stored", "query_id": str(uuid.uuid4())})
        queries.mark_answered.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_duplicate_question_is_not_answered_twice(self):
        send, queries, explainer = await _run_bg_question(
            True, {"status": "duplicate", "query_id": str(uuid.uuid4())})
        explainer.explain.assert_not_awaited()
        send.assert_not_awaited()
        queries.mark_answered.assert_not_awaited()


# ===========================================================================
# AC6 — run_pending() excludes config_error
# ===========================================================================

class TestRunPendingExcludesConfigError:
    @pytest.mark.asyncio
    async def test_run_pending_only_fetches_ready_to_push(self):
        """run_pending() must query status='ready_to_push', never 'config_error'."""
        from app.services.alert_dispatcher import AlertDispatcherService

        session = MagicMock()
        session.execute = AsyncMock(return_value=MagicMock(
            scalars=MagicMock(return_value=MagicMock(all=MagicMock(return_value=[])))
        ))

        await AlertDispatcherService().run_pending(session)

        call_args = session.execute.call_args
        stmt = call_args[0][0]
        # SQLAlchemy parameterises the value — check compiled params, not raw SQL string
        compiled = stmt.compile(compile_kwargs={"literal_binds": True})
        sql_str = str(compiled)
        assert "ready_to_push" in sql_str
        assert "config_error" not in sql_str


# ===========================================================================
# Q2-03 (HOS-289) — no PII (phone number / message body) in WhatsApp logs
# ===========================================================================
class TestWhatsAppLogPII:
    """Finding 8.5: sender/recipient numbers and message bodies must not be
    persisted to application logs."""

    def test_mask_number_hides_full_number(self):
        from app.services.whatsapp_service import _mask_number

        masked = _mask_number("whatsapp:+33612345678")
        assert "612345678" not in masked
        assert "33612345678" not in masked
        assert masked.startswith("whatsapp:")
        assert masked.endswith("78")

    def test_mask_number_handles_missing_or_bad_input(self):
        from app.services.whatsapp_service import _mask_number

        assert _mask_number(None) == "<none>"
        assert _mask_number("") == "<none>"

    def test_source_never_logs_raw_body_or_sender(self):
        """Regression guard against re-introducing the raw f-string logs."""
        import inspect

        import app.services.whatsapp_service as w

        src = inspect.getsource(w)
        assert "{body}" not in src, "message body must never be logged"
        assert "from {sender_raw}" not in src
        assert "sent to {to}" not in src

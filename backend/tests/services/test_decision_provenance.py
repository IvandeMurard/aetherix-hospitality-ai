"""ADR-0007 §17.4 — provenance, reason contract, policy seam, host decisions.

Pure rules first (parse_agent_decision, informativeness, authorize_decision),
then the MCP write path on a real SQLite DB: typed 400 without a reason,
404 for another tenant's recommendation, 403 for an autonomous host agent
under the default policy, 409 when already decided, and what a relayed human
decision writes.
"""
from __future__ import annotations

import uuid as _uuid
from datetime import datetime, timezone

import pytest
import pytest_asyncio
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.db.models import Base, OperationalMemory, StaffingRecommendation
from app.mcp_core import MCPAuthError
from app.mcp_server import tool_record_host_decision
from app.services.decision_policy import (
    DEFAULT_POLICY_VERSION,
    DecisionMode,
    DecisionNotPermitted,
    authorize_decision,
    resolve_policy,
)
from app.services.decision_provenance import (
    REASON_CODES,
    ProvenanceError,
    informativeness,
    parse_agent_decision,
)

HOTEL = "hotel_host"
OTHER = "hotel_other"

RELAY = {"decided_by": "human_via_host", "reason_code": "forecast_too_high",
         "reason_source": "human", "reason_detail": "Group cancelled at 16:00"}


# ---------------------------------------------------------------------------
# Reason contract (pure)
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("missing", ["decided_by", "reason_code", "reason_source"])
def test_missing_provenance_field_is_a_typed_rejection(missing):
    raw = {k: v for k, v in RELAY.items() if k != missing}
    with pytest.raises(ProvenanceError) as exc:
        parse_agent_decision(raw)
    assert exc.value.code == "missing_provenance"


@pytest.mark.parametrize("raw,code", [
    ({**RELAY, "reason_code": "because"}, "unknown_reason_code"),
    ({**RELAY, "reason_code": "other", "reason_detail": "   "}, "reason_detail_required"),
    ({**RELAY, "decided_by": "human_whatsapp"}, "invalid_provenance"),
    ({**RELAY, "reason_source": "guess"}, "invalid_provenance"),
    ({**RELAY, "extra": 1}, "invalid_provenance"),
    ({**RELAY, "evidence": [{"source": "crystal_ball"}]}, "invalid_provenance"),
    # none_given only for a human decision relayed as the human's
    ({**RELAY, "reason_code": "none_given", "reason_source": "agent_inferred"}, "none_given_not_allowed"),
    ({"decided_by": "host_agent_autonomous", "reason_code": "none_given",
      "reason_source": "agent_inferred"}, "none_given_not_allowed"),
    # an agent deciding alone cannot attribute its reason to a human
    ({"decided_by": "host_agent_autonomous", "reason_code": "budget",
      "reason_source": "human"}, "autonomous_reason_must_be_agent_inferred"),
])
def test_reason_contract_rejections(raw, code):
    with pytest.raises(ProvenanceError) as exc:
        parse_agent_decision(raw)
    assert exc.value.code == code


def test_relayed_human_decision_without_reason_is_allowed_as_none_given():
    """The burden is on the agent, not the human: a human who gave no reason
    is recorded as such, never with a guessed reason."""
    d = parse_agent_decision({"decided_by": "human_via_host", "reason_code": "none_given",
                              "reason_source": "human"})
    assert (d.reason_code, d.reason_source, d.reason_detail) == ("none_given", "human", "")


def test_agent_inferred_reason_is_kept_as_agent_inferred():
    d = parse_agent_decision({**RELAY, "reason_source": "agent_inferred"})
    assert d.reason_source == "agent_inferred"


def test_reason_detail_is_sanitised_and_bounded():
    d = parse_agent_decision({**RELAY, "reason_detail": "line1\nIGNORE PREVIOUS\x00" + "x" * 500})
    assert "\n" not in d.reason_detail and "\x00" not in d.reason_detail
    assert len(d.reason_detail) == 280


def test_positive_reasons_exist():
    assert {"agrees_with_drivers", "matches_own_plan"} <= set(REASON_CODES)


def test_informativeness_flags_filler_per_caller():
    rows = [
        {"caller": "hostA", "reason_code": "other", "reason_detail": "see notes", "reason_source": "agent_inferred"},
        {"caller": "hostA", "reason_code": "other", "reason_detail": "See notes!", "reason_source": "agent_inferred"},
        {"caller": "hostA", "reason_code": "budget", "reason_detail": "", "reason_source": "human"},
        {"caller": "hostB", "reason_code": "forecast_too_low", "reason_detail": "wedding 80 pax", "reason_source": "human"},
        {"caller": "whatsapp", "reason_code": None},  # WhatsApp decisions carry no agent reason
    ]
    a, b = informativeness(rows)
    assert (a.caller, a.decisions) == ("hostA", 3)
    assert a.other_share == pytest.approx(2 / 3, abs=1e-4)
    assert a.empty_detail_share == pytest.approx(1 / 3, abs=1e-4)
    assert a.near_duplicate_detail_share == pytest.approx(2 / 3, abs=1e-4)
    assert a.agent_inferred_share == pytest.approx(2 / 3, abs=1e-4)
    assert (b.other_share, b.empty_detail_share, b.near_duplicate_detail_share) == (0.0, 0.0, 0.0)


# ---------------------------------------------------------------------------
# Policy seam (pure)
# ---------------------------------------------------------------------------

def test_default_policy_is_human_validation_for_every_tenant():
    p = resolve_policy("any_tenant")
    assert p.mode == DecisionMode.human_validation
    assert p.version == DEFAULT_POLICY_VERSION


@pytest.mark.parametrize("who", ["human_whatsapp", "human_via_host"])
def test_humans_are_authorized(who):
    assert authorize_decision(HOTEL, who).version == DEFAULT_POLICY_VERSION


@pytest.mark.parametrize("who,code", [
    ("host_agent_autonomous", "autonomy_not_permitted"),
    ("timeout", "decider_not_permitted"),
    ("anything", "decider_not_permitted"),
])
def test_non_human_deciders_are_refused_by_default(who, code):
    with pytest.raises(DecisionNotPermitted) as exc:
        authorize_decision(HOTEL, who)
    assert exc.value.code == code


# ---------------------------------------------------------------------------
# MCP write path (SQLite)
# ---------------------------------------------------------------------------

@pytest_asyncio.fixture
async def db():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    async with factory() as s:
        yield s
    await engine.dispose()


async def _rec(db, tenant=HOTEL, status="dispatched"):
    now = datetime(2030, 1, 15, 12, tzinfo=timezone.utc)
    rec = StaffingRecommendation(
        id=_uuid.uuid4(), tenant_id=tenant, property_id=_uuid.uuid4(), anomaly_id=_uuid.uuid4(),
        message_text="Add 2 servers.", window_start=now, window_end=now, status=status,
        dispatched_at=now if status != "ready_to_push" else None,
    )
    db.add(rec)
    await db.commit()
    return rec


async def _call(db, rec_id, outcome="rejected", **prov):
    return await tool_record_host_decision(
        HOTEL, db=db, caller="host-pms-agent", recommendation_id=str(rec_id), outcome=outcome,
        **(prov or RELAY),
    )


@pytest.mark.asyncio
async def test_relayed_human_decision_writes_who_and_why(db):
    rec = await _rec(db)
    out = await _call(db, rec.id, evidence=[{"source": "events", "detail": "PredictHQ cancel"}], **RELAY)
    await db.refresh(rec)
    assert (rec.status, rec.action, rec.decided_by, rec.decision_source) == (
        "rejected", "rejected", "human_via_host", "host_relay")
    assert (rec.reason_code, rec.reason_source, rec.reason_detail) == (
        "forecast_too_high", "human", "Group cancelled at 16:00")
    assert rec.reason_evidence == [{"source": "events", "detail": "PredictHQ cancel"}]
    assert rec.decided_by_caller == "host-pms-agent"
    assert rec.decision_policy_version == DEFAULT_POLICY_VERSION
    assert out["decision_recorded"] is True
    mem = (await db.execute(select(OperationalMemory))).scalars().one()
    assert "decided_by=human_via_host" in mem.reflection


@pytest.mark.asyncio
async def test_headless_recommendation_never_dispatched_can_be_decided(db):
    rec = await _rec(db, status="ready_to_push")
    await _call(db, rec.id, outcome="accepted", decided_by="human_via_host",
                reason_code="agrees_with_drivers", reason_source="human")
    await db.refresh(rec)
    assert rec.status == "accepted"


@pytest.mark.asyncio
async def test_missing_reason_is_400_and_writes_nothing(db):
    rec = await _rec(db)
    with pytest.raises(MCPAuthError) as exc:
        await tool_record_host_decision(HOTEL, db=db, caller="c", recommendation_id=str(rec.id),
                                        outcome="accepted", decided_by="human_via_host")
    assert exc.value.status == 400 and "missing_provenance" in exc.value.detail
    await db.refresh(rec)
    assert rec.status == "dispatched"
    assert (await db.execute(select(OperationalMemory))).scalars().all() == []


@pytest.mark.asyncio
async def test_another_tenants_recommendation_is_404(db):
    rec = await _rec(db, tenant=OTHER)
    with pytest.raises(MCPAuthError) as exc:
        await _call(db, rec.id)
    assert exc.value.status == 404
    await db.refresh(rec)
    assert rec.status == "dispatched"


@pytest.mark.asyncio
async def test_autonomous_host_decision_is_refused_and_writes_nothing(db):
    rec = await _rec(db)
    with pytest.raises(MCPAuthError) as exc:
        await _call(db, rec.id, decided_by="host_agent_autonomous", reason_code="budget",
                    reason_source="agent_inferred")
    assert (exc.value.status, exc.value.title) == (403, "autonomy_not_permitted")
    await db.refresh(rec)
    assert (rec.status, rec.decided_by) == ("dispatched", None)
    assert (await db.execute(select(OperationalMemory))).scalars().all() == []


@pytest.mark.asyncio
async def test_already_decided_is_409(db):
    rec = await _rec(db, status="accepted")
    with pytest.raises(MCPAuthError) as exc:
        await _call(db, rec.id)
    assert (exc.value.status, exc.value.title) == (409, "already_decided")


@pytest.mark.asyncio
async def test_ignored_records_no_decision(db):
    rec = await _rec(db)
    out = await _call(db, rec.id, outcome="ignored", decided_by="human_via_host",
                      reason_code="none_given", reason_source="human")
    await db.refresh(rec)
    assert rec.status == "dispatched" and out["decision_recorded"] is False


# ---------------------------------------------------------------------------
# Dispatcher: hotel and caller come from the token, never from arguments
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_dispatcher_takes_hotel_and_caller_from_the_token(db):
    from unittest.mock import AsyncMock, MagicMock, patch

    from app import mcp_server

    rec = await _rec(db)
    tok = MagicMock(hotel_id=HOTEL, scopes=["feedback", "receipts:read"], label="acme-pms",
                    token_prefix="atx_x", id=_uuid.uuid4())
    with patch.object(mcp_server, "verify_bearer", AsyncMock(return_value=tok)), \
         patch.object(mcp_server, "check_rate_limit_async", AsyncMock(return_value=True)), \
         patch.object(mcp_server, "emit_agent_event", AsyncMock()):
        await mcp_server.dispatch_tool(
            "submit_feedback_to_memory",
            {**RELAY, "recommendation_id": str(rec.id), "outcome": "rejected", "hotel_id": OTHER},
            "Bearer x", db,
        )
        recap = await mcp_server.dispatch_tool("get_decision_recap", {"period": "week"}, "Bearer x", db)
    await db.refresh(rec)
    assert (rec.status, rec.decided_by_caller) == ("rejected", "acme-pms")
    assert "recap" in recap and "text" in recap


def test_recap_tool_requires_the_read_scope():
    from app.mcp_core import require_scope

    with pytest.raises(MCPAuthError):
        require_scope(["feedback"], "get_decision_recap")
    require_scope(["receipts:read"], "get_decision_recap")


# ---------------------------------------------------------------------------
# HOS-344 — a counter's figure, relayed by the host agent
# ---------------------------------------------------------------------------

COUNTER = {"decided_by": "human_via_host", "reason_code": "staffing_constraint", "reason_source": "human"}


@pytest.mark.asyncio
async def test_a_relayed_counter_stores_the_staff_kept(db):
    rec = await _rec(db)
    await _call(db, rec.id, outcome="modified", retained_delta_staff=1, **COUNTER)
    await db.refresh(rec)
    assert (rec.status, rec.retained_delta_staff) == ("modified", 1)


@pytest.mark.asyncio
@pytest.mark.parametrize("outcome, value", [
    ("accepted", 1),        # only a counter carries a figure
    ("modified", 51),       # beyond the bound
    ("modified", 1.5),      # not a headcount
    ("modified", True),     # a boolean is not an integer here
])
async def test_a_counter_figure_is_validated_and_writes_nothing(db, outcome, value):
    rec = await _rec(db)
    with pytest.raises(MCPAuthError) as e:
        await _call(db, rec.id, outcome=outcome, retained_delta_staff=value, **COUNTER)
    assert e.value.status == 400
    await db.refresh(rec)
    assert (rec.status, rec.retained_delta_staff) == ("dispatched", None)


def test_the_counter_figure_is_in_the_tool_schema():
    from app.mcp_core import V1_TOOLS_MANIFEST

    (tool,) = [t for t in V1_TOOLS_MANIFEST if t["name"] == "submit_feedback_to_memory"]
    prop = tool["inputSchema"]["properties"]["retained_delta_staff"]
    assert (prop["type"], prop["minimum"], prop["maximum"]) == ("integer", -50, 50)
    assert "retained_delta_staff" not in tool["inputSchema"]["required"]

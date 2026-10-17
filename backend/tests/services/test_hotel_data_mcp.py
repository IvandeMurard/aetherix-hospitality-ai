"""Hotel data through the hotel's own agent — HOS-349 (Décisions #43, #44).

The agent reads and requests over MCP; a deletion or an opt-in to the Hive
waits for the owner's WhatsApp confirmation with a code the agent never sees.
"""
from __future__ import annotations

import json
import re
import uuid
from datetime import datetime, timedelta, timezone

import pytest
import pytest_asyncio
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

from app.db.models import Base, HiveConsent, HotelDataRequest, MCPApiToken, RestaurantProfile
from app.mcp_core import HOTEL_DATA_TOOLS, V1_TOOLS_MANIFEST, MCPAuthError, hash_token
from app.mcp_server import dispatch_tool
from app.services import hive_gate as hg
from app.services import hotel_data_requests as hdr
from app.services import hotel_parameters as hp

T0 = datetime(2026, 10, 17, 9, 0, tzinfo=timezone.utc)
OWNER = "a1b2c3d4-0000-4000-8000-00000000000a"


@pytest_asyncio.fixture()
async def db():
    engine = create_async_engine(
        "sqlite+aiosqlite:///:memory:", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    maker = async_sessionmaker(engine, expire_on_commit=False)
    async with maker() as s:
        yield s
    await engine.dispose()


@pytest.fixture(autouse=True)
def _no_network(monkeypatch):
    """Rate limiting and the audit-log write are covered elsewhere; here they
    would reach Redis and the real database."""
    import app.mcp_server as srv

    async def no_limit(hotel_id, tool_name):
        return True

    async def no_log(event, session):
        return None

    monkeypatch.setattr(srv, "check_rate_limit_async", no_limit)
    monkeypatch.setattr(srv, "emit_agent_event", no_log)


@pytest.fixture()
def outbox(monkeypatch):
    """Capture what would be sent to the owner (WhatsApp + e-mail)."""
    sent: list[tuple[str, str]] = []

    async def fake_whatsapp(to, body):
        sent.append((to, body))

    async def fake_email(to, subject, body):
        sent.append((to, body))

    monkeypatch.setattr(hdr, "_send_whatsapp", fake_whatsapp)
    monkeypatch.setattr(hdr, "_send_email", fake_email)
    return sent


async def _hotel(db, tenant, phone="+33600000001", scopes=("hotel_data",)):
    db.add(RestaurantProfile(tenant_id=tenant, property_name="Hôtel", outlet_name=f"Resto {tenant}",
                             total_seats=80, owner_id=uuid.UUID(OWNER), phone_number=phone))
    raw = f"aex_{tenant}_{uuid.uuid4().hex}"
    db.add(MCPApiToken(hotel_id=tenant, token_hash=hash_token(raw), token_prefix="aex_",
                       label=f"agent-{tenant}", scopes=list(scopes)))
    await hp.set_parameter(db, tenant, "covers_per_server", 15, set_by=f"gm@{tenant}", set_via="dashboard_api", at=T0)
    await db.commit()
    return f"Bearer {raw}"


async def _call(db, tool, auth, **args):
    result = await dispatch_tool(tool, args, auth, db)
    await db.commit()
    return result


def _code(outbox) -> str:
    return re.search(r"\b([A-Z0-9]{6})\b \(", outbox[-1][1]).group(1)


async def _count(db, model, **where):
    stmt = select(func.count()).select_from(model)
    for k, v in where.items():
        stmt = stmt.where(getattr(model, k) == v)
    return (await db.execute(stmt)).scalar()


# --- manifest -------------------------------------------------------------------

def test_tools_are_served_scoped_and_attributed():
    names = {t["name"] for t in V1_TOOLS_MANIFEST}
    for t in HOTEL_DATA_TOOLS:
        assert t["name"] in names
        # The dispatcher strips these server-controlled keys from every call.
        assert not {"hotel_id", "request_id", "engine"} & set(t["inputSchema"].get("properties", {}))
        assert "Aetherix" in t["description"]


# --- scope and isolation --------------------------------------------------------------

@pytest.mark.asyncio
async def test_tools_refused_without_the_hotel_data_scope(db):
    auth = await _hotel(db, "h1", scopes=("receipts:read",))
    for t in HOTEL_DATA_TOOLS:
        with pytest.raises(MCPAuthError) as e:
            await dispatch_tool(t["name"], {"opted_in": False, "data_request_id": str(uuid.uuid4())}, auth, db)
        assert e.value.status == 403


@pytest.mark.asyncio
async def test_export_summary_and_pages_are_the_tokens_hotel_only(db, outbox):
    a1 = await _hotel(db, "h1")
    await _hotel(db, "h2", phone="+33600000002")
    summary = await _call(db, "get_hotel_data_export", a1)
    assert summary["source"] == "Aetherix" and summary["row_counts"]["restaurant_profiles"] == 1
    page = await _call(db, "get_hotel_data_export", a1, table="mcp_api_tokens")
    assert page["total"] == 1 and "token_hash" not in page["rows"][0]
    assert "h2" not in json.dumps(page)
    with pytest.raises(MCPAuthError):
        await _call(db, "get_hotel_data_export", a1, table="users")


@pytest.mark.asyncio
async def test_deletion_plan_deletes_nothing(db):
    a1 = await _hotel(db, "h1")
    plan = await _call(db, "get_hotel_data_deletion_plan", a1)
    assert plan["steps"][-1]["table"] == "restaurant_profiles"
    assert plan["rows_that_would_be_deleted"]["restaurant_profiles"] == 1
    assert await _count(db, RestaurantProfile, tenant_id="h1") == 1


# --- deletion: request, human confirmation, delay, execution -------------------------

@pytest.mark.asyncio
async def test_agent_request_never_deletes_and_never_sees_the_code(db, outbox):
    a1 = await _hotel(db, "h1")
    out = await _call(db, "request_hotel_data_deletion", a1, note="closing the restaurant")
    assert out["status"] == "pending_confirmation" and out["owner_notified"] is True
    code = _code(outbox)
    assert outbox[0][0] == "+33600000001"
    assert code not in json.dumps(out)
    assert await _count(db, RestaurantProfile, tenant_id="h1") == 1
    with pytest.raises(MCPAuthError) as e:                              # one open request per kind
        await _call(db, "request_hotel_data_deletion", a1)
    assert e.value.status == 409


@pytest.mark.asyncio
async def test_no_whatsapp_number_means_no_request(db, outbox):
    a1 = await _hotel(db, "h1", phone=None)
    with pytest.raises(MCPAuthError) as e:
        await _call(db, "request_hotel_data_deletion", a1)
    assert e.value.title == "no_verified_channel"


@pytest.mark.asyncio
async def test_owner_confirms_then_deletion_runs_only_after_the_delay(db, outbox):
    a1 = await _hotel(db, "h1")
    await _hotel(db, "h2", phone="+33600000002")
    await _call(db, "request_hotel_data_deletion", a1)
    code = _code(outbox)
    profile = (await db.execute(select(RestaurantProfile).where(RestaurantProfile.tenant_id == "h1"))).scalar_one()

    reply = await hdr.handle_command(db, profile, hdr.match_command(f"SUPPRIMER {code}"), now=T0 + timedelta(minutes=5))
    assert "ANNULER" in reply
    req = (await db.execute(select(HotelDataRequest))).scalar_one()
    assert req.status == "scheduled" and req.confirmed_by == "owner_whatsapp"

    assert await hdr.run_due_deletions(db, now=T0 + timedelta(hours=23)) == []
    assert await _count(db, RestaurantProfile, tenant_id="h1") == 1

    reports = await hdr.run_due_deletions(db, now=T0 + timedelta(hours=25))
    assert len(reports) == 1 and reports[0]["tenant_id"] == "h1"
    assert await _count(db, RestaurantProfile, tenant_id="h1") == 0
    assert await _count(db, RestaurantProfile, tenant_id="h2") == 1
    assert "+33600000001" in [to for to, _ in outbox[1:]]                # told before deletion


@pytest.mark.asyncio
async def test_wrong_code_other_hotel_or_expired_code_does_nothing(db, outbox):
    a1 = await _hotel(db, "h1")
    await _hotel(db, "h2", phone="+33600000002")
    await _call(db, "request_hotel_data_deletion", a1)
    code = _code(outbox)
    p1 = (await db.execute(select(RestaurantProfile).where(RestaurantProfile.tenant_id == "h1"))).scalar_one()
    p2 = (await db.execute(select(RestaurantProfile).where(RestaurantProfile.tenant_id == "h2"))).scalar_one()

    assert "aucune demande" in await hdr.handle_command(db, p1, hdr.match_command("SUPPRIMER ZZZZZZ"))
    assert "aucune demande" in await hdr.handle_command(db, p2, hdr.match_command(f"SUPPRIMER {code}"))
    late = datetime.now(timezone.utc) + timedelta(hours=3)
    assert "aucune demande" in await hdr.handle_command(db, p1, hdr.match_command(f"SUPPRIMER {code}"), now=late)
    assert await hdr.expire_stale(db, now=late) == 1
    assert (await db.execute(select(HotelDataRequest))).scalar_one().status == "expired"


@pytest.mark.asyncio
async def test_cancel_by_agent_or_by_owner_stops_the_deletion(db, outbox):
    a1 = await _hotel(db, "h1")
    out = await _call(db, "request_hotel_data_deletion", a1)
    cancelled = await _call(db, "cancel_hotel_data_request", a1, data_request_id=out["data_request_id"])
    assert cancelled["status"] == "cancelled" and cancelled["cancelled_by"].startswith("agent:")

    await _call(db, "request_hotel_data_deletion", a1)
    code = _code(outbox)
    p1 = (await db.execute(select(RestaurantProfile).where(RestaurantProfile.tenant_id == "h1"))).scalar_one()
    await hdr.handle_command(db, p1, hdr.match_command(f"DELETE {code}"))
    assert "cancelled" in (await hdr.handle_command(db, p1, hdr.match_command(f"CANCEL {code}"))).lower()
    assert await hdr.run_due_deletions(db, now=datetime.now(timezone.utc) + timedelta(days=2)) == []
    assert await _count(db, RestaurantProfile, tenant_id="h1") == 1
    listed = await _call(db, "get_hotel_data_requests", a1)
    assert [r["status"] for r in listed["requests"]] == ["cancelled", "cancelled"]
    assert all("code" not in k for r in listed["requests"] for k in r)


# --- Hive consent ---------------------------------------------------------------------

@pytest.mark.asyncio
async def test_agent_opts_out_at_once_but_never_opts_in_alone(db, outbox):
    a1 = await _hotel(db, "h1")
    out = await _call(db, "set_hive_consent", a1, opted_in=False)
    assert out["status"] == "opted_out" and out["set_via"] == "mcp"

    pending = await _call(db, "set_hive_consent", a1, opted_in=True)
    assert pending["status"] == "pending_confirmation"
    assert await hg.opted_in_tenants(db) == set()                       # nothing before the owner says yes

    p1 = (await db.execute(select(RestaurantProfile).where(RestaurantProfile.tenant_id == "h1"))).scalar_one()
    reply = await hdr.handle_command(db, p1, hdr.match_command(f"hive oui {_code(outbox)}"))
    assert "Hive" in reply
    assert await hg.opted_in_tenants(db) == {"h1"}
    latest = (await db.execute(select(HiveConsent).order_by(HiveConsent.set_at.desc()))).scalars().first()
    assert latest.set_via == "whatsapp" and latest.set_by == "owner_whatsapp"


@pytest.mark.asyncio
async def test_set_hive_consent_rejects_a_non_boolean(db):
    a1 = await _hotel(db, "h1")
    with pytest.raises(MCPAuthError) as e:
        await _call(db, "set_hive_consent", a1, opted_in="yes")
    assert e.value.status == 400


# --- WhatsApp command strictness --------------------------------------------------

@pytest.mark.parametrize("body,expected", [
    ("SUPPRIMER AB2CD3", ("confirm_deletion", "fr")),
    ("delete ab2cd3", ("confirm_deletion", "en")),
    ("Hive Oui AB2CD3", ("confirm_hive", "fr")),
    ("HIVE YES AB2CD3", ("confirm_hive", "en")),
    ("annuler AB2CD3", ("cancel", "fr")),
    ("supprimer", None),
    ("supprimer AB2CD", None),
    ("please delete AB2CD3", None),
    ("ok", None),
    ("recap semaine", None),
])
def test_commands_are_exact_whole_messages(body, expected):
    cmd = hdr.match_command(body)
    assert (None if cmd is None else (cmd.action, cmd.locale)) == expected


def test_golden_data_command_scenarios():
    """The receipt layer has no eval runner; this golden row is graded here."""
    from pathlib import Path

    golden = Path(__file__).resolve().parents[3] / "eval" / "golden_dataset.jsonl"
    rows = [json.loads(line) for line in golden.read_text(encoding="utf-8").splitlines()
            if line.strip() and json.loads(line)["id"].startswith("recpt-hotel-data-command-")]
    assert rows
    for row in rows:
        got = [(c.action if (c := hdr.match_command(m)) else None) for m in row["input"]["messages"]]
        assert got == row["expected"]["actions"], row["id"]

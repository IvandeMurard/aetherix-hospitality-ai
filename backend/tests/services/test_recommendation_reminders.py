"""One reminder before the point of no return — HOS-350 (Décisions #6, #43, #44)."""
from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone

import pytest
import pytest_asyncio
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

from app.db.models import Base, InboundReplyEvent, RestaurantProfile, StaffingRecommendation
from app.services import hotel_parameters as hp
from app.services import recommendation_reminders as rr
from app.services.decision_recap import RecRow, render_text, summarize

COMMIT = datetime(2026, 10, 17, 16, 0, tzinfo=timezone.utc)
T0 = COMMIT - timedelta(hours=10)


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


class Outbox:
    def __init__(self, fail=()):
        self.sent, self.fail = [], set(fail)

    async def __call__(self, channel, profile, text, template):
        if channel in self.fail:
            raise RuntimeError(f"{channel} down")
        self.sent.append((channel, text, template))


async def _setup(db, *, channel="whatsapp", phone="+33600000001", email="gm@h1.fr", task="staffing.add"):
    profile = (await db.execute(select(RestaurantProfile).where(RestaurantProfile.tenant_id == "h1"))).scalars().first()
    if profile is None:
        profile = RestaurantProfile(id=uuid.uuid4(), tenant_id="h1", property_name="P", outlet_name="O", total_seats=80)
        db.add(profile)
    profile.preferred_channel, profile.phone_number, profile.notification_email = channel, phone, email
    pid = profile.id
    rec = StaffingRecommendation(
        id=uuid.uuid4(), tenant_id="h1", property_id=pid, anomaly_id=uuid.uuid4(),
        message_text="Demain 101 couverts : 7 serveurs (règles de l'hôtel).",
        window_start=COMMIT + timedelta(hours=3), window_end=COMMIT + timedelta(hours=6),
        status="dispatched", dispatched_at=T0, commit_at=COMMIT, task_class=task,
    )
    db.add(rec)
    await db.commit()
    return pid, rec


async def _inbound(db, pid, at, rec_id=None):
    db.add(InboundReplyEvent(tenant_id="h1", property_id=pid, recommendation_id=rec_id,
                             channel="text", result="recorded", created_at=at))
    await db.commit()


async def _reload(db, rec):
    return (await db.execute(select(StaffingRecommendation).where(StaffingRecommendation.id == rec.id))).scalar_one()


# --- timing ------------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_not_due_before_the_offset_then_exactly_one_reminder(db, monkeypatch):
    monkeypatch.setattr(rr.config, "TWILIO_CONTENT_SID_REMINDER_FR", "HXreminder")
    _, rec = await _setup(db)
    out = Outbox()
    await rr.run_due(db, now=COMMIT - timedelta(hours=3), send=out)          # default offset 2 h
    assert out.sent == [] and (await _reload(db, rec)).reminder_status is None
    await rr.run_due(db, now=COMMIT - timedelta(hours=1), send=out)
    await rr.run_due(db, now=COMMIT - timedelta(minutes=30), send=out)
    assert len(out.sent) == 1
    r = await _reload(db, rec)
    assert r.reminder_status == "sent" and r.reminder_channel == "whatsapp" and r.status == "dispatched"


@pytest.mark.asyncio
async def test_hotel_offset_and_disable_are_respected(db):
    pid, rec = await _setup(db)
    await hp.set_parameter(db, "h1", "reminder_offset_hours.staffing.add", 6, set_by="gm@h1", set_via="dashboard_api")
    await db.commit()
    out = Outbox()
    await rr.run_due(db, now=COMMIT - timedelta(hours=5), send=out)
    assert len(out.sent) == 1                                                 # hotel's 6 h, not the 2 h default

    _, rec2 = await _setup(db, task="staffing.reduce")
    await hp.set_parameter(db, "h1", "reminder_offset_hours.staffing.reduce", 0, set_by="gm@h1", set_via="dashboard_api")
    await db.commit()
    await rr.run_due(db, now=COMMIT - timedelta(minutes=10), send=out)
    assert (await _reload(db, rec2)).reminder_status == "disabled" and len(out.sent) == 1


def test_default_offset_is_labelled_as_such():
    class P:
        def get(self, name):
            return None

    assert rr.offset_for(P(), "staffing.add") == rr.Offset(rr.DEFAULT_OFFSET_HOURS, "default")


@pytest.mark.asyncio
async def test_no_reminder_after_a_reply_a_decision_or_the_commit_point(db):
    pid, rec = await _setup(db)
    await _inbound(db, pid, T0 + timedelta(hours=1), rec_id=rec.id)
    out = Outbox()
    await rr.run_due(db, now=COMMIT - timedelta(hours=1), send=out)
    assert (await _reload(db, rec)).reminder_status == "skipped_answered" and out.sent == []

    _, late = await _setup(db)
    await rr.run_due(db, now=COMMIT + timedelta(minutes=1), send=out)
    assert (await _reload(db, late)).reminder_status == "missed" and out.sent == []


# --- channels and WhatsApp's 24 h rule -----------------------------------------------------

@pytest.mark.asyncio
async def test_whatsapp_outside_the_window_without_template_falls_back(db, monkeypatch):
    monkeypatch.setattr(rr.config, "TWILIO_CONTENT_SID_REMINDER_FR", "")
    _, rec = await _setup(db)                                                 # no inbound ever → outside window
    out = Outbox()
    await rr.run_due(db, now=COMMIT - timedelta(hours=1), send=out)
    assert [c for c, _, _ in out.sent] == ["email"]
    assert (await _reload(db, rec)).reminder_channel == "email"


@pytest.mark.asyncio
async def test_whatsapp_inside_the_window_is_free_text(db, monkeypatch):
    monkeypatch.setattr(rr.config, "TWILIO_CONTENT_SID_REMINDER_FR", "")
    pid, _ = await _setup(db)
    await _inbound(db, pid, COMMIT - timedelta(hours=5))                      # manager wrote 4 h before
    out = Outbox()
    await rr.run_due(db, now=COMMIT - timedelta(hours=1), send=out)
    channel, text, template = out.sent[0]
    assert channel == "whatsapp" and template == {} and "Sans réponse, rien n'est fait" in text


@pytest.mark.asyncio
async def test_template_send_carries_window_and_commit(db, monkeypatch):
    monkeypatch.setattr(rr.config, "TWILIO_CONTENT_SID_REMINDER_FR", "HXreminder")
    await _setup(db)
    out = Outbox()
    await rr.run_due(db, now=COMMIT - timedelta(hours=1), send=out)
    _, _, template = out.sent[0]
    assert template["sid"] == "HXreminder" and set(template["variables"]) == {"1", "2"}


@pytest.mark.asyncio
async def test_failed_channel_moves_to_the_next_then_records_failure(db, monkeypatch):
    monkeypatch.setattr(rr.config, "TWILIO_CONTENT_SID_REMINDER_FR", "")
    _, rec = await _setup(db, channel="email")
    out = Outbox(fail={"email"})
    await rr.run_due(db, now=COMMIT - timedelta(hours=1), send=out)
    assert [c for c, _, _ in out.sent] == ["sms"]                             # WhatsApp not allowed (window)

    _, rec2 = await _setup(db, channel="email", phone=None)
    await rr.run_due(db, now=COMMIT - timedelta(hours=1), send=Outbox(fail={"email"}))
    assert (await _reload(db, rec2)).reminder_status == "failed"


@pytest.mark.asyncio
async def test_no_usable_channel_is_recorded_never_forced(db, monkeypatch):
    monkeypatch.setattr(rr.config, "TWILIO_CONTENT_SID_REMINDER_FR", "")
    _, rec = await _setup(db, phone=None, email=None)
    await rr.run_due(db, now=COMMIT - timedelta(hours=1), send=Outbox())
    assert (await _reload(db, rec)).reminder_status == "no_compliant_channel"


def test_channel_plan_never_includes_whatsapp_outside_the_rule():
    class P:
        preferred_channel, phone_number, notification_email = "whatsapp", "+336", "a@b.fr"

    assert rr.channel_plan(P(), whatsapp_mode="outside_window") == ["email", "sms"]
    assert rr.channel_plan(P(), whatsapp_mode="session")[0] == "whatsapp"


# --- silence stays silence, and the recap counts ---------------------------------------

@pytest.mark.asyncio
async def test_silence_after_a_reminder_records_no_decision(db, monkeypatch):
    monkeypatch.setattr(rr.config, "TWILIO_CONTENT_SID_REMINDER_FR", "HXreminder")
    _, rec = await _setup(db)
    await rr.run_due(db, now=COMMIT - timedelta(hours=1), send=Outbox())
    await rr.run_due(db, now=COMMIT + timedelta(hours=1), send=Outbox())
    r = await _reload(db, rec)
    assert r.status == "dispatched" and r.action is None and r.decided_by is None


def test_recap_counts_reminders_and_answers_after_them():
    sent = COMMIT - timedelta(hours=1)
    base = dict(window_start=None, decided_by="human_whatsapp", decision_source="keyword",
                predicted_covers=None, actual_covers=None)
    rows = [
        RecRow(id=1, received_at=T0, status="accepted", actioned_at=sent + timedelta(minutes=5),
               reminder_sent_at=sent, **base),
        RecRow(id=2, received_at=T0, status="dispatched", actioned_at=None, reminder_sent_at=sent, **base),
        RecRow(id=3, received_at=T0, status="accepted", actioned_at=T0 + timedelta(hours=1), **base),
    ]
    s = summarize(rows, "week", T0.date(), T0.date())
    assert (s.reminders_sent, s.answered_after_reminder) == (2, 1)
    assert "Relances 2 · répondu après relance 1" in render_text(s, "fr")
    quiet = summarize([rows[2]], "week", T0.date(), T0.date())
    assert "Relances" not in render_text(quiet, "fr")

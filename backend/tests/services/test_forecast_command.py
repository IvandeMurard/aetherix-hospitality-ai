"""HOS-358 — "prévision mardi" on WhatsApp, and the one forecast context shared
by WhatsApp, the MCP tool and the predictions API.

What is pinned:
* the command is read without a model, whole reply only, FR/EN;
* the context is what the syncs stored, or absent with its reason — never a
  default presented as data (HOS-352);
* a caller's own context keys stay authoritative (MCP back-compat);
* the answer never shows a mock forecast as a figure, says whose staffing rules
  were used and what context is missing, and says the covers figure does not
  use that context yet;
* the command never writes a decision and never touches an open prompt.
"""
from __future__ import annotations

import uuid as _uuid
from datetime import date, datetime, timedelta, timezone
from unittest.mock import AsyncMock, patch

import pytest
import pytest_asyncio
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

from app.api.routes import twilio_inbound as webhook
from app.db.models import (
    Base,
    InboundReplyEvent,
    LocalEvent,
    ManagerPrompt,
    PMSSyncLog,
    RestaurantProfile,
    StaffingRecommendation,
    WeatherForecast,
)
from app.services import forecast_context
from app.services.forecast_reply import render_forecast
from app.services.manager_decision import (
    REPLY_RESULTS,
    ForecastCommand,
    match_forecast_command,
)

TENANT = "hotel_forecast"
PHONE = "+15550002222"
DAY = date(2030, 1, 15)               # a Tuesday
LAT, LNG = 48.8566, 2.3522


# ---------------------------------------------------------------------------
# The command
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("body, expected", [
    ("prévision", ForecastCommand(locale="fr")),
    ("Prévision ?", ForecastCommand(locale="fr")),
    ("prevision demain", ForecastCommand(days_ahead=1, locale="fr", ref="demain")),
    ("prévision mardi midi", ForecastCommand(weekday=1, service="lunch", locale="fr", ref="mardi")),
    ("prévision pour ce soir", ForecastCommand(service="dinner", locale="fr")),
    ("prévision 23/10", ForecastCommand(day_month=(23, 10), locale="fr", ref="23/10")),
    ("prévision petit-déjeuner demain",
     ForecastCommand(days_ahead=1, service="breakfast", locale="fr", ref="demain")),
    ("forecast friday lunch", ForecastCommand(weekday=4, service="lunch", locale="en", ref="friday")),
    ("forecast tonight", ForecastCommand(days_ahead=0, service="dinner", locale="en", ref="tonight")),
])
def test_reads_the_command(body, expected):
    assert match_forecast_command(body) == expected


@pytest.mark.parametrize("body", [
    "prévision trop haute hier",       # a comment, not the command
    "la prévision ?",                  # the command opens the reply
    "prévision mardi mercredi",        # two days
    "pourquoi ?", "oui", "recap", "",
])
def test_not_the_command(body):
    assert match_forecast_command(body) is None


@pytest.mark.parametrize("cmd, expected", [
    (ForecastCommand(), DAY),
    (ForecastCommand(days_ahead=1), DAY + timedelta(days=1)),
    (ForecastCommand(weekday=1), DAY),                       # today is Tuesday: today
    (ForecastCommand(weekday=0), DAY + timedelta(days=6)),   # next Monday
    (ForecastCommand(day_month=(20, 1)), date(2030, 1, 20)),
    (ForecastCommand(day_month=(10, 1)), date(2031, 1, 10)), # past this year → next year
    (ForecastCommand(day_month=(31, 2)), None),
])
def test_target_date_is_ahead(cmd, expected):
    assert cmd.target_date(DAY) == expected


def test_forecast_served_is_a_reply_result():
    assert "forecast_served" in REPLY_RESULTS


# ---------------------------------------------------------------------------
# The context: stored, true or absent
# ---------------------------------------------------------------------------

@pytest_asyncio.fixture
async def db():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:",
                                 connect_args={"check_same_thread": False}, poolclass=StaticPool)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async with factory() as s:
        yield s
    await engine.dispose()


async def _profile(db, coords: bool = True) -> RestaurantProfile:
    profile = RestaurantProfile(
        id=_uuid.uuid4(), tenant_id=TENANT, property_name="P", outlet_name="O",
        phone_number=PHONE, total_seats=80,
        latitude=LAT if coords else None, longitude=LNG if coords else None,
    )
    db.add(profile)
    await db.commit()
    return profile


def _weather(hour: int, code: int = 61, temp: float = 14.0) -> WeatherForecast:
    return WeatherForecast(
        tenant_id=TENANT, property_id=TENANT, condition_code=code, temperature_c=temp,
        precipitation_prob=80,
        forecast_timestamp=datetime(DAY.year, DAY.month, DAY.day, hour, tzinfo=timezone.utc),
    )


def _event(title: str = "Concert Bercy") -> LocalEvent:
    return LocalEvent(
        tenant_id=TENANT, event_id=title, title=title, category="concerts", rank=80,
        phq_attendance=5000, latitude=LAT + 0.005, longitude=LNG,
        start_dt=datetime(DAY.year, DAY.month, DAY.day, 19, tzinfo=timezone.utc),
        end_dt=datetime(DAY.year, DAY.month, DAY.day, 23, tzinfo=timezone.utc),
    )


def _pms(status: str = "ok", sold: int | None = 82, available: int | None = 100) -> PMSSyncLog:
    return PMSSyncLog(tenant_id=TENANT, sync_date=DAY, rooms_sold=sold,
                      rooms_available=available, occupancy_status=status)


@pytest.mark.asyncio
async def test_context_from_what_was_stored(db):
    profile = await _profile(db)
    db.add_all([_weather(9, code=0, temp=8.0), _weather(20), _event(), _pms()])
    await db.commit()
    ctx = await forecast_context.build(db, profile, DAY, "dinner")
    assert ctx["weather"] == {"condition": "rain", "condition_code": 61, "temp": 14.0,
                              "precipitation_prob": 80}      # the row nearest 20:00
    assert [e["name"] for e in ctx["events"]] == ["Concert Bercy"]
    assert ctx["occupancy"] == 0.82
    assert {k: v["status"] for k, v in ctx["context_sources"].items()} == {
        "weather": "ok", "events": "ok", "occupancy": "ok"}


@pytest.mark.asyncio
async def test_nothing_stored_is_absent_never_a_default(db):
    profile = await _profile(db)
    ctx = await forecast_context.build(db, profile, DAY, "lunch")
    assert (ctx["weather"], ctx["events"], ctx["occupancy"]) == ({}, [], None)
    assert ctx["context_sources"]["weather"]["reason"] == "no_forecast_near_service"
    assert ctx["context_sources"]["occupancy"]["reason"] == "not_synced_for_day"


@pytest.mark.asyncio
async def test_weather_too_far_from_the_service_is_absent(db):
    profile = await _profile(db)
    db.add(_weather(9))
    await db.commit()
    ctx = await forecast_context.build(db, profile, DAY, "dinner")
    assert ctx["weather"] == {}


@pytest.mark.asyncio
async def test_no_coordinates_no_weather_no_events(db):
    profile = await _profile(db, coords=False)
    db.add_all([_weather(20), _event()])
    await db.commit()
    ctx = await forecast_context.build(db, profile, DAY, "dinner")
    assert (ctx["weather"], ctx["events"]) == ({}, [])
    assert ctx["context_sources"]["weather"]["reason"] == "no_hotel_coordinates"
    assert ctx["context_sources"]["events"]["reason"] == "no_hotel_coordinates"


@pytest.mark.asyncio
@pytest.mark.parametrize("status, sold, available, expected", [
    ("pms_error", None, None, None),
    ("not_configured", None, None, None),
    ("no_data", None, None, None),
    ("ok", 10, 0, None),                 # no rooms: no rate, never a division by zero
    ("fixture", 50, 100, 0.5),           # demo data carries its status in the provenance
])
async def test_occupancy_only_when_the_pms_gave_it(db, status, sold, available, expected):
    profile = await _profile(db)
    db.add(_pms(status, sold, available))
    await db.commit()
    ctx = await forecast_context.build(db, profile, DAY, "dinner")
    assert ctx["occupancy"] == expected
    assert ctx["context_sources"]["occupancy"]["status"] == (status if expected is not None else "absent")


def test_caller_keys_win_and_empty_values_do_not():
    built = {"weather": {"condition": "rain"}, "events": [{"name": "E"}], "occupancy": 0.8,
             "context_sources": {"weather": {"status": "ok"}, "events": {"status": "ok"},
                                 "occupancy": {"status": "ok"}}}
    merged = forecast_context.merge(
        {"weather": {"condition": "Unknown"}, "events": [], "occupancy": 0.6, "banquet": True}, built)
    assert merged["weather"] == {"condition": "rain"}          # "Unknown" is not a value
    assert merged["events"] == [{"name": "E"}]                 # [] is not a value
    assert merged["occupancy"] == 0.6 and merged["banquet"] is True
    assert merged["context_sources"]["occupancy"]["status"] == "caller"
    assert forecast_context.merge(None, built)["occupancy"] == 0.8


@pytest.mark.parametrize("code, label", [(0, "clear"), (2, "partly_cloudy"), (3, "cloudy"),
                                         (45, "fog"), (63, "rain"), (75, "snow"),
                                         (81, "showers"), (95, "thunderstorm"), (None, None),
                                         (42, None)])
def test_wmo_labels(code, label):
    assert forecast_context.wmo_label(code) == label


def test_rag_query_never_writes_a_default_occupancy():
    from app.services.rag_service import RAGService

    text = RAGService.build_context_string(object.__new__(RAGService), DAY, "dinner",
                                           {"weather": {}, "events": [], "occupancy": None})
    assert "Hotel Occupancy: unknown" in text and "0.8" not in text


# ---------------------------------------------------------------------------
# The answer
# ---------------------------------------------------------------------------

_CTX = {"weather": {"condition": "rain", "temp": 14.0}, "events": [
    {"name": "Concert Bercy", "distance_km": 0.56}], "occupancy": None,
    "context_sources": {"events": {"status": "ok"}, "occupancy": {"status": "absent"}}}
_RESULT = {
    "prediction": {"covers": 84.4, "is_mock": False, "range_min": 70, "range_max": 98},
    "staffing_recommendation": {
        "servers": 6, "hosts": 1, "runners": 0, "kitchen": 3,
        "deltas": {"servers": 2, "hosts": 0, "kitchen": 1, "sommeliers": 0},
        "rules": {"servers": {"covers_per_source": "hotel"}, "hosts": {"covers_per_source": "hotel"},
                  "kitchen": {"covers_per_source": "hotel"}, "sommeliers": {"source": "default"}},
    },
}


def test_answer_fr():
    text = render_forecast(_RESULT, _CTX, DAY, "dinner", "fr")
    assert text.splitlines() == [
        "Prévision mardi 15/01, dîner : 84 couverts (fourchette 70–98).",
        "Effectif conseillé : 6 serveurs (+2), 1 à l'accueil, 3 en cuisine (+1) (règles de l'hôtel).",
        "À savoir : pluie, 14 °C ; Concert Bercy (0,6 km) ; occupation inconnue.",
        "La prévision de couverts ne tient pas encore compte de ce contexte.",
    ]


def test_answer_en_with_default_rules_and_calibrated_interval():
    result = {**_RESULT, "prediction": {**_RESULT["prediction"], "calibrated_interval": [72.4, 95.6]},
              "staffing_recommendation": {**_RESULT["staffing_recommendation"], "rules": {
                  "servers": {"covers_per_source": "default"}}}}
    text = render_forecast(result, {**_CTX, "occupancy": 0.82}, DAY, "lunch", "en")
    assert text.startswith("Forecast Tuesday 15/01, lunch: 84 covers (range 72–96).")
    assert "(default rules, not set by the hotel)" in text
    assert "occupancy 82%" in text


def test_mock_forecast_is_never_a_figure():
    result = {"prediction": {"covers": 45, "is_mock": True, "range_min": 38, "range_max": 52}}
    text = render_forecast(result, _CTX, DAY, "dinner", "fr")
    assert text.startswith("mardi 15/01, dîner : pas de prévision chiffrée")
    assert "45" not in text and "Effectif" not in text
    assert "ne tient pas encore compte" not in text


def test_engine_unavailable_is_said():
    text = render_forecast(None, {"weather": {}, "events": [], "occupancy": None,
                                  "context_sources": {"events": {"status": "absent"}}},
                           DAY, "dinner", "fr")
    assert text.splitlines() == [
        "mardi 15/01, dîner : prévision indisponible pour le moment.",
        "À savoir : météo inconnue ; événements inconnus ; occupation inconnue.",
    ]


def test_recommendation_already_sent_is_shown():
    rec = StaffingRecommendation(status="dispatched", message_text="+2 extras",
                                 risk_assessment={"recommended_delta_staff": 2})
    text = render_forecast(_RESULT, _CTX, DAY, "dinner", "fr", rec)
    assert "Recommandation déjà envoyée pour ce jour : 2 extras (en attente de décision)." in text


def test_baseline_used_is_said():
    result = {**_RESULT, "prediction": {**_RESULT["prediction"], "baseline_used": True}}
    assert "Valeur de référence" in render_forecast(result, _CTX, DAY, "dinner", "fr")


# ---------------------------------------------------------------------------
# The route: background task, never a decision
# ---------------------------------------------------------------------------

class _SessionCtx:
    def __init__(self, session):
        self._session = session

    async def __aenter__(self):
        return self._session

    async def __aexit__(self, *exc):
        return False


class _Engine:
    def __init__(self, result):
        self.result = result
        self.calls = []

    async def get_forecast(self, tenant_id, target_date, service_type, context):
        self.calls.append((tenant_id, target_date, service_type, context))
        return self.result


async def _run(db, body, engine):
    reply = AsyncMock(return_value="SM1")
    cmd = match_forecast_command(body)
    with (
        patch.object(webhook, "AsyncSessionLocal", lambda: _SessionCtx(db)),
        patch.object(webhook, "_now", lambda: datetime(DAY.year, DAY.month, DAY.day, 10,
                                                       tzinfo=timezone.utc)),
        patch.object(webhook._twilio_client, "send_whatsapp", reply),
    ):
        await webhook._bg_forecast(from_number=f"whatsapp:{PHONE}", command=cmd, engine=engine)
    return reply


@pytest.mark.asyncio
async def test_bg_forecast_uses_the_stored_context_and_writes_no_decision(db):
    profile = await _profile(db)
    rec = StaffingRecommendation(
        id=_uuid.uuid4(), tenant_id=TENANT, property_id=profile.id, anomaly_id=_uuid.uuid4(),
        message_text="+2 extras", window_start=datetime(DAY.year, DAY.month, DAY.day, 19,
                                                        tzinfo=timezone.utc),
        window_end=datetime(DAY.year, DAY.month, DAY.day, 23, tzinfo=timezone.utc),
        status="dispatched", dispatched_at=datetime(DAY.year, DAY.month, DAY.day, 9,
                                                    tzinfo=timezone.utc),
        risk_assessment={"recommended_delta_staff": 2},
    )
    prompt = ManagerPrompt(
        created_at=datetime(DAY.year, DAY.month, DAY.day, 9, 55, tzinfo=timezone.utc),
        tenant_id=TENANT, property_id=profile.id, recommendation_id=rec.id,
        kind="decision_confirmation", proposed_decision="accepted", origin="model",
        status="pending", expires_at=datetime(DAY.year, DAY.month, DAY.day, 10, 55,
                                              tzinfo=timezone.utc), request_id="r0")
    db.add_all([rec, prompt, _weather(20), _pms()])
    await db.commit()
    engine = _Engine(_RESULT)

    reply = await _run(db, "prévision ce soir", engine)

    [(tenant, day, service, ctx)] = engine.calls
    assert (tenant, day, service) == (TENANT, DAY, "dinner")
    assert ctx["weather"]["condition"] == "rain" and ctx["occupancy"] == 0.82
    to, text = reply.await_args.args
    assert to == f"whatsapp:{PHONE}"
    assert text.startswith("Prévision mardi 15/01, dîner : 84 couverts")
    assert "Recommandation déjà envoyée pour ce jour : 2 extras" in text
    assert "occupation 82 %" in text
    await db.refresh(rec)
    await db.refresh(prompt)
    assert (rec.status, rec.action, rec.decision_source) == ("dispatched", None, None)
    assert prompt.status == "pending"
    [ev] = (await db.execute(select(InboundReplyEvent))).scalars().all()
    assert (ev.result, ev.why, ev.recommendation_id) == ("forecast_served", "served", rec.id)


@pytest.mark.asyncio
async def test_bg_forecast_mock_and_unavailable(db):
    await _profile(db)
    reply = await _run(db, "prévision", _Engine({"prediction": {"covers": 45, "is_mock": True}}))
    assert "pas de prévision chiffrée" in reply.await_args.args[1]
    reply = await _run(db, "prévision", None)
    assert "prévision indisponible" in reply.await_args.args[1]
    whys = [e.why for e in (await db.execute(select(InboundReplyEvent))).scalars().all()]
    assert sorted(whys) == ["mock", "unavailable"]


@pytest.mark.asyncio
async def test_bg_forecast_bad_date(db):
    await _profile(db)
    reply = await _run(db, "prévision 31/02", _Engine(_RESULT))
    assert reply.await_args.args[1] == "Je ne trouve pas la date « 31/02 »."


def test_route_sends_the_command_to_the_background_with_the_engine(monkeypatch):
    from fastapi import FastAPI
    from fastapi.testclient import TestClient
    from unittest.mock import MagicMock

    from app.db.session import get_db

    monkeypatch.setenv("TWILIO_SKIP_SIGNATURE_VALIDATION", "true")
    app = FastAPI()
    app.include_router(webhook.router)
    app.state.engine = sentinel = object()

    async def _noop_db():
        yield AsyncMock()

    app.dependency_overrides[get_db] = _noop_db
    with patch.object(webhook, "_bg_forecast", new_callable=AsyncMock) as bg, \
         patch.object(webhook, "_bg_question", new_callable=AsyncMock) as bg_q, \
         patch.object(webhook.InboundDecisionService, "profile_for",
                      new_callable=AsyncMock, return_value=MagicMock()), \
         patch.object(webhook.InboundDecisionService, "handle_deterministic",
                      new_callable=AsyncMock) as deterministic:
        with TestClient(app) as client:
            resp = client.post("/webhooks/twilio/inbound",
                               data={"From": PHONE, "Body": "prévision demain ?", "To": "+1"})
    assert resp.status_code == 200
    bg.assert_awaited_once()
    assert bg.await_args.kwargs["engine"] is sentinel
    assert bg.await_args.kwargs["command"].days_ahead == 1
    deterministic.assert_not_awaited()            # never reaches decision capture
    bg_q.assert_not_awaited()


# ---------------------------------------------------------------------------
# The MCP tool and /predict share the context
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_mcp_tool_uses_the_stored_context_and_the_caller_wins(db):
    from app.mcp_server import tool_get_operational_predictions

    await _profile(db)
    db.add_all([_weather(20), _pms()])
    await db.commit()
    engine = _Engine({"prediction": {"covers": 80}})
    await tool_get_operational_predictions(TENANT, DAY.isoformat(), engine=engine, db=db)
    await tool_get_operational_predictions(TENANT, DAY.isoformat(), engine=engine, db=db,
                                           context={"occupancy": 0.5, "events": []})
    (_, _, _, first), (_, _, _, second) = engine.calls
    assert first["weather"]["condition"] == "rain" and first["occupancy"] == 0.82
    assert second["occupancy"] == 0.5 and second["weather"]["condition"] == "rain"


@pytest.mark.asyncio
async def test_predictions_current_invents_nothing(db):
    from types import SimpleNamespace

    from app.api.routes.predictions import get_property_prediction

    profile = await _profile(db)
    profile.owner_id = owner = _uuid.uuid4()
    await db.commit()
    engine = _Engine({"prediction": {"covers": 80}})
    request = SimpleNamespace(app=SimpleNamespace(state=SimpleNamespace(engine=engine)))
    await get_property_prediction(request, target_date=DAY, service_type="dinner",
                                  current_user={"id": owner}, db=db)
    [(_, _, _, ctx)] = engine.calls
    assert ctx["weather"] == {} and ctx["occupancy"] is None   # was "Clear, 22 °C" and 0.85

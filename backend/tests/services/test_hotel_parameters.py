"""Per-hotel decision parameters (ADR-0007 §18.3, Décision #40)."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest
import pytest_asyncio
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

from app.db.models import Base, RestaurantProfile
from app.services import hotel_parameters as hp

T0 = datetime(2026, 9, 25, 8, 0, tzinfo=timezone.utc)


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


@pytest.mark.parametrize("name,value", [
    ("extra_shift_cost", 0), ("extra_shift_cost", -5), ("extra_shift_cost", 2000.01),
    ("lost_cover_value", float("inf")), ("covers_per_extra_staff", 0),
    ("max_extra_staff", 2.5), ("max_extra_staff", 51), ("commit_offset_hours.staffing.add", -1),
    ("unknown_param", 1), ("extra_shift_cost", "abc"),
])
def test_out_of_bounds_values_are_refused_never_clamped(name, value):
    with pytest.raises(hp.ParameterError):
        hp.validate(name, value)


def test_valid_values_and_clear():
    assert hp.validate("extra_shift_cost", 180) == 180.0
    assert hp.validate("max_extra_staff", 0) == 0.0
    assert hp.validate("commit_offset_hours.staffing.reduce", 168) == 168.0
    assert hp.validate("lost_cover_value", None) is None


def test_catalog_covers_every_task_class_offset():
    for key in ("staffing.add", "staffing.reduce", "food_prep.batch"):
        assert f"commit_offset_hours.{key}" in hp.CATALOG


@pytest.mark.asyncio
async def test_latest_value_wins_with_provenance_and_clear(db):
    await hp.set_parameter(db, "h1", "extra_shift_cost", 150, set_by="a@x", set_via="dashboard_api", at=T0)
    await hp.set_parameter(db, "h1", "extra_shift_cost", 180, set_by="b@x", set_via="ops",
                           note="agency rate 2026", at=T0 + timedelta(hours=1))
    await hp.set_parameter(db, "h1", "lost_cover_value", 22, set_by="b@x", set_via="dashboard_api", at=T0)
    await hp.set_parameter(db, "h1", "lost_cover_value", None, set_by="b@x", set_via="dashboard_api",
                           at=T0 + timedelta(hours=2))
    await hp.set_parameter(db, "h2", "extra_shift_cost", 999, set_by="c@x", set_via="dashboard_api", at=T0)
    params = await hp.load(db, "h1")
    assert params.get("extra_shift_cost") == 180.0
    pv = params.values["extra_shift_cost"]
    assert (pv.set_by, pv.set_via, pv.currency, pv.note) == ("b@x", "ops", "EUR", "agency rate 2026")
    assert params.get("lost_cover_value") is None           # cleared → missing → no money
    assert "lost_cover_value" in params.as_dict()["missing"]
    hist = await hp.history(db, "h1", "extra_shift_cost")
    assert [h["value"] for h in hist] == [180.0, 150.0]      # append-only, newest first
    assert all(h["set_by"] for h in await hp.history(db, "h1"))


@pytest.mark.asyncio
async def test_money_in_another_currency_is_ignored_not_converted(db, monkeypatch):
    from app.core import config

    await hp.set_parameter(db, "h1", "extra_shift_cost", 150, set_by="a@x", set_via="ops", at=T0)
    await hp.set_parameter(db, "h1", "covers_per_extra_staff", 20, set_by="a@x", set_via="ops", at=T0)
    monkeypatch.setattr(config, "CURRENCY", "GBP")
    params = await hp.load(db, "h1")
    assert params.get("extra_shift_cost") is None and "extra_shift_cost" in params.ignored
    assert params.get("covers_per_extra_staff") == 20.0     # not money: unaffected


@pytest.mark.asyncio
async def test_write_requires_provenance(db):
    with pytest.raises(hp.ParameterError):
        await hp.set_parameter(db, "h1", "extra_shift_cost", 150, set_by=" ", set_via="dashboard_api")
    with pytest.raises(hp.ParameterError):
        await hp.set_parameter(db, "h1", "extra_shift_cost", 150, set_by="a", set_via="guess")


@pytest.mark.asyncio
async def test_commit_offsets_exposed_for_the_formatter(db):
    await hp.set_parameter(db, "h1", "commit_offset_hours.staffing.reduce", 168, set_by="a", set_via="ops", at=T0)
    params = await hp.load(db, "h1")
    assert params.commit_offsets() == {"staffing.reduce": 168.0}
    assert params.version() == T0.isoformat()


# ---------------------------------------------------------------------------
# Route — tenant-scoped
# ---------------------------------------------------------------------------

def _client(db, user):
    from app.api.routes import hotel_parameters as route
    from app.core.security import get_current_user
    from app.db.session import get_db

    app = FastAPI()
    app.include_router(route.router, prefix="/api/v1")

    async def _db():
        yield db

    app.dependency_overrides[get_db] = _db
    app.dependency_overrides[get_current_user] = lambda: user
    return TestClient(app)


async def _profile(db, tenant, owner):
    import uuid

    db.add(RestaurantProfile(tenant_id=tenant, property_name="P", outlet_name="O",
                             total_seats=80, owner_id=uuid.UUID(owner)))
    await db.commit()


OWNER = "a1b2c3d4-0000-4000-8000-00000000000a"
OTHER = "b1b2c3d4-0000-4000-8000-00000000000b"


@pytest.mark.asyncio
async def test_route_owner_sets_and_reads_with_provenance(db):
    await _profile(db, "h1", OWNER)
    user = {"id": OWNER, "email": "gm@hotel", "is_superuser": False}
    with _client(db, user) as c:
        r = c.put("/api/v1/hotels/h1/decision-parameters/extra_shift_cost", json={"value": 175, "note": "loaded"})
        assert r.status_code == 200 and r.json()["set_by"] == "gm@hotel" and r.json()["currency"] == "EUR"
        bad = c.put("/api/v1/hotels/h1/decision-parameters/extra_shift_cost", json={"value": -1})
        assert bad.status_code == 422
        got = c.get("/api/v1/hotels/h1/decision-parameters").json()
        assert got["values"]["extra_shift_cost"]["value"] == 175.0
        assert got["values"]["extra_shift_cost"]["set_via"] == "dashboard_api"
        assert "lost_cover_value" in got["missing"] and got["catalog"]


@pytest.mark.asyncio
@pytest.mark.parametrize("method,path,body", [
    ("get", "/api/v1/hotels/h1/decision-parameters", None),
    ("get", "/api/v1/hotels/h1/decision-parameters/history", None),
    ("put", "/api/v1/hotels/h1/decision-parameters/extra_shift_cost", {"value": 100}),
    ("get", "/api/v1/hotels/nope/decision-parameters", None),
])
async def test_route_refuses_a_tenant_the_user_does_not_own(db, method, path, body):
    await _profile(db, "h1", OWNER)
    with _client(db, {"id": OTHER, "email": "x@y", "is_superuser": False}) as c:
        resp = c.put(path, json=body) if method == "put" else c.get(path)
    assert resp.status_code == 403
    assert await hp.history(db, "h1") == []


@pytest.mark.asyncio
async def test_formatter_context_reads_the_hotels_own_offsets(db):
    import uuid

    from app.services.recommendation_formatter import RecommendationFormatterService

    await hp.set_parameter(db, "h1", "commit_offset_hours.staffing.add", 12, set_by="a", set_via="ops", at=T0)
    ctx = await RecommendationFormatterService()._load_decision_context(db, "h1", uuid.uuid4())
    assert ctx["commit_offsets"] == {"staffing.add": 12.0}
    assert ctx["params"].get("extra_shift_cost") is None  # not configured → no money downstream

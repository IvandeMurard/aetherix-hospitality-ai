"""Hotel data ownership — export, deletion, Hive gate (HOS-346, Décision #43)."""
from __future__ import annotations

import json
import re
import uuid
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

import pytest
import pytest_asyncio
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

from app.db.models import (
    Base, FBPattern, HiveConsent, HotelDecisionParameter, MCPApiToken, OperationalMemory,
    PMSSyncLog, RestaurantProfile,
)
from app.services import hive_gate as hg
from app.services import hotel_data as hd
from app.services import hotel_parameters as hp

T0 = datetime(2026, 10, 17, 8, 0, tzinfo=timezone.utc)
OWNER = "a1b2c3d4-0000-4000-8000-00000000000a"
OTHER = "b1b2c3d4-0000-4000-8000-00000000000b"


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


async def _seed_hotel(db, tenant, owner, pms=None):
    db.add(RestaurantProfile(tenant_id=tenant, property_name="P", outlet_name="O", total_seats=80,
                             owner_id=uuid.UUID(owner), pms_property_id=pms))
    await hp.set_parameter(db, tenant, "covers_per_server", 15, set_by=f"gm@{tenant}", set_via="dashboard_api", at=T0)
    await hg.set_consent(db, tenant, True, set_by=f"gm@{tenant}", set_via="dashboard_api", at=T0)
    db.add(FBPattern(tenant_id=tenant, service_type="dinner", pattern_text=f"{tenant} pattern", embedding=[0.1] * 1536))
    db.add(OperationalMemory(hotel_id=tenant, reflection=f"{tenant} reflection"))
    db.add(MCPApiToken(hotel_id=tenant, token_hash=f"secret-{tenant}", token_prefix="aex_"))
    db.add(PMSSyncLog(tenant_id=pms or tenant, sync_date=date(2026, 10, 1), status="success"))
    await db.commit()


# --- inventory ---------------------------------------------------------------

def test_every_table_is_classified():
    tables = set(Base.metadata.tables)
    classified = set(hd.HOTEL_TABLES) | set(hd.NOT_HOTEL_DATA)
    assert tables - classified == set(), "classify new tables in hotel_data.HOTEL_TABLES or NOT_HOTEL_DATA"
    assert classified - tables == set()
    assert not set(hd.HOTEL_TABLES) & set(hd.NOT_HOTEL_DATA)


def test_key_and_omitted_columns_exist():
    for name, rule in hd.HOTEL_TABLES.items():
        cols = Base.metadata.tables[name].c
        assert rule.key in cols, (name, rule.key)
        for c in rule.omit:
            assert c in cols, (name, c)


def test_deletion_order_respects_foreign_keys():
    for name, rule in hd.HOTEL_TABLES.items():
        for col in Base.metadata.tables[name].columns:
            for fk in col.foreign_keys:
                parent = fk.column.table.name
                if parent in hd.HOTEL_TABLES and parent != name:
                    assert rule.order < hd.HOTEL_TABLES[parent].order, f"{name} must be deleted before {parent}"


def test_plan_is_readable_and_ends_with_the_profile():
    steps = hd.build_deletion_plan("h1", "PAR")
    assert steps[-1].table == "restaurant_profiles"
    assert "property_id = 'PAR'" in next(s.match for s in steps if s.table == "training_runs")
    text = hd.render_plan("h1", steps)
    assert "restaurant_profiles" in text and "backups" in text


# --- export --------------------------------------------------------------------

@pytest.mark.asyncio
async def test_export_holds_everything_of_one_hotel_and_nothing_of_another(db):
    await _seed_hotel(db, "h1", OWNER, pms="PAR")
    await _seed_hotel(db, "h2", OTHER)
    db.add(FBPattern(tenant_id=None, service_type="dinner", pattern_text="global seed"))
    await db.commit()

    out = await hd.export_hotel_data(db, "h1")
    rec = out["records"]
    assert [r["tenant_id"] for r in rec["restaurant_profiles"]] == ["h1"]
    assert [r["pattern_text"] for r in rec["fb_patterns"]] == ["h1 pattern"]      # not h2, not the global seed
    assert rec["hotel_decision_parameters"][0]["set_by"] == "gm@h1"               # provenance travels
    assert rec["pms_sync_logs"][0]["tenant_id"] == "PAR"                          # PMS-id rows found too (HOS-347)
    assert "h2" not in json.dumps(out)
    assert "embedding" not in rec["fb_patterns"][0] and "token_hash" not in rec["mcp_api_tokens"][0]
    assert "secret-h1" not in json.dumps(out)
    assert out["omitted_columns"]["mcp_api_tokens"] == ["token_hash"]
    assert out["caveats"]


# --- deletion ------------------------------------------------------------------

async def _count(db, model, **where):
    stmt = select(func.count()).select_from(model)
    for k, v in where.items():
        stmt = stmt.where(getattr(model, k) == v)
    return (await db.execute(stmt)).scalar()


@pytest.mark.asyncio
async def test_dry_run_is_the_default_and_deletes_nothing(db):
    await _seed_hotel(db, "h1", OWNER)
    report = await hd.execute_deletion(db, "h1")
    assert report.dry_run is True
    assert report.rows["restaurant_profiles"] == 1 and report.rows["fb_patterns"] == 1
    assert await _count(db, RestaurantProfile, tenant_id="h1") == 1


@pytest.mark.asyncio
async def test_deletion_removes_one_hotel_only_and_keeps_global_patterns(db):
    await _seed_hotel(db, "h1", OWNER, pms="PAR")
    await _seed_hotel(db, "h2", OTHER)
    db.add(FBPattern(tenant_id=None, service_type="dinner", pattern_text="global seed"))
    await db.commit()

    report = await hd.execute_deletion(db, "h1", dry_run=False)
    assert report.as_dict()["total_rows"] >= 7
    for model, key in ((RestaurantProfile, "tenant_id"), (HotelDecisionParameter, "tenant_id"),
                       (HiveConsent, "tenant_id"), (FBPattern, "tenant_id"), (OperationalMemory, "hotel_id"),
                       (MCPApiToken, "hotel_id")):
        assert await _count(db, model, **{key: "h1"}) == 0, model.__tablename__
        assert await _count(db, model, **{key: "h2"}) == 1, model.__tablename__
    assert await _count(db, PMSSyncLog, tenant_id="PAR") == 0
    assert await _count(db, FBPattern, tenant_id=None) == 1


# --- Hive gate -----------------------------------------------------------------

def _contrib(n):
    return {f"h{i}": float(10 + i) for i in range(n)}


def test_hive_refuses_below_the_floor_of_hotels():
    with pytest.raises(hg.HiveRefused) as e:
        hg.aggregate("covers_per_server", _contrib(4), set(_contrib(4)))
    assert e.value.reason == "below_floor"


def test_hive_ignores_hotels_that_did_not_opt_in():
    contrib = _contrib(6)
    with pytest.raises(hg.HiveRefused):                      # 4 opted in < floor
        hg.aggregate("m", contrib, {"h0", "h1", "h2", "h3"})
    agg = hg.aggregate("m", contrib, set(contrib) - {"h5"})
    assert agg.n_hotels == 5 and agg.mean == 12.0           # h5 (15.0) excluded


def test_hive_output_never_carries_a_hotel_id_or_a_single_value():
    contrib = {"tenant_alpha": 11.0, "tenant_beta": 13.0, "tenant_gamma": 17.0, "tenant_delta": 19.0, "tenant_eps": 23.0}
    agg = hg.aggregate("m", contrib, set(contrib))
    out = json.dumps(agg.as_dict())
    assert set(agg.as_dict()) == {"metric", "n_hotels", "mean"}
    assert not re.search(r"tenant_", out)
    assert agg.mean not in contrib.values()


def test_hive_concentration_guard():
    contrib = _contrib(5)
    weights = {t: 1.0 for t in contrib} | {"h0": 10.0}
    with pytest.raises(hg.HiveRefused) as e:
        hg.aggregate("m", contrib, set(contrib), weights=weights)
    assert e.value.reason == "concentration"


@pytest.mark.asyncio
async def test_consent_latest_row_wins_and_opt_out_excludes(db):
    await hg.set_consent(db, "h1", True, set_by="gm@h1", set_via="dashboard_api", at=T0)
    await hg.set_consent(db, "h2", True, set_by="gm@h2", set_via="dashboard_api", at=T0)
    await hg.set_consent(db, "h1", False, set_by="gm@h1", set_via="dashboard_api", at=T0 + timedelta(hours=1))
    assert await hg.opted_in_tenants(db) == {"h2"}
    c = await hg.consent_for(db, "h1")
    assert c["opted_in"] is False and len(c["history"]) == 2
    with pytest.raises(ValueError):
        await hg.set_consent(db, "h3", True, set_by="", set_via="dashboard_api")


def test_nothing_writes_cross_hotel_rows_outside_the_gate():
    """No app code may insert into fb_patterns (the only cross-hotel table)
    except through hive_gate. Seeds live in scripts/, not in app/."""
    app_dir = Path(__file__).resolve().parents[2] / "app"
    offenders = []
    for path in app_dir.rglob("*.py"):
        if path.name == "hive_gate.py":
            continue
        src = path.read_text(encoding="utf-8")
        if re.search(r"INSERT\s+INTO\s+fb_patterns", src, re.I) or re.search(r"\bFBPattern\(", src):
            if path.name != "models.py":
                offenders.append(str(path.relative_to(app_dir)))
    assert offenders == []


# --- routes --------------------------------------------------------------------

def _client(db, user):
    from app.api.routes import hotel_data as route
    from app.core.security import get_current_user
    from app.db.session import get_db

    app = FastAPI()
    app.include_router(route.router, prefix="/api/v1")

    async def _db():
        yield db

    app.dependency_overrides[get_db] = _db
    app.dependency_overrides[get_current_user] = lambda: user
    return TestClient(app)


@pytest.mark.asyncio
async def test_routes_owner_exports_previews_and_deletes_with_confirmation(db):
    await _seed_hotel(db, "h1", OWNER)
    c = _client(db, {"id": OWNER, "email": "gm@h1", "is_superuser": False})
    assert c.get("/api/v1/hotels/h1/data/export").json()["row_counts"]["restaurant_profiles"] == 1
    plan = c.get("/api/v1/hotels/h1/data/deletion-plan").json()
    assert plan["rows_that_would_be_deleted"]["restaurant_profiles"] == 1
    assert c.post("/api/v1/hotels/h1/data/deletion", json={"confirm_tenant_id": "h2"}).status_code == 422
    dry = c.post("/api/v1/hotels/h1/data/deletion", json={"confirm_tenant_id": "h1"}).json()
    assert dry["dry_run"] is True and await _count(db, RestaurantProfile, tenant_id="h1") == 1
    done = c.post("/api/v1/hotels/h1/data/deletion", json={"confirm_tenant_id": "h1", "dry_run": False}).json()
    assert done["dry_run"] is False and await _count(db, RestaurantProfile, tenant_id="h1") == 0


@pytest.mark.asyncio
async def test_routes_owner_sets_hive_consent_with_provenance(db):
    await _seed_hotel(db, "h1", OWNER)
    c = _client(db, {"id": OWNER, "email": "gm@h1", "is_superuser": False})
    r = c.put("/api/v1/hotels/h1/hive-consent", json={"opted_in": False, "note": "not now"})
    assert r.status_code == 200 and r.json()["set_by"] == "gm@h1"
    assert c.get("/api/v1/hotels/h1/hive-consent").json()["opted_in"] is False


@pytest.mark.asyncio
@pytest.mark.parametrize("method,path,body", [
    ("get", "/api/v1/hotels/h1/data/export", None),
    ("get", "/api/v1/hotels/h1/data/deletion-plan", None),
    ("post", "/api/v1/hotels/h1/data/deletion", {"confirm_tenant_id": "h1", "dry_run": False}),
    ("get", "/api/v1/hotels/h1/hive-consent", None),
    ("put", "/api/v1/hotels/h1/hive-consent", {"opted_in": True}),
])
async def test_routes_refuse_another_hotels_data(db, method, path, body):
    await _seed_hotel(db, "h1", OWNER)
    c = _client(db, {"id": OTHER, "email": "x@other", "is_superuser": False})
    r = getattr(c, method)(path, json=body) if body is not None else getattr(c, method)(path)
    assert r.status_code == 403
    assert await _count(db, RestaurantProfile, tenant_id="h1") == 1

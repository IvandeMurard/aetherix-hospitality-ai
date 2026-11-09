"""push_demo_recommendation: sizes with the product's rule and stores a
ready_to_push recommendation the dispatcher can send (SQLite, no network)."""
from __future__ import annotations

import asyncio
import importlib.util
import uuid
from datetime import date
from pathlib import Path

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

SCRIPT = Path(__file__).resolve().parents[3] / "scripts" / "ops" / "push_demo_recommendation.py"


def _load():
    spec = importlib.util.spec_from_file_location("push_demo_recommendation", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


async def _run(apply: bool, *, phone="+33600000000", pending=False, costs=True):
    from app.db.models import Base, RestaurantProfile, StaffingRecommendation

    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    mod = _load()
    async with factory() as db:
        profile = RestaurantProfile(id=uuid.uuid4(), tenant_id="demo_hotel", property_name="P",
                                    outlet_name="O", total_seats=78, phone_number=phone, manager_locale="fr")
        db.add(profile)
        if pending:
            db.add(StaffingRecommendation(
                id=uuid.uuid4(), tenant_id="demo_hotel", property_id=profile.id, anomaly_id=uuid.uuid4(),
                message_text="m", window_start=date(2030, 1, 1), window_end=date(2030, 1, 1), status="dispatched"))
        await db.commit()
        out = await mod.build(db, tenant="demo_hotel", point=120.0, baseline=115.0, trigger="match à 2 km (21:00)",
                              day=date(2030, 1, 15), apply=apply, allow_pending=False, set_demo_costs=costs)
        recs = (await db.execute(select(StaffingRecommendation).where(
            StaffingRecommendation.status == "ready_to_push"))).scalars().all()
    await engine.dispose()
    return out, recs, profile


def test_dry_run_writes_nothing_and_sizes_with_the_newsvendor_rule():
    out, recs, _ = asyncio.run(_run(apply=False))
    assert recs == [] and out["id"] is None
    assert out["decision_rule"] == "newsvendor-v1" and out["delta"] == 2
    assert "Si accepté" in out["message"] and "données synthétiques" in out["message"]


def test_apply_stores_a_ready_to_push_recommendation_for_the_profile():
    out, recs, profile = asyncio.run(_run(apply=True))
    (rec,) = recs
    assert str(rec.id) == out["id"]
    assert str(rec.property_id) == str(profile.id)  # the dispatcher joins on this
    assert rec.risk_assessment["decision_rule"] == "newsvendor-v1"


def test_without_costs_it_says_so_and_falls_back():
    out, _, _ = asyncio.run(_run(apply=False, costs=False))
    assert out["decision_rule"] == "deviation-scale-v1" and out["missing_inputs"]


@pytest.mark.parametrize("kwargs", [{"phone": ""}, {"pending": True}])
def test_refuses_when_the_dispatch_or_the_reply_would_be_ambiguous(kwargs):
    with pytest.raises(SystemExit):
        asyncio.run(_run(apply=True, **kwargs))

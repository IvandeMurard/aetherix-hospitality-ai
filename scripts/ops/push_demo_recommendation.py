"""Push one staffing recommendation to the demo hotel's WhatsApp, through the real chain.

Sizes a recommendation with the product's rule (``risk_assessment.assess``,
newsvendor), composes the message the way ``RecommendationFormatterService``
does for that rule, and stores it as ``ready_to_push`` for the demo tenant.
The dispatch worker running on staging (every 2 minutes) then sends it to the
manager's phone; the manager's reply goes through the Twilio webhook like any
other. Nothing here sends a message itself.

Honesty (Décisions #11, #33): fictional hotel, fictional forecast; the
uncertainty is the committed *synthetic* calibration and the message says so;
costs are the hotel's parameters (``--set-demo-costs`` writes fictional ones,
labelled ``demo (fictif)``, if none are set).

Prerequisites (runbook §5.3): the phone has joined the Twilio sandbox, and has
written to it within the last 23 h 30 (a business-initiated message without an
approved template is only delivered inside that window). Only one recommendation
should be awaiting a decision, so that "ok" is unambiguous: the script refuses
to add one while another is pending, unless ``--allow-pending``.

Usage (from the repository root, with the staging DATABASE_URL in backend/.env):
    backend/.venv/Scripts/python scripts/ops/push_demo_recommendation.py --env backend/.env
    backend/.venv/Scripts/python scripts/ops/push_demo_recommendation.py --env backend/.env --apply
"""
from __future__ import annotations

import argparse
import asyncio
import os
import sys
import uuid
from datetime import date, datetime, time, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT / "backend"))

CALIBRATION = REPO_ROOT / "backend" / "data" / "calibration" / "prophet-predictionengine-synthetic-v1.json"
FORECASTER = "prophet-predictionengine-v1"
LOCAL_TZ = ZoneInfo("Europe/Paris")
DEMO_COSTS = {"covers_per_extra_staff": 15.0, "extra_shift_cost": 180.0, "lost_cover_value": 45.0}


async def build(db, *, tenant: str, point: float, baseline: float, trigger: str, day: date,
                apply: bool, allow_pending: bool, set_demo_costs: bool) -> dict:
    """Size and (with ``apply``) store one ``ready_to_push`` recommendation.
    Returns what was (or would be) stored. Commits only with ``apply``."""
    from sqlalchemy import select

    from app.db.models import RestaurantProfile, StaffingRecommendation
    from app.services import hotel_parameters as hp
    from app.services import risk_assessment as ra
    from app.services import task_classes
    from app.services.forecast_calibration import Calibration
    from app.services.recommendation_formatter import format_message

    profile = (await db.execute(
        select(RestaurantProfile).where(RestaurantProfile.tenant_id == tenant)
    )).scalars().first()
    if profile is None:
        raise SystemExit(f"no restaurant profile for tenant {tenant!r}")
    if not (profile.phone_number or "").startswith("+"):
        raise SystemExit(f"profile {tenant!r} has no E.164 phone_number: the dispatcher would skip it")

    pending = (await db.execute(
        select(StaffingRecommendation).where(
            StaffingRecommendation.property_id == uuid.UUID(str(profile.id)),
            StaffingRecommendation.status.in_(["ready_to_push", "dispatched"]),
        )
    )).scalars().all()
    if pending and not allow_pending:
        ids = ", ".join(f"{r.id} ({r.status})" for r in pending)
        raise SystemExit(f"{len(pending)} recommendation(s) already awaiting dispatch or a decision: {ids}. "
                         "Answer them first, or pass --allow-pending.")

    params = await hp.load(db, tenant)
    missing = [k for k in DEMO_COSTS if params.get(k) is None]
    if missing and set_demo_costs:
        for name in missing:
            await hp.set_parameter(db, tenant, name, DEMO_COSTS[name], set_by="demo (fictif)",
                                   set_via="ops", note="push_demo_recommendation : valeur fictive de démo")
        params = await hp.load(db, tenant)
        missing = []

    calibration = Calibration.load(CALIBRATION)
    c = params.get("covers_per_extra_staff")
    assessment = ra.assess(ra.Inputs(
        task_class=task_classes.TaskClassKey.staffing_add, point_forecast=point,
        baseline_covers=baseline, fallback_delta_staff=1, forecaster=FORECASTER,
        calibration=calibration, params=params, covers_per_staff=c,
        covers_per_staff_source="hotel_parameter" if c is not None else None,
    ))
    delta = int(assessment["recommended_delta_staff"])
    start = datetime.combine(day, time(19, 0), tzinfo=LOCAL_TZ)
    end = start + timedelta(hours=4)
    message = format_message("surge", max(delta, 1), 0.0, 0.0, start, end, trigger, show_money=False)
    if assessment["material"]:
        message = "\n".join([message, *ra.render_lines(assessment, profile.manager_locale or "fr")])

    out = {
        "tenant": tenant, "profile_id": str(profile.id), "delta": delta,
        "decision_rule": assessment["decision_rule"], "missing_inputs": missing,
        "message": message, "window": f"{start:%d/%m %H:%M}–{end:%H:%M} (Paris)", "id": None,
    }
    if not apply:
        return out

    rec = StaffingRecommendation(
        id=uuid.uuid4(), tenant_id=tenant, property_id=uuid.UUID(str(profile.id)),
        anomaly_id=uuid.uuid4(), message_text=message, triggering_factor=trigger,
        recommended_headcount=delta, predicted_covers=point,
        window_start=start, window_end=end, status="ready_to_push",
        task_class=assessment["task_class"], decision_rule=assessment["decision_rule"],
        risk_assessment=assessment,
    )
    db.add(rec)
    await db.commit()
    out["id"] = str(rec.id)
    return out


def _load_env(path: Path) -> None:
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


async def _main(args: argparse.Namespace) -> None:
    from app.db.session import AsyncSessionLocal

    day = date.fromisoformat(args.day) if args.day else datetime.now(LOCAL_TZ).date() + timedelta(days=1)
    async with AsyncSessionLocal() as db:
        out = await build(db, tenant=args.tenant, point=args.point, baseline=args.baseline,
                          trigger=args.trigger, day=day, apply=args.apply,
                          allow_pending=args.allow_pending, set_demo_costs=args.set_demo_costs)
    print(f"Tenant {out['tenant']} · créneau {out['window']} · règle {out['decision_rule']} · +{out['delta']}")
    if out["missing_inputs"]:
        print(f"  ⚠ coûts absents ({', '.join(out['missing_inputs'])}) : règle de repli, sans lignes de risque. "
              "Relancer avec --set-demo-costs pour des coûts fictifs étiquetés.")
    print("  Message :")
    for line in out["message"].splitlines():
        print(f"    {line}")
    if out["id"]:
        print(f"  ✅ enregistrée ready_to_push · id {out['id']} · envoi par le dispatcher sous 2 min")
    else:
        print("  (simulation : rien n'est écrit ; ajouter --apply pour l'enregistrer)")


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--env", required=True, help="fichier .env contenant DATABASE_URL (staging)")
    ap.add_argument("--tenant", default="demo_hotel")
    ap.add_argument("--point", type=float, default=120.0, help="couverts prévus (fictif)")
    ap.add_argument("--baseline", type=float, default=115.0, help="couverts pour lesquels l'équipe habituelle est dimensionnée")
    ap.add_argument("--trigger", default="match à 2 km (21:00)")
    ap.add_argument("--day", help="date du service AAAA-MM-JJ (défaut : demain)")
    ap.add_argument("--apply", action="store_true", help="enregistrer (sinon simulation)")
    ap.add_argument("--allow-pending", action="store_true")
    ap.add_argument("--set-demo-costs", action="store_true",
                    help="poser des coûts fictifs étiquetés s'ils manquent")
    args = ap.parse_args()
    _load_env(Path(args.env))
    asyncio.run(_main(args))


if __name__ == "__main__":
    main()

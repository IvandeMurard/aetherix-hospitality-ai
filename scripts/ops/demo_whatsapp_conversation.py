"""WhatsApp decision loop and learning loop, replayed on the production services — demo script.

Two fictional weeks at a fictional hotel (Maison Lumen). Each day a staffing
recommendation is sized by the product's own rule (``risk_assessment.assess``,
newsvendor), the manager replies in WhatsApp words, and the reply goes through
the services the Twilio webhook calls (``InboundDecisionService``,
``ReceiptsService.parse_inbound``, ``ExplainabilityService``, the recap
template). After the two weeks, the weekly learning pass
(``learning_store.run_pass``) runs, a named person approves its proposal
(``learning_store.decide``), the next recommendation is sized with the new
value, and the change is rolled back in one call (``rollback_parameter``).

The three feedback loops, each with its honest status:
* human feedback — decisions, reasons, corrections: built, replayed here;
* recommendation vs actual — actual covers are fictional and *declared*, not
  POS (``independent_actuals: false``); POS comparison is HOS-364;
* debrief of the last service — the "Dernier dîner mesuré" line is a PROTOTYPE computed
  by this script (HOS-363), not yet in the product. It is labelled as such.

* Database: SQLite in memory, schema from the ORM. No Supabase, no Twilio, no
  network. Nothing is sent.
* Model: replies the lexicon cannot decide reach the model.
  - ``--model claude:<exact model id>`` (needs ``ANTHROPIC_API_KEY``): the real
    model is called, as in production (tier pinned to that model).
  - default: a SCRIPTED stand-in returns a fixed answer for each of those
    replies. Every such line is labelled ``SCRIPTÉ`` — it shows the plumbing,
    never the model's quality.
* Data: fictional hotel, fictional covers and costs; the forecast uncertainty
  is the committed *synthetic* calibration (Décision #33).

Usage:
    backend/.venv/bin/python scripts/ops/demo_whatsapp_conversation.py
    ANTHROPIC_API_KEY=... backend/.venv/bin/python scripts/ops/demo_whatsapp_conversation.py \
        --model claude:claude-haiku-4-5-20251001
"""
from __future__ import annotations

import argparse
import asyncio
import json
import logging
import os
import sys
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT / "backend"))
# app.db.session builds an engine object at import time (no connection opened).
os.environ.setdefault("DATABASE_URL", "postgresql+asyncpg://demo:demo@localhost:5432/demo")
os.environ.setdefault("PII_HASH_PEPPER", "demo-only-pepper-not-a-secret")

from sqlalchemy import select  # noqa: E402
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine  # noqa: E402

from app.db.models import (  # noqa: E402
    Base,
    InboundReplyEvent,
    RestaurantProfile,
    StaffingRecommendation,
)
from app.services import hotel_parameters as hp  # noqa: E402
from app.services import learning_store as ls  # noqa: E402
from app.services import risk_assessment as ra  # noqa: E402
from app.services import task_classes  # noqa: E402
from app.services.explainability_service import ExplainabilityService  # noqa: E402
from app.services.forecast_calibration import Calibration  # noqa: E402
from app.services.inbound_decision import InboundDecisionService  # noqa: E402
from app.services.manager_decision import is_question  # noqa: E402
from app.services.receipts import ReceiptsService  # noqa: E402
from app.services.recommendation_formatter import format_message  # noqa: E402

TENANT = "demo_maison_lumen"
PHONE = "+33600000000"  # fictional
TZ = timezone.utc
CALIBRATION = REPO_ROOT / "backend" / "data" / "calibration" / "prophet-predictionengine-synthetic-v1.json"
FORECASTER = "prophet-predictionengine-v1"
OWNER = {"email": "claire@maison-lumen.example"}  # the hotel's approver (fictional)

# Hotel parameters (fictional): the ratio the recommendation is sized with and
# the costs the newsvendor rule weighs. Set by the hotel, as in production.
PARAMS = {"covers_per_extra_staff": 15.0, "extra_shift_cost": 180.0, "lost_cover_value": 45.0}

# Forecast and usual-staffing baseline (covers) for two kinds of evening.
NORMAL = (90.0, 95.0)   # a regular dinner → the rule proposes +1
EVENT = (120.0, 115.0)  # an event night  → the rule proposes +2

# ── Week 1: the conversation, one path per day ──────────────────────────────
# Each recommendation is sent at 14:00 the day before the dinner it is about
# (J-1). Days are named after the SERVICE, as the manager names them.
# (service day, sent at, kind, trigger, replies, actual covers (fictional))
WEEK1 = [
    ("mardi 10/11", datetime(2026, 11, 9, 14, tzinfo=TZ), NORMAL,
     "séminaire résident (60 pers.)", ["ok"], 88.0),
    ("mercredi 11/11", datetime(2026, 11, 10, 14, tzinfo=TZ), NORMAL,
     "pluie annoncée, clients sur place", ["pas besoin", "le séminaire dîne dehors ce soir"], 80.0),
    ("jeudi 12/11", datetime(2026, 11, 11, 14, tzinfo=TZ), EVENT,
     "match à 2 km (21:00)", ["mets-en 3 de plus"], 131.0),
    ("vendredi 13/11", datetime(2026, 11, 12, 14, tzinfo=TZ), NORMAL,
     "occupation 91 %", ["pourquoi ?", "bof, ça me paraît beaucoup", "oui"], 93.0),
    (None, datetime(2026, 11, 13, 14, tzinfo=TZ), None, None,
     ["corriger mardi refus", "oui", "recap semaine"], None),
]

# ── Week 2: the same manager, seven dinners, told compactly ─────────────────
# On event nights Claire always keeps one more extra than proposed.
WEEK2 = [
    ("mardi 17/11", NORMAL, "réservations habituelles", "ok", 91.0),
    ("mercredi 18/11", NORMAL, "groupe affaires (20 pers.)", "ok", 96.0),
    ("jeudi 19/11", NORMAL, "occupation 84 %", "ok", 89.0),
    ("vendredi 20/11", EVENT, "banquet de mariage (80 pers.)", "mets-en 3 de plus", 128.0),
    ("samedi 21/11", EVENT, "concert à 1 km (20:30)", "mets-en 3 de plus", 133.0),
    ("dimanche 22/11", NORMAL, "brunch prolongé", "ok", 87.0),
    ("lundi 23/11", NORMAL, "réservations habituelles", "ok", 90.0),
]
WEEK2_FIRST_SEND = datetime(2026, 11, 16, 14, tzinfo=TZ)
LEARNING_PASS_AT = datetime(2026, 11, 23, 3, 40, tzinfo=TZ)  # Monday 03:40, as the worker
NEXT_EVENT = ("mardi 24/11", datetime(2026, 11, 23, 14, tzinfo=TZ), EVENT, "match à 2 km (21:00)")

# What the scripted stand-in answers, per (reply, kind of call). "stance" = the
# reply classifier, "route" = the reason router. Any other call (e.g. the
# explanation) gets no scripted answer: the code takes its deterministic path.
SCRIPTED = {
    ("mets-en 3 de plus", "stance"): {"stance": "counter_value", "confidence": 0.9},
    ("pourquoi ?", "stance"): {"stance": "none", "confidence": 0.95},
    ("bof, ça me paraît beaucoup", "stance"): {"stance": "decline_proposal", "confidence": 0.6},
    ("le séminaire dîne dehors ce soir", "route"): {"route": "memory", "confidence": 0.8},
}


class ScriptedModel:
    """Stand-in for the model. Answers from SCRIPTED, or raises (the callers
    then take their own deterministic fallback, as in production)."""

    model_id = "SCRIPTÉ (aucun modèle appelé)"

    def __init__(self) -> None:
        self.last: str | None = None

    async def complete(self, messages, max_tokens=500, temperature=0.3, system=None, tier="reasoning"):
        text = json.dumps(messages, ensure_ascii=False) + (system or "")
        for (reply, kind), answer in SCRIPTED.items():
            if json.dumps(reply, ensure_ascii=False)[1:-1] in text and f'"{kind}"' in text:
                self.last = f"SCRIPTÉ → {json.dumps(answer, ensure_ascii=False)}"
                return json.dumps(answer)
        self.last = "SCRIPTÉ → pas de réponse (repli déterministe du code)"
        raise RuntimeError("scripted stand-in: no answer for this call")


class RecordingModel:
    """Real provider, recording the last raw answer for display."""

    def __init__(self, inner, label: str) -> None:
        self._inner = inner
        self.model_id = label
        self.last: str | None = None

    async def complete(self, messages, max_tokens=500, temperature=0.3, system=None, tier="reasoning"):
        raw = await self._inner.complete(messages=messages, max_tokens=max_tokens,
                                         temperature=temperature, system=system, tier=tier)
        self.last = f"modèle réel {self.model_id} → {raw.strip()[:160]}"
        return raw


def build_model(target: str | None):
    if not target:
        return ScriptedModel()
    provider, _, model = target.partition(":")
    if provider != "claude" or not model:
        raise SystemExit("--model expects claude:<exact model id>")
    key = os.environ.get("ANTHROPIC_API_KEY", "")
    if not key:
        raise SystemExit("ANTHROPIC_API_KEY is not set — the real model cannot be called.")
    from app.providers.claude_provider import ClaudeProvider

    return RecordingModel(ClaudeProvider(api_key=key, model=model, fast_model=model), target)


# ── Display ──────────────────────────────────────────────────────────────────

def say_agent(text: str) -> None:
    for i, line in enumerate((text or "").splitlines() or [""]):
        print(("  🤖 Aetherix : " if i == 0 else "               ") + line)


def say_manager(text: str) -> None:
    print(f"  👤 Manager  : {text}")


def note(text: str) -> None:
    print(f"     · {text}")


def title(text: str) -> None:
    print(f"\n━━ {text} ━━")


_DECISION_FR = {"accepted": "validé", "rejected": "refusé", "modified": "corrigé"}
_DAYS_FR = ("lundi", "mardi", "mercredi", "jeudi", "vendredi", "samedi", "dimanche")


# ── Recommendation: sized by the product's rule ─────────────────────────────

async def recommend(db, profile, cal, sent_at: datetime, kind, trigger: str) -> StaffingRecommendation:
    """Size one recommendation with ``risk_assessment.assess`` (the newsvendor
    rule the formatter uses), compose the message the same way as
    ``RecommendationFormatterService`` does for that rule, and store it."""
    point, baseline = kind
    params = await hp.load(db, TENANT)
    c = params.get("covers_per_extra_staff")
    assessment = ra.assess(ra.Inputs(
        task_class=task_classes.TaskClassKey.staffing_add, point_forecast=point,
        baseline_covers=baseline, fallback_delta_staff=1, forecaster=FORECASTER,
        calibration=cal, params=params, covers_per_staff=c, covers_per_staff_source="hotel_parameter",
    ))
    delta = int(assessment["recommended_delta_staff"])
    start = (sent_at + timedelta(days=1)).replace(hour=19)
    end = start + timedelta(hours=4)
    message = format_message("surge", delta, 0.0, 0.0, start, end, trigger, show_money=False)
    if assessment["material"]:
        message = "\n".join([message, *ra.render_lines(assessment, "fr")])
    rec = StaffingRecommendation(
        id=uuid.uuid4(), tenant_id=TENANT, property_id=profile.id, anomaly_id=uuid.uuid4(),
        message_text=message, triggering_factor=trigger, recommended_headcount=delta,
        predicted_covers=point, window_start=start, window_end=end,
        status="dispatched", dispatched_at=sent_at, dispatch_channel="whatsapp",
        task_class=assessment["task_class"], decision_rule=assessment["decision_rule"],
        risk_assessment=assessment,
    )
    db.add(rec)
    await db.commit()
    return rec


async def debrief_line(db, before: datetime) -> str | None:
    """PROTOTYPE (HOS-363, not in the product): one line on the last dinner
    that has its actual covers, read from the stored recommendation."""
    recs = (await db.execute(
        select(StaffingRecommendation).where(
            StaffingRecommendation.tenant_id == TENANT,
            StaffingRecommendation.actual_covers.is_not(None),
            StaffingRecommendation.window_end <= before,
        ).order_by(StaffingRecommendation.window_start.desc())
    )).scalars().all()
    if not recs:
        return None
    r = recs[0]
    gap = (float(r.actual_covers) - float(r.predicted_covers)) / float(r.predicted_covers) * 100
    decided = _DECISION_FR.get(r.status, "sans réponse")
    if r.status == "modified" and r.retained_delta_staff is not None:
        decided += f" (+{r.retained_delta_staff} retenu)"
    day = _DAYS_FR[r.window_start.weekday()]
    return (f"Dernier dîner mesuré ({day} {r.window_start:%d/%m}) : prévu {float(r.predicted_covers):.0f}, "
            f"réel {float(r.actual_covers):.0f} "
            f"({gap:+.0f} %, déclaré), proposé +{r.recommended_headcount}, vous aviez {decided}.")


async def enter_actuals(db, recs: dict, actuals: dict, at: datetime) -> list[str]:
    """Services already over get their actual covers (fictional, declared)."""
    done = []
    for label, rec in recs.items():
        if label in actuals and rec.actual_covers is None and rec.window_end <= at:
            rec.actual_covers = actuals[label]
            rec.actual_covers_source = "demo_fictional"
            rec.actual_covers_at = at
            done.append(label)
    await db.commit()
    return done


# ── Replies: routed like the Twilio webhook ─────────────────────────────────

async def reply(db, llm, profile, body: str, now: datetime, quiet: bool = False):
    """One inbound reply, routed like ``api/routes/twilio_inbound.py``."""
    decisions = InboundDecisionService(db)
    say_manager(body)
    if hasattr(llm, "last"):
        llm.last = None

    plan = await decisions.handle_deterministic(profile, body, "", now)
    if plan is not None:
        path = "déterministe (lexique / commande / confirmation), sans modèle"
    else:
        prompt = await decisions.open_prompt(profile, now)
        receipts = ReceiptsService(db, llm=llm)
        if prompt is not None and prompt.kind == "reason_request":
            route, conf = await receipts.route_reason(body)
            plan = await decisions.handle_reason(profile, prompt, body, route, conf, now)
            path = "raison facultative — ne change jamais la décision"
        elif is_question(body):
            explanation = await ExplainabilityService(llm=llm).explain(
                body, await decisions.latest_recommendation(profile), db, "fr")
            plan = await decisions.handle_question(profile, body, explanation,
                                                   receipts.parse_inbound, now)
            path = "question — expliquée, jamais une décision"
        else:
            recs = await decisions.pending_recommendations(profile)
            feedback = await receipts.parse_inbound(
                body, decisions.proposal_of(recs[0] if recs else None))
            plan, _res, _rec = await decisions.handle_free_text(profile, feedback, now)
            path = f"texte libre → modèle (source {feedback.source})"
    say_agent(plan.text or "")
    if not quiet:
        note(f"chemin : {path} · résultat : {plan.result}"
             + (f" · décision : {plan.decision}" if plan.decision else "")
             + (f" · source : {plan.source}" if plan.source else ""))
        if getattr(llm, "last", None):
            note(llm.last)
    return plan


# ── Run ──────────────────────────────────────────────────────────────────────

async def run(target: str | None) -> None:
    logging.disable(logging.WARNING)
    llm = build_model(target)
    cal = Calibration.load(CALIBRATION)
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    factory = async_sessionmaker(engine, expire_on_commit=False)

    print("━━ Aetherix — boucle de décision et boucle d'apprentissage, rejouées sur les services de production ━━")
    print("   Maison Lumen (fictif) · restaurant de 78 couverts · données, coûts et réels fictifs")
    print(f"   Modèle : {llm.model_id}")
    print(f"   Incertitude : calibration {cal.provenance} ({cal.version}) — vérifie la méthode, pas un hôtel réel")
    print("   Base : SQLite en mémoire (schéma ORM) · rien n'est envoyé")

    by_day: dict[str, StaffingRecommendation] = {}
    async with factory() as db:
        profile = RestaurantProfile(
            id=uuid.uuid4(), tenant_id=TENANT, property_name="Maison Lumen (fictif)",
            outlet_name="Restaurant", total_seats=78, phone_number=PHONE,
            manager_locale="fr", manager_name="Claire",
        )
        db.add(profile)
        for name, value in PARAMS.items():
            await hp.set_parameter(db, TENANT, name, value, set_by="Claire (fictif)",
                                   set_via="dashboard_api", note="démo, valeurs fictives",
                                   at=datetime(2026, 11, 1, tzinfo=TZ))
        await db.commit()
        note(f"règles de l'hôtel : {PARAMS['covers_per_extra_staff']:.0f} couverts par extra, "
             f"extra {PARAMS['extra_shift_cost']:.0f} €, couvert perdu {PARAMS['lost_cover_value']:.0f} € (fictifs)")

        # ── Week 1 ──────────────────────────────────────────────────────────
        title("Semaine 1 — la conversation : un chemin par réponse")
        actuals1 = {d[0]: d[5] for d in WEEK1 if d[0]}
        for label, sent_at, kind, trigger, replies, _actual in WEEK1:
            what = f"recommandation pour le dîner de {label}" if label else "pas de recommandation"
            print(f"\n── envoyé le {sent_at:%d/%m} à 14:00 · {what}")
            for done in await enter_actuals(db, by_day, actuals1, sent_at):
                note(f"après le service de {done} : {actuals1[done]:.0f} couverts réels (fictifs, déclarés)")
            if kind is not None:
                debrief = await debrief_line(db, sent_at)
                if debrief:
                    note(f"[aperçu HOS-363, pas encore dans le produit] {debrief}")
                rec = await recommend(db, profile, cal, sent_at, kind, trigger)
                by_day[label] = rec
                say_agent(f"{rec.message_text}\n(prévision : {rec.predicted_covers:.0f} couverts)")
            now = sent_at
            for body in replies:
                now += timedelta(minutes=20)
                await reply(db, llm, profile, body, now)

        # ── Week 2 ──────────────────────────────────────────────────────────
        title("Semaine 2 — même manager, sept dîners (résumé)")
        actuals2 = {d[0]: d[4] for d in WEEK2}
        all_actuals = {**actuals1, **actuals2}
        for i, (label, kind, trigger, body, _actual) in enumerate(WEEK2):
            sent_at = WEEK2_FIRST_SEND + timedelta(days=i)
            await enter_actuals(db, by_day, all_actuals, sent_at)
            print(f"\n── {sent_at:%d/%m} 14:00 · dîner de {label} · {trigger}")
            debrief = await debrief_line(db, sent_at)
            if debrief:
                note(f"[aperçu HOS-363] {debrief}")
            rec = await recommend(db, profile, cal, sent_at, kind, trigger)
            by_day[label] = rec
            say_agent(rec.message_text.splitlines()[0])
            plan = await reply(db, llm, profile, body, sent_at + timedelta(minutes=20), quiet=True)
            if plan.result == "confirmation_requested":
                await reply(db, llm, profile, "oui", sent_at + timedelta(minutes=25), quiet=True)
        await enter_actuals(db, by_day, all_actuals, LEARNING_PASS_AT)

        # ── Weekly learning pass ────────────────────────────────────────────
        title(f"Passe d'apprentissage hebdomadaire — lundi {LEARNING_PASS_AT:%d/%m %H:%M} (learning_store.run_pass)")
        out = await ls.run_pass(db, TENANT, now=LEARNING_PASS_AT, forecaster=FORECASTER)
        await db.commit()
        note(f"{out['rows']} recommandations relues · rien n'est appliqué par la passe elle-même")
        cp = out["calibration_proposal"]
        note(f"recalibration de l'incertitude : {'proposée' if cp['ok'] else 'non proposée'} ({cp['reason']})")
        items = await ls.list_items(db, TENANT)
        ratio_item = None
        for it in items:
            p = it["payload"] or {}
            if it["kind"] == "cost_parameter":
                ev = p.get("evidence", {})
                note(f"PROPOSITION {p.get('parameter')} : {p.get('current_value')} → {p.get('proposed_value')} "
                     f"({p.get('rule')}) · {ev.get('n')} décisions humaines dont {ev.get('counters')} "
                     f"contre-propositions · réels indépendants : {it['independent_actuals']} · "
                     f"à approuver par : {it['reviewer_role']}")
                if p.get("parameter") == "covers_per_extra_staff":
                    ratio_item = it
            else:
                note(f"à revoir ({it['reviewer_role']}) : {it['kind']} — {it['subject']}")

        if ratio_item is None:
            note("aucune proposition de ratio : les seuils (≥ 8 décisions, ≥ 3 contre-propositions, écart ≥ 20 %) "
                 "ne sont pas atteints")
        else:
            # ── Approval by a named person, then the next recommendation ───
            title("Approbation par une personne nommée, puis recommandation suivante")
            approved = await ls.decide(db, TENANT, str(ratio_item["id"]), approve=True, actor=OWNER,
                                       note="démo : Claire approuve", now=LEARNING_PASS_AT + timedelta(hours=6))
            await db.commit()
            note(f"approuvé par {approved['decided_by']} · statut {approved['status']} · "
                 f"{approved['applied_ref']}")
            before = ra.assess(ra.Inputs(
                task_class=task_classes.TaskClassKey.staffing_add, point_forecast=EVENT[0],
                baseline_covers=EVENT[1], fallback_delta_staff=1, forecaster=FORECASTER, calibration=cal,
                params=hp.HotelParameters(TENANT, {k: v for k, v in (await hp.load(db, TENANT)).values.items()
                                                   if k != "covers_per_extra_staff"}),
                covers_per_staff=PARAMS["covers_per_extra_staff"], covers_per_staff_source="hotel_parameter",
            ))
            label, sent_at, kind, trigger = NEXT_EVENT
            print(f"\n── {sent_at:%d/%m} 14:00 · dîner de {label} · {trigger} (soir d'événement)")
            rec = await recommend(db, profile, cal, sent_at, kind, trigger)
            say_agent(rec.message_text.splitlines()[0])
            after = rec.risk_assessment
            retained = sorted({r.retained_delta_staff for r in by_day.values() if r.retained_delta_staff})
            note(f"ratio en vigueur {after['covers_per_staff']:.0f} (était {before['covers_per_staff']:.0f}) · "
                 f"proposé +{after['recommended_delta_staff']} (était +{before['recommended_delta_staff']}) · "
                 f"Claire retenait +{', +'.join(str(x) for x in retained)}")
            if after["recommended_delta_staff"] == before["recommended_delta_staff"]:
                note("CONSTAT : la règle apprise ne change pas la recommandation. Le ratio entre aussi dans le "
                     f"coût du manque de personnel : seuil de risque {before['critical_ratio']} → "
                     f"{after['critical_ratio']}, demande couverte {before['demand_quantile']} → "
                     f"{after['demand_quantile']} couverts. La règle d'apprentissage suppose cette demande fixe.")
                note("→ défaut de composition entre apprentissage (HOS-344) et dimensionnement (newsvendor) : "
                     "HOS-365. La proposition est donc annulée.")
            back = await ls.rollback_parameter(db, TENANT, str(ratio_item["id"]), OWNER,
                                               now=LEARNING_PASS_AT + timedelta(days=1))
            await db.commit()
            note(f"retour arrière en un appel : statut {back['status']} · ratio en vigueur "
                 f"{(await hp.load(db, TENANT)).get('covers_per_extra_staff'):.0f}")
            history = await hp.history(db, TENANT, "covers_per_extra_staff")
            note("historique (append-only) : " + " → ".join(
                f"{h['value']:.0f} ({h['set_via']})" for h in sorted(history, key=lambda h: h["set_at"])))

        # ── What is recorded ────────────────────────────────────────────────
        title("Ce qui est enregistré (relu en base)")
        rows = (await db.execute(select(StaffingRecommendation)
                                 .order_by(StaffingRecommendation.dispatched_at))).scalars().all()
        labels = {r.id: d for d, r in by_day.items()}
        events = (await db.execute(select(InboundReplyEvent).where(
            InboundReplyEvent.result == "reason_captured"))).scalars().all()
        reasons = {e.recommendation_id: e.reason_text for e in events if e.reason_text}
        for r in rows:
            if r.id not in labels:
                continue
            print(f"  {labels[r.id]:15} proposé +{r.recommended_headcount} · {r.status:9}"
                  f" · source {r.decision_source or '—':16} · par {r.decided_by or '—':14}"
                  f" · retenu {r.retained_delta_staff if r.retained_delta_staff is not None else '—':>2}"
                  f" · prévu {r.predicted_covers or 0:.0f} / réel {r.actual_covers or '—'}"
                  + (f" · raison « {reasons[r.id]} »" if r.id in reasons else ""))
        print("\n  Données fictives. Réels déclarés, pas de POS (HOS-364). Ligne « Dernier dîner mesuré » = prototype (HOS-363)."
              "\n  Les lignes SCRIPTÉ ne mesurent pas le modèle : relancer avec --model claude:<id>.")
    await engine.dispose()


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--model", help="claude:<exact model id> — call the real model (needs ANTHROPIC_API_KEY)")
    args = ap.parse_args()
    asyncio.run(run(args.model))


if __name__ == "__main__":
    main()

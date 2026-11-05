"""WhatsApp decision loop, replayed on the production services — demo script.

One fictional week at a fictional hotel: each day a staffing recommendation is
"sent", the manager replies in WhatsApp words, and the reply goes through the
same services the Twilio webhook calls (``InboundDecisionService``,
``ReceiptsService.parse_inbound``, ``ExplainabilityService``, the recap
template). What is printed as the agent's answer is the text those services
return; what is printed as recorded is read back from the database.

* Database: SQLite in memory, schema from the ORM (``Base.metadata``). No
  Supabase, no Twilio, no network. Nothing is sent.
* Model: replies that the lexicon cannot decide reach the model.
  - ``--model claude:<exact model id>`` (needs ``ANTHROPIC_API_KEY``): the real
    model is called, as in production (tier pinned to that model).
  - default: a SCRIPTED stand-in returns a fixed answer for each of those
    replies. Every such line is labelled ``SCRIPTÉ`` — it shows the plumbing
    (schema validation, threshold, confirmation), never the model's quality.
* Data: fictional hotel, fictional covers. Synthetic (Décision #33).

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
from app.services.explainability_service import ExplainabilityService  # noqa: E402
from app.services.inbound_decision import InboundDecisionService  # noqa: E402
from app.services.manager_decision import is_question  # noqa: E402
from app.services.receipts import ReceiptsService  # noqa: E402
from app.services.recommendation_formatter import format_message  # noqa: E402

TENANT = "demo_hotel_kleber"
PHONE = "+33600000000"  # fictional
TZ = timezone.utc

# ── The week ─────────────────────────────────────────────────────────────────
# Each recommendation is sent at 14:00 the day before the dinner service it is
# about (J-1). Days are named after the SERVICE, as the manager names them
# ("corriger mardi" = the decision about Tuesday's dinner).
# (service day, sent at, extra staff proposed, predicted covers, trigger, replies)
WEEK = [
    ("mardi 10/11", datetime(2026, 11, 9, 14, 0, tzinfo=TZ), 1, 92.0,
     "corporate seminar (60 pax) in house", ["ok"]),
    ("mercredi 11/11", datetime(2026, 11, 10, 14, 0, tzinfo=TZ), 1, 88.0,
     "rain forecast, guests stay in", ["pas besoin", "le séminaire dîne dehors ce soir"]),
    ("jeudi 12/11", datetime(2026, 11, 11, 14, 0, tzinfo=TZ), 2, 131.0,
     "football match 2 km away (21:00)", ["mets-en 3 de plus"]),
    ("vendredi 13/11", datetime(2026, 11, 12, 14, 0, tzinfo=TZ), 1, 97.0,
     "occupancy 91 %", ["pourquoi ?", "bof, ça me paraît beaucoup", "oui"]),
    (None, datetime(2026, 11, 13, 14, 0, tzinfo=TZ), None, None, None,
     ["corriger mardi refus", "oui", "recap semaine"]),
]
# Actual covers entered after each service (fictional).
ACTUALS = {"mardi 10/11": 85.0, "mercredi 11/11": 80.0, "jeudi 12/11": 139.0}

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


# ── Loop ─────────────────────────────────────────────────────────────────────

async def reply(db, llm, profile, body: str, now: datetime) -> None:
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
    note(f"chemin : {path} · résultat : {plan.result}"
         + (f" · décision : {plan.decision}" if plan.decision else "")
         + (f" · source : {plan.source}" if plan.source else ""))
    if getattr(llm, "last", None):
        note(llm.last)


async def run(target: str | None) -> None:
    logging.disable(logging.WARNING)
    llm = build_model(target)
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    factory = async_sessionmaker(engine, expire_on_commit=False)

    print("━━ Aetherix — boucle de décision WhatsApp, rejouée sur les services de production ━━")
    print("   Hôtel Kléber (fictif) · restaurant « Le 16 » · 78 couverts · données fictives")
    print(f"   Modèle : {llm.model_id}")
    print("   Base : SQLite en mémoire (schéma ORM) · rien n'est envoyé\n")

    by_day: dict[str, StaffingRecommendation] = {}
    async with factory() as db:
        profile = RestaurantProfile(
            id=uuid.uuid4(), tenant_id=TENANT, property_name="Hôtel Kléber (fictif)",
            outlet_name="Le 16", total_seats=78, phone_number=PHONE,
            manager_locale="fr", manager_name="Claire",
        )
        db.add(profile)
        await db.commit()

        for label, sent_at, extra, predicted, trigger, replies in WEEK:
            what = f"recommandation pour le dîner de {label}" if label else "pas de recommandation"
            print(f"── envoyé le {sent_at:%d/%m} à 14:00 · {what} ──────────────")
            # Services already over: their actual covers (fictional) are entered.
            for done_label, rec in by_day.items():
                if done_label in ACTUALS and rec.actual_covers is None and rec.window_end <= sent_at:
                    rec.actual_covers = ACTUALS[done_label]
                    rec.actual_covers_source = "demo_fictional"
                    rec.actual_covers_at = sent_at
                    await db.commit()
                    note(f"après le service de {done_label} : {ACTUALS[done_label]:.0f} couverts réels (fictifs) enregistrés")
            if extra is not None:
                service_start = (sent_at + timedelta(days=1)).replace(hour=19)
                text = format_message("surge", extra, 0.0, 0.0, service_start,
                                      service_start + timedelta(hours=4), trigger,
                                      show_money=False)
                rec = StaffingRecommendation(
                    id=uuid.uuid4(), tenant_id=TENANT, property_id=profile.id,
                    anomaly_id=uuid.uuid4(), message_text=text, triggering_factor=trigger,
                    recommended_headcount=extra, predicted_covers=predicted,
                    window_start=service_start, window_end=service_start + timedelta(hours=4),
                    status="dispatched", dispatched_at=sent_at, dispatch_channel="whatsapp",
                )
                db.add(rec)
                await db.commit()
                by_day[label] = rec
                say_agent(f"{text}\n(prévision : {predicted:.0f} couverts)")
            now = sent_at
            for body in replies:
                now += timedelta(minutes=20)
                await reply(db, llm, profile, body, now)

            print()

        print("━━ Ce qui est enregistré (relu en base) ━━")
        rows = (await db.execute(select(StaffingRecommendation)
                                 .order_by(StaffingRecommendation.dispatched_at))).scalars().all()
        labels = {r.id: d for d, r in by_day.items()}
        events = (await db.execute(select(InboundReplyEvent).where(
            InboundReplyEvent.result == "reason_captured"))).scalars().all()
        reasons = {e.recommendation_id: e.reason_text for e in events if e.reason_text}
        for r in rows:
            print(f"  {labels.get(r.id, '?'):15} proposé +{r.recommended_headcount} · statut {r.status:9}"
                  f" · source {r.decision_source or '—':16} · par {r.decided_by or '—':15}"
                  f" · retenu {r.retained_delta_staff if r.retained_delta_staff is not None else '—':>2}"
                  f" · prévu {r.predicted_covers or 0:.0f} / réel {r.actual_covers or '—'}"
                  f" · raison {reasons.get(r.id) or '—'}")
        print("\n  Données fictives. Les lignes SCRIPTÉ ne mesurent pas le modèle : relancer avec"
              "\n  --model claude:<id> pour le modèle réel.")
    await engine.dispose()


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--model", help="claude:<exact model id> — call the real model (needs ANTHROPIC_API_KEY)")
    args = ap.parse_args()
    asyncio.run(run(args.model))


if __name__ == "__main__":
    main()

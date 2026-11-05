"""Peuple la sandbox Apaleo (propriété PAR = « Maison Lumen », hôtel FICTIF) en réservations futures.

Pourquoi ce script (HOS-353) : la sandbox n'avait pas de données F&B-pertinentes (aucune réservation à venir).
Apaleo refuse toute arrivée passée (« 'To' cannot be in the past », même avec $force) : on ne peut donc
semer QUE du futur (pick-up). L'historique reste synthétique (Décision #11).

Ce script écrit dans la SANDBOX Apaleo, hors produit. Il ne touche pas à APALEO_READONLY (garde du produit,
Décisions #7/#45). Simulation par défaut ; l'écriture exige --apply.

Usage :
    python scripts/ops/seed_apaleo_sandbox.py --env backend/.env                 # simulation
    python scripts/ops/seed_apaleo_sandbox.py --env backend/.env --apply         # écrit
    python scripts/ops/seed_apaleo_sandbox.py --env backend/.env --apply --resume  # reprend
    python scripts/ops/seed_apaleo_sandbox.py --env backend/.env --cleanup       # annule tout LUMEN-SEED-*

Toutes les réservations portent externalCode = LUMEN-SEED-<n> (nettoyage ciblé). Génération déterministe
(graine fixe) : deux exécutions produisent le même plan. Stdlib seule, aucun secret n'est affiché.
"""
from __future__ import annotations

import argparse
import json
import random
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from collections import Counter, defaultdict
from datetime import date, timedelta
from pathlib import Path

BASE = "https://api.apaleo.com"
PROPERTY = "PAR"
TAG = "LUMEN-SEED-"
SEED = 20261105

# Événements fictifs (alignés sur les prix posés par l'étape tarifs).
EVENTS = {
    date(2026, 11, 12): "Salon professionnel", date(2026, 11, 13): "Salon professionnel",
    date(2026, 11, 21): "Match de gala", date(2026, 11, 28): "Black Friday week-end",
    date(2026, 12, 5): "Marché de Noël du Marais", date(2026, 12, 12): "Défilé de mode",
    date(2026, 12, 24): "Réveillon", date(2026, 12, 31): "Saint-Sylvestre",
}
DOW_OCC = {0: 0.58, 1: 0.64, 2: 0.68, 3: 0.66, 4: 0.82, 5: 0.90, 6: 0.55}  # lun..dim
MONTH = {11: 1.00, 12: 1.04, 1: 0.88}
PLANS = {  # groupe -> [(tarif, poids)]
    "PAR-SGL": [("PAR-FLEX-SGL", 40), ("PAR-NONREF-SGL", 30), ("PAR-PROMO-SGL", 15), ("PAR-EARLY-SGL", 15)],
    "PAR-DBL": [("PAR-FLEX-DBL", 35), ("PAR-NONREF-DBL", 30), ("PAR-PROMO-DBL", 15), ("PAR-IBRKF-DBL", 20)],
}
CHANNELS = [("Direct", 40), ("Ibe", 25), ("BookingCom", 35)]
FIRST = ["Camille", "Louis", "Emma", "Hugo", "Léa", "Jules", "Chloé", "Arthur", "Inès", "Nathan", "Sofia",
         "Marc", "Anna", "Thomas", "Julia", "Pierre", "Elena", "Lucas", "Sarah", "Antoine", "Maria", "David",
         "Laura", "Paul", "Nora", "Felix", "Ingrid", "Marco", "Yuki", "Oliver"]
LAST = ["Martin", "Bernard", "Dubois", "Moreau", "Laurent", "Simon", "Michel", "Lefebvre", "Garcia", "Roux",
        "Fournier", "Girard", "Rossi", "Müller", "Schmidt", "Jensen", "Novak", "Tanaka", "Silva", "Cohen",
        "O'Brien", "Kowalski", "Hansen", "Costa", "Dupont", "Petit", "Lambert", "Faure", "Mercier", "Blanc"]
GUEST_REQ = [
    "Arrivée tardive vers 22 h, dîner au restaurant souhaité.",
    "Table pour 2 au restaurant samedi soir, anniversaire de mariage.",
    "Petit-déjeuner végétarien, merci.", "Chambre calme, côté cour si possible.",
    "Lit bébé souhaité.", "Départ tardif demandé (14 h).",
    "Dîner d'affaires prévu à l'hôtel avec 4 convives, merci de prévoir une table.",
    "Arrivée à 8 h après vol de nuit, check-in anticipé si possible.",
    "Allergie aux fruits à coque : prévenir la cuisine.", "Brunch en chambre le dimanche.",
]
NOTES = ["Client fidèle (3e séjour).", "Facture au nom de la société.", "Demande de renseignements sur le spa.",
         "A demandé à pouvoir annuler sans frais ; échange par e-mail.", "Séminaire d'entreprise, groupe de 6."]


def read_env(path: Path) -> dict:
    env = {}
    for ln in path.read_text(encoding="utf-8").splitlines():
        if "=" in ln and not ln.lstrip().startswith("#"):
            k, v = ln.split("=", 1)
            env[k.strip()] = v.strip().strip('"').strip("'")
    return env


class Api:
    def __init__(self, env: dict):
        self.env, self._tok = env, None

    def token(self) -> str:
        if not self._tok:
            body = urllib.parse.urlencode({"grant_type": "client_credentials",
                                           "client_id": self.env["APALEO_CLIENT_ID"],
                                           "client_secret": self.env["APALEO_CLIENT_SECRET"]}).encode()
            self._tok = json.load(urllib.request.urlopen(urllib.request.Request(
                "https://identity.apaleo.com/connect/token", data=body), timeout=30))["access_token"]
        return self._tok

    def call(self, method: str, path: str, payload=None):
        for attempt in range(4):
            h = {"Authorization": "Bearer " + self.token(), "Accept": "application/json"}
            data = None
            if payload is not None:
                data, h["Content-Type"] = json.dumps(payload).encode(), "application/json"
            try:
                r = urllib.request.urlopen(urllib.request.Request(BASE + path, data=data, method=method, headers=h),
                                           timeout=60)
                raw = r.read()
                return r.status, (json.loads(raw) if raw else {})
            except urllib.error.HTTPError as e:
                raw = e.read().decode("utf-8", "replace")
                if e.code == 401:
                    self._tok = None
                    continue
                if e.code in (429, 503):
                    time.sleep(float(e.headers.get("Retry-After", 2 + attempt * 2)))
                    continue
                try:
                    return e.code, json.loads(raw)
                except ValueError:
                    return e.code, {"_raw": raw[:300]}
        return 599, {"_raw": "retries épuisés"}


def wchoice(rng: random.Random, items):
    return rng.choices([i[0] for i in items], weights=[i[1] for i in items])[0]


def build_plan(capacity: dict[str, int], first: date, last_arrival: date) -> list[dict]:
    """Plan déterministe de réservations : respecte la capacité par groupe et par nuit."""
    rng = random.Random(SEED)
    used: dict[str, Counter] = {g: Counter() for g in capacity}
    plan: list[dict] = []
    d = first
    while d <= last_arrival:
        occ = DOW_OCC[d.weekday()] * MONTH.get(d.month, 1.0) + (0.12 if d in EVENTS else 0.0)
        if d.month == 12 and d.day in (25, 26):
            occ *= 0.8
        occ = min(0.95, max(0.35, occ + rng.uniform(-0.04, 0.04)))
        total_cap = sum(capacity.values())
        target_nights = occ * total_cap
        # nuits déjà occupées ce jour par des séjours plus anciens
        already = sum(used[g][d] for g in capacity)
        attempts = 0
        while already < target_nights and attempts < 400:
            attempts += 1
            g = "PAR-DBL" if rng.random() < 0.62 else "PAR-SGL"
            los = rng.choices([1, 2, 3, 4, 5], weights=[45, 30, 15, 6, 4])[0]
            nights = [d + timedelta(days=i) for i in range(los)]
            if any(used[g][n] >= capacity[g] for n in nights):
                continue
            for n in nights:
                used[g][n] += 1
            already += 1
            plan.append({"arrival": d, "nights": los, "group": g})
        d += timedelta(days=1)
    for i, r in enumerate(plan):
        rr = random.Random(SEED + i)
        r["i"] = i
        r["plan_candidates"] = [wchoice(rr, PLANS[r["group"]]) for _ in range(3)] + [PLANS[r["group"]][0][0]]
        r["channel"] = wchoice(rr, CHANNELS)
        r["adults"] = 1 if r["group"] == "PAR-SGL" else rr.choice([1, 2, 2, 2])
        r["first"], r["last"] = rr.choice(FIRST), rr.choice(LAST)
        r["guest_comment"] = rr.choice(GUEST_REQ) if rr.random() < 0.35 else None
        r["comment"] = rr.choice(NOTES) if rr.random() < 0.15 else None
        days_ahead = (r["arrival"] - first).days
        r["cancel"] = days_ahead >= 2 and rr.random() < 0.10
    return plan


def summarize(plan: list[dict], first: date, last: date, capacity: dict[str, int]) -> None:
    occ: Counter = Counter()
    for r in plan:
        if not r["cancel"]:
            for k in range(r["nights"]):
                occ[r["arrival"] + timedelta(days=k)] += 1
    cap = sum(capacity.values())
    print("Réservations planifiées :", len(plan), "| dont annulées :", sum(r["cancel"] for r in plan),
          "| avec demande client :", sum(bool(r["guest_comment"]) for r in plan))
    weeks: dict = defaultdict(list)
    d = first
    while d <= last:
        weeks[d - timedelta(days=d.weekday())].append(occ[d] / cap)
        d += timedelta(days=1)
    for w, v in weeks.items():
        print("  semaine du", w.isoformat(), "occupation moy.", f"{100 * sum(v) / len(v):.0f} %",
              "(max", f"{100 * max(v):.0f} %)")
    print("  jours d'événement :", ", ".join(f"{k.isoformat()} {v}" for k, v in sorted(EVENTS.items())))


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--env", required=True)
    ap.add_argument("--apply", action="store_true")
    ap.add_argument("--resume", action="store_true")
    ap.add_argument("--cleanup", action="store_true")
    ap.add_argument("--days", type=int, default=60)
    ap.add_argument("--state", default="apaleo_seed_state.json")
    a = ap.parse_args()
    api = Api(read_env(Path(a.env)))
    state_p = Path(a.state)

    if a.cleanup:
        s, o = api.call("GET", f"/booking/v1/reservations?propertyIds={PROPERTY}&pageSize=1000&status=Confirmed")
        todo = [r["id"] for r in o.get("reservations", []) if str(r.get("externalCode", "")).startswith(TAG)]
        print(len(todo), "réservations", TAG + "* à annuler", "(simulation)" if not a.apply else "")
        if a.apply:
            for rid in todo:
                print(rid, api.call("PUT", f"/booking/v1/reservation-actions/{rid}/cancel")[0])
        return 0

    today = date.today()
    first, last_arrival = today + timedelta(days=1), today + timedelta(days=a.days)
    s, av = api.call("GET", f"/availability/v1/unit-groups?propertyId={PROPERTY}&timeSliceTemplate=OverNight"
                            f"&from={first.isoformat()}&to={(first + timedelta(days=1)).isoformat()}")
    capacity = {}
    for g in (av.get("timeSlices") or [{}])[0].get("unitGroups", []):
        gid = g["unitGroup"]["id"]
        if gid in PLANS:
            capacity[gid] = int(g.get("sellableCount", g.get("physicalCount", 0)))
    if not capacity:
        print("Capacité introuvable :", s, str(av)[:200])
        return 2
    print("Capacité vendable par groupe :", capacity, "(FAMILY exclu : aucun tarif)")
    plan = build_plan(capacity, first, last_arrival)
    summarize(plan, first, last_arrival + timedelta(days=5), capacity)
    if not a.apply:
        print("\nSIMULATION — rien n'a été écrit. Relancer avec --apply.")
        return 0

    done = set(json.loads(state_p.read_text(encoding="utf-8"))["done"]) if (a.resume and state_p.exists()) else set()
    if state_p.exists() and not a.resume:
        print("État existant", state_p, "→ utiliser --resume (ou le supprimer).")
        return 2
    ok = canc = skipped = 0
    fails: Counter = Counter()
    created: list[dict] = []
    for r in plan:
        if r["i"] in done:
            continue
        dep = r["arrival"] + timedelta(days=r["nights"])
        placed = False
        for rate in dict.fromkeys(r["plan_candidates"]):
            body = {
                "booker": {"firstName": r["first"], "lastName": r["last"],
                           "email": f"{r['first']}.{r['last']}@example.com".lower().replace("'", "").replace(" ", "")},
                "reservations": [{
                    "arrival": r["arrival"].isoformat(), "departure": dep.isoformat(), "adults": r["adults"],
                    "channelCode": r["channel"], "externalCode": f"{TAG}{r['i']:04d}",
                    "primaryGuest": {"firstName": r["first"], "lastName": r["last"]},
                    "timeSlices": [{"ratePlanId": rate} for _ in range(r["nights"])],
                    **({"guestComment": r["guest_comment"]} if r["guest_comment"] else {}),
                    **({"comment": r["comment"]} if r["comment"] else {}),
                }],
            }
            s, o = api.call("POST", "/booking/v1/bookings", body)
            if s == 201:
                rid = o["reservationIds"][0]["id"]
                ok += 1
                placed = True
                if r["cancel"]:
                    if api.call("PUT", f"/booking/v1/reservation-actions/{rid}/cancel")[0] == 204:
                        canc += 1
                created.append({"i": r["i"], "id": rid, "rate": rate, "cancelled": r["cancel"]})
                break
            fails[(str(o.get("messages", o))[:90])] += 1
            if s == 422 and "channel" in str(o).lower():
                r["channel"] = "Direct"
        if not placed:
            skipped += 1
        done.add(r["i"])
        if len(done) % 25 == 0:
            state_p.write_text(json.dumps({"done": sorted(done), "created": created}), encoding="utf-8")
            print(f"  … {len(done)}/{len(plan)} traitées | créées {ok} | annulées {canc} | ignorées {skipped}", flush=True)
        time.sleep(0.1)
    state_p.write_text(json.dumps({"done": sorted(done), "created": created}), encoding="utf-8")
    print(f"\nTERMINÉ : créées {ok}, dont annulées {canc} ; ignorées {skipped} sur {len(plan)}.")
    for m, n in fails.most_common(5):
        print("  refus :", n, "×", m)
    return 0


if __name__ == "__main__":
    sys.exit(main())

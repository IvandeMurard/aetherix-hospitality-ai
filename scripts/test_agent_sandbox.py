"""
Test du CŒUR de l'agent Aetherix (reasoning Claude + staffing) sur de VRAIES
données sandbox Apaleo.

Réel ici :
  - Données : réservations sandbox Apaleo (REST booking/v1, datetime+TZ validé)
  - Reasoning : Claude (ANTHROPIC_API_KEY) via ReasoningService réel
  - Staffing : StaffingService réel

Stub / indisponible dans cet environnement local (signalé) :
  - Prophet (lib non installée) -> forecast dérivé des données sandbox, is_mock=True
  - RAG + mémoire + profil + persistance -> nécessitent la DB Postgres/pgvector (docker)
"""
import asyncio
import os
import sys
from datetime import date
from pathlib import Path

import httpx
from dotenv import load_dotenv

ROOT = Path(__file__).parent.parent
load_dotenv(ROOT / "backend" / ".env")
sys.path.insert(0, str(ROOT / "backend"))

from app.services.reasoning_service import ReasoningService   # noqa: E402
from app.services.staffing_service import StaffingService     # noqa: E402

CID = os.getenv("APALEO_CLIENT_ID", "")
SEC = os.getenv("APALEO_CLIENT_SECRET", "")
PID = os.getenv("APALEO_PROPERTY_ID", "PAR")


async def apaleo_token() -> str:
    async with httpx.AsyncClient(timeout=10) as h:
        r = await h.post("https://identity.apaleo.com/connect/token",
                         data={"grant_type": "client_credentials",
                               "client_id": CID, "client_secret": SEC})
        r.raise_for_status()
        return r.json()["access_token"]


async def sandbox_signals(token: str, target: date) -> dict:
    """Real sandbox data: reservations staying on target date + property unit count."""
    H = {"Authorization": f"Bearer {token}"}
    frm = f"{target.isoformat()}T00:00:00Z"
    to = f"{target.isoformat()}T23:59:59Z"
    async with httpx.AsyncClient(timeout=15) as h:
        res = await h.get("https://api.apaleo.com/booking/v1/reservations", headers=H,
                          params={"propertyIds": PID, "dateFilter": "Stay",
                                  "from": frm, "to": to, "pageSize": 1})
        reservations = res.json().get("count", 0) if res.status_code == 200 else 0
        units = await h.get("https://api.apaleo.com/inventory/v1/units", headers=H,
                            params={"propertyId": PID, "pageSize": 1})
        capacity = units.json().get("count", 0) if units.status_code == 200 else 0
    occupancy = min(1.0, reservations / capacity) if capacity else 0.0
    return {"reservations": reservations, "capacity": capacity, "occupancy": occupancy}


class StubForecast:
    """Stand-in for Prophet (lib unavailable). Covers derived from real occupancy."""
    def __init__(self, occupancy: float):
        base = 40
        self.predicted = int(round(base + occupancy * 120))
        self.lower = int(self.predicted * 0.85)
        self.upper = int(self.predicted * 1.15)
        self.confidence = 0.72
        self.is_mock = True


async def main() -> int:
    target = date(2026, 3, 13)   # vendredi avec données réelles dans la sandbox
    service_type = "dinner"
    print("=" * 64)
    print(f"  AGENT AETHERIX — test sandbox  |  {target.isoformat()} / {service_type}")
    print("=" * 64)

    token = await apaleo_token()
    sig = await sandbox_signals(token, target)
    print(f"[DONNÉES SANDBOX] property={PID}  réservations(stay)={sig['reservations']}"
          f"  capacité(units)={sig['capacity']}  -> occupancy={sig['occupancy']:.0%}")

    fc = StubForecast(sig["occupancy"])
    print(f"[FORECAST stub]   covers={fc.predicted} (range {fc.lower}-{fc.upper}), "
          f"confidence={fc.confidence:.0%}  [Prophet indisponible -> dérivé occupancy]")

    context = {
        "occupancy": sig["occupancy"],
        "weather": {"condition": "Pluie légère, 12°C"},  # illustratif (pas d'API météo configurée)
        "events": [],
        "regressors": {"occupancy": sig["occupancy"]},
    }

    # ---- Reasoning Claude (RÉEL) ----
    print("\n[REASONING] appel Claude réel ...")
    reasoner = ReasoningService()
    reasoning = await reasoner.generate_explanation(
        fc.predicted, fc.confidence, target, service_type,
        context, similar_patterns=[], is_mock=fc.is_mock,
    )
    print(f"  claude_used = {reasoning.get('claude_used')}")
    print(f"  facteurs    = {reasoning.get('confidence_factors')}")
    print(f"  EXPLICATION : {reasoning['summary']}")

    # ---- Staffing (RÉEL) ----
    staffer = StaffingService()
    staffing = await staffer.calculate_recommendation(fc.predicted, confidence=fc.confidence)
    print(f"\n[STAFFING] {staffing}")

    print("\n" + "=" * 64)
    print("  Pipeline agent (données sandbox -> reasoning Claude -> staffing) : OK")
    print("=" * 64)
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))

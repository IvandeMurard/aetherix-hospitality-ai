"""End-to-end de l'agent Aetherix sur la sandbox Apaleo — AVEC persistance DB.

Différence avec ``scripts/test_agent_sandbox.py`` (qui tourne sans DB) : ce script
exerce le **vrai** ``AetherixEngine`` câblé comme au démarrage du backend, contre
une Postgres/pgvector locale. Il valide donc, de bout en bout :

  1. DONNÉES   — réservations + capacité réelles de la sandbox Apaleo (REST booking/v1,
                 inventory/v1), OAuth2 client_credentials.
  2. PROFIL    — chargement du ``restaurant_profile`` depuis la DB (upsert idempotent
                 du tenant ``tenant_sandbox`` au préalable).
  3. FORECAST  — ``PredictionEngine`` (mock is_mock=True tant que Prophet n'est pas
                 entraîné — comportement nominal hors training).
  4. REASONING — ``ReasoningService`` => appel Claude RÉEL (ANTHROPIC_API_KEY).
  5. STAFFING  — ``StaffingService`` réel.
  6. PERSIST   — écriture dans ``recommendation_cache`` (vérifiée par relecture).

Note sur le câblage : tel que construit dans ``app.services.aetherix_engine``,
``RAGService`` et ``MemoryService`` n'ont pas de session injectée (db=None) ⇒ la
récupération de patterns / mémoire renvoie vide. C'est le comportement de l'engine
en production ; ce script le reproduit fidèlement. La persistance et le chargement
profil, eux, ouvrent leurs propres sessions ``AsyncSessionLocal`` (vraie DB).

Pré-requis (voir docs/testing/e2e-apaleo-sandbox.md) :
  - Postgres docker up + migrations appliquées.
  - .env renseigné (APALEO_CLIENT_ID/SECRET, ANTHROPIC_API_KEY, MISTRAL_API_KEY).

Lancement recommandé (dans le conteneur backend, deps garanties) :
    docker compose run --rm \
      -e E2E_DATABASE_URL=postgresql+asyncpg://postgres:password@db:5432/aetherix \
      backend python /scripts/ops/e2e_apaleo_sandbox.py

Lancement hôte (si les deps backend sont installées localement) :
    E2E_DATABASE_URL=postgresql+asyncpg://postgres:password@localhost:5434/aetherix \
      python scripts/ops/e2e_apaleo_sandbox.py
"""
from __future__ import annotations

import asyncio
import os
import sys
from datetime import date
from pathlib import Path

# --- Résolution des chemins (robuste en conteneur /app + /scripts et sur l'hôte) ---
SCRIPTS_DIR = Path(__file__).resolve().parents[1]   # .../scripts
ROOT = SCRIPTS_DIR.parent                            # racine repo (hôte)
BACKEND_DIR = ROOT / "backend"
for p in (str(SCRIPTS_DIR), str(BACKEND_DIR), "/app"):
    if p not in sys.path and Path(p).exists():
        sys.path.insert(0, p)

# --- DATABASE_URL DOIT être fixé AVANT d'importer app.* (engine créé à l'import) ---
# On utilise une variable dédiée E2E_DATABASE_URL pour ne JAMAIS taper par accident
# la DATABASE_URL de prod/Supabase présente dans .env.
_DEFAULT_LOCAL_DB = "postgresql+asyncpg://postgres:password@localhost:5434/aetherix"
os.environ["DATABASE_URL"] = os.environ.get("E2E_DATABASE_URL", _DEFAULT_LOCAL_DB)
os.environ.setdefault("AETHERIX_SKIP_BOOT_SCHEMA_CHECK", "true")

try:
    from _env_loader import load_env  # type: ignore
    load_env()  # ne surcharge pas les vars déjà posées (dont DATABASE_URL ci-dessus)
except Exception:
    pass  # en conteneur, les vars viennent de compose env_file

import httpx  # noqa: E402

from app.db.models import RestaurantProfile  # noqa: E402
from app.db.session import AsyncSessionLocal  # noqa: E402
from app.services.aetherix_engine import AetherixEngine  # noqa: E402
from sqlalchemy import text  # noqa: E402
from sqlalchemy.future import select  # noqa: E402

CID = os.getenv("APALEO_CLIENT_ID", "")
SEC = os.getenv("APALEO_CLIENT_SECRET", "")
PID = os.getenv("APALEO_PROPERTY_ID", "PAR")
TENANT = "tenant_sandbox"
TARGET = date(2026, 3, 13)   # vendredi avec des données réelles dans la sandbox
SERVICE = "dinner"

# Paris (property PAR) — coordonnées pour la feature distance-to-hotel (HOS-215).
PAR_LAT, PAR_LON = 48.8566, 2.3522


# ---------------------------------------------------------------------------
# 1. Données sandbox Apaleo (réelles)
# ---------------------------------------------------------------------------
async def apaleo_token() -> str:
    async with httpx.AsyncClient(timeout=15) as h:
        r = await h.post(
            "https://identity.apaleo.com/connect/token",
            data={"grant_type": "client_credentials", "client_id": CID, "client_secret": SEC},
        )
        r.raise_for_status()
        return r.json()["access_token"]


async def sandbox_signals(token: str, target: date) -> dict:
    """Réservations (dateFilter=Stay) + capacité (units) réelles de la sandbox."""
    H = {"Authorization": f"Bearer {token}"}
    frm = f"{target.isoformat()}T00:00:00Z"
    to = f"{target.isoformat()}T23:59:59Z"
    async with httpx.AsyncClient(timeout=20) as h:
        res = await h.get(
            "https://api.apaleo.com/booking/v1/reservations", headers=H,
            params={"propertyIds": PID, "dateFilter": "Stay", "from": frm, "to": to, "pageSize": 1},
        )
        reservations = res.json().get("count", 0) if res.status_code == 200 else 0
        units = await h.get(
            "https://api.apaleo.com/inventory/v1/units", headers=H,
            params={"propertyId": PID, "pageSize": 1},
        )
        capacity = units.json().get("count", 0) if units.status_code == 200 else 0
    occupancy = min(1.0, reservations / capacity) if capacity else 0.0
    return {"reservations": reservations, "capacity": capacity, "occupancy": occupancy}


# ---------------------------------------------------------------------------
# 2. Profil sandbox (upsert idempotent) — requis pour profile_loader + FK cache
# ---------------------------------------------------------------------------
async def ensure_profile(capacity: int) -> None:
    async with AsyncSessionLocal() as db:
        existing = (
            await db.execute(select(RestaurantProfile).where(RestaurantProfile.tenant_id == TENANT))
        ).scalars().first()
        if existing:
            return
        db.add(RestaurantProfile(
            tenant_id=TENANT,
            property_name="Aetherix Sandbox (Paris)",
            outlet_name="Le Banc d'Essai",
            total_seats=max(capacity, 80),
            pms_type="apaleo",
            pms_property_id=PID,
            latitude=PAR_LAT, longitude=PAR_LON,
            gps_lat=PAR_LAT, gps_lng=PAR_LON,
            manager_name="Sandbox Manager",
        ))
        await db.commit()


async def read_cached(target: date) -> dict | None:
    async with AsyncSessionLocal() as db:
        row = (await db.execute(text(
            "SELECT tenant_id, target_date, prediction_data, reasoning_summary, "
            "staffing_recommendation, created_at FROM recommendation_cache "
            "WHERE tenant_id = :t AND target_date = :d ORDER BY id DESC LIMIT 1"
        ), {"t": TENANT, "d": target})).mappings().first()
        return dict(row) if row else None


# ---------------------------------------------------------------------------
# Orchestration
# ---------------------------------------------------------------------------
async def main() -> int:
    line = "=" * 70
    print(line)
    print(f"  E2E AETHERIX × SANDBOX APALEO  |  {TARGET.isoformat()} / {SERVICE}  |  tenant={TENANT}")
    print(f"  DATABASE_URL = {os.environ['DATABASE_URL'].split('@')[-1]}")
    print(line)

    if not (CID and SEC):
        print("[FAIL] APALEO_CLIENT_ID / APALEO_CLIENT_SECRET manquants dans l'env.")
        return 2

    # 1. Données sandbox réelles
    token = await apaleo_token()
    sig = await sandbox_signals(token, TARGET)
    print(f"[1/6 DONNÉES]   property={PID}  réservations(stay)={sig['reservations']}  "
          f"capacité(units)={sig['capacity']}  occupancy={sig['occupancy']:.0%}")

    # 2. Profil en DB (réel)
    await ensure_profile(sig["capacity"])
    print(f"[2/6 PROFIL]    restaurant_profile '{TENANT}' présent en DB (upsert idempotent)")

    # 3-6. Pipeline agent complet (engine réel) + persistance
    context = {
        "occupancy": sig["occupancy"],
        "weather": {"condition": "Pluie légère, 12°C"},  # illustratif (pas d'API météo ici)
        "events": [],
        "regressors": {"occupancy": sig["occupancy"]},
    }
    print("[3/6 ENGINE]    AetherixEngine.get_forecast(...) — Prophet + Claude réel + staffing ...")
    engine = AetherixEngine()
    result = await engine.get_forecast(TENANT, TARGET, SERVICE, context)

    pred = result["prediction"]
    detail = result["reasoning_detail"]
    print(f"[4/6 FORECAST]  covers={pred['covers']} (range {pred['range_min']}-{pred['range_max']}), "
          f"confidence={pred['confidence']:.0%}, is_mock={pred['is_mock']}")
    print(f"[5/6 REASONING] claude_used={detail.get('claude_used')}  "
          f"facteurs={detail.get('confidence_factors')}")
    print(f"                « {result['reasoning'][:220]} »")
    print(f"[5/6 STAFFING]  {result['staffing_recommendation']}")

    # 6. Vérification persistance (relecture)
    cached = await read_cached(TARGET)
    if not cached:
        print("[6/6 PERSIST]   FAIL — aucune ligne recommendation_cache relue.")
        return 1
    print(f"[6/6 PERSIST]   OK — recommendation_cache relu (created_at={cached['created_at']}, "
          f"covers={cached['prediction_data'].get('covers')})")

    # Assertions e2e
    checks = {
        "données sandbox (capacité>0)": sig["capacity"] > 0,
        "reasoning Claude réel": detail.get("claude_used") is True,
        "staffing non vide": bool(result["staffing_recommendation"]),
        "persistance relue": cached is not None,
    }
    print(line)
    ok = all(checks.values())
    for name, passed in checks.items():
        print(f"  [{'PASS' if passed else 'FAIL'}] {name}")
    print(f"  RÉSULTAT E2E : {'✅ PASS' if ok else '❌ FAIL'}")
    print(line)
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))

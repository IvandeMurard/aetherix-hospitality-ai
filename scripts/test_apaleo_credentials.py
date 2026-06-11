"""
Test rapide des credentials Apaleo — sans backend.
Lance depuis la racine du repo : python scripts/test_apaleo_credentials.py
"""
import os, sys, time
import httpx
from dotenv import load_dotenv

load_dotenv("backend/.env")

client_id     = os.getenv("APALEO_CLIENT_ID", "")
client_secret = os.getenv("APALEO_CLIENT_SECRET", "")
property_id   = os.getenv("APALEO_PROPERTY_ID", "")

print("=" * 55)
print("  TEST APALEO SANDBOX CREDENTIALS")
print("=" * 55)

# 1. Credentials présents ?
print("\n[1] Credentials dans backend/.env")
ok = True
for key, val in [("CLIENT_ID", client_id), ("CLIENT_SECRET", client_secret), ("PROPERTY_ID", property_id)]:
    if not val or val in ("...", ""):
        print(f"    MANQUANT : APALEO_{key}")
        ok = False
    else:
        print(f"    OK  APALEO_{key} ({len(val)} chars)")
if not ok:
    sys.exit(1)

# 2. OAuth2 token
print("\n[2] OAuth2 — acquisition du token")
t0 = time.monotonic()
try:
    import base64
    credentials = base64.b64encode(f"{client_id}:{client_secret}".encode()).decode()
    r = httpx.post(
        "https://identity.apaleo.com/connect/token",
        headers={
            "Authorization": f"Basic {credentials}",
            "Content-Type": "application/x-www-form-urlencoded",
        },
        data={"grant_type": "client_credentials"},
        timeout=10,
    )
except Exception as e:
    print(f"    ERREUR réseau : {e}")
    sys.exit(2)

elapsed = (time.monotonic() - t0) * 1000
if r.status_code != 200:
    print(f"    ECHEC HTTP {r.status_code} : {r.text}")
    sys.exit(2)

token = r.json()["access_token"]
print(f"    OK  token en {elapsed:.0f}ms — {token[:20]}...")

# 3. Appel API : liste des réservations (pageSize=1)
print("\n[3] Appel API — GET /booking/v1/reservations")
try:
    resp = httpx.get(
        "https://api.apaleo.com/booking/v1/reservations",
        headers={"Authorization": f"Bearer {token}"},
        params={"propertyIds": property_id, "pageSize": 1},
        timeout=15,
    )
except Exception as e:
    print(f"    ERREUR réseau : {e}")
    sys.exit(3)

if resp.status_code not in (200, 204):
    print(f"    ECHEC HTTP {resp.status_code} : {resp.text}")
    sys.exit(3)

data = resp.json()
count = data.get("count", 0)
print(f"    OK  HTTP {resp.status_code} — {count} réservation(s) trouvée(s) (0 = normal en sandbox)")

print("\n" + "=" * 55)
print("  SANDBOX OK — credentials valides, API répond")
print("=" * 55)

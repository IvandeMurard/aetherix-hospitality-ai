"""
Diagnostic approfondi de l'authentification Apaleo.
Lance : python scripts/diagnose_apaleo_auth.py
"""
import base64
import os
import sys
import httpx
from dotenv import load_dotenv

load_dotenv("backend/.env")

client_id     = os.getenv("APALEO_CLIENT_ID", "")
client_secret = os.getenv("APALEO_CLIENT_SECRET", "")
property_id   = os.getenv("APALEO_PROPERTY_ID", "")

TOKEN_URL = "https://identity.apaleo.com/connect/token"

print("=" * 60)
print("  DIAGNOSTIC APALEO AUTH")
print("=" * 60)

# Afficher les valeurs exactes (secret masqué sauf début/fin)
def mask(s):
    if len(s) <= 6:
        return "***"
    return s[:3] + "*" * (len(s) - 6) + s[-3:]

print(f"\nCLIENT_ID     : '{client_id}'")
print(f"CLIENT_SECRET : '{mask(client_secret)}'  ({len(client_secret)} chars)")
print(f"PROPERTY_ID   : '{property_id}'")

# Vérifier caractères spéciaux dans le secret
has_special = any(c in client_secret for c in [' ', '\n', '\r', '\t'])
if has_special:
    print("\n⚠️  CLIENT_SECRET contient des espaces/retours à la ligne — problème probable !")
else:
    print("\nOK  Pas de whitespace dans le secret")

# Construire le header Basic auth et l'afficher (en partie)
raw = f"{client_id}:{client_secret}"
encoded = base64.b64encode(raw.encode()).decode()
print(f"\nBasic auth header : 'Basic {encoded[:20]}...' ({len(encoded)} chars)")

print("\n" + "-" * 60)
print("TEST 1 : Basic auth (méthode legacy pms_server)")
print("-" * 60)
r1 = httpx.post(
    TOKEN_URL,
    headers={
        "Authorization": f"Basic {encoded}",
        "Content-Type": "application/x-www-form-urlencoded",
    },
    data={"grant_type": "client_credentials"},
    timeout=10,
)
print(f"Status : {r1.status_code}")
print(f"Body   : {r1.text}")

print("\n" + "-" * 60)
print("TEST 2 : Form body (méthode apaleo_adapter)")
print("-" * 60)
r2 = httpx.post(
    TOKEN_URL,
    data={
        "grant_type":    "client_credentials",
        "client_id":     client_id,
        "client_secret": client_secret,
        "scope":         "offline_access openid profile",
    },
    timeout=10,
)
print(f"Status : {r2.status_code}")
print(f"Body   : {r2.text}")

print("\n" + "-" * 60)
print("TEST 3 : Basic auth + scope")
print("-" * 60)
r3 = httpx.post(
    TOKEN_URL,
    headers={
        "Authorization": f"Basic {encoded}",
        "Content-Type": "application/x-www-form-urlencoded",
    },
    data={
        "grant_type": "client_credentials",
        "scope": "offline_access openid profile",
    },
    timeout=10,
)
print(f"Status : {r3.status_code}")
print(f"Body   : {r3.text}")

print("\n" + "-" * 60)
print("TEST 4 : Introspection — le client existe-t-il ?")
print("-" * 60)
r4 = httpx.get(
    "https://identity.apaleo.com/.well-known/openid-configuration",
    timeout=10,
)
print(f"Status : {r4.status_code}")
if r4.status_code == 200:
    cfg = r4.json()
    print(f"Token endpoint confirmé : {cfg.get('token_endpoint')}")
    print(f"Grant types supportés   : {cfg.get('grant_types_supported')}")

print("\n" + "=" * 60)
print("Interprétation :")
if any(r.status_code == 200 for r in [r1, r2, r3]):
    print("  ✅ Un test a réussi — regarder lequel ci-dessus")
else:
    print("  ❌ Tous les tests échouent avec 'invalid_client'")
    print("  → Les credentials sont invalides ou expirés dans le portail Apaleo")
    print("  → Action : se connecter sur https://app.apaleo.com/ > Developers")
    print("             et vérifier / régénérer les credentials du client Aetherix")
print("=" * 60)

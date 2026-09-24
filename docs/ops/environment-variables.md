# Variables d'environnement

> Extrait de `CLAUDE.md` le 30/07/2026 — ce n'est ni un fact de session ni un index, donc sa place n'était pas dans le fichier chargé à chaque session (cf. `docs/INDEX.md` §Dette CLAUDE.md).
> **Secrets** : jamais committés. Production via `flyctl secrets set` — cf. `fly.toml` et `context/runbook-pre-pilot.md`. Incident de référence : Q2-01 (`.env.fly`, HOS-277, 21/06/2026).

## LLM & embeddings

| Variable | Rôle |
|----------|------|
| `ANTHROPIC_API_KEY` | Claude API |
| `LLM_BACKEND` | `"claude"` (défaut) · `"gemini"` · `"openai"` |
| `LLM_MODEL` | Tier `reasoning` du primaire — `"claude-sonnet-4-6"` (défaut) |
| `LLM_FAST_MODEL` | Tier `fast` du primaire — `"claude-haiku-4-5-20251001"` (défaut) |
| `LLM_FALLBACK_MODEL` | Tier `reasoning` du fallback — `"gemini-2.0-flash"` (défaut) |
| `LLM_FALLBACK_FAST_MODEL` | Tier `fast` du fallback — `"gemini-2.0-flash"` (défaut) |
| `MISTRAL_API_KEY` | Embeddings 1024d |
| `EMBEDDING_BACKEND` | `"mistral"` (défaut) · `"openai"` |
| `EMBEDDING_MODEL` | `"mistral-embed"` (défaut) |

> Routing par tâche (HOS-283, Décision #35) : les services demandent un **tier** (`reasoning` | `fast`), jamais un identifiant de modèle ; chaque provider le traduit. Le classifieur inbound demande `fast` (Haiku 4.5 sur Claude, Flash sur le fallback Gemini) — cf. `backend/app/services/receipts.py`. Changer de modèle = changer une variable ici. Impact coût dans `docs/Cost_Model.md` §2.

## Données & infrastructure

| Variable | Rôle |
|----------|------|
| `SUPABASE_URL` | PostgreSQL + pgvector |
| `SUPABASE_KEY` | Anon key |
| `DATABASE_URL` | DSN asyncpg |
| `REDIS_URL` | Upstash — session state, rate limiting |
| `LOGFIRE_TOKEN` | Pydantic Logfire (HOS-311) — **optionnel**, no-op si absent |

## Apaleo

| Variable | Rôle |
|----------|------|
| `APALEO_CLIENT_ID` | OAuth2 |
| `APALEO_CLIENT_SECRET` | OAuth2 |
| `COMPOSIO_API_KEY` | Apaleo MCP via Composio — **Inventory API uniquement** |

> Le reste du MCP Apaleo passe en natif depuis HOS-190 (Décision #21, nommage PascalCase). Composio ne subsiste que sur l'Inventory API.

## Outillage

| Variable | Rôle |
|----------|------|
| `LINEAR_API_KEY` | `lin_api_...` — workspace `Hospitalityagent` |
| `LINEAR_TEAM_ID` | `2f6bb5e2-d735-4769-9377-11fe186aa0ad` |
| `OBSIDIAN_VAULT_PATH` | `C:/Users/ivand/OneDrive/Documents/Agentic AI Hospitality` |

## RGPD — pseudonymisation & rétention (Story 7.5 / HOS-115)

| Variable | Rôle |
|----------|------|
| `PII_HASH_PEPPER` | Poivre des digests d'identifiants **stockés** (expéditeur WhatsApp, `guest_id` PMS). **Aucune valeur par défaut** : vide → l'app lève `PepperNotConfigured` au lieu de stocker un hachage nu. Générer avec `secrets.token_urlsafe(32)`, poser via `flyctl secrets set`. |
| `CONVERSATIONAL_QUERY_RETENTION_DAYS` | Rétention des messages entrants (défaut `90`). Table la plus exposée du système — cf. [`GDPR-DATA-INVENTORY.md`](../GDPR-DATA-INVENTORY.md) §6.2. |
| `RETENTION_PURGE_HOUR` | Heure UTC du passage de purge quotidien (défaut `3`). |

> ⚠️ **Rotation du poivre = rupture des digests.** Changer `PII_HASH_PEPPER` rend illisibles tous les digests existants : la dédup 60 s repart de zéro (sans dommage) mais un `guest_hashed_id` d'avant rotation ne correspondra plus à celui d'après, ce qui casse tout comptage par convive dans la durée. À traiter comme une migration, pas comme une rotation de clé ordinaire.

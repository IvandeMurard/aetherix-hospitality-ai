# Variables d'environnement

> Extrait de `CLAUDE.md` le 30/07/2026 — ce n'est ni un fact de session ni un index, donc sa place n'était pas dans le fichier chargé à chaque session (cf. `docs/INDEX.md` §Dette CLAUDE.md).
> **Secrets** : jamais committés. Production via `flyctl secrets set` — cf. `fly.toml` et `context/runbook-pre-pilot.md`. Incident de référence : Q2-01 (`.env.fly`, HOS-277, 21/06/2026).

## LLM & embeddings

| Variable | Rôle |
|----------|------|
| `ANTHROPIC_API_KEY` | Claude API |
| `LLM_BACKEND` | `"claude"` (défaut) · `"gemini"` · `"openai"` |
| `LLM_MODEL` | `"claude-sonnet-4-6"` (défaut) |
| `MISTRAL_API_KEY` | Embeddings 1024d |
| `EMBEDDING_BACKEND` | `"mistral"` (défaut) · `"openai"` |
| `EMBEDDING_MODEL` | `"mistral-embed"` (défaut) |

> Routing par tâche (HOS-283) : le classifieur inbound tourne sur Haiku 4.5, pas sur le modèle par défaut — cf. `backend/app/services/receipts.py`. Impact coût dans `docs/Cost_Model.md` §2.

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

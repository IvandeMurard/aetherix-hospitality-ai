# E2E — Agent Aetherix × Sandbox Apaleo (runbook réplicable)

> Objectif : rejouer un test **end-to-end complet** de l'agent F&B sur de **vraies
> données sandbox Apaleo**, avec persistance DB réelle. Deux chemins couverts :
> (1) script Python contre la Postgres locale, (2) appel HTTP de bout en bout sur
> le backend dockerisé. Dernière validation : **2026-06-11** (les deux PASS).

---

## 0. Pré-requis

- **Docker Desktop** up.
- `backend/.env` renseigné avec des credentials **valides** :
  `APALEO_CLIENT_ID`, `APALEO_CLIENT_SECRET`, `ANTHROPIC_API_KEY`, `MISTRAL_API_KEY`,
  `APALEO_PROPERTY_ID=PAR`.
- ⚠️ **Le stack docker lit le `.env` RACINE** (`docker-compose.yml` → `env_file: .env`),
  pas `backend/.env`. Les deux fichiers peuvent diverger. Avant de lancer l'e2e,
  vérifier que les secrets de la **racine** sont valides (voir §Gotchas).

---

## 1. Bootstrap de la base locale (une fois)

Le schéma vient des migrations Supabase (`supabase/migrations/*.sql`) — il n'y a pas
de `create_all` au boot ; le backend *vérifie* seulement la présence des tables
critiques (`app/db/schema_check.py`). Sur une Postgres « nue » (image `pgvector/pgvector`),
il faut donc créer rôles + extensions puis appliquer les migrations :

```bash
bash scripts/ops/setup_local_e2e.sh
```

Ce script (idempotent) : démarre `db`/`db_test`, crée les rôles Supabase
(`anon`, `authenticated`, `service_role`), les extensions `vector` + `uuid-ossp`,
des stubs `auth.uid()/role()/jwt()` (référencés par des policies RLS), applique les
33 migrations en ordre, puis liste les 7 tables critiques.

> Note : sur une base déjà initialisée, la migration de partitions
> `…_create_agent_action_log_partitions` / `…_add_agent_action_log` peut renvoyer
> « already exists » — bénin (non-idempotente, déjà appliquée).

---

## 2. Chemin A — Script e2e contre la Postgres locale (avec persistance)

Exerce le **vrai** `AetherixEngine` (forecast Prophet + reasoning **Claude réel** +
staffing) et écrit dans `recommendation_cache`. Recommandé **dans le conteneur backend**
(deps garanties, réseau interne vers `db`) :

```bash
# MSYS_NO_PATHCONV=1 requis sous Git-Bash (Windows) pour ne pas convertir /scripts
MSYS_NO_PATHCONV=1 docker compose run --rm \
  -e E2E_DATABASE_URL=postgresql+asyncpg://postgres:password@db:5432/aetherix \
  backend python //scripts/ops/e2e_apaleo_sandbox.py
```

Variante hôte (si les deps backend sont installées localement) — pointe le port hôte 5434 :

```bash
E2E_DATABASE_URL=postgresql+asyncpg://postgres:password@localhost:5434/aetherix \
  python scripts/ops/e2e_apaleo_sandbox.py
```

Sortie attendue (résumé) :

```
[1/6 DONNÉES]   property=PAR  réservations(stay)=4  capacité(units)=51  occupancy=8%
[4/6 FORECAST]  covers=45 (range 38-52), confidence=85%, is_mock=True
[5/6 REASONING] claude_used=True
[6/6 PERSIST]   OK — recommendation_cache relu
  RÉSULTAT E2E : ✅ PASS
```

> `E2E_DATABASE_URL` est une variable **dédiée** : le script l'utilise pour fixer
> `DATABASE_URL` avant l'import de `app.*`, afin de **ne jamais** taper par accident
> la `DATABASE_URL` de prod/Supabase présente dans `.env`.

---

## 3. Chemin B — Appel HTTP de bout en bout (backend dockerisé)

### 3.1 Démarrer le backend

```bash
docker compose up -d backend
curl -s http://localhost:8000/health    # -> {"status":"ok"}
```

> Le backend exige `AUTH_SECRET` (≥ 32 caractères, non placeholder) dans le `.env`
> racine, sinon « Application startup failed ». En générer un :
> `python -c "import secrets; print(secrets.token_hex(32))"`.

### 3.2 Forger un token MCP (scopes `predict` + `admin:train`)

L'endpoint `POST /api/v1/predictions/predict` exige un bearer avec scope `predict` ;
`POST /api/v1/predictions/train` exige `admin:train`. Le hash stocké = `sha256(raw)`
(`app/mcp_core.py::hash_token`). Insertion directe :

```bash
RAW="aetherix-e2e-sandbox-predict-token"
HASH=$(printf '%s' "$RAW" | sha256sum | cut -d' ' -f1)
docker compose exec -T db psql -U postgres -d aetherix -c \
 "INSERT INTO mcp_api_tokens (id, hotel_id, token_hash, token_prefix, scopes, label, created_at)
  VALUES (uuid_generate_v4(), 'tenant_sandbox', '$HASH', '${RAW:0:12}',
          ARRAY['predict','recommend','feedback','admin:train'], 'e2e-sandbox', now())
  ON CONFLICT (token_hash) DO NOTHING;"
```

### 3.3 Entraîner Prophet (pour `is_mock=false` — démo polie)

Sans modèle entraîné, `/predict` renvoie `is_mock=true` (placeholder) et **Claude
refuse** de le présenter comme un forecast. Entraîner d'abord sur les données démo
(365 jours, aucun credential requis) — le modèle est sauvé sur disque et **rechargé
au démarrage** par chaque worker (restart-resilience, voir §4) :

```bash
printf '%s' '{"property_id":"tenant_sandbox","data_source":"synthetic"}' > /tmp/train_body.json
curl -s -w "\nHTTP %{http_code}\n" -X POST http://localhost:8000/api/v1/predictions/train \
  -H "Authorization: Bearer $RAW" -H "Content-Type: application/json" \
  --data-binary @/tmp/train_body.json
# -> 200, "Prophet model trained on 365 days ... is_mock will be False"
```

> ⚠️ **Multi-workers** : `start.sh` lance uvicorn `--workers 4`. `/train` n'entraîne
> que le worker qui répond. Le modèle étant persisté, **redémarrer le backend**
> (`docker compose restart backend`) après le 1ᵉʳ `/train` pour que les 4 workers
> rechargent le modèle et renvoient `is_mock=false` de façon cohérente.

### 3.4 Appeler l'endpoint

```bash
printf '%s' '{"hotel_id":"tenant_sandbox","target_date":"2026-03-13","service_type":"dinner","context":{"occupancy":0.08,"weather":{"condition":"Light rain, 12C"},"events":[]}}' > /tmp/e2e_body.json
curl -s -w "\nHTTP %{http_code}\n" -X POST http://localhost:8000/api/v1/predictions/predict \
  -H "Authorization: Bearer $RAW" -H "Content-Type: application/json" \
  --data-binary @/tmp/e2e_body.json
```

Attendu : **HTTP 200**, `predicted_covers`, `confidence`, `claude_used: true`,
`staffing_recommendation`. Le `restaurant_profile` `tenant_sandbox` doit exister
(créé par le Chemin A, ou via le même upsert).

> ⚠️ Git-Bash (cp1252) corrompt les accents passés à `curl` → `400 "error parsing
> the body"`. Utiliser un corps **ASCII** ou un fichier UTF-8 via `--data-binary @`.

---

## 4. Gotchas rencontrés (2026-06-11)

| Symptôme | Cause | Correctif |
|---|---|---|
| `400 invalid_client` sur OAuth Apaleo | `APALEO_CLIENT_SECRET` du `.env` **racine** périmé (différent de `backend/.env`) | Synchroniser la racine sur la valeur validée |
| `AuthenticationError 401` (Claude) | `ANTHROPIC_API_KEY` racine périmée (rotée) | Idem — synchroniser depuis `backend/.env` |
| `Application startup failed` | `AUTH_SECRET` absent/placeholder | Générer un secret 64-hex dans `.env` racine |
| `400 error parsing the body` | accents corrompus par Git-Bash | corps ASCII ou `--data-binary @fichier.json` |
| migration 1 échoue (`uuid_generate_v4`) | extension `uuid-ossp` absente → cascade | `setup_local_e2e.sh` l'active |
| `can't open file '/app/C:/Program Files/Git/...'` | conversion de chemin MSYS | préfixer `MSYS_NO_PATHCONV=1`, chemin `//scripts/...` |
| `is_mock` incohérent (true/false alterné) | uvicorn `--workers 4` ; `/train` n'entraîne qu'un worker | redémarrer le backend après le 1ᵉʳ `/train` (reload modèle sur tous les workers) |
| `500 Regressor 'weather_score' missing` | `load_model()` ne restaurait pas `self.regressors` | corrigé : régresseurs relus depuis `model.extra_regressors` |
| mojibake `â€"` / `Â°` dans le reasoning | re-décodage cp1252 lors d'un pipe `python -m json.tool` sous Git-Bash | artefact d'**affichage** ; le payload JSON est du UTF-8 correct (vérifié U+2014/U+00B0) |

### Ce que l'e2e valide réellement

Réel : données sandbox Apaleo (REST `booking/v1` + `inventory/v1`), reasoning
**Claude** (`claude_used=true`), staffing, **persistance** `recommendation_cache`,
chargement `restaurant_profile` depuis la DB.

No-op par design : dans `AetherixEngine`, `RAGService`/`MemoryService` sont
construits **sans session** (`db=None`) → récupération patterns/mémoire renvoie vide.
C'est le comportement de l'engine en production ; l'e2e le reproduit fidèlement.

Démo polie (résolu 2026-06-11) : avec `is_mock=True` (Prophet non entraîné) + le
system prompt « agent constitution », **Claude refusait** de présenter la valeur mock
comme un forecast. Corrigé en entraînant Prophet (§3.3) → `is_mock=false` →
reasoning cohérent. Voir la preuve capturée : [`evidence/e2e-demo-2026-06-11.md`](./evidence/e2e-demo-2026-06-11.md).

Deux fixes de correctness révélés par cet e2e (commités avec) :
- `AetherixEngine` n'exposait pas `.forecaster` → `POST /train` était cassé (AttributeError).
- `AetherixEngine` ne rechargeait pas le modèle persisté au boot (restart-resilience
  promise mais absente), et `PredictionEngine.load_model()` ne restaurait pas
  `self.regressors` → `500 Regressor missing` sur tout modèle chargé.

---

## 5. Scripts liés

| Script | Rôle |
|---|---|
| `scripts/ops/setup_local_e2e.sh` | bootstrap DB locale (rôles + extensions + migrations) |
| `scripts/ops/e2e_apaleo_sandbox.py` | e2e **avec** persistance DB (Chemin A) |
| `scripts/test_agent_sandbox.py` | cœur agent (reasoning+staffing) **sans** DB — sanity check rapide |
| `scripts/test_apaleo_mcp_server.py` | smoke du serveur MCP Apaleo distant (`mcp.apaleo.com`) |

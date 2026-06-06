# Décisions architecturales — Aetherix

> Source de vérité détaillée des 22 décisions architecturales. CLAUDE.md ne contient que l'index 1-ligne.
> **Convention update :** ne jamais remettre en question sans raison documentée. Ajouter une nouvelle décision = ligne d'index dans CLAUDE.md + section détail H3 ici.
> **Cross-référence :** `docs/context/open-decisions.md` (décisions en débat avant arbitrage) · `docs/adr/` (ADR validés pour décisions techniques durables).

---

### 1 — Claude Sonnet > Mistral/GPT

Meilleur reasoning, 200K ctx, explainability critique pour notre cas (recommandations argumentées au manager F&B). Provider principal. Swap possible via `LLMProvider` abstraction (cf. Décision #9).

### 2 — Architecture mémoire 2 couches

Private Memory (pgvector par hôtel) + Hive Memory (cross-hôtels anonymisé). Backboard réévaluer Phase 3+. Détail → `docs/context/memory-architecture.md`.

### 3 — pgvector > Qdrant > Pinecone

Suffisant <50K patterns, 1 requête SQL, compatible latency MCP <500ms.

### 4 — Voice opt-in (pas voice-first)

Trop risqué en démo, clavier = fallback fiable. À re-évaluer Phase 5 dans le frame Aetherix Voice (cf. `docs/context/vision-future.md`).

### 5 — Reasoning collapsible par défaut

Réduction charge cognitive. Le manager peut déplier le raisonnement à la demande.

### 6 — Pas d'auto-actions (Phase MVP)

63% managers veulent contrôle humain (étude marché). Compatible avec frame *"tandem bike"* Murati adopté en marketing.

### 7 — Apaleo read-only Phase 0

Pas d'écriture sur réservations tant que l'outil n'est pas mature. Loguer toutes les actions agent dans `agent_action_log` (ADR-0003).

### 8 — Thin Frontend

Logique IA dans backend, dashboard = visualisation uniquement.

### 9 — Multi-LLM via `LLMProvider` abstrait

Swap Claude → Gemini → GPT sans réécriture. Claude reste provider principal (cf. Décision #1).

### 10 — Provider singleton via `lifespan` FastAPI

`LLMProvider` + `EmbeddingProvider` instanciés une fois au démarrage, stockés dans `app.state`. Factory = construction uniquement. Providers closés proprement (`aclose()`) au shutdown. Détail → `docs/bmad/_bmad-output/planning-artifacts/architecture.md`.

### 11 — Démo — stratégie données hybride

Apaleo sandbox = mock hôtel complet (5 properties, 100 réservations réelles BER/LND/MUC/PAR/VIE) — source primaire pour tests pipeline E2E et challenge de l'agent. Dataset synthétique 365j conservé pour training Prophet (`DEMO_MODE=true`). Script `scripts/ops/generate_demo_data.py` → `backend/data/demo/prophet_training.json`. Détail → `docs/context/demo-apaleo.md`.

### 12 — MCP Server Apaleo — probe suffisant pour candidature

`GET /pms/mcp/probe` (endpoint existant) prouve la connexion MCP native — suffit pour la démo Apaleo. HOS-71 (Aetherix MCP Server complet) = Phase 0.5, post-candidature.

### 13 — Pipeline Prophet — gap training identifié

`ApaleoMCPAdapter.get_historical_data()` → `DataTransformer.stay_records_to_prophet()` → `PredictionEngine.train()` : briques existent, orchestrateur manquant. Débloquer via `POST /api/v1/predictions/train` ou worker de démarrage.

### 14 — Phase 0 DoD amendée — MCP Server v0 inclus (17/04/2026)

Suite directive PM 17/04/2026 (tweet Benioff *"headless for agents"*) : ship Aetherix MCP Server v0 (HOS-71, 3 tools) est désormais un critère de validation Phase 0, **APRÈS** gate MAPE interne. Si MAPE > 22%, pivot avant ship MCP. Détail → `docs/planning/phase-0-1-execution-plan.md`.

### 15 — Phase 2 "Receipts" — scope locké (19/04/2026)

Channel = WhatsApp primary + email opt-in (SendGrid). Inbound classifier = Haiku, log confidence, auto-`modified` si < 0.6. Auth web drill-down = MCP bearer + scope `receipts:read`. Tone = terse + sharp bullets + luxury feel (driver principal, données quantitatives, evidence historique, confidence, follow-up proactif). Gate = two-track : (a) technical-ship sur Apaleo Sandbox (round-trip daily Receipt + feedback → memory + 4 Sundays digest) ; (b) trust-signal (US-7 ablation) reporté au premier pilote réel. Détail → `docs/planning/phase-2-agent-receipts.md`.

### 16 — Schema drift gate CI obligatoire (14/05/2026)

Invariant **"ORM = miroir exact des migrations"**. Tout merge bloqué si une colonne du modèle SQLAlchemy n'existe pas en DB (ou inverse). Découvert via Epic 9 (HOS-148) : 3 bugs silencieux résolus. Implémentation : `scripts/ci/check_schema_drift.py` + `scripts/ci/schema_drift_ignore.json`. Convention IDs : `docs/context/data-conventions.md`.

### 17 — Hébergement Fly.io (14/05/2026)

Backend déployé sur Fly.io, région `cdg` (Paris). 1 instance always-on (`min_machines_running=1`) — requis par APScheduler in-process. Image Docker Python 3.12 + uv multi-stage. Secrets via `flyctl secrets set` (jamais commités). Latence Paris ↔ Supabase Stockholm ~30ms (acceptable Phase 0). URL staging : `https://aetherix-backend.fly.dev`. Détail déploiement : `docs/secrets_handling.md`. Remplace l'ancienne contrainte *"local Windows / GitHub uniquement"*.

### 18 — Phase 3 cut serré + portfolio reinforcement (17/05/2026)

Phase 3 scope = Pilot Validation **uniquement** (Track A) + Portfolio Reinforcement (Track B). Multi-hotel / Mews / cross-property dashboard / food waste → Phase 4 (Scale). Track B = over-engineering volontaire pour hiring signal : Hive Memory algorithm (cold-start meta-learner per ADR-0005), Paris Open Data MCP node (`que-faire-a-paris` → pgvector → MCP tool callable par agents externes), 1 article technique public. Tacet MCP wrapping = repo séparé hors Linear Aetherix. Mews partnership form à soumettre Day 1 Phase 3 (latence partner approval). Détail → `docs/planning/phase-3-pilot-validation.md`. Epic 10 = HOS-174, 9 stories P3-1 → P3-9.

### 19 — Orchestrateur séparé — Aetherix = F&B execution node (19/05/2026)

Aetherix bounded context = F&B uniquement (forecast, staffing, memory, receipts). `AetherixEngine` délègue à `OrchestratorAgent` (services injectés). **Règle CI** : zéro import `app.*` dans `orchestrator/` (enforced par `tests/orchestrator/test_agent.py`). MCP v1 (`/mcp/v1/`) : `get_recommendations_with_memory_context` → 2 outils atomiques (`recall_memory` scope `memory:read` + `get_operational_predictions`). v0 maintenu jusqu'au 2026-08-01 (Sunset header). Anima / Guest Context Node = Phase 4. `backend/orchestrator/` = module Phase 3, repo séparé Phase 4. ADR → `docs/adr/0004-orchestrator-separation.md`.

### 20 — Anima — architecture mémoire 4 couches + DPIA gate (19/05/2026)

Le Guest Context Node Anima (Phase 4) nécessite une séparation stricte des couches temporelles, contrairement à Aetherix (mémoire opérationnelle largement long-terme). Couches :

- **Working** — Redis · TTL séjour · décisions immédiates
- **Episodic** — PostgreSQL time-filtered · séjour + 30j · contextuelles
- **Semantic** — pgvector permanent · profil
- **Segment** — k-means anonymisé cross-guests

MCP tool `query_guest_profile` prend un paramètre `scope` obligatoire. **Gate non-négociable avant tout build :** analyse RGPD/CNIL + DPIA formelle (profil émotionnel = donnée personnelle sensible). HiveMemory (Aetherix) et SensoryMemory (Tacet) servent d'embryons technologiques. Détail → `docs/mesh-architecture.md` §2 Anima.

### 21 — Apaleo MCP — convention de nommage native + sales evidence (26/05/2026, sales 28/05/2026)

Les tools Apaleo MCP natifs utilisent le **PascalCase sans préfixe** (`ListReservations`, `ListPropertyPerformanceReport`, `ListRevenuesReport`) — pas la convention Composio (`APALEO_GET_*`). Toutes les réponses sont enveloppées dans `{"data": {...}}`. `update_staffing` n'existe pas côté Apaleo MCP (retourne `False`). Tests : 17/17. MCP proxy : `scripts/apaleo_mcp_proxy.py` → `.mcp.json`.

**Sales evidence (28/05/2026) :** le playbook officiel Anthropic *"AI for Hotel Owners"* classe Apaleo dans le tier **"API-First"** recommandé (avec Mews) — direct talking point : *"Aetherix runs on one of the two PMS tiers the Anthropic playbook recommends."* À intégrer dans Agent Hub listing + deck pilot.

### 22 — Eval-by-design gate CI obligatoire (04/06/2026)

Suite Qonto talk *"AI @ Qonto: shipper et évaluer l'IA en production"* + BMad meta-gap identifié (BMM Dev Agent DoD ne couvre pas la reliability AI/ML — *"tests pass = working"* est insuffisant pour AI/ML products).

**Invariant :** *"Une story qui touche le modèle, le LLM, la memory, les providers, ou les prompts ne merge pas sans `eval/golden_dataset.jsonl` mis à jour + eval pipeline green."*

Pattern analogue à Décision #16 schema drift gate (hard gate, blocking merge). Implémentation : `scripts/ci/check_eval_coverage.py` + override label PR `eval-exempt` (refactor / doc / infra-only). Failure thresholds documentés par layer dans `eval/FAILURE_THRESHOLDS.md` (forecast MAPE, parser accuracy, memory recall, LLM reasoning, latency SLO, distribution shift).

**Framework adopté :** Qonto *"Working vs Reliable"* 5 dimensions + *"Eval as a Contract"*.

**Stories Phase 3 :** EVAL-0 (foundation BLOCKING) + EVAL-1 à EVAL-5 (5 dimensions). **Stories Phase 4 :** EVAL-6 à EVAL-10 (LLM-as-judge, human eval loops, adversarial probes étendus, cost tracking, A/B framework).

**Documents canoniques :**
- Brief PM → `docs/planning/evaluation-by-design.md`
- **ADR validé** → `docs/adr/0007-evaluation-by-design.md` (Q1-Q7 tranchés : schéma `golden_dataset.jsonl` poly + 11 catégories ; spec `scripts/ci/check_eval_coverage.py` + `scripts/eval/*.py` ; DDL Supabase 5 objets — ALTER `agent_action_log` +5 colonnes, tables `eval_runs` / `eval_baselines`, MV `distribution_shift_daily` / `abstention_daily` ; sentinel `AgentAbstention` Union-typed pas de cascade auto ; cascade drift WARN/FAIL par feature KS / Wasserstein / PSI ; story breakdown 6×Phase 3 ≈ 11j sur 3 sprints, pilot gate = EVAL-0+1+2+4)

**Asset REX Phase 3 Track B :** article *"How we extended BMad-Method with Evaluation-by-Design for AI/ML products"* à rédiger post-EVAL-0..5 shippés.

---

## Notes de maintenance

- Toute nouvelle décision architecturale : ajouter ligne d'index dans `CLAUDE.md` §Décisions architecturales + section H3 détaillée ici. Ne **JAMAIS** écrire le détail dans CLAUDE.md (rule budget ≤ 150 lignes).
- Si une décision devient obsolète, l'annoter `~~strikethrough~~` avec date de déprécation + note explicative. Ne pas supprimer (historique = asset).
- Cross-référence avec ADR : `docs/adr/000X-*.md` pour les décisions techniques formellement validées par session Architect. La décision architecturale ici = vue "fact" ; l'ADR = vue "rationale + alternatives + risques".

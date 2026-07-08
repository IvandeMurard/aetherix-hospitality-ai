# Décisions architecturales — Aetherix

> Source de vérité détaillée des 24 décisions architecturales. CLAUDE.md ne contient que l'index 1-ligne.
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

`LLMProvider` + `EmbeddingProvider` instanciés une fois au démarrage, stockés dans `app.state`. Factory = construction uniquement. Providers closés proprement (`aclose()`) au shutdown. Détail → `tools/bmad/_bmad-output/planning-artifacts/architecture.md`.

### 11 — Démo — stratégie données hybride

Apaleo sandbox = mock hôtel complet (5 properties, 100 réservations réelles BER/LND/MUC/PAR/VIE) — source primaire pour tests pipeline E2E et challenge de l'agent. Dataset synthétique 365j conservé pour training Prophet (`DEMO_MODE=true`). Script `scripts/ops/generate_demo_data.py` → `backend/data/demo/prophet_training.json`. Détail → `docs/context/demo-apaleo.md`.

### 12 — MCP Server Apaleo — probe suffisant pour candidature

`GET /pms/mcp/probe` (endpoint existant) prouve la connexion MCP native — suffit pour la démo Apaleo. HOS-71 (Aetherix MCP Server complet) = Phase 0.5, post-candidature.

### 13 — Pipeline Prophet — gap training identifié

`ApaleoMCPAdapter.get_historical_data()` → `DataTransformer.stay_records_to_prophet()` → `PredictionEngine.train()` : briques existent, orchestrateur manquant. Débloquer via `POST /api/v1/predictions/train` ou worker de démarrage.

### 14 — Phase 0 DoD amendée — MCP Server v0 inclus (17/04/2026)

Suite directive PM 17/04/2026 (tweet Benioff *"headless for agents"*) : ship Aetherix MCP Server v0 (HOS-71, 3 tools) est désormais un critère de validation Phase 0, **APRÈS** gate MAPE interne. Si MAPE > 22%, pivot avant ship MCP. Détail → `docs/_archive/planning/phase-0-1-execution-plan.md`.

### 15 — Phase 2 "Receipts" — scope locké (19/04/2026)

Channel = WhatsApp primary + email opt-in (SendGrid). Inbound classifier = Haiku, log confidence, auto-`modified` si < 0.6. Auth web drill-down = MCP bearer + scope `receipts:read`. Tone = terse + sharp bullets + luxury feel (driver principal, données quantitatives, evidence historique, confidence, follow-up proactif). Gate = two-track : (a) technical-ship sur Apaleo Sandbox (round-trip daily Receipt + feedback → memory + 4 Sundays digest) ; (b) trust-signal (US-7 ablation) reporté au premier pilote réel. Détail → `docs/_archive/planning/phase-2-agent-receipts.md`.

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

MCP tool `query_guest_profile` prend un paramètre `scope` obligatoire. **Gate non-négociable avant tout build :** analyse RGPD/CNIL + DPIA formelle (profil émotionnel = donnée personnelle sensible). HiveMemory (Aetherix) et SensoryMemory (Tacet) servent d'embryons technologiques. PoC hackathon (juin 2026, synthétique, jetable) a validé l'architecture 4-couches + scope-gating + split *Anima informe / Orchestrateur décide*. Détail → `docs/mesh-architecture.md` §2 Anima.

**Amendé par Décision #26 (17/06/2026) :** Anima renommée "Guest Cognition Layer" · Segment enrichie double portée (local + Hive prior) · `ProfileSnapshot` confidence-weighted (schema, pas couche) · Learning Engine = tier Mesh séparé (pas 5e couche) · instrumentation outcome-capture Phase 4. DPIA gate et 4 couches **inchangés**. Détail complet → `docs/adr/0011-learning-engine-hive-v2.md`.

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

**Amendement 19/06/2026 (ADR-0007 §13) — portée élargie : 3 bras.** L'invariant gate CI ci-dessus reste le **Bras A** ; eval-by-design couvre désormais explicitement tout le pipeline agentique via 3 bras partageant la même taxonomie + `eval/FAILURE_THRESHOLDS.md` (un « FAIL » = même sémantique partout) :
- **A — offline / dev-time** : non-régression golden dataset (gate `check_eval_coverage.py`, EVAL-0/1 — Epic 11 HOS-203).
- **B — runtime / online** : guardrails Epic 12 (HOS-212, G-1..G-6) + MV drift/latency sur `agent_action_log`. ⇒ l'`eval-exempt` posé sur Epic 12 est **cohérent**, pas une entorse (on mesure le parachute en vol, pas au golden dataset), tant que B tient le même standard (raison typée NFR2, métriques d'abstention).
- **C — outcome / aval** : Trust-KPI Epic 10 (HOS-174 / HOS-177/178) — *hors framework eval à ce jour*, à rattacher Phase 4 (HOS-275, articule Décision #26 outcome-capture).

Suivi ré-armement Bras A (gate offline → blocking) : HOS-216 (machinerie, WARN-first) → HOS-274 (flip blocking après N PR vertes). Détail complet → `docs/adr/0007-evaluation-by-design.md` §13.

### 23 — POS integration scope + adapter pattern (Phase 4) (06/06/2026)

Trigger : (a) Meuze.ai *"POS-only restaurants"* concurrent identifié 01/06 — défense narrative *"PMS+POS-aware cross-property intelligence"* (snippet H-6) requiert ship POS Phase 4 (pas 5) ; (b) ADR-0008 graphe de contexte (open decision 04/06) bloqué tant que schema features POS-driven non tranché ; (c) ADR-0005 cohort matching v1 PMS-only insuffisant pour discriminer hôtels même profil PMS / F&B opposé.

**Q1 vendors prioritaires Phase 4** — **Tier 1** : Lightspeed K-Series (pick #1 — REST moderne + EU fort + Mews Marketplace officiel + ICP boutique pilote) ; Oracle Micros Simphony (pick #2 conditionnel, gate post-validation Lightspeed). **Tier 2 defer** : Toast / Square / Tiller. **Tier 3 skip** : Revel / TouchBistro / CashPad / NCR Aloha / Sage / Adyen POS.

**Q2 phase** — Phase 4 confirmé. Repousser = laisser fenêtre Meuze pivot hôtels + décrédibiliser snippet H-6 + bloquer ADR-0008.

**Q3 pattern** — Nouvelle abstraction `POSProvider` Protocol dans `backend/app/providers/pos/` (cohérent Décision #9 `LLMProvider` jurisprudence) + un adapter par vendor. Read-only Phase 4 via `POS_READONLY=true` default + `POSWriteBlockedError` (analogue Décision #7 + `ApaleoWriteBlockedError`). Rejeté : single MCP client générique, mega-class multi-vendor switch, refactor `app/integrations/`.

**Q4 impact ADR-0005 cohort matching** — Promu v1 → v2 via table sœur `hotel_cohort_features_pos` (FK 1:1, opt-in tenant). 3 features POS-driven : `item_category_mix_distribution` (Dirichlet 9-dim), `ticket_size_distribution` (quantiles per service slot), `time_of_day_intensity` (covers histogram 168 buckets). Late-fusion blending α × cos_pms + β × cos_pos. Gate runtime auto-disable si Day-7 MAPE_v2 > MAPE_v1.

**Schema unifié** : `pos_outlet` + `pos_transaction` (discriminator `pos_provider` enum) + `pos_item`. Idempotence via `UNIQUE (pos_provider, vendor_transaction_id)`. Field `cover_source` (`pos_pos_count` / `pms_service_count` / `manual_input`) résout R3 cover-count divergence PMS vs POS. RLS 3/3 policies.

**Eval gate Décision #22** : `pos_anomaly` (réservé ADR-0007 D1 forward-compat) à populer Story P4-POS-6 — min 8 scenarios (cover-mismatch, late-ticket, void-spike, item-mix-shift, outlet-offline, ticket-size-tail, room-charge-orphan, modifier-explosion). `check_eval_coverage.py` enforce ≥ 5 scenarios si touche `app/providers/pos/*`.

**Story breakdown Phase 4** : 6 stories, 24 points, ~6 sprint-weeks single-dev. P4-POS-1 Protocol + Mock · P4-POS-2 migration + RLS · P4-POS-3 Lightspeed adapter · P4-POS-4 Micros stub conditionnel · P4-POS-5 cohort features v2 + LOO · P4-POS-6 `pos_anomaly` + thresholds.

**Variables env nouvelles** : `POS_BACKEND` (default `mock`), `POS_READONLY` (default `true`), `LIGHTSPEED_CLIENT_ID/SECRET`, `MICROS_TENANT_ID/CLIENT_ID/CLIENT_SECRET` (conditionnel).

**Document canonique** : `docs/adr/0006-pos-integration.md` (Q1-Q4 tranchés, 8 risques, DDL Supabase, Protocol code, story breakdown, DoD opérationnel).

**Débloque** : ADR-0008 graphe de contexte (open decision 04/06/2026) · open decision *"Food waste tracking"* Option B mesure précise.

### 24 — Graphe de contexte Postgres recursive CTE (Phase 4) (06/06/2026)

Trigger : (a) convergence session PM 04/06 thèse *"knowledge extraction = the real bottleneck"* (Mira Murati Thinking Machines + Hyperspell + GBrain + projet personnel Lore — `memory/market_signals_2026Q2.md`) ; (b) cohort matching v2 ADR-0006 = late-fusion **scalar** (`α × cos_pms + β × cos_pos`), insuffisant pour traverser *"event A causé outcome B chez hôtel co-cohorte 18 mois plus tôt"* ; (c) foundation Anima Phase 4 (Décision #20 — 4 couches Working/Episodic/Semantic/Segment) nécessite des relations explicites guest × stay × event × intervention ; (d) Aetherix Voice Phase 5+ (Lore-inspired tacit knowledge capture, `docs/context/vision-future.md`) pré-requis knowledge graph.

**Q1 choix tech — Path C ACCEPTED (PM sign-off 06/06/2026)** — **Postgres recursive CTE sur Supabase managed** (pas Apache AGE — confirmé non supporté Supabase managed jun 2026 via GitHub Discussion supabase/#40285 + Supabase docs extensions, vérifié cette session). Reco Architect initiale = Path A (Fly Postgres dédié + Apache AGE + `postgres_fdw`, +$15-30/mois). **PM tranche Path C** pour raison financière (cash discipline pre-pilote, $0 incrément hosting). Trade-offs acceptés : +1 sprint refactor effort (story breakdown 6 stories / 26 pts vs 5 / 21 pts Path A initial), expressivité réduite vs Cypher sur queries 3-hop (latence p95 attendue 1200ms vs 800ms Path A), pas de migration triviale vers Neo4j Phase 5+. Compensations Path C : 100% cohérent stack Décisions #3 + #17 (single vendor Supabase), RLS Postgres natives (simplifient tenant isolation vs `_inject_tenant_filter` Cypher injection Path A), schema drift gate Décision #16 intégral (pas d'exception nécessaire). **Réversibilité** : si Supabase ajoute support AGE (monitor WT1 watchlist trimestriel), Path A redevient option viable Phase 5+ — migration CTE schema → AGE Cypher MERGE déjà documentée ADR-0008 §16 (effort estimé 1-2 sprints).

**Q2 schema définitif (Path C CTE)** — 8 node types matérialisés en **8 tables `aetherix_graph.node_*`** + 9 edge types matérialisés en **9 tables `aetherix_graph.edge_*`** (cf. ADR-0008 §16.2 DDL complet). Pattern : chaque node table a `hotel_id` (FK + RLS native) ; chaque edge table a `from_*` / `to_*` FK vers node tables + UNIQUE constraint sur paire idempotente (upsert via `INSERT ... ON CONFLICT DO UPDATE`). Indexes B-tree sur (`hotel_id`, `date`), (`from_*`, `to_*`), et properties query-fréquentes. ORM SQLAlchemy mirror obligatoire (17 modèles dans `backend/app/models/graph/`) — cohérent Décision #16 schema drift gate, pas d'exception nécessaire. Migration Alembic versioned.

**Q3 migration path** — Coexistence permanente pgvector + AGE. pgvector reste source de vérité **recall sémantique flou** (cosine top-k payload). AGE source de vérité **recall relationnel/path**. Phase 4.0 setup + mock, Phase 4.1 backfill batch script `scripts/ops/backfill_context_graph.py --hotel-id` (cible ~50K-150K nodes / hôtel après 3y backfill, ~5-15 min single-property), Phase 4.2 worker nightly `refresh_context_graph_nightly` 03:00 cdg + dual-read, Phase 4.3 coexistence permanente — pas de cutover. `MemoryRecallService.recall()` étendu backward-compat avec param `recall_strategy: Literal["cosine_only","path_find","hybrid","cohort_traversal"]`, default `"cosine_only"` (zéro régression callers Phase 0-3).

**Q4 cohort matching v3** — Promotion ADR-0006 D4 late-fusion **scalar** → **multi-dim path traversal**. Score final = `γ × cos_pms + δ × cos_pos + ε × path_match_score` avec `γ+δ+ε = 1`, calibré pilote. Path patterns : `(:Hotel)-[:BELONGS_TO_COHORT]->(:Cohort)<-[:BELONGS_TO_COHORT]-(other:Hotel)-[:PRODUCED]->(:Outcome)<-[:CAUSED]-(:Event)` (event outcome history), `(:SeniorIntervention)-[:INTERVENED_ON]->(:Recommendation)-[:SUGGESTED]->(:Outcome)` filtré `manager_feedback='followed'` (senior wisdom validated). Gate runtime auto-disable v3 si Day-7 MAPE_v3 > MAPE_v2 — fallback v2 ADR-0006.

**Q5 foundation Anima Phase 4** — Le graphe Aetherix Phase 4 **ne contient pas** de données guest (DPIA gate Décision #20). Mais **réserve** 3 node types (`Guest`, `Stay`, `Sentiment`) + 4 edge types (`HAS_STAY`, `EXPERIENCED`, `EXPRESSED`, `MATCHES_SEGMENT`) **non créés** Phase 4, **documentés** forward-compat Anima Phase 4 quand DPIA passé. Pré-figure le MCP tool `query_guest_profile(scope)` Anima : `scope` Anima = Cypher temporal filter (`WHERE s.start_at > NOW() - INTERVAL '24 hours'` → Working / `INTERVAL '30 days'` → Episodic / permanent → Semantic / via `MATCHES_SEGMENT` → Segment). `EXPERIENCED` edge connecte `Stay` Anima → `Outcome` Aetherix = lingua franca cross-nœud Mesh.

**Q6 MCP tools exposés (Path C)** — Un seul nouveau MCP tool `query_context_graph(query_type, depth, ...)` exposé à `/mcp/v1/`, scope `graph:read`. Whitelist 6 query types Phase 4 implémentés comme **templates SQL recursive CTE** versionnés dans `backend/app/services/context_graph_queries/` (1 fichier `.sql` par query type). **SQL arbitraire interdit MCP** (analogue Cypher interdiction Path A). Écritures via service interne uniquement (worker / backfill, pas MCP). **Tenant isolation = RLS Postgres natives** (17 policies sur tables `aetherix_graph.*`, pattern `current_setting('app.tenant_id')`) — simplifié vs Path A (pas de `_inject_tenant_filter` Python décorator nécessaire). Scenario eval canary `graph-tenant-isolation-001` blocking + env kill-switch `GRAPH_BACKEND=disabled` runtime rollback. SLO latence p95 amendé **< 1200ms** (vs 800ms Path A initial — verbosité CTE + recursive depth absorption documentée acceptable).

**Q7 eval gate Décision #22** — Nouvelle catégorie `context_graph_query` taxonomy ADR-0007 D1, layer `graph`. Min 10 scenarios initiaux. Thresholds : `precision@5 senior_wisdom_path` WARN < 0.7 / FAIL < 0.55 ; band coverage `cohort_outcome_band` WARN < 0.75 / FAIL < 0.60 ; latency p95 `query_context_graph` WARN > 800ms / FAIL > 1500ms ; cross-tenant leak = 1 leak → FAIL immédiat blocking. `scripts/ci/check_eval_coverage.py` étendu avec `backend/app/services/context_graph_service.py` trigger path, require ≥ 5 scenarios `context_graph_query` si touché.

**Story breakdown Phase 4 (Path C amendé §13.8 ADR-0008)** : **6 stories, 26 points**, ~6-7 sprint-weeks single-dev. P4-GRAPH-1 schema 17 tables FK + RLS + ORM + drift check · P4-GRAPH-2 backfill script + ingest sources · P4-GRAPH-3 worker nightly + `ContextGraphService` Python + 6 query types CTE templates · P4-GRAPH-4 `MemoryRecallService` extension hybrid CTE + pgvector · P4-GRAPH-5 MCP tool `query_context_graph` whitelist + RLS-based tenant isolation · P4-GRAPH-6 eval gate `context_graph_query` 10 scenarios + `FAILURE_THRESHOLDS.md` graph section (latence p95 < 1200ms).

**Variables env nouvelles (Path C)** : `GRAPH_BACKEND` (default `postgres_cte` Phase 4 | `apache_age` Phase 5+ si Supabase ajoute support — cf. WT1 watchlist | `disabled` kill-switch). Pas de `GRAPH_DATABASE_URL`, pas de `GRAPH_FDW_ENABLED` (Path C = même DB Supabase).

**Document canonique** : `docs/adr/0008-context-graph.md` (Q1-Q7 tranchés Status Path C accepted, 9 risques + amendment §13 PM sign-off, §16 patterns CTE override D1/D2/D4/D6 incluant DDL 17 tables + recursive CTE recall hybrid + 6 query types translation Cypher → CTE, story breakdown 6×26pts, DoD opérationnel).

**Pré-requis externe vérifié** : ADR-0006 POS accepted 06/06/2026 (schema POS = source `Outcome` node + cohort features v2 base v3 graph extension).

**Débloque** : Anima Phase 4 Guest Context Node (forward-compat schema D5, DPIA gate reste blocker Anima ADR séparé) · Aetherix Voice Phase 5+ (Lore-inspired knowledge graph relationnel).

### 25 — Multi-repo strategy + governance (16/06/2026)

Séparation **vitrine publique** (vision Mesh) / **execution nodes privés**. Méta-repo `hospitality-agentic-mesh` (PUBLIC, MIT) = README vision + `mesh-architecture.md` (migré) + ADRs cross-cutting (0004, 0010) + reusable workflows CI. Chaque nœud (Aetherix, Tacet, Orchestrator, Anima) = repo privé propriétaire.

**Q1+Q5 — contradiction du brief résolue :** Aetherix se scinde en deux entités GitHub — `aetherix-hospitality-ai` (stub public **archivé**, conserve stars/historique + sert le redirect banner) + `aetherix` (privé, code F&B actif). Seule topologie satisfaisant à la fois IP privée (Q1) et redirect public (Q5). Divergence nulle (stub read-only).

**Q3 — push-back Architect sur convention PM #5 :** BMad référencé par **URL** (pas submodule par défaut) ; submodule uniquement si une tooling *exécute* les fichiers BMad. **Q4 :** reusable workflows GitHub depuis méta-repo public (schema-drift #16, eval-gate #22, lint, security-scan) — appelables sans grant car repo public. **Q6 :** Étape 1 = status quo · **Étape 1.5** = refonte README vision-first (exception sanctionnée, additive) · **Étape 2** = sprint migration 3-5j au trigger (pilote livré + NDA OU pré-fundraise). **Q7 :** secrets runtime Fly intouchés, seuls les GitHub Actions secrets à recréer dans le repo privé. **Q8 :** méta-repo `CLAUDE.md` séparé (cross-cutting) + scinder l'index actuel Étape 2.

**Numérotation :** cette décision = #25. Le « Eval rollout discipline » spéculé #25 dans `market_signals_2026Q2.md` prendra #26 s'il est formalisé.

**Document canonique :** [`docs/adr/0010-multi-repo-strategy.md`](../adr/0010-multi-repo-strategy.md) (Q1-Q9 tranchées, plan migration séquencé, specs submodule + reusable workflow + redirect banner, DoD). Brief d'entrée `-DRAFT` supprimé (superseded).

**Amendement 06/07/2026 (Q2 — exception ADR-0012) :** le critère cross-cutting (*"interface s'étendant sur ≥2 nœuds → méta-repo"*) ne s'applique pas automatiquement quand l'ADR documente l'IP différenciante plutôt que de la gouvernance/infra. ADR-0012 (Mesh Signal Contract, Décision #31) reste `aetherix` PRIVÉ en permanence malgré son caractère cross-cutting — détail dans ADR-0010 §Q2 et Décision #31.

**Amendement 07/07/2026 (exécution partielle — déclencheur pré-candidatures) :** un troisième trigger s'ajoute aux deux de Q6 (pilote+NDA / pré-fundraise) : la **recherche d'emploi** (audit critique `analyse-critique-2026-07.md` — le case study public pointait vers un repo privé, 404). Exécuté ce jour : méta-repo public [`hospitality-agentic-mesh`](https://github.com/IvandeMurard/hospitality-agentic-mesh) (README vision + inventaire honnête construit-vs-vision + MIT, **historique frais** — règle le risque résidu Q2-01 pour le contenu public) + cross-link `tacet-app`. **Non exécuté** (reste Étape 2) : scission stub public archivé / `aetherix` privé, migration `mesh-architecture.md` + ADRs cross-cutting, reusable workflows. Contenu méta-repo volontairement minimal tant que le ticket GitHub Support Q2-01 (HOS-304) n'est pas clos. Story : HOS-305 (Epic 16, HOS-300).

### 26 — Anima : Guest Cognition Layer + confidence-weighted claims + Segment dual-scope + HiveMemory v2 (Learning Engine tier Mesh) (17/06/2026)

**Trigger :** post-hackathon Anima PoC (juin 2026) + revue architecture multi-parties (sessions 13/06–17/06) — trois évolutions par rapport à Décision #20.

**D1 — Rename Anima "Guest Cognition Layer" :** les quatre couches étaient toujours cognitives, pas juste du stockage. "Mémoire" sous-vend. Garde anti-god-object non-négociable : Anima = compréhension individuelle uniquement. Pas de policy, pas de fédération, pas de décision.

Séparation canonique : **Anima** (*Who is this guest?*) · **Hive/Mesh** (*What have we learned from similar situations?*) · **Aetherix/Orchestrateur** (*What should we do now?*).

**D2 — Confidence-weighted claims :** discipline de schema `ProfileSnapshot`, pas une couche. Champs `confidence / evidence_count / last_confirmed / decay_rate` sur toute claim Semantic. Terme "belief" rejeté (incompatible fiabilité produit). L'Orchestrateur pondère automatiquement les claims stales via ces champs.

**D3 — Segment double portée :** couche Segment = deux fonctions explicites : **Local** ("guests like this, at this hotel" — cohortes anonymisées propriété, nightly recompute) + **Hive prior** ("guests like this, across all network hotels" — agrégats fédérés, Phase 5). Similarité inter-hotels apprise (embeddings metadata hotel), pas hard-codée. Partial pooling hiérarchique + détection divergence (safety valve negative transfer). Shift 80/20 → 20/80 (Hive prior → Guest knowledge) au fil des séjours : analogue concierge expérimenté.

**D4 — Learning Engine tier Mesh séparé (Phase 5) + instrumentation Phase 4 :** policy/outcome learning = tier Mesh distinct, pas une 5e couche Anima. Dès Phase 4 : logger triple **de-identified** `(context-features, action, propensity, outcome)` à chaque décision Orchestrateur, dans un store séparé d'Anima (personal-data-free by construction). `propensity` non-négociable pour off-policy evaluation future (IPW / doubly-robust). HiveMemory v2 (Phase 5) : partage de priors/policies appris, pas de données.

**D5 — Reframing moat :** le moat est la position dans la boucle act-and-measure (seul acteur qui agit + capture + attribue causalement + fédère), pas la taille du corpus.

**Vision validée (3 niveaux) :** "Comprend comme un humain" (Anima) · "Mesure comme une machine" (outcome capture) · "Apprend comme un réseau" (HiveMemory v2 / Learning Engine Phase 5).

**Story 3.5 (HOS-246) :** outcome-capture instrumentation — actionnable Phase 4.

**Décisions ouvertes déplacées open-decisions.md :** politique exploration éthique · reward multi-objectif · méthode off-policy evaluation · floor k-anonymat Segment.

**Document canonique :** `docs/adr/0011-learning-engine-hive-v2.md`.

---

### 28 — PMS canonical schema : jurisprudence Provider étendue aux adapters PMS (amendement ADR-0006) (23/06/2026)

**Trigger :** analyse concurrentielle approfondie Grevon (`docs/competitive/grevon-analysis.md`, 23/06/2026) — leur produit **Kore** revendique explicitement *"a typical PMS API gives you raw data — rates as numbers, room types as codes. Kore goes further: it enriches, validates, and translates that data into a format LLMs actually understand"*, en amont de tous leurs agents (Pulse/Echo/Ops). Vérification du code Aetherix a confirmé un gap réel : `PMSAdapter` (`backend/app/services/pms_sync.py`) existe comme interface normalisée (`get_occupancy`, `get_revenue`, `get_historical_data`, `update_staffing_in_pms`), mais le pipeline forecast (`data_transformer.py`) la **contourne** — il lit les champs Apaleo bruts directement ("arrival", "adults", "children") pour construire le dataframe Prophet. Aucun adapter Mews n'existe encore (Phase 4, Décision #23 / HOS-186).

**Antécédent documentaire :** `docs/ARCHITECTURE.md` (obsolète, fév. 2026 — cf. CLAUDE.md §Points d'attention) nommait déjà ce composant — "PMS Adapters" listé dans une "Semantic Layer" planifiée Phase 5 — jamais construit. Le scope est tombé silencieusement quand l'architecture a pivoté (Qdrant→pgvector, Décision #3) sans décision explicite de retrait : c'est une dette de *process* (rien n'a flaggé la disparition), pas seulement une dette technique. Le "Semantic Layer" qui a survécu dans les docs courants (`docs/_archive/MARKET_INTELLIGENCE.md`, `docs/_archive/ROADMAP_NOW_NEXT_LATER.md`) ne désigne aujourd'hui que la couche RAG/pgvector (`fb_patterns` + `operational_memory`) — un concept différent (rétrieval de patterns historiques), pas la normalisation de flux PMS live.

**Décision :** étendre la jurisprudence Provider (Décision #9/#10, déjà appliquée au POS via ADR-0006 D3) aux adapters PMS. Introduire un schéma canonique vendor-agnostique (dataclasses dans `backend/app/providers/pms/base.py`, miroir exact de `providers/pos/base.py`) entre les adapters (Apaleo aujourd'hui, Mews demain) et tout consommateur interne (`DataTransformer`, `PredictionEngine`, `StaffRecommender`). Aucun composant business ne doit plus jamais lire un champ vendor-spécifique directement — seuls les adapters connaissent le format natif du PMS source.

**Scope — distinct de HOS-186 :** HOS-186 ("PMS Connector universel") opère au niveau **Orchestrateur↔PMS** (Décision #19, cross-node, multi-PMS vu depuis l'extérieur d'Aetherix) — reste backlog Phase 4, ne démarre qu'après Phase 3 Track A. Cette décision opère au niveau **interne au node Aetherix** (adapters↔pipeline forecast) — orthogonale, ne bloque pas et n'est pas bloquée par HOS-186. Une fois construit, le schéma canonique devient la fondation sur laquelle HOS-186 pourra s'appuyer (l'Orchestrateur consommerait le schéma déjà normalisé plutôt que de re-normaliser depuis zéro).

**Parallélisation :** ne touche pas `app/providers/pos/*` (Epic 13, HOS-254) ni le pilote Apaleo prod (Phase 3 Track A) — fichiers disjoints. Pré-requis recommandé avant la première story d'adapter Mews (Phase 4), pas avant. Détail technique → amendement `docs/adr/0006-pos-integration.md` §9.

**Linear :** Epic 15 (HOS-279) — 2 stories, ~5 points, `relatedTo` HOS-186.

---

### 31 — Hospitality Agentic Mesh Signal Contract (ADR-0012) (06/07/2026)

**Trigger :** reframing stratégique 05/07/2026 (*"la vraie IP n'est ni le LLM, ni MCP, ni le forecast — c'est le signal model"*) + audit des sujets architecturaux couverts, qui a révélé une dette sémantique existante : le mot "signal" était déjà utilisé de façon incohérente à trois endroits du repo (Tacet "signaux structurés", Anima `sentiment_signal`, Aetherix "signal d'apprentissage" mémoire) sans jamais être unifié.

**Décision (r3, après deux cycles de revue externe) :** contrat Mesh-wide (pas Aetherix-only) définissant :
- **`DomainSignal`** — namespaced par bounded context du nœud propriétaire (`environmental.*` Tacet, `guest.*` Anima, `fnb.*` Aetherix, `operational.*`/`orchestrator.*` Orchestrateur). Aucune fonction de promotion centralisée — chaque nœud interprète déjà dans son domaine (cohérent ADR-0004 D1, ADR-0011 D1), pas d'objet `Observation` intermédiaire.
- **`SignalComposite`** — agrégation cross-domaine côté Orchestrateur, `significance_score` continu, **aucun champ actionable/candidate_decision** — frontière perception/décision protégée pour ne pas recréer l'antipattern déprécié par ADR-0004 D5.
- **Calibration à 3 niveaux** : prior de cohorte Hive (défaut day-1, Décision #2/#26 D3) → apprentissage local (boucle Private Memory) → override manager explicite (`orchestrator.override`, priorité max). Répond à la question "qui a autorité sur les seuils" sans reporter la charge de configuration initiale sur le client (ce qui contredirait la promesse cold-start).
- **`CollectivePattern`** — alias ontologique de `fb_patterns` (Hive Memory Aetherix) et du Hive prior Anima (Décision #26 D3, ADR-0011 D3/D4) — pas un nouveau store. Nourrit la calibration, jamais composé avec des signaux locaux (portée `hotel_id` stricte inchangée).
- **Pas de `decay_rate`** sur `DomainSignal` v0.1 (YAGNI) — reste exclusivement une propriété des Semantic claims Anima (ADR-0011 D2). `DomainSignal` utilise `observed_at`/`effective_from`/`expires_at`.

**Implémentation :** Phase 4, gated par le tranchage de la décision ouverte "Interaction model event-driven Phase 4-5" — sous cron quotidien actuel, la composition cross-domaine n'a pas d'occasion réelle de compter à temps.

**Gel terminologique post-acceptation :** tout changement de vocabulaire futur passe par amendement d'ADR explicite, pas un renommage silencieux.

**Amendement 06/07/2026 — reste privé, exception au méta-repo public :** décision Ivan — contrairement à `mesh-architecture.md`, ce document ne migre jamais vers le méta-repo public (Décision #25/ADR-0010 Q2), malgré son caractère cross-cutting (≥2 nœuds). C'est l'IP différenciante du produit, pas de la gouvernance/infra. Amendement correspondant : ADR-0010 §Q2. Si une mention publique apparaît un jour, elle se limite à une ligne générique sans vocabulaire ni mécanisme de calibration.

**Document canonique :** `docs/adr/0012-mesh-signal-contract.md`.

---

## Notes de maintenance

- Toute nouvelle décision architecturale : ajouter ligne d'index dans `CLAUDE.md` §Décisions architecturales + section H3 détaillée ici. Ne **JAMAIS** écrire le détail dans CLAUDE.md (rule budget ≤ 150 lignes).
- Si une décision devient obsolète, l'annoter `~~strikethrough~~` avec date de déprécation + note explicative. Ne pas supprimer (historique = asset).
- Cross-référence avec ADR : `docs/adr/000X-*.md` pour les décisions techniques formellement validées par session Architect. La décision architecturale ici = vue "fact" ; l'ADR = vue "rationale + alternatives + risques".

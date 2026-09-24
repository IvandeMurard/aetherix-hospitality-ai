# Décisions architecturales — Aetherix

> Source de vérité détaillée des décisions architecturales. CLAUDE.md ne contient que l'index 1-ligne.
> *Le compte n'est volontairement pas écrit ici : un nombre codé en dur dérive au premier ajout. Il se lit en comptant les sections `### N — ` — c'est ce que fait le détecteur D6 de l'agent d'hygiène.*
> **Convention update :** ne jamais remettre en question sans raison documentée. Ajouter une nouvelle décision = ligne d'index dans CLAUDE.md + section détail H3 ici.
> **Cross-référence :** `docs/context/open-decisions.md` (décisions en débat avant arbitrage) · `docs/adr/` (ADR validés pour décisions techniques durables).

---

### 1 — Claude Sonnet > Mistral/GPT

Meilleur reasoning, 200K ctx, explainability critique pour notre cas (recommandations argumentées au manager F&B). Provider principal. Swap possible via `LLMProvider` abstraction (cf. Décision #9).

### 2 — Architecture mémoire 2 couches

Private Memory (pgvector par hôtel) + Hive Memory (cross-hôtels, dite « anonymisée » — ⚠️ **propriété non prouvée**, plancher de k-anonymat non tranché (HOS-323), statut RGPD **pseudonyme par défaut** en attendant). Backboard réévaluer Phase 3+. Détail → `docs/context/memory-architecture.md`.

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

Backend déployé sur Fly.io, région `cdg` (Paris). 1 instance always-on (`min_machines_running=1`) — requis par APScheduler in-process. Image Docker Python 3.12 + uv multi-stage. Secrets via `flyctl secrets set` (jamais commités). Latence Paris ↔ Supabase Stockholm ~30ms (acceptable Phase 0). URL staging : `https://aetherix-backend.fly.dev`. Détail déploiement : `docs/SECURITY/secrets_handling.md`. Remplace l'ancienne contrainte *"local Windows / GitHub uniquement"*.

### 18 — Phase 3 cut serré + portfolio reinforcement (17/05/2026)

Phase 3 scope = Pilot Validation **uniquement** (Track A) + Portfolio Reinforcement (Track B). Multi-hotel / Mews / cross-property dashboard / food waste → Phase 4 (Scale). Track B = over-engineering volontaire pour hiring signal : Hive Memory algorithm (cold-start meta-learner per ADR-0005), Paris Open Data MCP node (`que-faire-a-paris` → pgvector → MCP tool callable par agents externes), 1 article technique public. Tacet MCP wrapping = repo séparé hors Linear Aetherix. Mews partnership form à soumettre Day 1 Phase 3 (latence partner approval). Détail → `docs/planning/phase-3-pilot-validation.md`. Epic 10 = HOS-174, 9 stories P3-1 → P3-9.

### 19 — Orchestrateur séparé — Aetherix = F&B execution node (19/05/2026)

Aetherix bounded context = F&B uniquement (forecast, staffing, memory, receipts). `AetherixEngine` délègue à `OrchestratorAgent` (services injectés). **Règle CI** : zéro import `app.*` dans `orchestrator/` (enforced par `tests/orchestrator/test_agent.py`). MCP v1 (`/mcp/v1/`) : `get_recommendations_with_memory_context` → 2 outils atomiques (`recall_memory` scope `memory:read` + `get_operational_predictions`). v0 maintenu jusqu'au 2026-08-01 (Sunset header) — **route `/mcp/v0/` retirée le 01/08/2026 (HOS-315)** : manifeste agent (`wellknown.py`) et smoke E2E bascules sur v1, `TOOLS_MANIFEST` conservé (il construit `V1_TOOLS_MANIFEST`), ADR-0001 marqué superseded. Anima / Guest Context Node = Phase 4. `backend/orchestrator/` = module Phase 3, repo séparé Phase 4. ADR → `docs/adr/0004-orchestrator-separation.md`.

### 20 — Anima — architecture mémoire 4 couches + DPIA gate (19/05/2026)

Le Guest Context Node Anima (Phase 4) nécessite une séparation stricte des couches temporelles, contrairement à Aetherix (mémoire opérationnelle largement long-terme). Couches :

- **Working** — Redis · TTL séjour · décisions immédiates
- **Episodic** — PostgreSQL time-filtered · séjour + 30j · contextuelles
- **Semantic** — pgvector durable **borné 36 mois** glissants depuis le dernier séjour (amendement DPIA 01/08, ci-dessous) · profil
- **Segment** — k-means anonymisé cross-guests

MCP tool `query_guest_profile` prend un paramètre `scope` obligatoire. **Gate non-négociable avant tout build :** analyse RGPD/CNIL + DPIA formelle (profil émotionnel = donnée personnelle sensible). HiveMemory (Aetherix) et SensoryMemory (Tacet) servent d'embryons technologiques. PoC hackathon (juin 2026, synthétique, jetable) a validé l'architecture 4-couches + scope-gating + split *Anima informe / Orchestrateur décide*. Détail → `docs/mesh-architecture.md` §2 Anima.

**Amendé par Décision #26 (17/06/2026) :** Anima renommée "Guest Cognition Layer" · Segment enrichie double portée (local + Hive prior) · `ProfileSnapshot` confidence-weighted (schema, pas couche) · Learning Engine = tier Mesh séparé (pas 5e couche) · instrumentation outcome-capture Phase 4. DPIA gate et 4 couches **inchangés**. Détail complet → `docs/adr/0011-learning-engine-hive-v2.md`.

**Amendement DPIA (01/08/2026, HOS-229) — le gate reste fermé, et il est désormais documenté.** L'analyse RGPD/CNIL formelle est livrée : [`docs/context/dpia-anima-2026-08.md`](dpia-anima-2026-08.md). Obligation art. 35 établie sans ambiguïté (6 critères pleins + 2 partiels sur les 9 du WP248) — le gate n'est pas une prudence maison. **Verdict : non levé**, 13 mesures bloquantes et 9 conditions de levée (§9.2 et §11 du doc). Quatre corrections apportées à la présente décision :

1. **Durées de conservation — la couche Semantic n'est plus « ∞ ».** « Permanent » est incompatible avec l'art. 5(1)(e) ; `decay_rate` pondère, il n'efface pas. Semantic devient **durable borné** : 36 mois glissants depuis le dernier séjour (24 si base = consentement), prolongeable par re-consentement. Working = check-out + 24 h, plafond dur 7 j (« durée du séjour » est un événement, pas une durée). Episodic = séjour + 30 j, à justifier et à réconcilier avec le 90 j PMS brut (Story 7.5 AC5). Segment ∞ **conditionnel** au plancher de k-anonymat. Tableau complet → doc §6. La séparation en 4 couches est **confirmée et renforcée** : c'est elle qui rend possible une durée par finalité, donc une mesure de minimisation opposable.
2. **Vocabulaire — « donnée personnelle sensible » était imprécis.** L'état émotionnel inféré n'est pas une donnée de l'art. 9 en soi ; il est **hautement personnel** au sens WP248, et devient art. 9 par ce qu'il révèle (santé, conviction religieuse — cf. l'exemple `menu végétarien` de la couche Episodic). Conséquence opérationnelle : les `drivers` de `get_emotional_risk` doivent être une **énumération fermée**, jamais une sortie libre de LLM.
3. **Frontière AI Act (règlement (UE) 2024/1689) — ligne rouge écrite.** Anima échappe au régime haut risque *uniquement* parce qu'elle infère depuis du texte et du comportement, pas depuis du biométrique (art. 3(39)). Toute entrée **voix ou visage** — donc la rencontre avec « Aetherix Voice » (`vision-future.md`, Phase 5) — bascule le système en Annexe III + art. 9 + art. 50(3) et change l'ordre de grandeur du coût de conformité. Seconde ligne rouge : **aucune inférence émotionnelle sur le personnel** (art. 5(1)(f) = pratique *interdite*, pas régulée).
4. **Rôle RGPD — la fédération fait sortir Aetherix de la sous-traitance.** Working/Episodic/Semantic + Segment local = sous-traitant pour le compte de l'hôtel. **Segment Hive prior (Phase 5) = Aetherix responsable de traitement** (finalité, moyens et bénéficiaires déterminés seul). La DPA type (Story 7.5 / HOS-115) doit être **à deux étages**, pas un modèle sous-traitant standard.

**Trois arbitrages restent ouverts** (doc §10, signalés sans être appliqués — ils ne consomment pas d'heures de preuve et ne rompent pas le gel Epic 16) : (a) qualification du store outcome ADR-0011 D4, dont l'anonymat est affirmé et non prouvé — position par défaut **pseudonyme** tant que l'analyse de ré-identification n'existe pas ; (b) ~~plancher de k-anonymat~~ — ✅ **tranché 01/08/2026 (HOS-323)** : `k = 20` clients par cohorte + garde de concentration ~90 % (k-anonymat seul ne protège pas des *attributs* — attaque par homogénéité) + dégradation vers une cohorte plus grossière sous le seuil, jamais un k plus bas. **Et aucun anonymat n'est revendiqué** : la couche 4 reste dans le régime des données personnelles, faute de relecture juridique finançable — on ne s'appuie pas sur une qualification qu'on ne peut pas faire valider, et s'en abstenir ne coûte rien tant que la couche n'est pas construite. Détail → `open-decisions.md` §Resolved ; (c) absence de chemin de **rectification** d'une claim inférée. Le reste (consentement, opposition, DSAR, DPA, tests) est du travail Phase 4 et **reste gelé** — la DPIA appartient au responsable de traitement, donc à un hôtel, et il n'y en a aucun à ce jour.

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

**Q4 impact ADR-0005 cohort matching** — ⚠️ **DIFFÉRÉ le 31/07/2026 (ADR-0006 §10).** La table `hotel_cohort_features` (v1, ADR-0005) sur laquelle cette décision construit **n'existe pas** — aucune migration, aucun ORM, aucune référence en code. Pire : la DDL de `hotel_cohort_features_pos` vivait dans la migration de **P4-POS-2** avec une FK vers cette table absente, donc l'intégralité du backlog POS échouait dès la deuxième story. Le socle est par ailleurs **gelé** (cohort matching = Hive = une des 5 briques gelées par l'audit). Précondition de levée : gel Hive levé + ADR-0005 D1-D5 construits + D7 (validation LOO) exécuté. Conception d'origine conservée pour mémoire : table sœur `hotel_cohort_features_pos` (FK 1:1, opt-in tenant), 3 features POS-driven (`item_category_mix_distribution` Dirichlet 9-dim, `ticket_size_distribution` quantiles per service slot, `time_of_day_intensity` histogram 168 buckets), late-fusion α × cos_pms + β × cos_pos, gate runtime auto-disable si Day-7 MAPE_v2 > MAPE_v1.

**Schema unifié** : `pos_outlet` + `pos_transaction` (discriminator `pos_provider` enum) + `pos_item`. Idempotence via `UNIQUE (pos_provider, vendor_transaction_id)`. Field `cover_source` (`pos_pos_count` / `pms_service_count` / `manual_input`) résout R3 cover-count divergence PMS vs POS. RLS 3/3 policies.

**Eval gate Décision #22** : `pos_anomaly` (réservé ADR-0007 D1 forward-compat) à populer Story P4-POS-6 — min 8 scenarios (cover-mismatch, late-ticket, void-spike, item-mix-shift, outlet-offline, ticket-size-tail, room-charge-orphan, modifier-explosion). `check_eval_coverage.py` enforce ≥ 5 scenarios si touche `app/providers/pos/*`.

**Story breakdown Phase 4** : **5 stories, 19 points** (amendé §10 — P4-POS-5 retirée), ~5 sprint-weeks single-dev. P4-POS-1 Protocol + Mock · P4-POS-2 migration + RLS · P4-POS-3 Lightspeed adapter · P4-POS-4 Micros stub conditionnel · ~~P4-POS-5 cohort features v2 + LOO~~ (hors périmètre) · P4-POS-6 `pos_anomaly` + thresholds. L'ingestion POS reste livrable : couper la dépendance vers du travail gelé la débloque.

**Variables env nouvelles** : `POS_BACKEND` (default `mock`), `POS_READONLY` (default `true`), `LIGHTSPEED_CLIENT_ID/SECRET`, `MICROS_TENANT_ID/CLIENT_ID/CLIENT_SECRET` (conditionnel).

**Document canonique** : `docs/adr/0006-pos-integration.md` (Q1-Q4 tranchés, 8 risques, DDL Supabase, Protocol code, story breakdown, DoD opérationnel).

**Débloque** : ADR-0008 graphe de contexte (open decision 04/06/2026) · open decision *"Food waste tracking"* Option B mesure précise.

### 24 — Graphe de contexte Postgres recursive CTE — 🛑 **DIFFÉRÉ Phase 4 (PM sign-off 31/07/2026)** (06/06/2026)

> **Statut 31/07/2026** : ADR-0008 passe `Accepted` → **`Deferred (Phase 4)`** dans son ensemble (ADR-0008 §17.6). Backlog P4-GRAPH-1→6 sorti de la Phase 4, aucune story Linear à créer au kickoff.
>
> **Cause** : la moitié du graphe repose sur `hotel_cohort_features`, table inexistante dont le socle Hive est gelé. Le nœud `Cohort` étant la frontière d'anonymisation (§6), les 3 query types cross-propriétés ne sont pas dégradables. Les 3 restants sont intra-propriété et recouvrent largement `operational_memory` + pgvector — alors que la justification écrite du graphe (§1.2/§1.3) porte sur la réutilisation cross-propriétés. **La valeur différenciante est exactement la partie gelée.**
>
> **Arbitrage de calendrier, pas de conception** : aucune ligne de §1-§16 n'est invalidée. Path C, schema 8 nodes / 9 edges, 6 query types, DDL, patterns CTE, isolation RLS, kill-switch restent la référence au moment de la reprise. Rien à réécrire.
>
> **Précondition de reprise** : ADR-0006 §10.4 dans l'ordre — gel Hive levé → ADR-0005 D1-D5 construits → D7 (LOO) exécuté → ADR-0006 §D4 levé → puis ADR-0008.
>
> **Effet transitif** : ADR-0011 (Learning Engine, Phase 5) déclare une dépendance à ADR-0008 — différée par conséquence.
>
> Le détail ci-dessous documente la conception, qui reste valide et non amendée.

Trigger : (a) convergence session PM 04/06 thèse *"knowledge extraction = the real bottleneck"* (Mira Murati Thinking Machines + Hyperspell + GBrain + projet personnel Lore — `memory/market_signals_2026Q2.md`) ; (b) cohort matching v2 ADR-0006 = late-fusion **scalar** (`α × cos_pms + β × cos_pos`), insuffisant pour traverser *"event A causé outcome B chez hôtel co-cohorte 18 mois plus tôt"* ; (c) foundation Anima Phase 4 (Décision #20 — 4 couches Working/Episodic/Semantic/Segment) nécessite des relations explicites guest × stay × event × intervention ; (d) Aetherix Voice Phase 5+ (Lore-inspired tacit knowledge capture, `docs/context/vision-future.md`) pré-requis knowledge graph.

**Q1 choix tech — Path C ACCEPTED (PM sign-off 06/06/2026)** — **Postgres recursive CTE sur Supabase managed** (pas Apache AGE — confirmé non supporté Supabase managed jun 2026 via GitHub Discussion supabase/#40285 + Supabase docs extensions, vérifié cette session). Reco Architect initiale = Path A (Fly Postgres dédié + Apache AGE + `postgres_fdw`, +$15-30/mois). **PM tranche Path C** pour raison financière (cash discipline pre-pilote, $0 incrément hosting). Trade-offs acceptés : +1 sprint refactor effort (story breakdown 6 stories / 26 pts vs 5 / 21 pts Path A initial), expressivité réduite vs Cypher sur queries 3-hop (latence p95 attendue 1200ms vs 800ms Path A), pas de migration triviale vers Neo4j Phase 5+. Compensations Path C : 100% cohérent stack Décisions #3 + #17 (single vendor Supabase), RLS Postgres natives (simplifient tenant isolation vs `_inject_tenant_filter` Cypher injection Path A), schema drift gate Décision #16 intégral (pas d'exception nécessaire). **Réversibilité** : si Supabase ajoute support AGE (monitor WT1 watchlist trimestriel), Path A redevient option viable Phase 5+ — migration CTE schema → AGE Cypher MERGE déjà documentée ADR-0008 §16 (effort estimé 1-2 sprints).

**Q2 schema définitif (Path C CTE)** — 8 node types matérialisés en **8 tables `aetherix_graph.node_*`** + 9 edge types matérialisés en **9 tables `aetherix_graph.edge_*`** (cf. ADR-0008 §16.2 DDL complet). Pattern : chaque node table a `hotel_id` (FK + RLS native) ; chaque edge table a `from_*` / `to_*` FK vers node tables + UNIQUE constraint sur paire idempotente (upsert via `INSERT ... ON CONFLICT DO UPDATE`). Indexes B-tree sur (`hotel_id`, `date`), (`from_*`, `to_*`), et properties query-fréquentes. ORM SQLAlchemy mirror obligatoire (17 modèles dans `backend/app/models/graph/`) — cohérent Décision #16 schema drift gate, pas d'exception nécessaire. Migration Alembic versioned.

**Q3 migration path** — Coexistence permanente pgvector + AGE. pgvector reste source de vérité **recall sémantique flou** (cosine top-k payload). AGE source de vérité **recall relationnel/path**. Phase 4.0 setup + mock, Phase 4.1 backfill batch script `scripts/ops/backfill_context_graph.py --hotel-id` (cible ~50K-150K nodes / hôtel après 3y backfill, ~5-15 min single-property), Phase 4.2 worker nightly `refresh_context_graph_nightly` 03:00 cdg + dual-read, Phase 4.3 coexistence permanente — pas de cutover. `MemoryRecallService.recall()` étendu backward-compat avec param `recall_strategy: Literal["cosine_only","path_find","hybrid","cohort_traversal"]`, default `"cosine_only"` (zéro régression callers Phase 0-3).

**Q4 cohort matching v3** — ⚠️ **DIFFÉRÉ le 31/07/2026 (ADR-0008 §17).** Hérite du blocage d'ADR-0006 §D4 : `hotel_cohort_features` n'existe pas et son socle Hive est gelé. **Le point décisif est autre qu'en ADR-0006** : ici le nœud `Cohort` est la **frontière d'anonymisation** (§6 — *« raw data stays in your tenant, operational patterns travel anonymized »*), donc les 3 query types cross-propriétés ne peuvent pas être dégradés en version sans filtre cohorte — ce serait la fuite que le canari `graph-tenant-isolation-001` traite en FAIL bloquant. Périmètre Phase 4 : 6 → 3 query types (intra-propriété), 8 → 7 node types, 26 → 21 pts. P4-GRAPH-4 dépendait de P4-POS-5 (sortie du périmètre) : le tool MCP et le gate eval étaient déjà inatteignables. **Question ouverte §17.5, non tranchée** : la valeur résiduelle d'un graphe intra-propriété à 3 requêtes justifie-t-elle 21 pts en Phase 4 ? Recommandation Architect = différer l'ADR en entier. Conception d'origine conservée pour mémoire : promotion ADR-0006 D4 late-fusion **scalar** → **multi-dim path traversal**. Score final = `γ × cos_pms + δ × cos_pos + ε × path_match_score` avec `γ+δ+ε = 1`, calibré pilote. Path patterns : `(:Hotel)-[:BELONGS_TO_COHORT]->(:Cohort)<-[:BELONGS_TO_COHORT]-(other:Hotel)-[:PRODUCED]->(:Outcome)<-[:CAUSED]-(:Event)` (event outcome history), `(:SeniorIntervention)-[:INTERVENED_ON]->(:Recommendation)-[:SUGGESTED]->(:Outcome)` filtré `manager_feedback='followed'` (senior wisdom validated). Gate runtime auto-disable v3 si Day-7 MAPE_v3 > MAPE_v2 — fallback v2 ADR-0006.

**Q5 foundation Anima Phase 4** — Le graphe Aetherix Phase 4 **ne contient pas** de données guest (DPIA gate Décision #20). Mais **réserve** 3 node types (`Guest`, `Stay`, `Sentiment`) + 4 edge types (`HAS_STAY`, `EXPERIENCED`, `EXPRESSED`, `MATCHES_SEGMENT`) **non créés** Phase 4, **documentés** forward-compat Anima Phase 4 quand DPIA passé. Pré-figure le MCP tool `query_guest_profile(scope)` Anima : `scope` Anima = Cypher temporal filter (`WHERE s.start_at > NOW() - INTERVAL '24 hours'` → Working / `INTERVAL '30 days'` → Episodic / permanent → Semantic / via `MATCHES_SEGMENT` → Segment). `EXPERIENCED` edge connecte `Stay` Anima → `Outcome` Aetherix = lingua franca cross-nœud Mesh.

**Q6 MCP tools exposés (Path C)** — Un seul nouveau MCP tool `query_context_graph(query_type, depth, ...)` exposé à `/mcp/v1/`, scope `graph:read`. Whitelist 6 query types Phase 4 implémentés comme **templates SQL recursive CTE** versionnés dans `backend/app/services/context_graph_queries/` (1 fichier `.sql` par query type). **SQL arbitraire interdit MCP** (analogue Cypher interdiction Path A). Écritures via service interne uniquement (worker / backfill, pas MCP). **Tenant isolation = RLS Postgres natives** (17 policies sur tables `aetherix_graph.*`, pattern `current_setting('app.tenant_id')`) — simplifié vs Path A (pas de `_inject_tenant_filter` Python décorator nécessaire). Scenario eval canary `graph-tenant-isolation-001` blocking + env kill-switch `GRAPH_BACKEND=disabled` runtime rollback. SLO latence p95 amendé **< 1200ms** (vs 800ms Path A initial — verbosité CTE + recursive depth absorption documentée acceptable).

**Q7 eval gate Décision #22** — Nouvelle catégorie `context_graph_query` taxonomy ADR-0007 D1, layer `graph`. Min 10 scenarios initiaux. Thresholds : `precision@5 senior_wisdom_path` WARN < 0.7 / FAIL < 0.55 ; band coverage `cohort_outcome_band` WARN < 0.75 / FAIL < 0.60 ; latency p95 `query_context_graph` WARN > 800ms / FAIL > 1500ms ; cross-tenant leak = 1 leak → FAIL immédiat blocking. `scripts/ci/check_eval_coverage.py` étendu avec `backend/app/services/context_graph_service.py` trigger path, require ≥ 5 scenarios `context_graph_query` si touché.

**Story breakdown Phase 4 (Path C amendé §13.8 ADR-0008)** : **6 stories, 26 points**, ~6-7 sprint-weeks single-dev. P4-GRAPH-1 schema 17 tables FK + RLS + ORM + drift check · P4-GRAPH-2 backfill script + ingest sources · P4-GRAPH-3 worker nightly + `ContextGraphService` Python + 6 query types CTE templates · P4-GRAPH-4 `MemoryRecallService` extension hybrid CTE + pgvector · P4-GRAPH-5 MCP tool `query_context_graph` whitelist + RLS-based tenant isolation · P4-GRAPH-6 eval gate `context_graph_query` 10 scenarios + `FAILURE_THRESHOLDS.md` graph section (latence p95 < 1200ms).

**Variables env nouvelles (Path C)** : `GRAPH_BACKEND` (default `postgres_cte` Phase 4 | `apache_age` Phase 5+ si Supabase ajoute support — cf. WT1 watchlist | `disabled` kill-switch). Pas de `GRAPH_DATABASE_URL`, pas de `GRAPH_FDW_ENABLED` (Path C = même DB Supabase).

**Document canonique** : `docs/adr/0008-context-graph.md` (Q1-Q7 tranchés Status Path C accepted, 9 risques + amendment §13 PM sign-off, §16 patterns CTE override D1/D2/D4/D6 incluant DDL 17 tables + recursive CTE recall hybrid + 6 query types translation Cypher → CTE, story breakdown 6×26pts, DoD opérationnel).

**Pré-requis externe vérifié** : ADR-0006 POS accepted 06/06/2026 (schema POS = source `Outcome` node + cohort features v2 base v3 graph extension).

**Débloque** : Anima Phase 4 Guest Context Node (forward-compat schema D5, DPIA gate reste blocker Anima ADR séparé) · Aetherix Voice Phase 5+ (Lore-inspired knowledge graph relationnel).

### 25 — Multi-repo strategy + governance (16/06/2026)

Séparation **vitrine publique** (vision Mesh) / **execution nodes privés**. Méta-repo `Hospitality-Multi-agent-Architecture` (PUBLIC, MIT) = README vision + `mesh-architecture.md` (migré) + ADRs cross-cutting (0004, 0010) + reusable workflows CI. Chaque nœud (Aetherix, Tacet, Orchestrator, Anima) = repo privé propriétaire.

**Q1+Q5 — contradiction du brief résolue :** Aetherix se scinde en deux entités GitHub — `aetherix-hospitality-ai` (stub public **archivé**, conserve stars/historique + sert le redirect banner) + `aetherix` (privé, code F&B actif). Seule topologie satisfaisant à la fois IP privée (Q1) et redirect public (Q5). Divergence nulle (stub read-only).

**Q3 — push-back Architect sur convention PM #5 :** BMad référencé par **URL** (pas submodule par défaut) ; submodule uniquement si une tooling *exécute* les fichiers BMad. **Q4 :** reusable workflows GitHub depuis méta-repo public (schema-drift #16, eval-gate #22, lint, security-scan) — appelables sans grant car repo public. **Q6 :** Étape 1 = status quo · **Étape 1.5** = refonte README vision-first (exception sanctionnée, additive) · **Étape 2** = sprint migration 3-5j au trigger (pilote livré + NDA OU pré-fundraise). **Q7 :** secrets runtime Fly intouchés, seuls les GitHub Actions secrets à recréer dans le repo privé. **Q8 :** méta-repo `CLAUDE.md` séparé (cross-cutting) + scinder l'index actuel Étape 2.

**Numérotation :** cette décision = #25. Le « Eval rollout discipline » spéculé #25 dans `market_signals_2026Q2.md` prendra #26 s'il est formalisé.

**Document canonique :** [`docs/adr/0010-multi-repo-strategy.md`](../adr/0010-multi-repo-strategy.md) (Q1-Q9 tranchées, plan migration séquencé, specs submodule + reusable workflow + redirect banner, DoD). Brief d'entrée `-DRAFT` supprimé (superseded).

**Amendement 06/07/2026 (Q2 — exception ADR-0012) :** le critère cross-cutting (*"interface s'étendant sur ≥2 nœuds → méta-repo"*) ne s'applique pas automatiquement quand l'ADR documente l'IP différenciante plutôt que de la gouvernance/infra. ADR-0012 (Mesh Signal Contract, Décision #31) reste `aetherix` PRIVÉ en permanence malgré son caractère cross-cutting — détail dans ADR-0010 §Q2 et Décision #31.

**Amendement 07/07/2026 (exécution partielle — déclencheur pré-candidatures) :** un troisième trigger s'ajoute aux deux de Q6 (pilote+NDA / pré-fundraise) : la **recherche d'emploi** (audit critique `analyse-critique-2026-07.md` — le case study public pointait vers un repo privé, 404). Exécuté ce jour : méta-repo public [`Hospitality-Multi-agent-Architecture`](https://github.com/IvandeMurard/Hospitality-Multi-agent-Architecture) (README vision + inventaire honnête construit-vs-vision + MIT, **historique frais** — règle le risque résidu Q2-01 pour le contenu public) + cross-link `tacet-app`. **Non exécuté** (reste Étape 2) : scission stub public archivé / `aetherix` privé, migration `mesh-architecture.md` + ADRs cross-cutting, reusable workflows. Contenu méta-repo volontairement minimal tant que le ticket GitHub Support Q2-01 (HOS-304) n'est pas clos. Story : HOS-305 (Epic 16, HOS-300).

**Clôture AC4 — 11/08/2026 :** le lien du case study est corrigé. Vérifié en lisant la source publiée de `ivandemurard.com/aetherix` : deux liens vers le méta-repo, **zéro occurrence de `aetherix-hospitality-ai`**. L'avertissement porté par `CLAUDE.md` depuis le 21/07 est retiré. Étape 2 (scission des repos, HOS-246) reste non exécutée — inchangé.

### 26 — Anima : Guest Cognition Layer + confidence-weighted claims + Segment dual-scope + HiveMemory v2 (Learning Engine tier Mesh) (17/06/2026)

**Trigger :** post-hackathon Anima PoC (juin 2026) + revue architecture multi-parties (sessions 13/06–17/06) — trois évolutions par rapport à Décision #20.

**D1 — Rename Anima "Guest Cognition Layer" :** les quatre couches étaient toujours cognitives, pas juste du stockage. "Mémoire" sous-vend. Garde anti-god-object non-négociable : Anima = compréhension individuelle uniquement. Pas de policy, pas de fédération, pas de décision.

Séparation canonique : **Anima** (*Who is this guest?*) · **Hive/Mesh** (*What have we learned from similar situations?*) · **Aetherix/Orchestrateur** (*What should we do now?*).

**D2 — Confidence-weighted claims :** discipline de schema `ProfileSnapshot`, pas une couche. Champs `confidence / evidence_count / last_confirmed / decay_rate` sur toute claim Semantic. Terme "belief" rejeté (incompatible fiabilité produit). L'Orchestrateur pondère automatiquement les claims stales via ces champs.

**D3 — Segment double portée :** couche Segment = deux fonctions explicites : **Local** ("guests like this, at this hotel" — cohortes anonymisées propriété, nightly recompute) + **Hive prior** ("guests like this, across all network hotels" — agrégats fédérés, Phase 5). Similarité inter-hotels apprise (embeddings metadata hotel), pas hard-codée. Partial pooling hiérarchique + détection divergence (safety valve negative transfer). Shift 80/20 → 20/80 (Hive prior → Guest knowledge) au fil des séjours : analogue concierge expérimenté.

**D4 — Learning Engine tier Mesh séparé (Phase 5) + instrumentation Phase 4 :** policy/outcome learning = tier Mesh distinct, pas une 5e couche Anima. Dès Phase 4 : logger triple **de-identified** `(context-features, action, propensity, outcome)` à chaque décision Orchestrateur, dans un store séparé d'Anima (annoncé « personal-data-free by construction » — ⚠️ **claim contestée, non prouvée** : l'absence d'identifiant direct ne fait pas l'anonymat, analyse de ré-identification à produire, position par défaut **pseudonyme** en attendant — DPIA §10.2). `propensity` non-négociable pour off-policy evaluation future (IPW / doubly-robust). HiveMemory v2 (Phase 5) : partage de priors/policies appris, pas de données.

**D5 — Reframing moat :** le moat est la position dans la boucle act-and-measure (seul acteur qui agit + capture + attribue causalement + fédère), pas la taille du corpus.

**Vision validée (3 niveaux) :** "Comprend comme un humain" (Anima) · "Mesure comme une machine" (outcome capture) · "Apprend comme un réseau" (HiveMemory v2 / Learning Engine Phase 5).

**Story 3.5 (HOS-247) :** outcome-capture instrumentation — actionnable Phase 4, **scope Anima / décisions Orchestrateur** (projet Linear « Anima — Guest Context Node », parent HOS-230), donc derrière le gate DPIA de la Décision #20. Le pendant F&B (trace de politique à l'émission sur les recommandations Aetherix, personal-data-free) est porté séparément — voir `docs/planning/phase-3-sprint-plan.md` §Amendement 11/08. *(⚠️ Ce point a longtemps été référencé « HOS-246 » — cet identifiant désigne en réalité la migration multi-repo ADR-0010. Corrigé le 11/08/2026.)*

**Décisions ouvertes déplacées open-decisions.md :** politique exploration éthique · reward multi-objectif · méthode off-policy evaluation · floor k-anonymat Segment.

**Document canonique :** `docs/adr/0011-learning-engine-hive-v2.md`.

---

### 28 — PMS canonical schema : jurisprudence Provider étendue aux adapters PMS (amendement ADR-0006) (23/06/2026)

**Trigger :** analyse concurrentielle approfondie Grevon (`docs/_archive/competitive/grevon-analysis.md`, 23/06/2026) — leur produit **Kore** revendique explicitement *"a typical PMS API gives you raw data — rates as numbers, room types as codes. Kore goes further: it enriches, validates, and translates that data into a format LLMs actually understand"*, en amont de tous leurs agents (Pulse/Echo/Ops). Vérification du code Aetherix a confirmé un gap réel : `PMSAdapter` (`backend/app/services/pms_sync.py`) existe comme interface normalisée (`get_occupancy`, `get_revenue`, `get_historical_data`, `update_staffing_in_pms`), mais le pipeline forecast (`data_transformer.py`) la **contourne** — il lit les champs Apaleo bruts directement ("arrival", "adults", "children") pour construire le dataframe Prophet. Aucun adapter Mews n'existe encore (Phase 4, Décision #23 / HOS-186).

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

### 32 — Processus de calibration LLM-judge, pré-requis EVAL-6 (ADR-0007 §14) (30/07/2026)

**Trigger :** veille comparative — Airbnb Engineering, "Eval-Driven Development: Lessons from Evaluating GenAI at Scale" (medium.com/airbnb-engineering). Comparaison avec eval-by-design Aetherix : gap identifié — EVAL-6 (LLM-as-judge sur la qualité du reasoning, Phase 4) n'avait jamais de processus documenté pour faire confiance au juge avant de le déployer en autonomie. Détail comparatif complet : vault Obsidian `Veille/Veille_Tech_Stack.md` §JUL 20, 2026.

**Décision :** avant qu'EVAL-6 ne score en autonomie sur trafic échantillonné, le juge doit être calibré contre un jugement humain de référence :
- **Rubrique binaire** = miroir exact de la définition "bad output" déjà contractuelle dans `FAILURE_THRESHOLDS.md` (mauvaise attribution de cause / événement inventé / chiffre inventé) — le juge n'invente pas de nouveaux critères.
- **Golden set dédié** `eval/judge_calibration_set.jsonl` (schema distinct de `golden_dataset.jsonl` — texte-libre + verdict humain, pas input→valeur attendue), minimum 50 exemples incluant les 3 catégories d'échec.
- **Juge = Claude Sonnet via `LLMProvider`** (Décision #9), call séparé sans accès au prompt de génération original (évite le biais d'auto-cohérence). Escalade à Opus-juge si la calibration échoue de façon répétée.
- **Métrique = Cohen's kappa ≥ 0.8** (pas le % d'accord brut — corrige le déséquilibre de classe PASS/FAIL), sur 2 runs consécutifs avant d'autoriser le scoring autonome.
- **Recalibration** sur triggers explicites (changement prompt/modèle, swap provider) + trimestrielle systématique — pas un calendrier fixe seul.

**Pourquoi maintenant plutôt qu'au moment de construire EVAL-6** : coût de correction nul aujourd'hui (EVAL-6 n'est pas encore construit, Phase 4) — documenter le processus avant plutôt que de découvrir le gap une fois le juge déjà déployé sans calibration.

**Amendement 24/09/2026 (Décision #35) — juge d'une autre famille :** le juge n'appartient à la famille d'aucun générateur dont il note les sorties (primaire Claude **et** fallback Gemini exclus aujourd'hui → troisième famille, choisie par la calibration ; Mistral candidat le moins coûteux). Le kappa ≥ 0.8 reste la condition d'admission. Remplace le choix Sonnet et l'escalade Opus. Détail : ADR-0007 §14.5.

**Détail complet :** `docs/adr/0007-evaluation-by-design.md` §14. Amende `docs/planning/evaluation-by-design.md` (EVAL-6 acceptance criteria) et `eval/FAILURE_THRESHOLDS.md` (ligne LLM reasoning).

---

### 33 — Gate honnêteté métriques : taxonomie de statut + lecture du benchmark Recruit (01/08/2026)

**Trigger :** adversarial review externe (GPT, 20/07/2026), Critical C6 + Finding F13 + High Value H8 — confirmant l'audit interne du 07/07. Story 16.17 / HOS-318.

**Décision — trois volets :**

1. **Taxonomie de statut obligatoire.** Toute brique présentée, sur quelque surface que ce soit, porte une des cinq étiquettes **Built / Shadow-mode / Synthetic PoC / Design / Research**, définies une seule fois dans `docs/context/status-taxonomy.md`. `Built` signifie « le code tourne », **jamais** « quelqu'un s'en sert » — d'où une colonne *Preuve* obligatoire nommant la nature des données et le nombre d'utilisateurs réels. `Built (PoC)` est une formulation interdite : elle emprunte la crédibilité de *Built* à du *Synthetic PoC*. Le présent de l'indicatif est réservé à *Built* et *Shadow-mode*.

2. **Le MAPE 15,09 % est circulaire** (`generate_demo_data.py` fabrique les couverts à partir des régresseurs que Prophet consomme). Le chiffre n'est pas supprimé — il reste le gate interne de non-régression de la Décision #14 — mais tout usage non qualifié est un drift, détecté par **D7** de l'agent d'hygiène.

3. **Verdict Recruit (HOS-307 AC4) : PASS formel maintenu ET clause de pivot déclenchée volontairement.** Le PASS tient parce que la métrique (MAPE all-leads) était figée dans le script avant le run : la relire sur MdAPE après coup serait le biais que `protocole-de-preuve.md` interdit. Mais la règle des 5 pts est un proxy de valeur économique, et les −6,15 pts mesurent en réalité la robustesse aux jours à très faible fréquentation, pas un gain décisionnel — à J+1, sur la médiane, Prophet est **derrière** la naïve (28,54 % vs 27,94 %). Conséquence actée : le forecast cesse d'être présenté comme le différenciateur tant que §4.1 du protocole n'est pas passé sur données hôtelières réelles ; LightGBM global reste le moteur candidat Phase 4 ; Prophet est conservé pour l'explicabilité et la robustesse aux extrêmes.

**Amendement au protocole de preuve (§7, HOS-316) :** **WAPE** (Σ|erreur| / Σ réel) devient une métrique **reportée obligatoire** aux côtés de MdAPE et MAPE. La métrique de décision primaire reste **Δ MdAPE**, gelée le 29/07 en connaissance de cause — on ne change pas deux fois de métrique primaire, cela viderait le gel de sa valeur de preuve. Motif de l'ajout : WAPE est la seule des trois à mesurer l'erreur **en couverts**, donc convertible en heures de staff et en euros ; ajouter une métrique reportée ne peut pas constituer du cherry-picking, le §5.3 imposant déjà le reporting exhaustif. Amendement admissible car HOS-308 n'était pas démarrée à la date d'écriture.

**Documents canoniques :** `docs/context/status-taxonomy.md` (taxonomie) · `docs/context/audit-surfaces-publiques-2026-08.md` (état des surfaces + correctifs) · `docs/context/mape-benchmark.md` §Verdict AC4 (lecture du benchmark) · `docs/planning/protocole-de-preuve.md` §7 (amendement WAPE).

---

### 34 — Apaleo A2A : wait-and-see, Aetherix reste MCP standalone (30/07/2026)

**Trigger :** audit fonctionnel Trace Agent (HOS-285) + spike A2A (HOS-278), tous deux flaggés par la veille du 20-22/06 (W2 RE-FIRED) qui avait correctement identifié l'annonce A2A mais surestimé sa maturité en la traitant comme actionnable « avant le pilote M4 ». Audit livré 30/07/2026, détail complet `docs/context/apaleo-a2a-spike-decision.md` et `docs/competitive/apaleo-trace-agent-analysis.md`.

**Constat de l'audit (4 sources publiques)** : Trace Agent (partenariat THE FLAG) ne couvre ni F&B, ni couverts, ni staffing, ni prévision — tâches réelles = amenities/room setup/dietary requirements/celebrations, créées dans Sweeply. Agent **réactif** (transforme une intention déjà écrite), pas prédictif — différence de classe de problème avec Aetherix, pas de maturité. Sur le protocole lui-même : au 30/07/2026, `apaleo.dev` ne documente que deux chemins d'intégration tiers (Claude Plugin, MCP Server OAuth2 ~230 tools) — **aucune spec A2A, aucun modèle d'auth, aucun endpoint**. Toute mention A2A est au futur (*"third-party apps and agents will also be able to connect"*) — **la cible n'existait pas** au moment du spike.

**Décision :** Aetherix reste MCP standalone. Pas de branchement A2A tant que le protocole n'est pas une interface réelle. **Pourquoi attendre ne coûte rien** : Décision #19 (Aetherix = F&B execution node appelé par un orchestrateur externe) rend Aetherix structurellement déjà prêt pour un branchement A2A futur — aucune dette d'architecture à provisionner en attendant. Le risque d'un branchement précoce est lui bien réel et asymétrique : se brancher en A2A ferait disparaître le Daily Receipt derrière l'UI Copilot et commoditiserait la couche exécution — soit précisément le wedge produit.

**Reformulation du vecteur de menace (conséquence de l'audit, pas un sujet séparé)** : Apaleo ne construit pas les agents F&B, il fournit les rails — Agent Hub (marketplace vendor-neutral, monétisée) + Agent Factory (co-construction co-financée avec hôteliers/partenaires). Trace Agent a été bâti avec un tiers (Sweeply) en prototype 1 mois → production 2,5 mois. Le risque pertinent n'est donc plus *"Apaleo absorbe le F&B"* (hors de son modèle, Scénario C affaibli) mais *"un tiers publie un agent F&B sur Agent Hub en un trimestre"* — catégorie F&B vacante au 30/07 (agents cités : Email Booking, Corporate Sales, Digital Twin, CRM & Guest Experience). Nouveau trigger d'escalade ajouté au monitoring W2, indépendant du scope propre du Copilot.

**Conditions de bascule (rouvrir le spike A2A si l'une se déclenche)** : **B1** spec A2A publique sur `apaleo.dev` (protocole + auth + endpoint) · **B2** un tiers publie un agent F&B/covers/staffing via Agent Hub ou A2A (partagé avec le trigger W2 ci-dessus) · **B3** un design partner exige la livraison via Copilot · **B4** Apaleo conditionne le référencement Agent Hub à une connexion A2A. Sans trigger : **re-vérification trimestrielle, 30/10/2026.**

**Statut watchlist W2 (canari Apaleo Copilot scope F&B) :** dé-escaladé — cadence bi-hebdo → mensuelle (7 semaines sans nouveau signal F&B). Reste **ouvert** (`docs/context/open-decisions.md`), ce n'est pas le canari lui-même qui est tranché, seul le volet protocole A2A l'est. Détail complet et vivant : vault Obsidian `Veille/Veille_Watchlist_W2_Apaleo.md` (source de vérité pour tout futur update de ce canari, cf. Décision consolidation veille 10/07 — pas dans ce repo).

---

### 35 — Portabilité de modèle : tiers de capacité + qualification par le gate (24/09/2026)

**Trigger :** question PM 23/09/2026 — « l'architecture est tool-agnostic, comment la rendre model-agnostic ? ». L'audit du code a montré que Décision #9 ne donne que la portabilité **d'appel** : un identifiant de modèle Claude codé en dur dans `receipts.py` était transmis tel quel au fallback Gemini, qui le rejetait — le failover était mort pour le classifieur inbound (corrigé commit `0db9d41`). Motivations PM, dans l'ordre : (1) résilience ; (2) capacité d'adaptation aux évolutions des modèles ; (3) amélioration continue du produit ; (4) évaluation plus efficace.

**Définition retenue.** *Model-agnostic* = **tout modèle qui passe le gate d'éval est admissible, et le qualifier coûte un run de gate, pas un chantier.** Ce n'est **pas** du multi-modèle en production : Sonnet reste primaire (Décision #1 et verdict `llm-provider-strategy-review-2026-06.md` §3 inchangés). La portabilité est une capacité qu'on entretient, pas une diversification qu'on exerce.

**Périmètre :** toute l'architecture — règle de Mesh, pas seulement Aetherix. Aetherix l'applique ici ; les autres nœuds l'adoptent dans leur propre repo. Non vérifié à cette date : si et comment Tacet appelle un LLM.

**Quatre couches, une règle chacune :**

- **D1 — Appels : des tiers, jamais d'identifiant de modèle dans un service.** `LLMProvider.complete(tier="reasoning"|"fast")` ; chaque provider traduit le tier en son propre modèle (config `LLM_MODEL` / `LLM_FAST_MODEL` / `LLM_FALLBACK_MODEL` / `LLM_FALLBACK_FAST_MODEL`). Le tier traverse le failover (restaure l'intention de HOS-283 AC2). Tier inconnu → `ValueError`, jamais de routage silencieux. **Livré avec cette décision** (`backend/app/providers/base.py`).
- **D2 — Contrat de sortie : un schéma, pas du texte.** Toute sortie LLM consommée par du code est validée par un schéma Pydantic à la frontière du provider ; chaque adapter utilise le mécanisme natif de son fournisseur (tool use chez Claude, `response_schema` chez Gemini). Le parsing à la main de texte libre (`receipts.py` Pass 3, `anomaly_detection.py`) est la dette à résorber. Sans D2, une comparaison entre fournisseurs mesure le formatage, pas la qualité. **Design.**
- **D3 — Qualité : le gate juge l'admissibilité.** Le golden dataset tourne sur une matrice (provider × modèle) avec une baseline par couple ; la couche parser tourne sur un LLM réel, au moins sur le primaire et le fallback ; les couches recommendation et receipt (3 cas chacune au 24/09) sont enrichies avant toute comparaison. **Exception assumée à D1 : l'éval épingle des identifiants de modèle exacts**, parce qu'un run doit être reproductible et qu'un tier remappé change le sujet mesuré. **Design.**
- **D4 — Données : chaque vecteur sait quel modèle l'a produit.** Colonne `embedding_model` sur `fb_patterns` et `operational_memory` ; un changement de modèle d'embedding = double écriture puis bascule, jamais une réindexation en place. C'est le verrou le plus coûteux de l'architecture, avant le LLM. **Design.**

**D5 — Cycle de vie du golden dataset (planifié dès maintenant).** Trois zones : **noyau figé** (contrats métier : guardrails, format, refus — ne change pas, sert à comparer dans le temps) · **zone datée** (tout cas dont la vérité dépend du monde réel porte une date de revue) · **zone de croissance** (échecs de production promus en cas, HOS-287 — c'est ce qui empêche la saturation). Un cas ne se modifie jamais en place : on le retire et on en ajoute un. Le dataset porte une version de contenu distincte de `schema_version` ; les baselines sont indexées par (version du dataset × modèle). Toute version comparée est gelée avant lecture des résultats (protocole HOS-316). **Design.**

**Garde-fous :**
- **Qualifier automatiquement, oui ; promouvoir automatiquement, non.** Un modèle qui passe le gate devient *admissible* ; le passer en primaire reste une décision humaine (Décision #6, niveau (c) de `llm-provider-strategy-review-2026-06.md` §6).
- **Juge (Décision #32, amendée ici) :** le juge appartient à une famille de modèles différente de celle de tout générateur qu'il note — primaire et fallback compris, donc une troisième famille aujourd'hui (ADR-0007 §14.5). L'ancrage reste le kappa ≥ 0.8 contre labels humains, pas la récence ni la famille du modèle. Version du juge épinglée (D3).
- **Latence :** le gate matriciel tourne hors ligne (coût CI, zéro latence utilisateur). Aucun juge runtime sur un chemin MCP synchrone (budget < 500 ms, Décision #3) : asynchrone ou échantillonné, et sur les sorties à fort impact seulement.

**Rapport au gel Epic 16 (HOS-300) :** dérogation explicite, sign-off PM 24/09/2026, pas de nouvel ADR — le détail vit ici. Motif : D1 est un correctif de résilience ; D2 à D5 renforcent la **preuve** (le gate), pas le Mesh — ils servent l'objet même de l'Epic 16. Ce qui était gelé le reste (Anima, Learning Engine, Hive, Context Graph).

**Statut public :** « model-agnostic » se dit **Design** sur toute surface publique tant qu'aucun second fournisseur n'a passé le gate (D3). D1 seul ne suffit pas à passer en Built : une portabilité jamais évaluée reste une hypothèse.

**Falsifiable par :** un run du gate matriciel où le fallback échoue massivement sur des cas que le primaire passe. La portabilité réelle serait alors plus faible qu'annoncé — c'est l'information recherchée, pas un échec du projet.

---

### 36 — Gel Epic 16 levé pour le développement architecture — objectif reformulé portfolio (22/09/2026)

**Numérotation :** rédigée le 22/09/2026 (PR #260), numérotée #36 à l'intégration parce que la Décision #35 (portabilité de modèle, 24/09/2026) a été mergée avant. Conséquence : la « dérogation au gel Epic 16 » écrite dans la #35 devient sans objet, le gel de développement étant levé ici.

**Contexte.** Epic 16 (arbitrage 07/07/2026, `docs/planning/plan-90j-proof-visibility.md`) gelait toute extension du Mesh (Anima, Context Graph, HiveMemory/meta-learner ADR-0005) pendant 90 jours, sur la base de deux audits indépendants — interne (`docs/context/analyse-critique-2026-07.md`) et revue adverse externe GPT (20/07/2026) — concluant que l'architecture était en avance sur la preuve produit, avec un risque de crédibilité face à un acheteur/investisseur qui creuserait au-delà de la démo.

**Ce qui change.** Ivan précise (22/09/2026) que l'objectif réel du projet est la recherche d'emploi — renforcer son profil — pas une vente ni une levée. Le projet a été originellement conçu et poursuivi comme un projet entrepreneurial ; la pression de la recherche d'emploi fait maintenant réévaluer certains coûts pris pour ce cadrage-là. Le raisonnement du gel visait un acheteur/investisseur en diligence ; il ne s'applique pas de la même façon à un jury de recrutement, pour qui la profondeur technique démontrée — y compris sur des briques non déployées commercialement — est un signal positif, à condition que le statut réel reste honnêtement étiqueté (Décision #33).

**Décision.** Le gel Epic 16 sur le développement (code, conception, Orchestrateur avancé, meta-learner ADR-0005, Anima) est **levé**. La construction reprend sur données synthétiques/mock (cohérent Décision #11), avec obligation d'étiquetage honnête — Design / Synthetic PoC, jamais « Built » — Décision #33 inchangée et renforcée comme garde-fou explicite de cette reprise.

**Ce qui n'est PAS levé — le gate DPIA reste intégralement en vigueur.** La Décision #20 (gate Anima) ne bouge pas d'un mot : les 13 mesures bloquantes, la relecture juridique, le DPA à deux étages et l'interdiction de traiter des données guest réelles (`docs/context/dpia-anima-2026-08.md`) restent des conditions absolues avant toute mise en production. Ce qui reprend ici est un exercice de conception sur données synthétiques — hors du champ d'application matériel du RGPD (art. 3, aucune personne physique réelle concernée) — pas un système traitant de vraies données.

**Précision RGPD pour supports externes (portfolio, entretiens)** — formulation à reprendre telle quelle :
> « Ce projet a fait l'objet d'une analyse de conformité RGPD/CNIL complète avant toute extension (`docs/context/dpia-anima-2026-08.md`) : 6 des 9 critères EDPB déclenchant l'obligation de DPIA sont réunis, 13 mesures bloquantes identifiées et documentées avant toute mise en production réelle. Dans un contexte d'entreprise, avec un design-partner et des données guest réelles, cette analyse serait intégralement appliquée — relecture juridique, DPA à deux étages, mesures techniques — comme condition de mise en production, pas comme option. Le développement présenté ici est un exercice de conception sur données synthétiques, pas un système traitant des données personnelles réelles : il documente la pensée de conformité plutôt que de la contourner. »

**Ce qui reste vrai et n'est pas remis en cause.** Les deux audits (interne + externe) restent des constats valides **pour un contexte commercial**. S'il y a un jour un vrai design-partner, le raisonnement du gel (ne pas construire au-delà de la preuve avant un acheteur) redevient pertinent et devra être réappliqué à ce moment-là. Ce n'est pas une invalidation des audits, c'est un changement d'audience.

**Références** : `docs/planning/plan-90j-proof-visibility.md` §Amendement 22/09/2026 · `docs/context/dpia-anima-2026-08.md` (inchangé) · Décision #20 (gate, inchangée) · Décision #33 (taxonomie statut, garde-fou) · décision ouverte « Marché de lancement Anima EU vs non-EU » (`docs/context/open-decisions.md`, question distincte et toujours ouverte).

---

## Notes de maintenance

- Toute nouvelle décision architecturale : ajouter ligne d'index dans `CLAUDE.md` §Décisions architecturales + section H3 détaillée ici. Ne **JAMAIS** écrire le détail dans CLAUDE.md (rule budget ≤ 150 lignes).
- Si une décision devient obsolète, l'annoter `~~strikethrough~~` avec date de déprécation + note explicative. Ne pas supprimer (historique = asset).
- Cross-référence avec ADR : `docs/adr/000X-*.md` pour les décisions techniques formellement validées par session Architect. La décision architecturale ici = vue "fact" ; l'ADR = vue "rationale + alternatives + risques".

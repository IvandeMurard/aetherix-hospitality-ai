# Décisions ouvertes & archive

> **Périmètre :** décisions cross-cutting en débat (§Actives) + archive des décisions tranchées (§Resolved).
> **Convention CLAUDE.md :** 1 ligne d'index dans `CLAUDE.md` §Décisions ouvertes (statut + 1-ligne summary). Détail complet (rationale, alternatives, échéance, dépendances) ici.
> **Archive policy :** garder indéfiniment. Historique = asset (sales, investors, onboarding équipe).

---

## Actives

### Embedding strategy (pgvector vs Qdrant)

**Statut :** Open
**Trigger :** Phase 4 — multi-tenant + Hive Memory à scale
**Rationale :** pgvector reste suffisant < 50K patterns et < 50 hôtels. Phase 4 = re-évaluer si scale impose.
**Décision binaire :** rester pgvector OU migrer Qdrant managed.

### Pricing model (HOS-179 P3-5)

**Statut :** Open
**Trigger :** Décision après 90j data pilote design partner
**Tracking Linear :** HOS-179
**Anchors documentés :**
- Anthropic playbook *"AI for Hotel Owners"* L2-L3 = $500-$2,500/property/mois multi-modules
- SafouAI €200-400/mois (mono-purpose revenue pricing)

**Reco interne :** $500-$2,500/property/mois selon scope modules activés.

### Apaleo Copilot scope F&B (canari à surveiller)

**Statut :** Open — monitor récurrent perpétuel (pas décision closeable)
**Date documentation :** 01/06/2026
**Risque :** Apaleo confirmé first PMS MCP à ITB Berlin 2026 + démos booking apps ChatGPT natives. Si Copilot étend vers F&B forecasting / staffing → ferme la niche Aetherix sur le PMS bedrock (Décisions #1, #7, #21).
**Triggers à monitorer (mensuel) :**
- Annonces Apaleo Copilot
- Releases MCP tools liés covers / staff
- Embauches Apaleo *"operations AI"*

**Mitigation :**
- (a) Shipper pilote HOS-176 Phase 3 avant Q4 2026
- (b) Outreach Apaleo Marketplace pour position de complément
- (c) Accélérer Aetherix MCP v1 pour interop défensif

**État actuel :** ✅ Mapping livré (HOS-197, 2026-06-03) → [`docs/competitive/apaleo-mcp-mapping.md`](../competitive/apaleo-mcp-mapping.md) — 235 tools classés (5 consommés / 44 border-zone F&B / 186 inutilisés), leading indicators LI-1 → LI-5, reco MCP v1 = accélérer HOS-71 v1 (`get_operational_predictions`).

**Aussi présent dans :** `docs/context/monitoring-watchlist.md` W2 comme monitor récurrent perpétuel (cf. également W1 Conduit.ai depuis 04/06).

### Food waste tracking

**Statut :** Open
**Trigger :** Décision Phase 4 vs Phase 5 — à trancher avec PM
**Rationale :** ~25% gaspillage moyen en hôtellerie FR (ADEME/Accor), ~115g/couvert. La plupart des hôtels ne mesurent pas précisément → notre modèle crée cette donnée comme sous-produit du forecasting.
**Option A — Phase 4 :** feature ROI (€ gaspillés évités) calculé sur predicted prep vs actual covers post-service.
**Option B — Phase 5 :** intégrer POS data pour mesure précise vs juste predicted.

### Graphe de contexte — Phase 4 priority (04/06/2026)

**Statut :** Open
**Trigger :** Brief ADR-0008 futur. Pré-requis : cadrage POS tranché (impact schema).
**Origine :** Convergence thèse *"knowledge extraction = real bottleneck"* (Mira Murati Thinking Machines + Hyperspell + GBrain + projet personnel Lore) + débat session PM 04/06.

**Scope proposé :** Ajouter une couche graphe explicite au-dessus de pgvector existant.
- `hotel × event × weather × time × outcome`
- `senior × tacit_pattern × edge_case`

**Reco implémentation :** **Apache AGE** (extension Postgres-native sur Supabase, pas Neo4j séparé — cohérence Décision #3 pgvector).

**Effort estimé :** ~2 sprints Phase 4
- Schema 1-2j
- Migration backfill 3-5j
- Memory recall integration 5-7j
- Eval gate Décision #22 2-3j

**Unlocks :**
- Cohort matching ADR-0005 v2 (relations multi-dim vs cosine statique)
- Memory recall path-find (event A → reaction typique B dans cohorte)
- HiveMemory federated plus expressif
- Foundation Anima Phase 4 Guest Context Node
- Knowledge graph Lore-style (cf. `docs/context/vision-future.md` Aetherix Voice Phase 5+)

**Sources :** `docs/competitive/conduit-ai-analysis.md` + `memory/market_signals_2026Q2.md` section 04/06.

### Interaction model — event-driven Phase 4-5 (04/06/2026)

**Statut :** Open — pas urgent
**Trigger :** Brief ADR-0009 futur
**Origine :** Challenge Mira Murati (Thinking Machines, *"tandem bike"* + *"time-based interaction"*) → Aetherix actuel = fondamentalement turn-based (cron daily + reply WhatsApp batch).
**Reframing PM Ivan 04/06 :** Pour notre cas (PMS-data anticipation, pas conversation continue) **event-driven > time-based**.

**Architecture cible Phase 4-5 :**
- **(a)** PMS webhook ingestion (Apaleo push booking / cancellation events)
- **(b)** External signals subscription (weather alerts, event calendars)
- **(c)** Threshold-based interim alerts — e.g. cancellation wave à 14h → push reco interim, pas attendre 06h00 lendemain
- **(d)** Manager context channel bidirectionnel — manager peut pousser tacit context en cours de journée *("banquet privé off-system ce soir, ignorer surge")*

**Trade-off :** reactivity ↑ vs alerting fatigue + complexité state / events Redis.

**Décisions liées :** #15 *"luxury feel + daily cadence"* à re-évaluer dans ce frame. #6 *"no auto-actions"* reste compatible.

**Adopté immédiatement :** marketing snippet *"tandem bike"* (`docs/marketing/positioning-snippets.md` H-6, sections Tandem bike framing).

---

## Resolved (archive)

### [x] Federated Hive timing — RÉSOLU 04/06/2026

**Décision :** **OUI** — avancer la narrative communication à *"announced Phase 3 + shipped Phase 4"*.
**Date :** 04/06/2026 (correction post-confusion initiale "Non" → "OUI")
**Rationale :** Meuze.ai revendique federated learning live en production. Pour ne pas paraître en retard dans les sales conversations contre Meuze (et tout futur concurrent), communiquer Federated Hive comme roadmap publique dès Phase 3 (design doc public + LOO validation visible) tout en shippant prod en Phase 4. Coût annonce ~0, retire le talking point différenciant à Meuze.
**Application downstream :**
- README §Roadmap Phase 4 highlights : *"Federated HiveMemory ship (announced Phase 3)"*
- `docs/marketing/positioning-snippets.md` H-7 snippet (cohort intelligence + raw data sovereignty + Day-1 unlock)
- `docs/context/vision-future.md` Phase 4 narrative

### [x] Hive Memory scope Phase 3 — RÉSOLU 28/05/2026 → ADR-0005

Swap *"LLM persona generation"* → **cold-start meta-learner** ACCEPTÉ dans HOS-174 Track B. Architecture validée :
- Cohort matching hybride (hard rules + embedding cosine)
- Prior Prophet via `add_seasonality` + hyperparams calibrés
- Blending Bayesian model averaging (`n_eff_prior=30`, hard cutoff J+90)
- Gate runtime auto-disable si Day-7 MAPE > 25%

Nouvelle table `hotel_cohort_features` (coefficients agrégés, opt-in tenant). MCP tool `query_cohort_prior` ajouté. Validation pré-pilote : LOO sur 5 sandbox properties. LLM persona déplacé Phase 4. Détail → `docs/adr/0005-cold-start-meta-learner.md`. Action SM : amender HOS-174 (P3-7 amend + P3-7b/7c new, +8 pts).

### [x] PMS priorité live — RÉSOLU 17/05/2026

Apaleo prod Phase 3 (1 design partner, HOS-176). Mews déplacé Phase 4 + form partner à soumettre Day 1 Phase 3 (latence approval).

### [x] MCP server — RÉSOLU 19/04/2026

FastAPI endpoint dédié retenu — `/mcp/v0` mounted sur l'app principale (lifespan partagé, ADR D2). Shippé via PR #73. Sidecar process rejeté (coût ops, pas de bénéfice latence observé).

### [x] Apaleo MCP direct — RÉSOLU 31/03/2026

URL confirmée `https://mcp.apaleo.com/mcp/`, transport HTTP Streamable (SSE déprécié — notre `streamablehttp_client` est correct). Scope MCP activé sur le compte (code IIQJ). Auth OAuth2 bearer identique à la raw API. Activer via `POST /pms/sync?use_mcp=true` + `APALEO_MCP_SERVER_URL=https://mcp.apaleo.com/mcp/` dans `.env`.

### [x] ROI dashboard vs WhatsApp — RÉSOLU implicitement post-Phase 1

WhatsApp primary retenu (cf. Décision #15 OQ1 — Receipts channel = WhatsApp + email opt-in). Dashboard différé Phase 3+ si adoption le justifie.

---

## KPIs à instrumenter (référence — voir aussi CLAUDE.md §KPI framework)

- `tool_success_rate` > 99.5%
- `p95_latency` < 500ms
- `schema_stability` = 0 breaking changes par sprint
- `agent_retry_rate` < 1%
- `MAPE` couverts < 15%
- `recommendation_acceptance_rate` (alerte si < 30%)
- `labor_cost_variance` cible –3% à –8%

---

## Notes de maintenance

- **Update protocol** : décision tranchée → déplacer de §Actives à §Resolved avec date + rationale. **Ne pas supprimer.**
- **Index CLAUDE.md** : pour chaque décision active = 1 ligne dans `CLAUDE.md` §Décisions ouvertes (statut + 1-ligne summary). Le détail (alternatives, échéance, dépendances, sources) vit ici.
- **Cross-références** : ADR (`docs/adr/`) pour décisions techniques validées. Watchlist (`docs/context/monitoring-watchlist.md`) pour monitors récurrents perpétuels (Conduit.ai, Apaleo Copilot, etc.).

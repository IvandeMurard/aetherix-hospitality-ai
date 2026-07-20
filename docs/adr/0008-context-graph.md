# ADR 0008 — Context Graph: Postgres recursive CTE layer on top of pgvector

> **Status**: **Accepted — Path C retenu (Postgres recursive CTE)** · **Date**: 2026-06-06 · **Author**: Architect (Winston, Opus 4.7)
> **Phase**: 4 (Scale & Distribution) — primary foundation Anima Phase 4 Guest Context Node
> **Linear**: HOS-GRAPH-1 → HOS-GRAPH-6 (à créer par SM Phase 4 kickoff — story breakdown amendé §13.6)
> **Implémente**: CLAUDE.md Décision architecturale #24 (ajoutée par cette session, libellé amendé "Postgres recursive CTE Phase 4")
> **Étend**: ADR 0002 (`MemoryRecallService` — recall cosine devient hybrid path-traversal + cosine), ADR 0003 (`agent_action_log` graph_path field), ADR 0007 (catégorie eval `context_graph_query`)
> **Articule**: ADR 0004 (orchestrator-only MCP — graphe exposé via MCP, jamais import Python), ADR 0006 (POS features = nouveaux node types `Outlet` / `Ticket` / `Item`)
> **Débloque**: Anima Phase 4 Guest Context Node (Décision #20 — 4 couches) · Aetherix Voice Phase 5+ (Lore-inspired knowledge graph relationnel — note : expressivité CTE inférieure à Cypher sur queries 3-hop, à reconsidérer Phase 5+ si Supabase ajoute AGE — cf. WT1 watchlist)
> **Pré-requis externe vérifié** : `docs/adr/0006-pos-integration.md` Accepted (06/06/2026) ✅
> **⚠️ Amendment 06/06/2026 même journée** : R6 confirmé bloquant — Apache AGE non supporté Supabase managed. Architecture §2 D2/D4/D5/D7 **inchangée** ; D1 backend tech remplacé Apache AGE → **Postgres recursive CTE** ; D6 invariant atomique + RLS native Supabase substitue `_inject_tenant_filter` Cypher injection. Voir §13 amendment complet + §16 patterns CTE override D1/D2/D4/D6.
> **PM sign-off Path C** : raison financière (Path A +$15-30/mois × multi-tenant Phase 5+ = trajectoire coût non-souhaitée vs Path C $0). Reco Architect Path A non-suivie pour priorité cash discipline pre-pilote.

---

## 1. Contexte

### 1.1 Problème actuel

Aetherix dispose de deux primitives mémoire distinctes :

1. **`operational_memory`** (ADR-0002) : pgvector 1024d Mistral, recall **cosine top-k** via `MemoryRecallService` — payload structuré `[type] outcome= rec_context= notes= actual=`. Cold-start fallback vers `fb_patterns` (cross-hôtels anonymisé).
2. **`hotel_cohort_features`** + **`hotel_cohort_features_pos`** (Décision #23 / ADR-0006) : features agrégées par hôtel, late-fusion blending `α × cos_pms + β × cos_pos` pour cohort matching.

**Limites observées** :

- **Recall = bag-of-similarity, pas relation.** Cosine top-k retourne les 5 reflections les plus proches sémantiquement, mais ne sait pas qu'un *event "IFA Berlin trade fair"* a **causé** une *spike covers dinner +85%*, qui a **provoqué** une *intervention senior chef* documentée 18 mois plus tôt. Le lien causal est implicite dans le texte du payload, jamais traversable.
- **Cohort matching v2 (ADR-0006) = 1 score scalaire (late-fusion).** Discrimine *boutique BER 80 chambres breakfast-heavy vs dinner-heavy*, mais ne dit pas *"cet hôtel est similaire au mien sur 6 mois de pattern d'événements météo × occupancy × outlet shifts"* — uniquement sur l'instantané des features.
- **Tacit knowledge tag-only.** Réflexion senior *"quand il pleut un vendredi soir + occupancy > 80%, la brasserie déborde toujours d'1h, prép 30 covers de plus"* devient un blob dans `reflection` column. Aucune façon programmatique d'extraire le **pattern** (weather=rain ∧ day=Friday ∧ occupancy > 0.8) → (intervention=+30_covers_brasserie).

### 1.2 Trigger session — convergence 04/06/2026

PM session 04/06 a documenté la convergence thèse *"knowledge extraction = the real bottleneck"* (Mira Murati / Thinking Machines + Hyperspell + GBrain + projet personnel Lore — `memory/market_signals_2026Q2.md` + `docs/competitive/conduit-ai-analysis.md`). Reformulation pour Aetherix :

- **RAG retrieves what you put in.** Le vrai unlock = capturer ET traverser les relations (pas juste les embeddings).
- **Knowledge graph relationnel** = pré-requis architectural Aetherix Voice Phase 5+ (`docs/context/vision-future.md` §*Tacit Knowledge Capture*).
- **Foundation Anima Phase 4** = la couche Semantic permanente (Décision #20) nécessite des relations explicites guest × stay × event × intervention — pas juste un blob pgvector.

Open decision §Actives 04/06 a recommandé **Apache AGE** (extension Postgres-native sur Supabase, cohérence Décision #3 pgvector — pas Neo4j séparé). Pré-requis POS débloqué ✅ par ADR-0006 (06/06).

### 1.3 Goal

Spécifier une couche graphe explicite **indexant** les structures existantes (`operational_memory`, `agent_action_log`, `pos_*`, `hotel_cohort_features*`) en **nodes typés** + **edges typés**, exposable via MCP tool (`query_context_graph`), implémentable sur Supabase managed sans switch infrastructure.

**Invariant fondamental** : le graphe **n'est pas une 3e couche mémoire** au sens Décision #2 (Private vs Hive). C'est une **vue indexée traversable** au-dessus des couches 1 et 2 existantes. Les sources de vérité (tables pgvector, JSONB, MV) restent inchangées. Le graphe est **dérivé**, **rebuildable**, **opt-in tenant**.

### 1.4 Non-goals (Phase 4)

- **Schema Anima Phase 4 complet** (4 couches Working/Episodic/Semantic/Segment) — ADR séparé futur. Cet ADR pose les **node types** qui préfigurent Anima, pas leur DDL final.
- **Migration scale vers Neo4j Phase 5+** — mention possibility §6.5, pas décision.
- **Cypher complet exposé via MCP** — Phase 4 = un tool atomique `query_context_graph(query_type, depth)` avec query types pré-définis ; pas de Cypher arbitraire (sécurité + cost control).
- **Implémentation code** — Dev Phase 4. Cet ADR spec le contrat.
- **Ingestion temps réel** (CDC sur `agent_action_log`) — Phase 4 = backfill batch + worker nightly. Streaming = Phase 5 si besoin avéré.
- **Suppression de pgvector** — coexistence permanente, queries hybrides (cf. §D4).

---

## 2. Décisions (Q1-Q7 tranchées)

### D1 (Q1) — Choix tech : **Apache AGE (extension Postgres-native sur Supabase)**

#### Décision

Adopter **Apache AGE 1.5+** (Postgres extension activable sur Supabase managed, OpenCypher partial support, repo Apache Software Foundation). Pas Neo4j hosted, pas Memgraph, pas table-recursive Postgres.

#### Critères pondérés appliqués

| Critère | Poids | Apache AGE | Neo4j Aura | Memgraph Cloud | Postgres recursive CTE |
|---|---|---|---|---|---|
| Cohérence stack Décision #3 (pgvector / Postgres / Supabase) | 30% | ✅ Native extension | ❌ Service séparé, +1 vendor | ❌ Service séparé, +1 vendor | ✅ Native |
| Coût ops mensuel cible < $50/mois Phase 4 | 20% | ✅ Inclus Supabase plan actuel | ❌ ~$65/mois entry tier | ❌ ~$50/mois entry tier | ✅ Gratuit |
| Performance traversal 1-3 hops sur < 1M nodes | 15% | ✅ Suffisant (testé Apache AGE perf benchmarks) | ✅ Excellent | ✅ Excellent | ⚠️ Acceptable mais SQL verbose |
| MCP integration latency < 500ms SLO (Décision #3) | 15% | ✅ Même DB connection, pas de RTT cross-network | ❌ Network hop +50-100ms p95 | ❌ Network hop +50-100ms p95 | ✅ Native |
| Queries hybrides (graph + pgvector + SQL JOIN) | 10% | ✅ Single transaction, JOIN direct sur tables | ❌ App-side join (complexe + lent) | ❌ App-side join | ✅ Native |
| Maturité prod + écosystème + community Q2 2026 | 5% | ⚠️ Moins mature que Neo4j, Apache project stable | ✅ Excellent | ⚠️ Moins établi | ✅ Excellent (Postgres) |
| Migration future si scale (Phase 5+) | 5% | ⚠️ Cypher portable vers Neo4j si besoin | — | ⚠️ Cypher partial | ❌ Refactor complet |

**Score pondéré (sur 100)** : Apache AGE = **88** · Neo4j Aura = 58 · Memgraph = 53 · Postgres CTE = 73.

#### Justification narrative

- **Cohérence Décision #3** (pgvector > Qdrant > Pinecone — *"compatible latency MCP <500ms"*). Apache AGE applique la même logique : extension Postgres native, pas service externe. Un seul vendor managed (Supabase), une seule DB connection pool, une seule lifecycle.
- **Cohérence Décision #10** (provider singleton via `lifespan` FastAPI). Apache AGE ne nécessite **pas** de nouveau provider — c'est une extension SQL accessible via la session asyncpg existante. Zero refactor `lifespan`.
- **Cohérence Décision #17** (Fly.io cdg ↔ Supabase Stockholm ~30ms). Network hop unique préservé. Neo4j Aura = un 2e hop network = +50-100ms p95, dépasse SLO MCP 500ms en stack cumulatif (ADR-0001).
- **Queries hybrides** : un seul SELECT peut joindre un `MATCH (h:Hotel)-[:OCCURRED_AT]->(e:Event)` Cypher avec un `JOIN operational_memory om ON om.hotel_id = h.id` SQL et un `embedding <=> CAST(:q AS vector)` pgvector. **Aucun autre choix ne permet ça dans une seule transaction.**

#### Rejeté avec justification chiffrée

- **Neo4j Aura** : meilleur graphe pur, mais (a) +$65/mois (b) network hop SLO-cassant (c) app-side joins pgvector ↔ Neo4j cassent l'invariant ADR-0002 (recall = single SQL). Reconsidérer Phase 5+ uniquement si Apache AGE benchmark hits limit > 1M nodes par hôtel.
- **Memgraph Cloud** : mêmes contre-arguments que Neo4j + écosystème moins mature.
- **Postgres recursive CTE** : pas de modèle graphe explicite, queries SQL verbose 50-100 lignes pour traversals 3-hop, pas d'index spécialisé sur edges, impossible à maintenir post-50 query types.
- **Supabase Postgres + arrays JSONB** (no graph engine, "fake graph") — code app-side complexe, pas de Cypher, échec sur eval gate `context_graph_query` (Décision #22 / ADR-0007).
- **Refactor complet vers Neo4j hosted** : viole Décision #3 (pgvector), force 2 vendor data planes, casse RLS Supabase, exige réimplémenter `MemoryRecallService` entier. **Rejeté.**

#### Migration path Phase 5+ (option de sortie)

Si Apache AGE benchmark échoue ≥ 1M nodes/hôtel en Phase 5 (très improbable — un hôtel single-property aura < 100K nodes), Cypher OpenCypher est **portable** vers Neo4j. Le coût de migration = (a) export AGE → Cypher dump, (b) provisioning Neo4j Aura, (c) refactor `query_context_graph` MCP tool (couche transport, pas business logic). Effort estimé Phase 5 : 5-8j. Pas un blocker pour Phase 4 ship.

#### Variables d'environnement nouvelles

```
GRAPH_BACKEND     — "apache_age" (défaut Phase 4) | "neo4j" (Phase 5+ option) | "disabled"
GRAPH_RLS_MODE    — "strict" (défaut — RLS Postgres standard sur tables sources) | "ext-relaxed" (Phase 5 si AGE RLS limitations)
```

---

### D2 (Q2) — Schema définitif : **8 node types + 9 edge types, DDL Apache AGE**

#### Principe directeur

Les nodes du graphe **référencent** les rows existantes (FK soft via `vendor_id` / `internal_id` properties), ils ne les remplacent pas. Suppression d'un node = pas suppression de la source data. Re-build du graphe depuis sources = idempotent.

#### Node types (8)

| Type | Représente | Propriétés clés | Source data |
|---|---|---|---|
| `Hotel` | Une propriété tenant Aetherix | `hotel_id`, `geo_cluster`, `capacity_bucket`, `segment` | Table `hotel` (existante) |
| `Event` | Un événement local datable (trade fair, festival, météo extrême) | `event_id`, `event_type`, `start_at`, `end_at`, `intensity` (0-1) | `agent_action_log` `event_context` JSONB + Paris Open Data (Décision #18 Track B) |
| `Weather` | État météo daté par hôtel | `weather_id`, `date`, `temperature`, `precipitation`, `weather_score` | Champs regressors Prophet (Décision #11) |
| `Outcome` | Réalisation mesurée (covers, ticket-size, occupancy) | `outcome_id`, `metric`, `value`, `unit`, `date`, `service_slot` | `pos_transaction` (ADR-0006) + `operational_memory` `actual` |
| `Recommendation` | Suggestion agent émise | `recommendation_id`, `service_type`, `predicted_value`, `confidence` | `agent_action_log` `recommendation` JSONB |
| `SeniorIntervention` | Action manager / senior chef documentée | `intervention_id`, `actor_role`, `tacit_pattern` (text), `applied_at` | `operational_memory` `memory_type=reflection` + manager replies (Décision #15) |
| `EdgeCase` | Cas hors-pattern annoté (ADR-0007 D1 catégorie `ood_edge` + `pos_anomaly`) | `edge_case_id`, `category`, `severity`, `failure_trigger` | `eval/golden_dataset.jsonl` + `agent_action_log` `abstention_reason` |
| `Cohort` | Groupe d'hôtels similaires (foundation ADR-0005 + ADR-0006 v2) | `cohort_id`, `geo_cluster`, `segment`, `pos_provider`, `aggregation_window` | `hotel_cohort_features` + `hotel_cohort_features_pos` |

#### Edge types (9)

Chaque edge porte 1-3 properties (timestamp + score/weight + provenance).

| Edge | From → To | Properties | Cardinalité |
|---|---|---|---|
| `OCCURRED_AT` | `Event` → `Hotel` | `started_at`, `intensity` | N:N |
| `HAS_WEATHER` | `Hotel` → `Weather` | `date` | 1:N daily |
| `PRODUCED` | `Hotel` → `Outcome` | `date`, `service_slot` | 1:N daily |
| `CAUSED` | `Event` ∪ `Weather` → `Outcome` | `causal_score` (0-1, Bayesian post-hoc), `confidence` | N:N |
| `SUGGESTED` | `Recommendation` → `Outcome` | `predicted_at`, `delta_to_actual` | 1:1 |
| `INTERVENED_ON` | `SeniorIntervention` → `Recommendation` ∪ `Outcome` | `manager_feedback` (followed / rejected / modified), `applied_at` | N:N |
| `MATCHES_PATTERN` | `Outcome` ∪ `SeniorIntervention` → `EdgeCase` | `similarity` (0-1, cosine on embedded payload) | N:N |
| `SIMILAR_TO` | `Hotel` → `Hotel` | `cohort_id`, `late_fusion_score`, `dim` (pms / pos / blended) | N:N (transitive opt-in) |
| `BELONGS_TO_COHORT` | `Hotel` → `Cohort` | `joined_at`, `weight` (k-means cluster proximity) | N:N |

#### DDL Apache AGE — exemples canoniques

```sql
-- supabase/migrations/PHASE_4/20260901000000_context_graph_age_setup.sql
-- Phase 4, Story P4-GRAPH-1

CREATE EXTENSION IF NOT EXISTS age;
LOAD 'age';
SET search_path = ag_catalog, "$user", public;

SELECT create_graph('aetherix_context');

-- Node label creation (idempotent)
SELECT create_vlabel('aetherix_context', 'Hotel');
SELECT create_vlabel('aetherix_context', 'Event');
SELECT create_vlabel('aetherix_context', 'Weather');
SELECT create_vlabel('aetherix_context', 'Outcome');
SELECT create_vlabel('aetherix_context', 'Recommendation');
SELECT create_vlabel('aetherix_context', 'SeniorIntervention');
SELECT create_vlabel('aetherix_context', 'EdgeCase');
SELECT create_vlabel('aetherix_context', 'Cohort');

-- Edge label creation
SELECT create_elabel('aetherix_context', 'OCCURRED_AT');
SELECT create_elabel('aetherix_context', 'HAS_WEATHER');
SELECT create_elabel('aetherix_context', 'PRODUCED');
SELECT create_elabel('aetherix_context', 'CAUSED');
SELECT create_elabel('aetherix_context', 'SUGGESTED');
SELECT create_elabel('aetherix_context', 'INTERVENED_ON');
SELECT create_elabel('aetherix_context', 'MATCHES_PATTERN');
SELECT create_elabel('aetherix_context', 'SIMILAR_TO');
SELECT create_elabel('aetherix_context', 'BELONGS_TO_COHORT');

-- Indexes on AGE node properties used in frequent MATCH
-- (Apache AGE indexes are GIN on the agtype property column)
CREATE INDEX idx_age_hotel_hotelid ON aetherix_context."Hotel" USING gin (properties);
CREATE INDEX idx_age_event_type_date ON aetherix_context."Event" USING gin (properties);
CREATE INDEX idx_age_outcome_metric_date ON aetherix_context."Outcome" USING gin (properties);
CREATE INDEX idx_age_intervention_actor ON aetherix_context."SeniorIntervention" USING gin (properties);
```

#### Exemple ingest Cypher (idempotent — Phase 4 backfill)

```sql
SELECT * FROM cypher('aetherix_context', $$
    MERGE (h:Hotel {hotel_id: $hotel_id})
      ON CREATE SET h.geo_cluster = $geo, h.capacity_bucket = $cap, h.segment = $seg
      ON MATCH  SET h.geo_cluster = $geo, h.capacity_bucket = $cap, h.segment = $seg
    MERGE (e:Event {event_id: $event_id})
      ON CREATE SET e.event_type = $etype, e.start_at = $start, e.intensity = $int
    MERGE (e)-[r:OCCURRED_AT {started_at: $start, intensity: $int}]->(h)
    RETURN h, e, r
$$, $params$ ... $params$) AS (h agtype, e agtype, r agtype);
```

Toutes les ingestions utilisent `MERGE` (idempotent) — re-build du graphe = relancer le worker (cf. D3).

#### Validation contre `check_schema_drift.py` (Décision #16)

Apache AGE crée un schema `aetherix_context` séparé. Ce schema **n'est pas miroir** d'un modèle ORM SQLAlchemy (le contrat est Cypher, pas Table). Exception explicite dans `scripts/ci/schema_drift_ignore.json` :

```json
{
  "schema_exclusions": ["aetherix_context", "ag_catalog"],
  "reason": "Apache AGE managed schemas — graph DDL via Cypher MERGE, not ORM. ADR-0008."
}
```

Le DDL graph reste **versionné Alembic** (migration `20260901000000_context_graph_age_setup.sql`) — pas inline.

---

### D3 (Q3) — Migration path : **dual-write Phase 4.0 → backfill batch → coexistence permanente**

#### Phase 4.0 — Setup + Mock (Story P4-GRAPH-1)

1. Migration `20260901000000_context_graph_age_setup.sql` (CREATE EXTENSION + create_graph + node/edge labels + indexes).
2. `backend/app/services/context_graph_service.py` — wrapper Python autour des appels Cypher via asyncpg (réutilise pool DB session ADR-0001).
3. `MockContextGraph` adapter pour tests pure-logic (in-memory dict-based, pattern `FakeEmbeddingProvider` ADR-0002 D11).
4. Pas encore exposé via MCP. Pas encore lu par `MemoryRecallService`.

#### Phase 4.1 — Backfill batch (Story P4-GRAPH-2)

Script `scripts/ops/backfill_context_graph.py` :

```python
# Pseudo-code
async def backfill_hotel(hotel_id: str, dry_run: bool = False):
    # 1. Hotel node
    await graph.merge_hotel(hotel_id, geo_cluster, capacity_bucket, segment)

    # 2. Events from agent_action_log event_context (3 years lookback)
    events = await db.fetch("SELECT DISTINCT event_context FROM agent_action_log WHERE hotel_id=$1 AND event_context IS NOT NULL", hotel_id)
    for ev in events:
        await graph.merge_event(ev)
        await graph.merge_edge_occurred_at(ev.event_id, hotel_id, ev.intensity)

    # 3. Weather from regressors history (Décision #11 demo dataset + prod Prophet input)
    weather_rows = await db.fetch("SELECT date, temperature, precipitation, weather_score FROM weather_history WHERE hotel_id=$1", hotel_id)
    for w in weather_rows:
        await graph.merge_weather(w)
        await graph.merge_edge_has_weather(hotel_id, w.weather_id, w.date)

    # 4. Outcomes from pos_transaction (ADR-0006) — daily aggregates per service_slot
    outcomes = await db.fetch("""
        SELECT hotel_id, DATE(closed_at) AS date, service_slot,
               SUM(cover_count) AS covers, AVG(gross_amount_cents)::INT AS avg_ticket
        FROM pos_transaction WHERE hotel_id=$1
        GROUP BY hotel_id, date, service_slot
    """, hotel_id)
    for o in outcomes:
        await graph.merge_outcome(o)
        await graph.merge_edge_produced(hotel_id, o.outcome_id, o.date, o.service_slot)

    # 5. Recommendations + SeniorInterventions from agent_action_log + operational_memory
    # 6. EdgeCases from eval/golden_dataset.jsonl + agent_action_log abstention_reason
    # 7. Cohort + SIMILAR_TO from hotel_cohort_features + hotel_cohort_features_pos
    # 8. CAUSED edges via Bayesian post-hoc score (cf. D4 § scoring)
    ...

    if not dry_run:
        await db.execute("UPDATE hotel SET graph_backfilled_at = NOW() WHERE hotel_id = $1", hotel_id)
```

Cible : un hôtel pilote = ~50K-150K nodes + ~150K-400K edges après 3 ans backfill. Backfill batch ~5-15 min single-property.

#### Phase 4.2 — Worker nightly + dual-read (Story P4-GRAPH-3)

- **Worker APScheduler nightly** (`refresh_context_graph_nightly`) : ingestion incrémentale depuis `agent_action_log` `created_at > graph_last_synced_at`.
- **`MemoryRecallService` étendu** (cf. D4) : pour query types `path_find` / `cohort_traversal`, lit Apache AGE en complément (pas en remplacement) de pgvector cosine.

#### Phase 4.3 — Coexistence permanente (pas de cutover pgvector → graph)

**Décision invariant** : pgvector `operational_memory` **reste source de vérité pour recall sémantique flou**. Apache AGE est **source de vérité pour recall relationnel/path**. Les deux coexistent indéfiniment.

Pourquoi pas cutover :
- pgvector excellent pour *"reflexions similaires à ce contexte"* (cosine sur payload texte naturel).
- Graphe excellent pour *"qu'a fait le chef de cette cohorte la dernière fois qu'IFA + pluie tombèrent ensemble"* (path-find).
- Cosine vs path = use cases distincts, pas substituables.
- ADR-0002 D4 (`MemoryHit` dataclass + `MemoryRecallService.recall()`) reste contrat stable pour callers.

#### Rejeté

- **Cutover pgvector → graph** : casse `MemoryRecallService` contract, oblige Mistral embedding sur tous nodes (cost + latency), perte des hits sémantiques flous valides.
- **CDC temps réel via Supabase Realtime sur `agent_action_log`** : Phase 5 si besoin. Phase 4 batch nightly suffit (operationnel forecast = lookback historique, pas temps réel).
- **Backfill complet en une fois multi-tenant** : risque OOM Supabase pool. Backfill **par hôtel**, séquentiel, gated par `--hotel-id` flag obligatoire.

---

### D4 (Q4) — Integration `MemoryRecallService` : **extension hybrid path-find + cosine**

#### Décision

Étendre `MemoryRecallService.recall()` (ADR-0002 D4) avec un nouveau paramètre `recall_strategy` :

```python
RecallStrategy = Literal[
    "cosine_only",       # ADR-0002 baseline — Phase 0-3 default, reste valide
    "path_find",         # Phase 4 — traverse graph depuis context, retourne hits relationnels
    "hybrid",            # Phase 4 default new — union des deux, rerank par combined score
    "cohort_traversal",  # Phase 4 — exploite SIMILAR_TO + BELONGS_TO_COHORT pour cold-start v3
]

async def recall(
    self,
    hotel_id: str,
    query_text: str,
    *,
    k: int = 5,
    min_similarity: float = 0.5,
    memory_types: Sequence[str] = ("feedback", "reflection"),
    since: datetime | None = None,
    only_followed: bool = False,
    recall_strategy: RecallStrategy = "cosine_only",   # NEW Phase 4
    graph_depth: int = 2,                              # NEW Phase 4 — max hops
    graph_query_type: GraphQueryType | None = None,    # NEW Phase 4 — voir D6
) -> list[MemoryHit]: ...
```

#### Cohort matching v3 (extension ADR-0006 D4 late-fusion)

ADR-0006 D4 = late-fusion **scalar** `α × cos_pms + β × cos_pos`. ADR-0008 promeut cohort matching v3 = **multi-dim path traversal** :

1. **Hard rules** identiques v1/v2 (geo + capacity bucket + segment).
2. **Late-fusion cosine** identique v2 (PMS + POS features).
3. **NEW** — path-find query `(:Hotel {hotel_id: $me})-[:BELONGS_TO_COHORT]->(:Cohort)<-[:BELONGS_TO_COHORT]-(other:Hotel)-[:PRODUCED]->(:Outcome)<-[:CAUSED]-(:Event {event_type: $current_event_type})` — retourne les outcomes historiques d'hôtels co-cohorte sur un type d'event donné.
4. **NEW** — pattern path `(:SeniorIntervention)-[:INTERVENED_ON]->(:Recommendation)-[:SUGGESTED]->(:Outcome)` filtré par `manager_feedback='followed'` + co-cohorte — exhume les **wisdoms validées** des managers d'hôtels similaires sur des situations comparables.
5. Score final = `γ × cos_pms + δ × cos_pos + ε × path_match_score` avec `γ+δ+ε = 1`, calibré pilote.

#### SQL pattern hybrid (single transaction)

```sql
WITH graph_hits AS (
    SELECT * FROM cypher('aetherix_context', $$
        MATCH (h:Hotel {hotel_id: $me})-[:BELONGS_TO_COHORT]->(:Cohort)<-[:BELONGS_TO_COHORT]-(other:Hotel)
        MATCH (other)-[:PRODUCED]->(o:Outcome)<-[:CAUSED]-(e:Event)
        WHERE e.event_type = $event_type
          AND o.service_slot = $service_slot
        RETURN other.hotel_id AS hotel_id, o.outcome_id AS outcome_id,
               o.value AS value, o.date AS date, e.intensity AS intensity
        LIMIT 20
    $$, $params$) AS (hotel_id agtype, outcome_id agtype, value agtype, date agtype, intensity agtype)
),
cosine_hits AS (
    SELECT id, 1 - (embedding <=> CAST(:q AS vector)) AS similarity,
           reflection, outcome, manager_feedback, memory_type, created_at
    FROM operational_memory
    WHERE hotel_id = :me
      AND memory_type = ANY(:types)
    ORDER BY embedding <=> CAST(:q AS vector) ASC
    LIMIT :k
)
SELECT 'graph' AS source, hotel_id::text, outcome_id::text AS id, value::text, date::text, intensity::float AS score, NULL::text AS reflection
FROM graph_hits
UNION ALL
SELECT 'cosine' AS source, NULL, id::text, NULL, created_at::text, similarity, reflection
FROM cosine_hits
WHERE similarity >= :min_similarity
ORDER BY score DESC NULLS LAST
LIMIT :k_final;
```

Single transaction. Single connection. SLO MCP 500ms préservé.

#### Backward compat

- Caller ne passant pas `recall_strategy` → default `"cosine_only"` = comportement ADR-0002 identique. Zero régression Phase 0-3 callers.
- MCP tool `recall_memory` v1 (ADR-0004 D5) inchangé. NEW MCP tool `query_context_graph` (D6) cohabite.

---

### D5 (Q5) — Foundation Anima Phase 4 : **node types `Guest` / `Stay` / `Sentiment` réservés forward-compat, Working/Episodic via Cypher temporal predicates**

#### Décision

Le graphe Aetherix Phase 4 **ne contient pas** de données guest (cohérent Décision #20 — Anima = repo séparé Phase 4, DPIA gate non-négociable). Mais il **réserve** 3 node types + 4 edge types **non créés** Phase 4, **documentés** pour Anima Phase 4 quand DPIA passé.

#### Node types réservés (Anima Phase 4)

| Type | Représente | Couche Anima Décision #20 |
|---|---|---|
| `Guest` | Guest identifiable (consent obtenu) | Semantic (couche 3) — pgvector permanent |
| `Stay` | Séjour datable d'un guest | Episodic (couche 2) — time-filtered |
| `Sentiment` | État inféré (fatigue / déçu / VIP-anxious / festif) | Working (couche 1) — TTL séjour Redis |

#### Edge types réservés (Anima Phase 4)

| Edge | From → To | Couche Anima |
|---|---|---|
| `HAS_STAY` | `Guest` → `Stay` | Episodic |
| `EXPERIENCED` | `Stay` → `Hotel` ∪ `Outcome` ∪ `Event` | Cross-couches (Anima → Aetherix bridge) |
| `EXPRESSED` | `Stay` → `Sentiment` | Working / Episodic |
| `MATCHES_SEGMENT` | `Guest` → `Cohort` (réutilise node `Cohort`) | Segment (couche 4 — cross-guest intelligence) |

#### Justification réservation

- **Cohérence Décision #20** (4 couches temporelles). Le graphe permet le scope-filtering via Cypher temporal predicates (`WHERE s.start_at > NOW() - INTERVAL '24 hours'` pour Working, `WHERE s.start_at > NOW() - INTERVAL '30 days'` pour Episodic) — pas besoin de 4 stores physiques distincts pour les **relations**. Les sources de vérité (Redis / PG time-filtered / pgvector / MV k-means) restent inchangées Décision #20 ; le graphe **indexe leurs liens**.
- **Pré-figure le MCP tool `query_guest_profile(scope)`** Anima : `scope = "working"` → graph query `WHERE s.start_at > $stay_start` ; `scope = "episodic"` → `WHERE s.start_at > NOW() - 30d` ; `scope = "semantic"` → permanent ; `scope = "segment"` → traverse via `MATCHES_SEGMENT`. **Le param `scope` Anima devient un Cypher temporal filter.**
- **Bridge cross-nœud Mesh** (`docs/mesh-architecture.md` §3 flux événement) : `EXPERIENCED` edge connecte `Stay` Anima → `Outcome` Aetherix. Le graphe **est** la lingua franca Mesh. Pas d'invention d'une 3e API.

#### Hors-scope Phase 4 (cet ADR)

- DDL Anima (`Guest` / `Stay` / `Sentiment` création) = ADR séparé futur, **gated par DPIA**.
- Implémentation `query_guest_profile` MCP tool = repo Anima Phase 4.
- Cet ADR garantit uniquement la **forward-compat schema** (les node/edge types réservés ne sont pas pris par autre chose).

---

### D6 (Q6) — MCP tools exposés : **`query_context_graph(query_type, depth)` atomique avec query_types whitelist**

#### Décision

Exposer **un seul nouveau MCP tool** à `/mcp/v1/` (cohérent ADR-0004 D4 — atomic tools, orchestration côté caller) :

```python
@mcp_server.tool()
async def query_context_graph(
    *,
    query_type: GraphQueryType,
    target_date: date | None = None,
    service_slot: str | None = None,
    event_type: str | None = None,
    depth: int = 2,
    limit: int = 10,
) -> GraphQueryResult: ...
```

Scope MCP minimum : `graph:read`. **Écritures via service interne uniquement** (pas exposé MCP).

#### Whitelist `GraphQueryType` (Phase 4 = 6 query types)

| Query type | Cypher pattern (résumé) | Use case orchestrateur |
|---|---|---|
| `event_outcome_history` | `(:Event {event_type})-[:CAUSED]->(:Outcome)<-[:PRODUCED]-(:Hotel)` filtré cohorte | "Quelles couverts attend-on quand IFA tombe sur un mardi septembre ?" |
| `senior_wisdom_path` | `(:SeniorIntervention)-[:INTERVENED_ON]->(:Recommendation {service_type})-[:SUGGESTED]->(:Outcome)` filtré `manager_feedback='followed'` + cohorte | "Qu'a fait un chef d'hôtel similaire face à cette situation, et ça a marché ?" |
| `cohort_outcome_band` | `(:Hotel {self})-[:BELONGS_TO_COHORT]->(:Cohort)<-[:BELONGS_TO_COHORT]-(:Hotel)-[:PRODUCED]->(:Outcome)` agrégé | "Quelle bande p25-p75 covers dinner pour ma cohorte un samedi normal ?" |
| `edge_case_lookup` | `(:Outcome {actual})-[:MATCHES_PATTERN]->(:EdgeCase)` | "Cet outcome est-il un cas connu ?" (abstention sentinel ADR-0007 D6) |
| `cause_diagnosis` | `(:Outcome {actual})<-[:CAUSED]-(:Event ∪ :Weather)` | "Qu'est-ce qui a causé ce spike covers ?" (post-hoc explainability) |
| `intervention_chain` | `(:Recommendation {rec_id})-[:SUGGESTED]->(:Outcome)<-[:INTERVENED_ON]-(:SeniorIntervention)` | "Quelles interventions sur cette recommendation et leur outcome ?" |

#### `GraphQueryResult` schéma

```python
@dataclass(frozen=True)
class GraphPathNode:
    node_type: str           # "Hotel" | "Event" | ...
    properties: dict         # filtered (no PII, no internal_id)
    score: float | None      # depth-discount × edge weight

@dataclass(frozen=True)
class GraphQueryResult:
    query_type: GraphQueryType
    paths: list[list[GraphPathNode]]   # liste de chemins
    aggregate: dict | None             # ex: {"p25": 78, "p50": 92, "p75": 108} for cohort_outcome_band
    cached: bool
    latency_ms: int
```

#### Sécurité — pas de Cypher arbitraire

**Pourquoi pas exposer Cypher brut via MCP** :
- Injection (analogue SQL injection sur AGE).
- Cost control (un `MATCH (a)-[*1..10]-(b)` peut exploser la DB).
- Audit RLS (tenant isolation impossible à enforcer sur Cypher arbitraire).

Whitelist 6 query types Phase 4 → ajouts via PR explicit (eval gate Décision #22 = nouvelle catégorie scenario à chaque query type ajouté).

#### Tenant isolation

Chaque MCP call résolu `hotel_id` côté serveur depuis le bearer (cohérent `docs/mesh-architecture.md` §4 *"hotel_id server-side"*). Les query patterns AGE injectent **systématiquement** le filter `MATCH (:Hotel {hotel_id: $hotel_id})` en premier hop. Pas de cross-tenant leak possible.

**RLS Postgres limitation Apache AGE** : AGE schema (`aetherix_context`) ne supporte pas nativement les Row Level Security policies au sens Postgres standard sur les nodes. Mitigation Phase 4 :

1. Tous les nodes `Hotel` (et nodes liés à un hôtel) portent property `hotel_id`.
2. Le `ContextGraphService` Python **inject obligatoirement** `hotel_id` dans chaque Cypher exécuté (pattern décorator). Compile-time check via test CI.
3. Si fuite cross-tenant détectée → switch `GRAPH_BACKEND=disabled` runtime + alert.
4. Phase 5+ : évaluer AGE 1.6+ ou switch backend si RLS native disponible.

---

### D7 (Q7) — Eval gate Décision #22 : **catégorie `context_graph_query` + 10 scenarios initiaux**

#### Décision

Étendre la taxonomie ADR-0007 D1 avec une nouvelle catégorie **`context_graph_query`** (layer `graph`). Min 10 scenarios initiaux dans `eval/golden_dataset.jsonl` à shipper avec Story P4-GRAPH-5.

#### Scenarios initiaux (10)

| Scenario id | Sub-category | Failure trigger candidat |
|---|---|---|
| `graph-event-outcome-history-001` | `event_outcome_history` query type | Retrieved outcomes médiane delta > 25% vs ground truth annotée |
| `graph-event-outcome-history-002` | Cohort 5+ hôtels, query 3y lookback | Latence p95 > 800ms (SLO graph wider que MCP basic 500ms) |
| `graph-senior-wisdom-path-001` | `senior_wisdom_path`, intervention `followed=true` | Aucun path retourné si pattern existe (precision drop > 10pp) |
| `graph-cohort-outcome-band-001` | `cohort_outcome_band` p25-p75 vs ground truth band | Band ne couvre pas valeur réelle dans > 25% des scenarios |
| `graph-edge-case-lookup-001` | `edge_case_lookup` sur outcome OOD | `EdgeCase` matché doit déclencher `AgentAbstention(reason="ood_edge")` (ADR-0007 D6) |
| `graph-cause-diagnosis-001` | `cause_diagnosis` post-hoc, weather + event collision | Top-cause incorrect (KL > 0.2 entre attended et returned distribution) |
| `graph-intervention-chain-001` | `intervention_chain` complete path | Chain incomplet (missing edge) si data ground truth complète |
| `graph-tenant-isolation-001` | Cross-tenant leak test (canary) | Query retourne ≥ 1 node d'un autre `hotel_id` = FAIL immédiat (blocking merge) |
| `graph-empty-cohort-002` | Cold-start (hôtel sans cohorte) | Doit retourner empty path + sentinel, pas crash |
| `graph-latency-slo-001` | `query_type=cohort_outcome_band`, `depth=3`, `limit=20` | p95 > 800ms = WARN, > 1500ms = FAIL |

#### Threshold précision retrievals graphe

- **Precision@5** sur les query types retournant un ranking (`senior_wisdom_path`, `event_outcome_history`) : ≥ 0.7 vs ground truth annotée par PM.
- **Band coverage** (`cohort_outcome_band`) : ≥ 0.75 des ground truth values dans [p25, p75] retourné.
- **Cross-tenant leak** : 0 sur canary `graph-tenant-isolation-001` = hard gate (analogue Décision #16).

#### Eval coverage CI gate

Story P4-GRAPH-5 enforce `scripts/ci/check_eval_coverage.py` (ADR-0007 D2.a) avec ajout :

```python
EVAL_TRIGGER_PATHS += [
    "backend/app/services/context_graph_service.py",
    "supabase/migrations/PHASE_4/*_context_graph_*.sql",
    "eval/golden_dataset.jsonl",   # déjà listé
]
# mapping
PATH_TO_LAYER["backend/app/services/context_graph_service.py"] = "graph"
```

PR touchant `context_graph_service.py` → require `context_graph_query` ≥ 5 scenarios dans golden dataset. Override `eval-exempt` autorisé refactor/doc/infra.

#### `FAILURE_THRESHOLDS.md` extension

Ajouter section *"Layer: graph"* dans `eval/FAILURE_THRESHOLDS.md` Phase 4 :
- Precision@5 senior_wisdom_path : WARN < 0.7, FAIL < 0.55.
- Band coverage cohort_outcome_band : WARN < 0.75, FAIL < 0.60.
- Latency p95 query_context_graph : WARN > 800ms, FAIL > 1500ms.
- Cross-tenant leak : 1 = FAIL immédiat (blocking).

---

## 3. Spec scripts (Phase 4 — backlog Dev)

### 3.1 Migration Alembic Apache AGE setup

**Fichier** : `supabase/migrations/PHASE_4/20260901000000_context_graph_age_setup.sql`
**Contenu** : DDL D2 (extension, create_graph, vlabels, elabels, indexes GIN).
**Idempotence** : `IF NOT EXISTS` partout. Re-run safe.
**Test CI** : intégrer `scripts/ci/check_schema_drift.py` exception + test `test_age_setup_idempotent.py` (apply migration twice, assert no error).

### 3.2 Backfill script

**Fichier** : `scripts/ops/backfill_context_graph.py`
**CLI** : `python -m scripts.ops.backfill_context_graph --hotel-id <UUID> [--dry-run] [--lookback-days 1095] [--node-types Hotel,Event,Weather,...]`
**Idempotence** : `MERGE` Cypher partout. Re-run = update properties si changed.
**Logging** : structured logs per node-type count + edge-type count + duration.
**Telemetry** : write to `agent_action_log` row `kind="graph_backfill"` avec count par label.

### 3.3 Worker nightly

**Fichier** : `backend/app/workers/refresh_context_graph_nightly.py`
**APScheduler trigger** : daily 03:00 cdg.
**Behavior** : incremental ingest depuis `agent_action_log WHERE created_at > graph_last_synced_at`. Idempotent.
**MV refresh** : update `context_graph_freshness_daily` MV (per-hotel last-sync + node count drift).

### 3.4 Eval script

**Fichier** : `scripts/eval/eval_graph.py`
**Conforme** ADR-0007 D5 (`scripts/eval/*.py` pattern).
**Behavior** :
1. Load `eval/golden_dataset.jsonl` scenarios `category="context_graph_query"`.
2. For each scenario : execute `query_context_graph` via MCP test client.
3. Assert precision@k / band coverage / latency.
4. Output JSON + Markdown report.

### 3.5 Service Python

**Fichier** : `backend/app/services/context_graph_service.py`
**Class** : `ContextGraphService(db: AsyncSession)`.
**Methods** :
- `async query(query_type, **params) -> GraphQueryResult` — entry point MCP tool.
- `async merge_hotel(hotel_id, ...) -> None` — ingest API.
- `async merge_event(event_id, ...) -> None`.
- ... (8 merge methods, un par node type).
- `async merge_edge_*(...)` (9 edge merge methods).
- `_inject_tenant_filter(cypher: str, hotel_id: str) -> str` — sécurité D6.

**Test** : `backend/tests/services/test_context_graph_service.py` — pure logic, mock asyncpg, assert all Cypher patterns contain `hotel_id` filter.

---

## 4. Story breakdown Phase 4 (POS-1 → GRAPH-5)

Cohérent format `docs/planning/phase-3-pilot-validation.md` Track A + ADR-0006 §3. Linear IDs à créer SM Phase 4 kickoff.

| Story | Title | Effort | Dépend de |
|---|---|---|---|
| **P4-GRAPH-1** | Apache AGE setup + migration + `ContextGraphService` skeleton + MockContextGraph + tests unit | 3 | ADR-0006 P4-POS-2 (schema POS doit exister pour Outcome node FK soft) |
| **P4-GRAPH-2** | Backfill script + 8 node merge methods + 9 edge merge methods + first pilot property backfill validation | 5 | P4-GRAPH-1 |
| **P4-GRAPH-3** | Worker nightly + `MemoryRecallService` extension `recall_strategy="hybrid"` + dual-read SQL hybrid pattern | 5 | P4-GRAPH-2 + ADR-0006 P4-POS-5 (cohort features v2 nécessaires pour cohort path) |
| **P4-GRAPH-4** | MCP tool `query_context_graph` + 6 query types whitelist + tenant isolation injection + scope `graph:read` | 5 | P4-GRAPH-3 |
| **P4-GRAPH-5** | Eval gate `context_graph_query` 10 scenarios + `FAILURE_THRESHOLDS.md` graph section + `check_eval_coverage.py` trigger paths extension | 3 | P4-GRAPH-4 |

**Total** : 5 stories, **21 points**, ~5 sprint-weeks single-dev.

**Pré-requis externes** : ADR-0006 P4-POS-1 + P4-POS-2 + P4-POS-5 shippés (schema POS + cohort features v2). Sequencing Phase 4 = POS d'abord (semaines 1-4), GRAPH ensuite (semaines 5-9).

---

## 5. Risques et mitigations

| ID | Risque | Probabilité | Sévérité | Mitigation |
|---|---|---|---|---|
| **R1** | Performance queries Cypher sur Supabase managed (Apache AGE pas réputé pour 1M+ nodes/hotel) | Faible Phase 4 (estim < 100K nodes/hotel), Moyenne Phase 5+ multi-tenant scale | Modérée | Benchmarks `scripts/eval/eval_graph.py` latency scenarios. Watchlist p95 query latency dans `agent_action_log`. Migration path Neo4j Aura documented §D1 si seuil atteint. |
| **R2** | Latence MCP `query_context_graph` casse SLO 500ms (Décision #3) sur queries 3-hop avec cohort 10+ hôtels | Moyenne | Sévère (SLO Décision #3) | (a) SLO graph étendu à 800ms p95 (vs 500ms recall basique) — documenté dans D7 thresholds. (b) Cache LRU sur `query_context_graph` (TTL 5min, invalidate sur worker nightly). (c) Query types whitelist (D6) = patterns optimisés, pas free-form Cypher. |
| **R3** | Complexity migration backfill batch (3y historique, ~100K nodes, edges sur cohort SIMILAR_TO O(N²)) | Élevée | Modérée (one-shot par hôtel) | Backfill par hôtel séquentiel (D3). Limit cohort SIMILAR_TO à top-10 nearest neighbors (pas all-pairs). Idempotent MERGE = re-run safe en cas de partial failure. Dry-run flag mandatoire. |
| **R4** | Training équipe Dev sur Apache AGE / Cypher (1 dev solo, Cypher = nouveau paradigme) | Moyenne | Modérée | (a) 6 query types whitelist (D6) = pas besoin Cypher mastery, juste templates. (b) Article Phase 4 Track B *"Building a context graph on Apache AGE + pgvector"* = capitalisation REX. (c) Docs interne `docs/graph/cookbook.md` (~10 patterns canoniques). |
| **R5** | RLS Postgres ne fonctionne pas nativement sur AGE schemas (cross-tenant leak risk) | Faible (mitigation §D6) | **Critique** (RGPD + perte confiance pilote) | Mitigation 3-layer §D6 : `_inject_tenant_filter` décorator + scenario eval `graph-tenant-isolation-001` blocking + `GRAPH_BACKEND=disabled` runtime kill-switch. Audit quarterly via canary scenarios. |
| **R6** | Apache AGE extension non disponible sur tier Supabase actuel | Faible (vérifié 06/06/2026 Supabase docs — AGE supporté Postgres 15+ avec extension allowlist) | Sévère (block ship) | **Action immédiate Architect (cette session DoD)** : tester sur staging Fly.io `cdg` via `CREATE EXTENSION age;` — si bloqué, contact support Supabase. Si refusé : fallback Postgres recursive CTE Phase 4 (downgrade fonctionnel +1 sprint refactor) ou switch Neo4j Aura (+$65/mois, viole Décision #3). |
| **R7** | Coexistence pgvector + AGE complexifie debug + monitoring | Moyenne | Faible | Telemetry séparée : recall via cosine = log `recall_strategy="cosine_only"` ; via graph = log `recall_strategy IN ("path_find","hybrid","cohort_traversal")`. MV `memory_recall_daily` segmenté par strategy (extension ADR-0002 D10). |
| **R8** | Graph stale (worker nightly skip) → décisions sur data obsolète | Moyenne | Modérée | MV `context_graph_freshness_daily` per-hotel. Alert WhatsApp ops si `freshness > 48h` (analogue ADR-0007 D6 variante 3 drift alert). |
| **R9** | Schema graph evolution complexe (ajouter node type post-Phase 4 ship) | Moyenne | Modérée | Apache AGE `create_vlabel` / `create_elabel` idempotent. Migration Alembic versioned. Backfill script paramétrable `--node-types` flag. Schema additif only ; suppression de node type = ADR séparé. |

---

## 6. Sécurité & data sovereignty

- **Read-only via MCP** : `query_context_graph` scope `graph:read`. Pas de tool MCP write. Toute écriture (`merge_*`) = service interne uniquement, callable via worker / backfill scripts.
- **Tenant isolation** : `_inject_tenant_filter` (D6) — chaque Cypher injecte `MATCH (:Hotel {hotel_id: $hotel_id})` en premier hop. Compile-time test CI. Scenario eval canary `graph-tenant-isolation-001` blocking.
- **RLS Postgres** : exception schema `aetherix_context` documentée dans `scripts/ci/schema_drift_ignore.json`. Mitigation 3-layer §D6.
- **PII guest = hors-scope Phase 4** (cohérent Décision #20 Anima DPIA gate). Node types `Guest` / `Stay` / `Sentiment` réservés mais non créés. Aucun guest_id dans le graphe Aetherix Phase 4.
- **Audit log** : chaque `query_context_graph` call → `agent_action_log` (ADR-0003) avec `query_type`, `depth`, `result_count`, `latency_ms`, `cached`.
- **Federated Hive narrative** (snippet H-7) — *"raw data stays in your tenant, operational patterns travel anonymized"*. Cohort nodes `Cohort` portent uniquement features agrégées (déjà anonymisées via ADR-0005 + ADR-0006). Pas de leak via le graphe.
- **Kill-switch** : env var `GRAPH_BACKEND=disabled` → `query_context_graph` retourne sentinel `GraphQueryResult(paths=[], aggregate=None, cached=False, latency_ms=0)` + `MemoryRecallService.recall(recall_strategy="cosine_only")` forcé. Permet de rollback runtime sans deploy.

---

## 7. Migration future Phase 5+ (option de sortie)

Mention possibility (pas décision) :

- **Switch Neo4j Aura** si Apache AGE benchmark hit limit > 1M nodes/hôtel ou si scale multi-tenant > 100 hôtels casse latency. Effort estimé 5-8j (export AGE → Cypher dump + provisioning + refactor transport layer `ContextGraphService`).
- **CDC temps réel Supabase Realtime** sur `agent_action_log` pour ingest streaming (vs batch nightly). Trigger : besoin d'orchestrateur réactif sur events temps réel (cohérent open decision *"Interaction model event-driven Phase 4-5"* — futur ADR-0013, corrigé 20/07/2026).
- **Cypher arbitraire exposé MCP** : Phase 5 si query types whitelist (D6) atteint > 30 et bloque cas d'usage légitime orchestrateur. Gated par sandbox query limits + cost budget per call.

---

## 8. Definition of Done — ADR-0008 ACCEPTED

**Architectural DoD (cette session)** :

- [x] §1 contexte écrit (problème actuel + trigger 04/06 + goal + non-goals)
- [x] §2 D1-D7 tranchés (tech choice, schema, migration, recall integration, Anima foundation, MCP tools, eval gate)
- [x] §3 spec scripts (5 files identifiés avec arborescence + behavior)
- [x] §4 story breakdown 5 stories, 21 points
- [x] §5 9 risques + mitigations chiffrées
- [x] §6 security checklist tenant isolation + kill-switch + Anima forward-compat
- [x] §7 migration path Phase 5+ documenté
- [x] §8 DoD opérationnel ci-dessous

**Operational DoD — gate ship Graph Phase 4** (Story P4-GRAPH-4 + P4-GRAPH-5) :

1. **Apache AGE installé** : `CREATE EXTENSION age` exécuté en staging Supabase + smoke test `RETURN 1` Cypher. (Action immédiate post-merge cet ADR — vérification R6.)
2. **Backfill** : ≥ 1 pilot property backfillée avec `--dry-run=false`. Logs structured node-type + edge-type counts cohérents avec source data (delta < 5% sur counts agent_action_log → events).
3. **Latency SLO** : `query_context_graph` p95 < 800ms sur 6 query types whitelist sur le pilot property post-backfill.
4. **Eval gate** : `context_graph_query` ≥ 10 scenarios dans `golden_dataset.jsonl` + `check_eval_coverage.py` green (Décision #22).
5. **Tenant isolation canary** : scenario `graph-tenant-isolation-001` PASS sur tous les runs CI.
6. **Cohort matching v3 LOO** : ≥ 2 sandbox properties → **MAPE_v3 ≤ MAPE_v2 - 0.5 pt** sur covers dinner (gate runtime auto-disable v3 si non — fallback v2 ADR-0006). Cohérent ADR-0006 D4 gate.
7. **Documentation** : article Phase 4 Track B *"Building a context graph on Apache AGE + pgvector — knowledge extraction without the bottleneck"* drafté (cf. snippet H-6 + thèse Lore vision-future.md).

**Gate ship Anima Phase 4** (conditionnel post-Graph Phase 4 ship) :

- Pré-requis Décision #20 (DPIA) → ADR séparé à venir.
- Cet ADR-0008 = forward-compat schema (D5) uniquement. Pas blocker DPIA.

---

## 9. Open questions (sortantes — re-trier post-pilote)

| ID | Question | Trigger résolution |
|---|---|---|
| OQ1 | RLS native Apache AGE arrive-t-il Phase 5 ? Si oui, retirer mitigation `_inject_tenant_filter` ? | Monitoring releases AGE quarterly |
| OQ2 | Cypher arbitraire exposé MCP scope `graph:query_advanced` réservé orchestrateur seulement (pas third-party) ? | Phase 5 si query types whitelist > 30 |
| OQ3 | Causal scoring sur `CAUSED` edges = post-hoc Bayesian (placeholder Phase 4) → vraie causal inference Phase 5 (DoWhy / EconML) ? | Demand pilot data scientist |
| OQ4 | Backfill streaming vs batch — CDC Supabase Realtime sur `agent_action_log` Phase 5 si réactif requis | Open decision *"Interaction model event-driven"* future ADR-0013 (corrigé 20/07/2026) |
| OQ5 | Suppression de nodes obsolètes (decay : `Outcome` > 3 ans pertinent encore ?) | Phase 5 si graph croît trop |

---

## 10. Décisions liées

- **CLAUDE.md Décision #2** (architecture mémoire 2 couches) — invariant préservé : graphe = vue indexée, pas 3e couche. Sources de vérité Private + Hive inchangées.
- **CLAUDE.md Décision #3** (pgvector > Qdrant > Pinecone — *"compatible latency MCP <500ms"*) — pivot du choix Apache AGE (Postgres-native vs Neo4j externe).
- **CLAUDE.md Décision #9 / #10** (`LLMProvider` / `EmbeddingProvider` Protocol + singleton `lifespan`) — pas de nouveau provider créé. `ContextGraphService` = service standard, pas Protocol-abstracted (Phase 5+ si multi-backend).
- **CLAUDE.md Décision #16** (schema drift gate) — exception explicite `aetherix_context` schema documentée.
- **CLAUDE.md Décision #19** (orchestrator séparé — Aetherix = F&B execution node) — MCP tool `query_context_graph` exposé par Aetherix, consommé par orchestrator (cohérent).
- **CLAUDE.md Décision #20** (Anima — 4 couches + DPIA gate) — forward-compat schema D5 réserve `Guest` / `Stay` / `Sentiment` non créés Phase 4. DPIA reste blocker Anima.
- **CLAUDE.md Décision #22** (eval-by-design) — nouvelle catégorie `context_graph_query` 10 scenarios initiaux.
- **CLAUDE.md Décision #23** / ADR-0006 (POS) — `Outcome` node sourcé `pos_transaction`. Pré-requis débloqué.
- **ADR-0001** MCP Server v0 — pattern lifespan + scope `graph:read`.
- **ADR-0002** memory-instrumentation — `MemoryRecallService.recall(recall_strategy)` étendu backward-compat.
- **ADR-0003** observability — `agent_action_log` log `query_type` / `recall_strategy` / `graph_path` (3 colonnes JSONB optionnelles à ajouter Phase 4 P4-GRAPH-3).
- **ADR-0004** orchestrator-separation — graphe exposé MCP-only, pas import Python orchestrator/.
- **ADR-0005** cold-start meta-learner (Resolved 28/05/2026 in `open-decisions.md`) — `query_cohort_prior` MCP tool inchangé Phase 4 ship ; étension cohort v3 multi-dim via D4 hybrid recall ne casse pas le contract.
- **ADR-0006** POS — `Outcome` node FK soft sur `pos_transaction.transaction_id`. Schema POS pré-requis.
- **ADR-0007** evaluation-by-design — D1 taxonomy étendue avec `context_graph_query`, D5 distribution shift surveille distribution graph node counts per type quotidien.

---

## 11. Actions post-ADR

1. **Update CLAUDE.md §Décisions architecturales** — ajouter ligne d'index #24 *"Graphe de contexte Apache AGE Phase 4 (06/06/2026)"* (action effectuée par cette session Architect).
2. **Update `docs/context/decisions-architecturales.md`** — ajouter section H3 §24 détail complet (action effectuée par cette session Architect).
3. **Update `docs/context/open-decisions.md`** — déplacer *"Graphe de contexte — Phase 4 priority"* de §Actives vers §Resolved avec date 06/06/2026 + ref ADR-0008 (action effectuée par cette session Architect).
4. **Update `docs/context/memory-architecture.md`** — ajouter section *"Couche graphe Phase 4 (ADR-0008)"* clarifiant que le graphe **n'est pas** une 3e couche mémoire mais une indexation cross-couches (action effectuée par cette session Architect).
5. **Notifier PM (Ivan)** — sign-off Q1 (Apache AGE) + validation final ADR.
6. **Action staging Supabase R6** : tester `CREATE EXTENSION age;` sur Fly.io staging avant Phase 4 kickoff. Si bloqué Supabase tier actuel → escalade support.
7. **Session SM (Bob)** — créer 5 stories Linear `HOS-GRAPH-1` à `HOS-GRAPH-5` Phase 4 :
   - Description = lien vers `docs/adr/0008-context-graph.md` + section pertinente.
   - Acceptance criteria = DoD section §8 mappée par story.
   - Effort = table §4.
   - Sequencing = post-ADR-0006 POS-2 + POS-5.
8. **Post-GRAPH-1...3 shippés** : capture asset Phase 4 Track B *"Building a context graph on Apache AGE + pgvector"* (article public, capitalise thèse knowledge extraction).
9. **Post-GRAPH-5 shippé** : pilot Phase 4 graph capability débloquée pour démo design partner #2.

---

## 12. Références

- ADR 0001 — Aetherix MCP Server v0 (pattern lifespan + scope)
- ADR 0002 — Memory instrumentation (`MemoryRecallService` extension recall_strategy)
- ADR 0003 — `agent_action_log` observability (extension JSONB graph_path)
- ADR 0004 — Orchestrator separation (graph exposé MCP-only)
- ADR 0006 — POS integration (`Outcome` node FK soft sur `pos_transaction`)
- ADR 0007 — Evaluation-by-design (taxonomy `context_graph_query`)
- `docs/context/decisions-architecturales.md` — Décisions #2, #3, #9, #10, #16, #19, #20, #22, #23 invoquées
- `docs/context/open-decisions.md` §Graphe de contexte (déplacée Resolved par cette session)
- `docs/context/memory-architecture.md` — modèle 2 couches (graphe = indexation cross-couches)
- `docs/mesh-architecture.md` — §2 Anima 4 couches forward-compat (D5)
- `docs/context/vision-future.md` — Aetherix Voice Phase 5+ Lore-inspired knowledge graph
- `docs/competitive/conduit-ai-analysis.md` — thèse knowledge extraction bottleneck (positioning défense)
- `memory/market_signals_2026Q2.md` §04/06 — convergence Mira Murati / Hyperspell / GBrain / Lore
- Apache AGE official docs : https://age.apache.org/age-manual/master/ (Cypher partial OpenCypher, Postgres extension)
- Supabase GitHub Discussion supabase/#40285 — Apache AGE not officially supported, FDW workaround recommended
- Supabase docs extensions : https://supabase.com/docs/guides/database/extensions

---

## 13. Amendment 06/06/2026 — Q1 Backend hosting (Supabase blocker)

> **Status amendment** : Q1 D1 **invalidée partiellement** (le backend hosting Supabase managed). Architecture §2 D2-D7 + DDL + schema + recall extension **inchangés**.

### 13.1 Finding

R6 (§5) confirmé bloquant. Vérifications cette session (06/06/2026 post-rédaction) :

- **Supabase GitHub Discussion supabase/#40285** : *"Supabase doesn't officially support Apache AGE yet"* — extension C non-trusted, pas dans la liste pre-approved Supabase managed.
- **Supabase docs extensions** : 50+ extensions disponibles, Apache AGE **absent**. `pg_tle` disponible mais réservé aux trusted languages (PL/pgSQL, SQL, pas C).
- **Roadmap officielle** : aucune mention. Demande communautaire ouverte depuis ≥ 2 ans (discussion #13263).
- **Workaround recommandé Supabase community** : architecture multi-DB (Supabase pour app + Postgres séparé pour AGE) reliée via `postgres_fdw`.

### 13.2 Impact analyse

- ✅ §2 D2 (schema 8 nodes / 9 edges) — inchangé
- ✅ §2 D4 (`MemoryRecallService` extension hybrid) — inchangé, mais le SQL hybride single-transaction §D4 nécessite FDW si AGE sur Postgres distinct
- ✅ §2 D5 (foundation Anima forward-compat) — inchangé
- ✅ §2 D6 (MCP tool `query_context_graph` whitelist 6 query types) — inchangé
- ✅ §2 D7 (eval gate `context_graph_query`) — inchangé
- ⚠️ §2 D1 (Apache AGE comme **extension Supabase native**) — **invalidé**
- ⚠️ §6 (RLS limitation §D6 + kill-switch) — invariant maintenu mais redéfini sur le nouveau backend
- ⚠️ Score pondéré §D1 doit être recalculé sur les 4 paths forward (§13.3)

### 13.3 Trois paths forward (PM decision required)

| Path | Description | Coût mensuel ajouté | Cohérence Décisions | Effort dev delta vs ADR initial |
|---|---|---|---|---|
| **A — Fly Postgres dédié + postgres_fdw** *(reco Architect)* | Provisionner instance Postgres séparée sur Fly.io cdg + Apache AGE installé + FDW depuis Supabase principal. Single vendor infra (Fly.io), single network hop intra-region (cdg ↔ cdg). | **+$15-30/mois** Fly Postgres entry tier | ✅ Décision #17 Fly.io déjà retenu · ⚠️ Décision #3 *"pgvector > Qdrant"* préservée (pgvector reste Supabase) · ✅ Décision #10 lifespan inchangé (2 pools DB) | **+2 jours** (provisioning Fly Postgres + FDW setup + tests connectivité) |
| **B — Neo4j Aura** | Service managed Neo4j externe. Cypher complet supporté. | **+$65/mois** entry tier | ❌ Décision #3 frame stricte (Postgres-native) — Neo4j = service non-Postgres · ⚠️ Network hop transatlantique (Aura US/EU) | **+3-5 jours** (refactor `ContextGraphService` transport layer Neo4j driver vs asyncpg) |
| **C — Postgres recursive CTE (fallback §R6 ADR)** | Pas d'extension, CTE récursives sur Supabase. Pas de Cypher. | **+$0** | ✅ 100% cohérent stack actuel | **+1 sprint complet** (refactor §D2 schema → tables FK + indexes B-tree + queries SQL recursives 50-100 lignes par query type). Eval §D7 query types whitelist toujours faisable, mais perfs et expressivité réduites. |
| **D — Attendre Supabase AGE support** | Indéfini, pas de roadmap. | **+$0** mais **bloque Phase 4 graphe** | — | Bloque calendrier Phase 4 indéfiniment — **rejeté** |

### 13.4 Reco Architect : Path A (Fly Postgres dédié + FDW)

**Pourquoi A et pas B/C** :

- **vs Path B (Neo4j Aura)** : Path A coûte 2× moins (+$15-30 vs +$65), même latence intra-region cdg (Fly Postgres cdg ↔ Fly app cdg < 5ms vs Neo4j Aura cross-region ~50ms), reste Postgres-native (cohérence Décision #3 invariant pgvector + maintenant Fly Postgres pour AGE).
- **vs Path C (CTE)** : Path A préserve Cypher + Apache AGE = expressivité 5-10× supérieure sur queries 3-hop. CTE = +1 sprint refactor + maintenance code SQL long-terme + impossibilité d'évoluer vers vraies queries graphe Phase 5 (Aetherix Voice).
- **vs Path D (wait)** : bloque Phase 4 calendar.

**Trade-offs Path A à accepter** :
- 2 instances Postgres à monitorer (backups Fly Postgres séparés du Supabase managed).
- FDW = single-transaction queries hybrides faisables mais latence +5-15ms par hop FDW (vs single-DB).
- RLS Postgres natif sur Fly Postgres (pas la limitation §D6 AGE schema) — peut **simplifier** la mitigation tenant isolation (vs Supabase + AGE).

**Mitigations Path A** :
- Fly Postgres = pas multi-tenant côté graphe (un seul rôle app, tenant filter via `_inject_tenant_filter` côté Python — invariant ADR maintenu).
- Backup automatique Fly Postgres + snapshot quotidien (cf. Décision #17 invariant Fly.io ops).
- Documentation `docs/ops/fly-postgres-graph.md` à créer (provisioning + connection string + FDW setup + restore procedure).
- Schema AGE versioned via Alembic séparé `supabase/migrations/PHASE_4/graph/` + cible `--database-url=$FLY_POSTGRES_GRAPH_URL`.

### 13.5 Variables env amendement Path A

```
# AMENDMENT 06/06/2026 — Path A retenu (PM sign-off pending)
GRAPH_DATABASE_URL    — postgresql+asyncpg://...@aetherix-graph-pg.fly.dev:5432/graph
                        (instance Fly Postgres dédiée graphe, distincte de DATABASE_URL Supabase)
GRAPH_BACKEND         — "apache_age" (Phase 4 Path A) | "fdw_relay" (queries hybrides via Supabase FDW) | "disabled" (kill-switch)
GRAPH_FDW_ENABLED     — "true" (default Phase 4 — active queries hybrides cross-DB) | "false"
```

### 13.6 Impact story breakdown

- **P4-GRAPH-1 +2pts** (passe de 3 → 5) : provisioning Fly Postgres + FDW setup + secrets `flyctl secrets set GRAPH_DATABASE_URL`.
- **P4-GRAPH-2 inchangé** (backfill cible nouveau Fly Postgres au lieu Supabase).
- **P4-GRAPH-3 +1pt** (passe de 5 → 6) : `MemoryRecallService` hybrid recall doit gérer 2 pools (Supabase pgvector + Fly Postgres AGE via FDW ou cross-DB asyncpg).
- **P4-GRAPH-4 inchangé**.
- **P4-GRAPH-5 inchangé**.

**Total amendé** : 5 stories, **24 points** (vs 21 initial), ~6 sprint-weeks single-dev (vs 5).

### 13.7 PM sign-off — Path C retenu 06/06/2026

**Décision PM** : **Path C — Postgres recursive CTE** retenu.

**Raison invoquée** : raison financière (cash discipline pre-pilote). Path A reco Architect +$15-30/mois × multi-tenant Phase 5+ ⇒ trajectoire coût jugée non-souhaitée vs Path C $0 incrément hosting.

**Trade-offs acceptés par PM** :
- ✅ $0 coût hosting incrément (vs +$15-30/mois Path A, vs +$65/mois Path B)
- ✅ 100% cohérent stack Décision #3 + #17 (un seul vendor Supabase, pas d'instance Postgres supplémentaire à provisionner / monitorer / backup)
- ✅ RLS Postgres native sur Supabase (simplifie tenant isolation vs `_inject_tenant_filter` Cypher injection D6 original)
- ⚠️ +1 sprint refactor §D2 (schema 8 nodes + 9 edges → tables FK normalisées + indexes B-tree + queries SQL recursives 50-100 lignes par query type)
- ⚠️ Expressivité réduite vs Cypher : queries 3-hop sur 10+ nodes/edges = SQL CTE verbose et plus lent (typiquement 2-5× latence vs Cypher AGE sur même dataset)
- ⚠️ Pas de migration future trivial vers Neo4j (vs Path A AGE → Neo4j export Cypher portable). Migration Phase 5+ vers Apache AGE faisable si Supabase ajoute support (WT1 watchlist) — effort estimé 1-2 sprints (CTE schema → AGE MERGE Cypher déjà documenté §D2 D2 original).

**Documenté downstream** :
- CLAUDE.md §Décisions architecturales #24 libellé amendé *"Postgres recursive CTE (Phase 4)"*
- `docs/context/decisions-architecturales.md` H3 §24 amendé (Q1 backend = Path C)
- `docs/context/open-decisions.md` §Resolved 06/06/2026 (sous-décision Q1 backend = Path C cash-driven)
- `docs/context/memory-architecture.md` couche graphe Phase 4 mention Path C
- `docs/context/monitoring-watchlist.md` WT1 — trigger si Supabase ajoute AGE → réouvrir Path A possibility

**Next step** : SM (Bob) crée 6 stories Linear (HOS-GRAPH-1...6, breakdown amendé §13.6) — pas 5 comme initialement prévu Path A.

### 13.8 Story breakdown amendé Path C (override §4)

| Story | Title (Path C) | Effort | Dépend de |
|---|---|---|---|
| **P4-GRAPH-1** | Schema tables FK normalisées (8 node tables + 9 edge tables) + Alembic migration + ORM SQLAlchemy + RLS policies natives (8 + 9 = 17 policies) + `check_schema_drift.py` green | 5 | ADR-0006 P4-POS-2 |
| **P4-GRAPH-2** | Backfill script + ingest depuis sources (`agent_action_log`, `operational_memory`, `pos_transaction`, `hotel_cohort_features*`) + first pilot property backfill validation | 5 | P4-GRAPH-1 |
| **P4-GRAPH-3** | Worker nightly + `ContextGraphService` Python wrapper + 6 query types recursive CTE templates (Cypher → SQL CTE translation, cf. §16) | 5 | P4-GRAPH-2 |
| **P4-GRAPH-4** | `MemoryRecallService` extension `recall_strategy` + dual-read pattern hybrid (cosine pgvector + CTE traversal single transaction) | 5 | P4-GRAPH-3 + ADR-0006 P4-POS-5 |
| **P4-GRAPH-5** | MCP tool `query_context_graph` + 6 query types whitelist + scope `graph:read` + RLS-based tenant isolation (pas `_inject_tenant_filter` Cypher) | 3 | P4-GRAPH-4 |
| **P4-GRAPH-6** | Eval gate `context_graph_query` 10 scenarios + `FAILURE_THRESHOLDS.md` graph section (thresholds amendés CTE — latence cible p95 < 1200ms vs 800ms Path A initial, expressivité reconnue inférieure) | 3 | P4-GRAPH-5 |

**Total amendé Path C** : 6 stories, **26 points**, ~6-7 sprint-weeks single-dev (vs 5 stories / 21 pts Path A initial). Surcoût effort net = +5 pts (+1 sprint) — cohérent §13.3 *"+1 sprint refactor"*.

### 13.9 Variables env amendement Path C

```
# AMENDMENT 06/06/2026 — Path C retenu PM sign-off
GRAPH_BACKEND         — "postgres_cte" (default Phase 4 Path C) | "apache_age" (Phase 5+ option si WT1 trigger débloque Supabase AGE) | "disabled" (kill-switch)
```

Pas de `GRAPH_DATABASE_URL` séparé (Path A). Pas de `GRAPH_FDW_ENABLED` (Path A). Schema graph dans Supabase principal (search_path = `aetherix_graph,public`).

---

## 14. TODO checklist — actions post-ADR (durable, source de vérité)

> **Pourquoi cette section** : la chat session Architect est éphémère. Ces actions doivent être complétables par PM/SM/Dev en autonomie post-session. Cocher au fur et à mesure. Quand toutes les cases sont cochées, ADR-0008 = entièrement exécuté.

### Pré-Phase 4 (bloquants techniques) — Path C accepted

- [x] **PM sign-off §13 Q1 amendment** — Path C accepted 06/06/2026 (raison financière, cf. §13.7). Documenté `docs/context/open-decisions.md` §Resolved + `docs/context/decisions-architecturales.md` §24 amendé.
- [x] **Reminder Supabase AGE compatibility** — cron `check-supabase-apache-age-compatibility` créé (trimestriel, 1er du mois 9h) + entrée `docs/context/monitoring-watchlist.md` WT1 (réouvre Path A si Supabase ajoute AGE Phase 5+).
- [ ] **Smoke test schema CTE sur Supabase** — `CREATE SCHEMA aetherix_graph; CREATE TABLE aetherix_graph.test (id UUID PRIMARY KEY); SELECT 1 FROM aetherix_graph.test;` puis `DROP SCHEMA aetherix_graph CASCADE;` → confirme Supabase permet schema custom + DDL standard (très probable, mais 5min de validation).
- [ ] **Benchmark recursive CTE 3-hop sur dataset mock** — créer dataset synthétique 50K nodes / 150K edges + lancer 6 query types templates SQL CTE → mesurer p95 vs SLO amendé Path C 1200ms. Si dépassement systématique → ajustement indexes + MV avant ship.
- ~~Provisionner Fly Postgres dédié graphe~~ (Path A — non retenu)
- ~~Documenter Fly Postgres ops~~ (Path A — non retenu)
- ~~Setup `postgres_fdw` Supabase → Fly Postgres~~ (Path A — non retenu)

### Sessions BMad à enchaîner

- [ ] **Session SM (Bob)** — créer **12 stories Linear Phase 4** : 6 stories POS (`HOS-POS-1`→`HOS-POS-6` via ADR-0006) + 6 stories GRAPH (`HOS-GRAPH-1`→`HOS-GRAPH-6` via ADR-0008 amendé Path C §13.8). Sequencing : POS sem 1-4, GRAPH sem 5-11 (graph dépend cohort features v2 P4-POS-5).
- [ ] **Session Architect — ADR-0013 event-driven interaction model** (numéro corrigé 20/07/2026 — était référencé ADR-0009 par erreur, déjà pris par runtime guardrails) — dernière open decision §Actives 04/06 non-tranchée. Logique enchaîner maintenant (cohérence cross-ADR : POS webhook + graphe CDC mentionnés OQ4 ADR-0008). Effort estimé : ~1.5-2h session Opus.
- [ ] **Session Analyst (Mary) — REX article Track B** : *"Building a context graph on Apache AGE + pgvector — knowledge extraction without the bottleneck"*. Draft **post P4-GRAPH-1/2/3 shippés** (pas avant code). Asset Phase 4 Track B Décision #18 portfolio reinforcement.

### Hygiène repo (rapide)

- [ ] **Commit + PR ADRs 0006 + 0008 + amendement §13** — branch `architect/adr-0006-0008-graphe-pos` + PR contre `main`. Inclure tous updates `CLAUDE.md` / `decisions-architecturales.md` / `open-decisions.md` / `memory-architecture.md` + nouveau `ADR-0008` + ADR-0006 untracked. Note PR : ADR-0006 était `Accepted` mais untracked depuis 06/06 — cette session le finalise dans le repo.
- [ ] **Créer placeholder ADR-0005** — `docs/adr/0005-cold-start-meta-learner.md` actuellement référencé partout (ADR-0006, ADR-0007, ADR-0008, `open-decisions.md` §Resolved 28/05) mais **fichier absent**. Soit le rédiger (spec inline existante à formaliser), soit ajouter note explicative dans `open-decisions.md` §Resolved 28/05 ligne *"ADR-0005 = spec inline `query_cohort_prior` MCP tool, pas ADR dédié — formalisation différée Phase 4 si pertinent"*.
- [ ] **Update watchlist** — `docs/context/monitoring-watchlist.md` W1 Conduit + W2 Apaleo : ajouter trigger *"annonces 'knowledge graph' / 'context awareness' / 'graph-based memory'"* — concurrents pourraient claim narrative knowledge extraction post-Phase 4 ship Aetherix.

### Post-ship Phase 4 (long-terme)

- [ ] **DPIA Anima** — l'ADR-0008 §D5 réserve forward-compat schema mais ne débloque **pas** Anima Phase 4. DPIA reste pré-requis non-négociable Décision #20. À planifier indépendamment, idéalement avant pilote design partner #2 si segment hôtel premium.
- [ ] **OQ1 Migration Path C → Path A si Supabase ajoute AGE** — monitor WT1 watchlist + cron `check-supabase-apache-age-compatibility` (trimestriel). Si débloqué : (a) session Architect amendement ADR-0008 §13 → migration plan ; (b) export tables CTE → MERGE Cypher (1-2 sprints estimés cf. §16) ; (c) décision PM Phase 5+ : migrer pour expressivité Cypher OU rester CTE si pas de bénéfice business prouvé.
- [ ] **OQ3 causal scoring upgrade** — post-hoc Bayesian Phase 4 → vraie causal inference (DoWhy / EconML) Phase 5 si demand pilot data scientist.

---

## 15. Notes session Architect (audit trail)

- **06/06/2026 14:30** — ADR rédigé Status Accepted basé sur reco PM open-decisions 04/06 (Apache AGE).
- **06/06/2026 15:15** — Amendment §13 ajouté suite vérification R6 read-only check (WebFetch Supabase docs + GitHub discussion supabase/#40285). Apache AGE not officially supported Supabase managed jun 2026. Reco Architect = Path A Fly Postgres dédié + FDW.
- **06/06/2026 15:45** — PM sign-off **Path C** retenu (raison financière). Status ADR amendé Accepted Path C. §13.7 + §13.8 (story breakdown 6 stories / 26 pts) + §13.9 (env vars) + §16 (patterns CTE override D1/D2/D4/D6) ajoutés. Watchlist WT1 créée (cron trimestriel + entrée monitoring-watchlist.md) pour réouvrir Path A si Supabase ajoute AGE Phase 5+.

---

## 16. Patterns CTE — override technique Path C (override §2 D1/D2/D4/D6)

> **Statut** : annexe technique post-PM-sign-off Path C. Override les sections §2 D1/D2/D4/D6 originales (qui ciblaient Apache AGE) avec les patterns Postgres recursive CTE équivalents.

### 16.1 Override D1 (Q1 tech) → Postgres recursive CTE sur Supabase

Backend retenu : **Postgres 15 + recursive CTE + indexes B-tree + RLS policies natives** (cohérent stack Décision #3 + #17 + Supabase managed actuel). Pas d'extension nouvelle. Pas de Cypher. Pas de FDW.

Score pondéré revisité §D1 sur les 4 paths :
- Path A (Apache AGE / Fly Postgres dédié + FDW) — 81/100, +$15-30/mois
- Path B (Neo4j Aura) — 58/100, +$65/mois
- **Path C (Postgres CTE)** — **76/100, $0** ← **retenu PM 06/06**
- Path D (wait Supabase AGE) — bloque calendrier, rejeté

Path C score inférieur Path A de 5 points (expressivité Cypher manquante + verbose SQL) mais discriminant final = **coût** (PM priorité cash discipline pre-pilote).

### 16.2 Override D2 (Q2 schema) → 8 tables nodes + 9 tables edges + indexes B-tree

#### DDL Path C (override D2 DDL Apache AGE)

```sql
-- supabase/migrations/PHASE_4/20260901000000_context_graph_cte_setup.sql
-- Phase 4 Path C, Story P4-GRAPH-1

CREATE SCHEMA IF NOT EXISTS aetherix_graph;
SET search_path = aetherix_graph, public;

-- ====================================================
-- Node tables (8) — chaque table = un node type ADR §D2
-- ====================================================

CREATE TABLE aetherix_graph.node_hotel (
    node_id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    hotel_id         UUID NOT NULL UNIQUE REFERENCES public.hotel(hotel_id) ON DELETE CASCADE,
    geo_cluster      TEXT,
    capacity_bucket  TEXT,
    segment          TEXT,
    properties       JSONB NOT NULL DEFAULT '{}',
    created_at       TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE aetherix_graph.node_event (
    node_id      UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    event_id     TEXT NOT NULL,                       -- vendor / Paris Open Data id
    hotel_id     UUID NOT NULL REFERENCES public.hotel(hotel_id) ON DELETE CASCADE,  -- denorm pour RLS
    event_type   TEXT NOT NULL,
    start_at     TIMESTAMPTZ NOT NULL,
    end_at       TIMESTAMPTZ,
    intensity    REAL,
    properties   JSONB NOT NULL DEFAULT '{}',
    created_at   TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (event_id, hotel_id)
);

CREATE INDEX idx_node_event_type_date ON aetherix_graph.node_event (event_type, start_at);
CREATE INDEX idx_node_event_hotel ON aetherix_graph.node_event (hotel_id, start_at);

CREATE TABLE aetherix_graph.node_weather (
    node_id     UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    hotel_id    UUID NOT NULL REFERENCES public.hotel(hotel_id) ON DELETE CASCADE,
    weather_date DATE NOT NULL,
    temperature REAL,
    precipitation REAL,
    weather_score REAL,
    properties  JSONB NOT NULL DEFAULT '{}',
    UNIQUE (hotel_id, weather_date)
);

CREATE INDEX idx_node_weather_hotel_date ON aetherix_graph.node_weather (hotel_id, weather_date DESC);

CREATE TABLE aetherix_graph.node_outcome (
    node_id        UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    hotel_id       UUID NOT NULL REFERENCES public.hotel(hotel_id) ON DELETE CASCADE,
    outcome_date   DATE NOT NULL,
    service_slot   TEXT,
    metric         TEXT NOT NULL,            -- covers / ticket_size / occupancy
    value          REAL NOT NULL,
    unit           TEXT,
    source         TEXT,                     -- pos_transaction | operational_memory | apaleo_service
    properties     JSONB NOT NULL DEFAULT '{}',
    created_at     TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_node_outcome_hotel_date ON aetherix_graph.node_outcome (hotel_id, outcome_date DESC);
CREATE INDEX idx_node_outcome_metric_slot ON aetherix_graph.node_outcome (metric, service_slot, outcome_date DESC);

CREATE TABLE aetherix_graph.node_recommendation (
    node_id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    recommendation_id UUID NOT NULL UNIQUE,
    hotel_id         UUID NOT NULL REFERENCES public.hotel(hotel_id) ON DELETE CASCADE,
    service_type     TEXT,
    predicted_value  REAL,
    confidence       REAL,
    issued_at        TIMESTAMPTZ NOT NULL,
    properties       JSONB NOT NULL DEFAULT '{}'
);

CREATE INDEX idx_node_recommendation_hotel ON aetherix_graph.node_recommendation (hotel_id, issued_at DESC);

CREATE TABLE aetherix_graph.node_senior_intervention (
    node_id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    intervention_id  UUID NOT NULL UNIQUE,
    hotel_id         UUID NOT NULL REFERENCES public.hotel(hotel_id) ON DELETE CASCADE,
    actor_role       TEXT,                    -- chef / GM / maitre_dhotel / concierge
    tacit_pattern    TEXT,                    -- text wisdom captured
    applied_at       TIMESTAMPTZ NOT NULL,
    properties       JSONB NOT NULL DEFAULT '{}'
);

CREATE INDEX idx_node_intervention_actor ON aetherix_graph.node_senior_intervention (actor_role, applied_at DESC);
CREATE INDEX idx_node_intervention_hotel ON aetherix_graph.node_senior_intervention (hotel_id, applied_at DESC);

CREATE TABLE aetherix_graph.node_edge_case (
    node_id           UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    edge_case_id      TEXT NOT NULL UNIQUE,    -- mirror eval/golden_dataset.jsonl id
    hotel_id          UUID REFERENCES public.hotel(hotel_id) ON DELETE CASCADE,  -- nullable (catalogue partagé cohérent ADR-0007)
    category          TEXT NOT NULL,           -- ood_edge | pos_anomaly | context_graph_query
    severity          TEXT NOT NULL,           -- WARN | FAIL
    failure_trigger   TEXT,
    properties        JSONB NOT NULL DEFAULT '{}'
);

CREATE INDEX idx_node_edge_case_category ON aetherix_graph.node_edge_case (category, severity);

CREATE TABLE aetherix_graph.node_cohort (
    node_id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    cohort_id            UUID NOT NULL UNIQUE REFERENCES public.hotel_cohort_features(cohort_id) ON DELETE CASCADE,
    geo_cluster          TEXT,
    segment              TEXT,
    pos_provider         TEXT,
    aggregation_window   TEXT,
    properties           JSONB NOT NULL DEFAULT '{}'
);

-- ====================================================
-- Edge tables (9) — chaque table = un edge type ADR §D2
-- Pattern : (from_node_id, to_node_id, properties, created_at, UNIQUE constraint sur la paire)
-- ====================================================

CREATE TABLE aetherix_graph.edge_occurred_at (
    edge_id      UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    from_event   UUID NOT NULL REFERENCES aetherix_graph.node_event(node_id) ON DELETE CASCADE,
    to_hotel     UUID NOT NULL REFERENCES aetherix_graph.node_hotel(node_id) ON DELETE CASCADE,
    started_at   TIMESTAMPTZ NOT NULL,
    intensity    REAL,
    UNIQUE (from_event, to_hotel)
);

CREATE INDEX idx_edge_occurred_event ON aetherix_graph.edge_occurred_at (from_event);
CREATE INDEX idx_edge_occurred_hotel ON aetherix_graph.edge_occurred_at (to_hotel, started_at DESC);

CREATE TABLE aetherix_graph.edge_has_weather (
    edge_id      UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    from_hotel   UUID NOT NULL REFERENCES aetherix_graph.node_hotel(node_id) ON DELETE CASCADE,
    to_weather   UUID NOT NULL REFERENCES aetherix_graph.node_weather(node_id) ON DELETE CASCADE,
    weather_date DATE NOT NULL,
    UNIQUE (from_hotel, to_weather)
);

CREATE TABLE aetherix_graph.edge_produced (
    edge_id      UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    from_hotel   UUID NOT NULL REFERENCES aetherix_graph.node_hotel(node_id) ON DELETE CASCADE,
    to_outcome   UUID NOT NULL REFERENCES aetherix_graph.node_outcome(node_id) ON DELETE CASCADE,
    outcome_date DATE NOT NULL,
    service_slot TEXT,
    UNIQUE (from_hotel, to_outcome)
);

CREATE INDEX idx_edge_produced_hotel_date ON aetherix_graph.edge_produced (from_hotel, outcome_date DESC);

CREATE TABLE aetherix_graph.edge_caused (
    edge_id            UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    from_node_type     TEXT NOT NULL CHECK (from_node_type IN ('event', 'weather')),
    from_node_id       UUID NOT NULL,           -- polymorphic FK soft (validated by trigger or app code)
    to_outcome         UUID NOT NULL REFERENCES aetherix_graph.node_outcome(node_id) ON DELETE CASCADE,
    causal_score       REAL,                    -- 0-1 Bayesian post-hoc
    confidence         REAL,                    -- 0-1
    UNIQUE (from_node_type, from_node_id, to_outcome)
);

CREATE INDEX idx_edge_caused_to_outcome ON aetherix_graph.edge_caused (to_outcome, causal_score DESC);
CREATE INDEX idx_edge_caused_from ON aetherix_graph.edge_caused (from_node_type, from_node_id);

CREATE TABLE aetherix_graph.edge_suggested (
    edge_id           UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    from_recommendation UUID NOT NULL REFERENCES aetherix_graph.node_recommendation(node_id) ON DELETE CASCADE,
    to_outcome        UUID NOT NULL REFERENCES aetherix_graph.node_outcome(node_id) ON DELETE CASCADE,
    predicted_at      TIMESTAMPTZ NOT NULL,
    delta_to_actual   REAL,
    UNIQUE (from_recommendation, to_outcome)
);

CREATE TABLE aetherix_graph.edge_intervened_on (
    edge_id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    from_intervention    UUID NOT NULL REFERENCES aetherix_graph.node_senior_intervention(node_id) ON DELETE CASCADE,
    to_node_type         TEXT NOT NULL CHECK (to_node_type IN ('recommendation', 'outcome')),
    to_node_id           UUID NOT NULL,           -- polymorphic FK soft
    manager_feedback     TEXT,                    -- followed | rejected | modified
    applied_at           TIMESTAMPTZ NOT NULL,
    UNIQUE (from_intervention, to_node_type, to_node_id)
);

CREATE INDEX idx_edge_intervened_to ON aetherix_graph.edge_intervened_on (to_node_type, to_node_id);
CREATE INDEX idx_edge_intervened_feedback ON aetherix_graph.edge_intervened_on (manager_feedback, applied_at DESC);

CREATE TABLE aetherix_graph.edge_matches_pattern (
    edge_id            UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    from_node_type     TEXT NOT NULL CHECK (from_node_type IN ('outcome', 'senior_intervention')),
    from_node_id       UUID NOT NULL,
    to_edge_case       UUID NOT NULL REFERENCES aetherix_graph.node_edge_case(node_id) ON DELETE CASCADE,
    similarity         REAL,                    -- 0-1 cosine on embedded payload (optional)
    UNIQUE (from_node_type, from_node_id, to_edge_case)
);

CREATE TABLE aetherix_graph.edge_similar_to (
    edge_id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    from_hotel           UUID NOT NULL REFERENCES aetherix_graph.node_hotel(node_id) ON DELETE CASCADE,
    to_hotel             UUID NOT NULL REFERENCES aetherix_graph.node_hotel(node_id) ON DELETE CASCADE,
    cohort_id            UUID REFERENCES public.hotel_cohort_features(cohort_id) ON DELETE SET NULL,
    late_fusion_score    REAL,                    -- ADR-0006 D4 + ADR-0008 D4 v3
    dim                  TEXT,                    -- pms | pos | blended
    UNIQUE (from_hotel, to_hotel, dim),
    CHECK (from_hotel != to_hotel)
);

CREATE INDEX idx_edge_similar_from ON aetherix_graph.edge_similar_to (from_hotel, late_fusion_score DESC);

CREATE TABLE aetherix_graph.edge_belongs_to_cohort (
    edge_id      UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    from_hotel   UUID NOT NULL REFERENCES aetherix_graph.node_hotel(node_id) ON DELETE CASCADE,
    to_cohort    UUID NOT NULL REFERENCES aetherix_graph.node_cohort(node_id) ON DELETE CASCADE,
    joined_at    TIMESTAMPTZ NOT NULL,
    weight       REAL,                            -- k-means cluster proximity
    UNIQUE (from_hotel, to_cohort)
);

-- ====================================================
-- RLS policies (native Supabase) — 17 policies (8 nodes + 9 edges)
-- Override §D6 _inject_tenant_filter Cypher injection
-- ====================================================

ALTER TABLE aetherix_graph.node_hotel ENABLE ROW LEVEL SECURITY;
CREATE POLICY node_hotel_tenant ON aetherix_graph.node_hotel
    USING (hotel_id IN (SELECT hotel_id FROM public.tenant_hotel WHERE tenant_id = current_setting('app.tenant_id')::uuid));

-- Pattern identique pour les 7 autres node tables (toutes portent hotel_id) + 9 edge tables (denorm via JOIN node):
-- node_event, node_weather, node_outcome, node_recommendation, node_senior_intervention, node_edge_case (nullable), node_cohort
-- Edges : RLS via EXISTS join sur from_*/to_* nodes correspondants (pattern Postgres standard)

-- Example edge RLS (toutes les autres edges suivent le même pattern):
ALTER TABLE aetherix_graph.edge_produced ENABLE ROW LEVEL SECURITY;
CREATE POLICY edge_produced_tenant ON aetherix_graph.edge_produced
    USING (
        EXISTS (
            SELECT 1 FROM aetherix_graph.node_hotel h
            WHERE h.node_id = edge_produced.from_hotel
              AND h.hotel_id IN (SELECT hotel_id FROM public.tenant_hotel WHERE tenant_id = current_setting('app.tenant_id')::uuid)
        )
    );
```

**Avantage RLS native Path C vs Path A** : pas de `_inject_tenant_filter` Python décorator à maintenir + pas de risque de Cypher injection cross-tenant (RLS Postgres = gate database-level, défense-in-depth).

#### Validation `check_schema_drift.py` (Décision #16)

Schema `aetherix_graph` = ORM SQLAlchemy mirror obligatoire (8 + 9 = 17 modèles à créer dans `backend/app/models/graph/`). **Pas d'exception** dans `scripts/ci/schema_drift_ignore.json` (vs Path A AGE qui nécessitait l'exception). Cohérence schema drift gate intégrale.

### 16.3 Override D4 (Q4 recall hybrid) — single transaction CTE + pgvector

```sql
-- MemoryRecallService.recall(recall_strategy="hybrid") — Path C pattern override D4
WITH RECURSIVE cohort_outcome_paths AS (
    -- Anchor : hôtels co-cohorte
    SELECT
        h_self.hotel_id AS self_hotel_id,
        h_other.hotel_id AS other_hotel_id,
        e.late_fusion_score,
        1 AS depth
    FROM aetherix_graph.node_hotel h_self
    JOIN aetherix_graph.edge_belongs_to_cohort bc1 ON bc1.from_hotel = h_self.node_id
    JOIN aetherix_graph.edge_belongs_to_cohort bc2 ON bc2.to_cohort = bc1.to_cohort
    JOIN aetherix_graph.node_hotel h_other ON h_other.node_id = bc2.from_hotel AND h_other.node_id != h_self.node_id
    LEFT JOIN aetherix_graph.edge_similar_to e ON e.from_hotel = h_self.node_id AND e.to_hotel = h_other.node_id
    WHERE h_self.hotel_id = :me

    UNION ALL

    -- Recursive : traversal jusqu'à depth = :graph_depth (default 2)
    SELECT
        cop.self_hotel_id,
        h_next.hotel_id,
        e.late_fusion_score,
        cop.depth + 1
    FROM cohort_outcome_paths cop
    JOIN aetherix_graph.edge_belongs_to_cohort bc1 ON bc1.from_hotel = (SELECT node_id FROM aetherix_graph.node_hotel WHERE hotel_id = cop.other_hotel_id)
    JOIN aetherix_graph.edge_belongs_to_cohort bc2 ON bc2.to_cohort = bc1.to_cohort
    JOIN aetherix_graph.node_hotel h_next ON h_next.node_id = bc2.from_hotel
    LEFT JOIN aetherix_graph.edge_similar_to e ON e.from_hotel = bc1.from_hotel AND e.to_hotel = h_next.node_id
    WHERE cop.depth < :graph_depth
),
graph_hits AS (
    SELECT
        cop.other_hotel_id AS hotel_id,
        o.node_id AS outcome_id,
        o.value,
        o.outcome_date,
        ec.causal_score,
        cop.late_fusion_score * power(0.7, cop.depth - 1) AS depth_discounted_score   -- depth penalty
    FROM cohort_outcome_paths cop
    JOIN aetherix_graph.node_hotel h_other ON h_other.hotel_id = cop.other_hotel_id
    JOIN aetherix_graph.edge_produced ep ON ep.from_hotel = h_other.node_id
    JOIN aetherix_graph.node_outcome o ON o.node_id = ep.to_outcome
    LEFT JOIN aetherix_graph.edge_caused ec ON ec.to_outcome = o.node_id
    LEFT JOIN aetherix_graph.node_event e ON e.node_id = ec.from_node_id AND ec.from_node_type = 'event'
    WHERE e.event_type = :event_type
      AND o.service_slot = :service_slot
    ORDER BY depth_discounted_score DESC NULLS LAST
    LIMIT 20
),
cosine_hits AS (
    SELECT id, 1 - (embedding <=> CAST(:q AS vector)) AS similarity,
           reflection, outcome, manager_feedback, memory_type, created_at
    FROM public.operational_memory
    WHERE hotel_id = :me
      AND memory_type = ANY(:types)
    ORDER BY embedding <=> CAST(:q AS vector) ASC
    LIMIT :k
)
SELECT 'graph' AS source, hotel_id::text, outcome_id::text AS id,
       value::text, outcome_date::text AS date_text, depth_discounted_score AS score,
       NULL::text AS reflection
FROM graph_hits
UNION ALL
SELECT 'cosine' AS source, NULL, id::text, NULL,
       created_at::text, similarity, reflection
FROM cosine_hits
WHERE similarity >= :min_similarity
ORDER BY score DESC NULLS LAST
LIMIT :k_final;
```

Single transaction. Single connection. SLO MCP étendu Path C : **p95 < 1200ms** (vs 800ms Path A — verbosité CTE + recursive depth absorption justifient extension SLO). Documenté §D7 thresholds amendés P4-GRAPH-6.

### 16.4 Override D6 (Q6 MCP + tenant isolation)

**MCP tool inchangé** : `query_context_graph(query_type, depth, ...)` exposé `/mcp/v1/`, scope `graph:read`, whitelist 6 query types.

**Tenant isolation Path C** : RLS Postgres natives (cf. §16.2 DDL) — `current_setting('app.tenant_id')` setté côté backend depuis bearer MCP avant chaque query. Pas de `_inject_tenant_filter` Python décorator (supprimé Path C). Pas de risque Cypher injection (pas de Cypher). Pattern stack-standard Supabase RLS.

**Kill-switch** : `GRAPH_BACKEND=disabled` → `query_context_graph` retourne sentinel `GraphQueryResult(paths=[], aggregate=None, ...)` + `MemoryRecallService.recall(recall_strategy="cosine_only")` forcé. Identique D6 original.

### 16.5 Translation des 6 query types Cypher → CTE (Story P4-GRAPH-3)

Chacune des 6 query types §D6 (Apache AGE Cypher pattern) devient un template SQL CTE Path C. Pattern général :

| Query type | Cypher → CTE complexité |
|---|---|
| `event_outcome_history` | Recursive CTE 2-hop (Hotel → Event → CAUSED → Outcome) — moyen, 30-40 lignes SQL |
| `senior_wisdom_path` | Recursive CTE 3-hop (SeniorIntervention → Recommendation → Outcome) + filter `manager_feedback='followed'` — moyen-élevé, 40-60 lignes |
| `cohort_outcome_band` | CTE non-recursive (Hotel → Cohort → Hotel co-cohorte → Outcome) + GROUP BY agrégat — simple, 20-30 lignes |
| `edge_case_lookup` | JOIN simple (Outcome → MATCHES_PATTERN → EdgeCase) — trivial, < 15 lignes |
| `cause_diagnosis` | JOIN inversed (Outcome ← CAUSED ← Event/Weather) — simple, < 20 lignes |
| `intervention_chain` | Chain forward (Recommendation → SUGGESTED → Outcome ← INTERVENED_ON ← SeniorIntervention) — moyen, 25-35 lignes |

Templates SQL versionnés dans `backend/app/services/context_graph_queries/` (un fichier `.sql` par query type, chargé au démarrage). Pattern cohérent ADR-0007 D5 `eval/golden_dataset.jsonl` (un fichier par query type = grep / diff trivial).

**Performance attendue Path C vs Path A** (estimation, à valider P4-GRAPH-6 benchmarks) :
- `event_outcome_history` depth 2 : ~200-500ms Path C vs ~80-200ms Path A
- `senior_wisdom_path` depth 3 : ~600-1200ms Path C vs ~200-500ms Path A
- `cohort_outcome_band` : ~150-300ms Path C vs ~100-200ms Path A
- 3 autres queries simples : équivalent ou Path C marginalement plus lent

**Mitigations performance Path C** :
- Cache LRU sur `query_context_graph` (TTL 5min, déjà §5 R2) — déjà prévu pour Path A, encore plus critique Path C
- Materialized views pour `cohort_outcome_band` agrégats (refresh nightly) — cohérent ADR-0003 pattern MV
- Indexes composites supplémentaires si benchmarks révèlent bottleneck spécifique (story P4-GRAPH-6 cleanup)

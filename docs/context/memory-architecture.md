# Architecture mémoire cognitive — Modèle à deux couches

> Chargé par les sessions Architect, Dev, et Veille quand pertinent.
> **Mettre à jour :** quand une décision sur la mémoire (pgvector, Backboard, MemoryProvider) est prise ou révisée.

Objectif : passer d'un agent de "semantic search" à un agent **self-improving per-property**, dont les décisions s'améliorent en continu grâce à la preuve d'impact (recommandation suivie + outcome positif).

---

## Couche 1 — Private Memory (par hôtel)

- **Technologie :** pgvector `operational_memory` (Phase 0-1)
- **Périmètre :** strictement isolé par `hotel_id`
- **Contenu :** idiosyncrasies ultra-personnalisées — ce qui fonctionne **uniquement** pour cet hôtel (capture rate réel, préférences manager, patterns locaux non-généralisables)
- **Signal d'apprentissage :** `recommendation_accepted` + `outcome` (covers réels vs prévus) → le modèle ajuste ses prochaines suggestions pour cet hôtel
- **Interface :** `MemoryProvider.store_feedback()`, `MemoryProvider.get_hotel_context(hotel_id)`

## Couche 2 — Hive Memory (cross-hôtels anonymisé)

- **Technologie :** pgvector Supabase — tables agrégées anonymisées (Phase 0-2). Backboard.io à réévaluer Phase 3+.
- **Périmètre :** patterns agrégés et anonymisés, groupés par tags : `quartier`, `typologie` (city/resort/airport), `clientèle` (leisure/business/MICE), `segment` (4*/5*/boutique), `taille_resto`, `saison`
- **Contenu :** ce qui fonctionne **en général** pour des propriétés similaires
- **Signal d'apprentissage :** outcomes agrégés → renforce ou déprécie les patterns vectoriels (`fb_patterns`)
- **Interface :** `MemoryProvider.get_cross_hotel_patterns(tags)`, `MemoryProvider.store_hive_insight()`

## Flux d'amélioration continue

```
Recommandation → Manager accepte/rejette → outcome mesuré (J+1)
    ↓ Couche 1 : ajuste Private Memory de cet hôtel
    ↓ Couche 2 : si outcome positif → contribue à la Hive (anonymisé)
    ↓ Claude : prochaine génération enrichie des deux mémoires
```

Chaque hôtel bénéficie de son apprentissage propre **et** de la sagesse collective d'hôtels similaires — sans jamais exposer les données d'un hôtel à un autre.

## Décisions liées

- Qdrant éliminé définitivement (surdimensionné à Phase 0/1, 504 timeouts documentés)
- Architecture mono-couche rejetée : risque de contamination cross-tenant
- `MemoryProvider` abstrait dès Phase 0 pour permettre l'insertion de Backboard en Phase 3+ sans réécriture
- Features de premier ordre pour le forecast contextuel : `arrival_time`, `origin_country`, `party_size`, `LOS` (source : EHL Cindy Heo, HOS-106)

---

## Couche graphe Phase 4 (ADR-0008 — Path C Postgres recursive CTE)

**Important** : la couche graphe Phase 4 (retenue **Path C Postgres recursive CTE**, PM sign-off 06/06/2026 — cf. ADR-0008 §13) **n'est pas** une 3e couche mémoire au sens du modèle 2 couches ci-dessus. C'est une **vue indexée traversable** (8 tables nodes + 9 tables edges `aetherix_graph.*`) au-dessus des couches 1 et 2 existantes.

### Invariant

| Aspect | Couches 1-2 (existantes) | Couche graphe Phase 4 (Path C CTE) |
|---|---|---|
| **Rôle** | Source de vérité (writes + reads) | Index dérivé (reads relationnels uniquement) |
| **Storage** | pgvector `operational_memory` + `fb_patterns` | Tables `aetherix_graph.node_*` + `aetherix_graph.edge_*` (Supabase managed, same DB) |
| **Suppression** | Suppression d'une row = perte donnée | Suppression d'un node = rebuild possible depuis source |
| **Use case recall** | Cosine top-k sémantique flou | Path-find relationnel multi-hop via recursive CTE |
| **Latence MCP** | < 500ms (Décision #3) | < 1200ms p95 (SLO étendu — verbosité CTE acceptable, vs 800ms Path A AGE non retenu) |
| **Tenant isolation** | RLS Supabase | RLS Supabase native (17 policies — pas `_inject_tenant_filter` Python décorator) |

### Pourquoi pas une 3e couche

- Aucune nouvelle donnée stockée — chaque node graphe **référence** une row existante (`hotel_id`, `transaction_id`, `agent_action_log` JSONB events) via FK.
- `INSERT ... ON CONFLICT DO UPDATE` idempotent → re-build du graphe depuis sources = same result.
- Suppression d'un node ne supprime pas la source data ; suppression d'une row source orpheline le node (worker nightly nettoie).
- Décision #2 invariant (Private + Hive, isolation tenant strict) inchangé. Les tables `node_*` portent `hotel_id` (RLS Supabase native cohérent `docs/mesh-architecture.md` §4 *"hotel_id server-side"*).

### Recall hybride — extension `MemoryRecallService` ADR-0002

Le contract `MemoryRecallService.recall()` Phase 0-3 reste backward-compat. Phase 4 ajoute un paramètre :

```python
async def recall(
    self,
    hotel_id: str,
    query_text: str,
    *,
    k: int = 5,
    ...,
    recall_strategy: Literal[
        "cosine_only",       # ADR-0002 baseline — default Phase 0-3 callers
        "path_find",         # Phase 4 — traverse graph depuis context
        "hybrid",            # Phase 4 — union des deux, rerank combined score
        "cohort_traversal",  # Phase 4 — exploite SIMILAR_TO + BELONGS_TO_COHORT
    ] = "cosine_only",
    graph_depth: int = 2,
) -> list[MemoryHit]: ...
```

Caller ne passant pas `recall_strategy` → comportement ADR-0002 identique. Zéro régression.

### Cohort matching v3 — extension ADR-0006 D4

ADR-0006 D4 = late-fusion **scalar** `α × cos_pms + β × cos_pos`. ADR-0008 promeut v3 = path traversal multi-dim ajoutant un 3e terme `ε × path_match_score` calibré pilote. Gate runtime auto-disable v3 si Day-7 MAPE_v3 > MAPE_v2 — fallback v2.

### Foundation Anima Phase 4

3 node types réservés (`Guest`, `Stay`, `Sentiment`) + 4 edge types (`HAS_STAY`, `EXPERIENCED`, `EXPRESSED`, `MATCHES_SEGMENT`) **non créés** Phase 4, documentés pour Anima Phase 4 quand DPIA passé (Décision #20). Le param `scope` Anima (working / current_stay / full_history / segment) devient un Cypher temporal filter. `EXPERIENCED` edge connecte `Stay` Anima → `Outcome` Aetherix = lingua franca cross-nœud Mesh.

### Détail complet

Voir [`docs/adr/0008-context-graph.md`](../adr/0008-context-graph.md) (Q1-Q7 tranchés, DDL Apache AGE, 6 query types whitelist MCP, eval gate `context_graph_query`).

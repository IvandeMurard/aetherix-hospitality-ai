# Architecture mémoire cognitive — Modèle à deux couches

> Chargé par les sessions Architect, Dev, et Veille quand pertinent.

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

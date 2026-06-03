# Data Conventions — Identifier Types

> Source de vérité pour les conventions d'identifiants cross-tables.
> Toute décision de migration → promouvoir en §Décisions architecturales dans CLAUDE.md.

---

## Convention cible

| Champ | Type Python / SQLAlchemy | Sémantique | Exemple |
|-------|--------------------------|------------|---------|
| `id` (PK) | `UUID(as_uuid=True)` | Identifiant primaire stable, opaque | `550e8400-e29b-41d4-a716-446655440000` |
| `tenant_id` | `String` slug humain | Identifiant lisible partagé entre PMS et Aetherix — stable, URL-safe | `demo_hotel`, `MUC` |
| `property_id` | `UUID(as_uuid=True)` | Alias interne de l'ID de propriété cross-tables | UUID |
| `hotel_id` | `String` slug humain | Alias de `tenant_id` dans le contexte MCP (MCPApiToken, OperationalMemory, AgentActionLog) | `demo_hotel` |

**Règle fondamentale :** ne jamais comparer un `UUID` avec un `String` sans conversion explicite documentée.
PostgreSQL accepte silencieusement les casts implicites via asyncpg — ces comparaisons ne lèvent pas d'erreur
mais violent le contrat de type et rendent le schéma illisible.

---

## État actuel des drifts (audit HOS-163, 2026-05-07)

| Modèle | `tenant_id` | `id` / `property_id` | `hotel_id` | Note |
|--------|-------------|----------------------|------------|------|
| `RestaurantProfile` | `String` ✅ | `String` ⚠️ (PK devrait être UUID) | — | PK String = dette historique |
| `DemandAnomaly` | `UUID` ✅ | `UUID` ✅ | — | |
| `StaffingRecommendation` | `UUID` ✅ | `UUID` ✅ | — | |
| `ConversationalQuery` | `UUID` ✅ | `UUID` ✅ | — | |
| `MCPApiToken` | — | `UUID` ✅ | `String` ✅ | `hotel_id` = alias tenant_id |
| `OperationalMemory` | — | `UUID` ✅ | `String` ✅ | `hotel_id` = alias tenant_id |
| `AgentActionLog` | — | `UUID` ✅ | `String` ✅ | `hotel_id` = alias tenant_id |
| `PMSSyncLog` | `String` ✅ | `Integer` (PK auto) | — | |
| `CaptationBaseline` | `String` ✅ | `Integer` (PK auto) | — | |
| `FBPattern` | `String` ✅ | `UUID` ✅ | — | |
| `TrainingRun` | — | `UUID` ✅ | — | `property_id` = `String` ⚠️ |
| `WeatherForecast` | `String` ✅ | `Integer` (PK auto) | — | `property_id` = `String` ⚠️ |
| `RecommendationCache` | `String` ✅ | `Integer` (PK auto) | — | |

---

## Mismatches connus dans les services

Listés par `scripts/audit_id_types.py`. Voir output de l'audit pour les lignes exactes.

### Pattern A — `tenant_id (String) == str(UUID)` dans les clauses WHERE
- **alert_dispatcher.py** : `RestaurantProfile.tenant_id == str(recommendation.property_id)`
  — `property_id` (UUID sur `StaffingRecommendation`) est casté en String pour rejoindre `tenant_id`.
  Migration cible : aligner `StaffingRecommendation.property_id` → FK sur `restaurant_profiles.tenant_id` (String).

### Pattern B — `property_id (UUID) == .id (String)` dans les clauses WHERE
- **action_logger.py**, **query_parser.py** : `StaffingRecommendation.property_id == profile.id`
  — `profile.id` est une PK String sur `RestaurantProfile` ; `property_id` est UUID.
  Migration cible : même que Pattern A.

### Pattern C — `str(UUID)` dans les params d'INSERT raw SQL
- **anomaly_detection.py** : `"tenant_id": str(tenant_id)`, `"property_id": str(property_id)` dans le bulk upsert
  — `DemandAnomaly.tenant_id` et `.property_id` sont des colonnes UUID ; passer `str()` est accepté par asyncpg
  mais viole le contrat de type.
- **recommendation_formatter.py** : `"tenant_id": str(tenant_id)`, `"property_id": str(property_id)`,
  `"anomaly_id": str(anomaly_id)`, `"id": rec_id` où `rec_id = str(uuid.uuid4())`
  — même problème sur `staffing_recommendations`.

---

## Plan de migration (Phase 3+)

Priorité basse — aucun bug runtime connu (asyncpg caste silencieusement). À traiter avec une migration Alembic
dédiée quand le premier pilote réel oblige à nettoyer le schéma.

1. Migrer `RestaurantProfile.id` de `String` → `UUID` (breaking change, coordonner avec les FK).
2. Ajouter FK explicite `StaffingRecommendation.property_id → restaurant_profiles.id` (UUID).
3. Supprimer les `str()` dans les dicts de bind params des raw SQL (utiliser uuid.UUID directement).
4. Renommer `hotel_id` → `tenant_id` sur `MCPApiToken`, `OperationalMemory`, `AgentActionLog`
   pour homogénéiser (ou documenter `hotel_id` comme alias permanent dans les tables MCP-facing).

> Script de vérification : `python scripts/audit_id_types.py` — doit lister 0 mismatch post-migration.

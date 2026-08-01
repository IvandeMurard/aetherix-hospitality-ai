# Decision Ledger — historique opérationnel outcome-tracked

> **Story** : [HOS-317](https://linear.app/hospitalityagent/issue/HOS-317) (Story 16.16, Epic 16 Proof & Visibility)
> **Origine** : review adverse externe (GPT, 20/07/2026) — Critical **C5** + Finding **F6** + Architectural Decision **AD2**
> **Statut de la brique** : **Built** au sens de [`status-taxonomy.md`](status-taxonomy.md) — le schéma est en base, les deux write-paths l'alimentent, la requête bout-en-bout est couverte par des tests. **0 utilisateur réel** : aucune ligne de ce ledger n'a encore été produite par un manager en pilote.
> **Voisins** : [`memory-architecture.md`](memory-architecture.md) (les deux couches mémoire) · [`data-conventions.md`](data-conventions.md) (`tenant_id` / `hotel_id`) · ADR-0003 (`agent_action_log`) · ADR-0007 §D6 (abstention) · ADR-0009 (guardrails runtime)

**Pourquoi ce fichier est une note technique et pas un ADR** : Epic 16 gèle les nouveaux ADRs (`CLAUDE.md` §Points d'attention 3), et le numéro ADR-0013 est réservé au modèle d'interaction event-driven (`open-decisions.md`). La story elle-même autorise « ADR **ou** note technique ». Rien ici n'ouvre une décision d'architecture nouvelle : c'est la mise en cohérence de tables qui existaient déjà.

---

## 1. Le constat

L'actif produit qui compte n'est pas « la mémoire » au sens vector-retrieval. C'est l'historique lié :

> contexte source → recommandation émise → réponse manager → action appliquée → outcome mesuré

Cet historique **existait déjà en totalité**, éparpillé dans cinq tables, sans arête explicite entre la recommandation et la réponse du manager. La conséquence concrète : la question « pour la recommandation X, qu'a répondu le manager et que s'est-il réellement passé ? » n'était pas exprimable en SQL. Elle demandait un `LIKE` sur du texte libre.

C'est ce que ferme HOS-317. **Une colonne, aucune table nouvelle.**

---

## 2. Audit des tables existantes (AC2)

État **avant** HOS-317, table par table.

| Table | Ce qu'elle portait déjà | Ce qui manquait |
|---|---|---|
| `demand_anomalies` | Contexte source : `triggering_factors` (JSONB), `deviation_pct`, `direction`, `expected_demand` vs `baseline_demand`, `detected_at` | Rien — le contexte est complet et déjà relié par FK |
| `staffing_recommendations` | Reco émise (`message_text`, `recommended_headcount`, `predicted_covers`), dispatch (`dispatched_at`, `dispatch_channel`), réponse **dashboard** (`action`, `actioned_at`), outcome (`actual_covers`, `actual_covers_source`, `actual_covers_at`). FK `anomaly_id` → contexte | La réponse manager **WhatsApp** n'atterrit jamais ici : `action` n'est écrit que par `action_logger` (chemin dashboard) |
| `operational_memory` | Réponse manager WhatsApp (`manager_feedback`, `outcome`, `memory_type='feedback'`) et outcome mesuré (`memory_type='ground_truth'`), `request_id` vers `agent_action_log` | **La FK vers la recommandation.** Le lien vivait comme texte dans `reflection` : `[rec=<uuid>] outcome=…`, retrouvé par `LIKE`. Les lignes `ground_truth` n'avaient même pas ce marqueur — seulement un `request_id` partagé, absent hors tour WhatsApp entrant |
| `agent_action_log` | Confiance / abstention (`abstention_reason`, `abstention_layer`), trips guardrail typés (`error_code`), latence, `request_id` | Rien — joignable via `request_id` **une fois** l'arête ci-dessus posée |
| `recommendation_cache` | Cache legacy `prediction_data` / `staffing_recommendation` par `(tenant_id, target_date)`, `is_pushed` | Hors boucle : pas de FK vers `staffing_recommendations`, granularité à la journée et non à la décision. **Volontairement laissé hors ledger** (voir §5) |
| `fb_patterns` | Patterns vectoriels cross-hôtels, `feedback_status`, `outcome_description` | Hors boucle par construction : couche 2 (Hive), agrégée et anonymisée — pas un journal de décisions individuelles |

### Verdict

Une seule arête manquait. Aucune table nouvelle n'était justifiée.

```sql
ALTER TABLE operational_memory ADD COLUMN recommendation_id UUID
    REFERENCES staffing_recommendations (id) ON DELETE SET NULL;
```

`ON DELETE SET NULL` et jamais `CASCADE` : la réponse d'un manager et un outcome mesuré sont des **pièces d'audit**. Ils survivent à la recommandation qu'ils commentent.

Migration : [`supabase/migrations/20260801100000_decision_ledger_link.sql`](../../supabase/migrations/20260801100000_decision_ledger_link.sql) · miroir ORM dans `backend/app/db/models.py` (Décision #16 — l'ORM est le miroir exact des migrations).

### Backfill

Le lien existait déjà en base sous forme de texte : il est **récupéré**, pas perdu.

1. Lignes `feedback` — extraction du marqueur `[rec=<uuid>]` en tête de `reflection`, avec garde `EXISTS` pour ne pas violer la FK sur des recommandations supprimées.
2. Lignes `ground_truth` — jointure sur `(request_id, hotel_id)` avec la ligne `feedback` du même tour entrant, qui vient d'être rattachée à l'étape 1.

---

## 3. Le schéma consolidé (AC1)

Pour chaque décision, les cinq legs et où ils vivent :

| Leg | Champ(s) | Source |
|---|---|---|
| **Contexte source + qualité des données** | `triggering_factors`, `deviation_pct`, `direction`, `context_detected_at` | `demand_anomalies` |
| **Recommandation émise** | `message_text`, `recommended_headcount`, `predicted_covers`, `window_start/end`, `roi_net`, `dispatched_at`, `dispatch_channel` | `staffing_recommendations` |
| **Réponse manager** (accept / reject / modify) | `manager_response`, `manager_responded_at`, `manager_response_channel` | `staffing_recommendations.action` (dashboard) **ou** `operational_memory.manager_feedback` (WhatsApp) |
| **Outcome mesuré** | `actual_covers`, `actual_covers_source`, `actual_covers_at`, `outcome_memory_id`, `abs_pct_error` | `staffing_recommendations` + ligne `ground_truth` |
| **Timestamps** | `context_detected_at` → `recommended_at` → `dispatched_at` → `manager_responded_at` → `actual_covers_at` | les trois tables |
| **Confiance / abstention** | `abstention_reason`, `abstention_layer`, `agent_status`, `agent_error_code` | `agent_action_log`, joint par `request_id` |

**Priorité des deux canaux de réponse** : la colonne `action` du dashboard l'emporte sur la ligne mémoire WhatsApp. C'est l'accept/reject explicite, là où la ligne mémoire couvre aussi « modified ». La trace WhatsApp n'est pas perdue pour autant — `feedback_memory_id` reste renseigné.

```
demand_anomalies ──FK anomaly_id──> staffing_recommendations
                                              │
                              FK recommendation_id (HOS-317)
                                              │
                                    operational_memory
                                    ├── memory_type='feedback'      → réponse manager
                                    └── memory_type='ground_truth'  → outcome mesuré
                                              │
                                    request_id (ADR-0003)
                                              │
                                      agent_action_log  → abstention / trip typé
```

---

## 4. La requête bout-en-bout (AC3)

Deux surfaces, une seule forme.

**Runtime** — `backend/app/services/decision_ledger.py`, lecture seule :

```python
record = await DecisionLedgerService(db).get_decision(rec_id, tenant_id=hotel_id)
record.manager_response        # 'followed' | 'rejected' | 'accepted' | …
record.manager_response_channel # 'dashboard' | 'whatsapp'
record.actual_covers            # outcome réel
record.abs_pct_error            # |prévu − réel| / réel, en %
record.is_closed                # répondue ET mesurée
```

SQLAlchemy portable, sans `LATERAL` : les tests tournent sur SQLite. `tenant_id` est une garde d'isolation optionnelle — à passer sur tout chemin où le tenant de l'appelant est connu.

**Analyste / démo** — la vue `decision_ledger` livrée par la migration, une ligne par recommandation émise. Elle alimente directement [HOS-310](https://linear.app/hospitalityagent/issue/HOS-310) (closed-loop demo). Elle est créée `WITH (security_invoker = true)` : sans cette clause une vue s'exécute avec les droits de son propriétaire et **contournerait silencieusement la RLS** des tables sous-jacentes (migrations `20260515000000` / `20260515100000`) — une lecture par tenant deviendrait une fuite cross-propriétés.

Couverture : `backend/tests/services/test_decision_ledger.py` (15 tests) — boucle complète, priorité dashboard/WhatsApp, recommandation sans réponse, isolation tenant sur `get_decision` **et** sur la jointure `agent_action_log`, division par zéro sur `actual_covers = 0`, et les deux write-paths qui estampillent l'arête.

---

## 5. Ce que le ledger ferme, et ce qu'il ne ferme pas

Section volontairement explicite : la story naît d'une review qui reprochait au projet de sur-revendiquer. Il serait absurde de la clore par une sur-revendication.

### Fermé

- Recommandation → réponse manager, **quel que soit le canal** (dashboard ou WhatsApp), en une jointure.
- Recommandation → outcome mesuré, y compris pour les lignes `ground_truth` écrites hors tour WhatsApp entrant.
- Décision → abstention / trip guardrail typé de ce tour-là (`request_id`, NFR2 / Décision #27).
- Erreur de prévision **par décision** (`abs_pct_error`), et la population des boucles réellement fermées (`closed_only=True`) — la seule sur laquelle une affirmation de qualité soit honnête.

### Non fermé — assumé, à ne pas revendiquer

| Manque | Pourquoi on ne l'a pas comblé ici |
|---|---|
| **« Action effectivement appliquée » ≠ réponse manager** | `accepted` est une intention déclarée. Personne ne mesure aujourd'hui si les 2 serveurs supplémentaires ont réellement été planifiés. Le combler suppose une intégration planning/POS (Phase 4, Décision #23) — ajouter des colonnes `applied_*` sans écrivain serait du schéma mort |
| **Confiance à l'émission** | Le pipeline anomalie est baseline-deviation, pas Prophet : aucune confiance n'existe au moment du formatage (`recommendation_formatter`). `agent_action_log` porte la confiance des *appels agent*, pas celle des recos issues du scan batch. Colonne volontairement non ajoutée |
| **Qualité des données du contexte** | Approchée par `triggering_factors` + `actual_covers_source` (`manager_feedback` vs `manager_feedback_flagged`, HOS-250) + les trips `feedback.ingestion`. Pas de score de qualité de première classe |
| **`recommendation_cache` reste hors boucle** | Cache legacy à granularité journalière, sans FK vers la décision. Le rattacher demanderait de le migrer, pas de le lier |
| **L'apprentissage** | Le ledger **enregistre**. Il ne prouve pas que l'agent s'améliore. Voir §6 |

---

## 6. Vocabulaire (AC4)

**« Decision Ledger » / « outcome-tracked operational history »** — et non « self-improving memory » / « mémoire auto-améliorante », tant que l'apprentissage n'est pas démontré sur données réelles.

La distinction n'est pas cosmétique :

- **Enregistrer** un outcome est un fait vérifiable en base. C'est ce qui est livré.
- **S'améliorer** grâce à lui est une affirmation de performance, qui exige une mesure avant/après sur des décisions réelles. Ce n'est pas livré, et le [protocole de preuve pré-enregistré](https://linear.app/hospitalityagent/issue/HOS-316) (HOS-316) est justement ce qui devra la trancher.

Surfaces alignées : `README.md`, `backend/app/mcp_core.py` + `backend/app/api/routes/wellknown.py` (descriptions de tools publiques, manifeste `.well-known`), `docs/context/memory-architecture.md`. Non touchés volontairement : `docs/adr/0002-*.md` (un ADR est un enregistrement daté, on ne le réécrit pas) et `docs/context/vision-future.md` (explicitement étiqueté vision Phase 5).

Cohérent avec la Décision #33 (gate honnêteté métriques) et la taxonomie `Built / Shadow-mode / Synthetic PoC / Design / Research`.

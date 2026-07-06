# ADR-0012 — Hospitality Agentic Mesh: Signal Contract

**Date :** 2026-07-05 (r2 : 2026-07-05 · r3 : 2026-07-05 — révisions suite retours Ivan + second avis externe) · **Accepted :** 2026-07-06
**Status :** Accepted
**Décideurs :** Ivan de Murard
**Contexte :** Reframing stratégique 05/07/2026 — *"la vraie IP n'est ni le LLM, ni MCP, ni le forecast. C'est le signal model."*
**Portée :** Mesh entier (Aetherix, Tacet, Anima, Orchestrateur), pas Aetherix seul — cf. §D-scope. Vit dans ce repo pour l'instant, comme `mesh-architecture.md` (Décision #25 Étape 1 statu quo).

---

## 1. Contexte

L'audit des sujets architecturaux couverts (mémoire, signaux, ontologie, boucle d'action, orchestration, position dans la chaîne de valeur) montre que six sujets sur sept ont déjà une réponse documentée ailleurs dans le repo :

| Sujet | Statut | Où |
|---|---|---|
| Mémoire | ✅ Traité | `docs/context/memory-architecture.md` (2 couches Aetherix) + `docs/mesh-architecture.md` §Anima (4 couches temporelles + confidence-weighted claims, ADR-0011 D2) |
| Boucle d'action | ✅ Traité (vision) / 🟡 partiel (implémenté) | ADR-0004 (agentic loop orchestrator), Décision #6 (no auto-actions), `docs/context/vision-future.md` (canonical use case bout-en-bout) |
| Couche d'orchestration | ✅ Traité | ADR-0004 — Aetherix = execution node, Orchestrateur = séquenceur MCP séparé (Décision #19) |
| Position chaîne de valeur | ✅ Traité | `docs/mesh-architecture.md` §1 (Mesh opère hors des 6 couches Commerce Hub du PMS) |
| Ontologie | 🟡 Partiel, implicite | Événements Anima déjà nommés (`check_in`, `complaint`, `flight_status`, `sentiment_signal`, `preference_observed`), scores Tacet, mais jamais unifiés |
| **Signaux** | 🔴 **Dette sémantique** | Le mot *"signal"* est déjà utilisé de façon incohérente à trois endroits : Tacet transforme des données chaotiques en *"signaux structurés"* (`mesh-architecture.md`), Anima nomme un event type `sentiment_signal`, Aetherix parle de *"signal d'apprentissage"* pour `recommendation_accepted + outcome` (`memory-architecture.md`). **Ce n'est pas seulement un vide — c'est une dette sémantique existante.** |

Cet ADR ne comble pas un trou : il **résorbe une incohérence terminologique déjà présente**, en donnant un contrat unique à ce que Tacet, Anima et Aetherix font déjà informellement chacun de leur côté.

### Historique des révisions

- **r1** (05/07) : premier draft — `Signal` écrit directement par chaque nœud, `confidence`/`decay_rate` réutilisés tels quels d'ADR-0011, portée `hotel_id` stricte.
- **r2** (05/07) : introduit `Observation → Signal → SignalComposite`, sépare `valid_until`/`decay_rate`, ajoute un modèle de calibration à 3 niveaux.
- **r3** (05/07, cette version) — second audit externe (lecture directe d'ADR-0004/0011, pas seulement des résumés) a identifié trois défauts dans r2 :
  1. **`Observation` intermédiaire obligatoire pour tout nœud** viole ADR-0004 D1 (atomic tools, bounded context) — Tacet (`get_room_risk_score`) et Anima (`get_emotional_risk`) interprètent **déjà** dans leur domaine ; une fonction de promotion centralisée duplique une interprétation qui existe déjà.
  2. **`decay_rate` gardé comme champ optionnel sur `Signal`** rouvre la confusion qu'il visait à résoudre — aucun cas d'usage v0.1 ne le justifie (YAGNI). Reste exclusivement une propriété d'ADR-0011 D2 (Semantic claims Anima).
  3. **La frontière perception/décision restait floue en prose** (D3 r2 parlait de "transition d'état actionnable" porté par le composite lui-même) — même si le schéma JSON ne portait déjà plus de champ `candidate_decision`, la prose recréait l'ambiguïté qu'ADR-0004 D5 avait tranchée en dépréciant `get_recommendations_with_memory_context`.

r3 corrige les trois et repositionne le document au niveau Mesh (§D-scope).

---

## 2. Décision proposée

### D-scope — Positionnement Mesh, pas Aetherix

Ce contrat n'est pas une abstraction interne à Aetherix : c'est le vocabulaire que **tout nœud du Mesh** (Tacet, Anima, Aetherix, Orchestrateur) utilise pour s'exposer à l'Orchestrateur sans que celui-ci ait à connaître la sémantique propriétaire de chaque nœud. Sans ce contrat, l'Orchestrateur doit apprendre à parler `room_risk_score` (Tacet), `ProfileSnapshot` (Anima) et `operational_memory` outcome (Aetherix) comme trois langages distincts — ce qui contredit l'ambition de composabilité du Mesh (ADR-0004).

Vit dans `aetherix-hospitality-ai/docs/adr/` pour l'instant, au même titre que `mesh-architecture.md`, tant que la migration multi-repo (Décision #25) n'a pas atteint son Étape 2.

### D0 — Pipeline conceptuel

```
Event (monde réel — hors Mesh)
        ↓ interprété DANS le bounded context du nœud qui le possède (ADR-0004 D1)
DomainSignal — namespaced par domaine, émis par le nœud propriétaire
        ↓ composition cross-domaine (Orchestrateur — ADR-0004 D7)
SignalComposite — description de situation, significance_score continu
═══════════════════ FRONTIÈRE PERCEPTION / DÉCISION ═══════════════════
        ↓ seuil calibré (D-calibration), appliqué par l'Orchestrateur
RecommendationCandidate — HITL (Décision #6)
```

**Pas d'objet `Observation` intermédiaire.** Chaque nœud a autorité pour interpréter les événements de son propre domaine et émettre directement un `DomainSignal` — c'est littéralement sa responsabilité de bounded context (Tacet interprète l'environnemental, Anima interprète le guest, Aetherix interprète le F&B). Aucune fonction de promotion centralisée n'est nécessaire ni souhaitable.

### D1 — Autorité par bounded context (namespace = permission)

| Nœud | Namespace autorisé | Exemple `DomainSignal` | Interprétation déjà existante (source) |
|---|---|---|---|
| Tacet | `environmental.*` | `environmental.room_noise_risk` | `get_room_risk_score` (`mesh-architecture.md` §2) |
| Anima | `guest.*` | `guest.emotional_recovery_risk` | `get_emotional_risk` (`mesh-architecture.md` §Anima) |
| Aetherix | `fnb.*` | `fnb.late_service_capacity_pressure` | Forecast + staffing (ADR-0004 D1, bounded context F&B) |
| Orchestrateur | `operational.*` | `operational.arrival_concentration`, `operational.cancellation_wave` | Événements PMS cross-domaine (webhook, décision ouverte event-driven Phase 4-5) — pas propriété d'un seul nœud, donc porté par l'Orchestrateur, pas par le PMS lui-même (système externe, pas un nœud Mesh) |
| Orchestrateur | `orchestrator.override` | `orchestrator.manual_context_override` | Canal tacite manager bidirectionnel (item d, open-decision event-driven) — pas domain-owned, priorité maximale |

**Invariant :** un nœud n'émet jamais de `DomainSignal` hors de son propre namespace. Ceci n'est pas une contrainte technique arbitraire — c'est directement l'invariant *"atomic tools, bounded context"* d'ADR-0004 D1 et la séparation *"Anima comprend, l'Orchestrateur décide"* d'ADR-0011 D1, appliqués au niveau du contrat perceptif plutôt qu'au niveau de l'API MCP.

Le suffixe `signal_type` (ex : `room_noise_risk`) n'est **pas** un enum fermé maintenu de façon centrale — chaque nœud peut introduire de nouveaux types dans son namespace sans coordination Mesh-wide. Seul le namespace racine (`environmental`, `guest`, `fnb`, `operational`, `orchestrator`) est un invariant architectural.

### D2 — Schéma `DomainSignal`

```json
{
  "signal_id": "uuid",
  "hotel_id": "required — jamais cross-tenant (RLS invariant, mesh-architecture.md §4)",
  "source_node": "tacet | anima | aetherix | orchestrator",
  "domain": "environmental | guest | fnb | operational | orchestrator",
  "signal_type": "namespaced string, ex: room_noise_risk",
  "subject": "ex: room:301 · guest:pseudonymous-id · service:dinner",
  "confidence": "0.0–1.0",
  "observed_at": "timestamp",
  "effective_from": "timestamp, optionnel — défaut = observed_at",
  "expires_at": "timestamp, optionnel — péremption dure",
  "evidence_refs": "pointeurs opaques vers l'interprétation interne du nœud — jamais le payload brut",
  "payload": "structured, domain-specific"
}
```

**Pas de `decay_rate` en v0.1.** `decay_rate` reste exclusivement un champ de `ProfileSnapshot` (Semantic claims Anima, ADR-0011 D2) — une confiance qui s'érode *doucement* sur des connaissances persistantes. Un `DomainSignal` répond à *"qu'est-ce qui est pertinent maintenant, pour cet hôtel"* — sa validité est bornée par `expires_at`, pas par une décroissance continue.

**Limite assumée** : `expires_at` seul est une approximation grossière pour un signal à décroissance naturellement progressive (ex : `guest.emotional_recovery_risk` s'atténue sur quelques heures plutôt que d'expirer net). Pas de cas d'usage v0.1 identifié qui l'exige — si le pilote en démontre un, ajouter un champ `decay_policy` explicite sur `DomainSignal` à ce moment-là, **distinct** de `decay_rate` (qui reste Anima Semantic claims only). YAGNI assumé, pas nié.

### D3 — Composition (`SignalComposite`)

```json
{
  "composite_id": "uuid",
  "hotel_id": "...",
  "contributing_signals": ["signal_id", "..."],
  "composition_rule": "co-occurrence | weighted-sum | rule-based (v1) — modèle appris (Phase 5, Learning Engine ADR-0011 D4)",
  "significance_score": "0.0–1.0, continu"
}
```

**Invariant non-négociable : `SignalComposite` ne contient aucun champ `actionable`, `threshold_crossed`, ou `candidate_decision`.** Il décrit une situation perçue à partir de signaux cross-domaine — rien de plus. Lui donner la responsabilité de décider franchirait la frontière perception/décision et recréerait exactement l'antipattern qu'ADR-0004 D5 a supprimé en dépréciant `get_recommendations_with_memory_context` : de l'orchestration dissimulée dans une abstraction intermédiaire.

**Composition Phase 3-4 (v1)** : règles explicites, auditables (cohérent Décision #5 reasoning explicite), calculées côté Orchestrateur. Ex : `environmental.room_noise_risk(0.87) + operational.cancellation_wave(0.6) + fnb.low_confidence_forecast(0.4)` → composite "demande instable" avec `significance_score` dérivé.
**Composition Phase 5 (v2)** : pondération apprise via Learning Engine (ADR-0011 D4).

### D-calibration — Qui calibre le seuil de décision de l'Orchestrateur ?

La question n'est pas *"qui a le droit d'écrire un signal"* (réglée par D1 — le bounded context) mais *"qui décide qu'un `significance_score` est assez élevé pour justifier une recommandation, pour cet établissement précis"*. Trois niveaux hiérarchisés, cohérents avec des décisions déjà actées :

| Niveau | Source | Mécanisme | Décision existante réutilisée |
|---|---|---|---|
| 1. Défaut | **Prior de cohorte (Hive)** | Seuil hérité de propriétés similaires — day-1, pas de configuration manuelle requise | Décision #2/#26 D3, Federated HiveMemory |
| 2. Apprentissage | **Recalibration locale** | Le seuil se resserre/desserre selon `recommendation_accepted`/rejected + outcome mesuré | Boucle Private Memory existante |
| 3. Override | **Manager explicite** | `orchestrator.override` (D1) — poids maximal, prime sur 1 et 2 pour l'occurrence concernée | Item (d), décision ouverte event-driven Phase 4-5 |

**Ce que ça évite** : demander à un nouvel établissement de configurer ses seuils en autonomie dès le jour 1, ce qui exigerait une maîtrise opérationnelle qu'un nouveau client n'a pas encore formalisée avec Aetherix, et contredirait la promesse cold-start de Décision #2/#26. Le client garde l'autorité *corrective* (niveau 3, toujours disponible, toujours prioritaire), pas la charge de configuration initiale.

### D4 — Portée établissement + réinjection Hive

`hotel_id` obligatoire sur tout `DomainSignal` et tout `SignalComposite` — aucune exception, aucun signal brut cross-tenant (RLS invariant, Décision #2, `mesh-architecture.md` §4).

La calibration (niveau 1, D-calibration) peut consulter un `CollectivePattern` — objet agrégé, anonymisé, sans donnée hôtel-identifiable — comme *contexte/prior*, jamais comme signal en propre :

| Objet | Nœud | Déjà existant sous quel nom |
|---|---|---|
| `CollectivePattern` (F&B) | Aetherix Hive Memory | `fb_patterns` (Décision #2) |
| `CollectivePattern` (guest) | Anima Segment | Hive prior (Décision #26 D3, confirmé ADR-0011 D3/D4 : *"fédération de priors/policies appris, pas de données"*) |

`CollectivePattern` n'est pas un nouveau store — c'est le nom ontologique commun donné à ce que `fb_patterns` et le Hive prior Anima font déjà. Il nourrit la calibration (niveau 1), jamais la composition : un `SignalComposite` ne peut agréger que des `DomainSignal` du même `hotel_id` ; il peut être *pondéré* par un `CollectivePattern`, jamais *composé* avec lui. Ceci confirme et durcit ce qu'ADR-0011 avait déjà tranché — pas une nouvelle décision.

### D5 — Décision déclenchée (`RecommendationCandidate`)

```
SignalComposite → Orchestrateur applique le seuil calibré (D-calibration)
    ↓ si franchi
RecommendationCandidate: { type, target_node, human_review_required: true }
    ↓ HITL (WhatsApp / dashboard) → Manager approve/reject
    ↓ outcome capturé (triple de-identified, ADR-0011 D4) → recalibre le seuil (niveau 2)
```

`RecommendationCandidate` est un objet distinct de `SignalComposite`, produit exclusivement par l'Orchestrateur — jamais par un nœud, jamais par le composite lui-même. Ceci ferme la boucle de `docs/context/vision-future.md` (*Signal Detection → Orchestration → HITL → Feedback*) en donnant un schéma concret à l'étape 1, jusqu'ici seulement narrative.

---

## 2bis. Points de rattachement à l'architecture existante (implémentation Phase 4)

Non-bloquants pour l'acceptation — à respecter au moment de l'implémentation, pour éviter de dupliquer ce qui existe déjà.

- **Monitoring (ADR-0009 / Décision #27)** : la santé de l'émission de signaux (volume par nœud, dérive de `confidence`, fréquence anormale d'`orchestrator.override`) doit s'intégrer au heartbeat/dead-man's switch et à l'alerting error-rate déjà construits — pas un second système de surveillance parallèle.
- **Outcome-capture (ADR-0011 D4, Story 3.5 HOS-246)** : `SignalComposite.significance_score` + le seuil de calibration appliqué (D-calibration) sont directement le `context-features`/`propensity` attendus par l'instrumentation de capture d'outcome déjà actée — l'implémentation doit brancher là-dessus, pas créer un second pipeline de logging.
- **Versioning MCP (ADR-0004 D5)** : exposer `DomainSignal` dans les tools MCP existants (`get_room_risk_score`, `get_emotional_risk`) est un changement de schéma cassant, soumis à la même discipline `v0`/`v1` que le reste du Mesh.
- **Déclencheur d'implémentation** : ce contrat ne prend sa pleine valeur que sous ingestion événementielle (décision ouverte "Interaction model event-driven Phase 4-5") — sous le cron quotidien actuel, un `SignalComposite` formé en cours de journée n'a aucun moment pour compter avant le batch du lendemain. L'implémentation de cet ADR est donc de fait gated par le tranchage de cette décision ouverte, pas seulement "Phase 4" au sens large.
- **Gel terminologique** : une fois `Accepted`, `DomainSignal` / `SignalComposite` / `RecommendationCandidate` / `CollectivePattern` sont figés. Tout changement de vocabulaire futur passe par un amendement d'ADR explicite, pas un renommage silencieux en cours d'implémentation (ce document a déjà été renommé trois fois pendant sa propre revue — pas un précédent à répéter après acceptation).

---

## 3. Ce que cet ADR NE tranche PAS (décisions ouvertes dérivées)

- **Valeurs de seuil de calibration** par type de composite — nécessite données pilote (§D-calibration)
- **Algorithme de composition v2 appris** — dépend du Learning Engine Phase 5 (ADR-0011 D4)
- **Format d'ingestion PMS webhook** — dépend du tranchage de "Interaction model event-driven Phase 4-5" (`open-decisions.md`)
- **Stockage physique** (nouvelle table `domain_signals`/`signal_composites` vs extension `operational_memory`/`agent_action_log` JSONB) — à trancher à l'implémentation (Phase 4)
- **`decay_policy` sur `DomainSignal`** — non introduit faute de cas d'usage v0.1 ; à réévaluer si le pilote démontre un besoin de décroissance progressive (cf. D2)
- **Extension des namespaces** (ex : `pos.*` pour l'ingestion POS Phase 4, ADR-0006) — le principe (namespace = bounded context du nœud propriétaire) s'applique, la liste exacte se complète à l'implémentation

---

## 4. Alternatives rejetées

| Alternative | Raison du rejet |
|---|---|
| Pas de contrat unifié — chaque nœud garde son vocabulaire | Statu quo — empêche la composition cross-source ; **dette sémantique déjà constatée** (§1), pas juste un risque théorique |
| `Observation` intermédiaire obligatoire, promue par une fonction d'interprétation centralisée (r2) | Viole ADR-0004 D1 (atomic tools, bounded context) — Tacet et Anima interprètent déjà dans leur domaine ; duplique une interprétation existante |
| `decay_rate` copié sur `DomainSignal` (r1, r2) | YAGNI — aucun cas d'usage v0.1 ; risque de reconflation entre péremption opérationnelle et érosion de confiance épistémique (réservé ADR-0011 D2) |
| `SignalComposite` avec champ `actionable`/`candidate_decision` | Recrée l'antipattern déprécié par ADR-0004 D5 (`get_recommendations_with_memory_context`) — orchestration cachée dans une abstraction intermédiaire |
| Le client configure seul les seuils de calibration dès le jour 1 | Détruit la promesse cold-start Décision #2/#26 D3 |
| `CollectivePattern` composé directement avec des `DomainSignal` locaux | Contredit ADR-0011 D3/D4 (*"fédération de priors/policies, pas de données"*) — le Hive prior calibre, il ne compose pas |

---

## 5. Conséquences si accepté

- Nouvelle ligne d'index CLAUDE.md §Décisions architecturales (Décision #31, à ajouter après validation)
- `docs/mesh-architecture.md` §5 (Naming) s'enrichit de : `DomainSignal`, `SignalComposite`, `RecommendationCandidate`, `CollectivePattern` (alias ontologique de `fb_patterns` + Hive prior Anima — pas un nouveau store)
- Décision ouverte à créer dans `open-decisions.md` : "Seuils de calibration SignalComposite — trigger : données pilote Phase 3"
- Implémentation reste Phase 4 (ne bloque pas Phase 3 pilote — ce contrat est un accord de vocabulaire cross-nœud, pas un chantier immédiat)

---

## 6. Statut

**Accepted 2026-07-06.** Propagé : CLAUDE.md §Décisions architecturales (Décision #31), `docs/context/decisions-architecturales.md` (détail #31), `docs/mesh-architecture.md` §5 (Naming), `docs/context/open-decisions.md` (nouvelle décision ouverte : seuils de calibration). Implémentation reste Phase 4, gated par le tranchage de "Interaction model event-driven Phase 4-5" (§2bis).

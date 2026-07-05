# ADR-0012 — Aetherix Signal Ontology

**Date :** 2026-07-05
**Status :** Proposed (draft pour revue Ivan — pas encore Accepted)
**Décideurs :** Ivan de Murard (à valider)
**Contexte :** Reframing stratégique 05/07/2026 — *"la vraie IP n'est ni le LLM, ni MCP, ni le forecast. C'est le signal model."*

---

## 1. Contexte

L'audit des sujets architecturaux couverts (mémoire, signaux, ontologie, boucle d'action, orchestration, position dans la chaîne de valeur) montre que six sujets sur sept ont déjà une réponse documentée ailleurs dans le repo :

| Sujet | Statut | Où |
|---|---|---|
| Mémoire | ✅ Traité | `docs/context/memory-architecture.md` (2 couches Aetherix) + `docs/mesh-architecture.md` §Anima (4 couches temporelles + confidence-weighted claims, ADR-0011 D2) |
| Boucle d'action | ✅ Traité (vision) / 🟡 partiel (implémenté) | ADR-0004 (agentic loop orchestrator), Décision #6 (no auto-actions), `docs/context/vision-future.md` (canonical use case bout-en-bout) |
| Couche d'orchestration | ✅ Traité | ADR-0004 — Aetherix = execution node, Orchestrateur = séquenceur MCP séparé (Décision #19) |
| Position chaîne de valeur | ✅ Traité | `docs/mesh-architecture.md` §1 (Mesh opère hors des 6 couches Commerce Hub du PMS) |
| Ontologie | 🟡 Partiel, implicite | Événements Anima déjà nommés (`check_in`, `complaint`, `flight_status`, `sentiment_signal`, `preference_observed` — `mesh-architecture.md` §Anima MCP tools), scores Tacet, mais **jamais unifiés en un schéma cross-nœud** |
| **Signaux** | 🔴 **Non traité** | Mentions éparses ("signal d'apprentissage" mémoire, "external signals" décision ouverte event-driven) — **aucune définition formelle** |

**Le trou identifié** : il n'existe pas de concept `Signal` de premier ordre. Chaque nœud du Mesh produit informellement des observations (Tacet → scores, PMS → webhooks à venir, Anima → events, Aetherix → feedback mémoire) sans schéma commun de : provenance, combinaison, seuil de significativité, portée établissement, confiance, durée de vie, décision déclenchée.

C'est exactement le gap que pointe le reframing du 05/07 : si Aetherix devient *"continuously interprets operational signals to maintain a live understanding of a property's state and recommend the next best operational action"*, alors le **signal model** — pas le LLM, pas MCP, pas Prophet — est l'actif défendable. Ce cadrage est cohérent avec Décision #26 D5 (le moat = position dans la boucle act-and-measure, pas la taille du corpus) : un signal model propriétaire, calibré par établissement et par cohorte, est la version *amont* de ce moat.

---

## 2. Décision proposée

Définir `Signal` et `SignalComposite` comme schémas de premier ordre, communs à tous les nœuds du Mesh (Aetherix, Tacet, Anima, futur Orchestrateur), répondant explicitement aux 7 questions posées.

### D1 — Quels événements observons-nous ? (taxonomie des sources)

| Source | Nœud producteur | Exemples |
|---|---|---|
| **PMS event** | Apaleo/Mews webhook (décision ouverte event-driven Phase 4-5) | booking, cancellation, no-show, room_move |
| **Environmental score** | Tacet | `room_risk_score`, météo, bruit, travaux |
| **Guest event** | Anima | `check_in`, `check_out`, `complaint`, `flight_status`, `sentiment_signal`, `preference_observed` (déjà nommés dans `update_guest_state`) |
| **Operational feedback** | Aetherix (`operational_memory`) | `recommendation_accepted`/`rejected` + outcome J+1 |
| **Manager tacit input** | Canal bidirectionnel (item d, open-decision event-driven) | *"banquet privé off-system ce soir, ignorer surge"* |
| **POS event** (Phase 4, ADR-0006) | Adapter POS | ticket volume, item mix anomaly |

Chaque observation brute devient un `Signal` :

```json
{
  "signal_id": "uuid",
  "hotel_id": "required — jamais cross-tenant (RLS invariant, cf. mesh-architecture.md §4)",
  "source": "pms_webhook | tacet_score | anima_event | memory_feedback | manager_input | pos_event",
  "type": "demand | environmental | guest | operational | systemic",
  "observed_at": "timestamp",
  "payload": "structured, source-specific",
  "confidence": "0.0–1.0",
  "decay_rate": "réutilise le schema ADR-0011 D2 (confidence-weighted claims)",
  "ttl_hint": "durée de pertinence estimée"
}
```

**Réutilisation délibérée** : le champ `confidence`/`decay_rate` n'est pas inventé ici — c'est la discipline déjà actée en ADR-0011 D2 pour les claims Anima, étendue à tout `Signal`. Un seul schéma de confiance dans tout le Mesh, pas un par nœud.

### D2 — Comment les combinons-nous ? (composition)

Un `SignalComposite` (ou "pattern") agrège N `Signal` du même `hotel_id` dans une fenêtre temporelle glissante :

```json
{
  "composite_id": "uuid",
  "hotel_id": "...",
  "contributing_signals": ["signal_id", "..."],
  "composition_rule": "co-occurrence | weighted-sum | rule-based (v1) — modèle appris (Phase 5, cf. Learning Engine ADR-0011 D4)",
  "significance_score": "0.0–1.0"
}
```

**Phase 3-4 (v1)** : règles explicites, auditable, pas de black-box (cohérent Décision #5 reasoning explicite). Ex : `cancellation_wave(PMS) + high_room_risk(Tacet) + low_confidence_forecast(Aetherix)` → composite "demande instable".
**Phase 5 (v2)** : pondération apprise via Learning Engine (ADR-0011 D4) — mêmes triples `(context-features, action, propensity, outcome)` peuvent inclure les composites comme feature de contexte.

### D3 — Quand une combinaison devient-elle significative ? (seuil)

`significance_score` franchit un seuil calibré par type de composite → transition d'état (`latent` → `actionable`). **Seuils non fixés dans cet ADR** — dépendent de données pilote réelles (cf. Décision ouverte event-driven : *"threshold-based interim alerts"* déjà identifié comme besoin, jamais chiffré). Proposé comme décision ouverte séparée (§5).

### D4 — Pour quel établissement ? (portée)

`hotel_id` obligatoire sur tout `Signal` et tout `SignalComposite` — pas d'exception. Aucun signal cross-tenant, cohérent avec l'invariant RLS déjà en place (Décision #2, `mesh-architecture.md` §4). Un composite ne peut agréger que des signaux du même `hotel_id`. Les patterns cross-hôtels (Hive) restent un objet distinct (`fb_patterns`, Segment layer Anima) — pas un `SignalComposite`.

### D5 — Avec quel niveau de confiance ?

Champ `confidence` sur `Signal` (source-level) et `significance_score` sur `SignalComposite` (combination-level) — deux niveaux de confiance distincts, pas conflés. Une source peu fiable (ex : manager input non confirmé) pondère à la baisse tout composite qui l'inclut.

### D6 — Pendant combien de temps ?

`decay_rate` + `ttl_hint` par type de signal — pas une constante globale. Un `pms_webhook` (cancellation) a une pertinence courte (heures) ; un `anima_event` de préférence guest a une pertinence longue (mois, cf. `decay_rate: 0.05` exemple ADR-0011). Un `SignalComposite` expire quand la majorité pondérée de ses signaux contributeurs a décayé sous un plancher.

### D7 — Quelle décision peut-elle déclencher ?

Un `SignalComposite` qui franchit le seuil de significativité produit une **recommandation candidate**, jamais une action automatique — cohérent Décision #6 (no auto-actions MVP) et ADR-0004 (la décision appartient à l'Orchestrateur, pas aux nœuds d'exécution). Mapping proposé :

```
SignalComposite (actionable) → Orchestrateur.evaluate(composite)
    → candidate_action: { type, target_node, human_review_required: true }
    → HITL (WhatsApp / dashboard) → Manager approve/reject
    → outcome capturé (triple de-identified, ADR-0011 D4) → nourrit le composite suivant
```

Ceci ferme la boucle décrite dans `docs/context/vision-future.md` (*Signal Detection → Orchestration → HITL → Feedback*) en lui donnant un schéma concret à l'étape 1 (*Signal Detection*), qui était jusqu'ici seulement narrative.

---

## 3. Ce que cet ADR NE tranche PAS (décisions ouvertes dérivées)

- **Valeurs de seuil de significativité** par type de composite — nécessite données pilote (cf. §D3)
- **Algorithme de composition v2 appris** — dépend du Learning Engine Phase 5 (ADR-0011 D4)
- **Format d'ingestion PMS webhook** — dépend du tranchage de la décision ouverte "Interaction model event-driven Phase 4-5" (`open-decisions.md`)
- **Stockage physique** (nouvelle table vs extension `operational_memory`/`agent_action_log` JSONB) — à trancher à l'implémentation (Phase 4, après Phase 3 pilote)
- **Qui a autorité pour écrire un `Signal`** (chaque nœud écrit ses propres signaux vs bus événementiel central) — question d'architecture d'implémentation, hors scope ontologie

---

## 4. Alternatives rejetées

| Alternative | Raison du rejet |
|---|---|
| Pas d'ontologie unifiée — chaque nœud garde son vocabulaire (scores Tacet, events Anima, feedback Aetherix) | Statu quo actuel — empêche la composition cross-source, empêche le Mesh (ADR-0004) de raisonner sur des signaux hétérogènes avec un contrat commun |
| Un `Signal` = déclenche une action directement | Viole Décision #6 (no auto-actions) et ADR-0004 D7 (la décision appartient à l'Orchestrateur) |
| Confiance/decay ad hoc par nœud | Réinvente ce qu'ADR-0011 D2 a déjà tranché pour Anima — un seul schéma de confiance Mesh-wide évite la dérive |

---

## 5. Conséquences si accepté

- Nouvelle ligne d'index CLAUDE.md §Décisions architecturales (Décision #31, à ajouter après validation)
- `docs/mesh-architecture.md` §5 (Naming) s'enrichit d'une entrée `Signal` / `SignalComposite`
- Décision ouverte à créer dans `open-decisions.md` : "Seuils de significativité SignalComposite — trigger: données pilote Phase 3"
- Implémentation reste Phase 4 (ne bloque pas Phase 3 pilote — cet ADR est un contrat de vocabulaire, pas un chantier immédiat)

---

## 6. Prochaine étape

**Ce document est un draft.** À valider par Ivan avant de :
1. Passer le Status à `Accepted`
2. Ajouter la ligne d'index CLAUDE.md
3. Créer la story d'implémentation (Linear) si Phase 4 scope confirmé

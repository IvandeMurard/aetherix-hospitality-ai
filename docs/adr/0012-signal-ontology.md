# ADR-0012 — Aetherix Signal Ontology

**Date :** 2026-07-05 (r2 : 2026-07-05 — révision suite retour Ivan + ChatGPT)
**Status :** Proposed (draft r2 pour revue Ivan — pas encore Accepted)
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

**Le trou identifié** : il n'existe pas de concept `Signal` de premier ordre. Chaque nœud du Mesh produit informellement des observations sans schéma commun de : provenance, combinaison, seuil de significativité, portée établissement, confiance, durée de vie, décision déclenchée.

### Révision r2 — ce que le premier draft confondait

Le premier draft (r1) faisait trois erreurs de modélisation, identifiées en revue (Ivan + second avis) :

1. **Il conflait "ce qu'un nœud produit" et "ce qui est jugé significatif".** Un score Tacet (`room_risk_score`) est déjà une interprétation *de données brutes*, mais du point de vue du Mesh, tant qu'aucune fonction n'a confronté ce score au contexte de l'établissement (seuils, historique, cohorte), ce n'est qu'une **perception** — pas un signal opérationnel. Un `Signal` au sens propre implique déjà un jugement de pertinence.
2. **Il conflait péremption opérationnelle et érosion de confiance.** `decay_rate` (ADR-0011 D2) modélise une confiance qui s'érode *doucement* dans le temps (une préférence guest observée il y a 3 ans reste plausible, juste moins certaine). Une vague d'annulations qui n'est plus d'actualité après 18h n'"s'érode" pas — elle **expire**, point dur. Ce sont deux mécanismes différents.
3. **Il laissait ouverte la question d'autorité d'écriture sans trancher l'autorité de calibration**, qui est la vraie question produit : qui décide qu'une combinaison de signaux est *significative pour cet établissement en particulier* ? Un nouvel hôtel ne peut pas raisonnablement configurer ça seul (ça détruirait la promesse Day-1 de Décision #2/#26 D3 — cold start via cohorte).

r2 corrige les trois.

---

## 2. Décision proposée

### D0 — Pipeline conceptuel : Event → Observation → Signal → SignalComposite

```
[Monde réel]         Event               un vol retarde, une chambre se libère, une réservation est annulée
        ↓ perception (nœud)
[Nœud du Mesh]       Observation         ce que Tacet/Anima/PMS/POS/Aetherix perçoit et rapporte, brut ou pré-agrégé
        ↓ interprétation (fonction de promotion, cf. D1bis)
[Fonction d'interprétation]  Signal      une Observation jugée pertinente pour une décision opérationnelle, à cet hôtel, maintenant
        ↓ composition (cf. D2)
[Fonction de composition]    SignalComposite    plusieurs Signal jugés significatifs ensemble
        ↓ arbitrage (Orchestrateur, ADR-0004)
[Orchestrateur]      Candidate action    recommandation soumise à HITL (Décision #6)
```

**Conséquence directe** : un nœud (Tacet, Anima, PMS adapter, POS adapter, `operational_memory`) **n'écrit jamais de `Signal` directement**. Il émet des `Observation`. Seule la fonction d'interprétation promeut une `Observation` en `Signal`. Ceci répond proprement à la question d'autorité technique (qui écrit quoi) sans avoir besoin de la trancher nœud par nœud : la réponse est structurelle, pas un choix arbitraire par producteur.

```json
// Observation — émise par un nœud, brute ou pré-agrégée
{
  "observation_id": "uuid",
  "hotel_id": "required",
  "source": "pms_webhook | tacet_score | anima_event | memory_feedback | manager_input | pos_event",
  "observed_at": "timestamp",
  "payload": "structured, source-specific"
}

// Signal — Observation promue par la fonction d'interprétation
{
  "signal_id": "uuid",
  "hotel_id": "required — jamais cross-tenant (RLS invariant, cf. mesh-architecture.md §4)",
  "derived_from": ["observation_id", "..."],
  "type": "demand | environmental | guest | operational | systemic",
  "confidence": "0.0–1.0 — fiabilité de la source + qualité de l'interprétation",
  "valid_until": "péremption dure, optionnelle — ex : fin de service, fin de séjour",
  "decay_rate": "érosion douce de confiance, optionnelle — réutilise ADR-0011 D2, ex : préférence guest ancienne"
}
```

`valid_until` et `decay_rate` sont **mutuellement non-exclusifs mais sémantiquement distincts** : un signal peut avoir les deux (une préférence guest confirmée pendant CE séjour a un `decay_rate` doux à long terme ET un `valid_until` = fin de séjour pour sa pertinence *immédiate*). Le premier répond à "est-ce encore d'actualité ?", le second à "à quel point suis-je encore sûr ?".

### D1 — Quels événements observons-nous ? (taxonomie des sources d'Observation)

| Source | Nœud producteur | Exemples (Observations, pas encore des Signals) |
|---|---|---|
| **PMS event** | Apaleo/Mews webhook (décision ouverte event-driven Phase 4-5) | booking, cancellation, no-show, room_move |
| **Environmental score** | Tacet | `room_risk_score`, météo, bruit, travaux |
| **Guest event** | Anima | `check_in`, `check_out`, `complaint`, `flight_status`, `sentiment_signal`, `preference_observed` (déjà nommés dans `update_guest_state`) |
| **Operational feedback** | Aetherix (`operational_memory`) | `recommendation_accepted`/`rejected` + outcome J+1 |
| **Manager tacit input** | Canal bidirectionnel (item d, open-decision event-driven) | *"banquet privé off-system ce soir, ignorer surge"* |
| **POS event** (Phase 4, ADR-0006) | Adapter POS | ticket volume, item mix anomaly |

### D1bis — Qui interprète ? (autorité de calibration — la vraie question, pas l'autorité d'écriture)

La fonction de promotion Observation → Signal vit **côté Orchestrateur** (cohérent ADR-0004 : les nœuds sont policy-neutral — *"Tacet produit des scores, pas des décisions"* — et l'Orchestrateur est le seul composant avec logique de décision). Mais la fonction elle-même a besoin de seuils calibrés, et **cette calibration n'est ni entièrement automatique ni entièrement déléguée au client** — elle a trois sources hiérarchisées, cohérentes avec des décisions déjà actées :

| Niveau | Source | Mécanisme | Décision existante réutilisée |
|---|---|---|---|
| 1. Défaut | **Prior de cohorte (Hive)** | Seuils hérités de propriétés similaires — day-1, pas de configuration manuelle requise | Décision #2/#26 D3, Federated HiveMemory |
| 2. Apprentissage | **Recalibration locale** | Le seuil se resserre/desserre selon `recommendation_accepted`/rejected + outcome mesuré | Boucle Private Memory existante |
| 3. Override | **Manager explicite** | Canal tacite bidirectionnel — poids maximal, prime sur 1 et 2 pour l'occurrence concernée | Item (d), décision ouverte event-driven Phase 4-5 |

**Ce que ça évite** : demander à un nouvel établissement de définir ses seuils de significativité en autonomie dès le jour 1 — ce qui exigerait une maîtrise fine de ses propres process *avant même qu'Aetherix ait généré de la valeur*, et contredirait la promesse cold-start de Décision #2/#26. Le client garde l'autorité *corrective* (niveau 3, toujours disponible, toujours prioritaire), pas la charge de configuration initiale.

### D2 — Comment les combinons-nous ? (composition)

Un `SignalComposite` agrège N `Signal` (jamais des `Observation` brutes) du même `hotel_id` dans une fenêtre temporelle glissante :

```json
{
  "composite_id": "uuid",
  "hotel_id": "...",
  "contributing_signals": ["signal_id", "..."],
  "composition_rule": "co-occurrence | weighted-sum | rule-based (v1) — modèle appris (Phase 5, Learning Engine ADR-0011 D4)",
  "significance_score": "0.0–1.0"
}
```

**Phase 3-4 (v1)** : règles explicites, auditable, pas de black-box (cohérent Décision #5 reasoning explicite). Ex : `cancellation_wave(PMS) + high_room_risk(Tacet) + low_confidence_forecast(Aetherix)` → composite "demande instable".
**Phase 5 (v2)** : pondération apprise via Learning Engine (ADR-0011 D4).

### D3 — Quand une combinaison devient-elle significative ? (seuil)

`significance_score` franchit un seuil calibré (cf. D1bis, les trois niveaux) → transition d'état (`latent` → `actionable`). **Valeurs de seuil non fixées dans cet ADR** — dépendent de données pilote réelles. Décision ouverte séparée (§3).

### D4 — Pour quel établissement ? (portée + réinjection Hive)

`hotel_id` obligatoire sur toute `Observation`, tout `Signal`, tout `SignalComposite` — pas d'exception, aucun signal brut cross-tenant, cohérent avec l'invariant RLS (Décision #2, `mesh-architecture.md` §4).

**Mais la fonction d'interprétation (D1bis) peut consulter un `CollectivePattern`** — objet agrégé, anonymisé, sans donnée hôtel-identifiable — comme *contexte/prior*, jamais comme signal en propre :

| Objet | Nœud | Déjà existant sous quel nom |
|---|---|---|
| `CollectivePattern` (F&B) | Aetherix Hive Memory | `fb_patterns` (Décision #2) |
| `CollectivePattern` (guest) | Anima Segment | Hive prior (Décision #26 D3) |

`CollectivePattern` n'est donc pas un nouveau store — c'est le nom ontologique commun donné à ce que `fb_patterns` et le Hive prior Anima font déjà : nourrir la calibration locale (niveau 1, D1bis) sans jamais devenir un `Signal` cross-tenant. Un `SignalComposite` ne peut agréger que des `Signal` du même `hotel_id` ; il peut être *pondéré* par un `CollectivePattern`, jamais *composé* avec lui.

### D5 — Avec quel niveau de confiance ?

`confidence` sur `Signal` (fiabilité de la source + interprétation) et `significance_score` sur `SignalComposite` (niveau combinatoire) — deux niveaux distincts, pas conflés. Une source peu fiable (ex : manager input non confirmé) pondère à la baisse tout composite qui l'inclut.

### D6 — Pendant combien de temps ? (`valid_until` ≠ `decay_rate`)

Deux mécanismes séparés, jamais un seul curseur :

- **`valid_until`** — péremption dure, déterministe. Une vague d'annulations n'est plus pertinente après la fin du service concerné. Un `room_risk_score` élevé expire quand les travaux sont terminés (signal Tacet le confirme).
- **`decay_rate`** — érosion douce de confiance, continue (réutilise ADR-0011 D2). Une préférence guest observée une fois il y a 3 ans reste plausible mais de moins en moins certaine — elle ne "expire" jamais franchement, elle s'affaiblit.

Un `SignalComposite` expire si un `Signal` contributeur requis a dépassé son `valid_until`, **indépendamment** de son `decay_rate` — les deux checks sont distincts, pas substituables l'un à l'autre.

### D7 — Quelle décision peut-elle déclencher ?

Un `SignalComposite` qui franchit le seuil de significativité produit une **recommandation candidate**, jamais une action automatique — cohérent Décision #6 (no auto-actions MVP) et ADR-0004 (la décision appartient à l'Orchestrateur, pas aux nœuds d'exécution) :

```
SignalComposite (actionable) → Orchestrateur.evaluate(composite)
    → candidate_action: { type, target_node, human_review_required: true }
    → HITL (WhatsApp / dashboard) → Manager approve/reject
    → outcome capturé (triple de-identified, ADR-0011 D4) → recalibre le seuil (D1bis niveau 2)
```

Ceci ferme la boucle décrite dans `docs/context/vision-future.md` (*Signal Detection → Orchestration → HITL → Feedback*) en lui donnant un schéma concret à l'étape 1, jusqu'ici seulement narrative.

---

## 3. Ce que cet ADR NE tranche PAS (décisions ouvertes dérivées)

- **Valeurs de seuil de significativité** par type de composite — nécessite données pilote (§D3)
- **Algorithme de composition v2 appris** — dépend du Learning Engine Phase 5 (ADR-0011 D4)
- **Format d'ingestion PMS webhook** — dépend du tranchage de "Interaction model event-driven Phase 4-5" (`open-decisions.md`)
- **Stockage physique** (nouvelle table `signals`/`observations` vs extension `operational_memory`/`agent_action_log` JSONB) — à trancher à l'implémentation (Phase 4)
- **Implémentation technique de la fonction d'interprétation** (règle statique Phase 3-4 vs modèle appris Phase 5) — direction posée en D2/D1bis, mécanique à spécifier à l'implémentation

---

## 4. Alternatives rejetées

| Alternative | Raison du rejet |
|---|---|
| Pas d'ontologie unifiée — chaque nœud garde son vocabulaire | Statu quo — empêche la composition cross-source avec un contrat commun |
| Chaque nœud écrit directement un `Signal` | Conflate perception (nœud) et jugement de pertinence (interprétation) — perd la distinction Observation/Signal, réintroduit la confusion r1 |
| Le client configure seul les seuils de significativité dès le jour 1 | Détruit la promesse cold-start Décision #2/#26 D3 ; exige une maîtrise opérationnelle qu'un nouveau client n'a pas encore formalisée avec Aetherix |
| Un seul champ de "durée de vie" (fusion `valid_until`/`decay_rate`) | Conflate péremption dure et érosion de confiance — deux besoins produit différents (r1 error #2) |
| Un `Signal` = déclenche une action directement | Viole Décision #6 (no auto-actions) et ADR-0004 D7 |
| Confiance/decay ad hoc par nœud | Réinvente ce qu'ADR-0011 D2 a déjà tranché pour Anima |

---

## 5. Conséquences si accepté

- Nouvelle ligne d'index CLAUDE.md §Décisions architecturales (Décision #31, à ajouter après validation)
- `docs/mesh-architecture.md` §5 (Naming) s'enrichit de : `Observation`, `Signal`, `SignalComposite`, `CollectivePattern` (alias ontologique de `fb_patterns` + Hive prior Anima — pas un nouveau store)
- Décision ouverte à créer dans `open-decisions.md` : "Seuils de significativité SignalComposite — trigger: données pilote Phase 3"
- Implémentation reste Phase 4 (ne bloque pas Phase 3 pilote — cet ADR est un contrat de vocabulaire, pas un chantier immédiat)

---

## 6. Prochaine étape

**Ce document est un draft r2.** À valider par Ivan avant de :
1. Passer le Status à `Accepted`
2. Ajouter la ligne d'index CLAUDE.md (Décision #31)
3. Créer la story d'implémentation (Linear) si Phase 4 scope confirmé

# ADR-0011 — Anima : Guest Cognition Layer, confidence-weighted claims & HiveMemory v2

**Date :** 2026-06-17
**Status :** Accepted
**Décideurs :** Ivan de Murard
**Contexte :** Post-hackathon Anima PoC (juin 2026) + revue architecture multi-parties (sessions 13/06–17/06)

---

## Contexte

Les échanges architecturaux de juin 2026 (post-hackathon Anima PoC, revue produit + systémique) ont consolidé trois évolutions par rapport à Décision #20 :

1. Anima n'est pas une "memory node" — les quatre couches sont cognitives, pas juste du stockage. "Mémoire" sous-vend.
2. Le système a besoin de représenter sa propre incertitude — mais pas comme une couche nommée, comme une discipline de data modeling invisible.
3. La couche Segment remplit deux fonctions (local + Hive prior) non nommées, et le Learning Engine décisionnel est un tier Mesh séparé, pas une 5e couche Anima.

Vision validée (trois niveaux, mapping direct sur l'architecture) :

| Vision | Nœud | Question |
|--------|------|----------|
| Comprend comme un humain | Anima (Guest Cognition Layer) | *Who is this guest?* |
| Mesure comme une machine | Outcome-capture instrumentation | *What happened after that decision?* |
| Apprend comme un réseau | HiveMemory v2 / Learning Engine (Phase 5) | *What works for similar situations?* |

---

## Décisions

### D1 — Anima = Guest Cognition Layer (individuel, périmètre strict)

Anima est renommée **"Guest Cognition Layer"** partout dans la documentation et le code.

**Garde anti-god-object — non-négociable :**

| Nœud | Responsabilité | Hors-périmètre |
|------|----------------|----------------|
| **Anima** | Compréhension individuelle guest | Policy, fédération, décision |
| **Hive / Mesh** | Connaissance collective anonymisée | Données individuelles, décision |
| **Aetherix / Orchestrateur** | Décision opérationnelle | Mémoire, apprentissage |

Ces frontières sont enforced architecturalement (MCP scope-gating, stores séparés, pas de cross-import Python direct entre nœuds).

### D2 — Confidence-weighted claims : discipline de schema, pas une couche

"Belief System" comme composant nommé est rejeté : philosophiquement chargé, incompatible avec l'attente de fiabilité d'un client payant, et générateur de confusion stakeholder. Le concept sous-jacent est légitime et nécessaire — le système doit savoir à quel point il est confiant, depuis combien d'évidences, avec quelle récence.

**Implémentation : champ dans `ProfileSnapshot`, invisible à l'utilisateur final.**

```json
{
  "value": 19,
  "unit": "°C",
  "confidence": 0.81,
  "evidence_count": 4,
  "last_confirmed": "2026-04-10",
  "decay_rate": 0.05
}
```

Toute claim dans la couche Semantic adopte ce schema. L'Orchestrateur utilise `confidence` + `last_confirmed` pour pondérer automatiquement les claims stales (ex : préférence observée il y a 3 ans, 1 séjour, jamais reconfirmée → confidence basse → pas d'action proactive, mémorisé pour confirmation). Aucune logique supplémentaire requise côté Orchestrateur.

### D3 — Couche Segment : double portée (local + Hive prior)

La couche Segment remplit deux fonctions qui doivent être nommées explicitement :

| Sous-portée | Question | Source de données | Temporalité |
|-------------|----------|-------------------|-------------|
| **Local** | "Guests *like this*, at *this hotel*" | Cohortes anonymisées de la propriété | Nightly recompute |
| **Hive prior** | "Guests *like this*, across *all network hotels*" | Agrégats fédérés du réseau | Phase 5 |

La vision Day-1 (PMS / POS / CRM / SOP → feedback loop → memory → learning) est **inchangée**. Le Hive prior clarifie ce que la couche Segment apporte *avant* toute donnée guest ou hotel-spécifique.

Shift 80/20 → 20/80 au fil des séjours : "Je connais ce type de clientèle" (Hive prior dominant) → "Je connais cette personne" (Guest knowledge accumulée). Analogue concierge expérimenté.

**Similarité inter-hotels : apprise, pas hard-codée.**
- Embeddings sur metadata hotel (localisation, type de venue, clientèle, expériences proposées) — similarité continue, pas de clusters rigides
- La metadata pose le *prior* sur qui est similaire ; les outcomes le *corrigent*
- Partial pooling hiérarchique avec détection de divergence : down-weighting si les outcomes d'un hotel divergent du groupe → safety valve contre le negative transfer
- La metadata est un proxy de similarité décisionnelle, pas la similarité elle-même. Deux hotels identiques sur tous les axes metadata peuvent répondre différemment à une même action. Les outcomes valident.

### D4 — Learning Engine = tier Mesh séparé (Phase 5) + instrumentation Phase 4

Le policy/outcome learning est un **tier Mesh distinct**, pas une couche Anima. Anima fournit le world model ("qui est ce guest") ; le Learning Engine apprend quoi faire ("quelle action → quel résultat pour quel contexte").

**Capture d'outcome dès Phase 4 — seul élément actionnable maintenant :**

À chaque décision de l'Orchestrateur, logger un triple **de-identified** dans un store dédié, séparé d'Anima :

```
(context-features, action, propensity, outcome)
```

- `context-features` : segment + situation type — **jamais l'identité guest**
- `propensity` : probabilité que cette action ait été choisie par l'Orchestrateur à ce moment (requis pour off-policy evaluation — IPW, doubly-robust, DR-learner)
- `outcome` : CSAT, NPS, complaint flag, repeat-booking — joint au triple a posteriori
- Store séparé d'Anima : **aucun champ identifiable, personal-data-free by construction**

Le log de `propensity` est non-négociable : l'évaluation off-policy nécessite de savoir *pourquoi* une action a été choisie pour distinguer l'effet causal de l'artefact de sélection. Sans ce log depuis Phase 4, le Learning Engine Phase 5 opère à l'aveugle.

**HiveMemory v2 (Phase 5) :** fédération de *priors/policies appris*, pas de données. Chaque hotel contribue anonymement ; chaque hotel adapte localement. La federation opère entièrement au-dessus de la ligne personal-data.

### D5 — Reframing du moat

| Ce qui n'est pas le moat | Pourquoi |
|--------------------------|----------|
| La taille du corpus | Rendements décroissants rapides ; données hospitality qui décroissent (ce qui enchantait en 2024 n'enchante plus en 2027) ; reproductible par un concurrent capitalisé |
| L'orchestrateur ou l'agent | Commoditise avec les LLMs de plateforme |

**Le moat est la position dans la boucle act-and-measure :** seul acteur qui (a) peut agir via PMS write, (b) capture l'outcome, (c) l'attribue causalement, (d) fédère les priors résultants anonymement. Cette position ne s'achète pas — elle se construit en années de boucle tournante. Le corpus est l'exhaust, pas le moteur.

---

## Alternatives rejetées

| Alternative | Raison du rejet |
|------------|----------------|
| 5e couche "Outcome/Policy" dans Anima | Weld d'un store per-guest erasure-subject avec un store permanent anonyme cross-hotel — RGPD contaminé, sémantiquement inséparables |
| "Belief System" comme couche nommée | Vocabulaire philosophique inadapté au contexte produit ; confusion fiabilité |
| Hard clusters metadata géo/type | Fragiles, gameable, curse of dimensionality, pas de safety valve negative transfer |
| Corpus comme moat principal | Contesté économiquement, rendements décroissants, non-défendable face à un concurrent capitalisé |
| Learning Engine en Phase 4 | Prématuré — dépend de données réelles bloquées par DPIA gate + prérequis CRM + pilote Apaleo prod |

---

## Conséquences

**Phase 4 (décisions immédiatement actives) :**
- Anima nommée "Guest Cognition Layer" dans toute documentation et tout code
- `ProfileSnapshot` enrichi : champs `confidence`, `evidence_count`, `last_confirmed`, `decay_rate` sur toute claim Semantic
- **Story 3.5 (HOS-247)** : outcome-capture instrumentation — triple de-identified (`context-features`, `action`, `propensity`, `outcome`), store séparé d'Anima, propensity loggée dès le premier déploiement
- Segment layer documentée avec double portée Local / Hive prior (sous-portée Hive = Phase 5)
- `scope="all"` reste anti-pattern loggé (inchangé depuis PoC)

**Phase 5 (Learning Engine) :**
- Learning Engine + HiveMemory v2 comme nœud Mesh distinct — ADR séparé au moment du build
- Dépend de ADR-0013 (event-driven interaction model, futur — réservé, corrigé 20/07/2026 : le numéro 0009 est déjà pris par runtime guardrails/Décision #27) + ADR-0008 (context graph, Décision #24 — ⚠️ **différé Phase 4 le 31/07/2026**, ADR-0008 §17.6 : cette dépendance est donc différée par transitivité ; reprise conditionnée à ADR-0006 §10.4)
- Méthode off-policy evaluation à choisir Phase 5 (IPW / doubly-robust / DR-learner)

**Cross-cutting :**
- Renforce Décision #6 (human-in-loop) : propensity logging prépare l'évaluation sans automatiser les décisions
- Renforce Décision #20 (DPIA gate) : Hive prior personal-data-free = argument RGPD renforcé pour la fédération
- Renforce Décisions #22 / #25 (eval-by-design) : outcome triple = signal d'évaluation naturel pour l'eval gate CI

---

## Décisions ouvertes (→ `docs/context/open-decisions.md`)

- **Politique d'exploration éthique** : quand ne pas donner la "meilleure" action connue pour explorer — tension avec "every guest deserves the best" + DPIA
- **Définition multi-objectif du reward** : CSAT vs marge vs fidélisation vs disponibilité opérationnelle — conflit non résolu intentionnellement
- **Méthode off-policy evaluation** : IPW, doubly-robust, DR-learner — choix Phase 5 selon volume de données
- **Floor k-anonymat couche Segment** : taille minimum cohorte pour éviter ré-identification individuelle dans les agrégats

---

## Addendum 2026-07-20 — validation externe narratif DPIA/éthique (veille)

> Sources : Edmondo Grassi, "The Remains of the Stay: Memory, Identity, and the Afterlife of the Guest" (Hotel Yearbook 2026) ; EmpathyEyes (empathy-eyes.com). Détail complet : vault Obsidian `Veille/Veille_Regulatory_Governance.md` §WEEK OF JUL 20 et `Veille/Veille_Guest_Experience.md` §WEEK OF JUL 13.

**Renforce D2 (`decay_rate`, confidence-weighted claims)** — Grassi (sociologue, San Raffaele) nomme sans le savoir le risque exact que D2 corrige : l'IA remplace la mémoire humaine du concierge — qui "oublie et pardonne" — par une "tertiary retention" algorithmique qui ne connaît "ni la grâce ni l'oubli", créant une asymétrie où *"the system will know them better than they remember themselves."* `decay_rate` n'est donc pas qu'un paramètre technique de pondération — c'est la réponse architecturale directe à un risque éthique documenté indépendamment : une mémoire qui s'efface/se pondère dans le temps plutôt qu'une rétention parfaite et permanente. Citable tel quel dans tout narratif DPIA formel ou pitch investisseur sur "pourquoi Anima n'est pas de la surveillance" : *"whether to remember is an act of care or an exercise of power"* (Grassi) — Anima choisit le camp du care par construction (D1 garde anti-god-object, D2 decay, D4 store personal-data-free séparé).

**Renforce D5 (reframing du moat)** — EmpathyEyes (smart glasses hôtelier, staff-initiated, retrieval PMS pur, "no biometric data collected or stored") valide en marché que la partie "affichage/retrieval du contexte guest" est déjà bâtie par un tiers, sans couche de cognition propre (pas de confidence-weighted claims, pas d'inférence cohort pour un guest inconnu, pas de mémoire qui apprend). Confirme par la négative que le moat Anima n'est pas "afficher le contexte au bon moment" (commodité, bâtie ailleurs) mais la profondeur cognitive (D2-D4) que ce type de device ne fait pas et pourrait un jour consommer plutôt que concurrencer.

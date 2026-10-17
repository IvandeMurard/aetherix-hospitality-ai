# Vision long-terme — Agentic Hospitality Mesh

> Vision stratégique post-Phase 3. Pas un plan d'exécution actuel — une direction.
> Source : note "Vision Avenir" `Ivan — Ideas/Projects/Aetherix/`.
> Référencée depuis CLAUDE.md §Roadmap (Phase 4).

---

## Statement

> *Aetherix's ultimate vision is to become the core intelligence layer in a fully agentic hospitality mesh: specialized agents detect revenue opportunities in real time, the Revenue Orchestration Agent coordinates context-rich workflows, and connected MCP-native systems (Design System → Claude Design → Claude Code) autonomously generate, deploy, and continuously optimize guest-facing experiences — all with humans remaining in the loop for strategic direction.*

> *This is how we move from reactive tools to invisible, self-improving intelligence that scales outcomes far beyond what any human team could achieve.*

---

## Goal

End-to-end responsivity entre événements externes et pricing/F&B/booking, avec feedback loop continue. Workflow complet :

`Event detection → Pricing adjustment → Booking surface → F&B prep → Food waste optimization → Knowledge memory → loop`

---

## Canonical use case — Agentic Last-Minute Promo Workflow (2026)

### 01 · Signal Detection — *Specialized Demand Agent*
Détecte un surge de bookings en temps réel.
*Exemple* : concert Céline Dion à l'Accor Arena → données historiques + Aetherix anticipent le pic de demande.

### 02 · Orchestration & Brief Creation — *Revenue Orchestration Agent*
Reçoit l'alerte → enrichit le contexte → crée un brief campagne :
> *"Create a high-conversion, mobile-first last-minute promo page with strong urgency CTA."*

### 03 · Design Generation via MCP

| Design System MCP | Claude Design MCP |
|---|---|
| Brand tokens retrieved (typo, spacing, palette, UI primitives) | Génère 3 variantes mobile promo on-brand avec urgency + CTA |

### 04 · Human-in-the-Loop
Manager review → approuve la meilleure variante. Une décision, quelques secondes. **[APPROVED]**

### 05 · Code & Deployment — *Claude Code MCP*
Design approuvé → code production-ready.
**[AUTO-DEPLOY]** — live sur site + app, *du signal à la page live en minutes*.

### 06 · Continuous Feedback Loop
L'agent monitore en continu : conversion rate, revenue, bounce rate. Analyse quotidienne → triggers automatiques d'amélioration 24/7.

---

## Execution breakdown — what's needed beyond current state

| Phase | Effort | Ce que ça demande | Difficulté |
|---|---|---|---|
| 1. MCP exposure of Aetherix *(partiellement fait — Phase 0/1)* | 3-5 jours | Predictions + memory pleinement callable | Medium |
| 2. Specialized Demand Detection Agent | 1 semaine | Agent simple qui watch Apaleo + Aetherix + events | Medium |
| 3. Revenue Orchestration Agent *(le chef d'orchestre)* | 2-3 semaines | **La partie la plus dure** — context enrichment, brief creation, sequencing calls | Hard |
| 4. Integration Claude Design + Claude Code MCP | 1.5-2 semaines | Prompt engineering, error handling, agent handoff | Hard |
| 5. Continuous Feedback Loop + monitoring | 1-1.5 semaines | Analytics ingestion + decision logic re-trigger | Medium-Hard |
| 6. Human-in-the-loop + logging + safety | 1 semaine | Approvals, audit trail, guardrails | Medium |

**Total estimatif** : 7-12 semaines à partir d'un MCP Server v0 stable + Phase 2 Receipts shippé.

---

## Pré-requis pour démarrer Phase 4

1. ✅ Phase 0 — Backtest PASS, MCP Server v0 shippé (HOS-71)
2. ✅ Phase 1 — Observability (ADR 0003) + memory instrumentation
3. 🟡 Phase 2 — Receipts complets (P2-1 → P2-7)
4. 🔲 Phase 3 — Multi-property + pilote réel + trust-KPI measurement

Sans Phase 3 (validation pilote réel), Phase 4 reste hypothétique. Le Revenue Orchestration Agent n'a aucune valeur si la couche Phase 0-2 n'est pas **prouvée trustworthy** sur du terrain.

---

## Linkages Linear (à créer le moment venu)

Quand Phase 3 est validée et qu'on amorce Phase 4 :

- **Epic 9** (à créer) : Agentic Mesh — Revenue Orchestration Agent
- **Epic 10** (à créer) : MCP-native Design Pipeline (Claude Design + Claude Code integration)

À ce moment, appliquer le template `docs/context/linear-conventions.md` strictement.

---

## Risques identifiés

- **Garde-fous obligatoires** : auto-deploy d'une promo page sans validation humaine = risque PR. La step 04 (HITL) n'est pas optionnelle.
- **Latence pricing** : si la pipeline détection→déploiement prend >15min, le surge est passé.
- **Cohérence cross-property** : un Revenue Orchestration Agent multi-tenants pose des questions d'isolation de données qui doivent être résolues bien avant de l'instancier.
- **Dépendances externes** : Claude Design MCP + Claude Code MCP doivent eux-mêmes être production-ready côté Anthropic. À monitorer.

---

## Phase 4 — Federated HiveMemory (narrative announcée Phase 3)

**Décision PM 04/06/2026** : avancer la communication de la 2e couche mémoire (Hive cross-hôtels anonymisée — Décision #2) à *"announced Phase 3, shipped Phase 4"*. Motivation : Meuze.ai revendique federated learning live en production. Pour ne pas paraître en retard dans les sales conversations, communiquer Federated HiveMemory comme roadmap publique dès Phase 3 (design doc public + LOO validation visible) tout en shippant prod en Phase 4.

**Architecture cible (référence ADR-0005 cold-start meta-learner + future ADR-0008 graphe de contexte) :**

- **Per-tenant isolation** : raw data ne quitte jamais le tenant hôtel. Compliance RGPD by design (anticipée pour design partners enterprise type Accor / Marriott).
- **Anonymized cohort patterns** : seuls les coefficients agrégés (saisonnalité Prophet, hyperparams calibrés, shapelets) traversent — pas de bookings ou couverts identifiables.
- **Day-1 unlock** : un nouvel hôtel onboardé démarre avec un prior bayésien Prophet construit depuis sa cohorte similaire (géo + segment + capacité + saisonnalité). MAPE Day-1 cible ~22% au lieu de 90j d'attente.
- **Cohort sharpening continu** : chaque recommendation accepted / rejected / modified par un manager sharpens le pattern de la cohorte pour tous les membres. Network effect.
- **MCP tool exposé** : `query_cohort_prior` callable par n'importe quel orchestrateur agent externe via MCP (cohérent Décision #19 séparation).

**Narrative marketing** : voir `docs/marketing/positioning-snippets.md` snippet H-7 + section "Federated cohort intelligence framing".

**Validation pré-pilote** : LOO sur 5 sandbox properties Apaleo (BER / LND / MUC / PAR / VIE — cf. Décision #11). Gate runtime auto-disable si Day-7 MAPE > 25% (ADR-0005).

**Pré-requis Phase 4** : (a) graphe de contexte tranché (décision ouverte 04/06) pour cohort matching v2 multi-dim, (b) ADR-0006 POS tranché (impact features cohort).

---

## Aetherix Voice — Tacit Knowledge Capture (Phase 5+ inspiration Lore)

**Origine** : convergence thèse "knowledge extraction = the real bottleneck" (Mira Murati, Hyperspell, GBrain, @t_blom — tous 06/2026) + projet personnel Lore (hackathon Speechmatics × AI Collective Paris, Feb 2026, github.com/IvandeMurard/Lore).

**Thèse** : RAG retrieves what you put in. Le vrai unlock = extraire activement le tacit que les seniors n'ont jamais écrit. Lore l'a démontré sur aviation maintenance (techniciens seniors avant retraite). Aetherix peut l'appliquer à hospitality.

**Cible en hospitality — corrigé 04/06** :

| Profil | Savoir tacit critique | Codification existante | Priorité capture |
|---|---|---|---|
| **General Manager** | Relations corporate clients · quirks bâtiment · politique syndicale · histoire de la maison · qui décide quoi dans le groupe | Quasi-zéro | **Priorité 1** |
| **Senior concierge** | Préférences guests récurrents · réseau restaurants/taxis/théâtres · coutumes par nationalité · alertes tacites | Quasi-zéro | **Priorité 1** |
| **Maître d'hôtel** | Pattern services · staff coordination · gestion edge cases salle | Moyenne (briefings oraux, SOPs F&B partiels) | Priorité 2 |
| **Chef de cuisine** | Recettes · supplier specs · menu engineering | Forte (recettes écrites, SOPs, fiches techniques) | Priorité 3 |

**Justification cible GM + concierge** : c'est là que la valeur (tacit non-codifié) × urgence (départs retraite, mobilité) est la plus haute. Chef knowledge est plus codifié (recettes, fiches techniques) → moindre urgence d'extraction.

**Conception (Phase 5+, pas avant)** :

- **Mode capture** : GM ou concierge senior débriefe Aetherix par voix après interaction marquante (corporate guest difficile, événement spécial, edge case). Aetherix interview activement — questions de follow-up, flag d'ambiguïté, contexte structuré (guest_id × season × event_type × intervention).
- **Mode query** : staff junior interroge Aetherix par voix devant le client / au bureau. Réponse en 3 couches : (1) SOP officielle, (2) wisdom contextuelle des seniors, (3) historique spécifique de ce guest / cette catégorie.
- **Mode log** : voice-first logging d'intervention pour persistence.

**Pattern adopté de Lore** : "Aetherix never contradicts a SOP. It completes it."

**Pré-requis architecturaux** :
- Graphe de contexte (cf. débat Phase 4 — décision ouverte à ouvrir)
- Voice stack (Speechmatics + Claude voice mode quand mature ; Décision #4 actuelle = voice opt-in pas voice-first, à revisiter Phase 5)
- Knowledge graph relationnel (guest × season × event × intervention × senior)
- Contradiction detection (si GM A et GM B disagree sur un même guest type → flag, pas average)
- Confidence scoring (observations confirmées par 4 staff sur 3 ans > note isolée)

**Asset cross-projet** : Lore prouve qu'Ivan a anticipé la thèse "knowledge extraction" avant qu'elle ne devienne consensus marché 06/2026. À surfacer dans deck investisseur + Apaleo Agent Hub listing + Phase 3 Track B technical write-up (footnote parallel work).

**Phasing** :
- Phase 5+ — pas avant pilote validé Phase 3 + multi-tenant Phase 4 stable
- Pré-requis : graphe de contexte Phase 4 livré + Décision #4 voice révisée
- Validation : pilote dédié sur 1 hôtel "design partner senior" (établissement avec GM 20+ ans d'ancienneté qui accepte d'être enregistré)

---

## Carnet d'idées — surface produit ouverte par le statut de responsable de traitement (Phase 5)

> **Origine :** DPIA Anima du 01/08/2026 ([`dpia-anima-2026-08.md`](dpia-anima-2026-08.md) §10.4).
> **Statut : Research** — aucune date, aucun scope, aucune DoD. Rien ici n'est du backlog.
> **Gelé** par le plan 90 j (Epic 16, §« Ce qu'on ne fait PAS »). On l'enregistre pour ne pas le
> reperdre, pas pour l'instruire.

La DPIA a établi que le Hive prior fait sortir Aetherix de la sous-traitance : sur la couche agrégée,
Aetherix détermine seul finalité, moyens et bénéficiaires — il est **responsable de traitement**.
C'est une charge (registre art. 30 propre, base légale propre, DSAR en direct, notification de
violation) et c'est **la forme juridique du moat d'ADR-0011 D5** : un pur sous-traitant n'accumule
rien, tout repart avec l'hôtel. Ce qui devient possible seulement à ce titre :

| Idée | Ce qu'elle exploite | Réserve |
|---|---|---|
| **Benchmark cross-propriétés vendable** — « votre capture rate F&B / no-show vs propriétés comparables » | Dataset agrégé propriété d'Aetherix, pas de l'hôtel | Conditionné au plancher de k-anonymat (décision ouverte) + **opt-in** hôtel (Décision #43, 17/10/2026 ; était opt-out) |
| **Cold-start packagé comme valeur d'onboarding** — « jour 1, vous avez déjà un prior » | Hive prior d'ADR-0011 D3, vendu comme bénéfice contractuel et non comme mécanique interne | Ne tient que si le prior bat réellement une heuristique — à prouver, cf. protocole de preuve |
| ~~**Portabilité asymétrique** — l'hôtel part avec ses données, les priors appris restent~~ **Remplacée par la Décision #43 (17/10/2026)** : tout ce qui est propre à l'hôtel, appris ou non, part avec lui ; seuls restent les agrégats anonymisés déjà calculés à partir d'hôtels ayant opté pour le Hive | ~~La distinction données / policy apprise d'ADR-0011 D4~~ | ~~Exige que la policy soit démontrablement non-personnelle (§10.2 DPIA, claim contestée)~~ |
| **Rapport sectoriel annuel** de données agrégées | Actif marketing gratuit une fois la couche existante | Même plancher k ; et publier des agrégats est un traitement, pas une communication |
| **Agent de conformité (art. 30 / DSAR / registre)** — voir ci-dessous | La position d'Aetherix comme responsable *et* comme fournisseur d'outillage | La plus séduisante et la plus piégeuse |

### Sur l'agent de conformité — la lecture honnête

L'idée (un agent qui tient le registre art. 30, trace les traitements, exécute les DSAR, produit la
preuve d'effacement) a une vraie logique : Aetherix doit de toute façon **construire** cette
plomberie pour lui-même — les mesures M-5 (rectification), M-6 (opposition à la lecture) et M-7
(DSAR testée de bout en bout) de la DPIA §9.2 sont des prérequis non négociables. Un outil qu'on
construit par obligation et qu'on revend ensuite est une bonne économie d'échelle, et le chemin de
rectification survivant au recompute nocturne est un problème technique réel et non résolu ailleurs.

Trois raisons de ne pas s'y engager maintenant, à garder écrites :

1. **C'est un changement de métier.** Vendre de la conformité, c'est du RegTech — cycle de vente,
   attentes de garantie et responsabilité juridique différents de l'opérationnel F&B. Le wedge
   (`positionnement-wedge.md`) devient illisible.
2. **La crédibilité se prend à l'envers.** Vendre un agent de conformité quand on n'a soi-même ni
   inventaire de données (`GDPR-DATA-INVENTORY.md` non livré), ni DPA, ni DSAR testée, ni
   design-partner, est exactement le défaut que la Décision #33 existe pour empêcher.
3. **Marché occupé.** OneTrust, Didomi, Dastra et consorts tiennent déjà le registre et les DSAR.
   L'angle défendable ne serait pas « un registre de plus » mais l'angle étroit et réel :
   *tracer et effacer une inférence dans une mémoire vectorielle et un store d'outcomes* — ce que
   les outils RegTech généralistes ne savent pas faire parce qu'ils n'ont jamais vu un embedding.

**Séquence à respecter si ça se fait un jour :** le construire pour Aetherix, le prouver sur le
premier pilote réel, publier la mécanique, et *ensuite seulement* se demander si c'est un produit.
Dans cet ordre, c'est un atout marketing gagné ; dans l'autre, c'est une promesse.

---

## Notes de mise à jour

- 2026-04-25 — Création initiale, extraction depuis note "Vision Avenir" personnelle.
- 2026-06-04 — Ajout section *"Aetherix Voice — Tacit Knowledge Capture (Phase 5+ inspiration Lore)"* suite veille convergence thèse knowledge extraction + correction cible chef → GM/concierge.
- 2026-08-01 — Ajout *"Carnet d'idées — surface produit ouverte par le statut de responsable de traitement"* (DPIA §10.4, HOS-229). ⚠️ **Alerte de trajectoire posée par la DPIA §5.4** : *Aetherix Voice* ci-dessus infère depuis la **voix**. Le jour où cette brique croise une inférence émotionnelle, le système devient un « système de reconnaissance des émotions » au sens de l'AI Act art. 3(39) — donnée **biométrique** (RGPD art. 9), **Annexe III haut risque**, obligation de transparence art. 50(3). Le coût de conformité change d'ordre de grandeur. Voix + émotion = nouvelle DPIA obligatoire, pas un incrément.

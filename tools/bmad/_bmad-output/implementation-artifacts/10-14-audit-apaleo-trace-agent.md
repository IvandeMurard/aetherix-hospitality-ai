# Story 10.14: Audit — Apaleo Trace Agent (THE FLAG) vs pipeline F&B Aetherix

Status: review

> **Linear**: [HOS-285](https://linear.app/hospitalityagent/issue/HOS-285) · **Epic**: 10 ([HOS-174](https://linear.app/hospitalityagent/issue/HOS-174)) · **Priorité**: 🔴 Urgent · **Estimate**: 2 pts · **Sprint**: S0 (30/07 → 02/08) · **Phase**: 3
> **Type**: audit documentaire / veille concurrentielle — **aucun code de production attendu**
> **Eval gate (Décision #22)** : **non applicable** — ne touche ni `{forecast, staffing, recommendation, memory, inbound_parser}`, ni `app/providers/`, ni les prompts. Marquer la PR `eval-exempt`.
> **Plan de sprint** : [`docs/planning/phase-3-sprint-plan.md`](../../../docs/planning/phase-3-sprint-plan.md) §S0

## Story

As a **PM Aetherix arbitrant le canari concurrentiel « Apaleo Copilot scope F&B »**,
I want **savoir si le Trace Agent d'Apaleo couvre déjà, même indirectement, le pattern F&B/covers/staffing d'Aetherix**,
so that **le scénario W2 (A/B/C) soit reclassé sur une preuve citée plutôt que sur une intuition, avant d'engager le pilote réel**.

## Contexte

Veille du 20/06/2026 (item 8/10) : Apaleo a lancé **Trace Agent** en partenariat avec **THE FLAG** — le premier agent Apaleo qui **exécute** des tâches opérationnelles (pas seulement du chat), en convertissant les *reservation comments* en tâches ops via LLM + APIs ouvertes.

Le pattern « demande guest → tâche opérationnelle exécutée » est désormais **prouvé en production chez Apaleo**. Il empiète potentiellement sur le pattern Aetherix « forecast → reco → push Receipt ». C'est ce qui a fait passer W2 de FIRED (08/06) à **RE-FIRED / ESCALADE (20/06)**.

**Distinct de [HOS-278](https://linear.app/hospitalityagent/issue/HOS-278)** (spike A2A, S1) : HOS-278 est un audit de *protocole d'intégration* et un go/no-go architectural. HOS-285 est un audit **fonctionnel de couverture** — « Trace Agent fait-il déjà ce que fait le pipeline F&B Aetherix ? ». Les deux alimentent la même décision ouverte mais ne répondent pas à la même question. Ne pas les fusionner.

## Acceptance Criteria

1. **AC1** — Types de tâches générées par Trace Agent listés (catégories observées / documentées dans la doc Apaleo + presse).
2. **AC2** — Couverture F&B / covers / staffing vérifiée, même indirecte (ex. *« prepare extra covers for late checkout group »*) — **réponse binaire + preuve citée**.
3. **AC3** — Benchmark écrit vs pipeline Aetherix (forecast → reco → push WhatsApp Receipt) sur 3 axes : profondeur prédictive, reasoning/explicabilité, mémoire cross-séjour.
4. **AC4** — Scénario W2 (A/B/C, `docs/context/monitoring-watchlist.md`) mis à jour avec ce signal — reclassification si AC2 positif.
5. **AC5** — Note de différenciation F&B livrée — `docs/competitive/apaleo-trace-agent-analysis.md`.

## Tasks / Subtasks

- [ ] **T0 — Re-scanner le signal avant d'écrire** (pré-requis AC1/AC2)
  - [ ] Le signal date du 20/06 et **aucune veille de juillet ne le mentionne** (vérifié : `2026-07-02`, `-07-06`, `-07-13`, `-07-20`, `-07-27`). Re-scanner `apaleo.com/blog/apaleo-news` + doc dev avant de conclure.
  - [ ] Si Trace Agent a évolué depuis le 20/06 → l'audit porte sur l'état courant, pas sur l'état de juin. Dater explicitement l'observation dans le livrable.
- [ ] **T1 — Inventaire des tâches Trace Agent** (AC1)
  - [ ] Sources primaires : blog Apaleo (`apaleo.com/blog/apaleo-news`), `apaleo.dev/guides/ai/overview.html`, presse (Hotel Yearbook 2026 « The Agentic Hotel »).
  - [ ] Catégoriser les tâches observées (housekeeping, front desk, maintenance, F&B ?) avec citation source pour chacune.
- [ ] **T2 — Vérification de couverture F&B** (AC2)
  - [ ] Rejouer `python scripts/list_apaleo_tools.py` et **differ contre les 235 tools comptés le 03/06** (`docs/competitive/apaleo-mcp-mapping.md` §AC1). Tout nouveau tool depuis cette date est un signal direct.
  - [ ] Re-vérifier la *border zone* de 44 tools F&B (§AC2 du mapping) : Trace Agent en compose-t-il ?
  - [ ] Conclusion **binaire** (oui / non), assortie d'au moins une citation littérale. Pas de « probablement pas ».
- [ ] **T3 — Benchmark 3 axes** (AC3)
  - [ ] Profondeur prédictive · reasoning/explicabilité · mémoire cross-séjour.
  - [ ] Ancrer sur la thèse déjà établie : Apaleo expose la donnée brute, **aucune primitive de forecast covers / capture-rate / staffing** (`apaleo-mcp-mapping.md` §TL;DR). Vérifier si Trace Agent invalide ce constat.
- [ ] **T4 — Mise à jour watchlist W2** (AC4)
  - [ ] `docs/context/monitoring-watchlist.md` §W2 : ajouter un *Status update* daté ; reclasser les scénarios A (30%) / B (50%) / C (20%) si AC2 est positif.
  - [ ] Répercuter dans `docs/context/open-decisions.md` §« Apaleo Copilot scope F&B » (l. 22-49).
- [ ] **T5 — Livrable** (AC5)
  - [ ] Écrire `docs/competitive/apaleo-trace-agent-analysis.md` au format des analyses existantes (cf. §Ancrages).
  - [ ] Ajouter la ligne `**Analyse complète** : docs/competitive/apaleo-trace-agent-analysis.md` dans §W2, comme W1/W10/W11/W14.

## Dev Notes

### Ancrages (anti-réinvention)

- **Base d'évidence existante — à réutiliser, pas à refaire** : `docs/competitive/apaleo-mcp-mapping.md` ([HOS-197](https://linear.app/hospitalityagent/issue/HOS-197), 03/06). Contient déjà le comptage live de **235 tools MCP Apaleo**, la partition **5 consommés / 44 border-zone F&B / 186 hors menace**, et la conclusion « Apaleo n'expose aucune primitive de forecast covers, capture-rate, ni staffing ». **C'est la baseline du benchmark AC3.**
- **Méthode reproductible déjà outillée** : `scripts/list_apaleo_tools.py` (source d'autorité = le serveur MCP live, pas la doc). Le mapping documente aussi `scripts/tmp_classify_apaleo.py` comme script jetable de classification.
- **Format du livrable** : suivre `docs/competitive/grevon-analysis.md` et `conduit-ai-analysis.md` (analyses les plus récentes). En-tête avec Story/Type/Date/Parent decision, TL;DR à puces, puis sections par AC — modèle visible dans `apaleo-mcp-mapping.md`.
- **Signal d'origine** : `docs/veille/2026-06-20-veille.md` §8/10 — contient l'action proposée qui a donné naissance à cette story.
- **Contexte stratégique croisé** : `docs/context/monitoring-watchlist.md` §W2 l. 42 — THE FLAG Zürich est identifié comme *« property à surveiller/benchmarker en priorité pour l'audit Trace Agent (même partenaire, accès facilité si outreach) »*. Piste d'accès concrète.

### Pièges

- **⚠ Collision de livrables.** `docs/context/monitoring-watchlist.md` §W2 (l. 58) et `docs/context/open-decisions.md` (l. 49) annoncent un **`docs/competitive/apaleo-copilot-functional-audit.md` qui n'a jamais été écrit** — l'agent d'hygiène architecturale ([HOS-320](https://linear.app/hospitalityagent/issue/HOS-320), drift D2) a détecté que le ✅ précédent surclamait une livraison. HOS-285 AC5 demande un fichier **différent** (`apaleo-trace-agent-analysis.md`). Deux options, à trancher au début de la story :
  1. Écrire `apaleo-trace-agent-analysis.md` et **retirer** la mention du fichier fantôme, ou
  2. Fusionner les deux audits dans un seul doc et mettre les deux références à jour.
  **Ne pas créer une seconde déclaration orpheline** — c'est exactement le drift que HOS-320 vient de corriger.
- **Signal potentiellement rassis.** 5+ semaines sans nouvelle mention en veille. Un audit écrit sur l'état de juin serait faux s'il est présenté au présent. D'où T0.
- **AC2 exige du binaire.** La formulation Linear est explicite : *« réponse binaire + preuve citée »*. Une conclusion nuancée sans citation ne satisfait pas l'AC.
- **Ne pas déborder sur HOS-278.** La question du protocole A2A, du lock-in et du choix « Aetherix-as-A2A-agent vs MCP standalone » appartient à HOS-278 (S1). Si l'audit fait émerger un élément d'architecture, le consigner comme *input pour HOS-278*, pas le trancher ici.
- **Drift de numérotation à corriger au passage** : `monitoring-watchlist.md` §W2 (l. 55) désigne HOS-278 comme « Story 10.7 ». Linear dit **Story 10.13** ; 10.7 est [HOS-181](https://linear.app/hospitalityagent/issue/HOS-181) (Hive Memory). Corriger la ligne pendant T4.

### Impact sur le plan de sprint

Cette story est **hors chemin critique du go-live** (elle ne bloque pas HOS-176). Sa valeur est décisionnelle : elle alimente le canari W2 et, indirectement, la forme du positionnement défendu dans [HOS-180](https://linear.app/hospitalityagent/issue/HOS-180) (Agent Hub listing, S7). Si AC2 ressort **positif** (Trace Agent couvre du F&B), c'est un déclencheur de re-plan : voir `phase-3-sprint-plan.md` §Risques — le scénario C de W2 exige un pivot documenté.

### Test Plan

- [ ] Validation manuelle : audit documentaire + test sandbox Apaleo si Trace Agent y est accessible.
- [ ] Aucun test automatisé — pas de code de production.
- [ ] Contrôle de complétude : les 5 AC sont adressés dans le livrable, chacun avec au moins une source citée.

### References

- [Source: Linear HOS-285] · [Source: docs/competitive/apaleo-mcp-mapping.md#TL;DR] · [Source: docs/competitive/apaleo-mcp-mapping.md#AC1] · [Source: docs/context/monitoring-watchlist.md#W2] · [Source: docs/context/open-decisions.md:22-49] · [Source: docs/veille/2026-06-20-veille.md#8/10] · [Source: scripts/list_apaleo_tools.py] · [Source: docs/planning/phase-3-sprint-plan.md#S0]

## Dev Agent Record

### Agent Model Used

Bob (Scrum Master) exécutant `dev-story` · claude-opus-5 · 2026-07-30

### Debug Log References

- Aucun test automatisé — story documentaire, aucun code de production touché. PR à marquer `eval-exempt`.
- 4 sources publiques consultées le 30/07/2026 ; 1 source inaccessible (PhocusWire, HTTP 403) — non bloquant, l'information était redondante avec l'annonce officielle Apaleo.

### Completion Notes List

- **AC1 ✅** — Inventaire livré : catégories (*amenities, room setup, dietary requirements, celebrations*), données lues (*booking comments, guest profiles, rate codes, special dates*), destination (Sweeply / toute API housekeeping), volumétrie (~30 tâches/jour, 3,5 h/semaine), mode de construction (Agent Factory + Sweeply, prototype 1 mois → prod 2,5 mois). Roadmap annoncée capturée.
- **AC2 ✅** — **Réponse binaire : NON**, sur 4 sources avec citations. Seule occurrence alimentaire = `dietary requirements` (préférence guest individuelle, pas de gestion F&B) — traitée explicitement pour éviter l'ambiguïté. Confirmation croisée par `apaleo-mcp-mapping.md` : Trace Agent est bâti sur les mêmes APIs ouvertes, il ne peut exposer une capacité absente du socle.
- **AC3 ✅** — Benchmark 3 axes livré. Conclusion : aucun chevauchement fonctionnel — Trace Agent **route de l'intention explicite**, Aetherix **anticipe une demande non exprimée**. Différence de classe de problème, pas de maturité.
- **AC4 ✅** — W2 mis à jour (`monitoring-watchlist.md`) + décision ouverte mise à jour (`open-decisions.md`). **Scénario A conforté** ; canari **dé-escaladé**, cadence bi-hebdo levée → mensuel. Vecteur de menace reformulé (voir ci-dessous). Nouveau trigger ajouté.
- **AC5 ✅** — `docs/competitive/apaleo-trace-agent-analysis.md` créé, format aligné sur `apaleo-mcp-mapping.md`.
- **Finding hors AC — le vecteur de menace a changé de nature.** Le risque n'est plus « Apaleo construit du F&B » mais « Apaleo outille un tiers pour le construire en un trimestre » (Agent Hub + Agent Factory, vitesse démontrée 1 mois → 2,5 mois). La catégorie F&B est **vacante** sur Agent Hub au 30/07. Requalifie [HOS-180](https://linear.app/hospitalityagent/issue/HOS-180) d'opportunité de visibilité en **acte défensif d'occupation de catégorie**.
- **Piège « collision de livrables » résolu — option 1.** Le fichier fantôme `apaleo-copilot-functional-audit.md` (annoncé dans 2 docs, jamais écrit, drift D2 de HOS-320) a été **remplacé par des références au fichier réel** dans `monitoring-watchlist.md` et `open-decisions.md`. Un seul fichier, pas deux. Aucune nouvelle déclaration orpheline créée.
- **Drift corrigé au passage** — `monitoring-watchlist.md` désignait HOS-278 comme « Story 10.7 » ; corrigé en **Story 10.13** (10.7 = HOS-181, Hive Memory).
- **⚠ Limite assumée — T2 partiellement exécutée.** `scripts/list_apaleo_tools.py` **n'a pas été rejoué** : il exige des credentials OAuth2 Apaleo indisponibles dans cette session. Le comptage des 235 tools et la partition border-zone datent donc toujours du **03/06/2026**. La conclusion « aucune primitive forecast/capture-rate/staffing » repose sur ce relevé. **Action de vérification à 5 minutes, à faire avant le go-live** — documentée dans §Limites du livrable.

### File List

- `docs/competitive/apaleo-trace-agent-analysis.md` *(créé)*
- `docs/context/monitoring-watchlist.md` *(modifié — §W2 : status update 07-30, nouveau trigger, référence fantôme supprimée, drift numérotation corrigé)*
- `docs/context/open-decisions.md` *(modifié — §Apaleo Copilot scope F&B : dé-escalade, audit livré, vecteur reformulé)*

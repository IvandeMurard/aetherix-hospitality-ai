# Story 10.13: Spike — Aetherix ↔ Apaleo Copilot A2A integration architecture

Status: review

> **Linear**: [HOS-278](https://linear.app/hospitalityagent/issue/HOS-278) · **Epic**: 10 ([HOS-174](https://linear.app/hospitalityagent/issue/HOS-174)) · **Priorité**: 🔴 Urgent · **Estimate**: 3 pts · **Sprint**: S1 (03/08 → 09/08) · **Phase**: 3
> **Type**: spike architecture / go-no-go — **aucun code de production attendu**, livrable = 1-pager de décision
> **Eval gate (Décision #22)** : **non applicable** — ne touche ni `{forecast, staffing, recommendation, memory, inbound_parser}`, ni `app/providers/`, ni les prompts. Marquer la PR `eval-exempt`.
> **⚠ Conditionne [HOS-180](https://linear.app/hospitalityagent/issue/HOS-180)** (Agent Hub listing, 5 pts, S7). Voir §Impact sur le plan de sprint.
> **Plan de sprint** : [`docs/planning/phase-3-sprint-plan.md`](../../../docs/planning/phase-3-sprint-plan.md) §S1

## Story

As the **architecte d'Aetherix**,
I want **trancher si Aetherix se branche dans Apaleo Copilot via A2A ou reste un agent MCP standalone**,
so that **le positionnement soit choisi délibérément — distribution contre contrôle — plutôt que subi par défaut d'arbitrage**.

## Contexte

Veille des 20/06 puis 22/06/2026 : Apaleo a lancé l'**Agent Hub** (premier marketplace d'agents IA hôteliers) **et** ouvert un canal **agent-to-agent (A2A)** sur son Copilot, qui accepte aussi l'upload de SOPs en texte brut. Le Copilot couvre ops/housekeeping mais **pas le F&B** — c'est précisément le créneau d'Aetherix.

Cela change la nature du risque W2 : il ne s'agit plus seulement de *« Apaleo absorbe le F&B »*, mais de *« Apaleo devient la plateforme dans laquelle Aetherix doit choisir de se brancher (A2A) ou non (MCP standalone) »*.

**Distinct de [HOS-180](https://linear.app/hospitalityagent/issue/HOS-180)** : ce n'est pas une soumission de listing, c'est un spike d'architecture et un go/no-go sur le protocole lui-même.
**Distinct de [HOS-285](https://linear.app/hospitalityagent/issue/HOS-285)** (S0) : HOS-285 audite la *couverture fonctionnelle* du Trace Agent. HOS-278 tranche le *protocole d'intégration*. Ne pas fusionner les deux livrables.

L'échéance d'origine (*« avant le pilote M4, juillet 2026 »*) est **déjà dépassée** — c'est la raison pour laquelle la story est remontée en tête de timeline lors du re-baseline du 30/07.

## Acceptance Criteria

1. **AC1** — Protocole A2A Apaleo documenté : spec publique disponible ? auth model ? (revue specs + docs dev).
2. **AC2** — Scope des tools Aetherix qui seraient exposés via A2A identifié et listé.
3. **AC3** — Contraintes cartographiées : qui contrôle le contexte, qui a la donnée, risque de lock-in.
4. **AC4** — Impact sur **Décision #19** (Orchestrateur séparé — Aetherix = F&B execution node) et **Décision #21** (Apaleo MCP nommage natif) explicité.
5. **AC5** — Recommandation argumentée écrite : *« Aetherix-as-A2A-agent »* vs *« MCP standalone »* + **condition de bascule explicite** si la recommandation est « wait and see ».
6. **AC6** — Décision consignée dans `docs/context/open-decisions.md` (liée à la décision ouverte *« Apaleo Copilot scope F&B »*).

## Tasks / Subtasks

- [ ] **T1 — Spec A2A** (AC1)
  - [ ] Sources : `apaleo.dev/guides/ai/overview.html`, blog Apaleo, docs Agent Hub.
  - [ ] **Si la spec n'est pas publique** (Apaleo était en *closed alpha* sur MCP — même pattern probable) : c'est un résultat, pas un échec. Écrire « spec non publique au JJ/MM » + le trigger de re-évaluation, et ne pas extrapoler une architecture sur une spec supposée.
  - [ ] Auth model : comparer à l'OAuth2 `client_credentials` déjà utilisé côté MCP Apaleo.
- [ ] **T2 — Scope des tools exposables** (AC2)
  - [ ] Partir du manifeste réel : `backend/app/mcp_server.py` expose **4 tools** — `get_operational_predictions` (v1), `recall_memory` (v1, scope `memory:read`), `get_recommendations_with_memory_context` (v0), `submit_feedback_to_memory`.
  - [ ] **Ne pas scoper l'exposition A2A sur `get_recommendations_with_memory_context`** : la v0 est en sunset au **2026-08-01** (Décision #19, Sunset header) — soit pendant ce sprint. Raisonner sur la surface v1.
  - [ ] Distinguer **construit vs planifié** : `query_cohort_prior` est cité comme primitive exposable (`vision-future.md` l.109, `apaleo-mcp-mapping.md` §5) mais **n'est pas implémenté** — il dépend de la chaîne cold-start ([HOS-192](https://linear.app/hospitalityagent/issue/HOS-192)/[HOS-193](https://linear.app/hospitalityagent/issue/HOS-193), S5-S6). Utiliser la taxonomie Built/Design de [HOS-318](https://linear.app/hospitalityagent/issue/HOS-318) (même sprint) pour étiqueter chaque tool.
- [ ] **T3 — Contraintes & lock-in** (AC3)
  - [ ] Qui contrôle le contexte conversationnel · qui détient la donnée · réversibilité de la sortie.
  - [ ] Le risque central à nommer : si Aetherix devient un *node d'exécution* appelé par Copilot, la couche exécution se commoditise et la relation client passe par Apaleo.
- [ ] **T4 — Impact décisions** (AC4)
  - [ ] **Décision #19** — Aetherix = F&B execution node délégué par `OrchestratorAgent`. Un branchement A2A place *Copilot* en position d'orchestrateur : est-ce compatible avec l'invariant, ou est-ce un second orchestrateur concurrent ? Question centrale du spike.
  - [ ] **Décision #21** — nommage natif PascalCase côté Apaleo. Vérifier si A2A impose une convention distincte (donc un troisième mapping à maintenir après Composio → natif).
- [ ] **T5 — Recommandation + consignation** (AC5, AC6)
  - [ ] 1-pager go/no-go avec condition de bascule datée et vérifiable.
  - [ ] Consigner dans `docs/context/open-decisions.md` sous la décision ouverte existante *« Apaleo Copilot scope F&B »* (l. 22-49).
  - [ ] Mettre à jour `docs/context/monitoring-watchlist.md` §W2 avec la conclusion.

## Dev Notes

### Ancrages (anti-réinvention)

- **Surface MCP réelle** : `backend/app/mcp_server.py` — `TOOLS_MANIFEST` + `V1_TOOLS_MANIFEST`, dispatch via `dispatch_tool` (l. 331), auth bearer `verify_bearer` (l. 50). C'est la réponse factuelle à AC2, pas la doc.
- **Décision #19** : `docs/context/decisions-architecturales.md` l. 81-83 + ADR [`docs/adr/0004-orchestrator-separation.md`](../../../docs/adr/0004-orchestrator-separation.md). Contient l'invariant CI *« zéro import `app.*` dans `orchestrator/` »* et le calendrier de sunset v0.
- **Décision #21** : `docs/context/decisions-architecturales.md` l. 98-102 — PascalCase, enveloppe `{"data": {...}}`, `update_staffing` inexistant côté Apaleo. Inclut l'argument sales (playbook Anthropic « AI for Hotel Owners », tier API-First).
- **Base d'évidence Apaleo** : `docs/competitive/apaleo-mcp-mapping.md` ([HOS-197](https://linear.app/hospitalityagent/issue/HOS-197)) — 235 tools natifs, aucune primitive de forecast/capture-rate/staffing, et §5 recommande explicitement de se positionner en *couche complémentaire* plutôt qu'en concurrence frontale. C'est la thèse à confirmer ou infirmer.
- **Signal d'origine** : `docs/veille/2026-06-22-veille.md` §10/10 et §W2 · `docs/context/monitoring-watchlist.md` §W2 l. 55.
- **Cadrage stratégique** : `docs/context/moat.md` l. 47 — *« être appelable par leur écosystème »* (Décision #21) est déjà posé comme une force, pas une soumission. Le spike doit dire où passe la frontière.

### Pièges

- **⚠ Référence à un fichier inexistant.** Les notes techniques Linear citent `docs/apaleo/agent-hub-integration.md` comme « référence croisée ». **Ce fichier et le répertoire `docs/apaleo/` n'existent pas** — c'est un livrable futur de HOS-180 (AC3). Ne pas le chercher comme source ; c'est une référence *avant*, pas *arrière*.
- **⚠ Sunset MCP v0 le 2026-08-01**, soit pendant ce sprint. Toute analyse d'exposition bâtie sur `get_recommendations_with_memory_context` sera périmée à la livraison.
- **⚠ Gel ADR (Epic 16, NFR2).** Le plan 90j gèle explicitement les nouveaux ADRs jusqu'au 05/10. AC6 demande une consignation dans `open-decisions.md` — c'est compatible. En revanche, une conclusion *« on devient agent A2A »* appellerait normalement un ADR : dans ce cas, livrer la recommandation **avec sa condition de bascule** (AC5) et différer l'ADR, plutôt que de forcer une décision architecturale pendant le gel.
- **Ne pas déborder sur HOS-285.** La question « Trace Agent couvre-t-il du F&B ? » appartient à S0. Si le spike croise un élément de couverture fonctionnelle, le consigner comme input pour HOS-285, pas le trancher ici.
- **Drift de numérotation** : `monitoring-watchlist.md` §W2 (l. 55) désigne HOS-278 comme « Story 10.7 ». Linear dit **Story 10.13** ; 10.7 est [HOS-181](https://linear.app/hospitalityagent/issue/HOS-181) (Hive Memory). Corriger en passant pendant T5.
- **Le livrable est une décision, pas une intégration.** Aucun code n'est attendu. Si le spike produit du prototype, il reste hors `backend/app/` et hors PR de production.

### Impact sur le plan de sprint

C'est **la raison pour laquelle cette story est en S1 et non plus tard**. [HOS-180](https://linear.app/hospitalityagent/issue/HOS-180) (Agent Hub listing, 5 pts) est planifié en **S7** : ses AC1-AC5 décrivent un listing d'agent *standalone* (formulaire, checklist sécurité, `agent_hub_compliant=true`, doc d'intégration client). Si HOS-278 conclut que la bonne voie est *« Aetherix devient la couche F&B de Copilot via A2A »*, alors **HOS-180 doit être re-spécifié avant exécution** — sinon 5 points partent dans un livrable qui décrit le mauvais mode d'intégration.

Trigger de re-plan associé : `phase-3-sprint-plan.md` §Risques **R4**.

### Test Plan

- [ ] Validation manuelle : pas de code de production dans ce spike — output = doc de décision (1-pager).
- [ ] Contrôle de complétude : les 6 AC adressés, chacun avec source citée ou constat d'indisponibilité daté.
- [ ] La recommandation AC5 est actionnable : soit une décision, soit un « wait and see » **assorti d'un trigger vérifiable**.

### References

- [Source: Linear HOS-278] · [Source: backend/app/mcp_server.py:42,50,76,180,331] · [Source: docs/context/decisions-architecturales.md:81-83] · [Source: docs/context/decisions-architecturales.md:98-102] · [Source: docs/adr/0004-orchestrator-separation.md] · [Source: docs/competitive/apaleo-mcp-mapping.md#TL;DR] · [Source: docs/context/monitoring-watchlist.md#W2] · [Source: docs/context/open-decisions.md:22-49] · [Source: docs/veille/2026-06-22-veille.md#10/10] · [Source: docs/context/moat.md:47] · [Source: docs/planning/phase-3-sprint-plan.md#S1]

## Dev Agent Record

### Agent Model Used

Bob (Scrum Master) exécutant `dev-story` · claude-opus-5 · 2026-07-30

### Debug Log References

- Aucun test automatisé — spike documentaire, aucun code de production touché. PR à marquer `eval-exempt`.
- 4 sources publiques exploitées ; 1 inaccessible (PhocusWire, HTTP 403) — non bloquant.
- Aucun ADR créé : gel Epic 16 NFR2 respecté (cf. piège anticipé dans la story).

### Completion Notes List

- **AC1 ✅** — **A2A est annoncé, pas spécifié.** `apaleo.dev` (autorité technique) ne documente que **Claude Plugin + MCP Server** (OAuth 2.0, ~230 tools). Les mentions A2A figurent sur la page produit et la communication Copilot, **au futur** : *« third-party apps and agents will also be able to connect »*. Ni spec, ni auth model, ni endpoint au 30/07/2026. Le cas « spec non publique = résultat, pas échec » anticipé par la story s'est effectivement réalisé.
- **AC2 ✅** — Surface réelle établie depuis `mcp_server.py`, étiquetée avec la taxonomie HOS-318 : **3 tools Built** exposables (`get_operational_predictions`, `recall_memory`, `submit_feedback_to_memory` — dont 1 write path à garder), `get_recommendations_with_memory_context` **exclu** (sunset 01/08), `query_cohort_prior` **Design non implémenté** — à ne jamais inscrire dans un listing avant HOS-193.
- **AC3 ✅** — Contraintes cartographiées en tableau comparatif. Risque central identifié comme **produit, pas technique** : se brancher en A2A ferait disparaître le Daily Receipt derrière l'UI Copilot, commoditisant la couche exécution — soit exactement le wedge.
- **AC4 ✅** — **Décision #19 : aucun conflit**, et c'est ce qui rend l'attente gratuite (Aetherix est déjà conçu pour être appelé par un orchestrateur externe → zéro dette à provisionner). **Décision #21 : pas de conflit immédiat** (#21 régit comment Aetherix *appelle* Apaleo ; A2A régirait comment il *est appelé*) — coût d'un 3ᵉ mapping à chiffrer au moment de la bascule, pas avant.
- **AC5 ✅** — Recommandation : **rester MCP standalone, wait-and-see**. 4 conditions de bascule vérifiables (B1 spec publique · B2 agent F&B tiers · B3 exigence design partner · B4 A2A obligatoire pour Agent Hub) + cadence trimestrielle, premier point **30/10/2026**.
- **AC6 ✅** — Consigné dans `open-decisions.md` sous la décision ouverte parente, et répercuté dans `monitoring-watchlist.md` §W2.
- **🎯 Impact plan de sprint — risque R4 LEVÉ.** [HOS-180](https://linear.app/hospitalityagent/issue/HOS-180) (5 pts, S7) est **confirmé tel quel** : puisque A2A n'est pas actionnable, le listing standalone est le bon mode d'intégration à documenter. Les 5 points de S7 ne partiront pas dans un livrable au mauvais format. C'était la raison d'être du séquencement S1 → S7 ; elle a payé.
- **Correctif de fond sur la veille.** Le trigger du 20/06 formulait A2A comme une *« décision archi time-sensitive avant le pilote M4 (juillet 2026) »*. Cette échéance était intenable : la cible n'existait pas. Remplacée par des conditions de bascule dans W2. La veille avait raison sur l'annonce, elle a surestimé la maturité.
- **Drift de numérotation** — déjà corrigé lors de HOS-285 (W2 désignait HOS-278 comme « Story 10.7 » ; c'est **10.13**).
- **⚠ Limite assumée.** Sources publiques uniquement. Une spec A2A peut exister en *closed alpha* — ce fut le cas du MCP server Apaleo avant ouverture. **Un e-mail au canal développeurs Apaleo trancherait en 48 h** : action PM, non faite, consignée dans les deux livrables.

### File List

- `docs/context/apaleo-a2a-spike-decision.md` *(créé — 1-pager go/no-go)*
- `docs/context/open-decisions.md` *(modifié — sous-section « Volet protocole — A2A : TRANCHÉ »)*
- `docs/context/monitoring-watchlist.md` *(modifié — §W2 : status update A2A, échéance M4 retirée, conditions de bascule)*

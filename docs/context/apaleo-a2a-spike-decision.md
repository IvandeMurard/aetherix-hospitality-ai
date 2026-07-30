# Spike A2A — Aetherix ↔ Apaleo Copilot : go/no-go

> **Story:** [HOS-278](https://linear.app/hospitalityagent/issue/HOS-278) (Story 10.13) — Spike architecture A2A
> **Type:** Décision d'architecture / positionnement — 1-pager go-no-go, aucun code
> **Date d'observation:** 2026-07-30 · **Décideur:** Ivan (PM/architecte)
> **Parent decision:** `docs/context/open-decisions.md` → *« Apaleo Copilot scope F&B »*
> **Related:** Décision #19 (Orchestrateur séparé) · Décision #21 (Apaleo MCP nommage natif) · [HOS-180](https://linear.app/hospitalityagent/issue/HOS-180) (Agent Hub listing) · [HOS-285](https://linear.app/hospitalityagent/issue/HOS-285) (audit Trace Agent)
> **Note gel** : Epic 16 (NFR2) gèle les nouveaux ADRs jusqu'au 05/10/2026. Ce document est un 1-pager de décision consigné dans `open-decisions.md`, **pas un ADR**. Un ADR sera ouvert si et seulement si la condition de bascule §5 se déclenche.

---

## Recommandation

> **Rester MCP standalone. Wait-and-see argumenté sur A2A, avec condition de bascule explicite.**
> **Ne pas re-spécifier [HOS-180](https://linear.app/hospitalityagent/issue/HOS-180)** — le listing Agent Hub tel qu'écrit reste correct.

Ce n'est pas un report par prudence : **il n'y a rien contre quoi construire aujourd'hui.**

---

## AC1 — État de la spec A2A : annoncée, non spécifiée

| Source | Ce qu'elle dit d'A2A |
|--------|----------------------|
| `apaleo.dev` — AI integrations overview *(doc développeur, autorité technique)* | **Rien.** Deux chemins documentés : **Claude Plugin** et **MCP Server** (*« OAuth 2.0 … ~230 tools across booking, finance, inventory, and operations »*). Aucune mention A2A. |
| Page produit AI-powered PMS | *« real-time agent-to-agent (A2A) communication will replace manual coordination »* — **énoncé de vision, au futur** |
| Communication Copilot | *« Third-party apps and agents **will also be able to** connect to Apaleo Copilot, enabling agent-to-agent (A2A) communication »* — **futur** |
| Annonce Agent Hub | **Aucun protocole mentionné** — ni A2A, ni MCP, ni REST. Positionnement marché uniquement. |

**Conclusion AC1.** A2A est un **cap annoncé**, pas une interface disponible. Au 30/07/2026 il n'existe publiquement :

- ❌ aucune spécification de protocole
- ❌ aucun modèle d'authentification documenté
- ❌ aucun endpoint
- ✅ en revanche, un chemin d'intégration tiers **réellement livré et documenté : MCP**, avec OAuth 2.0

La veille des 20-22/06 avait raison sur l'annonce. Elle a surestimé sa maturité en la traitant comme un chemin technique actionnable *« avant le pilote M4 »*. Cette échéance n'était pas tenable : **la cible n'existait pas.**

---

## AC2 — Scope des tools Aetherix exposables via A2A

Manifeste réel (`backend/app/mcp_server.py`), étiqueté selon la taxonomie de [HOS-318](https://linear.app/hospitalityagent/issue/HOS-318) :

| Tool | Version | Statut | Exposable via A2A ? |
|------|---------|--------|---------------------|
| `get_operational_predictions` | v1 | **Built** | Oui — c'est *la* primitive différenciante (absente des 235 tools Apaleo) |
| `recall_memory` (scope `memory:read`) | v1 | **Built** | Oui, sous réserve de scoping strict |
| `submit_feedback_to_memory` | — | **Built** | Oui — mais c'est un **write path** : garde-fous requis (cf. HOS-250, bornes d'entrée) |
| `get_recommendations_with_memory_context` | v0 | **Sunset 2026-08-01** | **Non** — à exclure de tout raisonnement d'exposition |
| `query_cohort_prior` | — | **Design** (non implémenté) | Non — dépend de la chaîne cold-start ([HOS-192](https://linear.app/hospitalityagent/issue/HOS-192)/[HOS-193](https://linear.app/hospitalityagent/issue/HOS-193), S5-S6) |

> ⚠️ `query_cohort_prior` est cité comme primitive exposable dans `vision-future.md` et dans la reco §5 de `apaleo-mcp-mapping.md`. **Il n'existe pas en code.** Ne jamais l'inscrire dans un listing ou une proposition d'intégration avant HOS-193.

**Surface réellement offrable aujourd'hui : 3 tools**, dont 1 en écriture.

---

## AC3 — Contraintes et lock-in

| Dimension | MCP standalone (actuel) | Aetherix-as-A2A-agent |
|-----------|-------------------------|------------------------|
| **Contrôle du contexte** | Aetherix reçoit un appel et répond ; il ne dépend d'aucun contexte conversationnel tiers | Copilot détient le fil, décide quand appeler Aetherix et comment présenter sa réponse |
| **Détention de la donnée** | Inchangé — Aetherix lit Apaleo via OAuth2, stocke sa mémoire propriétaire | Inchangé côté stockage, **mais** l'interaction manager transite par Copilot |
| **Surface produit** | Le **Daily Receipt** est la surface — c'est le wedge (`positionnement-wedge.md`) | Le Receipt disparaît derrière l'UI Copilot → **la couche exécution se commoditise** |
| **Relation client** | Directe | Intermédiée par Apaleo |
| **Réversibilité** | N/A | Faible une fois les hôteliers habitués à l'accès via Copilot |

**Le risque central n'est pas technique, il est produit.** Le wedge d'Aetherix est le rituel du Receipt explicable, pas l'appel de fonction sous-jacent. Se brancher en A2A revient à céder la surface qui porte la différenciation, en échange d'une distribution — sur un protocole dont on ne connaît pas les termes.

---

## AC4 — Impact sur les Décisions #19 et #21

### Décision #19 — Orchestrateur séparé (Aetherix = F&B execution node)

**Aucun conflit — et c'est précisément ce qui rend l'attente gratuite.**

L'invariant #19 (`AetherixEngine` délègue à `OrchestratorAgent` ; zéro import `app.*` dans `orchestrator/`, enforcé en CI) fait qu'Aetherix est **déjà conçu pour être appelé par un orchestrateur externe**. Un branchement A2A futur ne serait qu'un appelant de plus sur les mêmes tools v1. Il n'y a donc **aucune dette d'architecture à provisionner** en restant standalone.

La vraie question posée par A2A est de gouvernance, pas de code : *Copilot deviendrait-il un second orchestrateur, concurrent de l'`OrchestratorAgent` du Mesh ?* Elle ne se tranche pas avant que le protocole existe.

### Décision #21 — Apaleo MCP nommage natif

**Pas de conflit immédiat.** #21 régit la façon dont Aetherix **appelle** Apaleo (PascalCase, enveloppe `{"data": {...}}`). A2A régirait la façon dont Aetherix **est appelé**. Deux directions distinctes.

**Coût à provisionner au moment de la bascule** : si A2A arrive avec sa propre convention de schéma, ce sera un **troisième mapping** à maintenir après la migration Composio → natif. À chiffrer le jour où la spec sort, pas avant.

---

## AC5 — Recommandation argumentée + condition de bascule

### Décision : MCP standalone, wait-and-see

Quatre raisons, par ordre de poids :

1. **Il n'y a pas de spec.** Choisir « A2A » aujourd'hui, c'est s'engager sur une promesse marketing sans auth model ni endpoint. Indécidable, donc non décidé.
2. **Le chemin livré est celui qu'Aetherix emprunte déjà.** MCP est documenté, en production, avec OAuth2 — et Aetherix s'y conforme depuis la Décision #21. Rester coûte **zéro**.
3. **Attendre ne crée aucune dette.** Grâce à la Décision #19, Aetherix est structurellement prêt à être appelé par un orchestrateur externe. L'option reste ouverte sans provision.
4. **Le risque de commoditisation est réel et asymétrique.** Se brancher cède la surface produit ; ne pas se brancher ne cède rien tant qu'aucun hôtelier ne l'exige.

### Conditions de bascule — rouvrir le spike si **l'une** se déclenche

| # | Trigger | Réaction |
|---|---------|----------|
| **B1** | Apaleo publie une **spec A2A publique sur `apaleo.dev`** (protocole + auth model + endpoint) | Rouvrir le spike — 1 sprint, avec chiffrage du 3ᵉ mapping (§AC4) |
| **B2** | Un **tiers publie un agent F&B / covers / staffing** via Agent Hub ou A2A | **Escalade immédiate** — trigger partagé avec [HOS-285](https://linear.app/hospitalityagent/issue/HOS-285) / W2 |
| **B3** | Un **design partner exige** la livraison via Copilot | Rouvrir avec la contrainte commerciale comme entrée dominante |
| **B4** | Apaleo conditionne le **référencement Agent Hub** à une connexion A2A | Rouvrir — devient un prérequis de HOS-180, plus un choix |

**Cadence de re-vérification en l'absence de trigger : trimestrielle** (alignée sur WT3), premier point au **30/10/2026**.

---

## Conséquence directe sur le plan de sprint

**[HOS-180](https://linear.app/hospitalityagent/issue/HOS-180) (Agent Hub listing, 5 pts, S7) est confirmé tel quel — pas de re-spécification.**

Ses AC1-AC5 décrivent un listing d'agent standalone (formulaire, checklist sécurité, `agent_hub_compliant=true`, doc d'intégration client). Puisque A2A n'est pas actionnable, c'est le **bon** mode d'intégration à documenter. Le risque **R4** du plan de sprint (`phase-3-sprint-plan.md`) est **levé** : les 5 points de S7 ne partiront pas dans un livrable au mauvais format.

Corollaire issu de l'audit HOS-285 : la catégorie F&B est **vacante** sur Agent Hub au 30/07. Le listing gagne une valeur défensive — occuper la place avant qu'un tiers ne la prenne (trigger B2).

---

## Limites

- **Sources publiques uniquement.** Aucun contact direct avec l'équipe partenariats Apaleo. Une spec A2A peut exister en *closed alpha* — c'était le cas de leur MCP server avant l'ouverture. **Un e-mail au canal développeurs Apaleo trancherait en 48 h** et n'a pas été envoyé (hors périmètre d'un spike documentaire, et relève du PM).
- Le tableau AC2 reflète `mcp_server.py` au 30/07 ; la sunset v0 du **01/08** intervient dans les jours qui suivent.

---

## Sources

- [apaleo.dev — AI integrations overview](https://apaleo.dev/guides/ai/overview.html)
- [Apaleo — AI-powered PMS](https://apaleo.com/ai-powered-pms-solution)
- [Apaleo — Agent Hub announcement](https://apaleo.com/blog/apaleo-news/apaleo-unveils-agent-hub)
- [Hospitality Net — Apaleo launches AI Copilot](https://www.hospitalitynet.org/news/4131640/apaleo-launches-ai-copilot-to-ease-operational-pressure-on-hotel-teams)
- Internes : `backend/app/mcp_server.py` · `docs/context/decisions-architecturales.md` §19, §21 · `docs/adr/0004-orchestrator-separation.md` · `docs/competitive/apaleo-mcp-mapping.md` · `docs/competitive/apaleo-trace-agent-analysis.md`

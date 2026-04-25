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

## Notes de mise à jour

- 2026-04-25 — Création initiale, extraction depuis note "Vision Avenir" personnelle.

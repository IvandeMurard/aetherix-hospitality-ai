---
title: "Andrew Chen — Agent-First Distribution & Callable Primitives"
date: 2026-03-22
time: 14:13
tags: [intelligence, veille, agent-first, mcp, architecture, distribution, moat, roadmap]
source: claude-code
score: 10/10
---

# Andrew Chen — Agent-First Distribution & Callable Primitives

**Score de pertinence : 10/10**
**Source :** https://x.com/andrewchen/status/2035499669841957162
**Auteur :** Andrew Chen (a16z General Partner)

---

## Thèse principale

Les agents IA créent un nouveau canal de distribution fondamentalement différent des précédents (Web 1.0 : email/search, Web 2.0 : feeds/viral, Mobile : app stores).

> "Products built as APIs/CLIs that can be pulled into new projects by Codex/Claude on the fly"

**Distribution shifts from "top of funnel" → "top of call stack"**

Les agents ne veulent pas de destinations (UI, apps) → ils veulent des **capabilities composables, fiables, à interface claire**.

---

## Points clés

1. **Agent-first, not human-first** — bolter un chat panel sur un produit existant est la "weak form of AI"
2. **Composable, callable, reliable** — les produits futurs ressemblent à des CLIs avec opinionated defaults
3. **"Stripe API moment" for everything** — chaque vertical aura un primitive agent-callable dominant
4. **Brand becomes machine-legible** — reliability, latency, error rates, schema clarity remplacent le design
5. **"Agent SEO"** — ranking factors = success rate across agent runs, ease of integration in chain-of-thought
6. **New moat** = integration depth dans les écosystèmes agentiques (baked into prompts, templates, fine-tunes)
7. **UI = debug layer** — l'infrastructure réelle est orchestrée par les agents, la UI sert aux humains pour "peek"

---

## Lien avec Aetherix

| Thèse Andrew Chen | Décision Aetherix |
|---|---|
| "Agent-first, not human-first" | ✅ Thin Frontend / Fat Backend |
| "Composable, callable capabilities" | ✅ FastAPI = API-first par design |
| "Clean interfaces + structured outputs" | ✅ Anthropic tool_use + schemas Pydantic |
| "Default callable primitive in a domain" | 🎯 **À expliciter dans la roadmap** |

### Angle manquant identifié

Aetherix est actuellement pensé comme SaaS B2B (dashboard + WhatsApp). La question stratégique devient :

> *"What's the minimal, highest-leverage capability we can expose such that agents will repeatedly choose us when building something new?"*

**Réponse pour Aetherix :**
- Endpoint `/forecast` appelable par n'importe quel agent hôtelier
- MCP Server exposant les capabilities F&B core
- CLI que Claude/Codex peut puller dans un workflow de GM d'hôtel

---

## Actions créées

- **TAC-74** — [Architecture] Exposer Aetherix comme primitive agent-callable (MCP Server)
  https://linear.app/ivanportfolio/issue/TAC-74/architecture-exposer-aetherix-comme-primitive-agent-callable-mcp

- **TAC-75** — [Stratégie] Roadmap "Agent SEO" — métriques machine-legible
  https://linear.app/ivanportfolio/issue/TAC-75/strategie-roadmap-agent-seo-metriques-machine-legible

---

**Tags :** `#agent-first` `#distribution` `#mcp` `#architecture` `#roadmap` `#moat` `#agent-seo`

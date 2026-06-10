# OtelAI — Competitive Analysis

**Date:** 2026-06-08
**Owner:** PM
**Type:** Direct competitor F&B (priority 1)
**Source veille:** Batch 06-08 — `memory/market_signals_2026Q2.md` §veille 06-08 enrichi
**Status:** Promu W10 priorité 1 dans `docs/context/monitoring-watchlist.md`

---

## TL;DR

OtelAI (UK/Ireland) est le **concurrent F&B le plus direct identifié à ce jour**. Multi-departmental AI ops platform couvrant 6 domaines incluant **F&B explicite**. Founder Paul Ryan (ex-Accor CTO advisor). ISO 27001 + GDPR. Case client O'Callaghan +8.6% RevPAR. Stack hôtelier enterprise mature (Opera/Guestline/IDeaS/Duetto).

**Pas frontal sur architecture technique** : OtelAI = generalist multi-département vs Aetherix = F&B specialist. **Mais zone grise réelle** : un buyer hôtelier UK/IE peut acheter OtelAI "tout-en-un" et refuser Aetherix add-on.

**Position défensive Aetherix** : vertical depth F&B (Prophet + PMS+POS forecasting predictive) + Apaleo/Mews-first (OtelAI = Opera/Guestline) + Federated HiveMemory (announced Phase 3) + eval-by-design.

---

## Profile factuel

| Attribut | Valeur | Source |
|---|---|---|
| Founded | Non disclosed publiquement (~2024-2025 inféré R&D timeline) | Site |
| HQ | UK / Ireland | Site |
| Founders | Paul Ryan (ex-Accor advisor, hospitality background) + équipe non listée | Site |
| Team size | Non disclosed | — |
| Funding | Non disclosed | — |
| Customers nommés | O'Callaghan Collection (case study public +8.6% RevPAR) | Site case study |
| Compliance | ISO 27001 + GDPR | Site |
| Markets | UK · Ireland · Europe continent inferé | Site |
| Public pricing | Non visible (enterprise) | Site |
| Concurrents revendiqués | — | — |

## Produit — scope réel

### 6 départements couverts

| Département | Scope OtelAI |
|---|---|
| **Revenue Management** | RevPAR optimization, pricing recommendations |
| **F&B** | Operations management, F&B-specific workflows (scope detail non public) |
| **Payroll** | HR + payroll automation |
| **Operations** | Multi-property ops coordination |
| **Procurement** | Supplier + inventory management |
| **Guest Reviews** | Review monitoring + response automation |

**F&B explicite mais scope detail non disclosed** — à investiguer : forecasting predictive ? staffing ? procurement only ?

### Intégrations PMS / RMS connues

- **Opera** (Oracle)
- **Guestline**
- **IDeaS** (RMS)
- **Duetto** (RMS)
- **PAS** d'Apaleo ni Mews mentionné publiquement

### Métriques case studies publiées

- O'Callaghan Collection : **+8.6% RevPAR** (post-OtelAI deployment, baseline non disclosed)
- Autres : non public

### Ce qui N'EST PAS publicly disclosed

- Tech stack LLM / providers
- Memory architecture
- MCP integration (probable absent vs Aetherix)
- F&B forecasting predictive algorithms
- Pricing transparency
- Roadmap publique
- Funding stage

## Comparaison frontale vs Aetherix

| Axe | OtelAI | Aetherix |
|---|---|---|
| **Domaine** | 6 départements incl. F&B | F&B specialist (forecast + staffing + receipts) |
| **Scope F&B** | Mentionné, scope detail unclear | Predictive forecasting + staffing recommendations + memory + receipts |
| **Customer ICP** | Mid-market à enterprise UK/IE/EU | Hotel managers + F&B directors EU |
| **PMS integration** | Opera/Guestline (enterprise) | Apaleo + Mews (API-first modern) |
| **RMS integration** | IDeaS/Duetto (enterprise) | Non scope (différenciation explicite) |
| **MCP** | Non publiquement mentionné | Server v0 shipped + v1 spec'd (ADR-0004) |
| **Memory architecture** | Non publiquement mentionné | 2-layer Private + Hive Memory (Décision #2) + Graphe de contexte CTE (ADR-0008) |
| **Eval-by-design** | Non publiquement mentionné | Framework Qonto adopté (Décision #22, ADR-0007) |
| **Sales evidence** | O'Callaghan +8.6% RevPAR | À construire Phase 3 pilote |
| **Compliance** | ISO 27001 + GDPR | RLS 14/14 tables, SOC2 future |
| **Pricing transparency** | Non public (enterprise) | À définir HOS-179 P3-5 |
| **Stage** | Stealth (founder + team inconnus) | Pre-pilot solo founder |
| **Funding** | Non disclosed | Bootstrap |

## Verdict — concurrent adjacent multi-département, pas frontal F&B specialist

### Pourquoi pas frontal aujourd'hui

OtelAI fait **6 départements**. Aetherix fait **F&B uniquement avec profondeur**. La différenciation suit le frame :
- *"OtelAI manages 6 departments. Aetherix masters one — F&B."*
- *"Specialist beats generalist when stakes are operational decisions (30-45% labor costs, 25% food waste)."*

### Pourquoi adjacent quand même dangereux

1. **PMS stack différent** : OtelAI = Opera/Guestline (enterprise legacy), Aetherix = Apaleo/Mews (modern API-first). Buyers chevauchent peu mais l'UK/IE mid-market enterprise peut contenir des hôtels Apaleo/Mews qui considéreraient les 2.
2. **Marriott/Hilton flag pressure** : si un groupe enterprise est sur Opera/Guestline et achète OtelAI, ils ne questionneront pas leur PMS pour passer à Apaleo + Aetherix. Verrou ecosystem.
3. **F&B scope inconnu** : OtelAI peut très bien étendre vers F&B forecasting predictive natif. Plus de risque de pivot interne que vrai frontal aujourd'hui.

### Défense structurelle Aetherix

- **Vertical depth F&B** : Prophet + regressors (météo/events/occupancy) + cold-start meta-learner (ADR-0005) + Graphe de contexte (ADR-0008) = stack F&B expertise qui prend des années à construire
- **PMS-first API-modern** : Apaleo+Mews ≠ Opera/Guestline stack. Aetherix vit dans l'ecosystem PMS modern (Mews OS, Apaleo Marketplace).
- **Memory architecture documentée** : 2 layers + cold-start meta-learner + graphe = différenciateur defensible vs "AI assistant" générique OtelAI
- **Eval-by-design + reliability** : OtelAI n'a aucune communication publique sur reliability framework (vs Qonto/Aetherix)
- **Federated HiveMemory announcement Phase 3** : OtelAI = data closed-stack (probable), Aetherix = announced federated cohort intelligence

## Stratégie recommandée

### Monitoring (priorité 1 — mensuel via Cowork)

**Triggers à monitorer chaque lundi** :
- Annonces produit *"F&B forecasting"*, *"covers prediction"*, *"staffing recommendations"* (= signe d'extension vers notre scope)
- Embauches LinkedIn : "ML engineer", "data scientist", "forecast", "F&B product"
- Partenariats PMS publics : Apaleo Marketplace, Mews Marketplace (= signe d'expansion ecosystem)
- Funding rounds (Series A+ = signal agressivité GTM)
- Roadmap / changelog publique (actuellement absent → première publication = signal majeur)
- Customer wins publics (Marriott/Hilton/IHG flag = enterprise capture)

### Positioning narrative (immédiat)

> *"OtelAI manages 6 departments. Aetherix masters one — F&B. When 30-45% of operating costs depend on a single forecast, specialist beats generalist."*

Snippet H-8 ajouté `docs/marketing/positioning-snippets.md`.

### Action exploratoire — outreach ?

Founder Paul Ryan accessible via LinkedIn. Conversation founder-to-founder pour évaluer "partnership" (Aetherix F&B specialist + OtelAI 5 autres départements) vs "concurrence" — coût bas, signal info élevé. À planifier **post-Phase 3 pilote** (besoin d'avoir traction concrète à montrer).

### Action prioritaire — Apaleo Marketplace listing

Shipper notre listing dans Apaleo Marketplace **avant** que OtelAI n'y apparaisse. OtelAI n'a pas mentionné Apaleo publiquement, fenêtre ouverte. Priorité Phase 3 Track A (HOS-176 region).

## Sources

- [OtelAI website](https://www.otelai.com/)
- O'Callaghan Collection case study (site OtelAI)
- Veille hebdo 2026-06-08 (`docs/veille/2026-06-08-veille.md`)
- Analyse PM session 2026-06-08 (`memory/market_signals_2026Q2.md`)

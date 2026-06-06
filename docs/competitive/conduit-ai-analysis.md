# Conduit.ai — Competitive Analysis

**Date:** 2026-06-04
**Owner:** PM
**Type:** Competitive intel (adjacent player, asymmetric threat)
**Status:** Live monitoring — promoted to monthly canari priority 1

---

## TL;DR

Conduit.ai (YC W24, 15 employees, San Francisco) est **adjacent, pas frontal** : conversation/voice/workflow automation pour hospitality, **pas de F&B forecasting/staffing predictive**. Mais asymétrie massive : 1000+ brands, Marriott logo, YC capital (part de pool $152.6M raised avec Duve/Chatlyn/Canary), SOC2 Type II + HIPAA. 2 ans d'avance distribution + capital.

**Risque principal** : Conduit étend "internal agents" vers F&B forecasting native (pivot technique majeur requis) OU claim mindshare via marketing "F&B analytics" sans tech derrière.

**Position défensive Aetherix** : vertical depth F&B + Prophet + PMS+POS + eval-by-design + Apaleo first-mover.

---

## Profile factuel

| Attribut | Valeur | Source |
|---|---|---|
| Founded | 2024 (YC Winter 2024) | YC profile |
| HQ | San Francisco | YC |
| Team | 15 employees | YC |
| Founders | Cole Rubin (real estate + tech) · Punn Kam (ex-Google + family office trader/market-maker) | YC |
| Funding | Non disclosed individuellement, part d'un pool **$152.6M** raised collectif (Conduit + Duve + Chatlyn + Canary) | [Hotel Dive 2026](https://www.hoteldive.com/news/hospitality-tech-attracts-1b-in-funding-pms-ai-leaders/817439/) |
| Customers | 1,000+ marques · 120+ pays · **Marriott logo** + 15 case studies publiques | Site Conduit |
| G2 rating | 4.7/5 | Site |
| Compliance | SOC 2 Type II + HIPAA | Site |
| GTM verticals | Hotel Groups · Independent Hotels · Short-Term Rentals | Site |
| Concurrents revendiqués | Canary · Akia · Revinate · Volara · Zendesk · Salesforce · Intercom | Site |
| Public pricing | Page existe, contenu non visible publiquement | Site |

## Produit — scope réel

### 3 piliers fonctionnels

1. **Chat Agents** — email, WhatsApp, OTA, social (multi-canal guest comm)
2. **Voice Agents** — phone calls 24/7
3. **Internal Agents** — *"works with your team using the tools they already use"* ← **le pilier border-zone vs Aetherix**

### Features publiquement listées

- Multilingue (greet every guest in their language)
- Escalation handling ("Surface what AI couldn't handle")
- Procedures engine (multi-étapes ops)
- Observability ("Inspect every step your agent takes")
- API + **MCP support** (mentionné, profondeur non-détaillée)
- "Learning" automatique ("Agents learn from every interaction")
- Native integrations + custom tools

### Métriques case studies publiées

- HomeHop : 70% guest messaging automation
- Renjoy : 40% automation in first month
- (15+ case studies au total — Bali Luxury Stays, Beckon Homes, Cascadia Getaways, Lauderdale Boutique, etc.)

### Ce qui N'est PAS publiquement disclosed

- LLM partner / model architecture
- Memory architecture (rétention, vector DB, graph?)
- PMS spécifiques intégrés (zéro mention Apaleo/Mews/Opera/Cloudbeds)
- Pricing
- Roadmap publique / changelog
- Knowledge graph
- Team / founders à part les 2 listés YC

## Comparaison frontale vs Aetherix

| Axe | Conduit | Aetherix |
|---|---|---|
| **Domaine** | Conversation (guest chat/voice) + workflow automation interne | F&B back-of-house (forecast/staffing/receipts) |
| **Primary I/O** | Conversation (text/voice in-out) | Data → predictions → push notification |
| **Customer ICP** | Hotel groups + indep + STR | Hotel managers + F&B directors |
| **Stakeholder cible** | Front-desk / customer service / ops manager (généraliste) | F&B director (spécialiste back-of-house) |
| **PMS integration** | Non-disclosed | Apaleo first-class + Mews Phase 4 |
| **F&B forecasting** | ❌ Pas mentionné | ✅ Core product |
| **Staffing prediction** | ❌ Pas mentionné | ✅ Core product |
| **Voice** | ✅ Pilier produit | Opt-in Phase 5+ (Décision #4) |
| **MCP** | Mentionné, profondeur inconnue | Server v0 shipped, v1 spec'd (ADR-0004) |
| **Knowledge graph** | Non mentionné publiquement | À introduire Phase 4 (en débat actuel) |
| **Memory architecture** | Non mentionné | 2-layer Private + Hive (Décision #2) + cold-start meta-learner (ADR-0005) |
| **Eval-by-design** | Aucune communication publique | Framework Qonto adopté (Décision #22, ADR-0007) |
| **Reliability narrative** | Métriques business case studies | Pyramide 5 dimensions Qonto + CI gate |
| **Stage** | YC W24, 15 employees, ~2 ans | Pre-pilot, solo founder |
| **Customers paid** | 1000+ marques | 0 pilote (Phase 3 kickoff) |
| **Funding stage** | YC-backed, part de pool $152.6M | Bootstrap |
| **Enterprise compliance** | SOC 2 Type II + HIPAA | RLS 14/14 tables, pas SOC2 yet |

## Verdict — pas frontal, mais menace asymétrique

### Pourquoi pas frontal

Conduit ne fait **pas** de F&B forecasting / staffing prediction. Leur "internal agents" = workflow automation des tâches que le team fait déjà (procedures engine, escalation, ops automation), pas du predictive analytics F&B. Leur savoir-faire est conversational/workflow, pas time-series ML.

### Pourquoi asymétrique

Conduit a 1000+ brands, Marriott, YC capital, SOC2, 15 employés, 2 ans d'avance marché. Aetherix a 0 design partner et un solo founder. **Asymétrie de distribution + capital + ressources énorme.**

### 3 zones de risque réel

| Risque | Probabilité | Sévérité | Mitigation |
|---|---|---|---|
| **R1** Conduit étend "internal agents" vers F&B forecasting native | Moyenne — pivot technique majeur requis (stack conversational, pas time-series ML) | Sévère si réalisé | Speed Phase 3 pilote + ship eval-by-design avant qu'ils ne claim "reliability" |
| **R2** Hôtel Marriott achète Conduit pour comm + workflow et **refuse** Aetherix en plus *("on a déjà notre AI hospitality")* | Élevée sur enterprise | Sévère sur enterprise GTM | Reframe positioning *"Conduit answers the phone. Aetherix predicts who's calling for dinner."* — complémentarité explicite |
| **R3** Conduit annonce module "F&B analytics" en marketing/promesse même sans tech derrière → claim mindshare | Modérée | Modérée à sévère selon traction | Veille mensuelle + counter-positioning narrative sur eval-by-design (showing depth) |

### Défense structurelle Aetherix

- **Vertical depth** : F&B forecasting + Prophet + PMS+POS data fusion = expertise domaine + ML stack qui prend des années à construire
- **PMS-first** : Apaleo connection profonde + Mews Phase 4 — Conduit reste vague sur PMS, signe qu'ils ne sont pas PMS-native
- **Eval-by-design + reliability** : Conduit n'a aucune communication publique sur reliability (vs Qonto/Aetherix maintenant). Différenciateur sur enterprise quand SOC2 ne suffit plus
- **Speed de niche** : on peut shipper pilote F&B "ground truth" avant que Conduit ne pivot

## Stratégie recommandée

### Monitoring (mensuel via Cowork)

Promu **priorité 1** dans la watchlist `docs/context/monitoring-watchlist.md` (au-dessus du canari Apaleo Copilot).

**Triggers à monitorer** :
- Annonces produit "Predictive analytics" / "F&B forecasting" / "Staffing recommendations"
- Embauches LinkedIn "ML engineer" / "data scientist" / "forecast" / "operations research"
- Partenariats PMS publics (Apaleo Marketplace, Mews, Opera)
- Marriott press release mentioning Conduit scope expansion
- Funding rounds individuels (signal d'agressivité GTM)
- Annonces SOC2-only competitors (claim reliability sans framework eval)

### Positioning narrative

> *"Conduit answers the phone. Aetherix predicts who's calling for dinner tomorrow."*

Complémentarité explicite. Évite frame "concurrence frontale" (perdu d'avance asymétrie ressources). Ouvre possibilité partenariat.

### Action exploratoire — outreach YC network

Cole Rubin et Punn Kam sont accessibles via YC network. Conversation founder-to-founder pour évaluer "partnership" vs "concurrence" — coût bas, signal info élevé. À planifier post-Phase 3 pilote (besoin d'avoir une traction concrète à montrer).

### Action prioritaire — Apaleo Agent Hub

Shipper le listing Aetherix sur Apaleo Agent Hub **avant** que Conduit n'y apparaisse. Conduit n'a pas mentionné Apaleo publiquement, fenêtre ouverte. Priorité Phase 3 Track A (HOS-176 region).

## Sources

- [Conduit.ai (site)](https://www.conduit.ai/)
- [Conduit YC profile](https://www.ycombinator.com/companies/conduit-ai)
- [Hotel Dive — Hospitality tech $1B funding](https://www.hoteldive.com/news/hospitality-tech-attracts-1b-in-funding-pms-ai-leaders/817439/)
- [Hotel Technology News — $1B PMS + AI funding research](https://hoteltechnologynews.com/2026/04/research-hospitality-technology-tops-1-billion-across-40-startups-with-pms-and-ai-platforms-capturing-the-largest-share/)

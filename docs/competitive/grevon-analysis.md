# Grevon — Competitive Analysis

**Date:** 2026-06-23
**Owner:** PM
**Type:** Concurrent adjacent multi-produit, MCP-natif (priorité 1 — escaladé depuis intel HITEC 06-22)
**Source veille:** `docs/veille/2026-06-22-veille.md` + recherche approfondie 06-23 (au-delà de la homepage)
**Status:** W14 dans `docs/context/monitoring-watchlist.md` — escaladé suite à cette analyse

---

## TL;DR

Grevon n'est pas un concurrent "Ops staffing" isolé — c'est une **suite verticale complète AI-native pour l'hôtellerie**, fondée par des vétérans RMS Cloud (PMS établi), couvrant booking (Pulse), voice (Echo), staff Q&A (Ops), data hub MCP (Kore), connectivité PMS (Link), et deux produits à venir fin 2026 : distribution outbound vers LLMs (Axiom) et analytics ROI (Axis). Architecture **PMS-agnostique** (RMS Cloud, Cloudbeds, Oracle, **Apaleo**, Maxxton, Mews, Clock) — positionnement différent d'Apaleo/Mews qui possèdent leur propre PMS.

**Pas frontal sur le forecasting/staffing predictive F&B** (Ops = Q&A conversationnel sur SOPs + contexte PMS, aucune mention forecasting/covers/staffing prediction trouvée même en creusant les pages produit). **Mais zone de recoupement réelle et multiple** : (1) Ops pourrait évoluer vers du predictive, (2) Axiom recoupe directement la course UCP vs MCP (WT3) côté distribution agentique, (3) le thème "AIO" (Agent Intelligence Optimization) qu'ils développent en contenu (`/blog` "AIO Academy") est le même concept que l'Agent SEO interne Aetherix (`backend/app/middleware/agent_tracking.py`, P1-5/HOS-72) — validation marché externe d'une thèse qu'on pensait être un avantage propriétaire de framing.

---

## Profile factuel

| Attribut | Valeur | Source |
|---|---|---|
| Founded | Non disclosed (lancement public HITEC juin 2026) | Site |
| HQ | Non précisé sur les pages consultées | Site |
| Founders / leadership | **Tom Buttigieg** (CEO, ~10 ans RMS Cloud + Marketplacer) · **Todd Sabo** (CGO, 20+ ans hospitality SaaS) · **Zen Valli** (Chief Commercial & Strategy, 15+ ans) · **Peter Buttigieg** (Non-Exec Chairman, **fondateur de RMS Cloud**) | `/about.html` |
| Team size | Non disclosed | — |
| Funding | Non disclosed | — |
| Customers | 200+ propriétés actives, 12 pays (claim homepage) | Site |
| Compliance | GDPR/PCI DSS mentionné (homepage) | Site |
| Pricing | Non public sur les pages consultées | Site |
| Mission | *"To empower hospitality operators worldwide with AI-driven infrastructure that simplifies complexity, drives direct revenue, and builds lasting guest relationships."* | `/about.html` |
| Vision | *"Foundational AI layer enabling properties of all sizes to compete equally through intelligent, agentic technology."* | `/about.html` |
| Philosophie | *"Built AI-native — not retrofitted with AI"* | `/about.html`, répété sur plusieurs pages produit |

**Lecture clé** : Peter Buttigieg (fondateur RMS Cloud) + Tom Buttigieg (CEO, ex-RMS Cloud) = Grevon a vraisemblablement un accès réseau/distribution direct à la base client RMS Cloud existante. Différent du pattern OtelAI/TH1.ai (founders hospitality mais sans PMS propre en amont) — risque GTM plus rapide si RMS Cloud devient un canal de distribution informel.

## Produit — architecture complète (au-delà de la homepage)

### Vue d'ensemble du flux

```
Grevon Link (connecteur PMS)
   → Grevon Kore (hub MCP central — enrichit/valide/traduit en format LLM-readable)
      → Grevon Pulse (booking agent, inquiry→reservation)
      → Grevon Echo (voice agent, inbound 24/7)
      → Grevon Ops (staff Q&A conversationnel, SOPs + contexte PMS)
      → Grevon Axiom (à venir, fin 2026 — feed outbound vers LLMs/partenaires externes)
   → Grevon Axis (à venir, fin 2026 — dashboard analytics ROI/attribution)
```

### Détail par produit

| Produit | Rôle | Statut |
|---|---|---|
| **Link** | Connecteur API PMS→Kore. Supporte RMS Cloud, Cloudbeds, Oracle, **Apaleo**, Maxxton, Mews, Clock PMS + custom. 4-step flow : Link récupère data PMS → Kore structure/valide → agents (Pulse/Echo/Ops) interrogent Kore → booking confirmé écrit retour au PMS. | Shipped |
| **Kore** | Hub de données MCP central. Claim : va au-delà d'une API PMS classique — "enriches, validates, and translates raw data into a format LLMs actually understand." Ingère PMS + site web + SOPs/docs uploadés + reviews + contexte local + sources tierces. Feeds temps réel (pas de sync planifiée). | Shipped |
| **Ops** | Agent Q&A staff multi-département (front desk, housekeeping, maintenance). "Trained on your property's own SOPs, house rules, supplier contacts, and operational documents" + contexte PMS via Kore. Interaction conversationnelle naturelle. **Aucune architecture technique disclosed** (RAG/vector search/rules — non spécifié). **Aucune mention forecasting/staffing prediction/covers** trouvée même sur la page produit dédiée. | Shipped |
| **Pulse** | Booking agent — gère le guest journey inquiry→reservation. Business model = direct booking, élimination commission OTA. | Shipped |
| **Echo** | Voice agent, appels inbound 24/7. | Shipped |
| **Axiom** | *"The data feed that keeps external AI models and partners in sync with your live property."* Feed structuré (rates/availability/policies/amenities/photos) vers ChatGPT/Gemini/Perplexity et "AI trip planners". Accès scoped/révocable, anonymisé par défaut (jamais de data guest exposée), payloads signés/horodatés, enforcement rate parity. **Recoupe directement WT3 (UCP vs MCP)** — c'est une troisième approche de la même problématique "rendre l'inventaire hôtelier lisible/exécutable par les agents IA", orientée distribution plutôt que standard ouvert. | En dev, GA fin 2026 |
| **Axis** | Dashboard analytics — attribution booking par canal (agents IA vs OTA vs direct), monitoring performance des agents Grevon (conversion/abandon/escalade), ROI margin recovery vs commissions OTA évitées, benchmarking anonymisé vs propriétés similaires, alertes anomalies (rate parity drops). | En dev, GA fin 2026 |

### "AIO" — Agent Intelligence Optimization (thèse contenu/positioning)

Page `/solutions/agents.html` : Grevon identifie que les LLMs excellent en recherche/découverte mais échouent à la transaction (l'utilisateur quitte la conversation IA pour réserver ailleurs). Solution proposée = Axiom comme connecteur unique pour le cycle de transaction complet (inventaire temps réel + checkout unifié multi-propriété + paiement). Ils nomment ce problème **"AIO" (Agent Intelligence Optimization)** — équivalent SEO pour la visibilité auprès des agents IA. Ont un blog dédié ("AIO Academy", `/blog/index.html`) construit autour de cette thèse de contenu.

**Convergence notable** : Aetherix a déjà un concept interne d'"Agent SEO" (middleware `agent_tracking.py`, P1-5/HOS-72) — Grevon valide la même thèse de marché indépendamment, avec un blog entier dédié et un nom de catégorie packagé ("AIO"). Pas une menace directe (différent produit, différent niveau — eux sont sur la distribution/booking, Aetherix sur l'exécution F&B) mais signal que ce framing devient un terrain de positionnement disputé, pas un avantage propriétaire.

### Intégration / process technique

Documentation développeur **"Coming Soon"** (`/docs.html`) — pas de procédure d'intégration step-by-step publique, pas de timeframe. Contact `integration@grevon.ai` pour accès API. PMS credentials restent côté hôtelier (Grevon ne stocke pas les clés d'accès brutes) — posture sécurité similaire à l'approche OAuth2 minimal-scopes d'Aetherix (Décision #11).

## Comparaison frontale vs Aetherix

| Axe | Grevon | Aetherix |
|---|---|---|
| **Domaine** | Suite complète : booking + voice + staff Q&A + data hub + distribution + analytics | F&B specialist (forecast + staffing + receipts) |
| **Scope F&B** | Aucun forecasting/staffing predictive disclosed, même en profondeur | Predictive forecasting + staffing recommendations + memory + receipts |
| **PMS integration** | PMS-agnostique : RMS Cloud, Cloudbeds, Oracle, Apaleo, Maxxton, Mews, Clock | Apaleo + Mews (API-first modern, scope volontairement restreint) |
| **MCP** | Kore = hub MCP central day 1, claim "AI-native not retrofitted" | Server v0 shipped + v1 spec'd (ADR-0004), même thèse "AI-native" |
| **Distribution agentique** | Axiom (feed outbound vers ChatGPT/Gemini/Perplexity, en dev) | Non scope — différenciation explicite vers exécution ops, pas distribution |
| **Founders / réseau** | Lignée RMS Cloud (PMS établi, accès distribution potentiel) | Solo founder, pre-pilot |
| **Memory architecture** | Non disclosed (Kore enrichit/valide mais pas de mémoire opérationnelle F&B spécifique mentionnée) | 2-layer Private + Hive Memory (Décision #2) + Graphe de contexte CTE (ADR-0008) |
| **Eval-by-design** | Non publiquement mentionné | Framework Qonto adopté (Décision #22, ADR-0007) |
| **Sales evidence** | 200+ propriétés, 12 pays (claim agrégé, pas de case study chiffré trouvé) | À construire Phase 3 pilote |
| **Stage** | Lancé HITEC 2026, produits centraux shipped, 2 produits en dev GA fin 2026 | Pre-pilot solo founder |

## Verdict — concurrent adjacent multi-produit, recoupement réel sur 3 axes spécifiques (pas le forecasting F&B)

### Pourquoi pas frontal aujourd'hui

Grevon couvre booking/voice/staff-Q&A/distribution — Aetherix fait F&B forecasting/staffing avec profondeur. Même logique de différenciation que vs OtelAI/TH1.ai : *"Grevon orchestre la transaction et l'opération générique. Aetherix maîtrise une décision spécifique à fort enjeu — combien de covers, combien de staff, demain."*

### Pourquoi le recoupement est réel quand même

1. **Ops peut évoluer** : aujourd'hui Q&A conversationnel sur SOPs, mais l'architecture (Kore = données enrichies temps réel + agent conversationnel dessus) est triviale à étendre vers du predictive si Grevon le décide — même schéma de risque que W2 Apaleo Copilot.
2. **Axiom recoupe WT3 directement** : une troisième tentative de résoudre "comment l'inventaire hôtelier devient lisible par les agents IA", concurrente conceptuelle d'UCP (Amadeus/Google) et de l'approche A2A/Agent Hub d'Apaleo (W2). Si Axiom devient un standard de facto avant qu'Aetherix n'ait tranché son propre positionnement MCP vs A2A, ça ajoute un troisième acteur à arbitrer.
3. **Lignée RMS Cloud** : accès réseau founder à une base PMS établie — vitesse de distribution potentiellement supérieure à un concurrent stealth pur.

### Défense structurelle Aetherix (inchangée, renforcée)

- **Vertical depth F&B** : Prophet + regressors + cold-start meta-learner (ADR-0005) + Graphe de contexte (ADR-0008) — Grevon n'a aucune trace de ce niveau de profondeur F&B disclosed
- **Apaleo Marketplace + Agent Hub listing rapide** (HOS-180/278) : Grevon liste déjà Apaleo dans ses PMS supportés — fenêtre de chevauchement marketplace à surveiller (trigger déjà dans W14)
- **Positioning H-8** "specialist beats generalist" — applicable verbatim

## Stratégie recommandée

### Monitoring (cadence mensuelle, W14)

- Détail produit Ops révélant covers/labor forecasting explicite
- Lancement Axiom (GA fin 2026) — vérifier chevauchement concret avec décision A2A/MCP Aetherix (HOS-278)
- Lancement Axis — benchmarking anonymisé inter-propriétés = pattern proche de la thèse Hive Memory fédérée Aetherix, à surveiller pour positionnement
- Funding round / customer wins enterprise nommés
- Apparition sur Apaleo Agent Hub (chevauchement marketplace direct)

### Pas d'action immédiate

Aucun trigger de Scénario C (forecasting F&B natif) déclenché. Documenter et surveiller — pas de pivot de roadmap requis aujourd'hui.

## Sources

- [Grevon homepage](http://grevon.ai/) + pages produit `/platform/{pulse,echo,ops,kore,link,axiom,axis}.html`, `/about.html`, `/docs.html`, `/solutions/agents.html`
- Veille HITEC 2026 (`docs/veille/2026-06-22-veille.md`)
- Recherche approfondie 2026-06-23 (suite à correction process — cf. `feedback_working_style.md` memory, ne pas s'arrêter à la homepage)

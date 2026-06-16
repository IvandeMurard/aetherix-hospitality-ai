# Hospitality Agentic Mesh — Source de vérité cross-repos

> **Document canonique.** Toute session LLM (Claude sur Aetherix, Gemini sur Tacet, futur agent sur Anima)
> doit charger ce fichier pour avoir le contexte architectural global.
> **Repo canonique :** `aetherix-hospitality-ai/docs/mesh-architecture.md`
> **Référencé par :** `tacet-app/ARCHITECTURE_MANIFEST.md` · `aetherix/CLAUDE.md §Fichiers clés`
> **Mettre à jour :** toute décision qui change l'interface MCP d'un nœud, le rôle d'un nœud, ou le séquençage de phase.

---

## 1. Vision

Le Hospitality Agentic Mesh est une plateforme de nœuds IA spécialisés, indépendants, communicant exclusivement via **MCP (Model Context Protocol)**. Chaque nœud a un bounded context strict. Aucun nœud n'importe de code d'un autre nœud — l'interface est le schema MCP.

**Positionnement marché :** le PMS (Apaleo, Mews) est le Commerce Hub (6 couches, cf. hospitality.today 2026). Le Mesh opère en dehors de ces 6 couches commerciales — il orchestre l'opérationnel hôtelier (F&B, environnement, guest context) et s'y branche via MCP.

---

## 2. Nœuds du Mesh

### Aetherix — F&B Execution Node
**Repo :** `aetherix-hospitality-ai`
**Rôle :** Exécution opérationnelle F&B. Ne décide pas. Ne route pas. Exécute.
**Bounded context :** forecast couverts, staffing, mémoire opérationnelle, receipts, alertes WhatsApp.
**MCP tools exposés (v1) :**
- `get_operational_predictions(target_date, service_type, context)` → forecast + staffing
- `recall_memory(query, k_memory)` → hits mémoire opérationnelle (pgvector)
- `submit_feedback_to_memory(recommendation_id, outcome, notes)` → apprentissage
**Stack :** FastAPI + Python 3.12 · Prophet · pgvector (Mistral 1024d) · Supabase · Fly.io cdg
**ADR de référence :** `docs/adr/0004-orchestrator-separation.md`

---

### Tacet — Sensory Node (Jumeau Environnemental)
**Repo :** `tacet-app`
**Rôle :** Ingestion de données chaotiques (météo, bruit, open data) → signaux structurés. Ne prend pas de décision. Produit des scores.
**Bounded context :** risque environnemental par chambre/zone, modificateurs de prix prédictifs pour le RMS, signaux pour l'Orchestrateur.
**MCP tools exposés (cible) :**
- `get_room_risk_score(room_id, date_range)` → score risque environnemental (bruit, météo, travaux)
- `get_pricing_modifier(property_id, date)` → delta tarifaire suggéré (neutre — la politique de l'hôtel décide de l'action)
**Stack :** TBD (Gemini/Antigravity session)
**ADR de référence :** `tacet-app/ARCHITECTURE_MANIFEST.md`

---

### Orchestrateur — Supervisory Agent
**Repo :** Phase 3 → `aetherix-hospitality-ai/backend/orchestrator/` (module) · Phase 4 → repo dédié
**Rôle :** LLM root stateless. Lit les événements (Tacet, PMS), sélectionne les tools, chaîne les appels MCP, applique les business rules de l'hôtel. C'est le seul composant avec logique de décision et boucle de feedback.
**Ce qu'il N'est PAS :** un service métier. Il ne sait pas ce qu'est un couvert, une chambre, ou un vol en retard. Il appelle les nœuds qui le savent.
**Statut Phase 3 :** proto-stub dans `backend/orchestrator/agent.py`. Boucle agentique complète = Phase 4.
**Interface :** appelle uniquement via MCP client HTTP. Zéro import Python depuis `app/`.

---

### Anima — Guest Cognition Layer
**Repo :** à créer Phase 4
**Rôle :** Couche cognitive individuelle par guest. Maintient et consolide l'état émotionnel, logistique et relationnel : retard de vol, historique CRM, humeur inférée, statut VIP, préférences idiosyncratiques, plaintes passées. Chaque claim est confidence-weighted (cf. ADR-0011 D2).
**Principe directeur :** permettre à l'Orchestrateur de décider contextuellement *sans baisser les prix* — la bonne réponse au bon guest, au bon moment.
**Périmètre strict (ADR-0011 D1) :** compréhension individuelle uniquement. Pas de policy, de fédération, ni de décision — ces responsabilités appartiennent au Hive/Mesh et à l'Orchestrateur.

#### Architecture mémoire — 4 couches temporelles

Contrairement à Aetherix (mémoire opérationnelle largement long-terme — un feedback de 6 mois reste valide), Anima nécessite une distinction stricte entre couches temporelles. La décision "offrir un upgrade maintenant" dépend de QUELLE couche on interroge.

| Couche | Storage | TTL | Contenu | Décisions qu'elle alimente |
|--------|---------|-----|---------|---------------------------|
| **1. Working memory** | Redis | Durée du séjour | "Vol en retard de 3h ce soir · vient de se plaindre du bruit · arrivé fatigué" | Immédiates : compensation, ton du message, geste opérationnel |
| **2. Episodic memory** | PostgreSQL (time-filtered) | Séjour + 30j | "Ce séjour : 2× restaurant, menu végétarien, SPA mardi, demande oreillers" | Contextuelles : recommandations, upsell pertinent, late check-out |
| **3. Semantic memory** | pgvector (permanent) | ∞ | "VIP depuis 2023 · 12 séjours · sensible bruit · 19°C · anniversaire juin · famille de 4" | Profil : priorité intervention, niveau de geste commercial, reconnaissance |
| **4. Segment** (double portée) | Aggregations anonymisées | ∞ | **Local :** "Guests similaires à cet hôtel : 73% late check-out, F&B > SPA" · **Hive prior (Phase 5) :** "Même profil, tous hôtels réseau" | Prédictions sans historique direct · premier séjour traité comme habitué · Hive prior = 80% avant séjours, 20% après accumulation guest |

**Sans cette distinction**, l'Orchestrateur doit soit tout charger (latence + bruit), soit décider sans le bon contexte (mauvaise décision). Avec, il interroge le scope strictement nécessaire.

#### MCP tools cibles (Phase 4)

```
query_guest_profile(guest_id, context_query, scope) → ProfileSnapshot
  scope: "working" | "current_stay" | "full_history" | "segment" | "all"
  ProfileSnapshot: { working?, episodic?, semantic?, segment? }
  # Claims Semantic : confidence-weighted { value, confidence, evidence_count, last_confirmed, decay_rate }
  # scope="all" = anti-pattern (latence + leakage) — loggé comme warning

update_guest_state(guest_id, event) → { state_id, applied_to: [layers] }
  event types: check_in, check_out, complaint, feedback, flight_status,
               sentiment_signal, preference_observed

get_emotional_risk(guest_id, stay_context) → { risk_score, drivers, suggested_actions }
  drivers: liste structurée (fatigué, déçu_précédent, anniversaire_raté, etc.)
```

`scope` est le paramètre clé : l'Orchestrateur le choisit selon la décision à prendre. Charger `"all"` par défaut = anti-pattern (latence, leakage cross-couche).

#### Sources de données (Phase 4)

- **PMS write** (Apaleo / Mews) — check-in/out, room assignments, durée séjour
- **CRM partenaire** (Duve, HiJiffy, Canary, Akia) — historique conversationnel, préférences déclarées
- **Vol en temps réel** (FlightAware API ou équivalent) — retards, annulations
- **Property Social Sentiment** (Phase 4 internal context) — reviews TripAdvisor/Booking propriété-spécifiques
- **Feedback Aetherix** (`submit_feedback_to_memory`) — réactions managers, outcomes opérationnels guest-liés
- **Guest feedback at scale** (Customer Alliance ou équivalent, partenariat Phase 4-5 à explorer) — *"guest context at scale"* multilingual structuré continu. Per Nicholas Reid (juin 2026) : feedback = double-sided dans agentic stack — **output** (evaluation layer : did agent's actions land?) + **input** (steering signal : where to point attention?). Complémentaire de la mémoire interne Anima ; couvre le côté *"how it landed with the guest"* qui n'est pas dans le world model Mews. Boucle complète possible : Customer Alliance capture *"breakfast queue too long"* → Anima alimente Aetherix → ajustement staffing forecast → exécution → Customer Alliance confirme amélioration. Partenariat possible Phase 4-5 (pas concurrent — Anima = operator-side context, Customer Alliance = guest-side context).

#### Stack cible

| Couche | Technologie | Notes |
|--------|------------|-------|
| Working | Redis (Upstash) | TTL par séjour, sub-second access |
| Episodic | PostgreSQL (Supabase) + index sur `guest_id`, `stay_id`, `timestamp` | Time-filtered queries, JSONB events |
| Semantic | pgvector (Supabase) | Mistral 1024d embeddings, HNSW — même infra qu'Aetherix |
| Segment | Materialized views + nightly k-means | Patterns inférés cross-guests anonymisés |
| Interface | MCP server FastAPI | Pattern identique à Aetherix (bearer, hotel_id server-side) |

#### Embryons technologiques — Phase 3

Deux algorithmes existants servent de proof-of-viability pour Anima :

- **HiveMemory** (Aetherix) — cross-hôtels F&B anonymisé (k-means + shapelet + LLM persona). Prouve la viabilité de l'agrégation pattern + mémoire persistante vectorielle au niveau hôtel. Sera adapté en *Cross-guest intelligence* (couche 4) d'Anima.
- **SensoryMemory** (Tacet) — patterns environnementaux par zone. Prouve la viabilité du modèle épisodique time-filtered avec retrieval par scope.

#### Prérequis (avant de builder)

- [ ] 1er pilote Apaleo prod actif avec données guest réelles (Phase 3 Track A)
- [ ] Accord partenariat CRM (Duve, HiJiffy ou Canary) — accès historique conversationnel
- [ ] PMS write activé sur Apaleo prod (capacité de pousser des actions, pas juste lire)
- [ ] **Analyse RGPD/CNIL formelle** : le profil émotionnel inféré = donnée personnelle sensible. Consentement explicite, retention policy, droit à l'oubli implémentés *avant* tout build.
- [ ] DPIA (Data Protection Impact Assessment) si décisions automatisées affectent significativement le guest

#### Statut

- **Phase 3 :** conception uniquement (cette documentation). Aucun code.
- **Phase 4 :** build après pilote réel + partenariat CRM + clearance RGPD.
- **Phase 5 :** production multi-property + integration Orchestrator complète.

---

## 3. Flux d'un événement type (vision Phase 4)

```
[Tacet] Travaux rue → room_risk_score(301) = 0.87
    ↓ MCP event push
[Orchestrateur] Query: qui dort en 301 ?
    → MCP → [Anima] query_guest_profile("guest-VIP-fatigué")
    → result: VIP, vol retardé 3h, 1 plainte bruit historique
    Decision: déplacer côté cour + recovery kit
    → MCP → [Aetherix] adjust_staffing(recovery_kit=true)
    → MCP → [PMS/Apaleo] update_room_assignment(301 → 315)

[Tacet] Même nuit, chambre 302 → couple festif
    Decision: late check-out offert, aucune action lourde
    → MCP → [PMS/Apaleo] offer_late_checkout(302)

Résultat : 0% perte de yield. 100% fidélisation émotionnelle.
```

---

## 4. Règles d'interface (invariants)

| Règle | Détail |
|-------|--------|
| **MCP-only** | Aucun import Python cross-repos. L'interface = le schema MCP. |
| **Atomic tools** | Chaque tool fait une chose. La composition est le rôle de l'Orchestrateur. |
| **hotel_id server-side** | Jamais dans les arguments d'un tool. Résolu depuis le bearer token. |
| **Policy-neutral** | Tacet produit des scores, pas des décisions. Aetherix exécute, ne route pas. Les business rules = Orchestrateur. |
| **Backward compat** | Les endpoints v0 restent actifs lors d'un bump de version. Migration explicite. |

---

## 5. Naming — clarification

| Terme | Où | Définition précise |
|-------|----|--------------------|
| **HiveMemory** | Aetherix | Mémoire cross-hôtels anonymisée — patterns F&B agrégés (k-means + shapelet + LLM persona). Expose un MCP tool callable par agents externes. |
| **SensoryMemory** | Tacet | Apprentissage de patterns environnementaux (historique risques par zone/saison). Embryon technologique pour Anima. |
| **OperationalMemory** | Aetherix | Mémoire privée par hôtel — feedback managers, outcomes, décisions passées. Table `operational_memory`, pgvector. |
| **Anima** | Futur nœud | Mémoire relationnelle guest — émotionnel + logistique + CRM. Distinct des trois ci-dessus. |

> **Règle :** ne pas utiliser "Hive Memory" pour désigner les patterns Tacet. Utiliser "SensoryMemory" dans le repo Tacet dès maintenant.

---

## 6. Séquençage par phase

| Phase | Aetherix | Tacet | Orchestrateur | Anima |
|-------|----------|-------|---------------|-------|
| Phase 3 (now) | Execution node pur · MCP v1 · recall_memory · AetherixEngine → orchestrator/ · HiveMemory algorithm | Sensory Node · Paris Open Data MCP · SensoryMemory embryon | Proto-stub `orchestrator/agent.py` · Papier technique (architecture Mesh) | Conception uniquement |
| Phase 4 | MCP v2 · adjust_staffing write · Apaleo Agent Hub | MCP tools stables · RMS integration | Repo dédié · Boucle agentique complète · Tacet + Aetherix + Anima | Build (1er pilote réel → données CRM) |
| Phase 5 | Multi-tenant hardening | Cross-property | Revenue Orchestration Agent | Déploiement production |

---

## 7. Instructions LLM

**Claude (sessions Aetherix) :**
- Toute modification du schema MCP d'Aetherix → mettre à jour §2 Aetherix ici.
- Toute décision qui change le rôle d'un nœud → mettre à jour §2 + §6 ici + CLAUDE.md §Décisions architecturales.
- Ne pas créer de dépendances Python entre `backend/orchestrator/` et `tacet-app/`.

**Gemini (sessions Tacet) :**
- Toute modification du schema MCP de Tacet → mettre à jour §2 Tacet ici.
- Utiliser "SensoryMemory" (pas "Hive Memory") pour les patterns environnementaux Tacet.
- Référencer ce fichier dans `tacet-app/ARCHITECTURE_MANIFEST.md` comme source canonique globale.
- Ne pas introduire de logique de décision dans Tacet — scores uniquement.

**Tout agent :**
- Ce document prime sur tout autre document en cas de contradiction.
- Les ADRs de repo (`docs/adr/`, `tacet-app/ARCHITECTURE_MANIFEST.md`) détaillent les décisions locales. Ce fichier synthétise la vision globale.

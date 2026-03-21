# Linear Board — Mapping BMAD Stories & Success Criteria

> Généré le 2026-03-21. Source de vérité : `docs/bmad/_bmad-output/`.
> Toute modification du scope doit être reflétée dans `sprint-status.yaml`.

---

## Conformité globale

| Linear issue | Épic BMAD | Stories affiliées | Statut BMAD |
|---|---|---|---|
| HOS-34 | Epic 1 | Story 1.1 | done |
| HOS-38 | Epic 1 + 2 | Story 1.1, 2.1 | done / ready-for-dev |
| HOS-40 | Epic 1 | Story 1.1, 1.3 | done / backlog |
| HOS-41 | Epic 2 | Stories 2.1 → 2.4 | ready-for-dev → backlog |
| HOS-39 | Epic 4 + 5 | Stories 4.1, 4.2, 4.3, 5.1 | backlog |
| HOS-37 | Epic 3 + 5 | Stories 3.3a-c, 5.2 | backlog |
| HOS-35 | Outillage | *(hors BMAD — tooling)* | — |
| HOS-36 | Outillage | *(hors BMAD — tooling)* | — |

### ⚠️ Gap identifié — Issue manquante

**Epic 3 : Semantic Anomaly Engine** n'a pas de ticket propre.
→ **Créer HOS-42 : [AI/ML] Semantic Anomaly Engine** (Stories 3.1 + 3.2 + 3.3a/b/c)

---

## HOS-34 — [Infra] Déploiement Docker local

**Stories BMAD :** Story 1.1 *(done)*

**Objectif :** L'environnement de développement local tourne entièrement via Docker Compose, sans dépendance manuelle.

**Success criteria :**
- [ ] `docker compose up` démarre les 3 services sans erreur : Next.js (`:3000`), FastAPI (`:8000`), Supabase local (`:54321`)
- [ ] `docker compose ps` affiche tous les services en état `healthy`
- [ ] L'API client TypeScript est auto-générée depuis le schéma OpenAPI FastAPI
- [ ] Les erreurs HTTP FastAPI suivent le format RFC 7807 Problem Details
- [ ] Un `docker compose down && docker compose up` depuis zéro prend moins de 3 minutes

**NFR :** Story 1.1 — contrainte template `vintasoftware/nextjs-fastapi-template`

---

## HOS-35 — [Integration] Module Obsidian

**Stories BMAD :** *(Outillage — hors périmètre BMAD fonctionnel)*

**Objectif :** Les artefacts de connaissance du projet (audit hebdo, alertes, rétrospectives) sont accessibles dans le vault Obsidian sans action manuelle.

**Success criteria :**
- [ ] Le service `reporting_service.py` génère automatiquement une note dans `/AI Reports/` chaque vendredi
- [ ] Quand une anomalie est détectée, une note est créée dans `/Alerts/` avec : tenant_id, type d'anomalie, ROI estimé, timestamp
- [ ] Si MAPE > 30 %, une note `/Alerts/model-drift-{date}.md` est créée ET un ticket Linear est ouvert automatiquement
- [ ] Le dossier `docs/bmad/_bmad-output/` est visible dans le vault via lien symbolique (configuré une fois manuellement)
- [ ] Les notes Obsidian respectent le format Markdown BMAD (front-matter YAML + sections H2)

---

## HOS-36 — [Integration] Module Linear

**Stories BMAD :** *(Outillage — hors périmètre BMAD fonctionnel)*

**Objectif :** La détection d'anomalie ou de dérive crée automatiquement un ticket Linear sans intervention humaine.

**Success criteria :**
- [ ] `setup_linear_board.py` s'exécute sans erreur avec des credentials valides et crée : 6 labels (dont `Strategic Intelligence`), les états de workflow (`Backlog → In Progress → In Review → Done`), les projets par épic BMAD
- [ ] Quand `ops_dispatcher.py` détecte une anomalie `roi_positive`, un ticket Linear est créé avec : label correct, priorité `High`, lien vers la story BMAD affiliée dans la description
- [ ] Quand MAPE > 30 %, un ticket Linear `[AI/ML] Model drift detected` est créé automatiquement avec label `AI Alert`
- [ ] Les tickets créés automatiquement sont idempotents (pas de doublon si la même anomalie est re-détectée dans la même fenêtre de 4h)

---

## HOS-37 — [AI/ML] Pipeline Claude MCP

**Stories BMAD :** Story 3.3a, 3.3b, 3.3c *(Epic 3)* + Story 5.2 *(Epic 5)*

**Objectif :** Claude est intégré comme moteur de raisonnement pour (1) la détection d'anomalies et (2) l'explication conversationnelle aux managers.

**Success criteria :**
- [ ] **Story 3.3a** — Le moteur d'anomalies compare les 4-hour windows de demande prévue vs baseline historique et flag les déviations > 20 % (configurable)
- [ ] **Story 3.3b** — Pour chaque anomalie flaggée, un ROI net est calculé : `revenue_opportunity - labor_cost`. Si positif → `roi_positive = true`
- [ ] **Story 3.3c** — Une recommandation texte est générée : `"Ajouter 2 serveurs — ROI estimé : £620, coût main d'oeuvre : £180"`
- [ ] **Story 5.2** — Claude reçoit le contexte mathématique complet (données historiques, baseline, facteurs) et génère une explication < 150 mots
- [ ] Latence P95 de la réponse Claude ≤ 3 secondes (NFR6)
- [ ] Le scan global de tous les tenants actifs s'exécute en ≤ 5 secondes (NFR5)
- [ ] Les appels Claude sont loggués (prompt, response, tenant_id, latency_ms) pour audit

---

## HOS-38 — [Backend] API FastAPI health check

**Stories BMAD :** Story 1.1 *(Epic 1)* + Story 2.1 *(Epic 2)*

**Objectif :** L'API FastAPI est opérationnelle et expose les endpoints de santé et de test PMS.

**Success criteria :**
- [ ] `GET /health` → `200 OK` avec payload `{"status": "ok", "version": "x.y.z"}`
- [ ] `GET /api/v1/pms/test` → ping réussi vers sandbox Apaleo (OAuth 2.0 Client Credentials) → `200 OK`
- [ ] Credentials Apaleo stockés chiffrés AES-256-GCM en Supabase (NFR4)
- [ ] Credentials invalides → réponse `401 Unauthorized` au format RFC 7807
- [ ] Rate-limiting PMS (429) → retry avec backoff exponentiel jusqu'à 60 s (NFR1)
- [ ] Tous les modèles Pydantic utilisent `snake_case` en interne, `camelCase` en output JSON

---

## HOS-39 — [WhatsApp] Agent ambiant Twilio

**Stories BMAD :** Story 4.1, 4.2, 4.3 *(Epic 4)* + Story 5.1 *(Epic 5)*

**Objectif :** Les managers reçoivent des alertes WhatsApp actionnables et peuvent répondre en langage naturel.

**Success criteria :**
- [ ] **Story 4.1** — Twilio et SendGrid initialisent sans erreur au démarrage. Un message test est dispatchable via SMS, WhatsApp ET Email
- [ ] **Story 4.1 (UI)** — Le dashboard Next.js permet de configurer : canal préféré, numéro de téléphone, email, coordonnées GPS de la propriété
- [ ] **Story 4.2** — Une alerte `ready_to_push` est formatée et envoyée ≤ 3 minutes après détection de l'anomalie (NFR2)
- [ ] **Story 4.2** — Le message inclut : facteur déclencheur (ex : "Conférence Tech relocalisée"), recommandation spécifique, ROI estimé, coût main d'oeuvre
- [ ] **Story 4.3** — Réponse "Accept" ou "Reject" du manager → statut mis à jour dans Supabase dans les 5 secondes
- [ ] **Story 5.1** — Tout message entrant ≠ "Accept"/"Reject" est routé vers le moteur Claude en `BackgroundTask`
- [ ] Le webhook Twilio est traité de manière asynchrone (FastAPI `BackgroundTasks`) — pas de timeout HTTP (NFR6)

---

## HOS-40 — [Frontend] Interface Next.js

**Stories BMAD :** Story 1.1 *(Epic 1)* + Story 1.3 *(Epic 1)*

**Objectif :** Le manager accède à son espace isolé via une interface Next.js sécurisée.

**Success criteria :**
- [ ] **Story 1.3** — Login via Supabase Auth → session JWT avec `tenant_id` et `department_role` (F&B vs Front Office)
- [ ] Le token JWT est utilisé par FastAPI pour valider les RLS Supabase en backend
- [ ] Les managers F&B ne voient que leurs alertes (FR20 — isolation par département)
- [ ] Page de configuration des préférences : canal de notification, coordonnées GPS, rôle
- [ ] La page de test (`/test-notification`) permet d'envoyer un message de test via le canal configuré
- [ ] Le client TypeScript est auto-généré depuis OpenAPI FastAPI (aucun `fetch` manuel vers `/api/`)

---

## HOS-41 — [Apaleo] Connexion PMS

**Stories BMAD :** Story 2.1, 2.2, 2.3, 2.4 *(Epic 2)*

**Objectif :** Aetherix ingère et synchronise les données d'occupation Apaleo de façon sécurisée et continue.

**Success criteria :**
- [ ] **Story 2.1** — OAuth 2.0 Client Credentials vers `https://identity.apaleo.com/connect/token` → token valide
- [ ] **Story 2.1** — Credentials chiffrés AES-256-GCM en Supabase, déchiffrés uniquement en mémoire lors des appels API
- [ ] **Story 2.2** — Ingestion historique : toutes données guest avec PII (nom, email, téléphone) strippées/hachées avant insertion (NFR3)
- [ ] **Story 2.2** — Données associées au bon `tenant_id` avec RLS actif
- [ ] **Story 2.3** — Polling toutes les 15 minutes via FastAPI `BackgroundTasks`
- [ ] **Story 2.3** — Si Apaleo rate-limite (429) ou timeout : retry exponentiel (2s → 4s → 8s → 60s max) sans perte de séquence (NFR1)
- [ ] **Story 2.4** — Baseline calculée : revenu F&B moyen par chambre occupée + room service moyen, segmentés par jour de la semaine
- [ ] **Story 2.4** — Métriques baseline stockées par `tenant_id` dans Supabase

---

## HOS-42 (à créer) — [AI/ML] Semantic Anomaly Engine

**Stories BMAD :** Story 3.1, 3.2 *(Epic 3)*

**Objectif :** Ingérer météo + événements locaux pour alimenter le moteur d'anomalies HOS-37.

> Ce ticket est le **prérequis** de HOS-37. Il doit être en `Done` avant que HOS-37 puisse passer en `In Progress`.

**Success criteria :**
- [ ] **Story 3.1** — Sync météo toutes les 12h : données de prévision dans un rayon de 5 km des coordonnées GPS de la propriété (FR4)
- [ ] **Story 3.1** — Données normalisées et stockées avec `tenant_id` dans Supabase
- [ ] **Story 3.2** — Sync PredictHQ quotidienne : événements (conférences, concerts, sports) dans rayon 5 km (FR5)
- [ ] **Story 3.2** — Événements catégorisés (tech, sport, culture) pour pattern matching historique
- [ ] Les deux syncs s'exécutent en `BackgroundTasks`, indépendamment du cycle de polling PMS

---

## Dépendances entre issues

```
HOS-34 (Infra)
    └── HOS-38 (FastAPI)
        └── HOS-41 (Apaleo PMS)
            └── HOS-42 (Weather + Events) [À CRÉER]
                └── HOS-37 (Claude Pipeline)
                    └── HOS-39 (WhatsApp Agent)

HOS-34 (Infra)
    └── HOS-40 (Frontend)
        └── HOS-39 (WhatsApp — préférences UI)

HOS-36 (Linear module) — indépendant, peut tourner en parallèle
HOS-35 (Obsidian module) — indépendant, peut tourner en parallèle
```

---

## Action requise dans Linear

1. **Créer HOS-42** : `[AI/ML] Semantic Anomaly Engine` — label `AI/ML`, priorité `High`, blocker de HOS-37
2. **Ajouter les dépendances** (`Blocks / Blocked by`) dans Linear selon le graphe ci-dessus
3. **Lier les stories BMAD** en ajoutant dans la description de chaque issue le lien vers `docs/bmad/_bmad-output/planning-artifacts/epics.md#StoryX.Y`

# Story 10.1 (P3-1): Design partner recruitment kit

Status: ready-for-dev
Linear: [HOS-175](https://linear.app/hospitalityagent/issue/HOS-175) (Urgent, 2 pts)
Epic: HOS-174 (Phase 3) — Track A blocker
Blocks: [HOS-176](https://linear.app/hospitalityagent/issue/HOS-176) (real-pilot deploy)
Branch: `ivandemurard/hos-175-story-101-p3-1-design-partner-recruitment-kit`

> **Track A gate.** Aucun travail HOS-176 ne démarre tant qu'un design partner n'a pas accepté d'onboarder.
> **AC4 (3 prospects + outreach) = manuel Ivan.** Les AC1-AC3 sont des livrables docs — Dev peut les rédiger. AC4 nécessite ton réseau humain ; le pack fournit un template de ciblage et le message outreach.

---

## Story

As the Aetherix team,
I want a complete design partner recruitment kit,
so that I can identify, approach, and qualify 1 Apaleo hotel for the Phase 3 pilot within 2 weeks.

---

## Acceptance Criteria (verbatim from Linear)

- [ ] **AC1** : 1-pager value prop (PDF + Notion) — addresses ICP F&B manager, includes ROI calc, screenshots of daily Receipt
- [ ] **AC2** : Onboarding script (45-min discovery call) — qualifying questions + technical prereq checklist (Apaleo account, WhatsApp Business)
- [ ] **AC3** : Credentials-management SOP — how Aetherix stores `APALEO_CLIENT_ID/SECRET` for the pilot (Fly.io secrets, rotation policy)
- [ ] **AC4** : 3 prospect names + first outreach sent (LinkedIn / email)

---

## Périmètre Dev / Ivan

| AC | Qui | Quoi |
|----|-----|------|
| AC1 | Dev | Rédiger `docs/pilot/onboarding-kit.md` §Value prop + ROI calc. Format Notion-compatible (Markdown). PDF = export Notion par Ivan après relecture. |
| AC2 | Dev | Rédiger `docs/pilot/onboarding-kit.md` §Discovery call script + prereq checklist |
| AC3 | Dev | Rédiger `docs/pilot/credentials-sop.md` — SOP complète |
| AC4 | **Ivan** | Identifier 3 prospects (template ci-dessous), envoyer le premier message. Dev peut rédiger le message template dans `docs/pilot/outreach-template.md` |

---

## Tasks / Subtasks

### AC1 + AC2 — `docs/pilot/onboarding-kit.md`

- [ ] **T1 — Rédiger §1 Value prop 1-pager**
  - ICP ciblé : F&B Manager / GM d'un hôtel indépendant 4★, 100-150 chambres, restaurant ouvert (pas seulement petit-déj), client Apaleo, EU/Paris
  - Structure 1-pager (voir §Dev Notes ci-dessous pour le contenu) :
    - Headline : "Aetherix — F&B intelligence for your Apaleo hotel. 15-min setup, daily forecasts by WhatsApp."
    - Problème (1 paragraph), Solution (3 bullets), Preuve (MAPE 15.09%), ROI (−3% à −8% coût labour), Comment ça marche (4 étapes), Ce qu'on vous demande
  - Inclure une section "Pourquoi Apaleo first" (talking point Anthropic playbook + "Apaleo has no F&B primitives, we do")
  - Format : Markdown propre, headers H2/H3, pas de blabla

- [ ] **T2 — Rédiger §2 ROI calculator (inline dans la 1-pager)**
  - Formule : `Savings = (avg_covers/service × services_per_week × 52) × (labor_overstaffing_rate × avg_server_cost_per_hour × avg_shift_hours)`
  - Valeurs par défaut ICP : 60 covers/service, 3 services/jour, 7j/semaine, 10% overstaffing, €15/h, 8h shift → **~€16K/an économisés**
  - Paramètres éditables dans la doc pour personnalisation prospect par prospect

- [ ] **T3 — Rédiger §3 Discovery call script (45 min)**
  - Opening (2 min) : rappel contexte, objectif call
  - Qualifying questions (15 min) : voir §Dev Notes — 8 questions obligatoires
  - Demo walkthrough (15 min) : probe → forecast → WhatsApp Receipt → feedback loop
  - Technical prereq check (10 min) : voir checklist ci-dessous
  - Next steps (3 min) : pilot agreement, onboarding date, first Apaleo OAuth2

- [ ] **T4 — Rédiger §4 Technical prereq checklist**
  - Apaleo account type (doit avoir API access activé — tier requis ?)
  - WhatsApp Business phone number configuré
  - F&B Manager disponible 2 min/jour pour lire le Receipt
  - Accord RGPD (données opérationnelles, pas de PII guest)
  - Engagement : ≥ 4 semaines, feedback mensuel call 30 min

### AC3 — `docs/pilot/credentials-sop.md`

- [ ] **T5 — Rédiger la SOP credentials**
  - Scope : comment Aetherix reçoit, stocke et rotate les `APALEO_CLIENT_ID/SECRET` d'un design partner réel
  - Étapes :
    1. Partner génère des credentials dans Apaleo Developer Portal (read-only scope)
    2. Ivan reçoit hors Claude (`flyctl secrets set`) — **jamais en session IA, jamais par email**
    3. Validation : `python scripts/validate_apaleo_sandbox.py` sur les creds du partner (avec `APALEO_MCP_SERVER_URL` pointant sur leur property)
    4. Rotation policy : tous les 90 jours ou si compromission suspectée
    5. Révocation : à la fin du pilot, le partner révoque dans leur Apaleo portal
  - Référencer : CLAUDE.md Décision #7 (read-only Phase 0), Décision #17 (Fly.io secrets)

### AC4 — `docs/pilot/outreach-template.md` (template pour Ivan)

- [ ] **T6 — Rédiger le template outreach**
  - Message LinkedIn (300 mots max, tone professionnel mais direct)
  - Message email (idem, version légèrement plus longue avec contexte Apaleo)
  - Inclure : pourquoi eux spécifiquement (personnaliser avec property name), ce qu'on leur propose exactement (4 semaines, aucun coût, juste du feedback), CTA = 20-min call
  - Rédiger en **français ET anglais** (les deux langues utiles sur le segment Apaleo EU)

- [ ] **T7 — Rédiger le template de ciblage prospects (Ivan remplit)**
  - Critères ICP détaillés (voir §Dev Notes)
  - Sources de prospection : Apaleo Marketplace customer logos, LinkedIn "hotel manager" + "Apaleo", hospitality communities (Hotel Tech Report, HN hospitality), réseau direct Ivan
  - Template tableau : `| Property name | Location | Stars | Restaurant | Apaleo confirmed | Contact | Canal | Statut |`

### T8 — Commit + PR

- [ ] Créer `docs/pilot/` (nouveau dossier)
- [ ] Committer les 3 fichiers sur la branche
- [ ] CI vert (docs only, pas de schema drift gate)
- [ ] PR vers main + Linear HOS-175 → Done + URL PR en commentaire

---

## Dev Notes — Contenu clé à injecter

### ICP précis (source : `docs/context/demo-apaleo.md`)

```
Taille      : 100-150 chambres (indépendant ou petit groupe 2-5 properties)
Catégorie   : 4★ ou boutique tech-forward
PMS         : Apaleo client (requis — OAuth2 nécessaire)
Restaurant  : ouvert le soir (pas seulement breakfast) — covers dîner = le forecast le plus valuable
Localisation: Paris / EU majeure (modèle weather+events validé sur cette géographie)
Équipe      : pas de data analyst dédié — le F&B Manager fait la planification manuellement
Revenue F&B : > €500K/an (ça vaut de l'optimiser)
```

**Argument "pourquoi Apaleo"** (source : `docs/competitive/apaleo-mcp-mapping.md`, §TL;DR) :
> *"Apaleo expose 235 tools MCP. Aucun ne prédit les covers, ne calcule le capture-rate, ni ne recommande le staffing. Ce sont exactement les primitives qu'Aetherix expose. Nous sommes complémentaires, pas en concurrence."*

**Talking point Anthropic playbook** (CLAUDE.md Décision #21) :
> *"Aetherix runs on one of the two PMS tiers the Anthropic playbook recommends for AI hotel owners — Apaleo (API-first) and Mews. You're on the right infrastructure."*

### Qualifying questions discovery call (T3)

1. "Combien de couverts par service en moyenne au dîner ?" (calibration modèle)
2. "Comment planifiez-vous vos effectifs F&B aujourd'hui — tableur, feeling, autre ?" (pain validation)
3. "Avez-vous déjà manqué de personnel un soir à forte demande ?" (incident cost)
4. "Avez-vous un restaurant le soir ou seulement le petit-déjeuner ?" (scope check)
5. "Êtes-vous sur Apaleo depuis combien de temps ?" (historique disponible)
6. "Avez-vous un numéro WhatsApp Business pour la gestion opérationnelle ?" (prereq AC2)
7. "Combien de temps passez-vous à planifier les équipes F&B chaque semaine ?" (ROI baseline)
8. "Si on pouvait vous donner une prédiction de covers J+1 avec ±15% d'erreur par WhatsApp chaque matin, qu'est-ce que vous en feriez ?" (test adoption intent)

### ROI evidence disponible

| KPI | Valeur | Source |
|-----|--------|--------|
| MAPE J+1 (synthétique, gate PASS) | 15.09% | `docs/context/mape-benchmark-holdout.json`, run 2026-05-21 |
| Gate Décision #14 | ≤ 22% ✅ | CLAUDE.md |
| Savings labour estimés (ICP 60 covers, 3 services) | ~€16K/an | ROI calc T2 |
| Trust-KPI pipeline | Opérationnel sur sandbox | HOS-177 Done |
| Décision humain-in-the-loop | Décision #6 | Pas d'auto-actions Phase MVP |

### Ce que l'agent fait / ne fait pas (Human-in-the-loop, Décision #6)

À clarifier explicitement dans la 1-pager et le discovery call :
- **Fait** : forecast covers + recommandation staffing par WhatsApp + rapport hebdo
- **Ne fait pas** : modifier les réservations Apaleo, accéder aux données financières guests, envoyer des messages aux guests
- **Read-only PMS** (Décision #7) — aucune écriture sur le PMS pendant le pilot

### Fichiers à créer

```
docs/pilot/onboarding-kit.md        — AC1 + AC2 (1-pager + discovery call script)
docs/pilot/credentials-sop.md       — AC3
docs/pilot/outreach-template.md     — AC4 template (Ivan remplit les noms)
```

### Références

- [Source: docs/context/demo-apaleo.md] — scenario Hotel Kleber, Q&A préparées, ICP details
- [Source: docs/competitive/apaleo-mcp-mapping.md §TL;DR] — talking point différenciateur Apaleo
- [Source: CLAUDE.md Décision #6] — pas d'auto-actions Phase MVP
- [Source: CLAUDE.md Décision #7] — read-only PMS Phase 0
- [Source: CLAUDE.md Décision #17] — Fly.io secrets handling
- [Source: CLAUDE.md §KPI framework Niveau 2] — labor_cost_variance -3% à -8%
- [Source: docs/context/mape-benchmark-holdout.json] — MAPE 15.09% PASS

---

## ⚠️ AC4 — Manuel Ivan : 3 prospects + outreach

**Dev ne peut pas faire AC4.** Le critère de validation est l'envoi réel d'un message à un humain.

Processus suggéré :
1. Dev livre les templates dans `docs/pilot/outreach-template.md` (T6)
2. Ivan identifie 3 prospects avec le template de ciblage (T7) — sources : Apaleo Marketplace, LinkedIn, réseau direct
3. Ivan envoie le premier message au prospect #1
4. Screenshot de l'envoi archivé dans `docs/pilot/outreach-evidence/` (optionnel mais traceable)
5. Ivan marque AC4 Done dans Linear

**Critère minimum pour marquer AC4 Done :** 1 message envoyé à 1 prospect qualifié (Apaleo confirmé + restaurant ouvert le soir).

---

## Dev Agent Record

### Agent Model Used
_à remplir par Dev_

### Debug Log References
_à remplir par Dev_

### Completion Notes List
_à remplir par Dev_

### File List
- `docs/pilot/onboarding-kit.md` (new)
- `docs/pilot/credentials-sop.md` (new)
- `docs/pilot/outreach-template.md` (new)

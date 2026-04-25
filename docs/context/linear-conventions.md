# Linear Conventions — Aetherix

> Protocole de gestion Linear pour garder le board clean et présentable.
> Toute création d'Epic ou de Story DOIT respecter ce cadre.
> Toute violation = dette qui dégrade la lisibilité du board.

---

## Hiérarchie

```
Workspace (Hospitalityagent)
└── Team (Aetherix HOS)
      └── Project (Aetherix)
            └── Epic (issue parent, type:Epic)
                  └── Story (sub-issue, type:Story)
                        └── (optionnel) Sub-task
```

Une seule team. Un seul projet long-terme (`Aetherix`). Tous les Epics attachés au projet.

---

## Avant de créer un Epic ou une Story — vérification anti-doublons

**Obligatoire** :
1. Chercher dans Linear avec le titre exact ou une variante proche
2. Si match trouvé → décider : *enrichir l'existant* ou *créer en marquant Duplicate of <id>*
3. Ne JAMAIS créer une "v2" enrichie sans fermer la v1 dans le même mouvement

L'historique 146 issues / 22 Duplicates était causé par cette règle non-respectée. Pattern à éviter.

---

## Création d'Epic — checklist obligatoire

Un Epic n'est valide que s'il contient :

| Champ | Contenu |
|---|---|
| **Title** | `Epic N: <Nom>` (ex: `Epic 5: Conversational Receipts`) |
| **Type** | `Epic` (issue type custom Linear) |
| **Project** | `Aetherix` (attaché obligatoirement) |
| **Priority** | Urgent / High / Medium / Low — jamais No priority |
| **Labels** | `phase:X` + au moins un `area:Y` + `type:feature\|security\|docs` |
| **Description** | Voir template ci-dessous |

### Template description Epic

```markdown
## Goal
<1-2 phrases — quel problème métier l'Epic résout>

## Functional Requirements
- FR1: <capability mesurable>
- FR2: ...

## Non-Functional Requirements
- NFR1: <performance, sécurité, scalabilité — quantifié>
- NFR2: ...

## Technical Context
- ADR liés : <ADR 0001, 0002...>
- Décisions architecturales : <CLAUDE.md #X, #Y>
- Stack impacté : <services, migrations, intégrations>

## Definition of Done
- [ ] <critère de validation 1 — vérifiable>
- [ ] <critère 2>
- [ ] Tests : <fichiers de test attendus>
- [ ] Migrations : <si applicable>
- [ ] Documentation : <ADR, README, runbook>

## Stories
<auto-listé par Linear via sub-issues — ne pas dupliquer ici>
```

---

## Création de Story — checklist obligatoire

| Champ | Contenu |
|---|---|
| **Title** | `Story N.M: <Action concrète>` (ex: `Story 5.2: Generate LLM-powered Receipt`) |
| **Type** | `Story` |
| **Parent** | Epic concerné (sub-issue link) |
| **Priority** | Hérite de l'Epic ou ajustée |
| **Estimate** | Fibonacci 1 / 2 / 3 / 5 / 8 — JAMAIS vide |
| **Labels** | Hérite de l'Epic + `component:Z` si spécifique |
| **Description** | Voir template ci-dessous |

### Template description Story

```markdown
## Context
<pourquoi cette story, en 1-2 phrases>

## Acceptance Criteria
- [ ] AC1: <comportement testable>
- [ ] AC2: ...
- [ ] AC3: ...

## Technical Notes
- Fichiers impactés : `backend/app/services/x.py`, ...
- Migration nécessaire : oui/non
- Breaking change : oui/non

## Test Plan
- [ ] Tests unitaires : `tests/test_x.py`
- [ ] Tests intégration : <si applicable>
- [ ] Validation manuelle : <étapes>
```

---

## Transitions de statut — règles strictes

| Statut | Quand y entrer | Quand en sortir |
|---|---|---|
| **Backlog** | Story future, pas commencée, pas planifiée dans le sprint actuel | Sprint kickoff → Todo |
| **Todo** | Story planifiée pour le sprint actuel | Dev démarre → In Progress |
| **In Progress** | Branche créée, code en cours d'écriture | PR ouverte → In Review |
| **In Review** | PR ouverte, CI green ou en cours | PR mergée → Done |
| **Done** | **PR mergée sur main** + AC tous cochés + tests passants | Jamais (terminal) |
| **Duplicate** | Issue redondante → marquer `Duplicate of <id>` | Jamais (terminal) |
| **Canceled** | Décision PM d'abandonner — JAMAIS pour "j'ai fait autre chose" | Jamais (terminal) |

**Règle d'or** : `In Progress` ne doit JAMAIS dépasser **14 jours** sans commentaire de progression. Au-delà = signal de blocage à escalader.

---

## Labels — taxonomie minimale (4 groupes)

### `phase` — bleu
`phase:0` · `phase:0.5` · `phase:1` · `phase:2` · `phase:3`

### `area` — orange
`area:backend` · `area:frontend` · `area:infra` · `area:docs` · `area:integrations`

### `component` — violet
`component:mcp` · `component:memory` · `component:forecast` · `component:observability` · `component:apaleo` · `component:whatsapp` · `component:receipts`

### `type` — vert
`type:feature` · `type:bug` · `type:tech-debt` · `type:docs` · `type:spike` · `type:security`

**Minimum obligatoire** : 1 phase + 1 area + 1 type. Component si pertinent.

---

## Liens vers code et documentation

Chaque story qui ship du code doit avoir, en commentaire à la fermeture :
- **PR URL** : `https://github.com/IvandeMurard/aetherix-hospitality-ai/pull/XX`
- **Migration** (si applicable) : nom du fichier `supabase/migrations/`
- **ADR** (si décision architecturale) : référence dans `docs/adr/`

---

## Audit périodique

Lancer `python scripts/linear_audit.py > linear_state.md` à chaque fin de sprint. Vérifier :
- Aucun Duplicate non marqué
- Aucun In Progress > 14j
- Aucune Story unfinished sans AC
- Tous les Epics canoniques attachés au projet
- Tous les Epics ont labels phase+area+type

---

## Exemples — Epics canoniques actuels

| Epic | Phase | Status | Notes |
|---|---|---|---|
| HOS-73 (Epic 1 Workspace) | 0 | Done | Foundation |
| HOS-77 (Epic 2 PMS Sync) | 0 | Done | Apaleo OAuth2 + MCP |
| HOS-82 (Epic 3 Anomaly Engine) | 0 | Done | Prophet + RAG |
| HOS-88 (Epic 4 Push Delivery) | 0 | Done | Twilio + SendGrid |
| HOS-118 (Epic 0 LLM Provider) | 0 | Done | Multi-LLM abstraction |
| HOS-92 (Epic 5 Receipts) | 2 | In Progress | 7 stories P2-1→P2-7 |
| HOS-95 (Epic 6 Cross-Property) | 3 | Backlog | Multi-hotel |
| HOS-110 (Epic 7 Security) | 1 | Backlog | RLS audit, GDPR |
| HOS-117 (Epic 8 WhatsApp UX) | 1 | Backlog | Tone of voice, templates |

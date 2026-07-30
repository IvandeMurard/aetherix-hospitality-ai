# Phase 3 — Sprint Plan unifié (re-baseline)

> **Status**: Active · **Date**: 2026-07-30 · **Owner**: Ivan (solo dev) · **Re-evaluate**: chaque vendredi
> **Remplace** : baseline du 2026-06-03 (sprints S1→S4, 03/06 → 30/06) — **entièrement écoulée**, ne pas s'y référer.
> **Sources** : [`phase-3-pilot-validation.md`](phase-3-pilot-validation.md) (Epic 10) · [`evaluation-by-design.md`](evaluation-by-design.md) (Epic 11) · [`plan-90j-proof-visibility.md`](plan-90j-proof-visibility.md) (Epic 16) · état Linear vérifié le 2026-07-30
> **Contrainte structurante** : Epic 16 (HOS-300, due **2026-10-05**) est prioritaire sur Phase 3 jusqu'à ses critères de sortie J+90. Voir §Arbitrage de capacité.

---

## Ce qui a changé depuis la baseline du 03/06

| Fait | Conséquence sur le plan |
|------|--------------------------|
| **Epic 12** runtime guardrails (HOS-212) **clôturée** — G-1→G-5 Done, 6 findings QA-S4 Done, G-6 différé Phase 4, ADR-0009 Accepted, Décision #27 actée | Blocker fiabilité pré-pilote **levé**. Ne plus apparaître dans le chemin critique. |
| **Epic 11** eval : socle Done (EVAL-0/1/2/4/5), gate CI **blocking** (HOS-216, HOS-274) | Le « pilot gate technique » de l'ancienne baseline est **atteint**. Reste de la dette non bloquante. |
| **Epic 16** (HOS-300) créée le 07/07 suite à l'audit critique — 12/19 stories Done, due 05/10 | Occupe la même fenêtre calendaire et la même capacité. **Arbitré prioritaire.** |
| **HOS-175 supprimée par erreur** → recréée en **HOS-319** (22/07), In Progress | Le blocker dur de HOS-176 change d'identifiant. Diagramme mis à jour. |
| **HOS-308** (Epic 16) déclaré prérequis PM de HOS-176 le 22/07 | Le chemin critique pilote traverse désormais Epic 16. |
| Epics **13** POS (HOS-254) et **14** Context Graph (HOS-255) = Phase 4 | **Hors séquencement Phase 3.** Epic 14 bloqué par Epic 13. |

---

## Arbitrage de capacité (tranché le 30/07)

Capacité : **dev solo, 8-10 pts / sprint-semaine**. Fenêtre jusqu'au J+90 d'Epic 16 (05/10) : ~9 sprints ⇒ **72-90 pts**.

| Périmètre | Reste à faire |
|-----------|--------------:|
| Epic 16 — Proof & Visibility | ~23 pts (dont 2 stories non estimées) |
| Epic 10 — Pilot Validation | ~45 pts |
| Epic 11 — Evaluation by Design | ~19 pts |
| **Total** | **~87 pts** |

**Tout ne tient pas dans la fenêtre.** Arbitrage retenu :

1. **Epic 16 garde la main jusqu'à ses 5 critères de sortie** — date externe dure, et son plan gèle explicitement les nouvelles features (`plan-90j-proof-visibility.md` §« Ce qu'on ne fait PAS pendant 90 jours »).
2. **Les deux items Urgent Apaleo passent avant** — recherche/doc pure, aucun code, aucun eval gate : compatibles avec le gel.
3. **HOS-308 est traité comme item partagé** — il sert FR1 d'Epic 16 *et* lève le prérequis PM de HOS-176.
4. **La chaîne cold-start et Hive Memory sont décalées après le J+90 d'Epic 16** (S5+), sauf signature partenaire anticipée qui ferait remonter HOS-176.

Epic 16 se clôt à S3 (23/08), soit ~6 semaines avant sa deadline — ce qui libère S4→S9 pour Phase 3.

---

## Arbitrage Urgent dormants (tranché le 30/07)

`HOS-285` et `HOS-278` étaient **Urgent depuis fin juin sans être planifiés**. Décision : **priorité Urgent conservée, planifiés en tête de timeline.**

- **HOS-278** (spike A2A, 3 pts) — sa propre description porte « décision time-sensitive avant le pilote M4 (juillet 2026) » : l'échéance est **déjà dépassée**. Surtout, il **conditionne HOS-180** (Agent Hub listing, 5 pts) : si le spike conclut « Aetherix devient la couche F&B de Copilot via A2A », le listing tel que spécifié est du travail perdu. **Faire HOS-180 avant HOS-278 est une erreur de séquencement** — d'où S1 pour l'un, S7 pour l'autre.
- **HOS-285** (audit Trace Agent, 2 pts) — alimente le canari concurrentiel W2 et la décision ouverte « Apaleo Copilot scope F&B ». Placé en amorce S0 car c'est le moins cher des deux.

---

## Timeline — 30/07/2026 → 04/10/2026

### S0 — jeu 30/07 → dim 02/08 · « Amorce » (2 j ouvrés, ~2 pts) — ✅ **LIVRÉ 30/07**

| Item | Pts | État |
|------|----:|------|
| **HOS-285** audit Apaleo Trace Agent | 2 | ✅ **Livré** → `docs/competitive/apaleo-trace-agent-analysis.md`. Couverture F&B = **NON** (4 sources). Canari W2 **dé-escaladé**, vecteur reformulé. |
| **V1 — vérifier HOS-113 / HOS-114** | 0 | ✅ **Fait 30/07** — HOS-114 à délier (G-6 livré, 12 tests verts) ; HOS-113 reste blocker mais réduit à ~2-3 pts. Incertitude « +0 à +8 pts » **résolue**. Voir §Risques R1 / R1b. |
| _PM parallèle_ | — | **HOS-319** en cours — hors capacité dev |

> **Bonus S0** : HOS-278 a été livré en avance (voir S1).

### S1 — lun 03/08 → dim 09/08 · « Honnêteté métriques + unit economics » (~4 pts restants)

| Item | Épique | Pts | État |
|------|--------|----:|------|
| ~~**HOS-278** spike A2A~~ | 10 | ~~3~~ | ✅ **Livré en avance le 30/07** → `docs/context/apaleo-a2a-spike-decision.md`. **Risque R4 levé.** |
| **HOS-318** gate honnêteté métriques — taxonomie Built/Shadow/Synthetic | 16 | ~2 | ⬜ À faire — **non estimée dans Linear**, à pointer |
| **HOS-312** unit economics — coût/propriété/mois | 16 | 1 | ⬜ À faire |
| **HOS-313** docs stratégiques — **AC1/AC2/AC3 déjà livrés le 09/07** | 16 | ~1 | ⬜ Reste **AC4** (one-pager conformité) + **AC5** (périmètre honnête méta-repo) |

> HOS-312 débloque **HOS-179** (pricing doc, S8).
> **~5 pts de capacité libérés en S1** (HOS-278 fait en avance, HOS-313 aux ⅔ fait). Candidats à remonter : la vérification V1 de S0, ou **HOS-177** depuis S4.
> ⚠️ **HOS-318 porte un arbitrage non trivial** : le benchmark Recruit donne Prophet à **+6,15 pts de MAPE** mais **+0,56 pt de MdAPE** sur la baseline naïve. La DoD d'Epic 16 exige ≥ 5 pts « sinon pivot modèle documenté » — la clause se déclenche ou non selon la métrique lue. À trancher **avant** toute publication (HOS-314, S3).

### S2 — lun 10/08 → dim 16/08 · « Preuve terrain » (~9 pts)

| Item | Épique | Pts |
|------|--------|----:|
| **HOS-308** shadow mode restaurant réel — export POS + backtest FR | 16 | 3 |
| **HOS-309** interviews F&B managers ×5 | 16 | 3 |
| **HOS-317** Decision Ledger — mémoire/feedback/outcome auditables | 16 | ~3 |

> **HOS-308 porte une dépendance externe** (obtenir un export POS 12+ mois d'un restaurateur du réseau). S'il ne rentre pas, voir §Risques R3 — il ne doit pas bloquer S3.

### S3 — lun 17/08 → dim 23/08 · « Clôture J+90 » (~8 pts)

| Item | Épique | Pts |
|------|--------|----:|
| **HOS-314** contenu & distribution — article eval-gate, LinkedIn, registries MCP | 16 | 3 |
| **HOS-321** layer eval `guardrail` — 11 raisons typées Epic 12 | 16 | 5 |

> **Point de bascule.** À l'issue de S3, les 5 critères de sortie d'Epic 16 sont atteints ou à portée, ~6 semaines avant le 05/10. Phase 3 reprend la capacité à partir de S4.

### S4 — lun 24/08 → dim 30/08 · « Reprise Phase 3 : trust + dette eval » (~8 pts + SEC)

| Item | Épique | Pts |
|------|--------|----:|
| **HOS-177** trust-KPI instrumentation — `recommendation_acceptance_rate` | 10 | 3 |
| **HOS-218** EVAL-2 cold-start — abstention Union + propagation orchestrateur | 11 | 2 |
| **HOS-214** extraction des prompts inline restants | 11 | 2 |
| **HOS-219** persist parse confidence | 11 | 1 |
| **HOS-113** SEC-3 — reliquat : headers de sécurité + rate limit API publique + durcissement CORS prod | 7 | **~2-3** |

> HOS-177 livre **l'instrumentation** ; la *mesure* sur données réelles n'arrive qu'après go-live.

### S5 — lun 31/08 → dim 06/09 · « Cold-start — socle données puis algo » (~8 pts)

| Item | Épique | Pts |
|------|--------|----:|
| **HOS-195** cohort extractor worker + migration `hotel_cohort_features` | 10 | 3 |
| **HOS-192** meta-learner core — cohort matching + prior builder + BMA | 10 | 5 |

> Ordre imposé : **HOS-195 mergée avant HOS-192** — 192 consomme les features produites par 195. Migration à séquencer par timestamp.

### S6 — lun 07/09 → dim 13/09 · « Cold-start clôture + Hive Memory » (~10 pts — charge haute)

| Item | Épique | Pts |
|------|--------|----:|
| **HOS-193** cold-start runtime guard & LOO validation + MCP tool | 10 | 5 |
| **HOS-181** Hive Memory v1 — clustering + shapelet + MCP tool | 10 | 5 |

> 10 pts = plafond de capacité. Premier candidat au décalage si S5 a débordé.

### S7 — lun 14/09 → dim 20/09 · « Écosystème Apaleo + dette eval » (~8 pts)

| Item | Épique | Pts | Condition |
|------|--------|----:|-----------|
| **HOS-180** Apaleo Agent Hub listing | 10 | 5 | Forme dictée par la conclusion de **HOS-278** (S1) |
| **HOS-207** EVAL-3 distribution shift + auto-disable cold-start | 11 | 3 | — |

> HOS-180 ne dépend pas de HOS-319 : il reste en S7 malgré le décalage du go-live.

### S8 — lun 21/09 → dim 27/09 · « Monétisation + capitalisation » (~9 pts)

| Item | Épique | Pts |
|------|--------|----:|
| **HOS-179** pricing model decision doc — débloqué par HOS-312 (S1) | 10 | 2 |
| **HOS-183** technical write-up — Day-1 useful via cold-start | 10 | 2 |
| **HOS-178** ablation Receipts on/off — story inchangée | 10 | 5 |

> **Jalon PM — 25/09 : échéance HOS-319** (partenaire signé + creds OAuth2 prod). Conditionne S9.
> HOS-178 reste en l'état, non découpée. Son résultat exige ≥ 28 j de pilote live : il tombe mécaniquement après le J+90.

### S9 — lun 28/09 → dim 04/10 · « Go-live pilote » (~8 pts — **CONDITIONNEL**)

| Item | Épique | Pts | Condition |
|------|--------|----:|-----------|
| **HOS-176** real-pilot deploy Apaleo prod | 10 | 5 | **HOS-319 abouti au 25/09** + R1 levé + HOS-308 fait |
| **HOS-284** instrumentation fiabilité — accept/reject + « confidently wrong » | 11 | 3 | — |

> **Repli si HOS-319 n'aboutit pas au 25/09** : basculer S9 sur **HOS-286** (2) et **HOS-287** (3), et acter le pilote en Phase 3+.

**Hors fenêtre, assumé** : HOS-286 (2) · HOS-287 (3) · HOS-210 (WRITE-REX, 3, Low) · le résultat de HOS-178 · la mesure trust-KPI de HOS-177.

---

## Diagramme dépendances (chemin critique)

```
                    ┌─ EXTERNE / PM ────────────────────────────────┐
                    │  HOS-319 (In Progress)                        │
                    │  partenaire signé + creds OAuth2 Apaleo prod  │
                    │  ÉCHÉANCE 25/09 — révisée le 30/07            │
                    └───────────────────┬───────────────────────────┘
                                        │ blocker DUR, non compressible
                                        │
  HOS-190 ✅ sandbox gate ───────────────┤
                                        │
  HOS-308 (S2, Epic 16) ────────────────┤  prérequis PM 22/07
                                        │
  R1 : HOS-113 / HOS-114 ───────────────┤  ⚠ statut à confirmer (S0)
       (SEC-3 / SEC-4)                  │
                                        ▼
                                  ┌───────────┐
                                  │  HOS-176  │  S9 — CONDITIONNEL
                                  │  go-live  │  dernier sprint, zéro repli
                                  └─────┬─────┘
                                        │
                      ┌─────────────────┼──────────────────┐
                      ▼                 ▼                  ▼
                 HOS-177          HOS-178              HOS-179
              trust-KPI live    ablation J+28        pricing doc
              instru. S4        story inchangée     (aussi ← HOS-312)
              mesure ⤵          résultat ⤵           S8 — DANS la fenêtre
              HORS FENÊTRE      HORS FENÊTRE


  URGENT — indépendants du go-live
  HOS-285 (S0) ──┐
                 ├──► canari concurrentiel W2 / décision « Copilot scope F&B »
  HOS-278 (S1) ──┴──► conditionne la FORME de HOS-180 (S7)


  CHAÎNE COLD-START — parallélisable, hors chemin critique pilote
  HOS-195 (S5) ──► HOS-192 (S5) ──► HOS-193 (S6)
   features          core BMA        runtime guard + LOO

  HOS-181 (S6) Hive Memory v1 — indépendante


  EPIC 16 — prioritaire jusqu'à J+90 (clôture visée S3)
  HOS-313 ─┐
  HOS-318 ─┤
  HOS-312 ─┼──► HOS-179 (S8)
  HOS-308 ─┼──► HOS-176 (S7)
  HOS-309 ─┤
  HOS-317 ─┤
  HOS-314 ─┤
  HOS-321 ─┴──► critères de sortie J+90 (05/10)


  PHASE 4 — hors séquencement Phase 3
  HOS-254 (Epic 13 POS) ──► HOS-255 (Epic 14 Context Graph)
  HOS-253 (G-6) différé
```

---

## Track partenaire — chemin critique externe (HOS-319)

| Étape | Sprint visé | Statut |
|-------|-------------|--------|
| 1. État du recrutement documenté (AC1) — prospects, statuts, blocages | S0-S1 | En cours |
| 2. Kit de recrutement formalisé (AC2) | S1 | À faire |
| 3. Prochaine action + échéance par prospect actif (AC3) | S1-S2 | À faire |
| 4. Partenaire signé + creds OAuth2 Apaleo prod (AC4) | **≤ 25/09 (fin S8)** | **Bloque HOS-176** |
| 5. Go-live (HOS-176) | S9 | Conditionnel #4 |
| 6. ≥ 4 semaines live + trust-KPI mesuré (US-7) | Hors fenêtre | Phase 3 closure |

> **Deadline dure — révisée le 30/07 (décision Ivan)** : l'AC4 est attendu au **25/09** (précédemment 13/09). Décalage assumé, pas dérive : il aligne le plan sur la réalité du recrutement plutôt que l'inverse.
> **Contrepartie** : le go-live tombe dans le dernier sprint de la fenêtre. Il n'y a plus aucun sprint de repli après S9, et le pilote ne produit plus d'outcome mesuré avant le J+90 — voir §Conséquence structurelle.

---

## Conséquence structurelle du décalage au 25/09

Le go-live passe de S7 à **S9 (28/09 → 04/10)**, soit le dernier sprint avant le J+90. Trois effets à acter — ce ne sont pas des risques, ce sont des certitudes arithmétiques :

1. **Phase 3 ne peut plus se clôturer au 05/10.** Son critère de sortie exige ≥ 4 semaines de pilote live (US-7). Départ au plus tôt le 04/10 ⇒ clôture **début novembre**. La fenêtre J+90 reste celle d'Epic 16, pas celle de Phase 3.
2. **HOS-177 livre son instrumentation (S4) mais aucune mesure.** Le trust-KPI n'aura pas de données réelles avant novembre.
3. **HOS-178 est structurellement hors fenêtre** (J+28 depuis le 04/10 ⇒ ~01/11). La story reste inchangée et planifiée en S8 comme demandé ; c'est son *résultat* qui tombe après, pas sa préparation.

Ce que le décalage préserve en revanche : le recrutement partenaire cesse d'être une contrainte artificielle du plan, et les 8 sprints avant S9 sont entièrement dédiés à du travail non conditionnel — Epic 16 clôturée, chaîne cold-start livrée, dette eval résorbée. **Aucun de ces sprints ne dépend de HOS-319.**

---

## Risques + triggers de re-plan

| # | Trigger | Action |
|---|---------|--------|
| **R1** | ~~HOS-113 / HOS-114 confirmés blockers durs~~ — **VÉRIFIÉ 30/07, incertitude résolue** | **HOS-114 : à délier de HOS-176.** La défense G-6 est **livrée et verte** — `reasoning_service._build_prompt` clôture le `cognitive_context` non fiable dans `<UNTRUSTED_MANAGER_NOTES>` + cadrage data-only, instruction amplificatrice retirée ; `tests/security/test_prompt_injection.py` = **12 passed** (xfail levés). Couvre AC2 + AC3 de SEC-4 sur la surface réellement exploitable. Restent AC1 (`input_sanitizer.py`), AC4 (audit log), AC5 (dégradation gracieuse) — **durcissement, pas blocker**. **HOS-113 : reste un blocker réel mais réduit (~2-3 pts)** — voir R1b. |
| **R1b** | **Reliquat SEC-3 à livrer avant go-live** | ✅ CORS configuré (`main.py:201`) mais `allow_methods=["*"]` + `allow_headers=["*"]` avec `allow_credentials=True` → **durcir `CORS_ORIGINS` en prod**. ✅ Rate limiting Redis fail-open (ADR-0003 D6) mais **scopé aux tools MCP uniquement** (`check_rate_limit(hotel_id, tool_name)`) → **surface API publique et webhooks non limités**. ❌ **Headers de sécurité totalement absents** (ni HSTS, ni CSP, ni X-Frame-Options, ni X-Content-Type-Options). |
| **R2** | **HOS-319 sans partenaire signé au 25/09** | HOS-176 sort de la fenêtre — **ne pas le décaler une seconde fois**. Basculer S9 sur HOS-286 + HOS-287 et acter le pilote en Phase 3+. Ne jamais coder HOS-176 « spec-only » sans creds réelles. |
| **R3** | **HOS-308 : aucun export POS obtenu en S2** | Ne pas bloquer S3. Replier sur le seul benchmark Recruit (HOS-307, Done) pour le critère de sortie FR1, et retirer HOS-308 du prérequis de HOS-176 — en actant que le go-live perd sa deuxième lecture de performance réelle. |
| **R4** | ~~HOS-278 conclut « Aetherix = couche F&B de Copilot via A2A »~~ — **LEVÉ le 30/07** | HOS-278 a conclu : **A2A annoncé mais non spécifié** (aucune spec, auth model ni endpoint publics) → **Aetherix reste MCP standalone**. **HOS-180 confirmé tel quel, pas de re-spécification.** Décision consignée : `docs/context/apaleo-a2a-spike-decision.md`. Conditions de bascule B1-B4 en veille, re-vérification trimestrielle au 30/10. |
| **R5** | **S6 déborde (10 pts, plafond capacité)** | Sacrifier **HOS-181** (Hive Memory, indépendante) avant HOS-193 — 193 clôt la chaîne cold-start dont 195 et 192 sont déjà investis. |
| **R6** | **Epic 16 déborde au-delà de S3** | Décaler la reprise Phase 3 d'autant. Les critères de sortie J+90 priment : c'est l'arbitrage acté le 30/07. |
| **R7** | **Migration `hotel_cohort_features` (HOS-195) entre en conflit avec une migration Epic 11** | Séquencer par timestamp, audit ORM mirror (Décision #16) avant merge. Tables distinctes attendues — vérifier avant. |
| **R8** | **Le go-live S9 dérape de quelques jours** | Il n'existe plus de sprint de repli : tout dérapage sort HOS-176 de la fenêtre J+90. Décider **avant** d'ouvrir S9 si on lance le déploiement ou si on l'acte en Phase 3+ — pas en cours de sprint. |

---

## Re-évaluation hebdo

Chaque vendredi 18:00 — relire ce doc :

- AC tickés dans Linear ?
- **HOS-319 : une action concrète a-t-elle bougé cette semaine ?** (le seul blocker non compressible)
- Échéance du **25/09** encore tenable ? Elle a déjà été décalée une fois — un second décalage sort le pilote de la fenêtre (R2).
- Capacité réelle du sprint écoulé vs 8-10 pts — ajuster la suite, pas le passé.
- Un item Urgent est-il resté non planifié ? (le défaut corrigé le 30/07 — ne pas le reproduire)

**Source de vérité finale** = boards Linear HOS-174 (Epic 10), HOS-203 (Epic 11), HOS-300 (Epic 16). Ce doc = vue de séquencement Ivan solo, pas un remplaçant.

---

## Statuts Linear à transitionner (proposition — non appliquée)

Aucune transition n'a été faite. À valider par Ivan avant exécution :

| Issue | Actuel | Proposé | Sprint |
|-------|--------|---------|--------|
| HOS-285 | Backlog | **Todo** | S0 |
| HOS-278 | Backlog | **Todo** | S1 |
| HOS-312 | Backlog | **Todo** | S1 |
| HOS-308 | Backlog | **Todo** | S2 |
| HOS-309 | Backlog | **Todo** | S2 |
| HOS-314 | Backlog | **Todo** | S3 |
| HOS-321 | Backlog | **Todo** | S3 |
| HOS-177 | Backlog | **Todo** | S4 |
| HOS-214 · HOS-219 | Backlog | **Todo** | S4 |
| HOS-317 · HOS-318 | Todo | **estimer** (non pointées) | S1-S2 |
| HOS-319 | In Progress | **poser `dueDate` = 2026-09-25** + estimer ou marquer non-pointable (PM/externe) | — |
| HOS-207 | Backlog | **Todo** | S7 |
| HOS-114 | Backlog | **délier de HOS-176** si R1 le confirme | — |

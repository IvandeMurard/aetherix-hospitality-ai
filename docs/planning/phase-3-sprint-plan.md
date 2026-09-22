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
| Epic 16 — Proof & Visibility | **~13 pts** *(révisé 30/07 : HOS-321 livré −5, HOS-278 livré −3, HOS-313 aux ⅔ −2)* |
| Epic 10 — Pilot Validation | ~45 pts *(HOS-285 et HOS-278 livrés ; +3 pts trace d'émission ajoutés le 11/08, absorbés par la marge S3)* |
| Epic 11 — Evaluation by Design | ~19 pts |
| **Total** | **~74 pts** |

**Tout ne tient pas dans la fenêtre.** Arbitrage retenu :

1. **Epic 16 garde la main jusqu'à ses 5 critères de sortie** — date externe dure, et son plan gèle explicitement les nouvelles features (`plan-90j-proof-visibility.md` §« Ce qu'on ne fait PAS pendant 90 jours »).
2. **Les deux items Urgent Apaleo passent avant** — recherche/doc pure, aucun code, aucun eval gate : compatibles avec le gel.
3. **HOS-308 est traité comme item partagé** — il sert FR1 d'Epic 16 *et* lève le prérequis PM de HOS-176.
4. **La chaîne cold-start et Hive Memory sont décalées après le J+90 d'Epic 16** (S5+), sauf signature partenaire anticipée qui ferait remonter HOS-176.

Epic 16 se clôt à **S2 (16/08)**, soit ~7 semaines avant sa deadline — ce qui libère **S3→S9** pour Phase 3.

> **Révision du 30/07 (fin de journée).** Le reste-à-faire est passé de ~87 à ~74 pts en une journée : HOS-285 et HOS-278 livrés (audits Apaleo), HOS-321 livré en parallèle par une autre session, HOS-313 constaté aux deux tiers fait. **~13 pts de capacité libérés** — la reprise de Phase 3 avance d'une semaine et le chemin critique vers HOS-176 regagne de la marge.

---

## Arbitrage Urgent dormants (tranché le 30/07)

`HOS-285` et `HOS-278` étaient **Urgent depuis fin juin sans être planifiés**. Décision : **priorité Urgent conservée, planifiés en tête de timeline.**

- **HOS-278** (spike A2A, 3 pts) — sa propre description porte « décision time-sensitive avant le pilote M4 (juillet 2026) » : l'échéance est **déjà dépassée**. Surtout, il **conditionne HOS-180** (Agent Hub listing, 5 pts) : si le spike conclut « Aetherix devient la couche F&B de Copilot via A2A », le listing tel que spécifié est du travail perdu. **Faire HOS-180 avant HOS-278 est une erreur de séquencement** — d'où S1 pour l'un, S7 pour l'autre.
- **HOS-285** (audit Trace Agent, 2 pts) — alimente le canari concurrentiel W2 et la décision ouverte « Apaleo Copilot scope F&B ». Placé en amorce S0 car c'est le moins cher des deux.

---

## Amendement 11/08/2026 — la trace de politique doit précéder le go-live

**Le principe.** La couche moat n°1 (`docs/context/moat.md`) n'est pas du code, c'est un corpus de décisions observées. Il commence au premier override d'un vrai manager sur une vraie recommandation, c'est-à-dire à **HOS-176**. Ce qui n'est pas écrit à l'instant de l'émission ne se reconstitue pas *a posteriori* : on peut recalculer une erreur de prévision, jamais la raison pour laquelle cette recommandation-là a été choisie ce jour-là. Chaque jour de pilote qui tourne sans trace d'émission est un jour de corpus définitivement perdu.

**Ce qui est déjà là, et qui réduit fortement le chantier.** [HOS-317](https://linear.app/hospitalityagent/issue/HOS-317) (Decision Ledger, **Done le 01/08**) a fermé quatre des cinq legs : contexte source → recommandation émise → réponse manager *(dashboard **et** WhatsApp)* → outcome mesuré, plus l'abstention/trip typé du tour. Voir `docs/context/decision-ledger.md`. Le cinquième leg est nommément listé comme **non fermé** dans son §5 : *« Confiance à l'émission — colonne volontairement non ajoutée »*. C'est exactement la `propensity` d'ADR-0011 D4.

**Ce qui ne peut pas être le véhicule.** [HOS-247](https://linear.app/hospitalityagent/issue/HOS-247) (Story 3.5, outcome-capture) est **scopée Anima** : projet Linear « Anima — Guest Context Node », parent HOS-230, décisions Orchestrateur, `outcome` = CSAT / NPS / complaint / repeat-booking, table `learning_triples`. Elle est derrière le **gate DPIA non levé** (Décision #20, 13 mesures bloquantes au 01/08), derrière le gel Mesh d'Epic 16, et de facto gated par le modèle d'interaction event-driven (ADR-0012 §2bis). Ses signaux d'outcome n'existent pas dans un pilote F&B. **La remonter avant HOS-176 tirerait tout ce paquet sur le chemin critique du pilote** — pour un corpus qu'elle ne produirait pas.

**L'arbitrage retenu.** Découper le seul leg non reconstructible en une story **Aetherix, F&B, personal-data-free**, branchée sur le Decision Ledger existant — pas un second pipeline de logging (contrainte ADR-0012 §2bis, appliquée à ce qui existe réellement côté Aetherix).

| | |
|---|---|
| **Story** | Trace de politique à l'émission — `policy_id` + `selection_inputs` + confiance/tier sur la recommandation dispatchée |
| **Épique** | 10 (Pilot Validation) · `phase:3` · Aetherix — F&B Execution Node |
| **Points** | 3 |
| **Sprint** | **S3 (17→23/08)** — voir §Arbitrage de capacité ci-dessous |
| **Précondition go-live** | Mergée avant l'ouverture de S9. Aucune recommandation ne part vers un manager réel sans trace d'émission. |

**Périmètre (à raffiner en session SM/Dev) :**

- Persister sur `staffing_recommendations` : `policy_id` (version de la règle de décision qui a émis), `emission_confidence` + `emission_tier` (le verdict `forecast_guardrail.evaluate()` existe déjà à l'émission — Epic 12 G-4 — mais n'atterrit aujourd'hui que sur `agent_action_log`), `selection_inputs` JSONB (`deviation_pct`, baseline, seuil appliqué, `roi_net` au moment de l'émission). Une migration + miroir ORM (Décision #16).
- Exposer ces champs dans `DecisionLedgerService.get_decision()` et la vue `decision_ledger` — ce qui clôt la ligne « Confiance à l'émission » de `decision-ledger.md` §5.
- **Honnêteté sémantique (Décision #33)** : sous une politique déterministe la propensity vaut 1.0 et n'a aucune valeur pour de l'IPW. Ce qui est loggé est la **version de politique + ses entrées de sélection** — ce qui rend l'off-policy evaluation possible *le jour où* une politique stochastique ou multi-bras apparaît, et rend l'écart attribuable dès maintenant. Ne pas revendiquer « propensity loggée pour IPW » tant que la politique est déterministe.
- Aucune donnée personnelle, aucun champ guest. Store = tables Aetherix existantes, **pas** `learning_triples`.

**Ce que la story ne fait pas** : « action effectivement appliquée » (exige POS — Phase 4, Décision #23) et le pendant guest-side (HOS-247, reste Phase 4).

**Coût sur le chemin critique — l'objection posée franchement.** Le chemin vers HOS-176 est déjà chargé (HOS-319 abouti au 25/09 + R1 + HOS-308). Ces 3 points ne s'y ajoutent pas : ils vont dans **S3**, seul sprint avec de la marge réelle depuis que HOS-321 est tombé en avance (S3 ne porte plus que HOS-314, ~5 pts libres). S4 est déjà au plafond (8 pts + SEC-3), S9 n'a aucun repli. Le coût net sur le chemin critique est donc **nul si S3 tient**, et la story reste hors de la fenêtre conditionnelle : elle a de la valeur même si HOS-319 n'aboutit pas — elle ferme un manque documenté du Decision Ledger et débloque [HOS-275](https://linear.app/hospitalityagent/issue/HOS-275) (Bras C).

**Effet de bord positif** : une livraison, deux points fermés. Le trigger de la décision ouverte « Rattachement Bras C » est réécrit sur cette story (`open-decisions.md` §Bras C, amendé le 11/08) — il était auparavant adossé à HOS-247, donc inatteignable.

**Correction d'identifiant (drift D2)** : les docs référençaient « HOS-246 » pour l'outcome-capture. HOS-246 est en réalité l'épique *ADR-0010 multi-repo migration*. Corrigé le 11/08 dans ADR-0011, ADR-0012 §2bis, `decisions-architecturales.md` §26, `open-decisions.md` §Bras C, `CLAUDE.md`.

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
| **HOS-318** gate honnêteté métriques — taxonomie Built/Shadow/Synthetic | 16 | ~2 | ✅ **Livré le 01/08** → `docs/context/status-taxonomy.md`, **Décision #33**. Détecteur D7 branché. Statut Linear à corriger. |
| **HOS-312** unit economics — coût/propriété/mois | 16 | 1 | ✅ **Livré le 31/07** → `docs/Cost_Model.md` v2.0 (`56205c1`, PR #224). Statut Linear corrigé Done. |
| **HOS-313** docs stratégiques — **AC1/AC2/AC3 déjà livrés le 09/07** | 16 | ~1 | ⬜ Reste **AC4** (one-pager conformité) + **AC5** (périmètre honnête méta-repo) |

> HOS-312 débloque **HOS-179** (pricing doc, S8).
> **~5 pts de capacité libérés en S1** (HOS-278 fait en avance, HOS-313 aux ⅔ fait). Candidats à remonter : la vérification V1 de S0, ou **HOS-177** depuis S4.
> ✅ **L'arbitrage HOS-318 est tranché** (Décision #33, 01/08) : le benchmark Recruit donne Prophet à **+6,15 pts de MAPE** mais **+0,56 pt de MdAPE** sur la baseline naïve. Verdict retenu = **PASS formel sur le MAPE, et clause pivot déclenchée volontairement** — à J+1 Prophet est derrière la naïve en médiane. Amendement protocole §7 : le WAPE devient un report obligatoire, le Δ MdAPE reste la métrique primaire.

### S2 — lun 10/08 → dim 16/08 · « Preuve terrain » (~9 pts)

| Item | Épique | Pts |
|------|--------|----:|
| **HOS-308** shadow mode restaurant réel — export POS + backtest FR | 16 | 3 |
| **HOS-309** interviews F&B managers ×5 | 16 | 3 |
| **HOS-317** Decision Ledger — mémoire/feedback/outcome auditables | 16 | ~3 |

> **HOS-308 porte une dépendance externe** (obtenir un export POS 12+ mois d'un restaurateur du réseau). S'il ne rentre pas, voir §Risques R3 — il ne doit pas bloquer S3.

### S3 — lun 17/08 → dim 23/08 · « Clôture J+90 » (~3 pts restants)

| Item | Épique | Pts | État |
|------|--------|----:|------|
| **HOS-314** contenu & distribution — article eval-gate, LinkedIn, registries MCP | 16 | 3 | ⬜ À faire |
| **HOS-326** trace de politique à l'émission — `policy_id` + `selection_inputs` + confiance/tier | 10 | 3 | ⬜ **À créer dans Linear** — voir §Amendement 11/08 |
| ~~**HOS-321** layer eval `guardrail`~~ | 16 | ~~5~~ | ✅ **Livré le 30/07** (commit `aeb68a3`) — couvre **13** raisons typées d'Epic 12, pas 11 comme estimé initialement |

> **Point de bascule — avancé.** Avec HOS-321 livré, S3 ne porte plus que HOS-314. **Epic 16 peut se clôturer dès S2**, soit ~7 semaines avant sa deadline du 05/10. Phase 3 reprend donc la capacité à partir de **S3**, une semaine plus tôt que prévu au re-baseline.

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
| **HOS-176** real-pilot deploy Apaleo prod | 10 | 5 | **HOS-319 abouti au 25/09** + R1 levé + HOS-308 fait + **HOS-326 mergée** (trace d'émission — §Amendement 11/08) |
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
                                        │
  HOS-317 ✅ Decision Ledger             │
     └─► HOS-326 (S3) ────────────────┤  trace d'émission — précondition DURE
            trace de politique          │  du go-live (R9), non reconstructible
            └─► HOS-275 (Bras C, P4)    │  après coup
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
  HOS-321 ✅┴──► critères de sortie J+90 (05/10)


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
| **R9** | **HOS-326 (trace d'émission) n'est pas mergée à l'ouverture de S9** | **Ne pas lancer le pilote sans elle et ne pas la coder en urgence dans S9** (aucun repli dans ce sprint). Deux issues seulement : la remonter dans un sprint antérieur dès que S3 déborde, ou décaler le go-live. Un pilote qui tourne sans trace d'émission produit un corpus amputé de son leg le moins reconstructible — c'est le seul risque de ce plan dont le coût est **irréversible** (les autres coûtent du temps, celui-ci coûte de la donnée qui n'existera jamais). |
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

À valider par Ivan avant exécution — **sauf les trois lignes marquées ✅ appliqué le 11/08** (création HOS-326 + cadrage HOS-247 + re-pointage HOS-275), exécutées sur go explicite d'Ivan :

| Issue | Actuel | Proposé | Sprint |
|-------|--------|---------|--------|
| HOS-285 | Backlog | **Todo** | S0 |
| HOS-278 | Backlog | **Todo** | S1 |
| HOS-312 | Backlog | **Done** — livré le 31/07 (`56205c1`), statut Linear corrigé | — |
| HOS-308 | Backlog | **Todo** | S2 |
| HOS-309 | Backlog | **Todo** | S2 |
| HOS-314 | Backlog | **Todo** | S3 |
| HOS-321 | Backlog | **Done** — livré le 30/07 (`aeb68a3`), statut Linear à corriger | — |
| HOS-177 | Backlog | **Todo** | S4 |
| HOS-214 · HOS-219 | Backlog | **Todo** | S4 |
| HOS-317 · HOS-318 | Todo | **Done** — livrées le 01/08 (`docs/context/decision-ledger.md` · `docs/context/status-taxonomy.md`), statut Linear à corriger. L'estimation n'a plus d'objet. | — |
| HOS-319 | In Progress | **poser `dueDate` = 2026-09-25** + estimer ou marquer non-pointable (PM/externe) | — |
| HOS-207 | Backlog | **Todo** | S7 |
| HOS-114 | Backlog | **délier de HOS-176** si R1 le confirme | — |
| **HOS-326** | ✅ **créée le 11/08** — Epic 10 (HOS-174), projet Aetherix, `phase:3`/`Backend`/`Story`, 3 pts, Urgent, `blocks` HOS-176, `relatedTo` HOS-317 · HOS-177 · HOS-275 · HOS-247 | **Todo** *(appliqué)* | S3 |
| HOS-247 | Backlog | ✅ **cadrage appliqué le 11/08** — scope Anima / guest-side, gated DPIA (Décision #20), réutilise le substrat livré par HOS-326. **Reste Phase 4.** | — |
| HOS-275 | Backlog | ✅ **appliqué le 11/08** — trigger re-pointé sur HOS-326, estimée 3 pts, clause d'honnêteté propensity ajoutée | Phase 4 |

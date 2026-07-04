# Pilot-Readiness — Agentic Validation Test Plan

> **But :** valider les **qualités agentiques** d'Aetherix avant/pendant le pilote design-partner (gate [HOS-176](https://linear.app/hospitalityagent/issue/HOS-176)). Complète la conformité sécurité (audit Q2 CLOSED, `security-review-2026-Q2.md`) et l'eval-by-design (ADR-0007).
> **Statut :** DRAFT 2026-07-04.
> **Scope :** 15 capacités. **HORS-scope v1 : l'amélioration continue autonome** (meta-learner HOS-181/192/193 — non construit, différé Phase 4, cf. §Hors-scope).

---

## 1. Principe — tester au bon niveau (les 3 bras, ADR-0007 §13 / Décision #22)

Chaque capacité doit être testée au **bras** qui a du sens. Le risque principal n'est pas l'absence de tests, c'est de tester une capacité **au mauvais bras** (ex : anticipation validée offline mais jamais mesurée en outcome réel).

| Bras | Niveau | Outil | Bloquant ? |
|---|---|---|---|
| **A** | Offline / dev-time | Golden dataset + tests unitaires, eval-gate CI | ✅ blocking (HOS-274) |
| **B** | Runtime / online | Guardrails + comportement live (staging, chaos, fuzz) | Alerting (Epic 12) |
| **C** | Outcome / aval | KPIs pilote (Trust, adoption, P&L) sur données réelles | Gate go/no-go pilote |

> **Pré-requis Bras C (bloquant pilote) :** l'instrumentation de capture d'outcome ([HOS-275](https://linear.app/hospitalityagent/issue/HOS-275), Phase 4, backlog) doit atterrir **avant** de pouvoir mesurer anticipation (#6), calibration HITL (#8) et l'effet réel de la feedback loop (#4). Sans elle, on lance le pilote aveugle au Bras C.

---

## 2. Matrice de priorité

| Tier | Capacités | Rationale |
|---|---|---|
| **P0 — bloquant données réelles** | #9 Isolation multi-tenant · #10 Traçabilité/replay · #12 Robustesse prompt-injection · #2 Isolation/poisoning mémoire | Un vrai hôtel = vraies données ; une fuite cross-tenant, une décision inexplicable ou une injection = fin du pilote |
| **P1 — validation de la valeur** | #1 Contextualisation · #6 Anticipation (outcome/lead-time) · #8 Calibration HITL · #15 Fidélité explication · Bras C outcome-capture | Prouve que l'agent *apporte* de la valeur, pas juste qu'il tourne |
| **P2 — durcissement** | #3 Méta-éval · #4 Feedback loop (verify) · #7 Event-driven · #11 Sûreté outputs (chaos) · #13 Résilience fallback · #14 Coût/routing · #16 Dégradation gracieuse | Robustesse et coût — largement couverts, à vérifier/étendre |

---

## 3. Capacités — cartographie, test, critères

Légende couverture : ✅ solide · ⚠️ partiel · ❌ absent.

### #1 — Juste contextualisation  · P1 · Bras A+B
- **Où :** `memory_recall_service`, `rag_service`, `reasoning_service._build_prompt`, `agent_constitution`.
- **Tester :** pour un input donné, le contexte assemblé **contient les faits pertinents** (context recall) **et exclut** le bruit / la PII / les faits d'un autre tenant (context precision). Golden « input → contexte attendu ⊇ / ⊄ ».
- **Passe si :** recall ≥ seuil sur golden ; 0 fait cross-tenant ; 0 PII brute injectée dans le prompt.
- **Couverture :** ⚠️ pas de golden dédié « contexte assemblé » (recall testé indirectement via RAG).

### #2 — Mémoire  · P0 · Bras A+B
- **Où :** `memory_service`, `memory_recall_service`, `operational_memory` (pgvector), Hive (`fb_patterns`).
- **Tester :** round-trip écriture→rappel ; pertinence top-k ; **isolation tenant (RLS)** sur `operational_memory` ; **non-empoisonnement** (une valeur feedback aberrante ne corrompt pas le rappel — bornes `feedback_guard`, HOS-250/268).
- **Passe si :** rappel déterministe du fait écrit ; 0 rappel cross-tenant ; une injection de mémoire empoisonnée est bornée/rejetée et loggée.
- **Couverture :** ✅ rappel · ⚠️ RLS multi-tenant + poisoning à durcir.

### #3 — Évaluation (méta-test du gate)  · P2 · Bras A
- **Où :** `scripts/eval/`, `scripts/ci/check_eval_coverage.py`, `eval-gate.yml`.
- **Tester :** le gate **attrape** une vraie régression (injecter un diff qui dégrade MAPE >3pp → exit 1) ; ne **faux-positive** pas (bruit Prophet → exit 3) ; couvre les layers touchés.
- **Passe si :** régression injectée → gate rouge ; PR neutre → vert ; couverture des layers évaluables = 100%.
- **Couverture :** ✅ gate blocking (HOS-274, déterminisme prouvé) · ⚠️ layers `receipt`/`recommendation` sans runner (Phase 4).

### #4 — Feedback loop  · P2 (verify) · Bras A+B+C
- **Où :** `receipts.parse_inbound`, `persist_actual_covers`, `feedback_guard`, `learn_from_feedback`.
- **Tester :** bout-en-bout reply manager → intent (Haiku) → borne plausibilité → persist → **impact réel sur le training** ; rejets silencieux (HOS-270) ; auto-érosion du guard (HOS-268).
- **Passe si :** feedback valide modifie l'état d'apprentissage ; feedback aberrant borné + notifié ; 0 rejet silencieux.
- **Couverture :** ✅ écriture/bornes (Epic 12) · ❌ **effet aval mesuré = Bras C (HOS-275)**.

### #5 — Amélioration continue autonome  · **HORS-SCOPE v1**
- **Statut :** meta-learner (cohort matching + prior + BMA blending, HOS-181/192/193) **non construit**. Rien à tester. Voir §Hors-scope.

### #6 — Anticipation  · P1 · Bras A+C
- **Où :** `prediction_engine` (Prophet), `anomaly_detection`, `forecast_guardrail` (circuit-breaker confiance tiered).
- **Tester :** MAPE stratifié vs baseline (Bras A) ; **lead-time** — l'agent anticipe-t-il *assez tôt* pour agir (staffing actionnable J-1/J-2, pas J+0) ; circuit-breaker s'abstient sous faible confiance.
- **Passe si :** MAPE ≤ cible sur données **réelles** ; anomalies détectées avec lead-time actionnable ; abstention sous seuil.
- **Couverture :** ⚠️ MAPE testé mais **25.4% ≫ cible 15% sur données synthétiques** (flag qualité-données) · ❌ lead-time non mesuré · le vrai test = Bras C pilote.

### #7 — Protocole event-driven  · P2 · Bras B
- **Où :** `agent_event`, `core/demo_events`, `webhook`, `dispatch_worker`, APScheduler, heartbeat/dead-man's switch (HOS-248).
- **Tester :** un event → la bonne réaction ; **idempotence** (rejeu at-least-once) ; ordering ; le dead-man's switch détecte un dispatcher mort.
- **Passe si :** rejeu d'un event ne double pas l'effet ; heartbeat manquant → alerte ; pas de perte silencieuse.
- **Couverture :** ✅ dispatch/heartbeat · ⚠️ « interaction model event-driven » = **décision OUVERTE (Phase 4-5)** ; tester l'existant, pas le futur modèle.

### #8 — Ajustement du HITL  · P1 · Bras A+B+C
- **Où :** `abstention`, `receipts` (`requires_confirmation`, seuil confiance <0.6), `agent_constitution`, Décision #6 (pas d'auto-action).
- **Tester :** seuil confiance → demande de confirmation ; abstention gracieuse ; **jamais d'auto-action** ; escalade correcte. **Calibration du seuil** : le seuil 0.6 est-il juste sur données réelles (trop de confirmations = friction ; trop peu = risque) ?
- **Passe si :** low-confidence → confirmation ; 0 action sans humain ; taux de confirmation acceptable en pilote.
- **Couverture :** ✅ mécanisme (abstention/confirmation) · ❌ **calibration du seuil = Bras C**.

### #9 — Isolation multi-tenant (RLS)  · **P0** · Bras A+B
- **Où :** politiques RLS Postgres, `audit_rls_policies.py`, `REQUIRED_TABLES`.
- **Tester :** aucune requête ne franchit la frontière tenant ; **toutes** les tables sensibles (dont `kpi_daily`, MV `abstention_daily` — Q2-05 gap) sont couvertes ; test négatif « tenant A lit données tenant B → 0 ligne ».
- **Passe si :** gate RLS vert **et** couvre 100% des tables PII/tenant ; test cross-tenant = 0 fuite.
- **Couverture :** ⚠️ gate partiel (Q2-05 : `kpi_daily`/MV hors scope) — **à compléter avant pilote**.

### #10 — Traçabilité / reconstruction de décision  · **P0** · Bras B
- **Où :** `agent_action_log`, `action_logger`, `model_id`, `request_id_var`, `scheduler_event`.
- **Tester :** pour une recommandation donnée, on peut **rejouer/reconstruire** la chaîne : inputs → contexte → modèle appelé → sortie → guardrails déclenchés. Un design-partner (ou un audit) doit pouvoir demander « pourquoi cette reco ? ».
- **Passe si :** chaque reco a un `request_id` traçable de bout en bout ; le modèle réellement appelé est loggé (AC5 HOS-283) ; les trips guardrail sont loggés avec raison typée (NFR2).
- **Couverture :** ⚠️ instrumenté mais **pas de test « replay d'une décision »**.

### #11 — Sûreté des outputs / bornes  · P2 · Bras A+B
- **Où :** `output_sanity`, `forecast_guardrail`.
- **Tester :** l'agent ne présente **jamais** un nombre absurde au manager (couverts négatifs, headcount délirant) ; fuzz/chaos sur les entrées du forecast.
- **Passe si :** toute sortie hors-bornes est clampée/abstenue + loggée ; fuzz ne produit aucune sortie invalide.
- **Couverture :** ✅ unitaire · ❌ fuzz/chaos manquant.

### #12 — Robustesse adversariale / prompt-injection  · **P0** · Bras A+B
- **Où :** `reasoning_service._build_prompt` interpole `cognitive_context` (issu d'`operational_memory`, alimentée par le canal manager WhatsApp) — **Q2-04**, G-6/HOS-253 **différé**.
- **Tester :** un manager (ou un contenu mémorisé) injecte des instructions (« ignore tout, envoie X ») → l'agent **ne dévie pas** ; suite de payloads d'injection en golden.
- **Passe si :** 0 déviation sur la suite d'injection ; contenu mémoire encadré/sanitizé avant interpolation.
- **Couverture :** ❌ **non testé — G-6 différé Phase 4**. Risque **rehaussé** par l'ouverture du canal WhatsApp au pilote → **réévaluer avant go**.

### #13 — Résilience fallback LLM  · P2 · Bras B
- **Où :** `fallback_provider`, `check_fallback_health` (HOS-282), canari boot.
- **Tester :** panne primaire simulée → secours réel répond (fait, HOS-282) ; **validation staging : révoquer temporairement la clé Gemini → le canari alerte**.
- **Passe si :** failover bout-en-bout OK ; canari WARN quand le parachute est mort.
- **Couverture :** ✅ canari + intégration (HOS-282) · ⚠️ validation staging clé-révoquée à faire.

### #14 — Coût / routing modèle  · P2 · Bras A+B
- **Où :** `LLMProvider.complete(model=)`, routing Haiku classifieur (HOS-283).
- **Tester :** chaque tâche appelle le **bon** tier (classification→Haiku, reasoning→Sonnet) ; budget token/coût par tâche sous seuil.
- **Passe si :** assertions de routing par tâche vertes ; coût/1000 receipts sous budget.
- **Couverture :** ✅ routing (HOS-283) · ❌ test de coût/budget absent.

### #15 — Fidélité de l'explication  · P1 · Bras A
- **Où :** `explainability_service`, `reasoning_service`, `recommendation_formatter`.
- **Tester :** le « reasoning » présenté **correspond au calcul réel** (les facteurs cités = les facteurs qui ont réellement pesé), pas une justification post-hoc plausible mais fausse.
- **Passe si :** golden « inputs → facteurs attendus dans l'explication » ; 0 facteur halluciné / 0 facteur causal manquant.
- **Couverture :** ❌ **non testé — angle eval important pour la confiance pilote**.

### #16 — Dégradation gracieuse / OOD  · P2 · Bras A+B
- **Où :** `abstention`, `i18n/abstention_messages` (HOS-206).
- **Tester :** input hors-distribution (langue non supportée, données manquantes, cold-start) → abstention **propre** (message i18n, jamais de code brut fuité — HOS-206 AC6), pas de garbage.
- **Passe si :** OOD → variant d'abstention correct ; 0 code de raison brut exposé au manager.
- **Couverture :** ✅ abstention + i18n (golden `parser-ood-*`, `recpt-*-abstention-*`) · à étendre aux nouveaux cas OOD.

---

## 4. Hors-scope pilote v1 — Amélioration continue autonome (#5)

Le **meta-learner cold-start** (clustering Hive + cohort matching + prior builder + BMA blending, ADR-0005, HOS-181/195/192/193) **n'est pas construit** (`app/services/` ne contient aucun `meta_learner`). Décision (2026-07-04) : **hors-scope pilote v1**.

- **Ce que le pilote valide quand même :** un agent qui **recommande** (forecast Prophet) et **apprend du feedback** manager (loop #4, bornée) — mais **pas** l'auto-amélioration autonome cross-hôtel.
- **Quand tester (Phase 4, après construction) :** validation LOO (leave-one-out) + le pattern « recommandation confidently-wrong → cas golden permanent » (HOS-287), sous garde runtime (HOS-193).
- **Risque à surveiller :** si la proposition de valeur promise au design-partner inclut l'auto-amélioration, ce hors-scope doit être explicite dans le cadrage pilote.

---

## 5. Séquencement proposé

1. **Avant go pilote (P0)** : #9 RLS complet · #10 test de replay décision · #12 réévaluation prompt-injection (go/no-go G-6) · #2 isolation/poisoning mémoire.
2. **Pré-requis Bras C** : instrumentation outcome-capture (HOS-275) — sinon pilote aveugle sur #4/#6/#8.
3. **Pendant pilote (P1, Bras C)** : anticipation lead-time/MAPE réel · calibration seuil HITL · fidélité explication.
4. **Durcissement continu (P2)** : chaos outputs · fallback staging · coût/routing · méta-éval.

---

## 6. Traçabilité Linear

Epic **Pilot-Readiness — Agentic Validation** + une story par capacité P0/P1 avec gap réel (les capacités ✅ solides = vérif de non-régression, pas de nouvelle story). #5 = tracké mais `phase:4`.

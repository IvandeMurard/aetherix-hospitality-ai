# ADR 0009 — Runtime Guardrails: post-deployment reliability layer

> **Status**: **Accepted — livré (G-1→G-5), G-6 différé Phase 4** · **Date**: 2026-06-20 · **Author**: SM/Architect (Opus 4.8)
> **Phase**: 3 (pré-pilote) — pré-requis go-live design partner
> **Linear**: [HOS-212](https://linear.app/hospitalityagent/issue/HOS-212) (Epic 12) — stories G-1→G-6 (HOS-248→253) + findings QA-S4 (HOS-268→273)
> **Implémente**: CLAUDE.md Décision architecturale #27 (clôture mise en conformité)
> **Origine**: `docs/context/security-review-2026-05-01.md` (audit pré-pilote) + finding d'implémentation [HOS-200](https://linear.app/hospitalityagent/issue/HOS-200)
> **Étend**: ADR-0003 (`agent_action_log` — substrat des trips guardrail + raisons typées) ; ADR-0005 (généralise l'auto-disable cold-start en circuit-breaker au dispatch)
> **Articule**: ADR-0007 §13 (frontière des trois bras eval — ce runtime layer = **Bras B**, distinct du Bras A offline-eval) ; Décision #6 (HITL-always — un guardrail flague/rétrograde, ne supprime jamais binairement)

---

## 1. Contexte

Aetherix avait, avant Epic 12, **deux** couches de fiabilité et une troisième manquante :

| Couche | Question | Statut avant Epic 12 |
|---|---|---|
| Pre-merge eval (Epic 11 / ADR-0007, schema-drift gate #16) | « Le modèle est-il bon *avant* le ship ? » | En place |
| HITL par décision (Décision #6) | « Un humain a-t-il approuvé *cette* sortie ? » | En place |
| **Runtime guardrails (cet ADR)** | **« Que se passe-t-il à 2h du matin quand l'agent casse silencieusement chez un hôtel live ? »** | **Quasi absent** |

L'audit pré-pilote (2026-05-01) + le write-path non gardé ouvert par HOS-200 (feedback `actual_covers` → retraining) ont démontré que des parachutes *runtime* manquaient : un cron qui ne se déclenche pas, un pic de timeouts LLM, une valeur de feedback aberrante qui empoisonne Prophet, une reco hors-capacité dispatchée en silence.

**Frontière vs Epic 11 (ADR-0007).** Epic 11 possède l'évaluation *offline/CI* (golden dataset, seuils, gate de régression). Cet ADR possède les parachutes *online/production* (alerting, circuit-breakers, détection de panne silencieuse, bornes I/O). Ils **partagent des seuils** (`eval/FAILURE_THRESHOLDS.md`) mais s'exécutent à des moments différents. C'est la distinction Bras A (offline) / Bras B (runtime) d'ADR-0007 §13.

## 2. Décision

Installer un **layer de guardrails runtime** au point de dispatch et sur les paths planifiés, gouverné par trois invariants transverses, et décliné en 6 guardrails catalogués.

### 2.1 Invariants (NFR)

- **NFR1 — Budget latence** : un check guardrail ajoute < 50 ms au path de dispatch (cohérent budget MCP).
- **NFR2 — Auditabilité** : *tout* trip guardrail est loggé dans `agent_action_log` avec une **raison typée** (réutilise le contrat abstention ADR-0007 §D6 / EVAL-2 ; alimente les métriques d'abstention Epic 11).
- **NFR3 — Config-driven** : les seuils sont configurables sans redéploiement ; défauts documentés à côté de `eval/FAILURE_THRESHOLDS.md` (+ `eval/HEARTBEAT_THRESHOLDS.md`).
- **Non-suppression (Décision #6)** : un guardrail **flague ou rétrograde** vers une sortie plus sûre — il ne supprime jamais binairement une sortie attendue par le manager (livrer *rien* est pire que livrer un chiffre avec réserve).

### 2.2 Catalogue des guardrails

| ID | Guardrail | Story | Statut |
|---|---|---|---|
| **G-1** | Heartbeat / dead-man's switch sur dispatchers planifiés (Daily Receipt, weekly digest) — un run manqué/en échec alerte sous un cycle. Replie le fix du dispatch path cassé (HOS-211). | [HOS-248](https://linear.app/hospitalityagent/issue/HOS-248) | ✅ Livré |
| **G-2** | Alerting ops sur taux d'erreur agent / spikes de timeout LLM (fenêtre glissante sur `agent_action_log`). | [HOS-249](https://linear.app/hospitalityagent/issue/HOS-249) | ✅ Livré |
| **G-3** | Garde-fou bornes d'entrée sur la boucle feedback→training — `actual_covers` borné (capacité + range historique) avant persist *et* avant ré-ingestion retraining. | [HOS-250](https://linear.app/hospitalityagent/issue/HOS-250) | ✅ Livré |
| **G-4** | Circuit-breaker forecast tiered-confidence au dispatch — généralise l'auto-disable cold-start (ADR-0005) : confiance basse → rétrograde/flague (pas de suppression). | [HOS-251](https://linear.app/hospitalityagent/issue/HOS-251) | ✅ Livré |
| **G-5** | Bornes de sanity sur les outputs recommandés — headcount/covers contre capacité propriété + delta max avant dispatch. | [HOS-252](https://linear.app/hospitalityagent/issue/HOS-252) | ✅ Livré |
| **G-6** | Durcissement prompt-injection / inputs adverses sur le path inbound free-text → Haiku. | [HOS-253](https://linear.app/hospitalityagent/issue/HOS-253) | ⏳ **Différé Phase 4** |

**Décision sur G-6** : différé Phase 4 — classé stretch par l'audit (canal manager authentifié = surface réduite), report autorisé par la DoD Epic 12 « shipped *or explicitly deferred with rationale* ». À re-prioriser avec le durcissement sécurité Epic 7 / SEC-4.

### 2.3 Alert sink

Sink = **dispatch ops existant** (Linear/WhatsApp selon la criticité), cohérent avec le pattern `ops_dispatcher` déjà en place — pas de nouveau canal introduit.

## 3. Conséquences

**Positives**
- Le bloquant audit pré-pilote (panne silencieuse, empoisonnement modèle, reco aberrante) est levé → débloque l'arbitrage gate pilote [HOS-176](https://linear.app/hospitalityagent/issue/HOS-176).
- Les trips alimentent les métriques d'abstention Epic 11 (boucle offline↔runtime via raison typée commune).
- Seuils config-driven → tunables en pilote sans redéploiement.

**Négatives / dette**
- G-6 non couvert : le path inbound free-text reste sans durcissement anti-injection dédié (risque accepté, canal authentifié).
- Le registre des jobs surveillés a nécessité 3 findings d'altitude (HOS-271/272/273, résolus) — la généralisation du dead-man's switch reste à surveiller si de nouveaux dispatchers sont ajoutés.

## 4. Alternatives écartées

- **Suppression binaire des sorties low-confidence** : écartée (Décision #6 HITL-always — un staffing avec réserve > pas de staffing).
- **Nouveau canal d'alerting (Slack dédié)** : écarté pour la Phase 3 — réutilise le dispatch ops Linear/WhatsApp existant (coût ops nul).
- **Guardrails dans un sidecar séparé** : écarté — checks in-process < 50 ms, cohérent avec le rejet du sidecar MCP (ADR-0001).

## 5. Amendement 14/11/2026 — un garde-fou qui plante rend « non vérifié » (règle B)

> Décision signée par le PO le 14/11/2026, appliquée par HOS-366. Origine : `docs/context/audit-silences-2026-09.md` (catégories F et G, cas 3, 9, 10, 11, 12) — plusieurs garde-fous s'ouvraient en silence quand ils plantaient, ce qui contredisait NFR2 : un garde-fou qui plante sans rien dire n'est jamais compté comme déclenché.

**Règle.** Un garde-fou qui ne peut pas s'exécuter (exception, entrée illisible, dépendance indisponible) rend un verdict typé **« non vérifié »** et un événement (NFR2). Effets :

- le résultat n'est **jamais présenté comme vérifié** ;
- au pire, le manager reçoit le chiffre avec une **réserve qualitative** visible — jamais un silence, jamais un chiffre propre (cohérent avec la non-suppression §2.1 et G-4) ;
- **aucun score de confiance chiffré n'est montré au manager** : la `confidence` actuelle est une heuristique de largeur d'intervalle, non calibrée (et constante à 0.85 sur le mock non entraîné) ;
- jamais de valeur plausible inventée sur échec : absence typée, verdict « non vérifié », ou erreur ;
- pas de génération libre par le modèle sans la constitution de l'agent : réponse ou explication déterministe à la place.

**Exception écrite** : le *fail-open* voulu du rate-limit (`rate_limit.check_rate_limit_async`), qui reste ouvert quand Redis est indisponible.

**Porteurs réutilisés.** Raison HOS-206 `guardrail_not_verified` (ajoutée à l'ensemble, copie FR/EN qualitative dans `app/i18n/abstention_messages.py`) ; verdict `NOT_VERIFIED` de `forecast_guardrail` (G-4) ; sévérité `unverified` de `feedback_guard` (G-3, valeur enregistrée avec la source `manager_feedback_unverified` et sans `actual_covers`) ; raison `constitution_unavailable` du garde-fou de constitution WhatsApp. Chaque verdict « non vérifié » écrit une ligne typée dans `agent_action_log` et lève une alerte ops de niveau erreur. Couvert par la couche eval `guardrail` (scénarios positifs et négatifs).

**Limite connue.** Les enregistreurs de déclenchement avalent encore leur propre échec (catégorie M de l'audit) : traité par HOS-367, pas ici.

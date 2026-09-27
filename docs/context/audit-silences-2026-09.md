# Audit des silences — erreurs avalées sans signal (24/09/2026)

> **Statut : audit, pas décision.** Il prépare une future décision architecturale (portée : toute l'architecture, demande PM du 24/09/2026). Son numéro sera attribué au moment de la rédaction : annoncé d'avance, il a été pris deux fois par des sessions parallèles (#37, puis #40). Aucun code n'est modifié ici.
> **Principe audité :** une erreur doit être *entendue* (un événement typé), puis *analysée* (classée par criticité), puis *remontée ou non* selon cette criticité. Un log que rien ne lit n'est pas une écoute.

## Méthode

- **Périmètre :** tout le code qui s'exécute sans humain devant.
  - Aetherix : `backend/app`, `backend/orchestrator`.
  - Tacet : `app/`, commit `2816b5d`, lu en lecture seule.
  - Le méta-repo ne contient pas de code.
  - L'UI Tacet ne contient aucun bloc `catch`.
- **Détection :** analyse syntaxique (AST) de chaque `except Exception`, `except BaseException` et `except:` nu. Un gestionnaire est compté comme **avalant l'erreur** s'il remplit deux conditions :
  - il ne relance pas (`raise`) ;
  - il n'appelle aucun mécanisme de signal existant : `guardrail_trip`, `record_trip`, `dispatch_anomaly`, `dispatch_error`, `record_heartbeat`, écriture `status=` dans `agent_action_log`, abstention.
- **Classement :** fait cas par cas, à la main, en lisant chaque gestionnaire et ce que reçoit l'appelant. Les cas les plus graves (P1 des catégories F, G, R) ont été vérifiés dans le contexte du code, pas seulement dans l'extrait.
- **Résultat :**
  - Aetherix + Tacet : 179 gestionnaires larges, dont 140 avalent l'erreur ;
  - hors scripts, **93 cas d'exécution** (77 Aetherix, 16 Tacet), tous classés, sans reste.

### Limites

- **Les `except` étroits ne sont pas couverts.** Un `except ValueError: return 0` déguise une erreur tout aussi bien. Le nombre réel de silences est donc **plus élevé**.
- **La détection des signaux se fait par motif textuel.** Un signal émis par une fonction intermédiaire peut être manqué. Exemple : `apaleo_adapter.py:274` a été reclassé à la main en S.
- **La criticité est un jugement**, fait sans données d'exploitation (aucun pilote réel). Le PM doit la relire avant la décision.
- **Les scripts sont hors périmètre (45 cas).**
  - Les gates de CI signalent par leur code de sortie, sauf deux `pass` légitimes : l'échauffement de `smoke_test_e2e.py:139` et le chargeur d'environnement optionnel de `audit_rls_policies.py:50`.
  - Les scripts `scripts/ops` sont lancés par un humain qui lit leur sortie.

## Catégories

| Code | Catégorie | Pourquoi c'est un silence |
|---|---|---|
| **F** | Échec déguisé en donnée valide | L'appelant reçoit `80`, `0.0`, `[]`, `None` ou une valeur par défaut, et ne peut pas la distinguer d'une vraie réponse. C'est la pire : un faux négatif enregistré comme un fait. |
| **G** | Garde-fou contourné | Le contrôle qui devait protéger ne s'exécute pas, ou s'ouvre, et le traitement continue comme s'il était passé. |
| **R** | Aucune trace | `pass`, ou retour sans log. Rien ne permet de savoir que quelque chose a échoué. |
| **M** | L'alarme échoue | L'échec concerne le mécanisme qui devait signaler (trace de garde-fou, alerte ops, observabilité). Seul un log le mentionne. Quand l'alarme ne sonne pas, personne ne l'apprend. |
| **L** | Livraison client ratée | Le manager ne reçoit pas un message qui lui était destiné. |
| **D** | Dégradation silencieuse | Un repli fonctionne, mais la qualité baisse sans que rien ne l'enregistre. |
| **S** | Déjà signalé | Le signal passe par la donnée ou par la réponse (ligne `pending`, erreur renvoyée, compteur lu par le heartbeat). Il n'est pas dans la liste des mécanismes détectés, mais il existe. |
| **OK** | Légitime | Arrêt de l'application, span neutre, entrée illisible sans conséquence. |

## Criticité proposée et routage

| Niveau | Quand | Routage proposé |
|---|---|---|
| **P1 — alerte** | Donnée fausse persistée, garde-fou contourné, alarme en panne, client non servi | Linear **Urgent**, assigné, donc notification push sur mobile. Aujourd'hui, `ops_dispatcher` n'émet que **High** (erreurs) et **Medium** (anomalies) : aucune alerte Urgent n'existe. |
| **P2 — digest** | Dégradation rattrapée, repli fonctionnel | Événement typé `degraded` avec sa raison, compté. Au-delà d'un seuil sur une fenêtre, il passe en P1 (même mécanique que le moniteur de taux d'erreur, HOS-249). |
| **P3 — log** | Bruit attendu | Log seul, justifié par un commentaire. |

**Canal.** Linear pour l'exploitation, WhatsApp réservé au client (le manager). Une alerte d'exploitation envoyée au manager serait à la fois du bruit et une fuite d'information interne. En revanche, Linear n'est un canal d'**alerte** que si la criticité P1 déclenche une notification push. Sinon c'est une file d'attente, et une alerte P1 lue le lendemain est un silence retardé.

**Cas particulier de la catégorie M.** Une alarme en panne ne peut pas s'annoncer par le même canal. Il faut un signal par l'absence : le dead-man's switch (heartbeat) qui existe déjà doit couvrir aussi le canal d'alerte lui-même. Par exemple, une alerte-témoin périodique qui doit arriver dans Linear, dont l'absence se remarque.

## Ce que l'audit trouve

**1. Des données inventées sont enregistrées comme réelles (F, P1).**
- `ApaleoMCPAdapter.get_occupancy` renvoie **80 %** si Apaleo échoue. `pms_sync` enregistre cette valeur dans `PMSSyncLog` comme une vraie occupation.
- `get_revenue` fait de même avec **0.0**.
- Côté Tacet :
  - `query_paris_events` renvoie `risk_score: 0.0` : l'échec est présenté comme « aucun risque ». Or Tacet vend précisément une mesure du risque.
  - Les flux météo, trafic, chantiers et événements renvoient `None` ou `[]`, sans distinction avec « rien à signaler ».

**2. Des garde-fous s'ouvrent quand ils plantent (G, P1).**
- Le garde-fou G-3 (`_check_feedback_bounds`, Epic 12) renvoie `BoundsVerdict(True, "ok")` si sa lecture en base échoue. Le retour du manager part alors vers l'entraînement sans aucune borne.
- Le garde-fou de prévision (`aetherix_engine.py:152`) est sauté avec un simple WARNING : la prévision est livrée sans lui.
- Le LLM WhatsApp et l'orchestrateur tournent **sans la constitution de l'agent** si son chargement échoue.

Ces cas contredisent l'invariant de la Décision #27 : « tout déclenchement de garde-fou est loggé avec une raison typée ». Un garde-fou qui plante sans rien dire n'est jamais considéré comme déclenché.

**3. L'alarme est le maillon le plus silencieux (M : 21 cas, dont 11 P1).**
- Presque chaque enregistrement de déclenchement (`feedback_guard`, `output_sanity`, `forecast_guardrail`, `error_rate_monitor`, garde-fou de prévision mock) avale son propre échec.
- `ops_dispatcher.dispatch_error` aussi : si Linear est injoignable, l'alerte disparaît avec un WARNING.
- Le canari du fallback (HOS-282) ne tourne qu'au démarrage, et son échec est un WARNING. Sa docstring de test annonce une exécution chaque nuit, mais aucun workflow planifié ne la lance.

**4. L'envoi de recommandations peut échouer sans aucune trace (R, P1).**
- `alert_dispatcher.run_pending` fait `except Exception: pass` pour chaque recommandation. Pas même un log.

**5. Les échecs d'envoi au client ne sont que loggés (L : 11 cas).**
- WhatsApp, e-mail, réponse d'explicabilité, accusés de réception.
- Seule la boucle d'envoi des Receipts compte ses échecs, que le heartbeat lit (`evaluate_partial`). Les envois un par un ne le font pas.

**Ce qui fonctionne et sert de modèle :**
- l'écriture `embedding_pending` : l'échec est porté par la donnée elle-même (ADR D9) ;
- le comptage des échecs d'envoi lu par le heartbeat ;
- le moniteur de taux d'erreur avec anti-répétition.

La règle à venir devrait **généraliser ces motifs**, pas en inventer un nouveau.

## Proposition pour la future décision (à trancher, non décidée)

1. **Jamais d'erreur avalée sans événement typé.** Un gestionnaire large doit faire l'une de ces trois choses :
   - relancer ;
   - appeler un garde-fou ou un déclenchement typé ;
   - écrire un événement `degraded` avec sa raison.
   
   Le log seul n'est admis que pour P3, avec une justification écrite dans le code.
2. **Jamais de valeur inventée.** Un échec ne renvoie pas une valeur plausible. Il renvoie une absence **typée**, que l'appelant doit traiter : `None` explicitement documenté, `AgentAbstention`, ou une erreur.
3. **Un garde-fou qui plante est un déclenchement.** Il se ferme (*fail-closed*) et il est remonté. Exception : un *fail-open* voulu (comme le rate-limit), écrit comme tel dans la décision.
4. **L'alarme se surveille par l'absence** (catégorie M), via le dead-man's switch existant.
5. **Vérifié en CI :** un détecteur de l'agent d'hygiène refuse tout **nouveau** gestionnaire qui avale une erreur, sauf les exceptions listées et justifiées, comme pour le détecteur D1. Les 93 cas existants sont traités par lots, P1 d'abord, sans bloquer la CI sur l'existant.

## Suite proposée

- **Lot P1** (33 cas) : correctifs par catégorie, F et G d'abord.
  - Les 7 cas P1 de Tacet sont à arbitrer à part : Tacet est en pause et en maintenance depuis juillet 2026.
- **La décision** est rédigée **après** relecture de cette criticité par le PM ; elle prend le prochain numéro libre à cette date.
- **Détecteur d'hygiène** (règle 5) livré avec la décision, pour que la règle soit vérifiable dès le premier jour.

## Tableau complet (93 cas, triés par criticité puis catégorie)

| # | Crit. | Cat. | Nœud | Emplacement | Log | Ce que voit l'appelant |
|---|---|---|---|---|---|---|
| 1 | P1 | F | Aetherix | `backend/app/services/apaleo_mcp_adapter.py:58` (`get_occupancy`) | error | occupation inventée à 80 %, enregistrée comme réelle |
| 2 | P1 | F | Aetherix | `backend/app/services/apaleo_mcp_adapter.py:83` (`get_revenue`) | error | revenu F&B inventé à 0.0 |
| 3 | P1 | F | Aetherix | `backend/app/services/apaleo_mcp_adapter.py:111` (`get_historical_data`) | error | historique vide au lieu de « lecture échouée » |
| 4 | P1 | F | Tacet | `app/ingest/paris_events.py:75` (`fetch_active_events`) | print | « aucun événement » au lieu de « flux injoignable » (print) |
| 5 | P1 | F | Tacet | `app/ingest/paris_permits.py:62` (`fetch_active_permits`) | print | « aucun chantier » au lieu de « flux injoignable » (print) |
| 6 | P1 | F | Tacet | `app/ingest/traffic.py:37` (`fetch_traffic_congestion`) | print | trafic absent = « pas de congestion » (print) |
| 7 | P1 | F | Tacet | `app/ingest/weather.py:31` (`fetch_current_weather`) | print | météo absente (print) |
| 8 | P1 | F | Tacet | `app/services/paris_signals.py:93` (`query_paris_events`) | none | `risk_score: 0.0` : échec présenté comme « aucun risque » |
| 9 | P1 | G | Aetherix | `backend/app/services/aetherix_engine.py:152` (`_apply_forecast_guardrail`) | warning | prévision livrée sans garde-fou |
| 10 | P1 | G | Aetherix | `backend/app/services/receipts.py:746` (`_check_feedback_bounds`) | warning | garde-fou G-3 ouvert : `BoundsVerdict(True, "ok")`, retour manager vers l'entraînement sans borne |
| 11 | P1 | G | Aetherix | `backend/app/services/whatsapp_service.py:228` (`_generate_response`) | warning | LLM appelé sans la constitution de l'agent |
| 12 | P1 | G | Aetherix | `backend/orchestrator/agent.py:111` (`get_forecast`) | warning | prévision orchestrée sans constitution ni profil |
| 13 | P1 | R | Aetherix | `backend/app/services/alert_dispatcher.py:140` (`run_pending`) | none | envoi de recommandation échoué, aucune trace |
| 14 | P1 | M | Aetherix | `backend/app/core/observability.py:72` (`configure_observability`) | warning | observabilité désactivée au démarrage, signalée par un WARNING |
| 15 | P1 | M | Aetherix | `backend/app/providers/fallback_provider.py:146` (`check_fallback_health`) | warning | canari du fallback : un WARNING au démarrage, rien d'autre |
| 16 | P1 | M | Aetherix | `backend/app/services/feedback_guard.py:140` (`record_feedback_trip`) | warning | déclenchement de garde-fou non enregistré |
| 17 | P1 | M | Aetherix | `backend/app/services/feedback_guard.py:152` (`record_feedback_trip`) | warning | alerte ops non envoyée |
| 18 | P1 | M | Aetherix | `backend/app/services/forecast_guardrail.py:210` (`record_forecast_trip`) | warning | déclenchement de garde-fou non enregistré |
| 19 | P1 | M | Aetherix | `backend/app/services/ops_dispatcher.py:36` (`dispatch_error`) | warning | canal d'alerte Linear en panne, signalé par un WARNING |
| 20 | P1 | M | Aetherix | `backend/app/services/output_sanity.py:135` (`record_sanity_trip`) | warning | déclenchement de garde-fou non enregistré |
| 21 | P1 | M | Aetherix | `backend/app/services/reporting_service.py:119` (`_dispatch_ops`) | warning | alerte de déclenchement non envoyée |
| 22 | P1 | M | Aetherix | `backend/app/services/whatsapp_service.py:68` (`_record_mock_forecast_trip`) | warning | déclenchement de garde-fou non enregistré |
| 23 | P1 | M | Aetherix | `backend/app/workers/error_rate_monitor.py:169` (`_write_trip_row`) | warning | alerte de taux d'erreur non enregistrée |
| 24 | P1 | M | Aetherix | `backend/app/workers/latency_slo_worker.py:134` (`_alert`) | warning | alerte de latence non envoyée |
| 25 | P1 | L | Aetherix | `backend/app/api/routes/notifications.py:126` (`trigger_dispatch`) | exception | envoi manuel échoué |
| 26 | P1 | L | Aetherix | `backend/app/api/routes/twilio_inbound.py:341` (`_bg_receipt_feedback`) | warning | accusé de réception non envoyé |
| 27 | P1 | L | Aetherix | `backend/app/api/routes/twilio_inbound.py:431` (`_bg_receipt_feedback`) | warning | réponse au manager non envoyée |
| 28 | P1 | L | Aetherix | `backend/app/services/explainability_service.py:82` (`_send_twilio_reply`) | error | réponse non envoyée |
| 29 | P1 | L | Aetherix | `backend/app/services/whatsapp_service.py:271` (`send_message`) | error | message WhatsApp non envoyé |
| 30 | P1 | L | Aetherix | `backend/app/workers/receipts_dispatcher.py:75` (`_send_to_channels`) | exception | Receipt WhatsApp non envoyé |
| 31 | P1 | L | Aetherix | `backend/app/workers/receipts_dispatcher.py:91` (`_send_to_channels`) | exception | Receipt e-mail non envoyé |
| 32 | P1 | L | Tacet | `app/integrations/apaleo_client.py:58` (`push_apaleo_maintenance`) | print | tâche de maintenance non poussée au PMS (print) |
| 33 | P1 | L | Tacet | `app/integrations/mews_client.py:40` (`push_mews_tasks`) | print | tâches non poussées à Mews (print) |
| 34 | P2 | F | Aetherix | `backend/app/services/decision_ledger.py:309` (`_action_log_for`) | warning | ledger : « pas d'action » au lieu de « lecture échouée » |
| 35 | P2 | F | Aetherix | `backend/app/services/events_enrichment.py:73` (`enrich_events_context`) | warning | « aucun événement » au lieu de « requête échouée » |
| 36 | P2 | F | Aetherix | `backend/app/services/memory_recall_service.py:166` (`_recall_private`) | warning | « mémoire vide » au lieu de « rappel échoué » |
| 37 | P2 | F | Aetherix | `backend/app/services/memory_recall_service.py:214` (`_cold_start_fallback`) | warning | idem |
| 38 | P2 | F | Aetherix | `backend/app/services/rag_service.py:187` (`find_similar_patterns_by_embedding`) | warning | « aucun pattern » au lieu de « recherche échouée » |
| 39 | P2 | F | Aetherix | `backend/app/services/receipts.py:510` (`parse_inbound`) | exception | intention `free_form` par défaut (confiance 0.5 → confirmation demandée) |
| 40 | P2 | F | Aetherix | `backend/app/services/roi_calculator.py:333` (`_get_property_rates`) | debug | ROI calculé sur des tarifs par défaut (log DEBUG) |
| 41 | P2 | F | Aetherix | `backend/app/services/whatsapp_service.py:218` (`_generate_response`) | warning | réponse au manager bâtie sur un contexte de prévision par défaut |
| 42 | P2 | F | Tacet | `app/services/spatial.py:64` (`get_surrounding_buildings`) | print | « aucun bâtiment » au lieu de « OSM injoignable » (print) |
| 43 | P2 | G | Aetherix | `backend/app/services/rate_limit.py:92` (`check_rate_limit_async`) | warning | rate-limit ouvert (fail-open voulu) |
| 44 | P2 | R | Aetherix | `backend/app/api/routes/events.py:41` (`_background_sync`) | none | synchro événements échouée, aucune trace |
| 45 | P2 | R | Aetherix | `backend/app/services/roi_calculator.py:253` (`run_full_scan`) | exception | scan ROI qui ne fait rien |
| 46 | P2 | M | Aetherix | `backend/app/api/routes/predictions.py:337` (`train_prophet`) | warning | audit d'entraînement perdu |
| 47 | P2 | M | Aetherix | `backend/app/core/observability.py:106` (`guardrail_trip`) | debug | événement de garde-fou perdu (log DEBUG) |
| 48 | P2 | M | Aetherix | `backend/app/mcp_server.py:433` (`dispatch_tool`) | warning | trace d'audit MCP perdue |
| 49 | P2 | M | Aetherix | `backend/app/services/agent_event.py:91` (`emit_agent_event`) | warning | événement d'agent perdu |
| 50 | P2 | M | Aetherix | `backend/app/workers/heartbeat.py:167` (`_write_event`) | warning | événement heartbeat perdu (le dead-man's switch finit par le voir) |
| 51 | P2 | M | Aetherix | `backend/app/workers/kpi_aggregator.py:221` (`run_kpi_aggregation`) | warning | KPI publiés au manager périmés |
| 52 | P2 | M | Aetherix | `backend/app/workers/latency_slo_worker.py:115` (`run_latency_slo_job`) | warning | moniteur de latence arrêté |
| 53 | P2 | L | Aetherix | `backend/app/services/whatsapp_service.py:242` (`_generate_response`) | error | message d'excuse au manager |
| 54 | P2 | L | Tacet | `app/integrations/apaleo_client.py:27` (`get_apaleo_token`) | print | jeton Apaleo absent (print) |
| 55 | P2 | D | Aetherix | `backend/app/api/routes/predictions.py:433` (`_apply_captation_calibration`) | warning | calibration de captation sautée |
| 56 | P2 | D | Aetherix | `backend/app/api/routes/twilio_inbound.py:402` (`_bg_receipt_feedback`) | exception | retour manager non mémorisé (apprentissage perdu) |
| 57 | P2 | D | Aetherix | `backend/app/api/routes/weather.py:102` (`_run_sync`) | none | météo périmée (régresseur) |
| 58 | P2 | D | Aetherix | `backend/app/mcp_server.py:133` (`tool_get_recommendations_with_memory_context`) | warning | rappel mémoire par récence, pas par sens |
| 59 | P2 | D | Aetherix | `backend/app/mcp_server.py:169` (`tool_get_recommendations_with_memory_context`) | warning | reco sans prévision |
| 60 | P2 | D | Aetherix | `backend/app/mcp_server.py:216` (`tool_recall_memory`) | warning | idem |
| 61 | P2 | D | Aetherix | `backend/app/services/aetherix_engine.py:42` (`__init__`) | warning | moteur sans modèle rechargé (garde `is_mock` HOS-303) |
| 62 | P2 | D | Aetherix | `backend/app/services/explainability_service.py:300` (`_call_claude`) | error | réponse de repli |
| 63 | P2 | D | Aetherix | `backend/app/services/pms_sync.py:168` (`_trigger_captation_recalculation`) | warning | baseline de captation non recalculée |
| 64 | P2 | D | Aetherix | `backend/app/services/prediction_engine.py:76` (`train`) | warning | prévision sans jours fériés |
| 65 | P2 | D | Aetherix | `backend/app/services/rate_limit.py:62` (`_make_client`) | warning | limitation en mémoire locale (multi-instance affaiblie) |
| 66 | P2 | D | Aetherix | `backend/app/services/receipts.py:418` (`compose_narrative`) | exception | narratif de repli |
| 67 | P2 | D | Aetherix | `backend/app/services/receipts.py:888` (`compose_weekly_narrative`) | exception | narratif hebdo de repli |
| 68 | P2 | D | Aetherix | `backend/app/workers/event_sync.py:58` (`_run_event_sync_for_all_tenants`) | error | événements périmés pour un hôtel |
| 69 | P2 | D | Aetherix | `backend/app/workers/weather_sync.py:60` (`_run_weather_sync_for_all_tenants`) | error | météo périmée pour un hôtel |
| 70 | P2 | D | Aetherix | `backend/orchestrator/agent.py:192` (`_recall_with_retry`) | warning | rappel mémoire vide |
| 71 | P2 | D | Tacet | `app/ingest/worker.py:105` (`sync_external_data`) | error | synchro abandonnée, rollback |
| 72 | P2 | S | Tacet | `app/mcp_server.py:47` (`get_environmental_risk_profile`) | none | texte d'erreur renvoyé au client MCP (non typé) |
| 73 | P2 | S | Tacet | `app/mcp_server.py:87` (`get_paris_events`) | none | idem |
| 74 | P3 | F | Aetherix | `backend/app/api/routes/predictions.py:451` (`_compute_in_sample_mape`) | warning | MAPE in-sample absent |
| 75 | P3 | M | Aetherix | `backend/app/services/ops_dispatcher.py:44` (`dispatch_error`) | warning | canal secondaire (Obsidian) |
| 76 | P3 | M | Aetherix | `backend/app/services/ops_dispatcher.py:73` (`dispatch_report`) | warning | canal secondaire (Obsidian) |
| 77 | P3 | M | Aetherix | `backend/app/workers/memory_metrics.py:22` (`refresh_memory_instrumentation_mv`) | warning | vue d'instrumentation périmée |
| 78 | P3 | D | Aetherix | `backend/app/services/memory_recall_service.py:112` (`check_cosine_dedup`) | warning | doublon mémoire possible |
| 79 | P3 | D | Aetherix | `backend/app/services/memory_service.py:180` (`get_relevant_context`) | error | repli de dialecte SQL |
| 80 | P3 | D | Aetherix | `backend/app/services/rag_service.py:108` (`find_similar_patterns`) | error | repli de dialecte SQL |
| 81 | P3 | S | Aetherix | `backend/app/api/routes/mcp_v1.py:100` (`mcp_v1_rpc`) | exception | erreur RPC 500 renvoyée au client |
| 82 | P3 | S | Aetherix | `backend/app/mcp_server.py:301` (`tool_submit_feedback_to_memory`) | warning | ligne `embedding_pending` en base (ADR D9) |
| 83 | P3 | S | Aetherix | `backend/app/services/apaleo_adapter.py:274` (`update_staffing_in_pms`) | error | écrit via `_agent_logger.log` |
| 84 | P3 | S | Aetherix | `backend/app/services/memory_service.py:272` (`_safe_embed`) | warning | ligne `embedding_pending` |
| 85 | P3 | S | Aetherix | `backend/app/workers/receipts_dispatcher.py:136` (`_run_dispatch_loop`) | exception | compté → heartbeat `evaluate_partial` |
| 86 | P3 | S | Tacet | `app/api/webhooks.py:81` (`dispatch_daily_report`) | none | erreur comptée dans la réponse |
| 87 | P3 | OK | Aetherix | `backend/app/core/observability.py:90` (`span`) | none | span neutre |
| 88 | P3 | OK | Aetherix | `backend/app/main.py:183` (`lifespan`) | warning | arrêt de l'app |
| 89 | P3 | OK | Aetherix | `backend/app/main.py:190` (`lifespan`) | warning | arrêt de l'app |
| 90 | P3 | OK | Aetherix | `backend/app/services/rate_limit.py:117` (`close`) | none | fermeture |
| 91 | P3 | OK | Tacet | `app/ingest/worker.py:49` (`sync_external_data`) | none | date illisible |
| 92 | P3 | OK | Tacet | `app/ingest/worker.py:53` (`sync_external_data`) | none | date illisible |
| 93 | P3 | OK | Tacet | `app/ingest/worker.py:72` (`sync_external_data`) | none | date illisible |

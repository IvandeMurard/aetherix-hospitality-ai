# Apaleo MCP — Tool Mapping & F&B Border-Zone Analysis

> **Story:** [HOS-197](https://linear.app/hospitalityagent/issue/HOS-197) (Story 11.1) — Apaleo MCP tools mapping, border zone F&B vs couverture Aetherix
> **Type:** Competitive / defensive analysis — no code
> **Author:** Dev session (BMad Dev)
> **Date:** 2026-06-03
> **Parent decision:** CLAUDE.md → Décision ouverte *"Apaleo Copilot scope F&B — canari à surveiller (01/06/2026)"*
> **Related:** Décision #21 (PascalCase native naming), Décision #1 / #7 (Apaleo bedrock, read-only), [HOS-190](https://linear.app/hospitalityagent/issue/HOS-190) (Composio → natif remapping, Done), [HOS-71](https://linear.app/hospitalityagent/issue/HOS-71) (Aetherix MCP Server v0 → v1)

---

## TL;DR

- Apaleo expose **235 tools MCP natifs** (PascalCase, OAuth2, réponses `{"data": {...}}`) — comptage vérifié en live le 2026-06-03 via `scripts/list_apaleo_tools.py`.
- Aetherix en **consomme 5** : 3 en production (`ListPropertyPerformanceReport`, `ListRevenuesReport`, `ListReservations`) + 2 au probe/validation (`GetProperty`, `ListProperties`). `update_staffing` **n'existe pas** côté Apaleo (Décision #21).
  - *Mise à jour 18/10/2026 (HOS-352)* : `ListRevenuesReport` n'est plus consommé (il rend le total du compte « Revenues », pas le F&B). Occupation **et** revenu F&B net viennent de `ListPropertyPerformanceReport` (`soldCount`, `houseCount`, `outOfOrderCount`, `netFoodAndBeveragesRevenue`). Voir ADR-0006 §9.8.
- **44 tools** constituent la *border zone* F&B : ce qu'Apaleo Copilot pourrait composer pour fabriquer un concurrent F&B interne (services F&B, ordered-services / arrivals reports, occupancy granulaire, time-slices, market segments, group/banquet demand).
- **186 tools** sont *inutilisés* par Aetherix et hors menace F&B (folios, paiements, factures, comptabilité, inventaire, rate plans, policies, admin).
- **Le différenciateur Aetherix n'est pas l'accès aux données — c'est la couche d'intelligence par-dessus** (capture-rate appris, pgvector RAG sur patterns F&B, Prophet + regressors, cold-start meta-learner, mémoire propriétaire). Apaleo expose la *donnée brute* ; Apaleo n'expose **aucune** primitive de forecast covers, de capture-rate, ni de staffing.
- **Reco MCP v1** (§5) : accélérer HOS-71 v1 pour exposer `get_operational_predictions` + `query_cohort_prior` comme primitives *complémentaires* listables sur l'Apaleo Marketplace — se positionner comme la couche F&B-intelligence au-dessus du PMS, pas en concurrence frontale.

---

## AC1 — Source officielle Apaleo MCP

| Élément | Valeur |
|---------|--------|
| Endpoint MCP (autorité primaire, **interrogé en live**) | `https://mcp.apaleo.com/mcp/` |
| Transport | HTTP Streamable (SSE déprécié — cf. Décision ouverte 31/03/2026) |
| Auth | OAuth2 `client_credentials` (`https://identity.apaleo.com/connect/token`), bearer identique à la raw API |
| Protocole MCP négocié | `2025-11-25` (run #2 demo-apaleo.md §6) |
| `list_tools` count | **235** (vérifié 2026-06-03, reproduit run #2 du 2026-05-25) |
| Doc officielle "AI integrations" | <https://apaleo.dev/guides/ai/overview.html> — consultée 2026-06-03 |
| Annonce produit (contexte) | <https://apaleo.com/blog/apaleo-news/apaleo-launches-mcp-server> — *"first PMS MCP server", closed alpha, ~230+ endpoints transformés en tools, OAuth2* |

> **Note de méthode :** la source d'autorité retenue pour le comptage et les noms de tools est le **serveur MCP live lui-même** (`list_tools` sur `mcp.apaleo.com`), pas une page documentaire — Apaleo est en *closed alpha* et la doc publique chiffre "~230–237 endpoints", tandis que le serveur renvoie 235 tools effectifs à cette date. Le mapping ci-dessous est donc reproductible : `python scripts/list_apaleo_tools.py`.

---

## AC2 — Tableau exhaustif des 235 tools (3 catégories)

**Partition vérifiée par script** (`scripts/tmp_classify_apaleo.py`, jeté après génération) : aucun tool en double, aucun omis.

| Catégorie | Count | Part |
|-----------|------:|-----:|
| **Consommés** par Aetherix (post-HOS-190) | **5** | 2,1 % |
| **Border zone F&B** | **44** | 18,7 % |
| **Inutilisés** | **186** | 79,1 % |
| **Total** | **235** | 100 % |

### 2.1 — Consommés (5)

| Tool | Méthode adapter | Usage Aetherix | Réponse |
|------|-----------------|----------------|---------|
| `ListPropertyPerformanceReport` | `ApaleoMCPAdapter.get_occupancy` | Occupancy J (`soldCount`/`houseCount`) | `{"data": {...}}` |
| `ListRevenuesReport` | `ApaleoMCPAdapter.get_revenue` | Revenue pace J / J-7 / J-14 (`grossAmount.amount`) | `{"data": {...}}` |
| `ListReservations` | `ApaleoMCPAdapter.get_historical_data` | Réservations confirmées (proxy demande / training Prophet) | `{"data": {...}}` |
| `GetProperty` | `validate_apaleo_sandbox.py` step 5 | Probe / smoke test connexion MCP | `{"data": {...}}` |
| `ListProperties` | probe / discovery | Énumération properties sandbox | `{"data": {...}}` |

> ⚠️ **`update_staffing` n'existe pas** côté Apaleo MCP — `ApaleoMCPAdapter.update_staffing_in_pms()` retourne `False` (Décision #21 + read-only Phase 0, Décision #7). C'est structurel : **Apaleo n'a aucune primitive staffing.** Voir §3 pour l'implication défensive.

### 2.2 — Border zone F&B (44)

Tools dont la donnée est un *input direct* à un forecast covers / staffing / mise en place — donc ce qu'Apaleo Copilot devrait orchestrer pour fabriquer un concurrent F&B. Regroupés par thème.

**a) Couche "Services" F&B (12)** — chez Apaleo, le petit-déjeuner, le dîner, les extras restauration sont modélisés comme des *services* attachés aux réservations. C'est le cœur de la border zone.
`GetAvailableServices`, `ListServices`, `GetService`, `CountServices`, `CreateService`, `DeleteService`, `ListServiceOffers`, `GetReservationServices`, `GetReservationServiceOffers`, `BookService`, `RemoveServiceFromReservation`, `ListServiceTypes`

**b) Offres réservation (1)**
`GetReservationOffers`

**c) Reports covers / F&B / occupancy ground-truth (8)** — `ListOrderedServicesReport` est le tool le plus dangereux : c'est la *vérité terrain* de la consommation F&B.
`ListOrderedServicesReport`, `ListOrderedServicesReportNSFW`, `ListArrivalsReport`, `ListArrivalsReportNSFW`, `ListPropertyPerformanceReportNSFW`, `ListRevenuesReportNSFW`, `GetBedNightsReportNSFW`, `GetRoomNightsReportNSFW`

**d) Demande réservations / bookings (4)** — proxy covers, hors le `ListReservations` déjà consommé.
`CountReservations`, `GetReservation`, `ListBookings`, `GetBooking`

**e) Disponibilité / occupancy granulaire (3)**
`GetAvailableUnits`, `GetAvailableUnitGroups`, `GetAvailableUnitsForReservation`

**f) Time-slices — granularité intra-journée / par service (4)**
`CreateTimeSliceDefinition`, `DeleteTimeSliceDefinition`, `GetTimeSliceDefinition`, `ListTimeSliceDefinitions`

**g) Market segments — mix de demande (6)**
`CheckMarketSegmentExists`, `CountMarketSegments`, `CreateMarketSegment`, `DeleteMarketSegment`, `GetMarketSegment`, `ListMarketSegments`

**h) Groups / blocks — demande groupe / banquet (6)** — un bloc de 30 chambres = un événement F&B.
`ListGroups`, `GetGroup`, `CountGroups`, `ListBlocks`, `GetBlock`, `CountBlocks`

### 2.3 — Inutilisés (186)

Hors menace F&B : transactionnel, financier, inventaire, admin. Énumération exhaustive (count par domaine ; somme = 186).

| Domaine | Count | Tools |
|---------|------:|-------|
| Folios, charges & allowances | 31 | `BulkMoveCharges`, `CheckFolioExists`, `CloseFolio`, `CorrectFolio`, `CountFolios`, `CreateBulkAllowances`, `CreateChargeAllowance`, `CreateFolio`, `CreateFolioAllowance`, `CreateFolioCancellationFee`, `CreateFolioCharge`, `CreateFolioNoShowFee`, `CreateFolioPayment`, `CreateFolioRefund`, `CreateFolioTransitoryCharge`, `DeleteFolio`, `GetFolio`, `GetFolioPayment`, `GetFolioRefund`, `ListFolioLogs`, `ListFolioPayments`, `ListFolioRefunds`, `ListFolios`, `MoveAllFolioCharges`, `MoveFolioCharges`, `MoveFolioPayments`, `PostFolioCharges`, `ReopenFolio`, `SplitFolioCharge`, `SplitFolioPayment`, `UpdateFolio` |
| Accounting & financial export | 22 | `CheckSubAccountExists`, `CountSubAccounts`, `CreateSubAccount`, `DeleteSubAccount`, `ExportAccounts`, `ExportAccountsDaily`, `ExportAccountsGross`, `GetAccountAggregate`, `GetAccountAggregatePairs`, `GetAccountByNumber`, `GetAccountsAggregate`, `GetSubAccount`, `ListAccountSchema`, `ListChildAccounts`, `ListCurrencies`, `ListExternalAccounts`, `ListGlobalAccounts`, `ListGrossTransactionsReportNSFW`, `ListGuestAccounts`, `ListSubAccounts`, `ListTransactionExportLogs`, `ListVatTypes` |
| Rate plans, rates & offers | 17 | `CheckRatePlanExists`, `CountRatePlans`, `CountRates`, `CreateRatePlan`, `DeleteRatePlan`, `DeleteRatePlans`, `DeleteRates`, `GetRatePlan`, `GetRates`, `ListCorporateCodes`, `ListOfferIndex`, `ListOffers`, `ListPromoCodes`, `ListRatePlanOffers`, `ListRatePlans`, `UpdateRatePlan`, `UpdateRates` |
| Units (inventory write) | 13 | `AssignSpecificUnit`, `AssignUnit`, `CheckUnitExists`, `CountUnits`, `CreateMultipleUnits`, `CreateUnit`, `DeleteUnit`, `GetUnit`, `ListUnits`, `UnassignUnits`, `UpdateMultipleUnits`, `UpdateUnit`, `UpdateUnitsCondition` |
| Invoices | 12 | `CancelInvoice`, `CreateInvoice`, `GetInvoice`, `GetInvoicePdf`, `ListCompanyInvoicesVatReport`, `ListCompanyInvoicesVatReportNSFW`, `ListInvoiceAddresses`, `ListInvoicePreview`, `ListInvoicePreviewPdf`, `ListInvoices`, `PayInvoice`, `UpdateInvoiceAddresses` |
| Cancellation / no-show / capture policies | 10 | `CreateCancellationPolicy`, `CreateNoShowPolicy`, `DeleteCancellationPolicy`, `DeleteNoShowPolicy`, `GetCancellationPolicy`, `GetCapturePolicy`, `GetNoShowPolicy`, `ListCancellationPolicies`, `ListCapturePolicies`, `ListNoShowPolicies` |
| Maintenance & night audit | 10 | `CheckMaintenanceExists`, `CountMaintenances`, `CreateMaintenance`, `CreateMultipleMaintenances`, `DeleteMaintenance`, `GetMaintenance`, `ListMaintenances`, `ListNightAuditLogs`, `RunNightAudit`, `UpdateMaintenance` |
| Properties (admin write) | 9 | `ArchiveProperty`, `CheckPropertyExists`, `CloneProperty`, `CountProperties`, `CreateProperty`, `GetPropertySettings`, `ResetProperty`, `SetPropertyLive`, `UpdateProperty` |
| Blocks (allotment write/lifecycle) | 8 | `AmendBlock`, `CancelBlock`, `CheckBlockExists`, `ConfirmBlock`, `CreateBlock`, `DeleteBlock`, `ReleaseBlock`, `WashBlock` |
| Groups (write/lifecycle) | 4 | `AddReservationToGroup`, `CheckGroupExists`, `CreateGroup`, `DeleteGroup` |
| Unit groups | 8 | `CheckUnitGroupExists`, `CountUnitGroups`, `CreateUnitGroup`, `DeleteUnitGroup`, `GetUnitGroup`, `ListUnitGroups`, `UpdateUnitGroup`, `UpdateUnitGroupAvailability` |
| Payments & refunds | 7 | `CancelPayment`, `CreateAccountPayment`, `CreateAuthPayment`, `CreatePaymentLink`, `CreatePaymentRefund`, `CreateTerminalPayment`, `ListPaymentMethods` |
| City tax | 6 | `AddCityTax`, `CreateCityTax`, `DeleteCityTax`, `GetCityTax`, `ListCityTaxes`, `RemoveCityTax` |
| Unit attributes | 6 | `CheckUnitAttributeExists`, `CreateUnitAttribute`, `DeleteUnitAttribute`, `GetUnitAttribute`, `ListUnitAttributes`, `UpdateUnitAttribute` |
| Reservation write-actions & check-in/out | 9 | `AddReservationToBooking`, `AmendReservation`, `CancelReservation`, `CheckIn`, `CheckOut`, `CreateBooking`, `ListReservationLogs`, `MarkNoShow`, `RevertCheckIn` |
| Companies | 4 | `CreateCompany`, `DeleteCompany`, `GetCompany`, `ListCompanies` |
| Age categories | 4 | `CreateAgeCategory`, `DeleteAgeCategory`, `GetAgeCategory`, `ListAgeCategories` |
| Settings & addresses | 3 | `GetFeatureSettings`, `ListLanguageSettings`, `UpdateLanguageSettings` |
| Reference / lookup | 3 | `ListAllowedValues`, `ListCountries`, `ListSources` |

> **Reconciliation Inutilisés :** 31+22+17+13+12+10+10+9+8+4+8+7+6+6+9+4+4+3+3 = **186**. *(`CreateBooking` rattaché ici aux reservation write-actions : c'est une écriture, hors scope read-only Aetherix.)*

---

## AC3 — Analyse border zone (≥5 tools : a/ ce qu'Apaleo expose · b/ ce qu'Aetherix ajoute · c/ reco positionnement)

### BZ-1 · `ListOrderedServicesReport` / `ListOrderedServicesReportNSFW`
- **a) Apaleo expose :** la liste des *services commandés* (petit-déj, dîner, extras F&B) sur une période — la vérité terrain la plus proche des "covers réellement consommés" disponible nativement.
- **b) Aetherix ajoute :** ce report est *rétrospectif* (ce qui a été consommé). Aetherix le transforme en *prédictif* : capture-rate appris par propriété (base 18 % → 29 % les soirs CL, Décision contexte demo), embeddings pgvector des patterns similaires, blending Prophet + cold-start meta-learner (ADR 0005). Apaleo dit "hier 67 couverts" ; Aetherix dit "demain 74 [68–80] @ 83 %".
- **c) Reco : DIFFÉRENCIATION.** C'est précisément la frontière à surveiller (canari #1). Si Apaleo ajoute un tool `ForecastOrderedServices` ou un report *forward-looking*, la niche se referme. Mitigation : verrouiller le moat sur la *mémoire propriétaire apprise* (capture-rate + feedback loop) qu'un report générique ne peut pas répliquer.

### BZ-2 · Couche Services (`ListServices`, `GetService`, `BookService`, `GetReservationServices`, `ListServiceOffers`…)
- **a) Apaleo expose :** le catalogue de services F&B configurés, leur réservation/attachement à une réservation, les offres de service. CRUD complet.
- **b) Aetherix ajoute :** Aetherix ne gère pas le catalogue — il *raisonne* sur la demande agrégée future de ces services et la traduit en mise en place + staffing (`StaffingService.calculate_recommendation`). La couche Services est un *référentiel* ; Aetherix est un *moteur de décision*.
- **c) Reco : COMPLÉMENT.** Consommer `ListServices`/`GetReservationServices` en lecture pour enrichir le ground-truth covers (granularité par service, ex. dîner vs petit-déj) — upgrade naturel du pipeline post-pilote. À ajouter au backlog adapter (lecture seule, cohérent Décision #7). Ne **pas** toucher `BookService`/`CreateService` (écriture).

### BZ-3 · `ListArrivalsReport` (+NSFW)
- **a) Apaleo expose :** les arrivées prévues par jour — proxy direct des couverts petit-déjeuner J+1 (résidents présents au matin).
- **b) Aetherix ajoute :** conversion arrivées → couverts via capture-rate petit-déj propriétaire + regressors (jour de semaine, événement, météo terrasse). Apaleo donne le dénominateur ; Aetherix donne le taux appris.
- **c) Reco : COMPLÉMENT + ABSTRACTION.** Aetherix abstrait "arrivals + occupancy + reservations" en un seul signal "expected covers". À consommer en lecture pour couvrir le service petit-déjeuner (aujourd'hui le pipeline cible le dîner). Faible coût, fort ROI produit.

### BZ-4 · `ListPropertyPerformanceReport` (occupancy granulaire — déjà consommé, extension surveillée)
- **a) Apaleo expose :** `soldCount`/`houseCount` → occupancy. Déjà consommé par `get_occupancy`. La variante `…NSFW` ouvre potentiellement plus de granularité.
- **b) Aetherix ajoute :** occupancy n'est qu'un *regressor* parmi d'autres dans Prophet ; la valeur Aetherix est la composition multi-signaux (occupancy × capture-rate × events × météo × bookings pace) et l'explainability Claude.
- **c) Reco : ABSTRACTION.** Garder Apaleo comme source occupancy, ne jamais exposer cette donnée brute côté manager — c'est le forecast composé qui est le produit. Risque si Apaleo Copilot fait de l'occupancy un "insight" pré-mâché : rester en amont sur la *décision* (staffing/mise en place), pas sur la *métrique*.

### BZ-5 · Time-slices (`ListTimeSliceDefinitions`, `GetTimeSliceDefinition`…)
- **a) Apaleo expose :** la définition des découpages temporels (tranches tarifaires / par période). Permettrait une occupancy intra-journée.
- **b) Aetherix ajoute :** rien aujourd'hui — mais c'est l'angle d'attaque pour passer d'un forecast "par service" à un forecast "par créneau" (ex. premier vs second service du dîner). Différenciateur futur possible.
- **c) Reco : VEILLE (différenciation potentielle).** Pas de consommation immédiate. Si un pilote demande la granularité intra-service, c'est la brique Apaleo à exploiter avant qu'Apaleo Copilot ne la package.

### BZ-6 · Group / block demand (`ListGroups`, `GetBlock`, `CountBlocks`…)
- **a) Apaleo expose :** les blocs/groupes de réservations (allotments, événements groupe) en lecture.
- **b) Aetherix ajoute :** un bloc de N chambres = un signal de demande F&B banquet/événementiel non capturé par les couverts individuels. Aetherix peut intégrer la demande groupe comme regressor événementiel (au même titre que PredictHQ).
- **c) Reco : COMPLÉMENT (Phase 4+).** Lecture seule, à intégrer quand le scope passe au F&B événementiel/banquet. Hors scope pilote actuel (dîner restaurant), mais c'est un axe d'extension défendable (Apaleo a la donnée groupe, pas l'intelligence de conversion en couverts banquet).

> **Synthèse positionnement :** Apaleo expose la **donnée** (services, reports, occupancy, groupes). Aetherix possède l'**intelligence apprise par propriété** (capture-rate, RAG patterns, meta-learner cold-start, staffing, mise en place, explainability). Aucun des 235 tools n'expose une primitive forecast-covers / capture-rate / staffing — **le moat tient tant que ce gap existe.**

---

## AC4 — Leading indicators (canari Apaleo Copilot → F&B)

Signaux à monitorer mensuellement (synthèse veille). Déclenchent une ré-évaluation de la Décision ouverte si ≥1 vire au rouge.

| # | Indicateur | Quoi surveiller | Source | Seuil d'alerte |
|---|-----------|-----------------|--------|----------------|
| **LI-1** | **Annonces Copilot F&B** | Tout positionnement public Apaleo Copilot sur forecasting / covers / staffing / mise en place | apaleo.com/blog, apaleo.dev changelog, keynotes ITB/HITEC | Une mention explicite "F&B forecast" ou "staffing" |
| **LI-2** | **Nouveaux tools MCP covers/staffing** | Apparition d'un tool type `ForecastOrderedServices`, `GetStaffingRecommendation`, `PredictCovers`, report *forward-looking* | Diff de `list_tools` (re-run mensuel `scripts/list_apaleo_tools.py` → comparer au snapshot 235) | Tout nouveau tool à sémantique prédictive F&B |
| **LI-3** | **Embauches "operations AI" Apaleo** | Postes "AI/ML operations", "F&B intelligence", "revenue/operations data science" | apaleo.com/careers, LinkedIn Apaleo | ≥1 poste ciblant l'optimisation opérationnelle F&B |
| **LI-4** | **Releases Marketplace liées F&B** | Apps F&B forecasting/staffing publiées sur l'Apaleo Marketplace (par Apaleo ou un partenaire premier-party) | apaleo.com/marketplace | Une app F&B forecast first-party ou exclusive |
| **LI-5** | **Extension du report layer** | Passage des reports F&B (`OrderedServices`, `Revenues`) de rétrospectif à prédictif, ou ajout de granularité time-slice native | Diff `list_tools` + doc apaleo.dev | Report avec paramètre horizon futur |

> **Mécanique d'alerte (LI-2/LI-5) :** garder le snapshot des 235 noms (`scripts/list_apaleo_tools.py`) versionné ; un diff mensuel non-vide sur la catégorie border-zone = signal à escalader en session SM.

---

## AC5 — Reco scope MCP v1 Aetherix (lien HOS-71 v0 → v1)

**Contexte :** HOS-71 a shippé le MCP Server v0 (3 tools atomiques, PR #73). Décision #19 cadre v1 (`/mcp/v1/`) : `recall_memory` (scope `memory:read`) + `get_operational_predictions`, v0 maintenu jusqu'au 2026-08-01 (Sunset header). Décision #18 (Track B) ajoute `query_cohort_prior` (cold-start meta-learner, ADR 0005).

**Que shipper, quand, pourquoi — au regard du mapping :**

| Primitive MCP v1 Aetherix | Shipper | Pourquoi (vs mapping Apaleo) |
|---------------------------|---------|------------------------------|
| `get_operational_predictions` (covers + staffing + confidence) | **Phase 3, avant Q4 2026** | Apaleo n'expose **aucun** tool prédictif F&B (§3). C'est *le* trou dans les 235 tools que seul Aetherix comble. Le shipper en MCP-natif = devenir le tool que l'Apaleo Copilot *appelle* plutôt que le concurrent qu'il remplace. |
| `recall_memory` (scope `memory:read`) | **Phase 3** (déjà cadré Décision #19) | Le moat = la mémoire propriétaire apprise (capture-rate, feedback). Aucun report Apaleo ne la réplique. L'exposer en primitive callable verrouille la complémentarité. |
| `query_cohort_prior` (cold-start) | **Phase 3 Track B** (ADR 0005) | Différenciateur cross-property qu'Apaleo (single-property data model) ne peut pas offrir nativement. |

**Reco stratégique (3 mouvements, par ordre de priorité) :**
1. **Accélérer HOS-71 v1 comme défense interop.** Tant qu'Aetherix est *le* MCP tool F&B-prediction listable, Apaleo Copilot a intérêt à l'orchestrer plutôt qu'à le rebâtir. Fenêtre : avant que LI-2/LI-4 ne virent au rouge.
2. **Listing Apaleo Marketplace en position de complément** (pas concurrent) — cf. Décision ouverte mitigation (b). Argument de vente : *"Aetherix runs on one of the two PMS tiers the Anthropic 'AI for Hotel Owners' playbook recommends"* (Décision #21).
3. **Snapshot mensuel `list_tools` comme early-warning** (LI-2/LI-5) intégré à la veille — coût quasi nul, détecte le canari avant l'annonce produit.

**Ce qu'il ne faut PAS shipper en v1 :** aucune primitive d'écriture PMS (reste read-only, Décision #7) ; ne pas dupliquer les tools data Apaleo (occupancy/revenue/reservations) — les *consommer*, pas les ré-exposer. La valeur v1 = la couche intelligence, jamais la donnée brute.

---

## Annexe — Reproductibilité

```bash
# Lister les 235 tools natifs (autorité primaire)
python scripts/list_apaleo_tools.py            # → Total tools: 235

# Re-vérifier la partition 5 / 44 / 186 (script temporaire, non versionné)
# cf. scripts/tmp_classify_apaleo.py — partition asserts == 235
```

Adapter consommateur : `backend/app/services/apaleo_mcp_adapter.py` (mapping Décision #21).
Proxy MCP local Claude Code : `scripts/apaleo_mcp_proxy.py` → `.mcp.json`.

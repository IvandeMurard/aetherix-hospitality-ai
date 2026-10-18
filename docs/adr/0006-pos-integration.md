# ADR 0006 — POS Integration : scope, provider abstraction, cohort impact

> **Status**: Accepted · **Date**: 2026-06-06 · **Author**: Architect (Winston, Opus)
> **⚠️ Amendé 2026-07-31 (§10)** : **§D4 différé** — la table `hotel_cohort_features` sur laquelle il construit n'existe pas, et son socle (ADR-0005 / Hive) est gelé par l'audit. D1, D2, D3, D5-D7 et §9 restent Accepted ; l'ingestion POS reste livrable Phase 4 (5 stories, 19 pts).
> **Phase**: 4 (Scale & Distribution) — blocking pré-requis pour ADR-0008 (graphe de contexte)
> **Linear**: HOS-POS-1 → HOS-POS-6 (à créer par SM Phase 4 kickoff)
> **Implémente**: CLAUDE.md Décision architecturale #23 (à ajouter via cette session)
> **Étend**: ADR 0004 (provider singleton via `lifespan`, pattern `LLMProvider`/`EmbeddingProvider`), ADR 0007 (catégorie `pos_anomaly` forward-compat D1)
> **Articule**: ADR 0005 (cold-start meta-learner — features cohort v2 enrichies POS)
> **Débloque**: ADR 0008 futur (graphe de contexte — schema features cohort matching), open decision "Food waste tracking" (mesure précise via POS items vs forecast)
> **Note historique** : aucun fichier `0006-pos-integration-DRAFT.md` n'existait dans le repo au moment de cette session — l'ADR est rédigé directement en Accepted (sources de contexte = `memory/market_signals_2026Q2.md` §Meuze + `docs/marketing/positioning-snippets.md` H-6 + open-decisions §Actives). La structure Q1-Q4 est reconstruite à partir du brief de session PM 04/06.

---

## 1. Contexte

### 1.1 Trigger métier

Deux triggers convergents semaine du 2026-06-01 :

1. **Meuze.ai** (`memory/market_signals_2026Q2.md` §Meuze) — concurrent F&B le plus proche identifié, *POS-only restaurants/QSR*, revendique federated learning live. Risque pivot hôtels (Accor/Marriott/IHG groupes avec restaurants intégrés). Position défensive Aetherix = *"PMS+POS-aware cross-property intelligence"* (snippet H-6 adopté).
2. **Apaleo border zone F&B** (`docs/competitive/apaleo-mcp-mapping.md`) — Apaleo modélise breakfast/dinner/extras comme `Service` attachés aux réservations. Le `ListOrderedServicesReport` donne déjà un proxy covers — *mais sans granularité item-level, ni outlet non-PMS-linked (brasserie publique, bar lobby, room service).* POS = couche complémentaire indispensable pour la profondeur F&B.

### 1.2 Trigger architecture

ADR-0005 (cold-start meta-learner) **prévoit** `hotel_cohort_features` — coefficients agrégés Prophet + hyperparams calibrés, dérivés exclusivement PMS (occupancy, segment, capacité, saisonnalité). ⚠️ **Cette table n'est pas construite** (ADR-0005 §0, amendement §10) : le raisonnement ci-dessous porte sur la *conception* d'ADR-0005, pas sur un système en place. Ce profil PMS seul est **insuffisant** pour différencier deux hôtels de même profil PMS mais à F&B opposé (e.g. boutique BER 80 chambres breakfast-heavy vs boutique BER 80 chambres dinner-heavy avec brasserie publique). Cohort matching v2 = ajouter features POS-driven.

ADR-0008 futur (graphe de contexte, open decision 04/06/2026) cible un schema `hotel × event × weather × time × outcome` — `outcome` ne peut pas être *"covers PMS-service-derived"* sans granularité item / ticket / time-of-day. POS = pré-requis schema.

### 1.3 Brief PM source

`docs/adr/0006-pos-integration-DRAFT.md` mentionné en open-decisions §Actives (note : non créé dans le repo, reconstruit ici). 4 sous-questions Q1-Q4 reformulées d'après brief session PM 04/06 :

- **Q1** — Quels POS vendors prioritaires pour le pilote Phase 4 ?
- **Q2** — Phase 4 ou Phase 5 pour la livraison initiale ?
- **Q3** — Pattern intégration : adapter dans `app/integrations/` à la Apaleo, OU nouvelle abstraction `POSProvider` Protocol à la `LLMProvider` ?
- **Q4** — Quelles features POS enrichissent `hotel_cohort_features` (ADR-0005 → v2) ?

### 1.4 Goal

Trancher le scope POS (vendors prioritaires, phase, pattern code, impact cohort) avec un livrable v0 maintenable par 1 dev solo, cohérent avec :
- Décision #1 (Claude Sonnet provider principal — pas d'usage LLM côté POS adapter)
- Décision #7 (read-only Phase 0 type — appliqué au POS aussi)
- Décision #9 / #10 (Protocol abstraction + singleton `lifespan`)
- Décision #11 (stratégie démo hybride — `MockPOSAdapter` requis avant ship Lightspeed)
- Décision #21 (convention nommage native — analogue à appliquer pour adapter par vendor)
- Décision #22 (eval-by-design — `pos_anomaly` à populer)

### 1.5 Non-goals (v0 = Phase 4)

- **Write-back POS** (push manning roster vers POS, ajustement menu mix) — Phase 5+. Cohérent Décision #7.
- **Procurement / supplier EDI** (US Foods, Greco-style) — Phase 5 si demand pilot enterprise. `memory/market_signals_2026Q2.md` Meuze table = *"vertical différent (B2B procurement)"*.
- **POS pour STR / Airbnb** (Hostaway, Guesty) — non-MCP, hors hospitality F&B back-of-house.
- **GL reconciliation** (QuickBooks/Xero/NetSuite/R365 à la Meuze) — Phase 4-5, étend agent Receipts, ADR séparé.
- **Choix POS vendor final pour le design partner** — cet ADR donne reco + critères, le pick est PM/SM lors du recrutement design partner pilote Phase 4.

---

## 2. Décisions (Q1-Q4 tranchées)

### D1 (Q1) — Vendors prioritaires : **Tier 1 Lightspeed K-Series + Oracle Micros Simphony, Tier 2 Toast/Square/Tiller, Tier 3 defer**

#### Landscape exhaustif POS hospitality (état marché 2026-Q2)

| Vendor | API maturity | Déploiement EU | ICP hôtels | Integration Apaleo / Mews existante | Tier |
|---|---|---|---|---|---|
| **Lightspeed K-Series** (ex-iKentoo) | ✅ REST moderne, OAuth2, webhooks | ✅ Fort (CH, FR, UK, BE, DE) | ✅ Boutique + indépendants + groupes mid-market | ✅ Mews Marketplace officiel · ✅ Apaleo via partenaire integration | **T1** |
| **Oracle Micros Simphony** | ⚠️ OPERA Cloud + Simphony Cloud API REST, OXI legacy pour on-prem | ✅ Total (Marriott, IHG, Accor enterprise) | ✅ Enterprise + chaînes 50+ properties | ⚠️ Apaleo et Mews supportent Simphony Cloud côté `Service`, pas adapter F&B direct | **T1** |
| **Toast** | ✅ REST moderne, OAuth2, webhooks | ⚠️ US-first, expansion EU 2026 timide | ⚠️ Restaurants US — hôtels rare | ❌ Pas d'intégration Apaleo / Mews officielle | **T2** |
| **Square for Restaurants** | ✅ REST moderne, OAuth2 | ✅ Présent EU (UK, FR, IE) | ⚠️ SMB / boutique restaurants — hôtels rare (cafés intégrés petits BoH) | ❌ Pas d'intégration Apaleo / Mews officielle | **T2** |
| **Tiller** (SumUp) | ✅ REST + GraphQL | ✅ Fort FR/EU SMB | ⚠️ Brasseries + bars + cafés — hôtels boutique FR ponctuel | ⚠️ Pas Mews ni Apaleo natif, mais SumUp ecosystem | **T2** |
| **Revel** | ⚠️ REST, doc moins complète | ⚠️ Faible EU | ⚠️ Mid-market iPad-first US | ❌ Pas Apaleo / Mews | **T3** |
| **TouchBistro** | ⚠️ REST partiel | ❌ Quasi-nul EU | ⚠️ Indépendants US / CA | ❌ Pas Apaleo / Mews | **T3** |
| **CashPad** (Tactill / SumUp) | ⚠️ REST limité | ✅ FR fort | ⚠️ Indépendants FR | ❌ Pas Apaleo / Mews | **T3** |
| **Adyen POS** | ✅ REST moderne | ✅ Fort EU | ⚠️ Plus terminal de paiement que POS F&B complet | ⚠️ Adyen / Apaleo direct au paiement, pas F&B | **T3** |
| **NCR Aloha** | ⚠️ Legacy SOAP, license partner-restricted | ⚠️ Mixte | ⚠️ Restaurants enterprise legacy | ❌ Pas Apaleo / Mews | **T3** |
| **Sage POS** (ex-Loyverse) | ⚠️ REST minimal | ⚠️ EU partiel | ⚠️ SMB | ❌ Pas Apaleo / Mews | **T3** |

#### Critères de sélection appliqués

Pondération adoptée :

1. **Open API REST moderne + OAuth2 read-only** (cohérent Décision #7) — **poids 30%**
2. **Déploiement EU + adoption hôtels (vs restaurants only)** — **poids 25%**
3. **Integration native existante avec Apaleo et/ou Mews** — **poids 20%** (signal compatibilité ICP design partner pilote)
4. **Granularité ticket-item-level + outlet partitioning** — **poids 15%** (nécessaire features cohort v2 D4)
5. **Marketplace / partner program accessible solo founder** — **poids 10%** (signal effort onboarding)

#### Reco Phase 4

**Tier 1 (priorité absolue pilote Phase 4)** :

- **Lightspeed K-Series** = pick #1. Justification :
  - Open API REST + OAuth2 + webhooks = mappable directement au pattern `ApaleoMCPClient` (cf. D3).
  - Adoption EU forte sur le segment boutique hôtels Mews/Apaleo — recouvre l'ICP design partner Phase 3 (`docs/planning/phase-3-pilot-validation.md` A1).
  - Mews Marketplace officiel = signal *"PMS+POS-aware"* (snippet H-6) crédible immédiat.
  - Partner program self-serve (sandbox + clé dev en J+3 ouvré documenté communauté).

- **Oracle Micros Simphony** = pick #2 conditionnel. Justification :
  - Incontournable pour traction enterprise (Marriott, IHG, Accor groupes — chemin upmarket post-pilote).
  - Effort API ≈ 3× Lightspeed (Cloud API + OXI legacy mix selon propriété).
  - **Gate explicite** : ne pas démarrer adapter Simphony tant que pilote Lightspeed n'a pas validé `MAPE_with_pos ≤ MAPE_pms_only - 1pt` sur ≥ 1 propriété (cf. DoD §6).

**Tier 2 (defer Phase 4 late ou Phase 5)** :

- **Toast / Square / Tiller** — backlog. Tiller a un avantage local FR si un design partner FR boutique apparaît tôt Phase 4 ; sinon ouverture sur demande.

**Tier 3 (skip sauf demand pilote explicite)** :

- Revel, TouchBistro, CashPad, NCR Aloha, Sage, Adyen POS, autres.

**Rejeté** :

- *"Un adapter générique CSV / SFTP file-drop"* en lieu d'API native — viable comme fallback Phase 4 stretch, **pas** prioritaire car coupe la boucle agentic (latence batch quotidien, pas de webhook). Référence : Meuze Steal Table line 1 (`memory/market_signals_2026Q2.md`).

### D2 (Q2) — Phase : **Phase 4 confirmé, pas Phase 5**

**Phase 4 = oui** car :

- Pré-requis bloquant ADR-0008 (graphe de contexte, open decision 04/06/2026 §Graphe — *"cadrage POS tranché"*).
- Snippet H-6 *"PMS+POS-aware cross-property intelligence"* déjà adopté publiquement — sans ship Phase 4, narrative décrédibilisée si Meuze pivote hôtels d'ici Q4 2026 (`market_signals_2026Q2.md` §Triggers à monitorer).
- Cohort matching v2 (D4) débloque Day-1 unlock plus crédible — alignement Federated Hive narrative Phase 4 ship (resolved 04/06/2026).
- Food waste tracking (open decision Phase 4 vs Phase 5) — Option B *"intégrer POS data pour mesure précise vs juste predicted"* devient livrable dès Phase 4 si POS shipped.

**Phase 5 = non** car :

- Repousser POS à Phase 5 = laisser fenêtre 9-12 mois supplémentaire à Meuze pour pivoter hôtels.
- Phase 5 (Agentic Hospitality Mesh, `docs/context/vision-future.md`) suppose POS déjà acquis comme source data.

**Calendrier détaillé** :

| Sub-phase | Livrable | Lien story |
|---|---|---|
| Phase 4.0 (kickoff) | `MockPOSAdapter` + Protocol + schema migration | P4-POS-1, P4-POS-2 |
| Phase 4.1 | `LightspeedKSeriesAdapter` v1 read-only sandbox | P4-POS-3 |
| Phase 4.2 | Cohort features v2 + LOO validation | P4-POS-5 |
| Phase 4.3 | `pos_anomaly` golden scenarios + eval gate | P4-POS-6 |
| Phase 4.4 (conditionnel) | `OracleMicrosSimphonyAdapter` v1 stub | P4-POS-4 |

### D3 (Q3) — Pattern : **nouvelle abstraction `POSProvider` Protocol + un adapter par vendor, pas un single MCP client générique**

#### Décision

Créer `backend/app/providers/pos/` qui suit **strictement** le pattern Décision #9 / #10 (`LLMProvider` Protocol, factory `lru_cache` + singleton `lifespan`) :

```
backend/app/providers/pos/
├── __init__.py                  — re-export public API
├── base.py                      — Protocol POSProvider + dataclasses (POSTransaction, POSItem, POSOutlet)
├── factory.py                   — get_pos_provider() singleton, env-driven
├── mock_adapter.py              — MockPOSAdapter (génère depuis Apaleo Services + jitter — bridge Décision #11 démo hybride)
├── lightspeed_kseries.py        — LightspeedKSeriesAdapter (T1 ship Phase 4.1)
└── oracle_micros_simphony.py    — OracleMicrosSimphonyAdapter (T1 conditionnel Phase 4.4)
```

**Et un layer adapter par vendor pour la logique métier I/O** — analogue strict à `ApaleoMCPAdapter` (cf. `backend/app/integrations/apaleo_mcp_client.py`) :
- Auth (OAuth2 ou clé statique selon vendor)
- HTTP transport (httpx async, retry, timeout)
- Mapping vendor-native payload → schema unifié `pos_transaction` (D4)
- Write-guard cohérent Décision #7 : `_is_readonly_mode()` + raise `POSWriteBlockedError` sur tool list write — réutilise pattern `ApaleoWriteBlockedError`

#### Justification

**Pourquoi Protocol abstraction (et pas extension `app/integrations/`)** :

- 3+ vendors prévus (Lightspeed, Micros, optionnellement Toast/Tiller) — collection vs vendor unique Apaleo.
- Décision #9 *"Multi-LLM via `LLMProvider` abstrait"* est la jurisprudence de référence — *"swap Claude → Gemini → GPT sans réécriture"*. Le swap Lightspeed → Micros doit suivre la même invariant.
- Cohort matching v2 (D4) consomme **un** schema unifié `pos_transaction` — l'agnosticisme vendor est invariant produit, pas un détail intégration.
- Future graphe de contexte ADR-0008 — node `outlet × ticket × time` doit être vendor-agnostique sinon explosion combinatoire.

**Pourquoi pas un single MCP client générique POS** :

- Aucun POS hospitality n'expose actuellement un MCP Server natif (vérification 2026-06-06 — Lightspeed, Micros, Toast = REST/OAuth2, pas MCP).
- Construire un MCP server *côté Aetherix* qui wrappe un POS = anti-pattern (`docs/competitive/apaleo-mcp-mapping.md` reco MCP v1 — *"se positionner comme couche F&B-intelligence au-dessus du PMS, pas en concurrence frontale"*).
- À reconsidérer Phase 5 si un vendor POS annonce MCP natif (canari à monitorer).

**Pourquoi pas une refactorisation de `app/integrations/` à la Apaleo** :

- `app/integrations/apaleo*.py` = pattern simple (1 vendor, 1 client wrapping MCP).
- POS = multi-vendor avec une frontière agentic forte → mérite sa propre couche `providers/`.
- Le naming `providers` = "swappable runtime selon env / tenant" — exactement le cas POS (un tenant Aetherix peut être Lightspeed, un autre Micros).

#### Read-only enforcement (D3-bis)

Cohérent Décision #7 :

- **Phase 4 = read-only par défaut** : flag env `POS_READONLY=true` (analogue `APALEO_READONLY`). Tools de la liste write_tools (`PostTransaction`, `VoidItem`, `RefundPayment`, etc.) raise `POSWriteBlockedError` avant network call.
- Liste write_tools versionnée dans `backend/app/providers/pos/write_tools_registry.py` par vendor (pattern Décision #21 — convention nommage native par adapter).
- Activation writes Phase 5+ uniquement après ADR séparé + validation pilote read-only ≥ 90j.

#### Rejeté

- **Un mega-client multi-vendor** (one class `POSClient` qui switch sur `pos_provider` field) — viole single-responsibility, rend tests adapters dépendants entre vendors, complique évolutivité Phase 5.
- **Generic MCP wrapper côté Aetherix** — over-engineering Phase 4, gain net non démontré.
- **Direct usage `app/integrations/` sans Protocol** — pas swappable runtime, casse cohort matching v2 si pilote change vendor.

### D4 (Q4) — Impact ADR-0005 : **promouvoir `hotel_cohort_features` → v2 avec 3 features POS-driven (item-mix, ticket-size, time-of-day)**

#### Décision

Étendre `hotel_cohort_features` table (ADR-0005 — `Resolved` open decisions 28/05/2026) avec 3 nouvelles features POS-driven dans une **table sœur** `hotel_cohort_features_pos` (FK 1:1 `cohort_id`), opt-in tenant (tenant sans POS connecté → features v1 only).

Pourquoi table sœur et pas extension de la table v1 : sépare le contract LOO ADR-0005 v1 du contract v2 — un tenant PMS-only continue à matcher sur features v1 sans NULL pollution, un tenant PMS+POS bénéficie de cohort matching enrichi.

**Features POS-driven (cohort matching v2)** :

| Feature | Définition | Type | Source POS | Aggregation window |
|---|---|---|---|---|
| `item_category_mix_distribution` | Distribution % par catégorie F&B (breakfast hot / breakfast cold / lunch main / dinner main / wine / cocktail / non-alcoholic / room-service / banquet) | JSONB (Dirichlet 9-dim) | `POSItem.category` | 90j rolling |
| `ticket_size_distribution` | Médiane / p25 / p50 / p75 / p95 ticket gross_amount (€) par service slot | JSONB (per service) | `POSTransaction.gross_amount` | 90j rolling |
| `time_of_day_intensity` | Covers histogram 24h × 7j (168 buckets) — normalisé par occupancy | float[168] | `POSTransaction.opened_at` | 90j rolling, decay 0.95 weekly |

**Pourquoi ces 3 features et pas plus** :

- **Item mix** discrimine boutique breakfast-heavy vs brasserie dinner-heavy — exactly le scénario qui casse cohort v1 PMS-only (cf. §1.2).
- **Ticket size** discrimine luxury vs budget — invariant pricing complémentaire à `segment` PMS.
- **Time-of-day** discrimine resort (peak dinner 21h) vs business hotel (peak breakfast 7h + dinner 19h) — invariant pace orthogonal à `occupancy`.
- **Pas d'autres features** Phase 4 → respect du *"6 stories ≈ 24 points"* (cf. §5). Extensions (payment-method-mix, item-modifier-density, void-rate) = Phase 5 si LOO Phase 4 démontre besoin.

#### Cohort matching v2 algorithme

ADR-0005 v1 = *cohort matching hybride (hard rules + embedding cosine)* sur features PMS.

v2 = **late-fusion blending** :
1. Hard rules (geo + capacity bucket + segment) — identique v1.
2. Embedding cosine sur features PMS — identique v1, pondération α (calibré pilote, default 0.5).
3. **Nouveau** : embedding cosine sur features POS (Mistral 1024d sur JSON aplati) — pondération β = 1 - α si POS dispo, β = 0 sinon.
4. Score final = α × cos_pms + β × cos_pos.
5. Hard cutoff cohort size : top-5 cosine après hard rules.

**Gate runtime (analogue ADR-0005)** :
- Auto-disable v2 si Day-7 MAPE sur tenant POS > MAPE v1 tenant équivalent sans POS — fallback v1 + alert.
- Distribution shift sur features POS détecté → eval gate Décision #22 alarme `WARN`/`FAIL` selon KS / Wasserstein / PSI.

#### MCP tool exposé

Étendre `query_cohort_prior` (ADR-0005) avec param optionnel `include_pos_features: bool = True`. Backward-compatible.

### D5 (annexe — schema unifié `pos_transaction`)

#### DDL Supabase

```sql
-- migration: pos_integration_v0.sql
-- Phase 4, story P4-POS-2

CREATE TYPE pos_provider AS ENUM (
    'mock',
    'lightspeed_kseries',
    'oracle_micros_simphony',
    'toast',
    'square_restaurants',
    'tiller'
);

CREATE TYPE pos_service_slot AS ENUM (
    'breakfast',
    'brunch',
    'lunch',
    'afternoon',
    'dinner',
    'late_night',
    'bar',
    'room_service',
    'banquet'
);

CREATE TABLE pos_outlet (
    outlet_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    hotel_id UUID NOT NULL REFERENCES hotel(hotel_id) ON DELETE CASCADE,
    pos_provider pos_provider NOT NULL,
    vendor_outlet_id TEXT NOT NULL,        -- vendor-side stable id
    name TEXT NOT NULL,                    -- e.g. "Brasserie", "Bar Lobby", "Petit-déj"
    is_pms_linked BOOLEAN NOT NULL DEFAULT FALSE,
    timezone TEXT NOT NULL DEFAULT 'Europe/Paris',
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (hotel_id, pos_provider, vendor_outlet_id)
);

CREATE TABLE pos_transaction (
    transaction_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    hotel_id UUID NOT NULL REFERENCES hotel(hotel_id) ON DELETE CASCADE,
    outlet_id UUID NOT NULL REFERENCES pos_outlet(outlet_id) ON DELETE CASCADE,
    pos_provider pos_provider NOT NULL,    -- redondant denormalisé pour query speed
    vendor_transaction_id TEXT NOT NULL,   -- vendor-side stable id (idempotence)
    opened_at TIMESTAMPTZ NOT NULL,
    closed_at TIMESTAMPTZ,                 -- NULL si open ticket
    service_slot pos_service_slot NOT NULL,
    cover_count INTEGER NOT NULL DEFAULT 1,
    cover_source TEXT NOT NULL DEFAULT 'pos_pos_count',  -- pos_pos_count | pms_service_count | manual_input
    gross_amount_cents INTEGER NOT NULL,   -- € cents
    vat_amount_cents INTEGER NOT NULL DEFAULT 0,
    currency CHAR(3) NOT NULL DEFAULT 'EUR',
    payment_method TEXT,                   -- card / cash / room_charge / voucher / split
    linked_reservation_id TEXT,            -- Apaleo / Mews reservation_id si room_charge ou linked
    raw_payload JSONB,                     -- vendor-native for audit / debug
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (pos_provider, vendor_transaction_id)
);

CREATE INDEX idx_pos_tx_hotel_closed ON pos_transaction (hotel_id, closed_at DESC);
CREATE INDEX idx_pos_tx_outlet_service ON pos_transaction (outlet_id, service_slot, closed_at DESC);

CREATE TABLE pos_item (
    item_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    transaction_id UUID NOT NULL REFERENCES pos_transaction(transaction_id) ON DELETE CASCADE,
    vendor_item_id TEXT NOT NULL,
    name TEXT NOT NULL,                    -- e.g. "Croissant", "Côte de bœuf 800g"
    category TEXT NOT NULL,                -- breakfast_hot | breakfast_cold | lunch_main | ... (free text Phase 4, taxonomy Phase 5)
    quantity NUMERIC(10,3) NOT NULL,
    gross_amount_cents INTEGER NOT NULL,
    modifiers JSONB,                       -- vendor-native modifier list (e.g. {"size": "L", "no_onion": true})
    is_void BOOLEAN NOT NULL DEFAULT FALSE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX idx_pos_item_tx ON pos_item (transaction_id);
CREATE INDEX idx_pos_item_category ON pos_item (category);

-- RLS — cohérent pattern Décision #16 + apaleo
ALTER TABLE pos_outlet ENABLE ROW LEVEL SECURITY;
ALTER TABLE pos_transaction ENABLE ROW LEVEL SECURITY;
ALTER TABLE pos_item ENABLE ROW LEVEL SECURITY;

CREATE POLICY pos_outlet_tenant ON pos_outlet
    USING (hotel_id IN (SELECT hotel_id FROM tenant_hotel WHERE tenant_id = current_setting('app.tenant_id')::uuid));

CREATE POLICY pos_tx_tenant ON pos_transaction
    USING (hotel_id IN (SELECT hotel_id FROM tenant_hotel WHERE tenant_id = current_setting('app.tenant_id')::uuid));

CREATE POLICY pos_item_tenant ON pos_item
    USING (transaction_id IN (SELECT transaction_id FROM pos_transaction
                              WHERE hotel_id IN (SELECT hotel_id FROM tenant_hotel WHERE tenant_id = current_setting('app.tenant_id')::uuid)));

-- Cohort features v2 (D4) — table sœur
CREATE TABLE hotel_cohort_features_pos (
    cohort_id UUID PRIMARY KEY REFERENCES hotel_cohort_features(cohort_id) ON DELETE CASCADE,
    item_category_mix_distribution JSONB NOT NULL,    -- Dirichlet 9-dim
    ticket_size_distribution JSONB NOT NULL,          -- per service slot, quantiles
    time_of_day_intensity REAL[] NOT NULL,            -- 168 floats (24h × 7j)
    aggregation_window_start DATE NOT NULL,
    aggregation_window_end DATE NOT NULL,
    pos_provider pos_provider NOT NULL,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    CHECK (array_length(time_of_day_intensity, 1) = 168)
);

CREATE INDEX idx_cohort_pos_provider ON hotel_cohort_features_pos (pos_provider);
```

#### Validation contre `check_schema_drift.py` (Décision #16)

L'ORM SQLAlchemy équivalent (`backend/app/models/pos.py` — à créer Story P4-POS-2) doit miroir exactement ce DDL. Pas d'exception `schema_drift_ignore.json`. Migration Alembic versioned, pas inline.

### D6 (annexe — `POSProvider` Protocol)

```python
# backend/app/providers/pos/base.py
"""Protocol definition for POS providers (read-only Phase 4)."""
from __future__ import annotations
from dataclasses import dataclass
from datetime import date, datetime
from enum import Enum
from typing import Protocol, runtime_checkable


class POSServiceSlot(str, Enum):
    BREAKFAST = "breakfast"
    BRUNCH = "brunch"
    LUNCH = "lunch"
    AFTERNOON = "afternoon"
    DINNER = "dinner"
    LATE_NIGHT = "late_night"
    BAR = "bar"
    ROOM_SERVICE = "room_service"
    BANQUET = "banquet"


class POSProviderName(str, Enum):
    MOCK = "mock"
    LIGHTSPEED_KSERIES = "lightspeed_kseries"
    ORACLE_MICROS_SIMPHONY = "oracle_micros_simphony"
    TOAST = "toast"
    SQUARE_RESTAURANTS = "square_restaurants"
    TILLER = "tiller"


@dataclass(slots=True, frozen=True)
class POSItem:
    vendor_item_id: str
    name: str
    category: str
    quantity: float
    gross_amount_cents: int
    modifiers: dict | None = None
    is_void: bool = False


@dataclass(slots=True, frozen=True)
class POSTransaction:
    vendor_transaction_id: str
    outlet_vendor_id: str
    opened_at: datetime
    closed_at: datetime | None
    service_slot: POSServiceSlot
    cover_count: int
    cover_source: str           # "pos_pos_count" | "pms_service_count" | "manual_input"
    gross_amount_cents: int
    vat_amount_cents: int
    currency: str
    payment_method: str | None
    linked_reservation_id: str | None
    items: list[POSItem]
    raw_payload: dict | None = None


@dataclass(slots=True, frozen=True)
class POSOutlet:
    vendor_outlet_id: str
    name: str
    is_pms_linked: bool
    timezone: str


class POSWriteBlockedError(RuntimeError):
    """Write op attempted while POS_READONLY mode active (Phase 4 = read-only)."""


@runtime_checkable
class POSProvider(Protocol):
    """Minimal interface for POS providers — read-only Phase 4 (Décision #7).

    Concrete implementations:
        - MockPOSAdapter (Décision #11, démo hybride)
        - LightspeedKSeriesAdapter (T1 ship Phase 4.1)
        - OracleMicrosSimphonyAdapter (T1 conditionnel Phase 4.4)
    """

    @property
    def provider_name(self) -> POSProviderName:
        ...

    @property
    def is_configured(self) -> bool:
        """True when all credentials present + sandbox accessible."""
        ...

    async def list_outlets(self, hotel_vendor_id: str) -> list[POSOutlet]:
        """Discovery — returns outlets attached to the hotel-side vendor account."""
        ...

    async def fetch_transactions(
        self,
        hotel_vendor_id: str,
        *,
        date_from: date,
        date_to: date,
        outlet_vendor_ids: list[str] | None = None,
    ) -> list[POSTransaction]:
        """Read-only — returns closed transactions in [date_from, date_to].

        Implementations MUST raise POSWriteBlockedError if invoked with a
        write-intent tool name (Phase 4 invariant).
        """
        ...

    async def aclose(self) -> None:
        """Lifecycle hook (Décision #10 lifespan)."""
        ...
```

#### Adapter stub `MockPOSAdapter` (Phase 4.0)

Génère des transactions depuis Apaleo `ListOrderedServicesReport` (proxy covers) + jitter item-level synthetic, scaffold pour Story P4-POS-1. Aligné Décision #11 stratégie démo hybride.

```python
# backend/app/providers/pos/mock_adapter.py — sketch
class MockPOSAdapter:
    provider_name = POSProviderName.MOCK
    is_configured = True

    async def fetch_transactions(self, hotel_vendor_id, *, date_from, date_to, outlet_vendor_ids=None):
        # 1. Pull Apaleo ListOrderedServicesReport via ApaleoMCPAdapter.
        # 2. Map services → POSServiceSlot.
        # 3. Synthesize 1-N items per service with realistic price jitter (€ Beta distribution).
        # 4. Return list[POSTransaction].
        ...
```

#### Adapter stub `LightspeedKSeriesAdapter` (Phase 4.1)

```python
# backend/app/providers/pos/lightspeed_kseries.py — sketch
class LightspeedKSeriesAdapter:
    provider_name = POSProviderName.LIGHTSPEED_KSERIES

    def __init__(self, client_id: str, client_secret: str, base_url: str = "https://api.lightspeed.app"):
        self._auth = LightspeedOAuth2(client_id, client_secret)
        self._http = httpx.AsyncClient(base_url=base_url, timeout=15)

    @property
    def is_configured(self) -> bool:
        return self._auth.is_configured

    async def fetch_transactions(self, hotel_vendor_id, *, date_from, date_to, outlet_vendor_ids=None):
        token = await self._auth.get_token()
        # GET /v1/businesses/{hotel_vendor_id}/receipts?closedAtMin=...&closedAtMax=...
        # paginate, map to POSTransaction.
        ...

    async def aclose(self):
        await self._http.aclose()
```

#### Factory (D6-bis, cohérent Décision #10)

```python
# backend/app/providers/pos/factory.py
from functools import lru_cache
import os
from app.providers.pos.base import POSProvider, POSProviderName


@lru_cache(maxsize=1)
def get_pos_provider() -> POSProvider:
    backend = os.getenv("POS_BACKEND", "mock").lower()
    if backend == POSProviderName.LIGHTSPEED_KSERIES.value:
        from app.providers.pos.lightspeed_kseries import LightspeedKSeriesAdapter
        return LightspeedKSeriesAdapter(
            client_id=os.getenv("LIGHTSPEED_CLIENT_ID", ""),
            client_secret=os.getenv("LIGHTSPEED_CLIENT_SECRET", ""),
        )
    if backend == POSProviderName.ORACLE_MICROS_SIMPHONY.value:
        from app.providers.pos.oracle_micros_simphony import OracleMicrosSimphonyAdapter
        return OracleMicrosSimphonyAdapter(
            tenant_id=os.getenv("MICROS_TENANT_ID", ""),
            client_id=os.getenv("MICROS_CLIENT_ID", ""),
            client_secret=os.getenv("MICROS_CLIENT_SECRET", ""),
        )
    from app.providers.pos.mock_adapter import MockPOSAdapter
    return MockPOSAdapter()
```

Wire-up `lifespan` FastAPI à étendre dans `backend/app/main.py` :
- `app.state.pos = get_pos_provider()`
- `on_shutdown` : `await app.state.pos.aclose()`

#### Variables d'environnement nouvelles

Ajouter à CLAUDE.md §Variables d'environnement après cette session :

```
POS_BACKEND               — "mock" (défaut) | "lightspeed_kseries" | "oracle_micros_simphony" | "toast" | ...
POS_READONLY              — "true" (défaut Phase 4) | "false" (Phase 5+ après ADR séparé)
LIGHTSPEED_CLIENT_ID      — OAuth2 — Phase 4.1
LIGHTSPEED_CLIENT_SECRET  — OAuth2 — Phase 4.1
MICROS_TENANT_ID          — Oracle Hospitality tenant — Phase 4.4 conditionnel
MICROS_CLIENT_ID          — OAuth2 — Phase 4.4 conditionnel
MICROS_CLIENT_SECRET      — OAuth2 — Phase 4.4 conditionnel
```

### D7 (annexe — intégration eval gate Décision #22)

#### `pos_anomaly` category — populate plan

ADR-0007 D1 a réservé `pos_anomaly` avec 0 scenario forward-compat (`{"schema_version":"1.0.0","id":"pos-anomaly-placeholder","category":"pos_anomaly","layer":"forecast","created_at":"2026-06-04","author":"ivan","input":{},"expected":{},"failure_trigger":"PLACEHOLDER — Phase 4 ADR-0006","notes":"Forward-compat structure, pas de logique Phase 3"}`).

**Plan Phase 4** (Story P4-POS-6) — ajouter **min 8 scenarios** dans `eval/golden_dataset.jsonl` :

| Scenario id | Sub-category | Failure trigger candidat |
|---|---|---|
| `pos-cover-mismatch-001` | PMS service count vs POS cover count divergence > 15% | Forecast covers MAPE > 15% post-POS-fusion |
| `pos-late-ticket-002` | Ticket `closed_at` >> `opened_at` (table 4h+ ouverte) | Anomaly detection score > 0.7 |
| `pos-void-spike-003` | Item void rate > 8% sur shift (vs baseline 1-2%) | Recommendation includes void anomaly |
| `pos-item-mix-shift-004` | Item category distribution KL-divergence > 0.3 vs 30j prior | Distribution shift `WARN` triggered |
| `pos-outlet-offline-005` | Outlet flat 0 covers J vs J-7 (POS feed dropped) | Abstention sentinel `AgentAbstention(reason="pos_data_gap")` |
| `pos-ticket-size-tail-006` | p95 ticket > 3× median 90j (banquet privé off-system détecté) | Cohort prior NOT applied — manual confirmation |
| `pos-room-charge-orphan-007` | `linked_reservation_id` NULL sur room_charge payment_method | Reconciliation flag in receipt |
| `pos-modifier-explosion-008` | Item.modifiers cardinality > 10 (menu glitch / parser bug) | Parser confidence drops, manual flag |

**Failure thresholds POS** (à ajouter `eval/FAILURE_THRESHOLDS.md` Phase 4) :
- POS adapter latency p95 < 800ms par fetch (analogue MCP SLO).
- POS-derived cover count parity vs PMS service count : delta médian < 10% sur 90j.
- POS distribution shift : KS feature `item_category_mix` > 0.15 → `WARN`, > 0.25 → `FAIL`.

#### Eval coverage CI gate

Story P4-POS-6 enforce `scripts/ci/check_eval_coverage.py` :
- Touche `app/providers/pos/*` → require `pos_anomaly` scenario count ≥ 5 dans golden dataset.
- Override possible via label PR `eval-exempt` uniquement pour refactor pur (cohérent Décision #22).

---

## 3. Story breakdown Phase 4 (POS-1 → POS-6)

Cohérent format `docs/planning/phase-3-pilot-validation.md` Track A. Linear IDs à créer SM kickoff Phase 4.

| Story | Title | Effort | Dépend de |
|---|---|---|---|
| **P4-POS-1** | `POSProvider` Protocol + dataclasses + factory + `MockPOSAdapter` (génère depuis Apaleo Services) + lifespan wire-up | 3 | — |
| **P4-POS-2** | Schema migration Alembic `pos_integration_v0.sql` (DDL §D5) + ORM SQLAlchemy + RLS test + `check_schema_drift.py` green | 3 | P4-POS-1 |
| **P4-POS-3** | `LightspeedKSeriesAdapter` v1 read-only — OAuth2 + pagination + mapping payload → schema + write-guard + tests sandbox | 5 | P4-POS-2 |
| **P4-POS-4** | `OracleMicrosSimphonyAdapter` v1 stub conditionnel (gate : pilote Lightspeed validé MAPE -1pt) — OPERA Cloud Simphony API REST | 5 | P4-POS-3 + gate |
| ~~**P4-POS-5**~~ | ~~`hotel_cohort_features_pos` table + worker quotidien aggregation + late-fusion blending dans `query_cohort_prior` + LOO validation ≥ 2 sandbox properties~~ | ~~5~~ | **⛔ HORS PÉRIMÈTRE PHASE 4** — §D4 différé (§10). Précondition : gel Hive levé + ADR-0005 D1-D5 construits + D7 exécuté. La DDL `hotel_cohort_features_pos` sort de `pos_integration_v0.sql` et part avec cette story. |
| **P4-POS-6** | `pos_anomaly` ≥ 8 scenarios `eval/golden_dataset.jsonl` + `FAILURE_THRESHOLDS.md` POS section + `check_eval_coverage.py` enforce (Décision #22) | 3 | P4-POS-3 |

**Total** : **5 stories, 19 points** (amendement §10 — P4-POS-5 retirée), ~5 sprint-weeks single-dev. P4-POS-4 parallélisable post-pilote Lightspeed.

**Pré-requis externes** : compte sandbox Lightspeed dev + cred (PM/Ivan, J-15 avant kickoff P4-POS-3 — partner program self-serve J+3 ouvré confirmé).

---

## 4. Risques et mitigations

| ID | Risque | Probabilité | Sévérité | Mitigation |
|---|---|---|---|---|
| **R1** | Effort Oracle Micros (legacy OXI + Cloud mix) ≫ estimation 5pts | Moyenne | Sévère (calendrier Phase 4) | Gate explicite §D1 — Micros conditionnel post-validation Lightspeed. Adapter stub seulement Phase 4.4, full ship reporté Phase 5 si effort réel > 8pts. |
| **R2** | PII dans `POSItem.name` ou `modifiers` (guest name dans ticket comments) | Moyenne | Sévère (RGPD) | Pipeline sanitisation Haiku (réutilise pattern P2-4) sur `raw_payload` avant insert + RLS strict (cohérent Décision #16 + ADR-0007 D5). Audit colonnes nullable. |
| **R3** | Cover count POS ≠ Cover count PMS Apaleo `ListOrderedServicesReport` (divergence > 15%) | **Élevée** (structurel — POS compte covers entrés par serveur, PMS compte services facturés) | Modérée | Field `cover_source` (`pos_pos_count` / `pms_service_count` / `manual_input`) + reconciliation report quotidien + scenario `pos-cover-mismatch-001` golden dataset. Cohort matching v2 utilise `cover_source = 'pos_pos_count'` prioritairement. |
| **R4** | Meuze pivote hôtels avant ship Aetherix POS Phase 4 | Moyenne | Sévère (positioning) | (a) Narrative *"PMS-PRIMARY + POS-aware"* (snippet H-6) ancrée dans landing + Apaleo Marketplace listing dès Phase 3 ; (b) monitoring trigger *"Meuze pivot hôtels"* déjà actif (`market_signals_2026Q2.md` §Triggers) ; (c) Phase 4 P4-POS-1+2+3 = MVP démontrable dans deck pilote avant ship complet. |
| **R5** | Apaleo Service layer suffit déjà pour proxy covers — overbuild POS si pilote tarde | Faible | Modérée | `MockPOSAdapter` Phase 4.0 = bridge — dérive covers depuis Apaleo Services + jitter item-level pour prototyper cohort v2 sans dépendance vendor POS. Cohérent Décision #11 stratégie démo hybride. Validation cohort v2 LOO (Story P4-POS-5) sur Mock avant cred Lightspeed = découple. |
| **R6** | Vendor change tenant en cours de pilote (un design partner switch Lightspeed → Micros) | Faible | Modérée | Protocol abstraction §D3 = swap factory env-driven sans réécriture business logic. `pos_provider` discriminator en table = re-ingestion possible avec idempotence (`UNIQUE (pos_provider, vendor_transaction_id)`). |
| **R7** | Distribution shift sur features POS (saison touristique → menu mix change) faux-positif `FAIL` eval gate | Moyenne | Faible | Decay 0.95 weekly sur `time_of_day_intensity` + window glissante 90j sur `item_category_mix` = absorbe drift saisonnier graduel. Tuning seuils KS/PSI Story P4-POS-6 (cohérent ADR-0007 D5 cascade). |
| **R8** | Apaleo annonce Service-level forecast tool (Copilot étend F&B) — POS scope Aetherix redondant | Faible | Sévère (canari Apaleo Copilot, `open-decisions.md` §Apaleo Copilot scope) | POS = couche complémentaire ATTACHÉE au pilier `outlet × ticket × time` granulaire — Apaleo ne donnera *jamais* l'item-level (ce n'est pas leur domaine de modélisation). Différenciation structurelle. |

---

## 5. Sécurité & data sovereignty

- **Read-only Phase 4** : `POS_READONLY=true` default + `POSWriteBlockedError` (analogue `ApaleoWriteBlockedError`). Cohérent Décision #7.
- **RLS** : 3 nouvelles policies `pos_outlet_tenant`, `pos_tx_tenant`, `pos_item_tenant` — same pattern test Décision #16.
- **Tenant isolation** : Federated Hive narrative (snippet H-7) — *"raw data stays in your tenant, operational patterns travel anonymized"*. Cohort features v2 table = aggregated/anonymized, jamais de `vendor_transaction_id` cross-tenant.
- **PII** : sanitisation Haiku sur `raw_payload` avant insert (réutilise pattern P2-4 receipts). `POSItem.name` / `modifiers` audit pour leak guest name → flag dataset golden.
- **OAuth2 secrets** : Phase 4 = `flyctl secrets set LIGHTSPEED_CLIENT_SECRET` (cohérent Décision #17). Jamais commités, jamais loggés.
- **Audit log** : chaque `fetch_transactions` call → `agent_action_log` (ADR-0003) + observabilité dashboard.

---

## 6. Definition of Done — ADR-0006

**Architectural DoD (cette session)** :

- [x] §1 contexte écrit (triggers métier + architecture + brief PM)
- [x] §2 D1-D4 tranchés (vendors, phase, pattern, cohort impact)
- [x] §2 D5-D7 annexes spec (schema DDL, Protocol code, eval integration)
- [x] §3 story breakdown 6 stories, 24 points
- [x] §4 8 risques + mitigations chiffrées
- [x] §5 security checklist read-only + RLS + PII
- [x] §6 DoD opérationnel ci-dessous

**Operational DoD — gate ship POS Phase 4** (Story P4-POS-3 + P4-POS-6 — *P4-POS-5 retirée par l'amendement §10*) :

1. **Adapter Lightspeed** : `is_configured == True` + sandbox 1+ propriété + roundtrip `fetch_transactions(date_from=J-7, date_to=J)` retourne ≥ 100 transactions parseables.
2. **Schema migration** : `check_schema_drift.py` green (Décision #16) + tests RLS 3/3 pass.
3. ~~**Cohort matching v2** : LOO validation ≥ 2 sandbox properties → **MAPE_v2 ≤ MAPE_v1 - 1 pt** sur covers dinner.~~ **Retiré du gate Phase 4** (§10) — réintégré avec P4-POS-5 quand §D4 sera levé. Ne conditionne plus le ship POS.
4. **Eval gate** : `pos_anomaly` ≥ 8 scenarios dans `golden_dataset.jsonl` + `check_eval_coverage.py` green (Décision #22).
5. **Latence SLO** : `fetch_transactions` p95 < 800ms (analogue MCP).
6. **Documentation** : article Track B Phase 4 reinforcement *"PMS+POS fusion for hotel F&B forecasting"* drafté (cf. snippet H-6).

**Gate ship POS Phase 4.4 Micros** (conditionnel post-Phase 4.1+4.2) :

- Pilote Lightspeed validé operational DoD ci-dessus pendant ≥ 30j.
- 1 demand pilote enterprise confirmé Micros (sinon report Phase 5).
- Effort réel adapter Micros estimé ≤ 8pts post-spike technique.

---

## 7. Open questions (sortantes — re-trier post-pilote)

| ID | Question | Trigger résolution |
|---|---|---|
| OQ1 | Toast / Square / Tiller — quel vendor T2 ouvrir en deuxième Phase 4 late ? | Demand pilote design partner #2 |
| OQ2 | Adapter pattern *one-tenant-one-vendor* vs *multi-vendor-per-tenant* (resort avec brasserie Lightspeed + bar lobby Square) | Premier cas réel pilote |
| OQ3 | MCP wrapping côté Aetherix d'un POS pour exposer `query_pos_covers` à orchestrateurs externes ? | Phase 5 si demand orchestrateur |
| OQ4 | Granularité aggregation cohort POS features : 90j fixe vs adaptatif (saison) | Phase 4 post-LOO résultats |
| OQ5 | Food waste KPI (open decision Phase 4 vs 5) — POS items prep vs covers post-service comme mesure précise | Story Phase 4.5 séparée post-ship POS |

---

## 8. Références

- ADR 0001 — Aetherix MCP Server v0 (pattern lifespan + tool exposure)
- ADR 0002 — Memory instrumentation (testing strategy D11)
- ADR 0003 — `agent_action_log` observability
- ADR 0004 — Orchestrator separation (Aetherix = F&B execution node)
- ADR 0005 — Cold-start meta-learner (Resolved 28/05/2026, `docs/context/open-decisions.md` §Resolved)
- ADR 0007 — Evaluation-by-design (D1 `pos_anomaly` forward-compat)
- ADR 0008 *(future)* — Graphe de contexte (débloqué par cette session)
- `docs/competitive/apaleo-mcp-mapping.md` — border zone F&B Apaleo
- `docs/competitive/conduit-ai-analysis.md` — défense vertical depth
- `memory/market_signals_2026Q2.md` §Meuze.ai — POS-only restaurants concurrent
- `docs/marketing/positioning-snippets.md` H-6 — *"PMS+POS-aware cross-property intelligence"*
- `docs/context/decisions-architecturales.md` — Décisions #1, #7, #9, #10, #11, #21, #22 invoquées
- `docs/context/open-decisions.md` §Graphe de contexte (débloqué) · §Food waste tracking (étend)

---

## 9. Amendment 2026-06-23 — PMS canonical schema (jurisprudence Provider étendue)

> **Trigger** : analyse concurrentielle approfondie Grevon (`docs/_archive/competitive/grevon-analysis.md`) — leur produit Kore revendique explicitement la normalisation des données PMS brutes en format canonique avant tout consommateur agent. Implémente CLAUDE.md Décision #28.
> **Linear** : Epic 15 (HOS-279) — Story 15.1 (HOS-280), Story 15.2 (HOS-281). Parallélisable avec Epic 13 POS (HOS-254) et le pilote Apaleo Phase 3 Track A.
> **Distinct de** : HOS-186 ("PMS Connector universel", niveau Orchestrateur↔PMS, Décision #19) — backlog Phase 4 post-Track A, scope cross-node. Cet amendement est interne au node Aetherix (adapters↔pipeline forecast), orthogonal à HOS-186.

### 9.1 Constat

Vérification du code (06-23) : `PMSAdapter` (`backend/app/services/pms_sync.py`) existe comme interface normalisée (`get_occupancy`, `get_revenue`, `get_historical_data`, `update_staffing_in_pms`), implémentée par `ApaleoPMSAdapter` et `ApaleoMCPAdapter`. Mais le pipeline forecast — `DataTransformer` (`data_transformer.py`) — la **contourne** : il lit les champs de la réponse Apaleo brute directement ("arrival", "adults", "children") pour construire le dataframe Prophet (`ds`, `y`). Aucun adapter Mews n'existe encore (Phase 4, Décision #23).

**Conséquence si non corrigé** : brancher Mews (Phase 4, HOS-186 ou story dédiée) nécessitera soit dupliquer la logique du `DataTransformer` pour le format Mews, soit réécrire `DataTransformer` à ce moment-là sous pression de calendrier — exactement l'inverse de l'invariant Provider (Décision #9 : *"swap Claude → Gemini → GPT sans réécriture"*).

**Antécédent** : `docs/ARCHITECTURE.md` (obsolète, fév. 2026) nommait déjà "PMS Adapters" comme composant de sa "Semantic Layer", planifié Phase 5, jamais construit. Le scope est tombé silencieusement lors du pivot Qdrant→pgvector (Décision #3) sans décision explicite de retrait — dette de process, pas seulement dette technique. Le terme "Semantic Layer" a survécu dans les docs marketing courants (`docs/_archive/MARKET_INTELLIGENCE.md`) mais désigne aujourd'hui uniquement la couche RAG/pgvector (`fb_patterns` + `operational_memory`) — un concept différent (rétrieval de patterns historiques pour l'explicabilité), pas la normalisation de flux PMS live. Les deux ne doivent pas être confondus.

### 9.2 Décision

Étendre la jurisprudence Provider (§D3 ci-dessus, Décision #9/#10) aux adapters PMS, symétriquement à ce qui a été fait pour POS dans cet ADR :

```
backend/app/providers/pms/
├── __init__.py
├── base.py              — Protocol PMSProvider + dataclasses canoniques
│                           (NormalizedReservation, NormalizedOccupancy, ...)
├── factory.py            — get_pms_provider() singleton, env-driven (Décision #10)
├── apaleo_adapter.py      — migré depuis services/pms_sync.py + apaleo_adapter.py
└── mews_adapter.py        — Phase 4, story dédiée (hors scope HOS-279/280/281)
```

**Invariant** : à partir de cette migration, `DataTransformer` / `PredictionEngine` / `StaffRecommender` ne lisent **plus jamais** un champ vendor-spécifique directement — uniquement les dataclasses de `providers/pms/base.py`. Seul l'adapter connaît le format natif du PMS source. Quand `mews_adapter.py` sera écrit (Phase 4), il s'insère sans toucher au pipeline forecast.

### 9.3 Pourquoi maintenant et pas en même temps que l'adapter Mews

Faire la normalisation *au moment* d'écrire l'adapter Mews mélangerait deux risques dans une seule story (le mapping Mews lui-même + la rétro-compatibilité du pipeline forecast existant). Découpler permet de valider le refactor (HOS-280/281) sur Apaleo seul, avec un test de non-régression strict (mêmes sorties forecast avant/après), avant d'introduire un deuxième vendor.

### 9.4 Story breakdown (Epic 15, HOS-279)

| Story | Title | Effort | Dépend de |
|---|---|---|---|
| **HOS-280** (15.1) | `PMSProvider` Protocol + dataclasses canoniques + migration `ApaleoPMSAdapter`/`ApaleoMCPAdapter` — comportement inchangé | 3 | — |
| **HOS-281** (15.2) | `DataTransformer`/`PredictionEngine`/`StaffRecommender` consomment exclusivement le schéma canonique | 2 | HOS-280 |

**Total** : 2 stories, 5 points. Pur refactor — éligible label `eval-exempt` (Décision #22) si la régression test (AC3 des deux stories) confirme zéro changement de comportement observable.

### 9.5 Risque

| ID | Risque | Probabilité | Sévérité | Mitigation |
|---|---|---|---|---|
| **R9** | Refactor introduit une régression silencieuse dans le calcul MAPE (mapping canonique légèrement différent du mapping ad-hoc actuel) | Faible | Sévère (Phase 3 pilote en cours) | AC3 des deux stories = test de non-régression strict sur fixture sandbox identique avant/après. Ne pas merger si delta MAPE ≠ 0 (tolérance flottant). |

### 9.6 Références additionnelles

- `docs/_archive/competitive/grevon-analysis.md` — analyse déclencheur
- `docs/context/decisions-architecturales.md` — Décision #28
- HOS-186, HOS-254, HOS-279, HOS-280, HOS-281

### 9.7 Implémentation HOS-280 (17/10/2026) — deux écarts assumés

1. **Factory par PMS de l'hôtel, pas par variable d'environnement.** Le POS de §D6-bis choisit un fournisseur global via `POS_BACKEND`. Pour le PMS, HOS-347 a fait du `pms_type` un fait propre à chaque hôtel : `get_pms_provider(pms_type, transport)` garde une instance par (PMS, transport) (esprit Décision #10) et refuse un PMS sans adaptateur (`pms_not_supported`), jamais de repli vers un autre éditeur.
2. **Valeurs étiquetées, pas corrigées.** Le schéma canonique dit ce qu'est chaque valeur : `unit` (REST : figure du endpoint, unité non vérifiée ; MCP : pourcentage de chambres vendues), `scope` (REST retombe sur le total si la catégorie vaut 0 ; MCP ignore la catégorie), `is_placeholder` (MCP renvoyait occupation 80 et revenu 0.0 hors configuration ou en erreur, comme si le PMS l'avait dit). Les valeurs stockées par `PMSSyncLog` restent identiques (AC3) ; la sync journalise un placeholder. Corriger ces écarts change des chiffres : story dédiée.

---

## 10. Amendment 2026-07-31 — §D4 différé : le socle `hotel_cohort_features` n'existe pas

> **Statut §D4** : Accepted → **Deferred**. Le reste de l'ADR (D1, D2, D3, D5, D6, D7, §9) est **inchangé et reste Accepted**.
> **Déclencheur** : rédaction rétroactive d'ADR-0005 (27/07/2026), elle-même déclenchée par le détecteur D2 de l'agent d'hygiène architecturale (HOS-320).

### 10.1 Constat

`hotel_cohort_features` — la table sur laquelle §D4 construit — **n'existe pas**. Vérifié le 31/07/2026 : aucune migration, aucun modèle ORM, aucune référence dans `backend/`. Le tool `query_cohort_prior` qu'ADR-0005 D5 spécifie et que §D4 propose d'étendre n'existe pas davantage.

ADR-0005 §0 documente le détail : de cette décision, seul le **principe** « dégrader, ne pas éteindre » (D6) est en production, généralisé par Epic 12 G-4. Le mécanisme d'apprentissage — cohort matching, blending BMA, table de features, validation LOO — est resté au stade Design.

Trois conséquences, par ordre de gravité.

**(a) Le blocage est à la story 2, pas à la story 5.** La DDL de `hotel_cohort_features_pos` (§D5, ligne `REFERENCES hotel_cohort_features(cohort_id)`) vit **dans la migration `pos_integration_v0.sql`**, portée par **P4-POS-2**. Cette migration échouerait à l'application : la table cible de la clé étrangère n'existe pas. P4-POS-2 étant la dépendance de P4-POS-3 → 4 → 5 → 6, **l'intégralité du backlog POS Phase 4 est bloquée dès le deuxième jour de sprint**, pour une raison sans rapport avec le POS.

**(b) §1.2 affirme au présent ce qui n'est pas construit.** « ADR-0005 repose sur `hotel_cohort_features` » se lit comme un état de fait. C'est une intention. Corrigé ci-dessous.

**(c) Trois versions sont empilées sur un socle absent.** ADR-0005 v1 (non bâti) → ADR-0006 §D4 v2 → **ADR-0008 §Q4 v3** (`γ × cos_pms + δ × cos_pos + ε × path_match_score`). ADR-0008 hérite mécaniquement du même blocage. Non amendé ici — c'est le périmètre d'ADR-0008 — mais signalé.

### 10.2 Arbitrage

**§D4 est différé, pas rejeté.** Son raisonnement de conception tient : les 3 features POS-driven discriminent effectivement ce que le profil PMS seul ne discrimine pas (§1.2, boutique breakfast-heavy vs dinner-heavy). Ce n'est pas la décision qui est fausse, c'est son socle qui est absent — **et délibérément gelé**.

Car le blocage n'est pas un simple retard d'ingénierie. Le cohort matching *est* la Hive, et la Hive fait partie des cinq briques que l'audit interne (`analyse-critique-2026-07.md`) et la revue adverse externe du 20/07 ont gelées tant que la valeur n'est pas prouvée sur données réelles. Construire v1 pour débloquer v2 reviendrait à lever le gel par la porte de service.

Maintenir §D4 en `Accepted` pendant que son fondement est gelé, c'est exactement le motif « architecture sans preuve » que l'audit reproche au projet. Le geste honnête est de le dire dans l'ADR, pas de le laisser se découvrir au sprint planning de la Phase 4.

### 10.3 Effets — ce qui change

| Élément | Avant | Après |
|---|---|---|
| §D4 statut | Accepted | **Deferred** |
| DDL `hotel_cohort_features_pos` | dans `pos_integration_v0.sql` (P4-POS-2) | **extraite** vers une migration future, livrée avec P4-POS-5 |
| P4-POS-5 (cohort v2 + LOO, 5 pts) | Phase 4 | **hors périmètre Phase 4** — bloquée, précondition §10.4 |
| P4-POS-6 dépend de | P4-POS-5 | **P4-POS-3** |
| Total Phase 4 | 6 stories, 24 points | **5 stories, 19 points** |
| DoD opérationnel §6, item 3 (LOO cohort v2) | gate de ship Phase 4 | **retiré** du gate — réintégré avec P4-POS-5 |

**Ce qui n'est pas touché** : D1 (vendors + phase), D2/D3 (Protocol + adapter pattern), D5 (schema `pos_transaction`), D6, D7, et l'amendement §9 (PMS canonical schema, Décision #28). L'ingestion POS elle-même reste livrable en Phase 4.

C'est le point de l'arbitrage : **couper la dépendance vers du travail gelé rend le POS effectivement shippable**, au lieu de le laisser bloqué par une table que personne ne prévoyait de construire.

### 10.4 Précondition de levée — chaîne explicite

§D4 redevient actionnable quand, **dans cet ordre** :

1. Le gel Hive est levé — les 5 conditions de l'audit sont prouvées (données PMS/POS réelles, horizon de décision réel, forecast > baseline naïve, adoption manager, unit economics). Suivi : HOS-307 / HOS-308 / HOS-309 / HOS-312.
2. ADR-0005 D1-D5 sont **construits** : table `hotel_cohort_features`, tool `query_cohort_prior`, cohort matching hybride, blending BMA.
3. ADR-0005 D7 est **exécuté** : validation leave-one-out sur 5 propriétés sandbox — jamais réalisée à ce jour.

Tant que (1) n'est pas acquis, (2) et (3) ne doivent pas être entamés. Cette story n'est pas « à replanifier plus tard » : elle est **conditionnée à une preuve qui n'existe pas encore**.

### 10.5 Correction de §1.2

La phrase « ADR-0005 (cold-start meta-learner) repose sur `hotel_cohort_features` » doit se lire : *« ADR-0005 **prévoit** `hotel_cohort_features` — coefficients agrégés Prophet + hyperparams calibrés, dérivés exclusivement PMS. Cette table **n'est pas construite** (ADR-0005 §0). Le raisonnement ci-dessous porte sur la conception d'ADR-0005, pas sur un système en place. »*

### 10.6 Références

- `docs/adr/0005-cold-start-meta-learner.md` §0 — statut d'implémentation par élément
- `docs/context/analyse-critique-2026-07.md` — gel Hive
- `docs/adr/0008-context-graph.md` §Q4 — v3, hérite du même blocage
- HOS-320 (détection D2) · HOS-300 NFR2 (gel nouveaux ADRs — un amendement qui *restreint* le périmètre n'est pas concerné)

---

## 11. Amendment 2026-09-01 — Mews POS natif : absent de la table vendors §D1, catégorie distincte

> **Trigger** : mews.com/en/press/mews-pos-live-in-north-america (partagé par Ivan) — Mews POS (natif à l'OS Mews depuis 2024, 20+ pays) arrive en Amérique du Nord. Détail veille : vault Obsidian `Veille/Veille_Watchlist_Concurrents.md` §W4, `Veille_Competitors_Market.md` §SEP 1, 2026.
> **Ne restreint ni n'étend le périmètre décidé** (D1-D6 inchangés) — documente une catégorie de vendor absente du scan initial, cohérent avec la clause HOS-300 NFR2 sur les amendements qui ne créent pas de nouveau travail.

### 11.1 Constat

La table vendors §D1 (06/06/2026) évalue exclusivement des **POS tiers** (Lightspeed, Oracle Micros, Toast, Square, Tiller, etc.) et note, comme critère de scoring, si *ces vendors tiers* s'intègrent avec Apaleo et/ou Mews. **Mews POS lui-même n'apparaît jamais dans la table** — parce qu'il n'est pas un vendor tiers à évaluer, c'est une fonctionnalité **native de l'OS Mews**, hors du cadre "PMS + POS séparés" que la table présuppose implicitement.

### 11.2 Pourquoi ça change la question, pas la réponse

Pour une propriété Apaleo (le PMS principal, Décision #11), la question reste inchangée : Apaleo n'a pas de POS natif, un adapter `POSProvider` vers un vendor tiers (Lightspeed T1) reste la bonne architecture.

Pour une propriété **Mews** qui utilise **Mews POS natif** (pas un POS tiers), la question change de nature : la donnée F&B item-level vivrait dans l'écosystème/API Mews lui-même, pas chez un vendor `POSProvider` séparé. Dans ce cas précis, l'*ingestion* ne passerait pas par un adapter `POSProvider` supplémentaire — elle serait portée par le futur **adapter Mews** (HOS-186, PMS Connector universel, toujours backlog Phase 4, gated par la fin de Phase 3 Track A). Une propriété Mews sur un POS tiers (Lightspeed via Mews Marketplace, déjà noté §D1) resterait sur le chemin `POSProvider` standard — les deux cas coexistent, ce n'est pas un remplacement.

**Garde-fou tool-agnostic** : que l'adapter Mews "couvre PMS et POS d'un même mouvement" décrit le chemin d'*ingestion* (une seule connexion API côté Mews), **pas** une sortie vendor-spécifique. L'objectif produit reste d'être agnostique à l'outil (cf. Décision #9 *"swap Claude → Gemini → GPT sans réécriture"*, étendue aux PMS par l'amendement §9 de cet ADR). Concrètement : l'adapter Mews doit démapper les tickets F&B natifs vers le **même schéma canonique `pos_transaction`/`POSItem`/`POSOutlet`** (§D5) que produisent `LightspeedKSeriesAdapter` ou `OracleMicrosSimphonyAdapter` — soit en implémentant lui-même le Protocol `POSProvider` en interne (deux Protocols honorés par un seul adapter réseau), soit en émettant ses objets normalisés vers le même pipeline d'insertion. `DataTransformer` / cohort matching / forecast ne doivent jamais savoir si la donnée POS d'une propriété vient d'un adapter POS tiers ou d'un adapter PMS qui embarque le POS — exactement l'invariant que §9 a dû retrofit sur `DataTransformer` pour Apaleo, à ne pas re-casser ici par construction dès le départ.

### 11.3 Décision

Aucune action Phase 3/4 immédiate — le pilote reste Apaleo-first (Décision #11), aucun design partner Mews n'est en cours d'évaluation. **Documenté maintenant pour coût nul** (même logique que Décision #28) : quand HOS-186 sera scopé, ou qu'un design partner Mews avec POS natif actif sera évalué, vérifier en premier si la donnée F&B transite par l'écosystème Mews avant de présumer qu'un `POSProvider` tiers est nécessaire — et concevoir l'adapter Mews pour qu'il alimente le schéma canonique `pos_transaction` existant plutôt qu'un format Mews-spécifique en aval.

### 11.4 Références

- `docs/context/decisions-architecturales.md` Décision #23/#28
- HOS-186 (PMS Connector universel, backlog Phase 4)
- Vault Obsidian `Veille/Veille_Watchlist_Concurrents.md` §W4, `Veille_Competitors_Market.md` §SEP 1, 2026

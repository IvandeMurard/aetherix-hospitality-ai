# Aetherix — Positioning Snippets

**Purpose:** Copy patrol — phrases courtes, validées PM, prêtes à intégrer landing / Agent Hub listing / deck pilot / Apaleo Marketplace.

**Update protocol:** chaque ligne = un snippet réutilisable. Versionné en git. Pas de copy ad-hoc dans le code ou les decks — toujours puiser ici pour cohérence cross-channel.

---

## Headlines (1-liners)

| ID | Phrase | Contexte |
|---|---|---|
| H-1 | Aetherix predicts who's calling for dinner tomorrow. | Vs guest-comm AI platforms (Conduit, Canary, Akia) — souligne predictive vs reactive |
| H-2 | We don't automate your booking inbox. We make sure you're not understaffed when those bookings arrive. | Vs Jengu.ai (front-of-house automation) |
| H-3 | Airbnb owns the guest funnel. We own the ops intelligence behind it. | Vs Airbnb Summer 2026 release |
| H-4 | Their morning briefing covers your front desk. Ours covers your kitchen. | Vs Anthropic Claude Hotel playbook (Piers Thackray) |
| H-5 | F&B intelligence app on top of your PMS — native to Mews and Apaleo. | Vs Mews OS (verticalization PMS) |
| H-6 | Hotel-native, PMS+POS-aware cross-property intelligence. | Vs Meuze.ai (F&B for restaurants/QSR) |
| H-7 | Federated by design — your hotel inherits the cohort's operational wisdom from Day 1, your raw data stays in your tenant. | Hive Memory Federated narrative — counter Meuze.ai's live federated claim (announced Phase 3, shipped Phase 4) |
| H-8 | OtelAI manages 6 departments. Aetherix masters one — F&B. When 30-45% of operating costs depend on a single forecast, specialist beats generalist. | Anti multi-department generalist platforms (OtelAI, TH1.ai, Venli, AeroGuest) — vertical depth > horizontal breadth on operational decisions |
| H-9 | PMS vendors are racing to become the decisioning layer. We bet F&B decisioning is too deep a discipline for any of them to build as a side feature — local incumbent or global platform. | Vs the "record vs learn" PMS consolidation thesis (Christian H., LinkedIn 06/2026) — extends H-8 one level up: vs PMS-level learning layers, not just F&B startups |
| H-10 | Knowing that a cancellation wave, a noisy room, and a falling forecast confidence belong together, for this property, right now, takes an ontology. | Signal model framing (ADR-0012, repo privé — vocabulaire/mécanismes non exposés ici). Détaché de H-7 (Hive/federated) — axe différent : composition locale temps réel, pas apprentissage cross-hôtels |

## Human-AI collaboration framing — "Tandem bike" (Murati frame)

**Source narrative:** Mira Murati (Thinking Machines), 06/2026 — *"Having humans in the loop sounds like a checkpoint. AI should be built like a tandem bike."*

**Snippet copy (use in landing + deck pilot, replaces "Human-in-the-loop" jargon):**

> *"Aetherix is built like a tandem bike, not a checkpoint. When the data is clear — covers patterns, weather, occupancy — the agent pedals harder. When the manager has tacit context the agent can't see — the regular Tuesday banquet booked off-system, the new boutique opening down the street — the manager pedals harder. Same direction, shared steering. The manager never signs off and walks away. Aetherix never decides alone."*

**Architectural backing:** Décision #6 (no auto-actions Phase MVP) + feedback loop (accepted/rejected/modified) + Private Memory learning.

**Variant for sales deck (shorter):**

> *"Aetherix doesn't replace the F&B director's judgment. It hands them the data, the alternatives, the evidence, the confidence — and pedals alongside them through the day."*

## Reliability framing — "Eval as a contract" (Qonto frame)

**Source narrative:** Marianne Borzic Ducournau (Head of AI Products, Qonto), 06/2026 — *"Working is proven on a test set. Reliable is proven in production."*

**Snippet copy (use in technical-buyer-facing copy, Apaleo Marketplace, security/reliability page):**

> *"Aetherix treats evaluation as a contract, not an afterthought. A versioned golden dataset and per-layer failure thresholds define what 'bad output' means before any code is written. Any change to forecasts, providers, memory, or prompts requires updated examples and a green eval pipeline before merge — CI-enforced gate."*

**5 dimensions reliability (use in security/trust page):**
- Edge behavior — tested on out-of-distribution inputs, not just happy path
- Graceful degradation — explicit *"I don't know"* contract when confidence below threshold
- Observability — production dashboards on model behavior, not just server uptime
- Reproducibility — same input today = same output tomorrow
- Distribution shift resilience — alerted when production inputs drift from training data

## Knowledge extraction framing — "Tacit knowledge"

**Source convergence:** Mira Murati · @t_blom · Hyperspell · GBrain · Ivan's Lore project (Feb 2026). Thesis 06/2026 consensus: *"Models are smart enough. Bottleneck = company-specific context locked in senior heads."*

**Snippet copy (founder narrative + Phase 5+ teaser):**

> *"RAG retrieves what you put in. Aetherix extracts what your manager never thought to write down. Every accepted, rejected, or modified recommendation is a signal we learn from — the tacit knowledge of how this specific hotel actually runs, captured continuously, without anyone having to write it down."*

**Cross-project narrative (use in About / founder bio):**

> *"In February 2026, I built Lore — a voice AI that captures the tacit expertise of senior aviation maintenance technicians before they retire. The pattern: RAG isn't enough. You have to actively extract what seniors never thought to write down. Aetherix applies the same thesis to hospitality F&B: Private Memory + manager feedback = continuous capture of the tacit knowledge that's nowhere in the PMS."*

## Specialist vs Generalist framing — vertical depth on operational decisions

**Source narrative:** Veille 06-08 a identifié 4 multi-departmental AI ops platforms (OtelAI, TH1.ai, Venli, AeroGuest) qui se positionnent generalists. Aetherix doit clarifier le frame inverse : specialist beats generalist quand les enjeux sont opérationnels et financiers.

**Snippet copy (full version — deck pilot, Apaleo Marketplace, technical-buyer page):**

> *"Multi-departmental AI platforms (OtelAI, TH1.ai, Venli) promise to manage 5-6 departments at once. Aetherix masters one — F&B operations. When 30-45% of operating costs depend on a single forecast accuracy, and when 25% of food prep ends as waste, specialist depth beats horizontal breadth. Generalists answer 'good enough across the board.' Specialists deliver decisions that change the P&L."*

**Variant (shorter, 1-liner — landing / Agent Hub listing):**

> *"OtelAI manages 6 departments. Aetherix masters one — F&B. When 30-45% of operating costs depend on a single forecast, specialist beats generalist."*

**Variant (specialist + framework — combine with Eval-as-Contract for technical buyers):**

> *"F&B operations is not a feature to bolt onto a guest comm platform. It's a discipline: time-series forecasting, occupancy correlation, manager feedback memory, cohort intelligence. Aetherix is built for that discipline — and proves it ships reliable predictions under an Eval-by-Design contract."*

**4 surfaces this framing covers:**
- **Buyer education** (mid-market buyers see 4 multi-dept platforms, need decision framework)
- **Sales objection handling** (*"why not buy all-in-one OtelAI?"* → spec ic answer ready)
- **Apaleo Marketplace listing copy** (differentiate from Venli adjacent)
- **Phase 3 pilot conversations** (Aetherix doesn't compete with multi-dept platforms, it complements or replaces F&B partial coverage)

## Federated cohort intelligence framing — "Hive Memory"

**Source narrative:** Hive Memory architecture (Décision #2 + ADR-0005 cold-start meta-learner). Communicated publicly from Phase 3 (**announced**) → production Phase 4 (**shipped**). Counter Meuze.ai's live federated learning claim.

**Snippet copy (full version — deck pilot, Apaleo Marketplace, technical-buyer page):**

> *"Federated cohort intelligence — your hotel inherits the operational wisdom of every comparable property on Aetherix from Day 1, while your raw data never leaves your tenant. Solo cold-start eliminated. Every accepted recommendation sharpens the cohort for all members."*

**Variant (shorter, marketing landing / 1-liner):**

> *"You're not training Aetherix alone. Your hotel joins a federated cohort — raw data stays in your tenant, operational patterns travel anonymized. The collective calibrates your Day-1 forecast. Every accepted recommendation sharpens the network."*

**4 surfaces this framing covers:**
- **Data sovereignty** (privacy / security buyers) — raw data stays in your tenant
- **Network effect** (value buyers) — collective wisdom calibrates your forecast
- **Day-1 unlock** (acquisition pitch) — solo cold-start eliminated
- **Cohort sharpening** (retention pitch) — every accepted reco sharpens for all members

## "Record vs Learn" framing — PMS decisioning layer (Christian H. frame)

**Source narrative:** Christian H. (LinkedIn, 06/2026) — on the long tail of 300-1200+ regional PMS incumbents vs global platforms (Mews, Cloudbeds): *"The cloud settled legacy versus modern a decade ago. The divide is record versus learn... The winner will not be whoever has the best interface. It will be whoever becomes the trusted source of operational truth inside the hotel, and turns it into decisions the building acts on."*

**Why this matters for Aetherix:** this names, at market level, the exact mechanism already tracked under **W2** (Apaleo Copilot/Trace Agent) and **W4** (Mews "AI-native OS") in `docs/context/monitoring-watchlist.md` — PMS vendors, local or global, racing to become the layer that decides, not just records. It generalizes the threat from "will this one PMS add F&B" to "every PMS is trying to become the decisioning layer, period."

**Two nested axes in the post — don't conflate them:** (1) **the moat** — idiosyncrasy (local OTAs, payment rails, regulation, billing quirks a global platform ignores) vs generalist (scales, but doesn't adapt) — and (2) **the weapon** — record vs learn (storing vs learning a decision policy). His thesis: the winner combines both — a global platform that learns is still generalist without idiosyncratic depth; a regional incumbent that learns *and* keeps its local depth has a home-field advantage no global platform can replicate. The axis that maps onto Aetherix is **#1, idiosyncrasy vs generalist** — not a company-scale distinction (regional firm vs global firm), but an adaptation-depth one, applied one level deeper: per-property, not per-country.

**Snippet copy (full version — deck pilot, founder narrative, technical-buyer page):**

> *"Every PMS — a thirty-year-old regional incumbent or a two-year-old cloud platform — is racing to become the layer that decides, not just records. We don't compete in that race. We bet that F&B decisioning — covers forecasting, staffing, food waste — is too deep a discipline to be anyone's side feature, whoever wins the PMS war. Aetherix sits on top of whichever PMS a hotel runs, local or global, and does the one thing none of them will do well: turn F&B data into a decision the kitchen acts on tonight."*

**Variant (shorter, 1-liner — landing / LinkedIn comment):**

> *"PMS vendors are learning to decide. We bet F&B decisioning is too specialized a discipline for any of them to build as a side feature — local incumbent or global platform."*

**Variant (combine with Tacit Knowledge framing, not Hive Memory — idiosyncrasy is the right pole, not local-vs-global scale):**

> *"Christian H. is right that the moat is idiosyncrasy, not scale — local OTAs and billing quirks a global platform ignores. We apply the same principle one level deeper: the regular Tuesday banquet, the way this specific kitchen actually runs. Private Memory captures that — what your manager never thought to write down. Hive Memory is only the cold-start scaffold; it fades as your hotel's own idiosyncratic patterns take over (Day-1 prior → property-specific truth). We never let the generalist answer be the final one."*

**4 surfaces this framing covers:**
- **Founder narrative / LinkedIn engagement** — direct, additive response to a thought-leader post already framing the right market shift, rather than a defensive watchlist note
- **Technical-buyer page** — clarifies Aetherix is PMS-agnostic by design (Décision #19, #28), not a contender in the PMS consolidation war
- **Investor narrative** — extends H-8 (specialist vs generalist) one level up: vs PMS-level learning layers (Apaleo, Mews), not only vs F&B-specific startups (OtelAI, Grevon)
- **Memory architecture narrative** — clarifies Hive Memory is a cold-start prior, never the generalist endpoint Christian critiques (cf. Tacit Knowledge framing above, Décision #26 D3 80/20→20/80 shift)

**Cross-reference:** `docs/context/monitoring-watchlist.md` W2, W4 · Tacit Knowledge framing (idiosyncrasy pole) · H-7 (Federated cohort, cold-start mechanics only) · H-8 (Specialist vs Generalist).

## Sources de vérité

| Snippet inspiré de | Date | Status |
|---|---|---|
| Conduit.ai analysis | 2026-06-04 | `docs/competitive/conduit-ai-analysis.md` |
| Mews OS launch | 2026-05-27 | `memory/market_signals_2026Q2.md` |
| Anthropic Claude Hotel playbook | 2026-05-28 | `memory/market_signals_2026Q2.md` |
| Airbnb 2026 Summer Release | 2026-05-20 | `memory/market_signals_2026Q2.md` |
| Jengu.ai | 2026-05-25 | `memory/market_signals_2026Q2.md` |
| Meuze.ai | 2026-06-01 | `memory/market_signals_2026Q2.md` |
| Qonto talk + slides | 2026-06-04 | `docs/planning/evaluation-by-design.md` |
| Mira Murati Thinking Machines | 2026-06-04 | `memory/market_signals_2026Q2.md` |
| Lore (Ivan project) | 2026-02-28 → 2026-03-01 | `https://github.com/IvandeMurard/Lore` |

## Process

- Append-only — ne pas réécrire un snippet validé. Si revision nécessaire, ajouter un H-X+1 et marquer H-X comme deprecated avec date.
- Validation PM avant intégration — chaque snippet ajouté ici a été tranché en session PM.
- Cross-link depuis tout nouveau deck / landing — `voir docs/marketing/positioning-snippets.md` plutôt que recopier.

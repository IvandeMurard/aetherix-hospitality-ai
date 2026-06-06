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

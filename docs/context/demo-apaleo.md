# Demo PRD — Aetherix x Apaleo

> **Audience:** Lennart Reents, AI Engineer @ Apaleo (Munich)
> **Goal:** End-to-end agentic F&B pipeline integrating the official Apaleo MCP Server — proof of concept for application
> **Deliverable:** 90-second Loom + public GitHub repo
> **Target date:** April 2026
> **Last updated:** 2026-04-13 — PM session

---

## §1 — Demo scenario and hotel choice

**Hotel:** Hotel Kleber *(fictional, representative of the Apaleo segment)*
- Independent 4-star, 118 rooms, Paris 16th arrondissement
- Restaurant "Le 16" — 78 covers max
- Apaleo client since 2024, experienced F&B Manager with no dedicated revenue or data team

**Event:** PSG vs. Bayern Munich, Champions League semi-final second leg
- Match date: Wednesday 6 May 2026, 21:00 (Parc des Princes)
- Announced 3 weeks ago at the draw — already in the agent's event calendar (PredictHQ)
- Stadium: 2.1 km from the hotel

**Demo moment:** Tuesday 5 May 2026, 14:00 (J-1 daily cycle)

**Operational realism:**
- Base staffing and initial provisions were planned 10-15 days ago
- Aetherix's role at J-1 14:00 is the **final adjustment**: refine exact expected covers, confirm additional server count, adjust mise en place based on latest signals (pickup rate, updated weather, direct restaurant reservations, last-minute cancellations)
- The manager makes a final call the evening before — Aetherix gives them the data to do it with precision

**Value demonstrated:** Even when an event is known weeks in advance, the **final precision and last-minute contextual adjustment** remain critical — walk-ins, no-shows, weather, match outcome uncertainty all shift the actual number.

---

### Anticipated questions and prepared answers

| Question | Answer |
|----------|--------|
| Why Hotel Kleber more than others? | Proximity to Parc des Princes (2.1 km, natural post-match route). Private Memory holds 3 previous CL home nights: +60% covers vs. Wednesday baseline, walk-in spike confirmed in all three. |
| Why this hotel size? | 100-150 room independents are the Apaleo sweet spot: large enough for F&B revenue to make +20 covers worth €3-6K, small enough to have no dedicated data team. That is exactly where Aetherix creates value. |
| Why an independent, not an Accor or Marriott? | Chains have centralised analytics teams. Apaleo targets tech-forward independents and small groups (2-20 properties). Hotel Kleber chose Apaleo precisely because it wants open APIs — Aetherix is the natural beneficiary. |
| Why not a known brand (Mama Shelter, 25hours)? | Fictional avoids IP and affiliation issues. The profile is identical to a 25hours Paris or a Hoxton. |
| Does the manager need to do anything to set this up? | No. Once onboarded (30-minute setup, property linked via Apaleo OAuth), the agent runs automatically. |
| What if the manager ignores the recommendation? | It is logged. MemoryService notes the pattern. After 2 consecutive ignored recommendations, the agent proactively asks what the manager observed — that feedback updates the capture rate profile. |

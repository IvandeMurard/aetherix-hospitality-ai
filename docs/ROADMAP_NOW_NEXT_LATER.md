# Roadmap: Now → Next → Later

**Last review:** March 22, 2026
**Strategic direction:** Agent-First Distribution (MCP Server + Agent SEO)
**Source:** Andrew Chen (a16z) insight — "distribution shifts from top of funnel to top of call stack"

---

## 🔥 NOW (This Week - Jan 6-12, 2026)

**Focus:** Fix critical bug → Unblock MVP

### This Week Priority

**Fix contextual patterns bug** to enable realistic, varied predictions. Currently all predictions return ~143 covers regardless of context (Christmas, weekend, events). This blocks credibility and Staff Recommender work.

### Issues

- [ ] **IVA-29:** 🔥 CRITICAL - Contextual patterns not applied (1h) - **BLOCKER**
  - Problem: Patterns always hardcoded (Coldplay/U2), Christmas treated as regular day
  - Impact: Predictions not credible (always ~143 covers)
  - Solution: Debug Python cache issue, verify contextual logic executes

### Success Criteria

- ✅ Christmas Day predicts 40-70 covers (not 143)
- ✅ Weekend vs weekday shows variation (100-160 range)
- ✅ Events boost covers (+15 per event)
- ✅ Weather affects predictions (rain -10 covers)
- ✅ Pattern dates recent (3-12 months ago, not 2023)

### Intelligence from Veille

<!-- Update each Monday 9am with relevant insights from Perplexity -->

**2026-01-07:** Initial roadmap creation
- No pending insights from veille yet
- First review scheduled: Monday January 13, 9am

---

## ⏭️ NEXT (Next 2-3 Weeks - Jan 13-26, 2026)

**Focus:** Complete Phase 1 MVP (4 remaining issues, ~4.5h effort)

### Issues

- [ ] **IVA-30:** Staff Recommender Agent (2h)
  - Adaptive staffing calculations based on predicted covers
  - Restaurant-specific configs (covers per server ratio)
  - Integration into prediction pipeline
  - **Blocked by:** IVA-29

- [ ] **IVA-31:** Integration test suite (1h)
  - 5 scenarios: weekend, weekday, holiday, rainy, New Year's Eve
  - Validate covers variation (not all ~143)
  - Pytest-ready for CI/CD
  - **Blocked by:** IVA-29

- [ ] **IVA-32:** Deploy to Render.com (1h)
  - Public demo URL: `https://fb-agent-mvp.onrender.com`
  - Swagger docs accessible
  - Deployment guide documentation

- [ ] **IVA-33:** Phase 1 limitations documentation (30min)
  - Honest assessment of what works/doesn't
  - Phase 2 roadmap preview
  - PM critical thinking demonstration

### Potential Additions from Veille

<!-- Capture new features discovered via industry intelligence -->

**To evaluate in weekly reviews:**
- None currently
- Will assess based on Perplexity Monday veille

### Success Criteria (Phase 1 Complete)

- ✅ All 11 MVP issues done
- ✅ Backend API publicly accessible
- ✅ 5 test scenarios passing
- ✅ Limitations documented transparently

---

## 📅 LATER (Phase 2-3 - Feb-Mar 2026)

**Focus:** Real integrations + Production features

### Phase 2 - Integrations (High Priority)

**Critical Path:**

- [ ] **IVA-13:** PMS integration (Mews/Apaleo) - **KEY DIFFERENTIATOR**
  - Occupancy rate → +15% F&B demand boost
  - Hotel conferences/events
  - VIP arrivals, dietary preferences
  - **Impact:** 40% prediction weight from internal data

- [ ] **Real APIs:** PredictHQ (events), Weather API
  - Replace mock data with real-time info
  - Improve prediction accuracy

- [ ] **Qdrant semantic search:** Real pattern matching
  - Replace hardcoded patterns
  - Vector similarity search
  - Contextual historical matches

### Phase 2 - UI Features (Medium Priority)

- [ ] **IVA-9:** Manager approval workflows
  - Validate/modify/reject predictions
  - State management (pending, approved, rejected)
  - Audit log

- [ ] **IVA-10:** Voice input (reevaluate after industry research)
  - Note: Noisy restaurant environments challenge voice
  - May defer based on veille insights

- [ ] **IVA-12:** ElevenLabs voice synthesis
  - Cost: ~$225/month vs $6.65 Claude API
  - Dependent on IVA-10 feasibility

### Backlog - Advanced Features (Low Priority)

- [ ] **IVA-11:** Command palette (Cmd+K style)
- [ ] **IVA-14:** NLU intent recognition
- [ ] **IVA-15:** Continuous learning + prediction accuracy tracking
- [ ] **IVA-16:** No-show risk prediction
- [ ] **IVA-17:** Semantic layer (PMS-agnostic)

### Ideas from Veille (To Scope Later)

<!-- Capture emerging technologies/features, evaluate ROI -->

**In progress (elevated from backlog → Phase 0.5):**
- ✅ **MCP Server for agent-callable capabilities** — TAC-74 (HOS-xx pending team rename)
  - `forecast_occupancy(hotel_id, date_range)` → F&B demand predictions
  - `get_stock_alerts(hotel_id)` → critical inventory alerts
  - `get_fb_kpis(hotel_id, period)` → structured F&B KPIs
- ✅ **Agent SEO instrumentation** — TAC-75 (HOS-xx pending team rename)
  - Middleware tracking: `tool_success_rate`, `p95_latency`, `agent_retry_rate`
  - Target: > 99.5% success rate, < 500ms p95, 0 breaking schema changes/sprint

**Backlog explorations:**
- Anthropic Artifacts for manager dashboards
- New Qdrant features for pattern matching
- Hospitality-specific LLMs (if emerge)

**Evaluation criteria:**
- Does it accelerate Phase 2 timeline?
- Does it improve differentiation vs competitors?
- Is implementation effort justified?

---

## 📊 Weekly Progress Log

### Week of January 6, 2026

**Completed:**
- ✅ IVA-26: Backend environment setup (Python + FastAPI)
- ✅ IVA-27: Demand Predictor skeleton
- ✅ IVA-28: Enhanced context generation
- ✅ IVA-5, 6, 7, 8: Previous MVP capabilities

**In Progress:**
- 🔄 IVA-29: Contextual patterns bug (attempted fixes, not resolved)

**Blocked:**
- ⛔ IVA-30, 31, 32, 33: All waiting on IVA-29 fix

**Time invested this week:** 4.5h (Hour 1: 1.5h, Hour 2: 2h, Debugging: 1h)

**Veille insights:** N/A (roadmap creation week)

**Next week focus:** Fix IVA-29, unblock remaining MVP work

---

### Week of January 13, 2026

**Planned:**
- [ ] Complete IVA-29 fix
- [ ] Start IVA-30 (Staff Recommender)
- [ ] Review Perplexity veille Monday 9am

**To update next Monday...**

---

## 🧠 Strategic Notes

### Key Learnings (Phase 0-1)

**Architecture Decisions:**
- ✅ Dashboard-first (not voice-first) — industry requires visual transparency
- ✅ Agentic-first (not API-first) — aligns with Augmented Hospitality
- ✅ Explainability critical (EU AI Act, GDPR Article 22)

**Product Insights:**
- Christmas edge case = critical for credibility (50 covers vs 143)
- Internal context (PMS) = 40% prediction accuracy
- Pattern variation > reasoning quality for demo impact

### Strategic Pivot — Agent-First Distribution (March 2026)

**Trigger :** Andrew Chen (a16z) thread on agent-native distribution — score veille 10/10.

**Thesis :** Aetherix n'est pas seulement un produit agentic. Dans un monde agent-first, la distribution se passe au niveau du *call stack*, pas de l'*acquisition funnel*. Il faut être **le default callable primitive pour le F&B hôtelier**.

**Conséquences sur la roadmap :**
1. **MCP Server (Phase 0.5)** — exposer les 3-5 capabilities core via MCP avant la Phase 1
2. **Agent SEO (Phase 1)** — instrumenter les métriques machine-legible dès le début
3. **Schema stability** — 0 breaking changes/sprint devient une contrainte non-négociable
4. **UI = debug layer** — le backend API/MCP est le produit réel; l'UI sert à vérifier

**PM Competencies Demonstrated:**
- Critical thinking: Identified Christmas incohérence + agent-first strategic shift
- Domain expertise: Server background = operations understanding
- Honest assessment: Documented limitations vs over-promising

### Next Pivots to Consider

**Si la veille montre :**
- Un concurrent lance un MCP server hospitality → accélérer Phase 0.5
- Apaleo/Mews publie un MCP officiel → évaluer partnership vs compétition
- Regulatory updates (EU AI Act) → Adjust explainability features
- New PMS APIs (Mews updates) → Reprioritize integration work

**Decision framework:**
- High impact + Low effort → Add to NEXT
- High impact + High effort → Plan for Phase 2
- Low impact → Reject or defer to Backlog

---

## 📈 Milestones & Timeline

**Phase 1 MVP (January 2026):**
- ✅ January 6: 64% complete (7/11 issues)
- 🎯 January 12: IVA-29 resolved (100% unblocked)
- 🎯 January 19: IVA-30-33 complete (MVP done)
- 🎯 January 31: Deployed + documented

**Phase 2 Kickoff (February 2026):**
- 🎯 February 3: PMS integration research (Mews API docs)
- 🎯 February 10: First PMS mock integration
- 🎯 February 17: Real APIs (PredictHQ, Weather)
- 🎯 February 24: Qdrant semantic search

**Case Study Completion (March 2026):**
- 🎯 March 10: Phase 2 MVP complete
- 🎯 March 17: Full documentation (Architecture, Decisions, Learnings)
- 🎯 March 24: Portfolio publish + Mews PM application

---

## 🔗 Links & Resources

**Linear Project:** https://linear.app/ivanportfolio/project/fandb-agent-640279ce7d36

**GitHub Repo:** https://github.com/IvandeMurard/fb-agent-mvp

**Documentation:**
- [Architecture.md](ARCHITECTURE.md)
- [MVP_Scope.md](MVP_SCOPE.md)
- [Cost_Model.md](Cost_Model.md)
- [Phase 1 Limitations](PHASE_1_LIMITATIONS.md) (to create)

**Veille Sources:**
- Perplexity: Monday 9am hospitality agentique trends
- Comet: Filtered hospitality tech content
- X follows: @Pauline_Cx, @averycode (build in public)

---

**Last updated:** January 7, 2026 by Ivan de Murard  
**Next review:** Monday, January 13, 2026 at 9:00 AM


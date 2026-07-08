# F&B Operations Agent - Cost Model

**Version:** 0.1.0 (MVP Phase 0)  
**Last Updated:** December 2, 2025  
**Author:** Ivan de Murard

---

## Overview

This document details the complete cost structure for the F&B Operations Agent, from MVP development through production scaling to 1,000+ restaurants.

**Key Highlights:**
- **MVP Cost:** $6.65/restaurant/month (well under $10 target)
- **Scale Cost (500 restaurants):** $1.14/restaurant/month (-78% savings)
- **Pro Tier Margin:** 89% gross margin ($49 revenue - $6.65 cost)
- **Break-even:** 1 customer (instant profitability)

**Full Cost Model (Google Sheets):**  
https://docs.google.com/spreadsheets/d/1K2AZVUdOeTxWzZQb5FaFIbh_nJXkuGvjTrcNk0Z_OPQ/edit?usp=sharing

---

## 1. Monthly Operating Expenses (Per Restaurant)

### MVP Configuration (1 Restaurant)

| Service | Tier | Monthly Cost | Usage | Notes |
|---------|------|--------------|-------|-------|
| **Claude API** | Pay-as-you-go | $1.65 | 100 predictions | $0.0165/prediction (3K input + 500 output tokens) |
| **Qdrant Cloud** | Free | $0 | <1GB storage | 50 patterns ~100MB, well under limit |
| **ElevenLabs** | Starter | $5.00 | 30K chars | Voice synthesis + transcription (opt-in) |
| **Supabase** | Free | $0 | <500MB database | PostgreSQL + Auth + Real-time |
| **Vercel** | Hobby | $0 | <100GB bandwidth | Next.js hosting, auto-deploy |
| **Render.com** | Free | $0 | Sleep after 15min | FastAPI backend (acceptable for demo) |
| **Redis (Upstash)** | Free | $0 | <10K requests/day | Session state, conversation context |
| **PredictHQ** | Free | $0 | 1,000 calls/month | Events API (concerts, festivals) |
| **TOTAL MVP** | - | **$6.65** | - | Conservative estimate |

**Cost Breakdown Detail:**

**Claude API Calculation:**
```
Input: 3,000 tokens × $3/MTok = $0.009
Output: 500 tokens × $15/MTok = $0.0075
Per prediction: $0.0165

100 predictions/month: $0.0165 × 100 = $1.65/month
```

**ElevenLabs Optimization:**
- Free tier: 10,000 chars/month
- MVP usage estimate: ~2,500 chars (50 predictions × 50 chars)
- **Could use free tier, but keeping Starter ($5) as safety buffer**
- Optimized cost: $1.65/month (Claude only)

**Why these services:**
- **Claude Sonnet 4:** Best reasoning quality for explainability
- **Qdrant:** Fastest vector search, generous free tier
- **ElevenLabs:** Best voice quality (natural, conversational)
- **Supabase:** PostgreSQL + Auth + Real-time in one platform
- **Vercel:** Optimized for Next.js, auto-deploy from GitHub
- **Render:** Docker-ready, easy backend deployment

---

## 2. Development Costs (One-Time)

### Phase 0-2 (MVP Development)

| Item | Cost | Notes |
|------|------|-------|
| **Developer Time** | $0 | Portfolio project (80-120h invested) |
| **Cursor Pro** | $20/month | AI-assisted coding (already subscribed, optional) |
| **Warp Pro** | $0 | Terminal included in existing subscription |
| **Figma** | $0 | Free tier (Figma Make used for mockups) |
| **GitHub** | $0 | Public repositories (unlimited) |
| **Domain Name** | $12/year | Optional (can use .vercel.app free subdomain) |
| **TOTAL ONE-TIME** | **$0-32** | Minimal upfront investment |

**Notes:**
- No API setup fees (all services free tier or pay-as-you-go)
- No hosting setup fees (Vercel, Render, Supabase free tiers)
- Cursor Pro optional (can use VS Code free)
- Domain optional for MVP (vercel.app works for demo)

---

## 3. Scale Scenarios (Economies of Scale)

### Cost Per Restaurant at Different Scales

| Restaurants | Predictions/Month | Claude API | Qdrant | ElevenLabs | Other | **Total Cost** | **Per Restaurant** | **Savings** |
|-------------|-------------------|------------|--------|------------|-------|----------------|-------------------|-------------|
| **1** | 100 | $1.65 | $0 | $5.00 | $0 | **$6.65** | **$6.65** | - |
| **5** | 500 | $8.25 | $0 | $5.00 | $0 | **$13.25** | **$2.65** | -60% |
| **50** | 5,000 | $82.50 | $25 | $5.00 | $10 | **$122.50** | **$2.45** | -63% |
| **500** | 50,000 | $825 | $95 | $22 | $50 | **$992** | **$1.98** | -70% |
| **1,000** | 100,000 | $1,650 | $149 | $99 | $100 | **$1,998** | **$2.00** | -70% |

**Scale Economics Drivers:**

1. **Fixed Costs Amortized:**
   - Qdrant $25/month ÷ 50 restaurants = $0.50 each
   - Backend hosting $10/month ÷ 50 restaurants = $0.20 each

2. **Volume Discounts:**
   - Claude API: Bulk pricing negotiations at 50K+ predictions
   - ElevenLabs: Enterprise tier cheaper per-character at scale

3. **Efficiency Gains:**
   - Batch predictions (process multiple restaurants in one API call)
   - Shared embeddings (reuse similar patterns across restaurants)
   - Cached results (reduce duplicate Claude API calls)

**Break-Even Points:**
- **5 restaurants:** $2.65/restaurant (profitable at $49/month Pro tier)
- **50 restaurants:** $2.45/restaurant (89% margin maintained)
- **500 restaurants:** $1.98/restaurant (strong unit economics)

---

## 4. Revenue Model (Pricing Tiers)

### Proposed Pricing Structure

| Tier | Price | Predictions | Restaurants | Key Features | Target Customer |
|------|-------|-------------|-------------|--------------|----------------|
| **Free** | $0/month | 10/month | 1 | Basic predictions, email support | Trial / small cafes |
| **Pro** | $49/month | Unlimited | 1 | + Voice input, priority support, analytics | Independent restaurants |
| **Team** | $199/month | Unlimited | Up to 5 | + Multi-location dashboard, API access, account manager | Small chains |
| **Enterprise** | Custom | Unlimited | Unlimited | + White-label, SSO/RBAC, custom integrations, SLA 99.9% | Hotel chains |

---

### Unit Economics (Pro Tier)

**Pro Tier Analysis:**
```
Revenue:        $49/month
Cost (COGS):    $6.65/month (MVP scale)
Gross Margin:   $42.35 (89%)

LTV (Lifetime Value):
- Avg subscription: 24 months (industry benchmark SaaS B2B)
- Churn: 5%/month (1 / 0.05 = 20 months effective)
- LTV: $49 × 20 months = $980

CAC (Customer Acquisition Cost) Target:
- LTV:CAC ratio: 3:1 (healthy SaaS metric)
- Max CAC: $980 ÷ 3 = $327

Break-even: 1 customer (instant profitability)
```

**Why $49/month Pro tier:**
- **Competitive:** vs 7shifts ($30-50), HotSchedules ($50-100), Fourth ($75-150)
- **Value-based:** Time saved (5-8h → 2h) = 6h/week × $25/hour = $150/week value
- **Affordable:** <$2/day for average restaurant ($1M revenue)
- **Positioning:** "Premium but accessible" (not cheapest, best AI quality)

**Gross Margin Sustainability:**
```
At scale (500 restaurants):
- Cost: $1.98/restaurant
- Revenue: $49/month
- Margin: $47.02 (96%)

Strong SaaS margins maintained across scales.
```

---

## 5. Sensitivity Analysis

### What-If Scenarios

**Scenario A: High Usage (200 predictions/month)**
```
Claude API: $1.65 × 2 = $3.30
ElevenLabs: Same ($5.00)
Total: $8.30/month

Still <$10 target ✅
Margin: $49 - $8.30 = $40.70 (83%)
```

**Scenario B: Free Tier Optimization (ElevenLabs free)**
```
Claude API: $1.65
ElevenLabs: $0 (free tier)
Total: $1.65/month

Ultra-lean MVP ✅
Margin: $49 - $1.65 = $47.35 (97%)
```

**Scenario C: Claude API Price Increase (+50%)**
```
Claude API: $1.65 × 1.5 = $2.48
ElevenLabs: $5.00
Total: $7.48/month

Still profitable ✅
Margin: $49 - $7.48 = $41.52 (85%)
```

**Scenario D: Competition Forces Price Down ($29/month)**
```
Revenue: $29/month
Cost: $6.65
Margin: $22.35 (77%)

Still healthy margin ✅
But need 2x customers for same revenue
```

**Risk Mitigation:**
- ✅ 89% margin provides pricing flexibility
- ✅ Free tiers reduce downside risk
- ✅ Multiple revenue streams (Pro/Team/Enterprise)
- ✅ Cost decreases with scale (economies of scale)

---

## 6. Comparison with Alternatives

### Cost vs Competitors

| Solution | Cost/Restaurant/Month | Features | Our Advantage |
|----------|----------------------|----------|---------------|
| **7shifts** | $30-50 | Scheduling, forecasting, time tracking | + AI reasoning, PMS integration |
| **HotSchedules** | $50-100 | Scheduling, forecasting, POS integration | Cheaper, better AI |
| **Fourth** | $75-150 | Labor management, analytics, forecasting | 6x cheaper, specialized F&B |
| **Toast** | $69-165 | POS + scheduling (bundled) | Unbundled (no POS lock-in) |
| **Manual (spreadsheets)** | $0 | Manager time 5-8h/week | Saves $150/week labor cost |

**Our positioning:**
- **Not cheapest** (vs 7shifts low-end $30)
- **Best AI quality** (explainable reasoning, voice-enabled)
- **PMS-integrated** (Mews, Apaleo native)
- **Hospitality-specific** (not generic retail scheduling)

**Value proposition math:**
```
Manager time saved: 6h/week × $25/hour = $150/week = $650/month
Cost: $49/month
ROI: ($650 - $49) / $49 = 1,227% ROI
Payback period: <1 week
```

---

## 7. Key Assumptions & Risks

### Cost Assumptions

**Validated:**
- ✅ Claude API pricing confirmed (Anthropic pricing page, Dec 2025)
- ✅ Qdrant free tier confirmed (<1GB storage)
- ✅ ElevenLabs pricing confirmed (free 10K chars, Starter $5/month)
- ✅ Supabase, Vercel, Render free tiers confirmed

**Estimates:**
- ⚠️ 100 predictions/month average (could be 50-200 range)
- ⚠️ 3K input + 500 output tokens per prediction (varies by complexity)
- ⚠️ 50 patterns per restaurant (depends on historical data richness)

### Risk Factors

**Price Risk:**
- Claude API could increase prices (mitigated by 89% margin buffer)
- Free tiers could be restricted (mitigated by paying tiers as backup)

**Usage Risk:**
- Restaurants use more predictions than estimated (mitigated by unlimited Pro tier)
- Voice usage higher than expected (mitigated by free tier buffer)

**Competition Risk:**
- Competitors lower prices (mitigated by differentiation: AI quality, PMS integration)
- 7shifts adds AI reasoning (mitigated by hospitality specialization)

**Mitigation Strategy:**
1. **High margins (89%)** → Can absorb 2x cost increase
2. **Multiple tiers** → Capture different customer segments
3. **Economies of scale** → Cost decreases as we grow
4. **Free tier optimization** → ElevenLabs free tier reduces cost 75%

---

## 8. Financial Projections (3-Year)

### Revenue Scenarios

**Conservative (Year 1: 50 customers, 20% MoM growth):**
```
Year 1: 50 customers × $49 × 12 months = $29,400 revenue
Year 2: 150 customers × $49 × 12 months = $88,200 revenue
Year 3: 400 customers × $49 × 12 months = $235,200 revenue

Total 3-year revenue: $352,800
Gross margin (89%): $314,000
```

**Moderate (Year 1: 100 customers, 30% MoM growth):**
```
Year 1: 100 customers × $49 × 12 months = $58,800 revenue
Year 2: 350 customers × $49 × 12 months = $205,800 revenue
Year 3: 1,000 customers × $49 × 12 months = $588,000 revenue

Total 3-year revenue: $852,600
Gross margin (89%): $758,800
```

**Aggressive (Year 1: 200 customers, 40% MoM growth):**
```
Year 1: 200 customers × $49 × 12 months = $117,600 revenue
Year 2: 800 customers × $49 × 12 months = $470,400 revenue
Year 3: 2,500 customers × $49 × 12 months = $1,470,000 revenue

Total 3-year revenue: $2,058,000
Gross margin (89%): $1,831,620
```

**Key Metrics (Year 3 Moderate):**
- ARR (Annual Recurring Revenue): $588,000
- MRR (Monthly Recurring Revenue): $49,000
- COGS: ~$2,000/month (1,000 customers × $2/restaurant)
- Gross Margin: 96% (at scale)

---

## 9. Funding Requirements

### Bootstrap-Friendly Model

**MVP (Phase 0-2):**
- Development: $0 (portfolio project, own time)
- Infrastructure: $6.65/month (free tiers + Claude API)
- Total investment: <$100 for 3 months

**Growth (Phase 3-4):**
- Marketing: $5,000-10,000 (content marketing, SEO, partnerships)
- Sales: $0 (founder-led sales, Mews/Apaleo marketplace)
- Infrastructure: Scales with revenue (pay-as-you-go)

**No external funding required:**
- ✅ Instant profitability (89% margins)
- ✅ Free tier acquisition (viral loop)
- ✅ Low CAC target ($327, achievable via content + partnerships)
- ✅ Fast payback period (<1 week ROI for customers)

**Self-sustaining from Month 1 with 2 paying customers:**
```
Revenue: 2 × $49 = $98/month
Costs: 2 × $6.65 = $13.30/month
Profit: $84.70/month (covers founder ramen 🍜)
```

---

## 10. Summary & Recommendations

### Key Takeaways

1. **MVP Cost: $6.65/month** (conservative, <$10 target ✅)
2. **Scale Cost: $1.98/month at 500 restaurants** (-70% savings)
3. **Pro Tier Margin: 89%** (healthy SaaS economics)
4. **Break-even: 1 customer** (instant profitability)
5. **Bootstrap-friendly:** No external funding needed

### Recommendations

**Phase 0-1 (MVP Development):**
- ✅ Use free tiers aggressively (Qdrant, Supabase, Vercel, Render)
- ✅ Optimize ElevenLabs (try free tier first, upgrade only if needed)
- ✅ Monitor Claude API usage (set alerts at $5/month)

**Phase 2-3 (First Customers):**
- ✅ Validate pricing ($49 Pro tier) with 5-10 beta customers
- ✅ Track actual vs estimated usage (predictions/month, tokens/prediction)
- ✅ Measure ROI (time saved, accuracy improvement)

**Phase 4+ (Scale):**
- ✅ Negotiate volume discounts (Claude API, ElevenLabs at 50+ customers)
- ✅ Add Team tier ($199) to capture multi-location customers
- ✅ Explore Enterprise tier (custom pricing for hotel chains)

### Cost Model Health Check

✅ **Sustainable:** $6.65/month < $10 target  
✅ **Scalable:** -70% cost reduction at scale  
✅ **Profitable:** 89% margin maintained  
✅ **Defensible:** High margins allow pricing flexibility  
✅ **Competitive:** $49/month vs $50-150 market range  

**Decision:** ✅ Cost model approved for Phase 1 implementation

---

## Appendix

### Sources

- **Claude API Pricing:** https://www.anthropic.com/pricing (verified Dec 2025)
- **Qdrant Cloud Pricing:** https://qdrant.tech/pricing/ (verified Dec 2025)
- **ElevenLabs Pricing:** https://elevenlabs.io/pricing (verified Dec 2025)
- **Supabase Pricing:** https://supabase.com/pricing (verified Dec 2025)
- **Vercel Pricing:** https://vercel.com/pricing (verified Dec 2025)
- **Render Pricing:** https://render.com/pricing (verified Dec 2025)

### Related Documents

- **Problem Statement:** `docs/_archive/Problem_Statement.md`
- **MVP Scope:** `docs/_archive/MVP_SCOPE.md`
- **Architecture:** `docs/ARCHITECTURE.md`
- **Google Sheet (Live):** https://docs.google.com/spreadsheets/d/1K2AZVUdOeTxWzZQb5FaFIbh_nJXkuGvjTrcNk0Z_OPQ/edit?usp=sharing

---

**Document Version:** 1.0  
**Last Updated:** December 2, 2025  
**Next Review:** After Phase 2 (first paying customers, validate actual costs)
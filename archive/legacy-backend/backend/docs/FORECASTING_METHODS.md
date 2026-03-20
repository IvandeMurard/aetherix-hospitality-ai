# Forecasting Methods Research

> Research document for F&B demand forecasting methods and accuracy metrics.
> Part of the F&B Operations Agent portfolio project.

---

## Current Approach: RAG-Based Prediction

Our system uses **Retrieval-Augmented Generation** with semantic search:
```
Query context → Mistral embedding → Qdrant similarity search → Top-5 patterns → Weighted average
```

**Strengths:**
- **Explainable:** "Based on 5 similar Saturday dinners..."
- **Context-aware:** weather, events, holidays embedded in search
- **Adaptable:** new patterns added without retraining

**Limitations:**
- No trend detection (static historical patterns)
- Accuracy metrics require actual vs predicted comparison
- Dependent on pattern diversity in database

---

## Industry-Standard Methods

### 1. Accuracy Metrics

| Metric | Formula | Use Case | Industry Target |
|--------|---------|----------|----------------|
| **MAPE** | `mean(|actual - predicted| / actual) × 100` | Percentage error | < 15% |
| **MAE** | `mean(|actual - predicted|)` | Absolute error | — |
| **RMSE** | `sqrt(mean((actual - predicted)²))` | Penalizes large errors | — |

**Why MAPE matters:**
- Industry standard for demand forecasting
- Comparable across different volume restaurants
- Expected by hospitality tech buyers (e.g., Mews PM)

**Implementation requirement:**
MAPE requires historical predictions vs actual outcomes. With derived data (Kaggle), this would be artificial. Real accuracy tracking needs:
- Log predictions with timestamps
- Capture actual covers post-service
- Calculate rolling MAPE (7-day, 30-day windows)

### 2. Time Series Methods

| Method | Description | Complexity | Best For |
|--------|-------------|------------|----------|
| **Moving Average** | Average of last N periods | Low | Stable demand |
| **Exponential Smoothing** | Weighted recent data | Low | Trend detection |
| **Holt-Winters** | Trend + seasonality | Medium | Weekly/seasonal patterns |
| **ARIMA** | Autoregressive integrated | Medium-High | Complex time series |
| **Prophet** | Facebook's forecasting | Medium | Multiple seasonalities |

**Relevance to our approach:**
- RAG handles contextual similarity (events, weather)
- Time series handles temporal patterns (day-of-week, seasonality)
- Hybrid approach could combine both

### 3. Pickup Curves (Hotel-Specific)

Tracks booking pace as service date approaches:
```
Days before:   -14   -7   -3   -1   Day-of
Reservations:   20   45   72   85    92
Pickup rate:    —   +25  +27  +13    +7
```

**Application to F&B:**
- Track reservation pace for dinner service
- Adjust prediction based on booking velocity
- Alert if pace deviates from historical pattern

---

## Competitor Analysis

| Solution | Primary Method | Data Sources | Differentiator |
|----------|---------------|--------------|----------------|
| **Kikleo** | ML on POS data | Historical sales, inventory | Food cost optimization |
| **Ailean** | Time series + ML | POS, reservations | Kitchen-specific predictions |
| **Guac AI** | Ensemble models | Multi-source | Inventory management |
| **Mews BI** | Regression + Pickup | PMS, reservations | Integrated with PMS |
| **7shifts** | Demand curves | POS integration | Labor scheduling |
| **HotSchedules** | Statistical models | POS, traffic | Workforce management |

### Our Differentiation

| Competitor Gap | Our Approach |
|---------------|--------------|
| Black-box ML predictions | Explainable reasoning ("Based on 3 similar patterns...") |
| Single-source data | External context (events, weather, holidays) |
| Dashboard-only output | What-If scenario modeling (planned) |
| Vendor lock-in | PMS-agnostic adapter pattern |

---

## Recommended Hybrid Architecture

```
┌─────────────────────────────────────────────────┐
│  INPUT: Service date, restaurant context        │
└─────────────────┬───────────────────────────────┘
                  │
    ┌─────────────┴─────────────┐
    │                           │
    ▼                           ▼
┌─────────────┐         ┌─────────────────┐
│ RAG Search  │         │ Time Series     │
│ (Qdrant)    │         │ (Exp. Smooth.)  │
│             │         │                 │
│ Context-    │         │ Trend +         │
│ similar     │         │ Seasonality     │
│ patterns    │         │ adjustment      │
└──────┬──────┘         └────────┬────────┘
       │                         │
       └──────────┬──────────────┘
                  │
                  ▼
        ┌─────────────────┐
        │ ENSEMBLE        │
        │                 │
        │ RAG weight: 70% │
        │ TS weight:  30% │
        └────────┬────────┘
                 │
                 ▼
        ┌─────────────────┐
        │ OUTPUT          │
        │ 145 covers      │
        │ ±12 (interval)  │
        │ MAPE: 11.2%     │
        └─────────────────┘
```

**Why 70/30 split:**
- RAG captures context (event nearby = +15%)
- Time series captures trend (covers trending up 3% weekly)
- Context is primary driver in F&B (a concert matters more than a 3% trend)

---

## Implementation Roadmap

| Phase | Scope | Effort | Dependency |
|-------|-------|--------|------------|
| **Now** | Documentation (this file) | ✅ Done | None |
| **Next** | Add MAPE calculation to response | 2h | Real prediction logs |
| **Later** | Exponential smoothing baseline | 4h | Time series data |
| **Future** | Hybrid ensemble model | 8h | Both above |

**Blocking factor:**
MAPE implementation requires real predictions vs actual outcomes. Current data (Kaggle-derived) cannot provide this. Options:
- Wait for design partner (real hotel data)
- Simulate actuals with variance (artificial, not recommended)
- Document methodology, implement when data available ✅

---

## Key Takeaways for Portfolio

- ✅ RAG is complementary, not competing with traditional forecasting
- ✅ MAPE < 15% is the industry benchmark to target
- ✅ Explainability differentiates from black-box competitors
- ✅ Hybrid approach combines best of both worlds
- ⚠️ Implementation blocked by lack of real prediction history

---

## References

- Mews Revenue Management Documentation
- "Hotel Revenue Management" (Cross, 2011)
- Kikleo, Ailean, Guac AI public documentation
- "Forecasting: Principles and Practice" (Hyndman & Athanasopoulos)
- STR Industry Reports on F&B forecasting

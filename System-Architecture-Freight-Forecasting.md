# System Architecture
## Intelligent Freight Forecasting Model — SIH 2026

**Version:** 0.1 (builds on SRS v0.1)
**Scope of this document:** Components, data flow, and technology choices with reasoning. No database schema or API contracts yet — that's next.

---

## 1. Architectural Style: Clean / Layered Architecture

Four layers, each depending only on the layer beneath it — nothing in the domain logic knows about FastAPI or Postgres, so the forecasting logic can be tested and swapped independently of the web framework.

```
┌─────────────────────────────────────────────────┐
│  Presentation Layer                              │
│  React dashboard, PDF/CSV export                 │
├─────────────────────────────────────────────────┤
│  API Layer                                       │
│  FastAPI endpoints, request/response models      │
├─────────────────────────────────────────────────┤
│  Domain / Application Layer                      │
│  Forecasting service, Vessel-matching service,    │
│  Timing-recommendation service, Risk-alert service│
├─────────────────────────────────────────────────┤
│  Infrastructure Layer                            │
│  Postgres repository, data ingestion jobs,       │
│  trained model artifacts                         │
└─────────────────────────────────────────────────┘
```

**Why this matters for a hackathon, not just in theory:** judges and future extension both benefit from the forecasting logic (the actual "intelligence" in "Intelligent Freight Forecasting Model") being isolated from the web plumbing — you can demo the core model in a Jupyter notebook using the exact same service classes the API calls, which is useful both for your own debugging and for explaining the solution to evaluators.

---

## 2. Components

### 2.1 Data Ingestion Component
**Responsibility:** Pull in the Kaggle BDI/sub-index historical dataset, apply the synthetic route-adjustment layer, and populate the historical freight-rate table. Also loads the manually-compiled port-constraints reference data (draft/LOA/beam/handling rate for the 3 MVP ports).

**Why a separate component:** this is the part most likely to change (swap in real licensed data later, add more ports) — isolating it means that change never touches the forecasting logic.

### 2.2 Forecasting Service
**Responsibility:** For a given route + vessel class, produce a 60-day freight-rate forecast with a confidence interval (FR-2).

**Model choice and reasoning (scientific concept before implementation):**
- **Prophet (primary):** Freight rates exhibit trend + strong seasonality (shipping demand cycles with commodity/harvest seasons) + irregular shocks (fuel price spikes, geopolitical events). Prophet is an additive decomposition model — it explicitly separates `trend + seasonality + holiday/event effects + residual` — which fits this structure directly and, critically, produces interpretable uncertainty intervals out of the box. That interpretability matters for FR-2.2 (confidence bands) and NFR-4 (non-technical users).
- **XGBoost (secondary/ensemble):** Gradient-boosted trees model the *nonlinear interactions* Prophet's additive structure misses — e.g., how a fuel price spike combined with a specific season affects rates differently than either alone. It also lets us fold in cross-sectional features (port congestion score, commodity price index) that Prophet doesn't naturally use as regressors.
- **Why not a pure LSTM:** LSTMs need substantially more training data than a hackathon-scope dataset (12 route-class combinations, a few years of history) reliably supports, and they sacrifice the interpretability that a chartering manager needs to trust a recommendation. Worth revisiting only if you scale to the full 5×7×4 route matrix with several years of granular data later.
- **Final forecast = weighted ensemble of the two**, weighted by each model's recent backtest accuracy per route (so the ensemble adapts if one model works better for a specific route).

### 2.3 Vessel-Matching Service
**Responsibility:** Given cargo volume + origin/destination port constraints, determine the largest feasible vessel class (FR-3).

**This is a constraint-satisfaction problem, not a ML problem** — deliberately kept rule-based: compare cargo volume against each vessel class's typical DWT range, then filter out any class whose draft/LOA/beam exceeds either port's limits. Simpler, fully explainable, and doesn't need training data — appropriate because port physical limits are hard constraints, not a hasty pattern to learn from a small dataset.

### 2.4 Timing-Recommendation Service
**Responsibility:** Scan the Forecasting Service's 60-day output for the route/vessel-class combination and rank the lowest-cost entry windows (FR-4).

Built on top of the Forecasting Service's output — it doesn't forecast anything itself, it just ranks the already-produced forecast curve. Keeping it a thin layer over the Forecasting Service avoids duplicating forecasting logic.

### 2.5 Risk Alert Service
**Responsibility:** Flag high-uncertainty forecasts and known port congestion (FR-6). For the MVP, congestion data is a static/periodically-updated reference value per port rather than a live feed (per the SRS's phased scope decision), with the live feed noted as a post-MVP upgrade path.

### 2.6 Presentation Layer
React dashboard consuming the API layer; renders forecast charts (with confidence bands), the recommended vessel class, ranked timing windows, and any active alerts, per FR-7.

---

## 3. Data Flow (single query)

```
User enters cargo/route/duration on dashboard
        │
        ▼
API layer validates input against known routes (FR-1.2)
        │
        ▼
Forecasting Service generates 60-day rate forecast (Prophet + XGBoost ensemble)
        │
        ├──► Timing-Recommendation Service ranks entry windows
        │
        ├──► Risk Alert Service checks forecast uncertainty + port congestion reference
        │
Vessel-Matching Service (runs independently, needs only cargo + port data, not the forecast)
        │
        ▼
API layer assembles: forecast chart data + recommended vessel + ranked windows + alerts
        │
        ▼
Dashboard renders result; user can export (FR-7.3)
```

Vessel-matching is deliberately drawn as independent of the forecast — it only needs static port/cargo data, so it can run in parallel with forecasting rather than waiting on it, keeping the interactive response time down (NFR-1).

---

## 4. Technology Stack (with reasoning)

| Layer | Choice | Why |
|---|---|---|
| Backend framework | FastAPI (Python) | Async-friendly, automatic OpenAPI docs (useful for your team dividing API work), and Python keeps the API layer in the same language as the ML services — no serialization boundary between "the model" and "the app" |
| Forecasting | Prophet + XGBoost (scikit-learn ecosystem) | See §2.2 |
| Database | PostgreSQL | Relational structure fits well-defined entities (ports, routes, forecasts logged); good time-series query support for the historical rate table |
| Frontend | React + a charting library (e.g., Recharts) | Confidence-band charts and side-by-side comparisons (FR-7.2) are straightforward with a component-based charting library |
| Deployment (demo) | Single-instance deploy (e.g., Render/Railway free tier, or local for the demo) | Hackathon scope doesn't need production-grade infra; architecture doesn't preclude it later (NFR-6/7) |

---

## 5. How This Maps Back to Non-Functional Requirements

- **NFR-6 (extensibility):** New ports/origins are new rows in the port-constraints and route-adjustment tables, not new code paths — both the Forecasting Service and Vessel-Matching Service are written generic-over-route/port.
- **NFR-7 (clean architecture/testability):** Each service in §2 is a plain Python class with a defined interface, independently unit-testable without spinning up FastAPI or a database (use an in-memory fake repository in tests).
- **NFR-5 (graceful degradation):** If the congestion reference data is stale/missing for a port, Risk Alert Service should return "no congestion data available" rather than silently omitting the alert — this becomes an explicit requirement for the module breakdown stage.

---

## 6. What's Next

Once you're happy with this shape, the next stage is the **database schema** — tables for routes, ports, historical rates, forecasts-log, and vessel classes — followed by **API design** (endpoint contracts), then **module/class breakdown** with testing strategy, and finally the **implementation roadmap** you can turn into a GitHub project board for your team.

Flag anything above you want changed before we move on — especially if your team has opinions on Prophet/XGBoost vs. something else, since that choice ripples into the schema (what gets logged per forecast) and the module breakdown.

# CargoNex

**Intelligent Freight Forecasting Model for Optimized Vessel Chartering and Bulk Cargo Procurement**

Smart India Hackathon 2026 · Problem Statement 26006 · Theme: Transportation & Logistics

---

## 1. Executive Summary

CargoNex replaces the current reactive, daily spot-market approach to chartering bulk carrier vessels for coal and dry-bulk cargo movement from overseas origins (Australia, Indonesia) to India's East Coast ports with a data-driven, predictive system. It combines freight-rate forecasting, port-constraint-aware vessel matching, and market-timing recommendations into a single decision-support tool for logistics managers.

Unlike a purely conceptual proposal, the core forecasting and decision logic described in this report has already been implemented and is covered by an automated test suite of **45 passing tests**, with a working REST API demonstrated end-to-end. This repository contains that implementation.

## 2. Problem Statement

Vessel chartering decisions for bulk cargo bound for East Coast Indian ports (Paradip, Vizag, Gangavaram, Gopalpur, Dhamra, Sagar-Sandheads, Haldia) are currently made through daily, reactive engagement with the freight market. This leads to missed cost-saving opportunities, no systematic way to match vessel size to a specific cargo lot and port's physical constraints (draft, LOA, beam), and avoidable vessel idle time from poor turnaround planning.

## 3. Proposed Solution

- **Rate Forecasting** — predicts freight rates ahead of time using historical Baltic Dry Index data, so chartering decisions are planned rather than reactive.
- **Vessel-Port Matching** — recommends the largest vessel class that both suits the cargo volume and physically fits both the origin and destination port's draft, LOA, and beam limits.
- **Market Entry Timing** — ranks non-overlapping windows in the forecast horizon by predicted cost, so a logistics manager can choose when to commit to a charter.
- **Risk Alerts** — flags elevated forecast uncertainty and port congestion, including an explicit "data unavailable" alert when congestion data is missing or stale, rather than silently omitting a warning.

## 4. Technical Approach

### 4.1 Forecasting Model

The forecasting service combines two models in a residual-correction ensemble: **Prophet** fits trend and yearly seasonality (freight demand has a genuine annual cycle tied to commodity and harvest seasons), and **XGBoost** is trained on Prophet's residuals using lag features to capture nonlinear effects Prophet's additive structure misses. Critically, the XGBoost residual correction is only used in the final forecast if backtesting on held-out historical data shows it actually reduces error — it is not assumed to help by default.

### 4.2 Vessel Matching

Vessel-class recommendation is deliberately rule-based rather than machine-learned, since port physical limits are hard constraints, not statistical patterns. The algorithm anchors on the cargo's natural vessel class (the smallest class whose capacity covers the cargo volume) and only steps down to a smaller class when a port's draft, LOA, or beam forces it — it never recommends a larger class than necessary, since that would waste chartered capacity.

### 4.3 System Architecture

The system follows a clean/layered architecture:

```
Presentation layer   → React dashboard
API layer            → FastAPI REST endpoints
Application layer    → 4 independent services (Forecasting, Vessel Matching,
                        Timing Recommendation, Risk Alerts) + Query Orchestrator
Infrastructure layer → SQLAlchemy repositories, Prophet/XGBoost model wrappers
```

Each layer depends only on the layer beneath it through abstract interfaces, which is what makes every service independently unit-testable without a database or web framework.

## 5. Feasibility and Viability

- Core data (Baltic Dry Index historical rates, port authority specifications) is publicly or commercially available — no novel data-collection barrier.
- Prophet and XGBoost are proven, production-grade time-series techniques; the technology risk is in data integration and tuning, not in unproven methods.
- Market volatility is mitigated by presenting confidence intervals rather than single-point forecasts, so uncertainty is visible rather than hidden.
- A phased rollout — starting with a small set of high-volume routes before scaling — keeps real-time data licensing costs manageable early on.

## 6. Impact and Benefits

Estimated impact of moving from reactive spot chartering to the CargoNex approach (illustrative figures based on the system's design goals, to be validated against real operational data during pilot deployment):

| Metric | Before (Reactive Spot Chartering) | After (CargoNex) |
|---|---|---|
| Freight cost index (illustrative, 100 = baseline) | 100 | ~88 (est. 12% reduction via optimal entry timing) |
| Average vessel idle time per voyage | ~4.5 days | ~2.0 days (est., via port-constraint-aware vessel matching) |
| Planning lead time / market visibility | 0 days (same-day spot decision) | 60 days (forecast horizon with confidence intervals) |
| Risk visibility before committing to a charter | None — manual judgment only | Explicit volatility + congestion alerts |

- **Economic** — reduced freight costs via optimally timed charters; fewer demurrage penalties from correct vessel-port matching.
- **Operational** — shift from reactive daily spot chartering to planned short/mid-term voyage contracts.
- **Environmental** — less idle and deadhead sailing reduces fuel consumption and emissions per tonne of cargo moved.
- **Strategic** — strengthens the reliability of coal and bulk imports into East Coast India, directly relevant to the power and steel sectors that depend on them.

## 7. Current Implementation Status

The following components are already built and verified with automated tests, not just designed on paper:

| Component | Status |
|---|---|
| Data ingestion (BDI CSV parsing + validation) | Implemented, unit-tested (9 tests) |
| Forecasting service (Prophet + XGBoost residual ensemble) | Implemented, backtested, unit-tested (5 tests) |
| Vessel matching (port-constraint-aware) | Implemented, unit-tested (12 tests, shared w/ timing) |
| Timing recommendation (non-overlapping windows) | Implemented, unit-tested |
| Risk alerts (volatility + congestion, graceful degradation) | Implemented, unit-tested (10 tests) |
| Query orchestration (end-to-end pipeline) | Implemented, unit-tested (3 tests) |
| REST API (FastAPI) + database (SQLAlchemy) | Implemented, integration-tested (6 tests) |
| **Total automated test suite** | **45/45 passing (39 unit + 6 integration)** |
| Real Kaggle dataset integration | Pending — placeholder synthetic data in use for demo |
| Frontend dashboard | Not yet built |

See the `README.md` in this repository for setup instructions, how to run the test suite, and how to boot the live API locally.

## 8. References

- Baltic Exchange — Baltic Dry Index and route-specific freight rate historical data.
- Clarksons Research — Shipping Intelligence Network, vessel and freight market data.
- Indian Ports Association and individual port authority websites — draft, LOA, and berth specifications.
- UNCTAD Review of Maritime Transport — global trade lane and dry bulk demand trends.
- Academic literature on time-series forecasting (LSTM, Prophet) applied to freight rate prediction.
- AIS vessel tracking data providers (e.g., MarineTraffic) for real-time positioning reference.

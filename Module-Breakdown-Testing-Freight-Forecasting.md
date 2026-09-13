# Module Breakdown & Testing Strategy
## Intelligent Freight Forecasting Model — SIH 2026

**Version:** 0.1 (builds on API Design v0.1)
**Scope of this document:** Concrete Python module/class structure and how each piece gets tested. Next stage after this is the GitHub board and roadmap.

---

## 1. Design Principle: Depend on Interfaces, Not on Postgres or FastAPI

This is what makes NFR-7 ("independently unit-testable without spinning up FastAPI or a database") actually true rather than aspirational. Every application-layer service takes **repository interfaces** (Python `Protocol` classes — structural typing, no inheritance needed) as constructor arguments, never a concrete SQLAlchemy session directly. In tests, you hand it an in-memory fake instead of a real database; in production, FastAPI's dependency injection hands it the real repository. Same service code, zero test infrastructure needed for the majority of tests.

This single decision is *why* the architecture doc's four-layer split (§1 of that doc) pays off in practice rather than being a diagram nobody follows.

---

## 2. Folder Structure

```
freight_forecasting/
├── domain/
│   ├── models.py            # plain dataclasses: Port, VesselClass, Route, Forecast,
│   │                          ForecastPoint, TimingWindow, RiskAlert, Query
│   └── enums.py              # DurationType, AlertType, Severity, PortRole
│
├── application/               # the "intelligence" — framework-agnostic
│   ├── interfaces/            # Protocol classes the services depend on
│   │   ├── port_repository.py
│   │   ├── route_repository.py
│   │   ├── rate_repository.py
│   │   ├── forecast_repository.py
│   │   └── query_repository.py
│   ├── forecasting_service.py
│   ├── vessel_matching_service.py
│   ├── timing_recommendation_service.py
│   ├── risk_alert_service.py
│   └── query_orchestrator.py  # coordinates the four services per §3 of API design
│
├── infrastructure/
│   ├── db/
│   │   ├── orm_models.py      # SQLAlchemy models, mirrors the schema doc's tables
│   │   ├── session.py
│   │   └── repositories/      # concrete implementations of application/interfaces/*
│   ├── ml/
│   │   ├── prophet_model.py
│   │   ├── xgboost_model.py
│   │   └── ensemble.py        # combines the two per architecture §2.2
│   └── ingestion/
│       ├── kaggle_loader.py       # pulls + cleans the base BDI dataset
│       └── route_adjustment.py    # applies route_adjustment_factors → route_freight_rates
│
├── api/
│   ├── routers/                # one file per resource from the API design doc
│   │   ├── ports.py
│   │   ├── vessel_classes.py
│   │   ├── routes.py
│   │   ├── queries.py
│   │   ├── export.py
│   │   └── admin.py
│   ├── schemas/                # Pydantic request/response models (mirror API doc JSON exactly)
│   └── dependencies.py         # DB session + auth injection
│
└── tests/
    ├── unit/                   # application/ tested against fakes — no DB, no network
    ├── integration/            # API endpoints tested against a real (test) DB
    └── fixtures/                # shared small synthetic datasets
```

---

## 3. Key Classes and Responsibilities

### 3.1 `ForecastingService`
```
class ForecastingService:
    def __init__(self, rate_repo: RateRepositoryProtocol, prophet: ProphetModel, xgb: XGBoostModel):
        ...
    def generate_forecast(self, route_id: int, vessel_class_id: int, horizon_days: int = 60) -> Forecast:
        # 1. pull historical route_freight_rates via rate_repo
        # 2. fit/predict with both models
        # 3. combine via weighted ensemble (weights = recent backtest accuracy per route)
        # 4. return Forecast domain object (not yet persisted — orchestrator persists)
```
Depends only on `RateRepositoryProtocol` and the two model wrappers — never touches the API layer or knows a Forecast will eventually become JSON.

### 3.2 `VesselMatchingService`
```
class VesselMatchingService:
    def __init__(self, vessel_repo: VesselClassRepositoryProtocol, port_repo: PortRepositoryProtocol):
        ...
    def recommend_vessel(self, cargo_volume_tonnes: int, origin_port_id: int, destination_port_id: int) -> VesselRecommendation:
        # pure constraint-satisfaction, no ML — deterministic, so this is the easiest module to
        # get to 100% test coverage on, and a good one to demo live if judges ask "how does it decide?"
```

### 3.3 `TimingRecommendationService`
```
class TimingRecommendationService:
    def rank_windows(self, forecast: Forecast, window_size_days: int = 5, top_n: int = 3) -> list[TimingWindow]:
        # scans forecast.points for the lowest-average-rate windows of window_size_days
        # pure function of a Forecast — no repository dependency at all
```
Worth noting: this class needs **no constructor dependencies** — it's a pure function over data it's handed. That makes it the simplest possible unit test (no fakes needed, just construct a `Forecast` object and assert on the output).

### 3.4 `RiskAlertService`
```
class RiskAlertService:
    def __init__(self, port_repo: PortRepositoryProtocol):
        ...
    def evaluate(self, route: Route, forecast: Forecast) -> list[RiskAlert]:
        # checks: (a) forecast band width vs. volatility threshold
        #         (b) port.congestion_score vs. threshold, or 'data_unavailable' alert
        #             if port.congestion_updated_at is stale (implements NFR-5 explicitly)
```

### 3.5 `QueryOrchestrator`
```
class QueryOrchestrator:
    def __init__(self, route_repo, forecasting_service, vessel_matching_service,
                 timing_service, risk_service, query_repo):
        ...
    async def handle_query(self, request: QueryRequest) -> QueryResult:
        # 1. validate route exists (route_repo) -> raise RouteNotFoundError if not (maps to API's 422)
        # 2. run forecasting_service.generate_forecast(...) and
        #    vessel_matching_service.recommend_vessel(...) concurrently (asyncio.gather) —
        #    they don't depend on each other, per the architecture doc's parallel data flow
        # 3. once forecast is ready: timing_service.rank_windows(forecast), risk_service.evaluate(...)
        # 4. persist Query + Forecast via query_repo/forecast_repo
        # 5. assemble and return QueryResult
```
This class is the direct implementation of `POST /queries` from the API design doc — the router in `api/routers/queries.py` is a thin wrapper that calls this and translates exceptions to HTTP status codes. Keeping the orchestration logic here (not in the router) means it's unit-testable without an HTTP layer at all.

---

## 4. Testing Strategy

### 4.1 Test Pyramid for This Project

```
        ▲  a few end-to-end smoke tests (API doc's example flows, via TestClient)
       ╱ ╲
      ╱   ╲  integration tests (routers + real test-DB, one per endpoint's success/error cases)
     ╱─────╲
    ╱       ╲  unit tests (every application/ service, against fakes — the bulk of the suite)
   ╱─────────╲
```

Most of your test count should be at the bottom — they're fast, need no DB, and are what actually lets you refactor the forecasting model later without fear.

### 4.2 Unit Tests — Deterministic Modules (test to exact values)
- `VesselMatchingService`: table-driven tests — for each (cargo_volume, origin constraints, destination constraints) input, assert the exact expected vessel class and that the `reason` string names the binding constraint. Easy to get to full coverage since it's pure logic.
- `TimingRecommendationService`: construct a `Forecast` with a known synthetic curve (e.g., a clear dip at day 15), assert the top-ranked window covers that dip.
- `RiskAlertService`: test each branch explicitly — high volatility, high congestion, and (important, often forgotten) the `data_unavailable` branch when `congestion_updated_at` is stale.

### 4.3 Unit Tests — ML Module (test structure and sanity, not exact numbers)
Forecasting output isn't deterministic to the decimal, so don't assert exact predicted values. Instead assert:
- Output has exactly `horizon_days` points.
- `lower_bound <= predicted_rate <= upper_bound` for every point (a violated bound is a real bug, not model noise).
- **Backtest check:** hold out the last 60 days of historical data, forecast over that period using only earlier data, and assert the error metric (e.g., MAPE) is below an agreed threshold. This is your actual evidence the model works — worth having a script your team runs before the demo, not just a CI check, so you can quote a real accuracy number to judges (directly satisfies NFR-2).

### 4.4 Integration Tests
One test class per router, using FastAPI's `TestClient` against a test database (SQLite in-memory is fine for CI speed; Postgres for anything using its specific features):
- `POST /queries` — happy path returns 201 with all four sections populated; unknown route returns 422 with a `reason`; invalid cargo volume returns 400.
- `PUT /ports/{id}` — succeeds with admin token, 403 with a non-admin token, 401 with no token.
- `GET /queries/{id}/export` — both format values return the correct content-type.

### 4.5 What NOT to Over-Test (given hackathon time constraints)
- Don't write exhaustive tests for the Pydantic schema layer itself — it's declarative, FastAPI validates it, low bug risk.
- Don't test the Kaggle ingestion script's exact numeric output against the live dataset (it'll change over time) — test that it produces the right *shape* (correct columns, no nulls) from a small fixture CSV instead.

---

## 5. What's Next

Next and final planning stage: **GitHub project board + implementation roadmap** — turning everything above into issues/milestones your team can actually assign and check off, sequenced so you have a demoable product well before the deadline rather than everything landing at once the night before.

One thing to decide before I lay out the roadmap: **how many teammates, and does anyone already have a role preference** (e.g., someone keen on the ML side vs. someone who'd rather own the frontend)? That changes how I'd split the issues.

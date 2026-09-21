# CargoNex — Milestones 1–5: Full End-to-End Query Pipeline

This is the milestone the roadmap called your **minimum viable demo**:
a single call now runs forecasting, vessel matching, timing, and risk
alerts together and returns one composite result — the same shape
`POST /queries` will return once the FastAPI layer is added on top.

## What's here

```
domain/
  enums.py     — VesselClass, PortRole, DurationType, AlertType, Severity
  models.py    — all domain dataclasses, including Route, QueryResult,
                 RouteNotFoundError (see "Milestone 5" section below)
application/
  interfaces/
    rate_repository.py         — Protocol for ForecastingService
    route_repository.py        — Protocol for route lookup (FR-1.2)
    port_repository.py         — Protocol for port constraint lookup
    vessel_class_repository.py — Protocol for vessel class specs
  forecasting_service.py            — pulls history, fits ensemble, returns a Forecast
  vessel_matching_service.py        — FR-3: natural_vessel_class() + recommend_vessel()
  timing_recommendation_service.py  — FR-4: pure ranking of non-overlapping low-rate windows
  risk_alert_service.py             — FR-6: volatility + congestion alerts, NFR-5 graceful degradation
  query_orchestrator.py             — wires all four together; IS the POST /queries logic
infrastructure/ingestion/
  kaggle_loader.py     — parses a wide-format BDI CSV into BaseIndexValue objects
  route_adjustment.py  — applies the synthetic route-adjustment transform
infrastructure/ml/
  prophet_model.py, xgboost_residual_model.py, ensemble.py — see Milestone 2 notes below
tests/
  fixtures/sample_bdi.csv, synthetic_data.py
  unit/test_ingestion.py              — 9 tests
  unit/test_forecasting_service.py    — 5 tests
  unit/test_vessel_and_timing.py      — 12 tests
  unit/test_risk_alerts.py            — 10 tests
  unit/test_query_orchestrator.py     — 3 tests (full end-to-end flow)
```

**39/39 tests passing.** Run them yourself:
```bash
pip install -r requirements.txt
python -m pytest tests/ -v
```

## The design conflict this milestone had to resolve

The architecture doc claimed forecasting and vessel-matching run
independently in parallel. That's not quite true as originally drawn: a
`Forecast` is keyed by `(route, vessel_class)`, and vessel-matching is
what determines the vessel class — so naively, forecasting would have to
wait for the full recommendation.

The fix, implemented in `vessel_matching_service.natural_vessel_class()`:
split "which vessel class is this cargo's natural market segment"
(computable from cargo volume alone, no ports needed) from "which class
can actually be chartered given port constraints" (needs ports, may step
down). The forecast runs against the **natural class**; the full
port-aware recommendation runs separately; both now genuinely don't
depend on each other and run concurrently via `asyncio.gather` in
`QueryOrchestrator`.

**When a port constraint forces a smaller final vessel than the natural
class the forecast used, `QueryResult.forecast_vessel_class_note` says so
explicitly** — see `test_forecast_vessel_class_note_appears_when_port_forces_stepdown`
for the exact scenario. This was a deliberate call to surface a real
mismatch rather than let a user notice the forecast and recommendation
reference different vessel classes with no explanation.

## Risk alerts: the NFR-5 branch that's easy to forget

`risk_alert_service.evaluate()` checks volatility (from the forecast's
own confidence interval width) and congestion (from each port's stored
reference score). Missing or stale congestion data produces its own
`data_unavailable` alert, not silence — see
`test_missing_congestion_score_produces_data_unavailable_not_silence`
and `test_stale_congestion_data_produces_data_unavailable`.

## Vessel matching: one design decision worth understanding

`recommend_vessel()` anchors on the cargo's **natural** vessel class and
never recommends a *larger* class than that, even if a bigger vessel
could also physically carry the cargo — chartering a Capesize for a
70,000t parcel wastes paid-for capacity. It steps DOWN (never up) only
when a port forces it, flagging the result `is_constrained=True` with
the specific binding constraint named.

## Timing windows: non-overlapping by design

Three top-ranked windows that all cover the same days would be one real
option presented three times, not three genuinely different choices.

## How the forecasting actually works

1. **Prophet** fits trend + yearly seasonality on the historical rate series.
2. **XGBoost** is trained on Prophet's *residuals*, using lag features —
   correcting what Prophet missed, not re-forecasting from scratch.
3. **The residual correction is only used if backtesting shows it helps**
   on held-out data — `EnsembleForecastModel.fit()` returns a
   `BacktestResult` with both MAPE numbers.
4. Minimum 180 days of history required to fit at all.

**Known limitation worth stating out loud:** Prophet warns when yearly
seasonality is fit on under ~2 years of training data. If your real
Kaggle dataset is shorter, mention this proactively if asked.

## Getting the real dataset

1. Search Kaggle for **"Baltic Dry Index"** or **"Baltic Exchange"**.
   Prefer a dataset with the four sub-indices as separate columns.
2. Download the CSV into `data/raw/` (git-ignored — see below).
3. Match your CSV's actual column names in `column_map`.
4. Run `route_adjustment.py` for each of your 12 MVP route/vessel-class
   combinations.
5. Compile real port constraints (draft/LOA/beam, congestion score +
   last-updated timestamp) into `Port` objects, and real route data into
   `Route` objects — the test fixtures are illustrative placeholders.

## A note on `.gitignore`

```
data/raw/*.csv
__pycache__/
*.pyc
.pytest_cache/
```

## Next milestone

The application layer is now feature-complete and fully tested with
in-memory fakes. What's left is **infrastructure**: real SQLAlchemy
repositories implementing the four Protocol interfaces against Postgres
(per Schema v0.1), then the FastAPI routers from API Design v0.1 that
call `QueryOrchestrator`. At that point the web layer is genuinely thin
plumbing around logic that's already built and tested — which is the
whole point of having kept them separate this whole time.





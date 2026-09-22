# CargoNex — Full Stack: Ingestion → Forecasting → Services → API → Dashboard

This is a **running system end to end**, not just tested logic —
`main.py` boots a real FastAPI app backed by a real (SQLite by default)
database, and `frontend/` is a real React dashboard that talks to it.
See "Running it for real" below for the exact commands that produced a
real 201 response with a 60-point forecast, and `frontend/README.md`
for the dashboard.

## What's here

```
domain/            — all domain dataclasses and errors (framework-free)
application/        — the 4 services + QueryOrchestrator + Protocol interfaces
infrastructure/
  ingestion/         — kaggle_loader.py, route_adjustment.py (still needs real Kaggle data)
  ml/                — Prophet + XGBoost residual ensemble
  db/
    orm_models.py     — SQLAlchemy models for ports, vessel_classes, routes, route_freight_rates
    session.py         — engine/session setup (SQLite by default, Postgres via DATABASE_URL)
    seed.py            — populates placeholder demo data so the API runs immediately
    repositories/       — SqlAlchemy{Port,VesselClass,Route,Rate}Repository —
                          concrete implementations of the application layer's Protocols
api/
  routers/             — ports.py, vessel_classes.py, routes.py, queries.py
  schemas/             — Pydantic request/response models
  dependencies.py       — wires repositories + services + orchestrator per-request
frontend/               — React 18 + Vite + Tailwind + Recharts dashboard (FR-7).
                          See frontend/README.md for setup and a real CORS bug
                          this build caught in main.py.
main.py                — FastAPI app assembling everything above
tests/
  unit/                — 39 tests, all against in-memory fakes, no DB needed
  integration/test_api.py — 6 tests, real FastAPI app + real in-memory SQLite DB
```

**45/45 tests passing** (39 unit + 6 integration).
```bash
pip install -r requirements.txt
python -m pytest tests/ -v
```

## Running it for real

```bash
python -m infrastructure.db.seed        # creates cargonex.db, seeds placeholder data
python -m uvicorn main:app --reload     # starts the API on http://127.0.0.1:8000
```

Then:
```bash
curl http://127.0.0.1:8000/ports
curl -X POST http://127.0.0.1:8000/queries -H "Content-Type: application/json" -d '{
  "cargo_volume_tonnes": 70000,
  "origin_port_id": "AUS_NEWCASTLE",
  "destination_port_id": "IN_PARADIP",
  "horizon_days": 60
}'
```

This exact flow was run and verified while building this milestone — a
real HTTP 201 with a genuine Prophet+XGBoost forecast, not a mock.

## A real bug this milestone caught (worth understanding, not just fixing)

SQLite doesn't preserve timezone info on stored datetimes — a value
written as UTC-aware comes back **naive** on read. `RiskAlertService`
compares `congestion_updated_at` against a timezone-aware "now", so this
surfaced as a `TypeError` the moment integration tests hit a real DB —
something the unit tests (which only ever used in-memory Python objects,
never round-tripped through SQLite) could never have caught. Fixed at
the repository boundary (`SqlAlchemyPortRepository._to_domain`), which
is the right layer for a persistence-format quirk — the domain and
application layers never need to know which DB backend introduced it.
This is exactly why integration tests exist alongside unit tests: they
catch a different category of bug.

## Known, honest gaps (not silently dropped — deliberately deferred)

- **FR-8.3 (log every forecast/query)**: not yet persisted. `forecasts`,
  `forecast_points`, `recommended_timing_windows`, `risk_alerts`, and
  `queries` tables from Schema v0.1 aren't implemented — the current API
  computes everything live per-request and returns it, but doesn't save
  it. Add these the same way as the four existing tables (ORM model +
  repository) when you need query history.
- **Admin endpoints, export, comparison** (API Design v0.1 §4/§5/§6):
  not built. Confirm with your team whether comparison is launch-scope
  before prioritizing it (per the roadmap's open question).
- **Frontend polish**: the dashboard (`frontend/`) is functional and
  talks to the real API, but has no loading skeleton and no comparison
  view — see `frontend/README.md`'s "Known gaps".
- **Ingestion is still placeholder data** (`infrastructure/db/seed.py`'s
  synthetic generator), not the real Kaggle dataset — see "Getting the
  real dataset" below.
- **Pydantic validation returns 422** for a bad cargo volume, where API
  Design v0.1 originally specified 400 — a minor, documented deviation
  from the spec (FastAPI's default for request validation errors),
  not worth fighting the framework's convention over for a hackathon.

## Risk alerts: the NFR-5 branch that's easy to forget

Missing or stale congestion data produces its own `data_unavailable`
alert, not silence — see `test_missing_congestion_score_produces_data_unavailable_not_silence`
and `test_stale_congestion_data_produces_data_unavailable`.

## Vessel matching: one design decision worth understanding

`recommend_vessel()` anchors on the cargo's **natural** vessel class and
never recommends a *larger* class than that, stepping DOWN (never up)
only when a port forces it. See `test_never_recommends_larger_than_natural_class`
and `test_steps_down_when_destination_port_is_shallow`.

## The forecasting/vessel-class split (why QueryOrchestrator looks the way it does)

A `Forecast` needs a vessel class before it can run, but the full
port-aware vessel recommendation is what determines that class — so
they can't be naively parallel. The fix: `natural_vessel_class()` (cargo
volume only) decides which class's rates to forecast; the full
`recommend_vessel()` (needs ports) runs separately; when they disagree
(a port forced a step-down), `QueryResult.forecast_vessel_class_note`
says so explicitly rather than leaving the mismatch unexplained.

## How the forecasting actually works

1. **Prophet** fits trend + yearly seasonality.
2. **XGBoost** is trained on Prophet's *residuals* using lag features.
3. **The residual correction is only kept if backtesting shows it helps**
   — `EnsembleForecastModel.fit()` returns a `BacktestResult` with both
   MAPE numbers.
4. Minimum 180 days of history required to fit at all.

**Known limitation:** Prophet warns when yearly seasonality is fit on
under ~2 years of training data. Mention this proactively if your real
dataset is shorter and a judge asks about accuracy.

## Getting the real dataset

1. Search Kaggle for **"Baltic Dry Index"** or **"Baltic Exchange"**,
   preferring a dataset with the four sub-indices as separate columns.
2. Download into `data/raw/` (git-ignored).
3. Match column names in `column_map` passed to `load_base_index_csv()`.
4. Run `route_adjustment.py`'s `apply_route_adjustment()` for your real
   route/vessel-class combinations, and write a real seed/loader script
   that inserts the results into `route_freight_rates` (replacing
   `infrastructure/db/seed.py`'s placeholder generator).
5. Compile real port constraints and route data to replace the
   illustrative values in `seed.py`.

## Next steps (genuinely optional at this point)

The system works end-to-end, backend and frontend both. From here it's
refinement, not new architecture: real Kaggle data, the deferred
persistence tables (FR-8.3's query/forecast logging), and admin/export
endpoints if your team decides they're in scope for the demo.






# Database Schema
## Intelligent Freight Forecasting Model — SIH 2026

**Version:** 0.1 (builds on Architecture v0.1)
**Scope of this document:** Table definitions, relationships, and the reasoning behind normalization choices. No API contracts yet — that's next.

---

## 1. Design Principle: Separate "Real Signal" from "Derived/Route-Specific" Data

This is the single most important modeling decision here, so it's worth stating explicitly before the tables: the **real free data** (Kaggle-sourced BDI sub-indices) is *global*, not route-specific — it's one number per vessel class per day, independent of which port pair you're shipping between. The **synthetic route adjustment** is what turns that global signal into a route-specific series.

If these two are mixed into one table, you lose the ability to tell a judge (or your future self) "here's the real data, here's what we derived" — which matters both for scientific honesty and for debugging (if a forecast looks wrong, you can check whether the base index or the adjustment factor is the problem). So the schema keeps them as separate tables connected by a documented transformation.

---

## 2. Entity-Relationship Overview

```
vessel_classes ──┐
                 ├──< base_index_values (global, real data)
ports ──┐        │
        ├──< routes >──┐
        │              ├──< route_adjustment_factors
        │              ├──< route_freight_rates (derived, route-specific)
        │              ├──< forecasts ──< forecast_points
        │              │                        │
        │              ├──< risk_alerts          │
        │              │                        │
        └──< (as origin or destination)          │
                                                   │
queries ──< recommended_timing_windows ───────────┘
   │
   └──> resolves to one route + vessel_class + forecast
```

---

## 3. Tables

### 3.1 `ports`
One row per port, whether it's used as an origin (loading) or destination (discharge) — a single table because the same constraint fields (draft/LOA/beam) apply to both roles, and a port could theoretically appear on either side later (e.g., if scope ever expands to India-to-India moves).

| Column | Type | Notes |
|---|---|---|
| port_id | SERIAL PK | |
| name | VARCHAR(100) | e.g. "Paradip", "Newcastle" |
| country | VARCHAR(100) | |
| role | ENUM('origin','destination','both') | MVP: Australia/Indonesia ports = origin, the 3 East Coast ports = destination |
| max_draft_m | NUMERIC(5,2) | |
| max_loa_m | NUMERIC(6,2) | |
| max_beam_m | NUMERIC(5,2) | |
| cargo_handling_rate_tph | NUMERIC(8,2) | tonnes/hour, used for turnaround-time context |
| congestion_score | NUMERIC(3,2) | static/periodically-updated reference (0=clear, 1=severe), per SRS FR-6.2 phased scope |
| congestion_updated_at | TIMESTAMP | lets Risk Alert Service know if this is stale (NFR-5) |

### 3.2 `vessel_classes`
Reference table — Handysize/Supramax/Panamax/Capesize, each with the physical envelope used by the Vessel-Matching Service.

| Column | Type | Notes |
|---|---|---|
| vessel_class_id | SERIAL PK | |
| name | VARCHAR(50) | Handysize / Supramax / Panamax / Capesize |
| min_dwt | INTEGER | deadweight tonnage range this class typically covers |
| max_dwt | INTEGER | |
| typical_draft_m | NUMERIC(5,2) | used to check against a port's max_draft_m |
| typical_loa_m | NUMERIC(6,2) | |
| typical_beam_m | NUMERIC(5,2) | |

### 3.3 `routes`
One row per origin-destination pair the system covers. Explicit table (rather than just joining ports on the fly) because a route also carries route-specific metadata (distance, default commodity) that doesn't belong on either port.

| Column | Type | Notes |
|---|---|---|
| route_id | SERIAL PK | |
| origin_port_id | FK → ports | |
| destination_port_id | FK → ports | |
| commodity | VARCHAR(50) | default 'coal' for MVP scope |
| distance_nm | INTEGER | nautical miles, feeds the route-adjustment calculation |
| is_active | BOOLEAN | lets you add a route to the DB before it's "live" in the UI |

### 3.4 `base_index_values`
The real, free data: BDI sub-index values by date and vessel class, straight from the Kaggle-sourced historical dataset. Nothing route-specific lives here.

| Column | Type | Notes |
|---|---|---|
| index_value_id | SERIAL PK | |
| vessel_class_id | FK → vessel_classes | which sub-index (BCI/BPI/BSI/BHSI maps to Capesize/Panamax/Supramax/Handysize) |
| date | DATE | |
| index_value | NUMERIC(10,2) | raw index points |
| source | VARCHAR(100) | e.g. "Kaggle BDI historical dataset" — kept explicit for the honesty/documentation reason above |

### 3.5 `route_adjustment_factors`
The parameters of the synthetic layer — kept as data, not hardcoded logic, so your team can tune them without a code change (and so a judge can see the assumptions are explicit and inspectable).

| Column | Type | Notes |
|---|---|---|
| adjustment_id | SERIAL PK | |
| route_id | FK → routes | |
| vessel_class_id | FK → vessel_classes | |
| base_multiplier | NUMERIC(6,4) | scales the global index to this route's rate level (e.g., reflects distance) |
| seasonal_amplitude | NUMERIC(6,4) | how much this route's rate swings with season, relative to the base index |
| notes | TEXT | document *why* this value was chosen — important since it's a hackathon assumption, not licensed data |

### 3.6 `route_freight_rates`
The derived, route-specific historical series — `base_index_values` transformed through `route_adjustment_factors`. This is what the Forecasting Service actually trains on.

| Column | Type | Notes |
|---|---|---|
| rate_id | SERIAL PK | |
| route_id | FK → routes | |
| vessel_class_id | FK → vessel_classes | |
| date | DATE | |
| adjusted_rate_usd_per_tonne | NUMERIC(10,2) | |
| generated_at | TIMESTAMP | when this derived row was computed — lets you regenerate the whole table if you tune adjustment factors later |

### 3.7 `forecasts`
One row per forecast run (FR-8.3 requires logging every forecast). Keeps the *request context* separate from the *day-by-day points* (3.8) — a classic one-to-many split so you're not repeating route/model metadata 60 times per forecast.

| Column | Type | Notes |
|---|---|---|
| forecast_id | SERIAL PK | |
| route_id | FK → routes | |
| vessel_class_id | FK → vessel_classes | |
| generated_at | TIMESTAMP | |
| horizon_days | INTEGER | 60 for MVP, per architecture decision |
| model_version | VARCHAR(50) | e.g. "prophet_xgb_ensemble_v1" — required once you start comparing model iterations (NFR-2) |

### 3.8 `forecast_points`
The actual predicted curve, one row per day of the horizon.

| Column | Type | Notes |
|---|---|---|
| point_id | SERIAL PK | |
| forecast_id | FK → forecasts | |
| day_offset | INTEGER | 0–59 |
| predicted_rate | NUMERIC(10,2) | |
| lower_bound | NUMERIC(10,2) | confidence interval, per FR-2.2 |
| upper_bound | NUMERIC(10,2) | |

### 3.9 `recommended_timing_windows`
Output of the Timing-Recommendation Service (FR-4) for a given forecast — kept as its own table rather than recomputed on every dashboard load, since the ranking is deterministic given a forecast and cheap to store once.

| Column | Type | Notes |
|---|---|---|
| window_id | SERIAL PK | |
| forecast_id | FK → forecasts | |
| start_day_offset | INTEGER | |
| end_day_offset | INTEGER | |
| rank | INTEGER | 1 = best window |
| avg_predicted_rate | NUMERIC(10,2) | |

### 3.10 `risk_alerts`
Output of the Risk Alert Service (FR-6).

| Column | Type | Notes |
|---|---|---|
| alert_id | SERIAL PK | |
| forecast_id | FK → forecasts, NULLABLE | congestion alerts may not be tied to a specific forecast run |
| route_id | FK → routes | |
| alert_type | ENUM('volatility','congestion','data_unavailable') | the third value implements the NFR-5 graceful-degradation case explicitly, rather than silently skipping |
| message | TEXT | plain-language reason, per FR-6.3 |
| severity | ENUM('low','medium','high') | |
| generated_at | TIMESTAMP | |

### 3.11 `queries`
Logs each dashboard query a user makes (useful both for FR-8.3-style traceability and, practically, for your demo — you can show a judge a query history).

| Column | Type | Notes |
|---|---|---|
| query_id | SERIAL PK | |
| cargo_volume_tonnes | INTEGER | |
| route_id | FK → routes | |
| desired_duration_type | ENUM('spot','short_term','mid_term') | per FR-1.1 |
| recommended_vessel_class_id | FK → vessel_classes | output of Vessel-Matching Service |
| forecast_id | FK → forecasts | which forecast run served this query |
| requested_at | TIMESTAMP | |

### 3.12 `admin_users` (minimal, for NFR-8)
Only needed if you implement the "restricted reference-data editing" requirement for the demo. A single-role table is enough for MVP — don't over-build auth for a hackathon.

| Column | Type | Notes |
|---|---|---|
| user_id | SERIAL PK | |
| username | VARCHAR(100) | |
| password_hash | VARCHAR(255) | |
| role | ENUM('admin','viewer') | |

---

## 4. Indexing Notes
- `route_freight_rates(route_id, vessel_class_id, date)` — composite index; this is the table the Forecasting Service queries most (training data pull for a specific route/class).
- `forecast_points(forecast_id, day_offset)` — composite, since points are always fetched together for one forecast.
- `base_index_values(vessel_class_id, date)` — the ingestion pipeline's main lookup pattern.

## 5. What This Schema Deliberately Does *Not* Include Yet
- No AIS/live-tracking tables — out of scope per SRS §1.5, add only if you pursue the post-MVP upgrade.
- No multi-tenant/company structure — single-team internal tool assumption for the hackathon demo.

---

## 6. What's Next

Next stage: **API design** — the FastAPI endpoint contracts (request/response shapes) that sit on top of these tables and the services from the architecture doc. After that: module/class breakdown with testing strategy, then the GitHub project board and implementation roadmap you can actually assign to teammates.

Flag anything here you'd want changed — in particular, if your team wants user query history to be a launch feature or just a nice-to-have, since that affects how much you build out `queries` before the demo.

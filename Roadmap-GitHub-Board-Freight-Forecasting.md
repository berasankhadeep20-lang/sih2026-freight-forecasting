# GitHub Project Board & Implementation Roadmap
## Intelligent Freight Forecasting Model — SIH 2026

**Version:** 0.1 (final planning doc — builds on all prior stages)
**Assumption stated up front:** team of 6, split by role below. Remap names onto roles as fits your actual team; the split itself is what matters, not the labels.

---

## 1. Role Split (assumed 6-person team)

| Role | Owns |
|---|---|
| Data/ML Lead | Kaggle ingestion, route-adjustment layer, Prophet + XGBoost + ensemble, backtest accuracy reporting |
| Backend Lead | FastAPI routers, `QueryOrchestrator`, repositories, DB migrations |
| Backend/Domain support | `VesselMatchingService`, `TimingRecommendationService`, `RiskAlertService`, their unit tests |
| Frontend Lead | React dashboard: query form, forecast chart with confidence bands, timing/alerts display |
| Frontend support | Comparison view (if in scope), export button, query history view |
| Integration/QA + Presentation | Integration tests, demo script, SIH idea PPT (Napkin content from earlier), final pitch deck for the build stage |

If your actual team is smaller, collapse "support" roles into their paired lead first — the ML and Backend Lead roles are the ones that shouldn't be merged, since forecasting and orchestration are the parts everything else depends on.

---

## 2. Milestones (work backward from your submission deadline)

Since I don't have your exact SIH deadline, the phases below are **relative** — slot your actual dates in. The sequencing is the part that matters: each milestone produces something demoable, so you're never one all-nighter away from having nothing to show.

### Milestone 1 — Data & Skeleton (produces: a runnable, empty-shell system)
- Kaggle dataset pulled and cleaned into `base_index_values` shape
- Route-adjustment layer implemented and run once to populate `route_freight_rates` for the 12 MVP combinations
- DB schema created (all tables from the schema doc), seeded with the 3 ports + 2 origins + vessel classes
- FastAPI skeleton with `/ports`, `/vessel-classes`, `/routes` working against the real DB
- React skeleton hitting those three endpoints, rendering dropdowns
- **Demo checkpoint:** you can open the dashboard and see real port/route data populate a form. Nothing predicts yet — that's fine, this milestone is about proving the pipe is connected end to end.

### Milestone 2 — Core Intelligence (produces: a working forecast, end-to-end for one route)
- `ForecastingService` implemented for exactly one route/vessel-class pair, backtested, accuracy number recorded
- `VesselMatchingService` and `TimingRecommendationService` implemented and unit-tested (these are fast to build — prioritize getting them done early since they're deterministic and low-risk)
- `RiskAlertService` implemented against the static congestion reference
- `QueryOrchestrator` wires it all together; `POST /queries` works for that one route
- Dashboard's forecast chart renders real confidence-band data for that one route
- **Demo checkpoint:** the full pipeline works for one origin-destination-vessel combination. This is your "minimum viable demo" — if you ran out of time after this milestone, you'd still have something real to show.

### Milestone 3 — Full MVP Scope
- Extend forecasting/backtesting to all 12 route-vessel combinations
- 422 validation for unknown routes, error handling per the API doc
- Admin endpoints for port/adjustment-factor editing (only if a teammate needs to tune values live during demo prep — otherwise this can be a direct DB edit and the endpoint becomes a stretch goal)
- Export endpoint (PDF/CSV)
- Integration test suite covering the endpoints in the API doc
- **Demo checkpoint:** all 12 combinations work, exports work, error cases handled gracefully.

### Milestone 4 — Polish, Comparison Feature (if in scope), Presentation
- Comparison view, if your team confirmed it's launch scope (from the API design doc's open question)
- Query history view
- Visual polish pass on the dashboard
- Rehearse the live demo — decide in advance which 2-3 query scenarios you'll run live (pick ones that clearly show a non-trivial recommendation, e.g., a case where the "obvious" vessel choice is wrong because of a port draft limit)
- Finalize the SIH pitch deck, referencing the backtest accuracy number and the architecture's honesty about real-vs-synthetic data as a credibility point

### Milestone 5 — Buffer
Reserve real time here. Every hackathon plan slips somewhere — usually the ML backtest taking longer to get to a presentable accuracy number than expected. Don't schedule Milestone 4 right up against your deadline.

---

## 3. GitHub Project Board Structure

**Columns:** `Backlog` → `In Progress` → `In Review` → `Done`

**Labels:**
- `area:data-ml`, `area:backend`, `area:frontend`, `area:integration`, `area:docs`
- `milestone:1` through `milestone:5`
- `priority:core` (needed for any demo at all) vs `priority:stretch` (comparison view, admin UI polish, etc.) — this label is what lets you triage honestly if you're behind schedule: cut `stretch` items first, never `core`.

**Suggested first issues to create** (one per bullet in Milestone 1 above), each referencing the relevant section of the docs you already have:
1. "Ingest Kaggle BDI dataset → `base_index_values`" (link: ingestion doc §2.6 in module breakdown)
2. "Implement route-adjustment transformation → `route_freight_rates`" (link: schema doc §3.5–3.6)
3. "Create DB schema + seed data" (link: schema doc, full)
4. "FastAPI skeleton: `/ports`, `/vessel-classes`, `/routes`" (link: API doc §2)
5. "React skeleton: query form + dropdowns wired to above"

Each subsequent milestone's issues follow the same pattern — one issue per bullet, tagged with its milestone and area label, linked back to the specific document section so nobody has to re-derive the "why."

---

## 4. A Few Things That Actually Win SIH Evaluations (worth keeping in mind through all of the above)

- **A working, even if small-scope, live demo beats a large-scope slideware pitch.** The milestone sequencing above is designed so Milestone 2 alone is a legitimate demo — protect that over trying to hit all 12 route combinations at the cost of nothing working end-to-end.
- **Be upfront about the synthetic-data layer.** Judges who know shipping will know real route-level freight data is commercial. Volunteering "here's our real signal, here's our documented synthetic adjustment, here's the backtest accuracy we got" reads as rigorous; getting caught implying it's all real data reads as the opposite.
- **Have the backtest number ready to say out loud.** "Our ensemble model achieves X% MAPE on held-out data" is a concrete, defensible claim — much stronger than "we used machine learning."
- **The deterministic modules (vessel-matching, timing) are your safest live-demo material** — no risk of an odd ML output confusing things in front of judges, and you can explain the logic in one sentence.

---

This closes out the planning stack: SRS → Architecture → Schema → API → Modules/Testing → Roadmap. Everything from here is execution — come back anytime you want to work through a specific module's actual code, debug something, or revisit a decision once your team has hands-on experience with it.

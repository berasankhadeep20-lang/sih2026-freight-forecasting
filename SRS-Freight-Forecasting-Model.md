# Software Requirements Specification
## Intelligent Freight Forecasting Model for Optimized Vessel Chartering and Bulk Cargo Procurement

**Version:** 0.1 (Draft for review)
**Prepared for:** SIH 2026
**Scope of this document:** Requirements only. No architecture, algorithms, or implementation decisions are made here — this defines *what* the system must do, so those decisions can be made deliberately in the next stage.

---

## 1. Introduction

### 1.1 Purpose
Define the functional and non-functional requirements for a system that predicts freight rates and recommends vessel-chartering decisions for bulk cargo shipments from overseas origins to India's East Coast ports, replacing the current reactive, daily-spot-market decision process.

### 1.2 Problem Being Solved
Logistics managers currently charter vessels based on same-day market conditions with no forward-looking model. This causes:
- Missed cost-saving windows in freight rate cycles
- No systematic way to pick the right vessel class for a given cargo + route + destination port
- Vessel idle time from poor turnaround planning
- No early warning for market or port-side disruptions

### 1.3 Intended Users
- **Logistics/chartering managers** — primary users; input cargo/route details, receive forecasts and recommendations
- **Shipping operations analysts** — review historical accuracy, tune thresholds, monitor model performance
- **Port/commercial teams** — reference vessel-port compatibility to negotiate contracts

### 1.4 Definitions
| Term | Meaning |
|---|---|
| LOA | Length Overall — max vessel length a port can berth |
| Draft | Vessel's underwater depth — must be less than port's channel/berth depth |
| Handysize/Supramax/Panamax/Capesize | Bulk carrier size classes, in ascending deadweight tonnage |
| Laycan | Laydays/cancelling — the window during which a vessel must arrive to load |
| Deadheading | Vessel sailing without cargo (empty) to reposition |
| BDI | Baltic Dry Index — benchmark for dry bulk freight rates |

### 1.5 Out of Scope (for this version)
- Actual contract negotiation or booking execution (system recommends, humans execute)
- Real-time AIS vessel tracking integration (deferred to a post-MVP phase; MVP uses periodic/delayed data)
- Container/liner shipping (dry bulk only)
- Currency hedging or bunker fuel price forecasting as standalone modules (treated only as input features)

---

## 2. Overall Description

### 2.1 Product Perspective
A standalone decision-support web application with a forecasting/recommendation engine as its core, and a dashboard as the primary user interface. It ingests external market and port data, produces predictions, and surfaces actionable recommendations — it does not replace existing chartering/booking systems, it advises them.

### 2.2 High-Level Capabilities
1. Freight rate forecasting per route and vessel class
2. Vessel-type recommendation given cargo + port constraints
3. Optimal market-entry timing recommendation
4. Idle-time / repositioning suggestions
5. Risk alerts (volatility, congestion, disruption)
6. Dashboard for input and visualization of the above

### 2.3 Assumptions and Dependencies
- Historical freight rate data (route-level, vessel-class-level) is obtainable, at minimum via publicly available indices (e.g., BDI) supplemented by any dataset the team can access or licensed sample data for prototype purposes
- Port infrastructure specs (draft, LOA, beam, cargo handling rate) can be manually compiled into a reference database from port authority publications for the 7 named East Coast ports
- The system is a decision-support tool — final chartering decisions remain human-made
- Prototype timeline (hackathon) constrains initial scope to a subset of routes/ports; architecture should not preclude scaling to the full set later

---

## 3. Functional Requirements

### FR-1: Cargo & Route Input
- FR-1.1: User shall input cargo type, cargo volume (tonnes), origin (country/load port), destination (one of the 7 named East Coast ports), and desired contract duration/type (spot / short-term / mid-term).
- FR-1.2: System shall validate that entered origin-destination pairs correspond to known trade lanes in the reference dataset; if unknown, system shall inform the user rather than silently guessing.

### FR-2: Freight Rate Forecasting
- FR-2.1: System shall generate a freight rate forecast for the specified route and a default forecast horizon (e.g., next 30/60/90 days), expressed per vessel class.
- FR-2.2: Forecast output shall include a confidence interval or uncertainty band, not a single point estimate.
- FR-2.3: System shall re-generate forecasts on a defined refresh cycle (e.g., daily) as new market data arrives.

### FR-3: Vessel Type Recommendation
- FR-3.1: Given cargo volume and destination port, system shall recommend the largest vessel class that satisfies the destination port's draft, LOA, and beam constraints.
- FR-3.2: If the origin (loading) port also has constraints, system shall check both ends and recommend the vessel class satisfying the more restrictive of the two.
- FR-3.3: System shall flag when no vessel class in the standard set (Handysize/Supramax/Panamax/Capesize) fits the cargo volume efficiently (e.g., cargo too small for economical Panamax use) and suggest the closest viable alternative.

### FR-4: Market Entry Timing Recommendation
- FR-4.1: System shall identify, within the forecast horizon, the time window(s) where predicted freight cost for the specified route/vessel class is lowest relative to the rest of the horizon.
- FR-4.2: Recommendation shall be presented as a ranked list of windows (not a single "best" answer only), so the user can weigh timing against operational urgency.

### FR-5: Idle-Time / Repositioning Management
- FR-5.1: System shall flag routes/periods where historical and forecast data indicate low demand (elevated idle-time risk).
- FR-5.2: For a flagged high-idle-risk scenario, system shall suggest alternative nearby routes or cargo types with better utilization potential, where data supports it.

### FR-6: Risk Alerts
- FR-6.1: System shall generate an alert when forecast uncertainty for a route exceeds a defined threshold (indicating high market volatility).
- FR-6.2: System shall generate an alert when known port congestion or disruption data indicates delays at the selected origin or destination port.
- FR-6.3: Alerts shall include a plain-language reason, not just a flag.

### FR-7: Dashboard & Reporting
- FR-7.1: System shall provide a dashboard where a user enters cargo/route/duration and views: forecast chart, recommended vessel class, recommended entry-timing windows, and active risk alerts, all for that query.
- FR-7.2: System shall allow the user to compare 2 or more origin-destination-vessel combinations side by side.
- FR-7.3: System shall allow exporting a given forecast/recommendation result (e.g., as PDF or CSV) for offline sharing.

### FR-8: Data Management
- FR-8.1: System shall maintain a reference database of port constraints (draft, LOA, beam, cargo handling rate) for the 7 named East Coast ports, editable by an authorized administrator.
- FR-8.2: System shall maintain a historical freight-rate dataset per route/vessel class, updatable as new data arrives.
- FR-8.3: System shall log every forecast generated (inputs, output, timestamp) to support later accuracy evaluation.

---

## 4. Non-Functional Requirements

### 4.1 Performance
- NFR-1: A forecast + recommendation result for a single query shall be returned within a target of a few seconds for an interactive dashboard experience (exact target to be finalized at architecture stage based on model choice).

### 4.2 Accuracy & Model Governance
- NFR-2: Forecast accuracy shall be tracked against realized freight rates once known, and reported (e.g., MAPE per route) so model quality is visible, not just assumed.
- NFR-3: The system shall distinguish clearly between model-generated recommendations and administrator-entered reference data (ports, constraints) so users know which parts are predictive vs. authoritative.

### 4.3 Usability
- NFR-4: Dashboard shall be usable by a logistics manager without ML background — outputs presented in shipping/chartering terminology, not raw model metrics, by default (advanced/technical view can be a secondary option).

### 4.4 Reliability
- NFR-5: If live/external data (e.g., port congestion feed) is unavailable, system shall degrade gracefully — show forecasts based on available data with a visible notice, rather than failing entirely.

### 4.5 Maintainability & Scalability
- NFR-6: Architecture shall allow adding new routes, ports, or vessel classes without core redesign (data-driven configuration, not hardcoded route logic).
- NFR-7: Codebase shall follow clean architecture principles with clear separation between data ingestion, forecasting/recommendation logic, and presentation layers, to support test coverage and incremental extension (per team's standard engineering practice).

### 4.6 Security & Access
- NFR-8: Reference data editing (ports, constraints) shall be restricted to authorized users; forecast/dashboard viewing may be open to all logistics team members.

---

## 5. External Interface Requirements

### 5.1 Data Inputs (external)
- Historical freight rate data (route/vessel-class level) — source(s) to be finalized at architecture stage (candidates: Baltic Exchange indices, any accessible historical dataset)
- Port infrastructure reference data — compiled from port authority publications (manual/semi-manual for MVP)
- Optional (post-MVP): live port congestion feed, live AIS positioning feed

### 5.2 User Interface
- Web dashboard (primary interface), responsive enough for desktop use by logistics managers (mobile support not a hard requirement for MVP)

### 5.3 Output Formats
- On-screen dashboard visualizations
- Exportable report (PDF/CSV) per FR-7.3

---

## 6. Open Questions for Team Sign-Off Before Architecture Stage

These need your team's decision before we move to system architecture, since they materially affect the design:

1. **Data source for historical freight rates** — do you have access to a paid dataset (Clarksons, Baltic Exchange), or should the prototype use a public/synthetic dataset for the hackathon demo?
2. **Number of routes/ports for the MVP demo** — all 7 ports × 5 origins, or a reduced set (e.g., 2 origins × 3 ports) to keep the hackathon build achievable?
3. **Forecast horizon** — what time horizon matters most to a chartering manager in practice (30/60/90 days)? This affects model choice.
4. **Team's tech comfort** — does the team already have a preferred stack (e.g., Python/React), or should that be decided fresh at architecture stage?

---

*End of SRS v0.1. Once reviewed, next stage: System Architecture (component diagram, data flow, technology selection with rationale) — followed by database schema, API design, module breakdown, testing strategy, and implementation roadmap, one at a time.*

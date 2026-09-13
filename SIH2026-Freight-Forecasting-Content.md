# SIH 2026 — Idea PPT Content & Napkin AI Prompts
**Topic:** Intelligent Freight Forecasting Model for Optimized Vessel Chartering & Bulk Cargo Procurement (Overseas → East Coast India)

---

## How to proceed (workflow)

1. **Fill Slide 1 (Title)** manually in the template — PS ID, PS Title, Theme, Team ID, Team Name. Don't touch this in Napkin.
2. For Slides 2–6, copy the **bullet content** below straight into Napkin AI's text box — Napkin turns pasted text into a diagram automatically. Use the **Napkin prompt** under each slide to steer *which* visual style it generates (flowchart, comparison, timeline, etc.).
3. In Napkin: paste text → click "Generate" → it proposes 3–4 visual layouts → pick the one matching the prompt's suggested type → simplify labels so nothing overflows (SIH slides are dense; Napkin sometimes adds decorative extras — delete anything not adding information).
4. Export each visual as PNG/SVG and drop into the actual SIH template slide (keep the template's title bar and "Your Team Name" placeholder — you're only allowed to fill placeholders, not redesign the template, per Slide 7's rules).
5. Final file must be exported as **PDF** before upload — no PPTX/DOCX accepted.
6. Delete Slide 7 (Important Instructions) before submission.

---

## Slide 2 — IDEA TITLE / Proposed Solution

**Bullet content to paste in Napkin:**
- Problem: East Coast India bulk cargo chartering relies on reactive, daily spot-market decisions with no forecasting — leads to missed cost-saving windows and vessel idle time
- Solution: AI/ML-driven Freight Forecasting Dashboard that predicts freight rates and recommends optimal charter timing, vessel type, and routing
- Core capability 1: Time-series forecasting of freight rates per route (Australia/US/Mozambique/Russia/Indonesia → Paradip/Vizag/Gangavaram/Gopalpur/Dhamra/Haldia)
- Core capability 2: Vessel-type recommendation engine matching cargo volume + port draft/LOA/beam constraints to Handysize/Supramax/Panamax/Capesize
- Core capability 3: Idle-time & risk alerts — congestion, seasonal demand dips, market volatility
- Uniqueness: combines freight-rate ML forecasting with port-infrastructure constraint-matching in one decision layer — most freight-rate tools ignore destination-port physical limits, most port-planning tools ignore rate forecasting

**Napkin prompt:**
> "Create a 3-box process flow: Problem → Solution Engine (3 sub-modules: Rate Forecasting, Vessel-Port Matching, Risk Alerts) → Outcome (Cost savings, less idle time). Style: clean horizontal flow diagram, icons for ship/chart/port."

---

## Slide 3 — TECHNICAL APPROACH

**Bullet content to paste in Napkin:**
- Data sources: historical Baltic Dry Index & route-specific freight rates, AIS vessel tracking, port draft/LOA/beam/cargo-handling-rate databases, commodity price indices (coal/iron ore), weather & seasonal demand data
- Forecasting layer: time-series models (LSTM / Facebook Prophet) + regression (XGBoost) ensembled for freight-rate prediction per route
- Constraint-matching layer: rule-based optimization (linear programming) matching cargo parcel size to vessel class within port draft/LOA limits
- Recommendation engine: ranks entry-timing windows and vessel types by predicted cost + turnaround time
- Frontend: web dashboard (React) for logistics managers to input cargo/route/duration and view forecasts + recommendations
- Backend: Python (FastAPI), PostgreSQL for port/vessel data, scheduled ML pipeline retraining
- Deployment: cloud-hosted (AWS/GCP), API integration point for live AIS/port congestion feeds

**Napkin prompt:**
> "Create a layered architecture / pipeline diagram: Data Sources (left, 4-5 icons) → Processing Layer (Forecasting Model + Constraint Optimizer, stacked boxes) → Recommendation Engine → Dashboard Output (right). Style: horizontal pipeline with arrows, tech-stack labels under each layer."

*(Alternative if you have a working prototype: swap this for an actual screenshot flow — Napkin is best for the conceptual pipeline, not UI mockups.)*

---

## Slide 4 — FEASIBILITY AND VIABILITY

**Bullet content to paste in Napkin:**
- Feasibility: historical freight rate data (Baltic Exchange, Clarksons) and AIS data are publicly/commercially available; port infrastructure specs are published by port authorities — no novel data-collection barrier
- Feasibility: proven ML techniques (LSTM/Prophet/XGBoost) for time-series forecasting — technology risk is low, main effort is data integration and tuning
- Challenge 1: Freight market volatility (geopolitical shocks, fuel price swings) can degrade forecast accuracy → Mitigation: ensemble models + confidence-interval outputs + manual override by logistics managers
- Challenge 2: Fragmented/inconsistent port data across countries → Mitigation: build a standardized internal port-constraints database, updated periodically from official sources
- Challenge 3: Real-time AIS/congestion feeds may have licensing costs → Mitigation: start with delayed/free-tier data for MVP, upgrade to real-time feeds post-pilot
- Viability: modular design allows phased rollout — start with 1-2 routes (e.g., Australia→Paradip) before scaling to all origins/ports

**Napkin prompt:**
> "Create a two-column comparison/risk-mitigation table-style diagram: left column 'Challenges' (3 items with warning icons), right column 'Mitigation Strategy' (matched 1-to-1 with shield/checkmark icons). Style: simple paired-row layout."

---

## Slide 5 — IMPACT AND BENEFITS

**Bullet content to paste in Napkin:**
- Target audience: shipping/logistics companies, bulk commodity importers (coal, iron ore), port authorities on India's East Coast
- Economic impact: reduced freight costs via optimal charter timing; fewer demurrage/idle-time penalties from better vessel-port matching
- Operational impact: shift from reactive daily spot chartering to proactive short/mid-term voyage contracts — more predictable logistics planning
- Efficiency impact: reduced vessel turnaround time and port congestion through better-matched vessel sizing
- Environmental impact: less idle/deadhead sailing reduces fuel consumption and emissions per tonne of cargo moved
- Strategic impact: strengthens India's East Coast port competitiveness and supply chain resilience for coal/bulk imports critical to power/steel sectors

**Napkin prompt:**
> "Create a hub-and-spoke or 4-icon benefit diagram around a central 'Freight Forecasting Model' node, with 4 spokes: Economic (cost savings), Operational (proactive contracts), Environmental (lower emissions), Strategic (supply chain resilience). Style: radial infographic with distinct icon per spoke."

---

## Slide 6 — RESEARCH AND REFERENCES

**Bullet content to paste in Napkin (as a simple list, not a diagram):**
- Baltic Exchange — Baltic Dry Index & route-specific freight rate historical data (balticexchange.com)
- Clarksons Research — Shipping Intelligence Network, vessel & freight market data
- Indian Ports Association / individual port authority websites (Paradip Port Authority, Vizag Port Authority, etc.) — draft, LOA, berth specifications
- UNCTAD Review of Maritime Transport — global trade lane and dry bulk demand trends
- Academic reference: time-series forecasting literature on LSTM/Prophet applications to freight rate prediction (cite specific papers your team finds during literature review)
- AIS vessel tracking data providers (e.g., MarineTraffic) for real-time positioning reference

**Napkin prompt:**
> Skip Napkin here — this slide is meant to be a plain, precise list (source name + what it provides). A generated diagram would look decorative and add no clarity for a references slide.

---

## Notes on staying within SIH rules
- Max 6 slides total (title included) — the content above fits slides 2–6 exactly as your template numbers them.
- Every slide above is bullet/diagram-first, no paragraphs, per Slide 7's instruction.
- Fill in your actual **Team ID, Team Name, PS ID** on Slide 1 before generating anything else — Napkin visuals go on slides 2–6 only.

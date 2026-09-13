# API Design
## Intelligent Freight Forecasting Model — SIH 2026

**Version:** 0.1 (builds on Schema v0.1)
**Scope of this document:** REST endpoint contracts — request/response shapes and status codes. No class-level implementation yet — that's the module breakdown stage next.

---

## 1. Design Principle: One "Query" Resource Ties Everything Together

Looking back at the architecture doc's data flow: a single dashboard submission triggers three services (Forecasting, Timing-Recommendation, Risk Alert) plus the independent Vessel-Matching service, and the schema logs that as one `queries` row linked to one `forecasts` row. The API should mirror that — **one endpoint, one response, that already contains everything the dashboard needs to render** — rather than making the frontend call four separate endpoints and stitch results together itself.

This matters concretely: it means the parallel execution (vessel-matching running alongside forecasting, per the architecture doc) is an internal implementation detail of one API call, not something the frontend has to orchestrate. Reference data (ports, vessel classes, routes) gets separate, simple GET endpoints since the dashboard needs those to populate dropdowns *before* a query is even submitted.

---

## 2. Reference Data Endpoints (read-only, populate dashboard inputs)

### `GET /ports`
Returns all ports, optionally filtered by role.

**Query params:** `role` (optional: `origin` | `destination`)

**Response 200:**
```json
[
  {
    "port_id": 1,
    "name": "Paradip",
    "country": "India",
    "role": "destination",
    "max_draft_m": 18.0,
    "max_loa_m": 300.0,
    "congestion_score": 0.3
  }
]
```

### `GET /vessel-classes`
**Response 200:**
```json
[
  { "vessel_class_id": 1, "name": "Supramax", "min_dwt": 50000, "max_dwt": 60000 },
  { "vessel_class_id": 2, "name": "Panamax", "min_dwt": 65000, "max_dwt": 80000 }
]
```

### `GET /routes`
Returns the routes the system currently covers (the 12 MVP combinations), each with origin/destination names resolved — the frontend shouldn't have to join `ports` itself.

**Response 200:**
```json
[
  {
    "route_id": 1,
    "origin": { "port_id": 5, "name": "Newcastle", "country": "Australia" },
    "destination": { "port_id": 1, "name": "Paradip", "country": "India" },
    "commodity": "coal"
  }
]
```

---

## 3. The Core Endpoint: Submitting a Query

### `POST /queries`
Implements FR-1 through FR-6 in one call — validates the route, runs forecasting + vessel-matching + timing + risk-alert services (per the architecture's parallel data flow), logs the query, and returns the full result.

**Request body:**
```json
{
  "cargo_volume_tonnes": 70000,
  "origin_port_id": 5,
  "destination_port_id": 1,
  "desired_duration_type": "short_term"
}
```

**Response 201 (created — this is logged as a new `queries` row):**
```json
{
  "query_id": 42,
  "route": { "route_id": 1, "origin": "Newcastle", "destination": "Paradip" },
  "recommended_vessel_class": { "vessel_class_id": 2, "name": "Panamax", "reason": "Largest class fitting destination draft (18.0m) and cargo volume (70,000t)" },
  "forecast": {
    "forecast_id": 101,
    "horizon_days": 60,
    "model_version": "prophet_xgb_ensemble_v1",
    "points": [
      { "day_offset": 0, "predicted_rate": 24.50, "lower_bound": 22.10, "upper_bound": 26.90 }
    ]
  },
  "recommended_timing_windows": [
    { "rank": 1, "start_day_offset": 12, "end_day_offset": 18, "avg_predicted_rate": 21.30 },
    { "rank": 2, "start_day_offset": 40, "end_day_offset": 45, "avg_predicted_rate": 22.10 }
  ],
  "risk_alerts": [
    { "alert_type": "congestion", "severity": "medium", "message": "Paradip congestion score elevated (0.6) based on last update." }
  ]
}
```

**Error responses:**
- `400 Bad Request` — cargo volume ≤ 0, or duration type not one of the enum values
- `422 Unprocessable Entity` — origin/destination pair is not a known route (implements FR-1.2's "inform the user rather than silently guessing" — the response body names *why*, e.g. `"reason": "No route configured for Mozambique → Gopalpur in current MVP scope"`)

**Note on the `reason` fields:** both the vessel recommendation and the 422 error include a plain-language reason string. This isn't just nice UX — NFR-4 requires non-ML-background users to trust the output, and a bare number with no reasoning fails that requirement even if the underlying computation is correct.

### `GET /queries/{query_id}`
Retrieves a previously-run query result in the same shape as the POST response — lets the dashboard reload a past result (e.g., from query history) without recomputation.

**Response 200:** same shape as `POST /queries` response.
**Response 404:** query_id not found.

### `GET /queries`
Lists past queries (summary only, not full forecasts) for a history view.

**Query params:** `limit`, `offset` (pagination)

**Response 200:**
```json
[
  { "query_id": 42, "route": "Newcastle → Paradip", "requested_at": "2026-09-10T09:00:00Z" }
]
```

---

## 4. Comparison Endpoint (FR-7.2)

### `POST /queries/compare`
Accepts 2+ query specs and returns their results side by side in one call — avoids the frontend firing multiple `POST /queries` calls and creating duplicate log entries for what's conceptually one comparison action.

**Request body:**
```json
{
  "queries": [
    { "cargo_volume_tonnes": 70000, "origin_port_id": 5, "destination_port_id": 1, "desired_duration_type": "short_term" },
    { "cargo_volume_tonnes": 70000, "origin_port_id": 6, "destination_port_id": 1, "desired_duration_type": "short_term" }
  ]
}
```

**Response 200:** array of the same per-query result shape as `POST /queries`, in request order. Each is *also* logged individually to `queries`, so history stays consistent with single submissions.

---

## 5. Export Endpoint (FR-7.3)

### `GET /queries/{query_id}/export?format=pdf|csv`
**Response 200:** binary file (`application/pdf` or `text/csv`), `Content-Disposition: attachment`.
**Response 404:** query_id not found.
**Response 400:** unsupported format value.

---

## 6. Admin Endpoints (NFR-8 — restricted access)

These mutate reference data and require an authenticated admin session. For hackathon scope, a simple bearer-token check is enough — don't over-build auth.

### `POST /auth/login`
**Request:** `{ "username": "...", "password": "..." }`
**Response 200:** `{ "access_token": "...", "role": "admin" }`
**Response 401:** invalid credentials.

### `PUT /ports/{port_id}`
Updates port constraints (draft/LOA/beam/congestion_score). Requires `Authorization: Bearer <token>` with `role=admin`.
**Response 200:** updated port object.
**Response 403:** authenticated but not admin.
**Response 401:** no/invalid token.

### `PUT /route-adjustment-factors/{adjustment_id}`
Lets an admin tune the synthetic route-adjustment parameters documented in the schema — useful during development/demo prep as your team calibrates the synthetic layer against what judges might sanity-check.
**Response 200:** updated adjustment object.

---

## 7. Cross-Cutting Notes

- **All list endpoints return arrays directly** (not wrapped in `{ "data": [...] }`) — simpler for the hackathon timeline, revisit only if you need envelope metadata (e.g., total counts) later.
- **Timestamps are ISO 8601 UTC** throughout.
- **Validation errors always include a `reason` or `detail` string** — this is a deliberate consistency rule across every endpoint, not just `POST /queries`, because NFR-4 (non-technical usability) applies everywhere the user sees output, not just the main flow.
- **No endpoint blocks on a live external feed** — congestion data is read from the stored reference value (per architecture §2.5), so `POST /queries` never has an external-network failure mode to handle. This directly satisfies NFR-1 (fast interactive response) and NFR-5 (graceful degradation) simultaneously, by design rather than by exception-handling.

---

## 8. What's Next

Next stage: **module/class breakdown with testing strategy** — the actual Python classes/functions implementing each service from the architecture doc, mapped to these endpoints, plus what gets unit-tested vs. integration-tested. After that: GitHub project board and implementation roadmap your team can start executing against.

Flag anything above you'd change — in particular, whether your team wants the comparison feature (§4) for the MVP demo or whether it's a stretch goal, since that affects how much of the module breakdown to prioritize for it.

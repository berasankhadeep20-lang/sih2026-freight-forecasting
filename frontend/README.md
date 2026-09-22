# CargoNex Frontend

React 18 + Vite + Tailwind CSS + Recharts, consuming the FastAPI backend
in the parent directory. Implements FR-7 (dashboard) from the SRS: a
user picks a route, cargo volume, and horizon, and sees the forecast
chart with confidence bands, the recommended vessel, ranked timing
windows, and risk alerts — all real data from the live API, nothing
mocked.

## Running it

You need the backend running first (from the repo root):

```bash
python -m infrastructure.db.seed   # once, to create + seed cargonex.db
python -m uvicorn main:app --reload
```

Then, in this `frontend/` directory:

```bash
npm install
cp .env.example .env    # only needed if your API isn't on localhost:8000
npm run dev
```

Open the URL Vite prints (typically `http://localhost:5173`).

## A real bug this build caught

The backend had **no CORS policy** — a browser calling it from a
different origin (Vite's dev server on a different port counts as a
different origin) would have every request silently blocked before it
reached any router. This is invisible if you only test the API with
`curl` or the FastAPI `TestClient`, since neither enforces browser CORS
rules — it only surfaces the moment a real browser is involved, which is
exactly why building the frontend mattered even though the API "worked"
before this. Fixed in `main.py` with `CORSMiddleware`, verified with a
real OPTIONS preflight request returning the correct
`access-control-allow-origin` header before this was called done.

## Structure

```
src/
  api/client.js              — fetch wrapper matching API Design v0.1's contract
  components/
    QueryForm.jsx              — route/cargo/horizon input, populated from real /routes + /ports
    ForecastChart.jsx           — Recharts confidence-band chart
    VesselRecommendationCard.jsx
    TimingWindowsList.jsx
    RiskAlertsList.jsx
  App.jsx                     — wires it together, handles the API's real error responses
```

## Design choice: the form only offers known routes

`QueryForm` populates its route dropdown from `GET /routes` rather than
letting the user freely pick any origin + any destination. The backend
would reject an unknown combination with a 422 either way (defense in
depth is still there), but this avoids a user hitting that error on a
routine first query just because the MVP only covers one seeded route
so far. As your team adds more real routes to the database, they appear
in this dropdown automatically — no frontend code change needed.

## Known gaps

- No loading skeleton — a slow forecast (Prophet fitting can take a
  second or two) just shows the disabled button's "Running forecast…"
  text. Fine for a demo, worth polishing if you have time.
- No route comparison view (API Design v0.1 §4) — confirm with your
  team whether that's launch-scope per the roadmap's open question
  before building it.

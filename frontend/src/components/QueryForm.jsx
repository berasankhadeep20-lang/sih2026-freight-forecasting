import { useEffect, useState } from "react";
import { api } from "../api/client";

// The form deliberately lets the user pick from KNOWN routes (from
// GET /routes) rather than freely combining any origin + any
// destination — that mirrors how the system actually works (only
// specific route/vessel-class combinations have historical data to
// forecast from) and avoids the happy-path user hitting the 422
// "unknown route" error on a routine query. The backend still enforces
// this independently either way — this is a UX improvement, not a
// substitute for that validation.
export default function QueryForm({ onSubmit, submitting }) {
  const [ports, setPorts] = useState([]);
  const [routes, setRoutes] = useState([]);
  const [routeId, setRouteId] = useState("");
  const [cargoVolume, setCargoVolume] = useState(70000);
  const [horizonDays, setHorizonDays] = useState(60);
  const [loadError, setLoadError] = useState(null);

  useEffect(() => {
    Promise.all([api.listPorts(), api.listRoutes()])
      .then(([portsData, routesData]) => {
        setPorts(portsData);
        setRoutes(routesData);
        if (routesData.length > 0) setRouteId(routesData[0].route_id);
      })
      .catch((err) => setLoadError(err.message));
  }, []);

  const portName = (portId) => ports.find((p) => p.port_id === portId)?.name || portId;

  function handleSubmit(e) {
    e.preventDefault();
    const route = routes.find((r) => r.route_id === routeId);
    if (!route) return;
    onSubmit({
      cargo_volume_tonnes: Number(cargoVolume),
      origin_port_id: route.origin_port_id,
      destination_port_id: route.destination_port_id,
      horizon_days: Number(horizonDays),
    });
  }

  if (loadError) {
    return (
      <div className="rounded-lg bg-red-50 border border-red-200 text-red-700 p-4 text-sm">
        Couldn't load reference data from the API: {loadError}. Is the backend
        running at the configured VITE_API_BASE_URL?
      </div>
    );
  }

  return (
    <form onSubmit={handleSubmit} className="bg-white rounded-xl border border-slate-200 p-6 space-y-5">
      <div>
        <label className="block text-sm font-semibold text-slate-700 mb-1">Route</label>
        <select
          className="w-full rounded-lg border border-slate-300 px-3 py-2 text-sm"
          value={routeId}
          onChange={(e) => setRouteId(e.target.value)}
        >
          {routes.length === 0 && <option>Loading routes…</option>}
          {routes.map((r) => (
            <option key={r.route_id} value={r.route_id}>
              {portName(r.origin_port_id)} → {portName(r.destination_port_id)} ({r.commodity})
            </option>
          ))}
        </select>
      </div>

      <div>
        <label className="block text-sm font-semibold text-slate-700 mb-1">
          Cargo volume (tonnes)
        </label>
        <input
          type="number"
          min="1"
          className="w-full rounded-lg border border-slate-300 px-3 py-2 text-sm"
          value={cargoVolume}
          onChange={(e) => setCargoVolume(e.target.value)}
        />
        <p className="text-xs text-slate-500 mt-1">
          Try a value above 180,000t to see the system's real "no vessel class fits" error.
        </p>
      </div>

      <div>
        <label className="block text-sm font-semibold text-slate-700 mb-1">
          Forecast horizon (days)
        </label>
        <input
          type="number"
          min="1"
          max="180"
          className="w-full rounded-lg border border-slate-300 px-3 py-2 text-sm"
          value={horizonDays}
          onChange={(e) => setHorizonDays(e.target.value)}
        />
      </div>

      <button
        type="submit"
        disabled={submitting || !routeId}
        className="w-full bg-blue-600 hover:bg-blue-700 disabled:opacity-50 text-white font-semibold rounded-lg py-2.5 text-sm transition"
      >
        {submitting ? "Running forecast…" : "Get recommendation"}
      </button>
    </form>
  );
}

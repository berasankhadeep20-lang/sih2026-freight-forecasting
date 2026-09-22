import { useState } from "react";
import { api, ApiError } from "./api/client";
import QueryForm from "./components/QueryForm";
import ForecastChart from "./components/ForecastChart";
import VesselRecommendationCard from "./components/VesselRecommendationCard";
import TimingWindowsList from "./components/TimingWindowsList";
import RiskAlertsList from "./components/RiskAlertsList";

export default function App() {
  const [result, setResult] = useState(null);
  const [error, setError] = useState(null);
  const [submitting, setSubmitting] = useState(false);

  async function handleSubmit(payload) {
    setSubmitting(true);
    setError(null);
    setResult(null);
    try {
      const data = await api.submitQuery(payload);
      setResult(data);
    } catch (err) {
      // ApiError carries the API's plain-language `detail` message —
      // e.g. "No route configured for X -> Y" or a NoVesselCapacityError
      // message. Surface it directly rather than a generic failure.
      setError(err instanceof ApiError ? err.message : "Something went wrong. Is the API running?");
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <div className="min-h-screen bg-slate-50">
      <header className="bg-white border-b border-slate-200">
        <div className="max-w-5xl mx-auto px-6 py-5 flex items-center justify-between">
          <div>
            <h1 className="text-xl font-bold text-slate-900">🚢 CargoNex</h1>
            <p className="text-sm text-slate-500">
              Intelligent Freight Forecasting — SIH 2026, PS 26006
            </p>
          </div>
          <span className="text-xs bg-green-50 text-green-700 font-semibold px-3 py-1.5 rounded-full">
            Live backend
          </span>
        </div>
      </header>

      <main className="max-w-5xl mx-auto px-6 py-8 grid md:grid-cols-[340px_1fr] gap-6">
        <div>
          <QueryForm onSubmit={handleSubmit} submitting={submitting} />
        </div>

        <div className="space-y-5">
          {error && (
            <div className="rounded-lg bg-red-50 border border-red-200 text-red-700 p-4 text-sm">
              {error}
            </div>
          )}

          {!result && !error && (
            <div className="bg-white rounded-xl border border-dashed border-slate-300 p-10 text-center text-slate-400">
              Submit a query to see the forecast, vessel recommendation, timing windows, and risk alerts.
            </div>
          )}

          {result && (
            <>
              <VesselRecommendationCard
                recommendation={result.recommended_vessel}
                note={result.forecast_vessel_class_note}
              />

              <div className="bg-white rounded-xl border border-slate-200 p-5">
                <ForecastChart forecast={result.forecast} />
              </div>

              <div className="grid sm:grid-cols-2 gap-5">
                <div className="bg-white rounded-xl border border-slate-200 p-5">
                  <h3 className="font-semibold text-slate-800 mb-3">Best entry-timing windows</h3>
                  <TimingWindowsList windows={result.timing_windows} />
                </div>
                <div className="bg-white rounded-xl border border-slate-200 p-5">
                  <h3 className="font-semibold text-slate-800 mb-3">Risk alerts</h3>
                  <RiskAlertsList alerts={result.risk_alerts} />
                </div>
              </div>
            </>
          )}
        </div>
      </main>
    </div>
  );
}

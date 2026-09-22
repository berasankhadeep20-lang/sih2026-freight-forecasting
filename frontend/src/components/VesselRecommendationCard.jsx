export default function VesselRecommendationCard({ recommendation, note }) {
  return (
    <div
      className={`rounded-xl border p-5 ${
        recommendation.is_constrained ? "border-amber-300 bg-amber-50" : "border-slate-200 bg-white"
      }`}
    >
      <div className="text-xs font-semibold uppercase tracking-wide text-slate-500 mb-1">
        Recommended vessel
      </div>
      <div className="text-2xl font-bold text-slate-900">
        {recommendation.vessel_class}
        {recommendation.is_constrained && (
          <span className="ml-2 text-sm font-medium text-amber-700 align-middle">
            (constrained by port)
          </span>
        )}
      </div>
      <p className="text-sm text-slate-600 mt-2">{recommendation.reason}</p>
      {note && (
        <p className="text-sm text-blue-700 bg-blue-50 rounded-lg p-3 mt-3">{note}</p>
      )}
    </div>
  );
}

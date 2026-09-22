const SEVERITY_STYLES = {
  high: "bg-red-50 text-red-700 border-red-200",
  medium: "bg-amber-50 text-amber-700 border-amber-200",
  low: "bg-slate-50 text-slate-600 border-slate-200",
};

export default function RiskAlertsList({ alerts }) {
  if (alerts.length === 0) {
    return (
      <div className="text-sm text-slate-500">
        No elevated risk alerts for this route and forecast.
      </div>
    );
  }
  return (
    <div className="space-y-2">
      {alerts.map((a, i) => (
        <div
          key={i}
          className={`text-sm rounded-lg px-4 py-2.5 border ${SEVERITY_STYLES[a.severity] || SEVERITY_STYLES.low}`}
        >
          <span className="font-semibold uppercase text-xs mr-2">{a.alert_type}</span>
          {a.message}
        </div>
      ))}
    </div>
  );
}

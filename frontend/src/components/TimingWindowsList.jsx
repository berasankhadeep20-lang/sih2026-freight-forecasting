export default function TimingWindowsList({ windows }) {
  if (windows.length === 0) {
    return (
      <div className="text-sm text-slate-500">
        No timing windows available (forecast horizon shorter than one window).
      </div>
    );
  }
  return (
    <div className="space-y-2">
      {windows.map((w) => (
        <div
          key={w.rank}
          className="flex items-center justify-between bg-slate-50 rounded-lg px-4 py-2.5 border border-slate-200"
        >
          <span className="text-sm font-medium text-slate-700">
            #{w.rank} · Day {w.start_day_offset}–{w.end_day_offset}
          </span>
          <span className="text-sm font-mono text-slate-900">
            avg ${w.avg_predicted_rate.toFixed(2)}/day
          </span>
        </div>
      ))}
    </div>
  );
}

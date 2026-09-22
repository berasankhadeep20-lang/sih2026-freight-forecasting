import {
  ComposedChart, Area, Line, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer,
} from "recharts";

// Confidence band drawn as a stacked area trick: an invisible base area
// up to lower_bound, then a visible band area of height (upper - lower)
// on top of it — the standard Recharts pattern for a shaded interval,
// since Recharts has no first-class "band" series type.
export default function ForecastChart({ forecast }) {
  const data = forecast.points.map((p) => ({
    day: p.day_offset,
    lower: p.lower_bound,
    band: Number((p.upper_bound - p.lower_bound).toFixed(2)),
    predicted: p.predicted_rate,
  }));

  return (
    <div>
      <div className="flex items-center justify-between mb-2">
        <h3 className="font-semibold text-slate-800">
          {forecast.horizon_days}-day forecast — {forecast.vessel_class}
        </h3>
        <span className="text-xs text-slate-500 font-mono">{forecast.model_version}</span>
      </div>
      <ResponsiveContainer width="100%" height={280}>
        <ComposedChart data={data} margin={{ top: 5, right: 10, left: 0, bottom: 5 }}>
          <CartesianGrid strokeDasharray="3 3" stroke="#e2e8f0" />
          <XAxis dataKey="day" tick={{ fontSize: 12 }} label={{ value: "Day", position: "insideBottom", offset: -3, fontSize: 12 }} />
          <YAxis tick={{ fontSize: 12 }} label={{ value: "USD/tonne", angle: -90, position: "insideLeft", fontSize: 12 }} />
          <Tooltip
            formatter={(value, name) => {
              if (name === "band") return null;
              return [`$${value}`, name === "predicted" ? "Predicted rate" : "Lower bound"];
            }}
            labelFormatter={(day) => `Day ${day}`}
          />
          <Area type="monotone" dataKey="lower" stackId="band" stroke="none" fill="transparent" isAnimationActive={false} />
          <Area type="monotone" dataKey="band" stackId="band" stroke="none" fill="#2f6fed" fillOpacity={0.15} isAnimationActive={false} />
          <Line type="monotone" dataKey="predicted" stroke="#2f6fed" strokeWidth={2} dot={false} isAnimationActive={false} />
        </ComposedChart>
      </ResponsiveContainer>
    </div>
  );
}

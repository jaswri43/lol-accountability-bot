import { Line, LineChart, ResponsiveContainer } from "recharts";

/** Deliberately minimal: no axes, grid, or tooltip -- a trend shape, not a
 * chart to read values off. Renders nothing but reserves its footprint
 * when there isn't enough data yet. */
export function Sparkline({ data, color = "#5b7fa6" }: { data: number[]; color?: string }) {
  if (data.length < 2) {
    return <div className="h-8 w-20 shrink-0" />;
  }

  return (
    <div className="h-8 w-20 shrink-0">
      <ResponsiveContainer width="100%" height="100%">
        <LineChart data={data.map((v, i) => ({ i, v }))} margin={{ top: 3, right: 3, bottom: 3, left: 3 }}>
          <Line
            type="monotone"
            dataKey="v"
            stroke={color}
            strokeWidth={1.5}
            dot={false}
            isAnimationActive={false}
          />
        </LineChart>
      </ResponsiveContainer>
    </div>
  );
}

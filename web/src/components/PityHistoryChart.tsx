import { Line, LineChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import type { PityHistoryPoint } from "../api/types";
import { formatDate } from "../lib/tier";

export function PityHistoryChart({ points }: { points: PityHistoryPoint[] | null }) {
  return (
    <div className="rounded-3xl border border-hairline bg-white p-5">
      <p className="text-xs font-medium uppercase tracking-widest text-zinc-500">Pity over time</p>
      {points === null ? (
        <p className="mt-3 text-sm text-zinc-500">Loading…</p>
      ) : points.length < 2 ? (
        <p className="mt-3 text-sm text-zinc-500">
          Not enough history yet — this fills in as counted losses/wins happen.
        </p>
      ) : (
        <div className="mt-3 h-40">
          <ResponsiveContainer width="100%" height="100%">
            <LineChart data={points} margin={{ top: 4, right: 4, bottom: 0, left: -20 }}>
              <XAxis
                dataKey="recorded_at"
                tickFormatter={(v: string) => formatDate(v)}
                tick={{ fontSize: 11, fill: "#a1a1aa" }}
                axisLine={false}
                tickLine={false}
                minTickGap={40}
              />
              <YAxis tick={{ fontSize: 11, fill: "#a1a1aa" }} axisLine={false} tickLine={false} width={30} />
              <Tooltip
                labelFormatter={(v: string) => formatDate(v)}
                formatter={(value: number) => [value.toFixed(1), "Pity"]}
                contentStyle={{ borderRadius: 8, borderColor: "#e5e5e5", fontSize: 12 }}
              />
              <Line type="monotone" dataKey="pity" stroke="#5b7fa6" strokeWidth={2} dot={false} />
            </LineChart>
          </ResponsiveContainer>
        </div>
      )}
    </div>
  );
}

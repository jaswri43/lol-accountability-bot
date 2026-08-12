import { Bar, BarChart, Cell, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import type { StatusResponse } from "../api/types";
import { TIER_HEX } from "../lib/tier";

export function OddsChart({ odds }: { odds: StatusResponse["odds"] }) {
  const data = [
    { name: "Low", value: odds.low, color: TIER_HEX.low },
    { name: "Medium", value: odds.medium, color: TIER_HEX.medium },
    { name: "High", value: odds.high, color: TIER_HEX.high },
  ];

  return (
    <ResponsiveContainer width="100%" height={140}>
      <BarChart data={data} layout="vertical" margin={{ top: 0, right: 24, bottom: 0, left: 0 }}>
        <XAxis
          type="number"
          domain={[0, 1]}
          tickFormatter={(v: number) => `${Math.round(v * 100)}%`}
          tick={{ fontSize: 12 }}
        />
        <YAxis type="category" dataKey="name" width={64} tick={{ fontSize: 13 }} />
        <Tooltip
          formatter={(value: number) => `${Math.round(value * 100)}%`}
          cursor={{ fill: "rgba(0,0,0,0.03)" }}
        />
        <Bar dataKey="value" radius={[0, 6, 6, 0]} barSize={22}>
          {data.map((entry) => (
            <Cell key={entry.name} fill={entry.color} />
          ))}
        </Bar>
      </BarChart>
    </ResponsiveContainer>
  );
}

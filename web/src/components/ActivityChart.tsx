import { Bar, BarChart, ResponsiveContainer, Tooltip, XAxis } from "recharts";
import type { ActivityPoint } from "../api/types";

function formatDay(dateStr: string): string {
  return new Date(`${dateStr}T00:00:00Z`).toLocaleDateString(undefined, { month: "short", day: "numeric" });
}

export function ActivityChart({ activity }: { activity: ActivityPoint[] | null }) {
  const data = activity?.map((p) => ({ ...p, label: formatDay(p.date) })) ?? [];

  return (
    <div className="rounded-3xl border border-hairline bg-white p-5">
      <p className="text-xs font-medium uppercase tracking-widest text-zinc-500">Tasks completed</p>
      {activity === null ? (
        <p className="mt-3 text-sm text-zinc-500">Loading…</p>
      ) : (
        <div className="mt-3 h-40">
          <ResponsiveContainer width="100%" height="100%">
            <BarChart data={data} margin={{ top: 4, right: 4, bottom: 0, left: -20 }}>
              <XAxis
                dataKey="label"
                tick={{ fontSize: 11, fill: "#a1a1aa" }}
                axisLine={false}
                tickLine={false}
                interval={1}
              />
              <Tooltip
                cursor={{ fill: "rgba(0,0,0,0.03)" }}
                formatter={(value: number) => [value, "Completed"]}
                contentStyle={{ borderRadius: 8, borderColor: "#e5e5e5", fontSize: 12 }}
              />
              <Bar dataKey="count" fill="#5b7fa6" radius={[4, 4, 0, 0]} barSize={14} />
            </BarChart>
          </ResponsiveContainer>
        </div>
      )}
    </div>
  );
}

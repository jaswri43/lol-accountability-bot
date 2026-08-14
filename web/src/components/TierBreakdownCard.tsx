import type { Tier, TierStat } from "../api/types";
import { TIER_HEX, TIER_LABEL } from "../lib/tier";

const TIERS: Tier[] = ["low", "medium", "high"];
const EMPTY: TierStat = { count: 0, completed: 0, completion_rate: 0 };

export function TierBreakdownCard({ breakdown }: { breakdown: Record<Tier, TierStat> }) {
  return (
    <div className="rounded-3xl border border-hairline bg-white p-5">
      <p className="text-xs font-medium uppercase tracking-widest text-zinc-500">Tasks by tier</p>
      <div className="mt-4 space-y-4">
        {TIERS.map((tier) => {
          const stat = breakdown[tier] ?? EMPTY;
          return (
            <div key={tier}>
              <div className="flex items-center justify-between text-sm">
                <span className="flex items-center gap-2 text-zinc-600">
                  <span
                    className="h-2 w-2 rounded-full"
                    style={{ backgroundColor: TIER_HEX[tier] }}
                    aria-hidden="true"
                  />
                  {TIER_LABEL[tier]}
                </span>
                <span className="text-zinc-500">
                  {stat.completed}/{stat.count} done
                </span>
              </div>
              <div className="mt-1.5 h-1.5 overflow-hidden rounded-full bg-zinc-100">
                <div
                  className="h-full rounded-full transition-all"
                  style={{
                    width: `${Math.round(stat.completion_rate * 100)}%`,
                    backgroundColor: TIER_HEX[tier],
                  }}
                />
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}

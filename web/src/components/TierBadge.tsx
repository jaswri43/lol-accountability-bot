import type { Tier } from "../api/types";
import { TIER_CLASSES, TIER_LABEL } from "../lib/tier";

export function TierBadge({ tier }: { tier: Tier | null }) {
  if (!tier) {
    return (
      <span className="inline-flex items-center rounded-full bg-slate-100 px-2.5 py-0.5 text-xs font-medium text-slate-600 ring-1 ring-inset ring-slate-500/20">
        Untagged
      </span>
    );
  }
  return (
    <span
      className={`inline-flex items-center rounded-full px-2.5 py-0.5 text-xs font-medium ring-1 ring-inset ${TIER_CLASSES[tier]}`}
    >
      {TIER_LABEL[tier]}
    </span>
  );
}

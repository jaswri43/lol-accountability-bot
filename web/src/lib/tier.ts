import type { Tier } from "../api/types";

export const TIER_LABEL: Record<Tier, string> = {
  low: "Low",
  medium: "Medium",
  high: "High",
};

// One hue, tint-to-shade -- matches the badge/chart colors defined as CSS
// vars in index.css's @theme block. High uses white text since its base
// color is dark enough to need it; low/medium stay on light tints with
// dark text, same pattern as the rest of the app's pill badges.
export const TIER_CLASSES: Record<Tier, string> = {
  low: "bg-tier-low-soft text-tier-low-text ring-tier-low-text/20",
  medium: "bg-tier-medium-soft text-tier-medium-text ring-tier-medium-text/20",
  high: "bg-tier-high text-white ring-tier-high/30",
};

export const TIER_HEX: Record<Tier, string> = {
  low: "#c9a876",
  medium: "#a97845",
  high: "#7a4f26",
};

export function formatDate(iso: string | null): string {
  if (!iso) return "—";
  const d = new Date(iso.endsWith("Z") ? iso : `${iso}Z`);
  return d.toLocaleString(undefined, {
    month: "short",
    day: "numeric",
    hour: "numeric",
    minute: "2-digit",
  });
}

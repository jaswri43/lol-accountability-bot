import type { Tier } from "../api/types";

export const TIER_LABEL: Record<Tier, string> = {
  low: "Low",
  medium: "Medium",
  high: "High",
};

export const TIER_CLASSES: Record<Tier, string> = {
  low: "bg-emerald-100 text-emerald-700 ring-emerald-600/20",
  medium: "bg-amber-100 text-amber-700 ring-amber-600/20",
  high: "bg-rose-100 text-rose-700 ring-rose-600/20",
};

export const TIER_HEX: Record<Tier, string> = {
  low: "#10b981",
  medium: "#f59e0b",
  high: "#e11d48",
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

import type { ReactNode } from "react";

/** The "big number, small tracked-out label" pattern used throughout the
 * dashboard -- a self-contained card, not just inner content, so it drops
 * straight into a grid. */
export function StatTile({
  label,
  value,
  hint,
  accent,
}: {
  label: string;
  value: ReactNode;
  hint?: ReactNode;
  accent?: boolean;
}) {
  return (
    <div className="rounded-3xl border border-hairline bg-white p-5">
      <p className="text-xs font-medium uppercase tracking-widest text-zinc-500">{label}</p>
      <p className={`mt-1 text-3xl font-medium ${accent ? "text-accent" : "text-zinc-900"}`}>{value}</p>
      {hint && <p className="mt-1 text-xs text-zinc-500">{hint}</p>}
    </div>
  );
}

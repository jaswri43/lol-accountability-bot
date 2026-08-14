import type { StatusResponse } from "../api/types";
import { OddsChart } from "./OddsChart";

/** The dashboard's signature stat gets the dark "hero" treatment (see
 * README's Phase 13 notes) -- everything else on the page is a white card. */
export function HeroOddsCard({ status }: { status: StatusResponse | null }) {
  return (
    <div className="rounded-3xl bg-hero p-6 text-white">
      <p className="text-xs font-medium uppercase tracking-widest text-zinc-400">Task severity odds</p>
      {status ? (
        <>
          <p className="mt-1 text-3xl font-medium">
            {status.pity.toFixed(1)} <span className="text-base font-light text-zinc-400">pity</span>
          </p>
          <div className="mt-4">
            <OddsChart odds={status.odds} />
          </div>
          {!status.opted_into_severity && (
            <p className="mt-2 text-xs text-zinc-400">
              Not opted in — every loss picks a Low task. Tag a task Medium or High in the Tasks tab to
              activate the pity system.
            </p>
          )}
        </>
      ) : (
        <p className="mt-4 text-sm text-zinc-400">Loading…</p>
      )}
    </div>
  );
}

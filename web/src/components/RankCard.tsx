import type { RankQueue, WinLoss } from "../api/types";
import { Sparkline } from "./Sparkline";

function TrendIndicator({ trend }: { trend: number[] }) {
  if (trend.length < 2) {
    return <span className="text-xs text-zinc-500">Not enough games tracked yet</span>;
  }
  const delta = trend[trend.length - 1] - trend[0];
  if (delta === 0) {
    return <span className="text-xs text-zinc-500">Flat over last {trend.length} games</span>;
  }
  const up = delta > 0;
  return (
    <span className={`text-xs font-medium ${up ? "text-accent-strong" : "text-zinc-500"}`}>
      {up ? "▲" : "▼"} {Math.abs(delta)} LP over last {trend.length} games
    </span>
  );
}

export function RankCard({
  label,
  rank,
  winLoss,
}: {
  label: string;
  rank: RankQueue | null;
  winLoss: WinLoss;
}) {
  return (
    <div className="rounded-3xl border border-hairline bg-white p-5">
      <p className="text-xs font-medium uppercase tracking-widest text-zinc-500">{label}</p>
      {rank ? (
        <div className="mt-2 flex items-end justify-between gap-3">
          <div>
            <p className="text-xl font-medium text-zinc-900">{rank.formatted}</p>
            <div className="mt-1">
              <TrendIndicator trend={rank.trend} />
            </div>
          </div>
          <Sparkline data={rank.trend} />
        </div>
      ) : (
        <p className="mt-2 text-sm text-zinc-500">Not ranked yet</p>
      )}
      {winLoss.wins + winLoss.losses > 0 && (
        <p className="mt-3 border-t border-hairline pt-2 text-xs text-zinc-500">
          {winLoss.wins}W - {winLoss.losses}L tracked ·{" "}
          <span className="text-zinc-700">{Math.round(winLoss.win_rate * 100)}%</span>
        </p>
      )}
    </div>
  );
}

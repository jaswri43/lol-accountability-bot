import { useEffect, useState } from "react";
import { api, ApiError } from "../api/client";
import type { Match, PityHistoryPoint, StatsOverview, StatusResponse, Task } from "../api/types";
import { useAuth } from "../context/AuthContext";
import { HeroOddsCard } from "../components/HeroOddsCard";
import { RankCard } from "../components/RankCard";
import { StatTile } from "../components/StatTile";
import { TierBreakdownCard } from "../components/TierBreakdownCard";
import { ActivityChart } from "../components/ActivityChart";
import { MatchHistoryFeed } from "../components/MatchHistoryFeed";
import { PityHistoryChart } from "../components/PityHistoryChart";
import { formatDate } from "../lib/tier";
import type { Tier, TierStat, WinLoss } from "../api/types";

const EMPTY_TIER_STAT: TierStat = { count: 0, completed: 0, completion_rate: 0 };
const EMPTY_TIER_BREAKDOWN: Record<Tier, TierStat> = {
  low: EMPTY_TIER_STAT,
  medium: EMPTY_TIER_STAT,
  high: EMPTY_TIER_STAT,
};
const EMPTY_WIN_LOSS: WinLoss = { wins: 0, losses: 0, win_rate: 0 };

export function Dashboard() {
  const { user } = useAuth();
  const [status, setStatus] = useState<StatusResponse | null>(null);
  const [tasks, setTasks] = useState<Task[] | null>(null);
  const [overview, setOverview] = useState<StatsOverview | null>(null);
  const [matches, setMatches] = useState<Match[] | null>(null);
  const [pityHistory, setPityHistory] = useState<PityHistoryPoint[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [completingId, setCompletingId] = useState<number | null>(null);

  useEffect(() => {
    Promise.all([api.status(), api.tasks("pending"), api.statsOverview(), api.matches(8), api.pityHistory(30)])
      .then(([s, t, o, m, p]) => {
        setStatus(s);
        setTasks(t);
        setOverview(o);
        setMatches(m);
        setPityHistory(p);
      })
      .catch((err: unknown) => {
        if (err instanceof ApiError) setError(err.message);
      });
  }, []);

  async function markDone(taskId: number) {
    setCompletingId(taskId);
    setError(null);
    try {
      await api.completeTask(taskId);
      // Re-fetch rather than patch local state: completing a task can
      // renumber the rest of the pending list (tier-sorted order, same
      // reasoning as Templates.tsx's create/delete), and also changes
      // overview's completion rate, tier breakdown, and activity chart --
      // more than a local pending_count decrement would ever capture.
      const [t, s, o] = await Promise.all([api.tasks("pending"), api.status(), api.statsOverview()]);
      setTasks(t);
      setStatus(s);
      setOverview(o);
    } catch (err) {
      if (err instanceof ApiError) setError(err.message);
    } finally {
      setCompletingId(null);
    }
  }

  const riotId = user?.riot_game_name
    ? `${user.riot_game_name}#${user.riot_tag_line}`
    : "Not linked yet — use /register in Discord";

  const winRate = overview ? Math.round(overview.win_loss_overall.win_rate * 100) : null;
  const completionRate = overview ? Math.round(overview.task_completion_rate * 100) : null;
  const streakLabel =
    overview && overview.streak.count > 0
      ? `${overview.streak.count}-game ${overview.streak.direction === "win" ? "win" : "loss"} streak`
      : "No streak yet";

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-normal tracking-tight text-zinc-900">
          Welcome back, {user?.discord_username}
        </h1>
        <p className="mt-1 text-sm text-zinc-500">Riot ID: {riotId}</p>
      </div>

      {error && (
        <div className="rounded-2xl bg-rose-50 px-4 py-3 text-sm text-rose-700 ring-1 ring-inset ring-rose-600/20">
          {error}
        </div>
      )}

      {/* Quick stats */}
      <div className="grid grid-cols-2 gap-4 sm:grid-cols-4">
        <StatTile label="Pending tasks" value={status ? status.pending_count : "—"} />
        <StatTile label="Win rate" value={winRate !== null ? `${winRate}%` : "—"} accent={winRate !== null && winRate >= 50} />
        <StatTile label="Streak" value={overview ? overview.streak.count || "—" : "—"} hint={overview ? streakLabel : undefined} />
        <StatTile label="Task completion" value={completionRate !== null ? `${completionRate}%` : "—"} accent />
      </div>

      {/* Hero pity/odds card + rank */}
      <div className="grid grid-cols-1 gap-4 lg:grid-cols-3">
        <div className="lg:col-span-2">
          <HeroOddsCard status={status} />
        </div>
        <div className="flex flex-col gap-4">
          <RankCard
            label="Solo/Duo"
            rank={overview?.solo_rank ?? null}
            winLoss={overview?.win_loss_solo ?? EMPTY_WIN_LOSS}
          />
          <RankCard
            label="Flex"
            rank={overview?.flex_rank ?? null}
            winLoss={overview?.win_loss_flex ?? EMPTY_WIN_LOSS}
          />
        </div>
      </div>

      {/* Tier breakdown + activity */}
      <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
        <TierBreakdownCard breakdown={overview?.tier_breakdown ?? EMPTY_TIER_BREAKDOWN} />
        <ActivityChart activity={overview?.activity ?? null} />
      </div>

      {/* Pending tasks */}
      <div className="rounded-3xl border border-hairline bg-white">
        <div className="border-b border-hairline px-5 py-4">
          <p className="text-xs font-medium uppercase tracking-widest text-zinc-500">Pending tasks</p>
        </div>
        {tasks === null ? (
          <p className="px-5 py-6 text-sm text-zinc-500">Loading…</p>
        ) : tasks.length === 0 ? (
          <p className="px-5 py-6 text-sm text-zinc-500">No pending tasks right now. 🎉</p>
        ) : (
          <ul className="divide-y divide-hairline">
            {tasks.map((task) => (
              <li key={task.id} className="flex items-center justify-between gap-4 px-5 py-4">
                <div>
                  <p className="text-sm text-zinc-900">
                    <span className="text-zinc-500">#{task.number}</span> {task.task_description}
                  </p>
                  <p className="mt-0.5 text-xs text-zinc-500">Assigned {formatDate(task.created_at)}</p>
                </div>
                <button
                  type="button"
                  disabled={completingId === task.id}
                  onClick={() => markDone(task.id)}
                  className="shrink-0 rounded-full bg-hero px-3.5 py-1.5 text-sm text-white transition-colors hover:bg-zinc-800 disabled:cursor-not-allowed disabled:opacity-50"
                >
                  {completingId === task.id ? "Marking…" : "Mark Done"}
                </button>
              </li>
            ))}
          </ul>
        )}
      </div>

      {/* Match history + pity history */}
      <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
        <MatchHistoryFeed matches={matches} />
        <PityHistoryChart points={pityHistory} />
      </div>
    </div>
  );
}

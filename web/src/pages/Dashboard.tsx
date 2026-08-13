import { useEffect, useState } from "react";
import { api, ApiError } from "../api/client";
import type { StatusResponse, Task } from "../api/types";
import { useAuth } from "../context/AuthContext";
import { OddsChart } from "../components/OddsChart";
import { formatDate } from "../lib/tier";

export function Dashboard() {
  const { user } = useAuth();
  const [status, setStatus] = useState<StatusResponse | null>(null);
  const [tasks, setTasks] = useState<Task[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [completingId, setCompletingId] = useState<number | null>(null);

  useEffect(() => {
    Promise.all([api.status(), api.tasks("pending")])
      .then(([s, t]) => {
        setStatus(s);
        setTasks(t);
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
      setTasks((prev) => (prev ? prev.filter((t) => t.id !== taskId) : prev));
      setStatus((prev) => (prev ? { ...prev, pending_count: Math.max(0, prev.pending_count - 1) } : prev));
    } catch (err) {
      if (err instanceof ApiError) setError(err.message);
    } finally {
      setCompletingId(null);
    }
  }

  const riotId = user?.riot_game_name
    ? `${user.riot_game_name}#${user.riot_tag_line}`
    : "Not linked yet — use /register in Discord";

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-semibold text-slate-900">
          Welcome back, {user?.discord_username}
        </h1>
        <p className="mt-1 text-sm text-slate-500">Riot ID: {riotId}</p>
      </div>

      {error && (
        <div className="rounded-md bg-rose-50 px-4 py-3 text-sm text-rose-700 ring-1 ring-inset ring-rose-600/20">
          {error}
        </div>
      )}

      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
        <div className="rounded-xl border border-slate-200 bg-white p-5 shadow-sm">
          <p className="text-sm font-medium text-slate-500">Pending tasks</p>
          <p className="mt-1 text-3xl font-semibold text-slate-900">
            {status ? status.pending_count : "—"}
          </p>
        </div>

        <div className="rounded-xl border border-slate-200 bg-white p-5 shadow-sm">
          <p className="text-sm font-medium text-slate-500">Task severity odds</p>
          {status ? (
            <>
              <OddsChart odds={status.odds} />
              {!status.opted_into_severity && (
                <p className="mt-1 text-xs text-slate-400">
                  Not opted in — every loss picks a Low task. Tag a task Medium or High in the
                  Tasks tab to activate the pity system.
                </p>
              )}
            </>
          ) : (
            <p className="mt-2 text-sm text-slate-400">Loading…</p>
          )}
        </div>
      </div>

      <div className="rounded-xl border border-slate-200 bg-white shadow-sm">
        <div className="border-b border-slate-200 px-5 py-4">
          <h2 className="text-base font-semibold text-slate-900">Pending tasks</h2>
        </div>
        {tasks === null ? (
          <p className="px-5 py-6 text-sm text-slate-400">Loading…</p>
        ) : tasks.length === 0 ? (
          <p className="px-5 py-6 text-sm text-slate-500">
            No pending tasks right now. 🎉
          </p>
        ) : (
          <ul className="divide-y divide-slate-100">
            {tasks.map((task) => (
              <li key={task.id} className="flex items-center justify-between gap-4 px-5 py-4">
                <div>
                  <p className="text-sm font-medium text-slate-900">
                    <span className="text-slate-400">#{task.number}</span> {task.task_description}
                  </p>
                  <p className="mt-0.5 text-xs text-slate-400">
                    Assigned {formatDate(task.created_at)}
                  </p>
                </div>
                <button
                  type="button"
                  disabled={completingId === task.id}
                  onClick={() => markDone(task.id)}
                  className="shrink-0 rounded-md bg-emerald-600 px-3 py-1.5 text-sm font-medium text-white transition-colors hover:bg-emerald-500 disabled:cursor-not-allowed disabled:opacity-50"
                >
                  {completingId === task.id ? "Marking…" : "Mark Done"}
                </button>
              </li>
            ))}
          </ul>
        )}
      </div>
    </div>
  );
}

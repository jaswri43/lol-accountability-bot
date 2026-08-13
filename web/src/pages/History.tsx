import { useEffect, useState } from "react";
import { api, ApiError } from "../api/client";
import type { Task } from "../api/types";
import { formatDate } from "../lib/tier";

function StatusBadge({ status }: { status: string }) {
  const done = status === "done";
  return (
    <span
      className={`inline-flex items-center rounded-full px-2.5 py-0.5 text-xs font-medium ring-1 ring-inset ${
        done
          ? "bg-emerald-100 text-emerald-700 ring-emerald-600/20"
          : "bg-slate-100 text-slate-600 ring-slate-500/20"
      }`}
    >
      {done ? "Done" : "Pending"}
    </span>
  );
}

export function History() {
  const [tasks, setTasks] = useState<Task[] | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    api
      .tasks("all")
      .then(setTasks)
      .catch((err: unknown) => {
        if (err instanceof ApiError) setError(err.message);
      });
  }, []);

  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-semibold text-slate-900">Task History</h1>

      {error && (
        <div className="rounded-md bg-rose-50 px-4 py-3 text-sm text-rose-700 ring-1 ring-inset ring-rose-600/20">
          {error}
        </div>
      )}

      <div className="overflow-hidden rounded-xl border border-slate-200 bg-white shadow-sm">
        {tasks === null ? (
          <p className="px-5 py-6 text-sm text-slate-400">Loading…</p>
        ) : tasks.length === 0 ? (
          <p className="px-5 py-6 text-sm text-slate-500">No tasks yet.</p>
        ) : (
          <div className="overflow-x-auto">
            <table className="min-w-full divide-y divide-slate-100">
              <thead className="bg-slate-50">
                <tr>
                  <th className="px-5 py-3 text-left text-xs font-semibold uppercase tracking-wide text-slate-500">
                    #
                  </th>
                  <th className="px-5 py-3 text-left text-xs font-semibold uppercase tracking-wide text-slate-500">
                    Task
                  </th>
                  <th className="px-5 py-3 text-left text-xs font-semibold uppercase tracking-wide text-slate-500">
                    Status
                  </th>
                  <th className="px-5 py-3 text-left text-xs font-semibold uppercase tracking-wide text-slate-500">
                    Assigned
                  </th>
                  <th className="px-5 py-3 text-left text-xs font-semibold uppercase tracking-wide text-slate-500">
                    Completed
                  </th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100">
                {tasks.map((task) => (
                  <tr key={task.id}>
                    <td className="px-5 py-3 text-sm text-slate-400">{task.number}</td>
                    <td className="px-5 py-3 text-sm text-slate-900">{task.task_description}</td>
                    <td className="px-5 py-3">
                      <StatusBadge status={task.status} />
                    </td>
                    <td className="px-5 py-3 text-sm text-slate-500">
                      {formatDate(task.created_at)}
                    </td>
                    <td className="px-5 py-3 text-sm text-slate-500">
                      {formatDate(task.completed_at)}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </div>
  );
}

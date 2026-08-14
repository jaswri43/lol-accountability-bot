import { useEffect, useState } from "react";
import { api, ApiError } from "../api/client";
import type { Task } from "../api/types";
import { formatDate } from "../lib/tier";

function StatusBadge({ status }: { status: string }) {
  const done = status === "done";
  return (
    <span
      className={`inline-flex items-center rounded-full px-2.5 py-0.5 text-xs font-medium ${
        done ? "bg-accent-soft text-accent-strong" : "bg-zinc-100 text-zinc-500"
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
      <h1 className="text-2xl font-normal tracking-tight text-zinc-900">Task History</h1>

      {error && (
        <div className="rounded-2xl bg-rose-50 px-4 py-3 text-sm text-rose-700 ring-1 ring-inset ring-rose-600/20">
          {error}
        </div>
      )}

      <div className="overflow-hidden rounded-3xl border border-hairline bg-white">
        {tasks === null ? (
          <p className="px-5 py-6 text-sm text-zinc-500">Loading…</p>
        ) : tasks.length === 0 ? (
          <p className="px-5 py-6 text-sm text-zinc-500">No tasks yet.</p>
        ) : (
          <div className="overflow-x-auto">
            <table className="min-w-full divide-y divide-hairline">
              <thead className="bg-zinc-50/60">
                <tr>
                  <th className="px-5 py-3 text-left text-xs font-medium uppercase tracking-widest text-zinc-500">
                    #
                  </th>
                  <th className="px-5 py-3 text-left text-xs font-medium uppercase tracking-widest text-zinc-500">
                    Task
                  </th>
                  <th className="px-5 py-3 text-left text-xs font-medium uppercase tracking-widest text-zinc-500">
                    Status
                  </th>
                  <th className="px-5 py-3 text-left text-xs font-medium uppercase tracking-widest text-zinc-500">
                    Assigned
                  </th>
                  <th className="px-5 py-3 text-left text-xs font-medium uppercase tracking-widest text-zinc-500">
                    Completed
                  </th>
                </tr>
              </thead>
              <tbody className="divide-y divide-hairline">
                {tasks.map((task) => (
                  <tr key={task.id}>
                    <td className="px-5 py-3 text-sm text-zinc-500">{task.number}</td>
                    <td className="px-5 py-3 text-sm text-zinc-900">{task.task_description}</td>
                    <td className="px-5 py-3">
                      <StatusBadge status={task.status} />
                    </td>
                    <td className="px-5 py-3 text-sm text-zinc-500">{formatDate(task.created_at)}</td>
                    <td className="px-5 py-3 text-sm text-zinc-500">{formatDate(task.completed_at)}</td>
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

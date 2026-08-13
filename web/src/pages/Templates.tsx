import { useEffect, useState, type FormEvent } from "react";
import { api, ApiError } from "../api/client";
import type { TaskTemplate, Tier } from "../api/types";
import { TierBadge } from "../components/TierBadge";

export function Templates() {
  const [templates, setTemplates] = useState<TaskTemplate[] | null>(null);
  const [description, setDescription] = useState("");
  const [tier, setTier] = useState<Tier>("low");
  const [submitting, setSubmitting] = useState(false);
  const [deletingId, setDeletingId] = useState<number | null>(null);
  const [error, setError] = useState<string | null>(null);

  function load() {
    api
      .templates()
      .then(setTemplates)
      .catch((err: unknown) => {
        if (err instanceof ApiError) setError(err.message);
      });
  }

  useEffect(load, []);

  async function handleSubmit(e: FormEvent) {
    e.preventDefault();
    if (!description.trim()) return;
    setSubmitting(true);
    setError(null);
    try {
      const created = await api.createTemplate(description.trim(), tier);
      setTemplates((prev) => (prev ? [...prev, created] : [created]));
      setDescription("");
      setTier("low");
    } catch (err) {
      if (err instanceof ApiError) setError(err.message);
    } finally {
      setSubmitting(false);
    }
  }

  async function handleDelete(id: number) {
    setDeletingId(id);
    setError(null);
    try {
      await api.deleteTemplate(id);
      setTemplates((prev) =>
        prev ? prev.map((t) => (t.id === id ? { ...t, active: false } : t)) : prev,
      );
    } catch (err) {
      if (err instanceof ApiError) setError(err.message);
    } finally {
      setDeletingId(null);
    }
  }

  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-semibold text-slate-900">Task Templates</h1>

      {error && (
        <div className="rounded-md bg-rose-50 px-4 py-3 text-sm text-rose-700 ring-1 ring-inset ring-rose-600/20">
          {error}
        </div>
      )}

      <form
        onSubmit={handleSubmit}
        className="flex flex-col gap-3 rounded-xl border border-slate-200 bg-white p-5 shadow-sm sm:flex-row sm:items-end"
      >
        <div className="flex-1">
          <label htmlFor="description" className="block text-sm font-medium text-slate-700">
            New task
          </label>
          <input
            id="description"
            type="text"
            value={description}
            onChange={(e) => setDescription(e.target.value)}
            placeholder="e.g. Do 20 pushups"
            maxLength={500}
            className="mt-1 w-full rounded-md border border-slate-300 px-3 py-2 text-sm shadow-sm focus:border-indigo-500 focus:outline-none focus:ring-1 focus:ring-indigo-500"
          />
        </div>
        <div>
          <label htmlFor="tier" className="block text-sm font-medium text-slate-700">
            Tier
          </label>
          <select
            id="tier"
            value={tier}
            onChange={(e) => setTier(e.target.value as Tier)}
            className="mt-1 rounded-md border border-slate-300 px-3 py-2 text-sm shadow-sm focus:border-indigo-500 focus:outline-none focus:ring-1 focus:ring-indigo-500"
          >
            <option value="low">Low</option>
            <option value="medium">Medium</option>
            <option value="high">High</option>
          </select>
        </div>
        <button
          type="submit"
          disabled={submitting || !description.trim()}
          className="rounded-md bg-indigo-600 px-4 py-2 text-sm font-medium text-white transition-colors hover:bg-indigo-500 disabled:cursor-not-allowed disabled:opacity-50"
        >
          {submitting ? "Adding…" : "Add task"}
        </button>
      </form>

      <div className="rounded-xl border border-slate-200 bg-white shadow-sm">
        {templates === null ? (
          <p className="px-5 py-6 text-sm text-slate-400">Loading…</p>
        ) : templates.length === 0 ? (
          <p className="px-5 py-6 text-sm text-slate-500">
            No tasks yet — add one above. Losses fall back to a generic default until you do.
          </p>
        ) : (
          <ul className="divide-y divide-slate-100">
            {templates.map((template) => (
              <li key={template.id} className="flex items-center justify-between gap-4 px-5 py-4">
                <div className="flex items-center gap-3">
                  <span className="w-6 shrink-0 text-sm text-slate-400">
                    {template.number ?? "—"}
                  </span>
                  <span
                    className={`text-sm ${
                      template.active ? "text-slate-900" : "text-slate-400 line-through"
                    }`}
                  >
                    {template.description}
                  </span>
                  <TierBadge tier={template.tier} />
                </div>
                {template.active ? (
                  <button
                    type="button"
                    disabled={deletingId === template.id}
                    onClick={() => handleDelete(template.id)}
                    className="shrink-0 rounded-md border border-slate-200 px-3 py-1.5 text-sm font-medium text-rose-600 transition-colors hover:bg-rose-50 disabled:cursor-not-allowed disabled:opacity-50"
                  >
                    {deletingId === template.id ? "Removing…" : "Remove"}
                  </button>
                ) : (
                  <span className="shrink-0 text-xs text-slate-400">Removed</span>
                )}
              </li>
            ))}
          </ul>
        )}
      </div>
    </div>
  );
}

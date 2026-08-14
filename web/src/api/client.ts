import type {
  Match,
  Me,
  PityHistoryPoint,
  StatsOverview,
  StatusResponse,
  Task,
  TaskTemplate,
  Tier,
} from "./types";

const BASE = "/api";

export class ApiError extends Error {
  status: number;
  constructor(status: number, message: string) {
    super(message);
    this.status = status;
  }
}

/** Fetch wrapper shared by every endpoint call below: always sends the
 * session cookie, and treats a 401 as "log in again" uniformly rather than
 * leaving each call site to handle it separately. The initial auth check in
 * AuthContext deliberately does NOT go through this (see its own comment)
 * since a 401 there is the normal, expected "not logged in yet" case. */
async function apiFetch<T>(path: string, options: RequestInit = {}): Promise<T> {
  const res = await fetch(`${BASE}${path}`, {
    ...options,
    credentials: "include",
    headers: {
      "Content-Type": "application/json",
      ...options.headers,
    },
  });

  if (res.status === 401) {
    window.location.reload();
    throw new ApiError(401, "Not authenticated");
  }

  if (!res.ok) {
    const body = await res.json().catch(() => ({}));
    throw new ApiError(res.status, body.detail ?? `Request failed (${res.status})`);
  }

  if (res.status === 204) {
    return undefined as T;
  }
  return res.json() as Promise<T>;
}

export const api = {
  me: () => apiFetch<Me>("/me"),
  status: () => apiFetch<StatusResponse>("/status"),
  tasks: (status: "pending" | "all" = "pending") =>
    apiFetch<Task[]>(`/tasks?status=${status}`),
  completeTask: (id: number) => apiFetch<Task>(`/tasks/${id}/complete`, { method: "POST" }),
  templates: () => apiFetch<TaskTemplate[]>("/task-templates"),
  createTemplate: (description: string, tier: Tier) =>
    apiFetch<TaskTemplate>("/task-templates", {
      method: "POST",
      body: JSON.stringify({ description, tier }),
    }),
  deleteTemplate: (id: number) => apiFetch<void>(`/task-templates/${id}`, { method: "DELETE" }),
  logout: () => apiFetch<{ ok: boolean }>("/auth/logout", { method: "POST" }),
  statsOverview: () => apiFetch<StatsOverview>("/stats/overview"),
  matches: (limit = 10) => apiFetch<Match[]>(`/matches?limit=${limit}`),
  pityHistory: (limit = 50) => apiFetch<PityHistoryPoint[]>(`/pity-history?limit=${limit}`),
};

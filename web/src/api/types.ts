// Mirrors api/schemas.py exactly -- keep these in sync with the backend.

export type Tier = "low" | "medium" | "high";

export interface Task {
  id: number;
  match_id: string;
  task_description: string;
  status: string;
  created_at: string;
  completed_at: string | null;
}

export interface TaskTemplate {
  id: number;
  description: string;
  active: boolean;
  tier: Tier | null;
  created_at: string;
}

export interface StatusResponse {
  pending_count: number;
  opted_into_severity: boolean;
  pity: number;
  odds: { low: number; medium: number; high: number };
}

export interface Me {
  discord_id: number;
  discord_username: string;
  riot_game_name: string | null;
  riot_tag_line: string | null;
  registered_at: string | null;
  muted: boolean;
}

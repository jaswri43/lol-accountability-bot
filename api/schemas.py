"""Pydantic request/response models for the API."""

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field


class TaskOut(BaseModel):
    id: int
    # Cosmetic 1-indexed position within the list this task was returned
    # in (see bot/cosmetic.py) -- NOT a stored value, just this response's
    # ordering. Only `id` is ever valid for POST /tasks/{id}/complete.
    number: int
    match_id: str
    task_description: str
    status: str
    created_at: datetime
    completed_at: datetime | None

    model_config = {"from_attributes": True}


class TaskTemplateOut(BaseModel):
    id: int
    # Cosmetic position among the user's ACTIVE templates only (matching
    # /mytasks and /removetask in Discord) -- null for inactive/removed
    # templates, which aren't part of that numbered list. Only `id` is
    # ever valid for DELETE /task-templates/{id}.
    number: int | None
    description: str
    active: bool
    tier: str | None
    created_at: datetime

    model_config = {"from_attributes": True}


class TaskTemplateCreate(BaseModel):
    description: str = Field(min_length=1, max_length=500)
    # No "threshold" concept exists on task_templates in the current schema
    # (only description/active/tier) -- just tier here.
    tier: Literal["low", "medium", "high"] = "low"


class StatusOut(BaseModel):
    pending_count: int
    opted_into_severity: bool
    pity: float
    odds: dict[str, float]


class MeOut(BaseModel):
    discord_id: int
    discord_username: str
    riot_game_name: str | None
    riot_tag_line: str | None
    registered_at: datetime | None
    muted: bool


class RankQueueOut(BaseModel):
    tier: str
    rank: str
    lp: int
    formatted: str
    # Recent lp_after values for this queue, oldest first, capped to the
    # last handful of games -- a sparkline data source, not a full chart.
    # Empty (not missing) until enough post-migration games exist.
    trend: list[int]


class WinLossOut(BaseModel):
    wins: int
    losses: int
    win_rate: float


class StreakOut(BaseModel):
    direction: Literal["win", "loss"]
    count: int


class TierStatOut(BaseModel):
    count: int
    completed: int
    completion_rate: float


class ActivityPointOut(BaseModel):
    date: str
    count: int


class StatsOverviewOut(BaseModel):
    solo_rank: RankQueueOut | None
    flex_rank: RankQueueOut | None
    win_loss_overall: WinLossOut
    win_loss_solo: WinLossOut
    win_loss_flex: WinLossOut
    streak: StreakOut
    task_completion_rate: float
    tier_breakdown: dict[str, TierStatOut]
    activity: list[ActivityPointOut]


class MatchTaskOut(BaseModel):
    id: int
    task_description: str
    status: str


class MatchOut(BaseModel):
    match_id: str
    queue: str
    was_loss: bool
    champion: str | None
    kills: int | None
    deaths: int | None
    assists: int | None
    detected_at: datetime
    task: MatchTaskOut | None


class PityHistoryPointOut(BaseModel):
    pity: float
    recorded_at: datetime

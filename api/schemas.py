"""Pydantic request/response models for the API."""

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field


class TaskOut(BaseModel):
    id: int
    match_id: str
    task_description: str
    status: str
    created_at: datetime
    completed_at: datetime | None

    model_config = {"from_attributes": True}


class TaskTemplateOut(BaseModel):
    id: int
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

"""Picks the accountability task assigned after a ranked loss."""

import random

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from db import TaskTemplate

DEFAULT_TASK_DESCRIPTION = "Do 10 pushups"


async def pick_task_for_user(session: AsyncSession, discord_id: int) -> tuple[str, bool]:
    """Return (description, used_fallback) for a user's next accountability task.

    Picks randomly among the user's active task_templates rows. If they
    haven't added any yet, falls back to a generic default so the loss ->
    task flow always has something to assign.
    """
    result = await session.execute(
        select(TaskTemplate).where(
            TaskTemplate.discord_id == discord_id, TaskTemplate.active.is_(True)
        )
    )
    templates = result.scalars().all()

    if not templates:
        return DEFAULT_TASK_DESCRIPTION, True

    return random.choice(templates).description, False

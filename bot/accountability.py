"""Picks the accountability task assigned after a ranked loss."""

import random

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from db import TaskTemplate

DEFAULT_TASK_DESCRIPTION = "Do 10 pushups"


async def pick_task_for_user(
    session: AsyncSession, discord_id: int, tier: str | None = None
) -> tuple[str, str | None]:
    """Return (description, note) for a user's next accountability task.

    Picks randomly among the user's active task_templates rows. If `tier` is
    given (severity mode), prefers templates tagged with that tier, falling
    back to any active template if none match rather than leaving the user
    with no task at all. If they haven't added any templates at all, falls
    back to a generic default.

    note is one of:
      - None: normal pick, nothing to flag to the caller
      - "no_templates": no active templates at all, used the generic default
      - "tier_fallback": had active templates but none tagged `tier`
    """
    result = await session.execute(
        select(TaskTemplate).where(
            TaskTemplate.discord_id == discord_id, TaskTemplate.active.is_(True)
        )
    )
    templates = result.scalars().all()

    if not templates:
        return DEFAULT_TASK_DESCRIPTION, "no_templates"

    if tier is not None:
        tier_templates = [t for t in templates if t.tier == tier]
        if tier_templates:
            return random.choice(tier_templates).description, None
        return random.choice(templates).description, "tier_fallback"

    return random.choice(templates).description, None

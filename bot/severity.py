"""Pity-based task-severity system.

There's no on/off toggle -- a user is "in" severity mode the moment they've
tagged at least one active task Medium or High via /addtask (see
has_opted_into_severity below). Until then, every task they add defaults to
Low, pity never accrues, and losses behave exactly like the pre-severity
plain-random pick. This is what makes the feature invisible to anyone who
never engages with tiers at all.

Once opted in, the user's `pity` float (users.pity) rises on counted ranked
losses and falls on counted ranked wins. Tier odds (Low/Medium/High) are
computed fresh every time by linearly interpolating between a DEFAULT
distribution (pity = 0) and a MAX distribution (pity >= PITY_CAP) -- there's
no separate "banked" state beyond the pity number itself.

Remakes never touch pity at all; that exclusion is enforced by callers (see
polling.py) via riot_api.is_remake, not here.
"""

import random

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from db import TaskTemplate

# Tier odds at pity == 0 and pity >= PITY_CAP. Tune these (and PITY_CAP) to
# change how aggressively severity ramps up -- nothing else needs to change.
DEFAULT_ODDS = {"low": 0.6, "medium": 0.3, "high": 0.1}
MAX_ODDS = {"low": 0.2, "medium": 0.4, "high": 0.4}
PITY_CAP = 60.0

LOSS_STEP = 8.0
WIN_STEP = LOSS_STEP * 0.9  # 7.2
# Multiplier applied to pity right after a High draw, so hitting High
# doesn't just keep compounding toward more Highs forever.
RETAIN_FACTOR = 0.6

TIERS = ("low", "medium", "high")


async def has_opted_into_severity(session: AsyncSession, discord_id: int) -> bool:
    """A user is in severity mode iff they have at least one active task
    tagged Medium or High -- tagging one is the entire opt-in mechanism,
    there's no separate toggle."""
    result = await session.execute(
        select(TaskTemplate.id).where(
            TaskTemplate.discord_id == discord_id,
            TaskTemplate.active.is_(True),
            TaskTemplate.tier.in_(("medium", "high")),
        )
    )
    return result.first() is not None


def compute_odds(pity: float) -> dict[str, float]:
    """Tier odds for the given pity value, clamped to [0, PITY_CAP] and
    linearly interpolated between DEFAULT_ODDS and MAX_ODDS."""
    t = max(0.0, min(pity, PITY_CAP)) / PITY_CAP
    return {tier: DEFAULT_ODDS[tier] + t * (MAX_ODDS[tier] - DEFAULT_ODDS[tier]) for tier in TIERS}


def draw_tier(odds: dict[str, float]) -> str:
    """Randomly draw a tier from a {tier: probability} mapping."""
    tiers = list(odds.keys())
    weights = [odds[tier] for tier in tiers]
    return random.choices(tiers, weights=weights, k=1)[0]


def apply_loss_pity(user) -> str:
    """Draw a tier from the user's CURRENT (pre-loss) pity, then update
    pity for a counted loss: += LOSS_STEP, then soft-reset (*= RETAIN_FACTOR)
    if the draw was High. Returns the drawn tier. Mutates user.pity in
    place -- caller commits.
    """
    tier = draw_tier(compute_odds(user.pity))

    user.pity += LOSS_STEP
    if tier == "high":
        user.pity *= RETAIN_FACTOR

    return tier


def apply_win_pity(user) -> None:
    """Update pity for a counted win: -= WIN_STEP, floored at 0. Mutates
    user.pity in place -- caller commits."""
    user.pity = max(0.0, user.pity - WIN_STEP)

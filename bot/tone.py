"""Picks the wording/color for a loss announcement based on the user's
current consecutive-loss streak. Tone only -- never affects which task
gets assigned, its difficulty, or anything else about the task itself.
"""

import random

import discord

TIER_1_MESSAGES = [  # streak == 1
    "Rough game. Here's your task:",
    "Took an L. Time to lock in on something else:",
    "That's a loss. Accountability task incoming:",
]

TIER_2_MESSAGES = [  # streak 2-3
    "That's {streak} in a row now. Here's your task:",
    "{streak} losses back-to-back -- might be time for a water break. Task:",
    "{streak} straight losses. Let's turn this around off the Rift:",
]

TIER_3_MESSAGES = [  # streak 4+
    "{streak} LOSSES IN A ROW. This is a certified losing streak. Task:",
    "Okay, {streak} in a row is a problem. Go touch grass. Task:",
    "{streak} straight L's. At this point the task is basically mandatory:",
]


def pick_intro(streak: int) -> str:
    """Return an intro line for the loss announcement, worded for the
    caller's current consecutive-loss streak (1, 2-3, or 4+)."""
    if streak <= 1:
        template = random.choice(TIER_1_MESSAGES)
    elif streak <= 3:
        template = random.choice(TIER_2_MESSAGES)
    else:
        template = random.choice(TIER_3_MESSAGES)

    return template.format(streak=streak)


def pick_color(streak: int) -> discord.Color:
    """Escalate the embed's side color along with streak severity."""
    if streak <= 1:
        return discord.Color.orange()
    elif streak <= 3:
        return discord.Color.red()
    else:
        return discord.Color.dark_red()


# Tier-based wording, used instead of the streak-based intro/color above
# whenever a severity tier was drawn (see severity.py) -- light/cheerful for
# Low, more pointed for Medium, most emphatic for High. Never affects which
# task gets assigned, only how the announcement reads.
LOW_TIER_MESSAGES = [
    "Low tier task, not too bad:",
    "That's a loss, but a light one. Here's your task:",
    "Could be worse. Task:",
]

MEDIUM_TIER_MESSAGES = [
    "Medium severity this time -- step it up. Task:",
    "That one stings a bit more. Task:",
    "Medium tier. Let's go:",
]

HIGH_TIER_MESSAGES = [
    "HIGH SEVERITY. No mercy this time. Task:",
    "That's a big one. High tier task incoming:",
    "Maximum severity drawn. Get to it:",
]

TIER_MESSAGES = {"low": LOW_TIER_MESSAGES, "medium": MEDIUM_TIER_MESSAGES, "high": HIGH_TIER_MESSAGES}
TIER_COLORS = {"low": discord.Color.orange(), "medium": discord.Color.red(), "high": discord.Color.dark_red()}


def pick_severity_intro(tier: str) -> str:
    """Return an intro line for the loss announcement, worded for the
    drawn severity tier ("low"/"medium"/"high")."""
    return random.choice(TIER_MESSAGES[tier])


def pick_severity_color(tier: str) -> discord.Color:
    """Escalate the embed's side color along with the drawn severity tier."""
    return TIER_COLORS[tier]

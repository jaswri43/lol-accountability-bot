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

"""Picks the accountability task assigned after a ranked loss."""

import random

TASK_POOL = [
    "Apply to one job posting today.",
    "Send one cold outreach email today.",
    "Do a 15-minute workout today.",
]


def random_task() -> str:
    return random.choice(TASK_POOL)

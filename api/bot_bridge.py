"""Bridges the api/ package to the existing bot/ code without duplicating it.

bot/'s modules use bare imports (`from db import ...`) because the bot is run
as `python bot/main.py`, which puts bot/ on sys.path[0] automatically. The
API process doesn't get that for free since it's launched from api/main.py
instead, so this module inserts bot/ onto sys.path itself, then re-exports
what the rest of api/ needs. Import from here, not from `db`/`severity`/
`accountability` directly, so the path setup always happens before those
imports regardless of what order api/'s own modules get imported in.
"""

import sys
from pathlib import Path

_BOT_DIR = Path(__file__).resolve().parent.parent / "bot"
if str(_BOT_DIR) not in sys.path:
    sys.path.insert(0, str(_BOT_DIR))

from db import (
    Task,
    TaskTemplate,
    User,
    async_session,
    complete_task,
    init_db,
)
from severity import compute_odds, has_opted_into_severity
from accountability import DEFAULT_TASK_DESCRIPTION
from cosmetic import number_items, resolve_cosmetic_number

__all__ = [
    "Task",
    "TaskTemplate",
    "User",
    "async_session",
    "complete_task",
    "init_db",
    "compute_odds",
    "has_opted_into_severity",
    "DEFAULT_TASK_DESCRIPTION",
    "number_items",
    "resolve_cosmetic_number",
]

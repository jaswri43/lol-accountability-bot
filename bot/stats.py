"""Pure statistics computations over already-fetched DB rows -- no session
or DB access here, that orchestration lives in the callers (polling.py,
api/routes.py via bot_bridge). Kept separate from ranked.py (which compares
two rank snapshots) and severity.py (which drives the pity/tier draw): this
is a distinct concern, summarizing history for display rather than driving
any behavior.
"""

from collections import defaultdict
from datetime import datetime, timedelta, timezone
from typing import Sequence

TIERS = ("low", "medium", "high")


def match_chronological_key(match_id: str) -> int:
    """Riot match ids are '{platformId}_{gameId}'; gameId increases
    monotonically per platform, giving a reliable recency ordering that
    doesn't depend on DB insertion order."""
    return int(match_id.rsplit("_", 1)[1])


def sort_matches_recent_first(matches: Sequence) -> list:
    """ProcessedMatch rows, newest game first."""
    return sorted(matches, key=lambda m: match_chronological_key(m.match_id), reverse=True)


def current_streak(matches_recent_first: Sequence) -> tuple[str, int]:
    """(direction, count) for the current win/loss streak, given
    ProcessedMatch rows already sorted newest-first (see
    sort_matches_recent_first). direction is "win" or "loss"; ("loss", 0)
    if there's no history at all."""
    if not matches_recent_first:
        return "loss", 0

    direction = "loss" if matches_recent_first[0].was_loss else "win"
    count = 0
    for match in matches_recent_first:
        if (direction == "loss") != match.was_loss:
            break
        count += 1
    return direction, count


def loss_streak_length(matches_recent_first: Sequence) -> int:
    """How many of the most recent games in a row were losses -- 0 if the
    most recent game was a win, or there's no history. What
    polling.py's loss-announcement footer has always shown; kept as its own
    function so that specific "always the loss count, 0 otherwise"
    semantics doesn't need reinterpreting at each call site."""
    direction, count = current_streak(matches_recent_first)
    return count if direction == "loss" else 0


def win_loss_record(matches: Sequence) -> dict:
    """{'wins', 'losses', 'win_rate'} for whatever set of ProcessedMatch
    rows is passed in -- callers filter by queue_id first (see
    riot_api.RANKED_QUEUE_IDS) to scope this to ranked games, and further by
    queue if they want a per-queue split rather than overall."""
    wins = sum(1 for m in matches if not m.was_loss)
    losses = sum(1 for m in matches if m.was_loss)
    total = wins + losses
    return {"wins": wins, "losses": losses, "win_rate": wins / total if total else 0.0}


def task_completion_rate(tasks: Sequence) -> float:
    """Fraction of the given tasks with status == 'done'. 0.0 if empty --
    there's no 'expired' status in this app, only pending/done."""
    if not tasks:
        return 0.0
    done = sum(1 for t in tasks if t.status == "done")
    return done / len(tasks)


def tier_breakdown(tasks: Sequence) -> dict[str, dict]:
    """{'low'/'medium'/'high': {'count', 'completed', 'completion_rate'}}
    for the given tasks, keyed by Task.tier (never None post-migration, see
    db.py's backfill, but treated as 'low' defensively anyway)."""
    by_tier: dict[str, list] = {tier: [] for tier in TIERS}
    for task in tasks:
        by_tier.setdefault(task.tier or "low", []).append(task)

    return {
        tier: {
            "count": len(tier_tasks),
            "completed": sum(1 for t in tier_tasks if t.status == "done"),
            "completion_rate": task_completion_rate(tier_tasks),
        }
        for tier, tier_tasks in by_tier.items()
    }


def tasks_completed_by_day(tasks: Sequence, days: int = 14) -> list[dict]:
    """[{'date': 'YYYY-MM-DD', 'count': n}, ...] for the last `days` days
    (oldest first, one entry per day even if 0), counting each task on the
    UTC calendar day it was completed. Only considers tasks with a
    completed_at set."""
    today = datetime.now(timezone.utc).date()
    counts: dict = defaultdict(int)
    for task in tasks:
        if task.completed_at is None:
            continue
        counts[task.completed_at.date()] += 1

    start = today - timedelta(days=days - 1)
    return [
        {"date": (start + timedelta(days=i)).isoformat(), "count": counts.get(start + timedelta(days=i), 0)}
        for i in range(days)
    ]

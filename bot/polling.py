"""Background loops: one polls each registered user's recent ranked matches
for losses and assigns an accountability task for each new one found; the
other periodically reminds users about accountability tasks they still
haven't completed.

processed_matches is what makes match-polling idempotent across poll
cycles/restarts: a (match_id, discord_id) pair is only ever handled once.
Muted users (users.muted) are skipped entirely by both loops.
"""

import logging
from datetime import datetime, timedelta, timezone

import discord
from discord.ext import tasks
from sqlalchemy import or_, select

from accountability import pick_task_for_user
from db import ProcessedMatch, Task, User, async_session
from riot_api import (
    RANKED_QUEUE_IDS,
    RiotAPIError,
    did_player_lose,
    get_match_details,
    get_match_ids_by_puuid,
)

log = logging.getLogger("bot.polling")

POLL_INTERVAL_MINUTES = 5
MATCHES_TO_CHECK = 10

# How often the reminder loop checks for/sends reminders, and (deliberately
# the same value) how long since a task's last reminder before it's due for
# another one -- keeps a still-pending task from getting re-pinged every run.
REMINDER_INTERVAL_HOURS = 3
# Don't remind about a task until it's been pending at least this long.
MIN_TASK_AGE_HOURS = 2

_started = False
_reminders_started = False


def start_polling(bot: discord.Client, channel_id: int) -> None:
    """Start the polling loop. Safe to call more than once (e.g. on_ready
    firing again after a reconnect) -- only starts it the first time."""
    global _started
    if _started:
        return
    _started = True

    @tasks.loop(minutes=POLL_INTERVAL_MINUTES)
    async def poll_matches():
        async with async_session() as session:
            users = (
                await session.execute(select(User).where(User.muted.is_(False)))
            ).scalars().all()

        for user in users:
            await _check_user(bot, channel_id, user)

    @poll_matches.before_loop
    async def before_poll():
        await bot.wait_until_ready()

    poll_matches.start()
    log.info(f"Started match-polling loop (every {POLL_INTERVAL_MINUTES}m)")


def start_reminders(bot: discord.Client, channel_id: int) -> None:
    """Start the task-reminder loop. Safe to call more than once -- only
    starts it the first time, same as start_polling."""
    global _reminders_started
    if _reminders_started:
        return
    _reminders_started = True

    @tasks.loop(hours=REMINDER_INTERVAL_HOURS)
    async def send_reminders():
        await _send_reminders(bot, channel_id)

    @send_reminders.before_loop
    async def before_reminders():
        await bot.wait_until_ready()

    send_reminders.start()
    log.info(f"Started task-reminder loop (every {REMINDER_INTERVAL_HOURS}h)")


async def _send_reminders(bot: discord.Client, channel_id: int) -> None:
    channel = bot.get_channel(channel_id)
    if channel is None:
        log.error(f"Announce channel {channel_id} not found/accessible; skipping reminders")
        return

    now = datetime.now(timezone.utc)
    task_cutoff = now - timedelta(hours=MIN_TASK_AGE_HOURS)
    reminder_cutoff = now - timedelta(hours=REMINDER_INTERVAL_HOURS)

    async with async_session() as session:
        result = await session.execute(
            select(Task)
            .join(User, User.discord_id == Task.discord_id)
            .where(
                Task.status == "pending",
                Task.created_at <= task_cutoff,
                User.muted.is_(False),
                or_(Task.last_reminded_at.is_(None), Task.last_reminded_at <= reminder_cutoff),
            )
        )
        due_tasks = result.scalars().all()
        if not due_tasks:
            return

        by_user: dict[int, list[Task]] = {}
        for task in due_tasks:
            by_user.setdefault(task.discord_id, []).append(task)

        for discord_id, tasks_for_user in by_user.items():
            lines = "\n".join(f"- #{t.id}: {t.task_description}" for t in tasks_for_user)
            await channel.send(
                f"<@{discord_id}> reminder: you still have {len(tasks_for_user)} pending "
                f"accountability task(s):\n{lines}"
            )
            for task in tasks_for_user:
                task.last_reminded_at = now

        await session.commit()


async def seed_existing_matches(user: User) -> None:
    """Mark a newly-registered user's current ranked match history as already
    processed, so the polling loop won't retroactively assign tasks for games
    played before they registered -- only losses from here on get flagged."""
    try:
        match_ids = await get_match_ids_by_puuid(
            user.riot_puuid, count=MATCHES_TO_CHECK, queue_type="ranked"
        )
    except RiotAPIError as e:
        log.error(f"Failed to seed match history for {user.riot_game_name}#{user.riot_tag_line}: {e}")
        return

    async with async_session() as session:
        for match_id in match_ids:
            already_processed = await session.get(ProcessedMatch, (match_id, user.discord_id))
            if already_processed is not None:
                continue

            try:
                match = await get_match_details(match_id)
            except RiotAPIError as e:
                log.error(f"Failed to seed match {match_id}: {e}")
                continue

            was_loss = match["info"]["queueId"] in RANKED_QUEUE_IDS and did_player_lose(match, user.riot_puuid)
            session.add(ProcessedMatch(match_id=match_id, discord_id=user.discord_id, was_loss=was_loss))

        await session.commit()


async def _check_user(bot: discord.Client, channel_id: int, user: User) -> None:
    try:
        match_ids = await get_match_ids_by_puuid(
            user.riot_puuid, count=MATCHES_TO_CHECK, queue_type="ranked"
        )
    except RiotAPIError as e:
        log.error(f"Failed to fetch match ids for {user.riot_game_name}#{user.riot_tag_line}: {e}")
        return

    async with async_session() as session:
        for match_id in match_ids:
            already_processed = await session.get(ProcessedMatch, (match_id, user.discord_id))
            if already_processed is not None:
                continue

            try:
                match = await get_match_details(match_id)
            except RiotAPIError as e:
                log.error(f"Failed to fetch match {match_id}: {e}")
                continue

            # type=ranked already excludes normals/ARAM/etc, but double-check
            # queueId so only Solo/Duo (420) and Flex (440) get flagged.
            if match["info"]["queueId"] not in RANKED_QUEUE_IDS:
                session.add(ProcessedMatch(match_id=match_id, discord_id=user.discord_id, was_loss=False))
                continue

            was_loss = did_player_lose(match, user.riot_puuid)
            session.add(ProcessedMatch(match_id=match_id, discord_id=user.discord_id, was_loss=was_loss))

            if was_loss:
                await _assign_task(session, bot, channel_id, user, match_id)

        await session.commit()


async def _assign_task(session, bot: discord.Client, channel_id: int, user: User, match_id: str) -> None:
    description, used_fallback = await pick_task_for_user(session, user.discord_id)
    task = Task(discord_id=user.discord_id, match_id=match_id, task_description=description)
    session.add(task)
    await session.flush()  # populate task.id before we reference it in the message

    channel = bot.get_channel(channel_id)
    if channel is None:
        log.error(f"Announce channel {channel_id} not found/accessible; task #{task.id} created but not posted")
        return

    fallback_note = (
        "\n(No custom tasks set for you yet -- use `/addtask` to customize this.)" if used_fallback else ""
    )
    message = await channel.send(
        f"<@{user.discord_id}> took a ranked loss. Accountability task (#{task.id}): **{description}**\n"
        f"Mark it done with `/done task_id:{task.id}` or by reacting with ✅ below.{fallback_note}"
    )
    task.message_id = message.id

    try:
        await message.add_reaction("✅")
    except discord.HTTPException:
        log.error(f"Failed to add checkmark reaction to task #{task.id} message")

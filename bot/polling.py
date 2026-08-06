"""Background loop that polls each registered user's recent ranked matches
for losses and assigns an accountability task for each new one found.

processed_matches is what makes this idempotent across poll cycles/restarts:
a (match_id, discord_id) pair is only ever handled once.
"""

import logging

import discord
from discord.ext import tasks
from sqlalchemy import select

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

_started = False


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
            users = (await session.execute(select(User))).scalars().all()

        for user in users:
            await _check_user(bot, channel_id, user)

    @poll_matches.before_loop
    async def before_poll():
        await bot.wait_until_ready()

    poll_matches.start()
    log.info(f"Started match-polling loop (every {POLL_INTERVAL_MINUTES}m)")


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

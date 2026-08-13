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
from cosmetic import number_items, sort_by_tier_then_date
from db import ProcessedMatch, Task, User, async_session
from ranked import describe_change, format_rank, format_tier_rank
from riot_api import (
    QUEUE_ID_LABELS,
    QUEUE_ID_TO_QUEUE_TYPE,
    RANKED_QUEUE_IDS,
    RANKED_SOLO_QUEUE_ID,
    RiotAPIError,
    did_player_lose,
    get_match_details,
    get_match_ids_by_puuid,
    get_participant,
    get_ranked_stats,
    is_remake,
)
from severity import apply_loss_pity, apply_win_pity, has_opted_into_severity
from tone import pick_color, pick_intro, pick_severity_color, pick_severity_intro
from views import TaskCompletionView

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
        # An uncaught exception here would stop this tasks.loop permanently
        # (it doesn't auto-retry next interval like a normal cron job would),
        # so log-and-continue at both the per-user and whole-cycle level.
        try:
            async with async_session() as session:
                users = (
                    await session.execute(select(User).where(User.muted.is_(False)))
                ).scalars().all()

            for user in users:
                try:
                    await _check_user(bot, channel_id, user)
                except Exception:
                    log.exception(
                        f"Unexpected error checking {user.riot_game_name}#{user.riot_tag_line}; "
                        "skipping them this cycle"
                    )
        except Exception:
            log.exception("Unexpected error in match-polling loop; will retry next cycle")

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
        try:
            await _send_reminders(bot, channel_id)
        except Exception:
            log.exception("Unexpected error in reminder loop; will retry next cycle")

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
            # Number against the user's full pending list (same set/order
            # /status and /done use), not just this due-for-reminder
            # subset -- otherwise a number shown here could resolve to a
            # different task via /done than the one it's actually next to.
            all_pending_result = await session.execute(
                select(Task)
                .where(Task.discord_id == discord_id, Task.status == "pending")
                .order_by(Task.created_at)
            )
            all_pending = sort_by_tier_then_date(all_pending_result.scalars().all())
            number_by_id = {t.id: n for n, t in number_items(all_pending)}

            lines = "\n".join(
                f"- #{number_by_id[t.id]}: {t.task_description}" for t in tasks_for_user
            )
            embed = discord.Embed(
                title="Task Reminder",
                description=f"You still have {len(tasks_for_user)} pending accountability task(s):\n{lines}",
                color=discord.Color.gold(),
            )
            embed.set_footer(text="Mark one done with /done or the Mark Done button on its original message.")
            await channel.send(content=f"<@{discord_id}>", embed=embed)
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
                await _assign_task(session, bot, channel_id, user, match_id, match)
            else:
                await _apply_win_pity(session, user, match)

        await session.commit()


async def _apply_win_pity(session, user: User, match: dict) -> None:
    """Ease off pity on a counted ranked win, for users who've opted into
    severity by tagging a Medium/High task. No-op otherwise, and for
    remakes (excluded entirely)."""
    if is_remake(match, user.riot_puuid) or not await has_opted_into_severity(session, user.discord_id):
        return
    tracked_user = await session.get(User, user.discord_id)
    apply_win_pity(tracked_user)


def _match_chronological_key(match_id: str) -> int:
    """Riot match ids are '{platformId}_{gameId}'; gameId increases
    monotonically per platform, giving a reliable recency ordering that
    doesn't depend on the order matches happened to be fetched/inserted in
    (which can vary when several new matches are found in one poll cycle)."""
    return int(match_id.rsplit("_", 1)[1])


async def _get_current_loss_streak(session, discord_id: int) -> int:
    """How many of the user's most recent ranked games in a row were losses,
    stopping at the first win or the start of their recorded history."""
    result = await session.execute(select(ProcessedMatch).where(ProcessedMatch.discord_id == discord_id))
    matches = sorted(
        result.scalars().all(), key=lambda m: _match_chronological_key(m.match_id), reverse=True
    )

    streak = 0
    for match in matches:
        if not match.was_loss:
            break
        streak += 1
    return streak


async def _update_rank_tracking(session, user: User, queue_id: int) -> tuple[str | None, discord.Embed | None]:
    """Fetch current ranked stats, compute the LP change since the last
    stored snapshot for this queue, update the stored snapshot, and build a
    separate rank-change announcement embed if the tier/rank changed.

    Returns (rank_field_text, rank_change_embed) -- either may be None:
    rank_field_text is None if the user isn't ranked in this queue at all
    (not placed yet); rank_change_embed is None unless a promotion/demotion
    just happened.
    """
    queue_type = QUEUE_ID_TO_QUEUE_TYPE.get(queue_id)
    if queue_type is None:
        return None, None

    try:
        stats = await get_ranked_stats(user.riot_puuid)
    except RiotAPIError as e:
        log.error(f"Failed to fetch ranked stats for {user.riot_game_name}#{user.riot_tag_line}: {e}")
        return None, None

    new_entry = stats.get(queue_type)
    if new_entry is None:
        return None, None  # unranked/not placed in this queue -- nothing to track yet

    # `user` may be a detached instance loaded by an earlier, already-closed
    # session; re-fetch through the active session so the mutations below
    # are actually picked up when the caller commits.
    tracked_user = await session.get(User, user.discord_id)

    is_solo = queue_id == RANKED_SOLO_QUEUE_ID
    old_tier = tracked_user.solo_tier if is_solo else tracked_user.flex_tier
    old_entry = None
    if old_tier is not None:
        old_entry = {
            "tier": old_tier,
            "rank": tracked_user.solo_rank if is_solo else tracked_user.flex_rank,
            "leaguePoints": tracked_user.solo_lp if is_solo else tracked_user.flex_lp,
        }

    lp_change, changed, direction = describe_change(old_entry, new_entry)

    if is_solo:
        tracked_user.solo_tier = new_entry["tier"]
        tracked_user.solo_rank = new_entry["rank"]
        tracked_user.solo_lp = new_entry["leaguePoints"]
    else:
        tracked_user.flex_tier = new_entry["tier"]
        tracked_user.flex_rank = new_entry["rank"]
        tracked_user.flex_lp = new_entry["leaguePoints"]

    queue_label = QUEUE_ID_LABELS[queue_id]

    if changed and old_entry is not None:
        went_up = direction == "up"
        announcement = discord.Embed(
            title="Promotion! \U0001f53c" if went_up else "Demotion \U0001f53d",
            description=(
                f"<@{user.discord_id}> {'ranked up' if went_up else 'dropped'} in "
                f"**{queue_label}**: {format_rank(old_entry)} → {format_rank(new_entry)}"
            ),
            color=discord.Color.gold() if went_up else discord.Color.dark_grey(),
        )
        return format_rank(new_entry), announcement

    if lp_change is not None:
        sign = "+" if lp_change >= 0 else ""
        return f"{format_tier_rank(new_entry)} ({new_entry['leaguePoints']} LP, {sign}{lp_change})", None

    return format_rank(new_entry), None


async def _assign_task(
    session, bot: discord.Client, channel_id: int, user: User, match_id: str, match: dict
) -> None:
    opted_in = await has_opted_into_severity(session, user.discord_id)
    counted = opted_in and not is_remake(match, user.riot_puuid)

    tier: str | None = None
    if counted:
        tracked_user = await session.get(User, user.discord_id)
        tier = apply_loss_pity(tracked_user)  # draws from pre-loss pity, then updates it in place

    description, note = await pick_task_for_user(session, user.discord_id, tier=tier)
    # Stores the drawn severity tier (what the pity system decided this
    # loss was worth), not necessarily the tier of the specific template
    # `description` came from -- pick_task_for_user can fall back to a
    # different tier's template (note == "tier_fallback") when none exist
    # for the drawn one yet. "low" for non-opted-in/non-counted losses,
    # matching task_templates' own default.
    task = Task(
        discord_id=user.discord_id,
        match_id=match_id,
        task_description=description,
        tier=tier if tier is not None else "low",
    )
    session.add(task)
    await session.flush()  # populate task.id (and let the streak query below see this match)

    streak = await _get_current_loss_streak(session, user.discord_id)

    channel = bot.get_channel(channel_id)
    if channel is None:
        log.error(f"Announce channel {channel_id} not found/accessible; task #{task.id} created but not posted")
        return

    queue_id = match["info"]["queueId"]
    participant = get_participant(match, user.riot_puuid)
    kda = f"{participant['kills']}/{participant['deaths']}/{participant['assists']}"
    champion = participant["championName"]
    queue_label = QUEUE_ID_LABELS.get(queue_id, "Ranked")

    rank_field, rank_announcement = await _update_rank_tracking(session, user, queue_id)

    if note == "no_templates":
        extra_note = "\n*(No custom tasks set for you yet -- use `/addtask` to customize this.)*"
    elif note == "tier_fallback":
        extra_note = f"\n*(No **{tier}** tier tasks set up yet -- use `/addtask` with a tier to customize this.)*"
    else:
        extra_note = ""

    if tier is not None:
        intro, color = pick_severity_intro(tier), pick_severity_color(tier)
    else:
        intro, color = pick_intro(streak), pick_color(streak)

    # Cosmetic position within the user's current pending list (same
    # set/order /status and /done use) -- shown instead of task.id so the
    # `/done number:` hint below actually resolves to this task.
    pending_result = await session.execute(
        select(Task)
        .where(Task.discord_id == user.discord_id, Task.status == "pending")
        .order_by(Task.created_at)
    )
    pending_for_numbering = sort_by_tier_then_date(pending_result.scalars().all())
    number_by_id = {t.id: n for n, t in number_items(pending_for_numbering)}
    task_number = number_by_id[task.id]

    embed = discord.Embed(
        title="Ranked Loss",
        description=(
            f"{intro}\n\n"
            f"**Task #{task_number}:** {description}\n\n"
            f"Mark it done with the button below or `/done number:{task_number}`.{extra_note}"
        ),
        color=color,
    )
    embed.add_field(name="Champion", value=champion, inline=True)
    embed.add_field(name="KDA", value=kda, inline=True)
    embed.add_field(name="Queue", value=queue_label, inline=True)
    if rank_field is not None:
        embed.add_field(name="Rank", value=rank_field, inline=True)
    embed.set_footer(text=f"Current streak: {streak} loss{'es' if streak != 1 else ''}")

    message = await channel.send(content=f"<@{user.discord_id}>", embed=embed, view=TaskCompletionView())
    task.message_id = message.id

    if rank_announcement is not None:
        await channel.send(embed=rank_announcement)

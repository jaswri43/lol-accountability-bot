"""
LoL Accountability Bot - entry point.

Connects to Discord, registers slash commands (/register, /done, /addtask,
/mytasks, /removetask, /status, /stats), and starts the background
match-polling loop that assigns accountability tasks after ranked losses.
"""

import logging
import os
from datetime import datetime, timezone

import discord
from discord import app_commands
from discord.ext import commands
from dotenv import load_dotenv
from sqlalchemy import select

from db import Task, TaskTemplate, User, async_session, init_db
from polling import seed_existing_matches, start_polling
from riot_api import RiotAPIError, get_account_by_riot_id

load_dotenv()

DISCORD_TOKEN = os.getenv("DISCORD_TOKEN")
GUILD_ID = os.getenv("GUILD_ID")  # optional: set this for instant command sync during dev
ANNOUNCE_CHANNEL_ID = os.getenv("ANNOUNCE_CHANNEL_ID")  # where loss/task messages get posted

logging.basicConfig(level=logging.INFO)
log = logging.getLogger("bot")

intents = discord.Intents.default()
intents.message_content = True

bot = commands.Bot(command_prefix="!", intents=intents)


@bot.event
async def on_ready():
    log.info(f"Logged in as {bot.user} (id: {bot.user.id})")

    await init_db()
    log.info("Database initialized")

    if GUILD_ID:
        # Syncing to a specific guild is near-instant, useful while developing.
        guild = discord.Object(id=int(GUILD_ID))
        bot.tree.copy_global_to(guild=guild)
        synced = await bot.tree.sync(guild=guild)
        log.info(f"Synced {len(synced)} command(s) to guild {GUILD_ID}")
    else:
        # Global sync can take up to an hour to propagate the first time.
        synced = await bot.tree.sync()
        log.info(f"Synced {len(synced)} command(s) globally")

    if ANNOUNCE_CHANNEL_ID:
        start_polling(bot, int(ANNOUNCE_CHANNEL_ID))
    else:
        log.warning("ANNOUNCE_CHANNEL_ID is not set; match polling will not start")


@bot.tree.command(name="ping", description="Check that the bot is alive")
async def ping(interaction: discord.Interaction):
    await interaction.response.send_message("Pong! Bot is up and running.")


@bot.tree.command(name="register", description="Link your Riot ID to your Discord account")
@app_commands.describe(
    game_name="Your Riot ID name (the part before the #)",
    tag_line="Your Riot ID tag (the part after the #, without the #)",
)
async def register(interaction: discord.Interaction, game_name: str, tag_line: str):
    await interaction.response.defer()

    try:
        account = await get_account_by_riot_id(game_name, tag_line)
    except RiotAPIError as e:
        if e.status_code == 404:
            await interaction.followup.send(
                f"No Riot account found for **{game_name}#{tag_line}**. Double-check the spelling and try again."
            )
        else:
            log.error(f"Riot API error during /register: {e}")
            await interaction.followup.send(
                "Something went wrong talking to the Riot API. Please try again in a moment."
            )
        return
    except Exception:
        log.exception("Unexpected error during /register")
        await interaction.followup.send(
            "Something unexpected went wrong. Please try again in a moment."
        )
        return

    async with async_session() as session:
        user = await session.get(User, interaction.user.id)
        if user is None:
            user = User(discord_id=interaction.user.id)
            session.add(user)

        user.riot_puuid = account["puuid"]
        user.riot_game_name = account["gameName"]
        user.riot_tag_line = account["tagLine"]

        await session.commit()

    await seed_existing_matches(user)

    await interaction.followup.send(
        f"You're now tracked as **{account['gameName']} #{account['tagLine']}**."
    )


async def _complete_task(session, task: Task) -> None:
    """Shared by /done and the ✅-reaction listener so completion is defined
    in exactly one place."""
    task.status = "done"
    task.completed_at = datetime.now(timezone.utc)


@bot.tree.command(name="done", description="Mark an accountability task as complete")
@app_commands.describe(
    task_id="The task ID from the reminder message. Leave blank to mark your most recent pending task done."
)
async def done(interaction: discord.Interaction, task_id: int | None = None):
    async with async_session() as session:
        if task_id is not None:
            task = await session.get(Task, task_id)
            if task is None or task.discord_id != interaction.user.id:
                await interaction.response.send_message(
                    f"No task #{task_id} found for you.", ephemeral=True
                )
                return
        else:
            result = await session.execute(
                select(Task)
                .where(Task.discord_id == interaction.user.id, Task.status == "pending")
                .order_by(Task.created_at.desc())
            )
            task = result.scalars().first()
            if task is None:
                await interaction.response.send_message(
                    "You don't have any pending accountability tasks.", ephemeral=True
                )
                return

        if task.status != "pending":
            await interaction.response.send_message(
                f"Task #{task.id} is already marked **{task.status}**.", ephemeral=True
            )
            return

        await _complete_task(session, task)
        await session.commit()

    await interaction.response.send_message(f"Task #{task.id} marked done: **{task.task_description}**")


@bot.tree.command(name="addtask", description="Add a custom accountability task to your rotation")
@app_commands.describe(description="What you'll do when you lose a ranked game")
async def addtask(interaction: discord.Interaction, description: str):
    async with async_session() as session:
        user = await session.get(User, interaction.user.id)
        if user is None:
            await interaction.response.send_message(
                "You need to /register first before adding tasks.", ephemeral=True
            )
            return

        template = TaskTemplate(discord_id=interaction.user.id, description=description)
        session.add(template)
        await session.commit()

    await interaction.response.send_message(f"Added task #{template.id}: **{description}**")


@bot.tree.command(name="mytasks", description="List your active accountability task templates")
async def mytasks(interaction: discord.Interaction):
    async with async_session() as session:
        result = await session.execute(
            select(TaskTemplate)
            .where(TaskTemplate.discord_id == interaction.user.id, TaskTemplate.active.is_(True))
            .order_by(TaskTemplate.id)
        )
        templates = result.scalars().all()

    if not templates:
        await interaction.response.send_message(
            "You don't have any custom tasks yet. Add one with `/addtask`.", ephemeral=True
        )
        return

    lines = [f"#{t.id}: {t.description}" for t in templates]
    await interaction.response.send_message("Your active tasks:\n" + "\n".join(lines), ephemeral=True)


@bot.tree.command(name="removetask", description="Deactivate one of your custom accountability tasks")
@app_commands.describe(task_id="The task template id shown in /mytasks")
async def removetask(interaction: discord.Interaction, task_id: int):
    async with async_session() as session:
        template = await session.get(TaskTemplate, task_id)
        if template is None or template.discord_id != interaction.user.id:
            await interaction.response.send_message(
                f"No task template #{task_id} found for you.", ephemeral=True
            )
            return

        template.active = False
        await session.commit()

    await interaction.response.send_message(f"Removed task #{task_id}: **{template.description}**")


@bot.tree.command(name="status", description="Show your currently pending accountability tasks")
async def status(interaction: discord.Interaction):
    async with async_session() as session:
        result = await session.execute(
            select(Task)
            .where(Task.discord_id == interaction.user.id, Task.status == "pending")
            .order_by(Task.created_at)
        )
        pending = result.scalars().all()

    if not pending:
        await interaction.response.send_message("You have no pending accountability tasks. \U0001f389", ephemeral=True)
        return

    lines = [
        f"#{t.id}: **{t.task_description}** (assigned {t.created_at.strftime('%Y-%m-%d %H:%M UTC')})"
        for t in pending
    ]
    await interaction.response.send_message("Your pending tasks:\n" + "\n".join(lines), ephemeral=True)


@bot.tree.command(name="stats", description="Show your accountability task completion counts")
async def stats(interaction: discord.Interaction):
    async with async_session() as session:
        result = await session.execute(select(Task).where(Task.discord_id == interaction.user.id))
        all_tasks = result.scalars().all()

    total = len(all_tasks)
    completed = sum(1 for t in all_tasks if t.status == "done")
    pending = sum(1 for t in all_tasks if t.status == "pending")

    await interaction.response.send_message(
        f"**Your stats**\nTotal tasks: {total}\nCompleted: {completed}\nPending: {pending}",
        ephemeral=True,
    )


@bot.event
async def on_raw_reaction_add(payload: discord.RawReactionActionEvent):
    if bot.user is not None and payload.user_id == bot.user.id:
        return
    if str(payload.emoji) != "✅":
        return

    async with async_session() as session:
        result = await session.execute(select(Task).where(Task.message_id == payload.message_id))
        task = result.scalars().first()
        if task is None or task.discord_id != payload.user_id or task.status != "pending":
            return

        await _complete_task(session, task)
        await session.commit()

    channel = bot.get_channel(payload.channel_id)
    if channel is not None:
        await channel.send(
            f"<@{payload.user_id}> marked task #{task.id} done via reaction: **{task.task_description}**"
        )


def main():
    if not DISCORD_TOKEN:
        raise RuntimeError("DISCORD_TOKEN is not set. Check your .env file.")
    bot.run(DISCORD_TOKEN)


if __name__ == "__main__":
    main()

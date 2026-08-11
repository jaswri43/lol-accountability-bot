"""
LoL Accountability Bot - entry point.

Connects to Discord, registers slash commands (/register, /mute, /unmute,
/severity, /done, /addtask, /mytasks, /removetask, /status, /stats, /help),
registers the persistent Mark Done button view, and starts the background
loops that assign accountability tasks after ranked losses and periodically
remind users of ones still pending.
"""

import logging
import logging.handlers
import os

import discord
from discord import app_commands
from discord.ext import commands
from dotenv import load_dotenv
from sqlalchemy import select

from db import Task, TaskTemplate, User, async_session, complete_task, init_db
from polling import seed_existing_matches, start_polling, start_reminders
from riot_api import RiotAPIError, get_account_by_riot_id
from severity import compute_odds
from views import TaskCompletionView

load_dotenv()

DISCORD_TOKEN = os.getenv("DISCORD_TOKEN")
GUILD_ID = os.getenv("GUILD_ID")  # optional: set this for instant command sync during dev
ANNOUNCE_CHANNEL_ID = os.getenv("ANNOUNCE_CHANNEL_ID")  # where loss/task messages get posted

# Rotating file handler (5MB x 3 backups) alongside stdout, so logs survive
# under systemd/journald without growing bot/logs/bot.log unbounded.
LOG_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "logs")
os.makedirs(LOG_DIR, exist_ok=True)

_log_formatter = logging.Formatter("[%(asctime)s] [%(levelname)-8s] %(name)s: %(message)s")

_console_handler = logging.StreamHandler()
_console_handler.setFormatter(_log_formatter)

_file_handler = logging.handlers.RotatingFileHandler(
    os.path.join(LOG_DIR, "bot.log"), maxBytes=5 * 1024 * 1024, backupCount=3
)
_file_handler.setFormatter(_log_formatter)

logging.basicConfig(level=logging.INFO, handlers=[_console_handler, _file_handler])
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
        start_reminders(bot, int(ANNOUNCE_CHANNEL_ID))
    else:
        log.warning("ANNOUNCE_CHANNEL_ID is not set; match polling will not start")

    # Re-registers the Mark Done button's callback for every task message
    # ever posted (not just ones from this process run) -- without this,
    # buttons on messages from before a restart stop responding entirely.
    bot.add_view(TaskCompletionView())


@bot.tree.command(name="ping", description="Check that the bot is alive")
async def ping(interaction: discord.Interaction):
    await interaction.response.send_message("Pong! Bot is up and running.")


@bot.tree.command(name="help", description="Show how to use the bot and its commands")
async def help_command(interaction: discord.Interaction):
    text = (
        "**LoL Accountability Bot**\n"
        "Tracks your ranked League of Legends losses and assigns you an accountability "
        "task each time you lose -- job hunting, workouts, whatever you set up. Complete "
        "a task with `/done` or the **Mark Done** button on its message.\n"
        "\n"
        "**Getting started**\n"
        "`/register game_name tag_line` -- link your Riot ID (e.g. `Yogurt` / `fried` for "
        "Yogurt#fried). Required before anything else works. Only ranked Solo/Duo and Flex "
        "losses from *after* you register ever get flagged -- your existing match history "
        "is never retroactively turned into tasks.\n"
        "`/mute` / `/unmute` -- pause or resume loss detection and reminders for yourself "
        "only; the other person keeps getting tracked normally.\n"
        "\n"
        "**Customizing your tasks**\n"
        "`/addtask description [tier]` -- add a task to your rotation (e.g. \"Do 20 pushups\"), "
        "optionally tagged Low/Medium/High for severity mode.\n"
        "`/mytasks` -- list your active tasks and their ids.\n"
        "`/removetask task_id` -- deactivate one of your tasks by id.\n"
        "Once you have at least one active task, losses always draw from your rotation. "
        "With none set, losses fall back to a generic default task.\n"
        "\n"
        "**Severity mode**\n"
        "`/severity` -- toggle a pity-based severity system for yourself (off by default). "
        "While on, each loss draws a Low/Medium/High severity task; the odds of a harsher "
        "draw rise the more you've been losing and ease off as you win. Tag tasks by tier "
        "with `/addtask` so the right kind of task gets picked; `/status` shows your current "
        "odds while severity mode is on.\n"
        "\n"
        "**Completing a task**\n"
        "`/done [task_id]` -- mark a task done. Leave `task_id` blank to complete your "
        "most recent pending task. Or click the **Mark Done** button on the task's "
        "announcement message in the channel -- only the person the task belongs to can "
        "complete it that way. A pending task left untouched for a while gets an "
        "occasional reminder ping in the channel.\n"
        "\n"
        "**Checking progress**\n"
        "`/status` -- your currently pending tasks.\n"
        "`/stats` -- your total/completed/pending counts.\n"
        "\n"
        "**Other**\n"
        "`/ping` -- check the bot is alive.\n"
        "`/help` -- this message."
    )
    await interaction.response.send_message(text, ephemeral=True)


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


@bot.tree.command(name="mute", description="Pause loss detection and reminders for yourself")
async def mute(interaction: discord.Interaction):
    async with async_session() as session:
        user = await session.get(User, interaction.user.id)
        if user is None:
            await interaction.response.send_message("You need to /register first.", ephemeral=True)
            return

        user.muted = True
        await session.commit()

    await interaction.response.send_message(
        "Muted -- losses won't be tracked and you won't get reminders until you `/unmute`.",
        ephemeral=True,
    )


@bot.tree.command(name="unmute", description="Resume loss detection and reminders for yourself")
async def unmute(interaction: discord.Interaction):
    async with async_session() as session:
        user = await session.get(User, interaction.user.id)
        if user is None:
            await interaction.response.send_message("You need to /register first.", ephemeral=True)
            return

        user.muted = False
        await session.commit()

    await interaction.response.send_message("Unmuted -- loss tracking is back on.", ephemeral=True)


@bot.tree.command(name="severity", description="Toggle pity-based task severity for yourself")
async def severity(interaction: discord.Interaction):
    async with async_session() as session:
        user = await session.get(User, interaction.user.id)
        if user is None:
            await interaction.response.send_message("You need to /register first.", ephemeral=True)
            return

        user.severity_mode = not user.severity_mode
        new_mode = user.severity_mode
        await session.commit()

    if new_mode:
        message = (
            "Severity mode is now **on**. Losses now draw a Low/Medium/High severity task "
            "based on a pity meter that builds up as you lose and eases off as you win -- "
            "check `/status` for your current odds. Tag tasks by tier with `/addtask`."
        )
    else:
        message = "Severity mode is now **off**. Losses go back to a plain random task pick."

    await interaction.response.send_message(message, ephemeral=True)


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

        await complete_task(session, task)
        await session.commit()

    await interaction.response.send_message(f"Task #{task.id} marked done: **{task.task_description}**")


@bot.tree.command(name="addtask", description="Add a custom accountability task to your rotation")
@app_commands.describe(
    description="What you'll do when you lose a ranked game",
    tier="Severity tier this task applies to when /severity mode is on (optional)",
)
@app_commands.choices(
    tier=[
        app_commands.Choice(name="Low", value="low"),
        app_commands.Choice(name="Medium", value="medium"),
        app_commands.Choice(name="High", value="high"),
    ]
)
async def addtask(
    interaction: discord.Interaction,
    description: str,
    tier: app_commands.Choice[str] | None = None,
):
    async with async_session() as session:
        user = await session.get(User, interaction.user.id)
        if user is None:
            await interaction.response.send_message(
                "You need to /register first before adding tasks.", ephemeral=True
            )
            return

        template = TaskTemplate(
            discord_id=interaction.user.id,
            description=description,
            tier=tier.value if tier is not None else None,
        )
        session.add(template)
        await session.commit()

    tier_note = f" (tier: {tier.name})" if tier is not None else ""
    await interaction.response.send_message(f"Added task #{template.id}: **{description}**{tier_note}")


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

    lines = [f"#{t.id}: {t.description}" + (f" [{t.tier}]" if t.tier else "") for t in templates]
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
        user = await session.get(User, interaction.user.id)
        result = await session.execute(
            select(Task)
            .where(Task.discord_id == interaction.user.id, Task.status == "pending")
            .order_by(Task.created_at)
        )
        pending = result.scalars().all()

    if not pending:
        embed = discord.Embed(
            description="You have no pending accountability tasks. \U0001f389",
            color=discord.Color.green(),
        )
    else:
        lines = "\n".join(
            f"#{t.id}: **{t.task_description}** (assigned {t.created_at.strftime('%Y-%m-%d %H:%M UTC')})"
            for t in pending
        )
        embed = discord.Embed(title="Pending Tasks", description=lines, color=discord.Color.blurple())

    if user is not None and user.severity_mode:
        odds = compute_odds(user.pity)
        embed.add_field(
            name="Severity Mode",
            value=f"Current odds: Low {odds['low']:.0%} / Medium {odds['medium']:.0%} / High {odds['high']:.0%}",
            inline=False,
        )

    await interaction.response.send_message(embed=embed, ephemeral=True)


@bot.tree.command(name="stats", description="Show your accountability task completion counts")
async def stats(interaction: discord.Interaction):
    async with async_session() as session:
        result = await session.execute(select(Task).where(Task.discord_id == interaction.user.id))
        all_tasks = result.scalars().all()

    total = len(all_tasks)
    completed = sum(1 for t in all_tasks if t.status == "done")
    pending = sum(1 for t in all_tasks if t.status == "pending")

    embed = discord.Embed(title="Your Stats", color=discord.Color.blurple())
    embed.add_field(name="Total", value=str(total))
    embed.add_field(name="Completed", value=str(completed))
    embed.add_field(name="Pending", value=str(pending))
    await interaction.response.send_message(embed=embed, ephemeral=True)


def main():
    if not DISCORD_TOKEN:
        raise RuntimeError("DISCORD_TOKEN is not set. Check your .env file.")
    # log_handler=None: we already configured logging above (console + rotating
    # file); without this, discord.py additionally installs its own handler and
    # every log line gets printed twice in two different formats.
    bot.run(DISCORD_TOKEN, log_handler=None)


if __name__ == "__main__":
    main()

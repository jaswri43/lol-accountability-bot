"""
LoL Accountability Bot - entry point.

For now this just connects to Discord and registers a /ping command
so we can confirm the deployment pipeline (code -> running bot -> visible
in Discord) works before adding Riot API / database logic.
"""

import logging
import os

import discord
from discord import app_commands
from discord.ext import commands
from dotenv import load_dotenv

from db import User, async_session, init_db
from riot_api import RiotAPIError, get_account_by_riot_id

load_dotenv()

DISCORD_TOKEN = os.getenv("DISCORD_TOKEN")
GUILD_ID = os.getenv("GUILD_ID")  # optional: set this for instant command sync during dev

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

    await interaction.followup.send(
        f"You're now tracked as **{account['gameName']} #{account['tagLine']}**."
    )


def main():
    if not DISCORD_TOKEN:
        raise RuntimeError("DISCORD_TOKEN is not set. Check your .env file.")
    bot.run(DISCORD_TOKEN)


if __name__ == "__main__":
    main()

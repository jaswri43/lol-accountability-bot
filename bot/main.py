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


def main():
    if not DISCORD_TOKEN:
        raise RuntimeError("DISCORD_TOKEN is not set. Check your .env file.")
    bot.run(DISCORD_TOKEN)


if __name__ == "__main__":
    main()

"""Persistent button-based task completion, replacing the old checkmark-
reaction listener. TaskCompletionView is registered once via bot.add_view()
in main.py's on_ready so the button on messages posted before a restart
keeps working -- that's what makes it "persistent" rather than a normal
view, which stops responding as soon as the process that created it exits.
"""

import logging

import discord
from sqlalchemy import select

from db import Task, async_session, complete_task

log = logging.getLogger("bot.views")

# Stable across restarts and across every task message -- required for a
# persistent view (discord.py routes a button click back to this class by
# matching this exact string, not by any in-memory Python state).
MARK_DONE_CUSTOM_ID = "lol_bot:mark_done"


class TaskCompletionView(discord.ui.View):
    def __init__(self) -> None:
        super().__init__(timeout=None)  # no timeout: required for persistence

    @discord.ui.button(label="Mark Done", emoji="✅", style=discord.ButtonStyle.success, custom_id=MARK_DONE_CUSTOM_ID)
    async def mark_done(self, interaction: discord.Interaction, button: discord.ui.Button) -> None:
        async with async_session() as session:
            result = await session.execute(select(Task).where(Task.message_id == interaction.message.id))
            task = result.scalars().first()

            if task is None:
                await interaction.response.send_message(
                    "Couldn't find a task tied to this message.", ephemeral=True
                )
                return

            if task.discord_id != interaction.user.id:
                await interaction.response.send_message("This isn't your task.", ephemeral=True)
                return

            if task.status != "pending":
                await interaction.response.send_message(
                    f"Task #{task.id} is already marked **{task.status}**.", ephemeral=True
                )
                return

            await complete_task(session, task)
            await session.commit()
            task_id = task.id

        # Build a fresh, disabled view/button for the edit rather than
        # mutating this callback's own `button`/`self`. Every task message's
        # button click gets routed through this SAME registered persistent
        # view instance, so mutating its component state here would
        # incorrectly disable the button on every other still-pending
        # task's message too, not just this one.
        done_view = discord.ui.View()
        done_view.add_item(
            discord.ui.Button(label="Done", emoji="✅", style=discord.ButtonStyle.secondary, disabled=True)
        )

        embed = interaction.message.embeds[0] if interaction.message.embeds else discord.Embed()
        embed.color = discord.Color.dark_grey()
        embed.add_field(name="Status", value=f"✅ Completed by <@{interaction.user.id}>", inline=False)

        await interaction.response.edit_message(embed=embed, view=done_view)
        log.info(f"Task #{task_id} completed via button by {interaction.user.id}")

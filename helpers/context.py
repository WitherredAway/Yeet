from __future__ import annotations

from typing import List, Optional, Tuple, Union
import typing

import discord
from discord.ext import commands

if typing.TYPE_CHECKING:
    from main import Bot


class ConfirmView(discord.ui.View):
    def __init__(
        self,
        ctx: CustomContext,
        *,
        embeds: Optional[Union[Bot.Embed, List[Bot.Embed]]] = None,
        edit_after: Optional[str] = None,
        confirm_label: Optional[str] = "Confirm",
        cancel_label: Optional[str] = "Cancel",
    ):
        super().__init__(timeout=30)
        self.ctx = ctx
        self.embeds = embeds
        self.edit_after = edit_after
        self.result: bool = False

        self.message: discord.Message
        self.confirm.label = confirm_label
        self.cancel.label = cancel_label

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id not in (self.ctx.author.id, *self.ctx.bot.owner_ids):
            await interaction.response.send_message(
                f"This instance does not belong to you.",
                ephemeral=True,
            )
            return False
        return True

    async def on_timeout(self) -> None:
        await self.message.delete()

    @discord.ui.button(label="Confirm", style=discord.ButtonStyle.green)
    async def confirm(self, interaction: discord.Interaction, button: discord.Button):
        self.result = True

        kwargs = {"view": None}
        if self.embeds:
            for embed in self.embeds:
                embed.description = self.edit_after
            kwargs["embeds"] = self.embeds
        elif self.edit_after is not None:
            kwargs["content"] = self.edit_after
        else:
            await self.message.delete()
            return self.stop()

        await self.message.edit(**kwargs)
        self.stop()

    @discord.ui.button(label="Cancel", style=discord.ButtonStyle.red)
    async def cancel(self, interaction: discord.Interaction, button: discord.Button):
        self.result = False
        await self.message.delete()
        self.stop()


class CustomContext(commands.Context):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.bot: Bot

    async def confirm(
        self,
        content: Optional[str] = None,
        *,
        embed: Optional[Union[Bot.Embed, List[Bot.Embed]]] = None,
        file: Optional[Union[discord.File, List[discord.File]]] = None,
        edit_after: Optional[str] = "Hang on...",  # None means delete
        confirm_label: Optional[str] = "Confirm",
        cancel_label: Optional[str] = "Cancel",
    ) -> Tuple[bool, discord.Message]:
        if embed and not isinstance(embed, list):
            embed = [embed]
        if file and not isinstance(file, list):
            file = [file]

        view = ConfirmView(
            self,
            embeds=embed,
            edit_after=edit_after,
            confirm_label=confirm_label,
            cancel_label=cancel_label,
        )
        view.message = await self.message.reply(
            content, embeds=embed, files=file, view=view
        )
        await view.wait()
        return view.result, view.message

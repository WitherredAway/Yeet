from __future__ import annotations
from enum import Enum

import random
from typing import List, Optional, Self
import typing
import discord
from discord.ext import commands

from helpers.context import CustomContext

if typing.TYPE_CHECKING:
    from cogs.AFD.afd import Afd


class SkipView(discord.ui.View):
    def __init__(self, remaining: List[str], *, ctx: CustomContext):
        super().__init__(timeout=300)
        self.remaining = remaining
        self.ctx = ctx

    async def on_timeout(self):
        await self.message.edit(view=None)
        self.stop()

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user != self.ctx.author:
            await interaction.response.send_message(
                f"This instance does not belong to you!",
                ephemeral=True,
            )
            return False
        return True

    @discord.ui.button(label="Skip", style=discord.ButtonStyle.red)
    async def skip_btn(
        self, interaction: discord.Interaction, button: discord.ui.Button
    ):
        await interaction.response.defer()
        self.remaining[:] = [random.choice(self.remaining)]


class RandomView(discord.ui.View):
    def __init__(
        self,
        afdcog: Afd,
        ctx: CustomContext,
        choice: str,
        pokemon_options: Optional[List[str]] = None,
    ):
        super().__init__(timeout=300)
        self.afdcog = afdcog
        self.choice = choice
        self.pokemon_options = pokemon_options
        self.ctx = ctx

    async def on_timeout(self):
        await self.message.edit(view=None)
        self.stop()

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user != self.ctx.author:
            await interaction.response.send_message(
                f"This instance does not belong to you!",
                ephemeral=True,
            )
            return False
        return True

    @discord.ui.button(label="Claim", style=discord.ButtonStyle.blurple)
    async def claim_btn(
        self, interaction: discord.Interaction, button: discord.ui.Button
    ):
        await interaction.response.defer()
        await self.afdcog.claim(self.ctx, self.choice)

    @discord.ui.button(label="Reroll", style=discord.ButtonStyle.red)
    async def reroll_btn(
        self, interaction: discord.Interaction, button: discord.ui.Button
    ):
        await interaction.response.defer()
        await self.afdcog.random(self.ctx, self.pokemon_options)

    @discord.ui.button(label="Reroll (skip)", style=discord.ButtonStyle.red)
    async def reroll_skp_btn(
        self, interaction: discord.Interaction, button: discord.ui.Button
    ):
        await interaction.response.defer()
        await self.afdcog.random(self.ctx, self.pokemon_options, skip=True)


class RandomFlagDescriptions(Enum):
    _name = "This flag can be used to specify all the pokémon that will participate in the randomizer. Otherwise it'll randomly pick 10 unclaimed pokémon."
    skip = "This flag can be used to skip the contest directly to the winner."
    claimed = "This flag can be used to include claimed pokémon to help decide which to draw. If used alone, it will instead proceed with all of your claimed pokémon."


class RandomFlags(
    commands.FlagConverter, prefix="--", delimiter=" ", case_insensitive=True
):
    name: Optional[str] = commands.flag(
        aliases=("n",), max_args=-1, description=RandomFlagDescriptions._name.value
    )
    skip: Optional[bool] = commands.flag(
        aliases=("sk",),
        default=False,
        max_args=1,
        description=RandomFlagDescriptions.skip.value,
    )
    claimed: Optional[bool] = commands.flag(
        default=False,
        max_args=1,
        description=RandomFlagDescriptions.claimed.value,
    )

    @classmethod
    async def convert(cls, ctx: CustomContext, argument: str) -> Self:
        argument = argument.replace("—", "--")
        return await super().convert(ctx, argument)

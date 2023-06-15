from __future__ import annotations
import asyncio

import re
from typing import TYPE_CHECKING, Optional
import discord
from discord.ext import commands

from cogs.utils.utils import enumerate_list, force_log_errors, reload_modules

from .ext.poketwo_chances import PoketwoChances
from .ext.poketwo_moves import PoketwoMoves

if TYPE_CHECKING:
    from main import Bot


POKETWO_ID = 716390085896962058


class Poketwo(PoketwoChances, PoketwoMoves):
    """Utility commands for the Pokétwo bot"""

    def __init__(self, bot: Bot):
        self.bot = bot
        self.pk = self.bot.pk

        self.pkm_list = list(self.pk["name.en"])

    hint_pattern = re.compile(r"The pokémon is (?P<hint>.+)\.")
    ids_pattern = re.compile(r"^`?\s*(\d+)`?\b", re.MULTILINE)

    display_emoji = "🫒"

    @force_log_errors
    async def cog_unload(self):
        reload_modules("cogs/Poketwo", skip=__name__)

    @commands.command(
        name="extract_ids",
        aliases=["ids"],
        brief="Extract pokémon IDs from Pokétwo embeds",
        help="Extract pokémon IDs from Pokétwo embeds like marketplace, inventory, etc by providing message link, ID or by replying to the message",
    )
    async def extract_ids(
        self, ctx: commands.Context, msg: Optional[discord.Message] = None
    ):
        if (ref := ctx.message.reference) is not None:
            content = ref.resolved.embeds[0].description
        elif msg is not None:
            content = msg.embeds[0].description
        else:
            return await ctx.send_help(ctx.command)

        ids = self.ids_pattern.findall(content)
        await ctx.send(" ".join(ids) or "No IDs found.")

    @commands.Cog.listener("on_message")
    async def on_message(self, message: discord.Message):
        if message.author.id != POKETWO_ID:
            return

        content = message.content
        match = self.hint_pattern.match(content)
        if match is None:
            return

        hint = match.group("hint").replace(r"\_", ".")
        hint = f"^{hint}$"
        pattern = re.compile(hint)

        pkms = []
        for pkm in self.pkm_list:
            if pattern.match(pkm):
                pkms.append(pkm)

        if len(pkms) > 1:
            pkms = enumerate_list(pkms)

        await message.channel.send("\n".join(pkms), reference=message)


async def setup(bot):
    await bot.add_cog(Poketwo(bot))

from __future__ import annotations
import asyncio

import re
from typing import TYPE_CHECKING, Optional
import discord
from discord.ext import commands

from cogs.utils.utils import enumerate_list, force_log_errors, reload_modules
from helpers.context import CustomContext

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
        aliases=("ids", "extractids"),
        brief="Extract pokémon IDs from Pokétwo embeds",
        help="Extract pokémon IDs from Pokétwo embeds like marketplace, inventory, etc by providing message link, ID or by replying to the message.",
    )
    async def extract_ids(
        self, ctx: CustomContext, msg: Optional[discord.Message] = None
    ):
        msg = msg or (
            (ref.resolved or await ctx.channel.fetch_message(ref.message_id))
            if (ref := ctx.message.reference)
            else None
        )
        if msg is not None:
            content = msg.embeds[0].description
        else:
            return await ctx.send_help(ctx.command)

        ids = self.ids_pattern.findall(content)
        await ctx.send(" ".join(ids) or "No IDs found.")

    @commands.command(
        name="resolve_id",
        aliases=("resolveid",),
        brief="Get the timestamp associated with a Pokémon ID",
        help="Get the timestamp associated with a Pokémon ID",
    )
    async def resolve_id(self, ctx: CustomContext, pokemon_id: str):
        try:
            if len(pokemon_id) < 8:
                raise ValueError

            timestamp = int(pokemon_id[:8], 16)
        except ValueError:
            content = f"`{pokemon_id}` is not a valid Pokémon ID!"
        else:
            content = f"<t:{timestamp}:F> (<t:{timestamp}:R>)"

        await ctx.reply(content)

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

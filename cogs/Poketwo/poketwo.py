from __future__ import annotations

import re
from typing import TYPE_CHECKING, List, Optional
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
        name="resolve-id",
        aliases=("resolveid",),
        brief="Get the timestamp associated with a Pokémon ID",
        help="Get the timestamp associated with a Pokémon ID",
    )
    async def resolve_id(self, ctx: CustomContext, pokemon_id: str):
        try:
            if len(pokemon_id) < 8:
                raise ValueError

            b = bytes.fromhex(pokemon_id)
            timestamp = int.from_bytes(b[:4])
        except ValueError:
            content = f"`{pokemon_id}` is not a valid Pokémon ID!"
        else:
            content = f"<t:{timestamp}:F> (<t:{timestamp}:R>)"

        await ctx.reply(content)

    def solve_hint(self, text: str, *, limit: Optional[int] = 10) -> List[str] | None:
        match = self.hint_pattern.match(text)

        official_hint = match is not None

        hint = match.group("hint") if official_hint else text
        hint = re.sub(r"\\?_", ".", hint)
        pattern = re.compile(hint, re.IGNORECASE)

        if official_hint:
            hint = f"^{hint}$"
            method = pattern.match
        else:
            hint = text
            method = pattern.search

        matches = []
        for pkm in self.pkm_list:
            if match := method(pkm):
                matches.append((match.start()/len(pkm), pkm))
        matches.sort(key=lambda m: m[0])

        return [m[1] for m in matches][:limit]

    @commands.command(
        name="solve-hint",
        aliases=("solvehint", "solve"),
        brief="Solve the hint sent by Pokétwo for a pokémon spawn",
        help=(
            "Solve the hint sent by Pokétwo for a pokémon spawn. Pass in the message/hint into this command."
        )
    )
    async def solve_hint_command(self, ctx: CustomContext, *, text: str):
        pokemon = self.solve_hint(text)
        if not pokemon:
            return await ctx.send("Could not solve that hint. Please make sure it's in the same format as posted by Pokétwo.")

        if len(pokemon) > 1:
            pokemon = enumerate_list(pokemon)

        return await ctx.send("\n".join(pokemon), reference=ctx.message)


async def setup(bot):
    await bot.add_cog(Poketwo(bot))

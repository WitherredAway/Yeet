import re
from typing import Optional
import discord
from discord.ext import commands

from cogs.utils.utils import force_log_errors, reload_modules

from .ext.poketwo_chances import PoketwoChances
from .ext.poketwo_moves import PoketwoMoves


class Poketwo(PoketwoChances, PoketwoMoves):
    """Utility commands for the Pokétwo bot"""

    pattern = re.compile(r"^`?\s*(\d+)`?\b", re.MULTILINE)

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

        ids = self.pattern.findall(content)
        await ctx.send(" ".join(ids) or "No IDs found.")


async def setup(bot):
    await bot.add_cog(Poketwo(bot))

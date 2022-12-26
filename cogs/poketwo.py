import re
from discord.ext import commands

from .Poketwo.poketwo_chances import PoketwoChances
from .Poketwo.poketwo_moves import PoketwoMoves


class Poketwo(PoketwoChances, PoketwoMoves):
    """Utility commands for the Pokétwo bot"""

    pattern = re.compile(r"^`?\s*(\d+)`?\b", re.MULTILINE)

    display_emoji = "🫒"
        
    @commands.command()
    async def ids(self, ctx):
        content = ctx.message.reference.resolved.embeds[0].description
        ids = self.pattern.findall(content)
        await ctx.send(" ".join(ids))


async def setup(bot):
    await bot.add_cog(Poketwo(bot))
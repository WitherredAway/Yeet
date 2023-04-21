from __future__ import annotations

import typing

import discord
from discord.ext import commands

if typing.TYPE_CHECKING:
    from main import Bot


class NewCog(commands.Cog):
    def __init__(self, bot: Bot):
        self.bot = bot


async def setup(bot):
    await bot.add_cog(NewCog(bot))

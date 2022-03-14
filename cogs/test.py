import discord
import random

from typing import List
from .utils.paginator import BotPages
from discord.ext import commands, menus


class Test(commands.Cog):
    """Commands for testing."""
    def __init__(self, bot):
        self.bot = bot
        self.hidden = True

    display_emoji = "🧪"


async def setup(bot):
    await bot.add_cog(Test(bot))

import discord
import random
import slash_util as slash

from main import *
from typing import List
from .utils.paginator import BotPages
from discord.ext import menus


class Test(slash.Cog):
    def __init__(self, bot):
        self.bot = bot

    display_emoji = "🧪"


def setup(bot):
    bot.add_cog(Test(bot))

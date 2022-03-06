import discord
import random

from main import *
from typing import List
from .utils.paginator import BotPages
from discord.ext import commands, menus


class Test(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    display_emoji = "🧪"


def setup(bot):
    bot.add_cog(Test(bot))

import discord
from main import *
import cogs.utils.slash as slash
import random

class Test(slash.ApplicationCog):
    def __init__(self, bot):
        super().__init__(bot)
        self.bot = bot

    display_emoji = "🧪"
    
def setup(bot):
    bot.add_cog(Test(bot))
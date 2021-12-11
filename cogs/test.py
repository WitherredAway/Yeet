import discord
from main import *

class Test(slash.ApplicationCog):
    def __init__(self, bot):
        self.bot = bot

    display_emoji = "🧪"


def setup(bot):
    bot.add_cog(Test(bot))
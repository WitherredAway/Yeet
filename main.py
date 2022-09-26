import os
import sys
import json
import datetime
import gists

import discord
from discord.ext import commands
import aiohttp

from keep_alive import keep_alive


def get_prefix(bot, message):
    prefixes = bot.PREFIXES
    if not message.guild:
        return bot.PREFIX
    return commands.when_mentioned_or(*prefixes)(bot, message)


class Bot(commands.Bot):
    PREFIXES = json.loads(os.getenv("PREFIXES"))
    PREFIX = PREFIXES[0]

    COGS = {
        "admin": "admin",
        "bot": "bot",
        "channel": "channel",
        "define": "define",
        "docs": "docs",
        "draw": "draw",
        "fun": "fun",
        "gist": "gist",
        "help": "help",
        "jishaku": "jishaku",
        "jsk": "jishaku",
        "math": "math",
        "poketwo_chances": "poketwo_chances",
        "p2c": "poketwo_chances",
        "poketwo_moves": "poketwo_moves",
        "p2m": "poketwo_moves",
        "test": "test",
        "useful": "useful",
}

    def __init__(self, **kwargs):
        super().__init__(**kwargs)

        self.uptime = datetime.datetime.utcnow()
        self.activity = discord.Game(f"{self.PREFIXES[0]}help")
        self.status = discord.Status.online

    async def setup_hook(self):
        self.LOG_CHANNEL = await self.fetch_channel(os.getenv("logCHANNEL"))

        self.session = aiohttp.ClientSession(loop=self.loop)

        self.gists_client = gists.Client()
        await self.gists_client.authorize(os.getenv("githubTOKEN"))

        for filename in set(self.COGS.values()):
            await self.load_extension(f"cogs.{filename}")

    class Embed(discord.Embed):
        def __init__(self, **kwargs):
            self.EMBED_COLOUR = 0xF1C40F

            color = kwargs.pop("color", self.EMBED_COLOUR)
            super().__init__(**kwargs, color=color)


TOKEN = os.getenv("botTOKEN")

if __name__ == "__main__":
    bot = Bot(
        command_prefix=get_prefix,
        owner_ids=[267550284979503104, 761944238887272481],
        case_insensitive=True,
        intents=discord.Intents.all(),
    )
    if os.getenv("REPL_ID") is not None:
        keep_alive()
        try:
            bot.run(TOKEN)
        except discord.errors.HTTPException as error:
            if error.response.status == 429:
                print("\033[0;31mRate-limit detected, restarting process.\033[0m")
                os.system(f"kill 1 && python3 -m {sys.argv[0]}")
    else:
        bot.run(TOKEN)

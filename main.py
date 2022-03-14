import os
import discord
import requests
import json
import datetime
import humanize

from keep_alive import keep_alive
from discord.ext import commands


COMMAND_COOLDOWN = 2  # seconds

TOKEN = os.getenv("botTOKEN")

intents = discord.Intents.default()
intents.message_content = True
intents.members = True


def get_prefix(bot, message):
    prefixes = bot.PREFIXES
    if not message.guild:
        return prefixes[0]
    return commands.when_mentioned_or(*prefixes)(bot, message)


class Bot(commands.Bot):
    PREFIXES = json.loads(os.getenv("PREFIXES"))
    PREFIX = PREFIXES[0]

    def __init__(self, **kwargs):
        super().__init__(**kwargs)

        self.LOG_CHANNEL = os.getenv("logCHANNEL")
        self.uptime = datetime.datetime.utcnow()
        self.activity = discord.Game(f"{self.PREFIXES[0]}help")
        self.status = discord.Status.online

    async def setup_hook(self):
        #self.load_extension("jishaku")
        for filename in os.listdir("./cogs"):
            if filename.endswith(".py"):
               await self.load_extension(f"cogs.{filename[:-3]}")

    class Embed(discord.Embed):
        def __init__(self, **kwargs):
            self.EMBED_COLOUR = 0xF1C40F

            color = kwargs.pop("color", self.EMBED_COLOUR)
            super().__init__(**kwargs, color=color)


bot = Bot(
    command_prefix=get_prefix,
    owner_ids=[267550284979503104, 761944238887272481],
    case_insensitive=True,
    intents=intents,
)

r = requests.head(url="https://discord.com/api/v1")
if r.headers.get("Retry-After", None):
    print(f"Rate limit {round(int(r.headers['Retry-After']) / 60, 2)} minutes left")
else:
    print(f"No rate limit.")
    keep_alive()
    bot.run(TOKEN)

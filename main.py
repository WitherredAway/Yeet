import os
import sys
import datetime
import asyncio
import aiohttp
import logging

import discord
from discord.ext import commands
from cogs.draw_utils.colour import Colour
import gists

from keep_alive import keep_alive


logger = logging.basicConfig()


def get_prefix(bot, message):
    prefixes = bot.PREFIXES
    if not message.guild:
        return bot.PREFIX
    return commands.when_mentioned_or(*prefixes)(bot, message)


class Bot(commands.Bot):
    PREFIXES = os.getenv("PREFIXES").split(", ")
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
        "poketwo": "poketwo",
        "p2": "poketwo",
        "test": "test",
        "useful": "useful",
    }

    def __init__(self, **kwargs):
        super().__init__(**kwargs)

        self.uptime = datetime.datetime.utcnow()
        self.activity = discord.Game(f"{self.PREFIXES[0]}help")
        self.status = discord.Status.online

        self.lock = asyncio.Lock()

    async def setup_hook(self):
        self.EMOJI_SERVER_IDS = [
            1019908440786735144,
            1019908649293979718,
            1019908721343741952,
            1019908780617633804,
            1019908871717933077,
        ]
        self.EMOJI_SERVERS = [
            await self.fetch_guild(_id) for _id in self.EMOJI_SERVER_IDS
        ]

        self.STATUS_CHANNEL = await self.fetch_channel(os.getenv("statusCHANNEL"))
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

    async def upload_emoji(self, colour: Colour) -> discord.Emoji:
        # Look if emoji already exists
        for guild in self.EMOJI_SERVERS:
            guild_emojis = await guild.fetch_emojis()
            for guild_emoji in guild_emojis:
                if colour.hex == guild_emoji.name:
                    return guild_emoji

        # Emoji does not exist already, proceed to create
        for guild in self.EMOJI_SERVERS:
            try:
                emoji = await colour.to_emoji(guild)
            except discord.HTTPException:
                continue
            else:
                return emoji
        else:  # If it exits without returning aka there was no space available
            emoji_delete = (await self.EMOJI_SERVERS[0].fetch_emojis())[0]  # Get first emoji from the first emoji server
            await emoji_delete.delete()  # Delete the emoji to make space for the new one
            await self.upload_emoji(colour)  # Run again

    


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
        except discord.HTTPException as error:
            if error.response.status == 429:
                print("\033[0;31mRate-limit detected, restarting process.\033[0m")
                os.system(f"kill 1 && python3 {sys.argv[0]}")
    else:
        bot.run(TOKEN)

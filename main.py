from __future__ import annotations

import os
import sys
import datetime
import asyncio
import aiohttp
import logging

import discord
from typing import Union
from discord.ext import commands
from cogs.draw_utils.colour import Colour
import gists

from constants import LOG_BORDER, NL
from keep_alive import keep_alive
from cogs.draw_utils.emoji_cache import EmojiCache
from cogs.draw import DrawView


logging.basicConfig(level=logging.INFO)
log = logging.getLogger(__name__)


def get_prefix(bot, message):
    prefixes = bot.PREFIXES
    if not message.guild:
        return bot.PREFIX
    return commands.when_mentioned_or(*prefixes)(bot, message)


class Bot(commands.Bot):
    PREFIXES = os.getenv("PREFIXES").split(", ")
    PREFIX = PREFIXES[0]

    COGS = {
        "afd_2023": "afd_2023",
        "afd": "afd_2023",
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

        self.emoji_cache: EmojiCache = EmojiCache(bot=self)

        self.lock = asyncio.Lock()

    @property
    def invite_url(self) -> str:
        perms = discord.Permissions.none()
        perms.send_messages = True
        perms.read_messages = True
        perms.read_message_history = True
        perms.add_reactions = True
        perms.external_emojis = True
        perms.external_stickers = True
        perms.manage_channels = True
        perms.manage_messages = True
        perms.manage_emojis = True
        perms.attach_files = True
        perms.embed_links = True
        return discord.utils.oauth_url(self.user.id, permissions=perms)

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

        self.status_channel = await self.fetch_channel(os.getenv("statusCHANNEL"))
        self.log_channel = await self.fetch_channel(os.getenv("logCHANNEL"))

        self.session = aiohttp.ClientSession(loop=self.loop)

        self.gists_client = gists.Client()
        await self.gists_client.authorize(os.getenv("githubTOKEN"))

        for filename in set(self.COGS.values()):
            await self.load_extension(f"cogs.{filename}")

        total_s: int = (datetime.datetime.utcnow()-self.uptime).seconds
        m, s = divmod(total_s, 60)
        msg = f"\033[32;1m{self.user}\033[0;32m connected in \033[33;1m{m}m{s}s\033[0;32m.\033[0m"
        await self.status_channel.send(f"```ansi\n{msg}\n```")
        log.info(msg)

    class Embed(discord.Embed):
        def __init__(self, **kwargs):
            self.EMBED_COLOUR = 0xF1C40F

            color = kwargs.pop("color", self.EMBED_COLOUR)
            super().__init__(**kwargs, color=color)

    async def upload_emoji(
        self, colour: Colour, *, draw_view: DrawView, interaction: discord.Interaction
    ) -> Union[discord.Emoji, discord.PartialEmoji]:
        # First look if there is cache of the emoji
        if (emoji := self.emoji_cache.get_emoji(colour.hex)) is not None:
            return emoji

        async with draw_view.disable(interaction=interaction):
            # Look if emoji already exists in a server
            guild_emoji_lists = []
            for guild in self.EMOJI_SERVERS:
                guild_emojis = await guild.fetch_emojis()
                guild_emoji_lists.append(guild_emojis)
                for guild_emoji in guild_emojis:
                    if colour.hex == guild_emoji.name:
                        self.emoji_cache.add_emoji(guild_emoji)
                        return guild_emoji

            # Emoji does not exist already, proceed to create
            for guild in self.EMOJI_SERVERS:
                try:
                    emoji = await colour.to_emoji(guild)
                except discord.HTTPException:
                    continue
                else:
                    self.emoji_cache.add_emoji(emoji)
                    return emoji
            # If it exits without returning aka there was no space available
            else:
                emoji_to_delete = guild_emoji_lists[0][
                    0
                ]  # Get first emoji from the first emoji server
                await emoji_to_delete.delete()  # Delete the emoji to make space for the new one
                self.emoji_cache.remove_emoji(
                    emoji_to_delete
                )  # Delete that emoji from cache if it exists
                await self.upload_emoji(
                    colour, draw_view=draw_view, interaction=interaction
                )  # Run again


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

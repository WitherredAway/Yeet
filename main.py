from __future__ import annotations

import asyncio
import datetime
import logging
import os
import sys
import time
from functools import cached_property
from typing import Union

import aiohttp
import discord
from cogs.AFD.afd import AFDRoleMenu
from cogs.utils.utils import RoleMenu
import gists
from discord.ext import commands
import pandas as pd

from helpers.context import CustomContext
from cogs.Draw.utils.colour import Colour
from cogs.Draw.draw import DrawView
from cogs.Draw.utils.emoji_cache import EmojiCache
from helpers.constants import LOG_BORDER, NL
from helpers.keep_alive import keep_alive

logging.basicConfig(level=logging.INFO)
log = logging.getLogger(__name__)


def get_prefix(bot, message):
    prefixes = bot.PREFIXES
    if not message.guild:
        return bot.PREFIX
    return commands.when_mentioned_or(*prefixes)(bot, message)


class Bot(commands.Bot):
    TEST_BOT_ID = 561963276792102912
    MAIN_BOT_ID = 634409171114262538
    PREFIXES = os.getenv("PREFIXES").split(", ")
    PREFIX = PREFIXES[0]

    COGS = {
        "poketwo": "Poketwo.poketwo",
        "p2": "Poketwo.poketwo",
        "docs": "RDanny.docs",
        "help": "RDanny.help",
        "admin": "admin",
        "bot": "bot",
        "channel": "channel",
        "define": "define",
        "draw": "Draw.draw",
        "gist": "gist",
        "jishaku": "jishaku",
        "jsk": "jishaku",
        "math": "math",
        "image": "Image.image",
        # "afd": "AFD.afd",
        # "test": "test",
    }

    def __init__(self, **kwargs):
        super().__init__(**kwargs)

        self.uptime = datetime.datetime.utcnow()
        self.activity = discord.Game(f"{self.PREFIXES[0]}help")
        self.status = discord.Status.online

        self.emoji_cache: EmojiCache = EmojiCache(bot=self)

        self.lock = asyncio.Lock()

        self.pokemon_csv = (
            "https://raw.githubusercontent.com/poketwo/data/master/csv/pokemon.csv"
            # os.getenv("POKEMON_CSV")
        )

    @cached_property
    def original_pk(self):
        original_pk = pd.read_csv(self.pokemon_csv)
        return original_pk

    @cached_property
    def pk(self):
        pk = self.original_pk[self.original_pk["catchable"] > 0]
        return pk

    @cached_property
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

    async def get_context(self, message, *, cls=None):
        return await super().get_context(message, cls=cls or CustomContext)

    async def setup_hook(self):
        self.EMOJI_SERVER_IDS = [
            # 1095209373627846706,
            # 1095209373627846706,
            # 1095209396675559557,
            # 1095209424454418522,
            # 1095209448810749974,
            # 1095211521136656457,
            # 1095211546025656340,
            # 1095211570264559696,
            # 1095211594289528884,
            # 1095212928959004694,
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

        self.add_view(AFDRoleMenu())

        ext_start = time.time()
        log.info("Started loading extensions" + NL + LOG_BORDER)
        for filename in set(self.COGS.values()):
            start = time.time()
            await self.load_extension(f"cogs.{filename}")
            log.info(
                f"Loaded \033[34;1mcogs.{filename}\033[0m in \033[33;1m{round(time.time()-start, 2)}s\033[0m"
            )
        log.info(
            f"Loaded all extensions in \033[33;1m{round(time.time()-ext_start, 2)}s\033[0m"
            + NL
            + LOG_BORDER
        )

        total_s: int = (datetime.datetime.utcnow() - self.uptime).seconds
        m, s = divmod(total_s, 60)
        msg = f"\033[32;1m{self.user}\033[0;32m connected in \033[33;1m{m}m{s}s\033[0;32m.\033[0m"
        await self.status_channel.send(f"```ansi\n{msg}\n```")
        log.info(msg)

    class Embed(discord.Embed):
        COLOUR = 0x9BFFD6

        def __init__(self, **kwargs):
            if kwargs.get("color", None) is None:
                kwargs["color"] = self.COLOUR
            super().__init__(**kwargs)

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
                return await self.upload_emoji(
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

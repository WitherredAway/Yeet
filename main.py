from __future__ import annotations

from helpers.timer import Timer

main_timer = Timer("main").start()

import os

import sys
import traceback
import asyncio
import datetime
import logging
from functools import cached_property
from typing import Any, Optional, Tuple, Union

import aiohttp
import discord
import gists
from discord.ext import commands

from helpers.context import CustomContext
from cogs.Draw.utils.colour import Colour
from cogs.Draw.draw import DrawView
from cogs.Draw.utils.emoji_cache import EmojiCache
from helpers.constants import (
    PY_BLOCK_FMT,
    EMBED_DESC_CHAR_LIMIT,
    EMBED_FIELD_CHAR_LIMIT,
    LOG_BORDER,
    NL,
)
from helpers.keep_alive import keep_alive
from cogs.Poketwo.poketwo import DataManager
from helpers.utils import UrlView, unwind


logging.basicConfig(level=logging.INFO)
log = logging.getLogger(__name__)


def get_prefix(bot, message):
    prefixes = bot.PREFIXES
    return commands.when_mentioned_or(*prefixes)(bot, message)


class Bot(commands.Bot):
    TEST_BOT_ID = 561963276792102912
    MAIN_BOT_ID = 634409171114262538
    BUG_CHANNEL_ID = 1116056244503978114
    PREFIXES = os.getenv("PREFIXES").split(", ")
    PREFIX = PREFIXES[0]

    COGS = unwind(
        {
            ("poketwo", "p2", "p2data"): "Poketwo.poketwo",
            "docs": "RDanny.docs",
            "help": "RDanny.help",
            "admin": "admin",
            "bot": "bot",
            "channel": "channel",
            ("define", "df"): "define",
            "draw": "Draw.draw",
            "gist": "gist",
            ("jishaku", "jsk"): "Jishaku.jishaku",
            "math": "math",
            "image": "Image.image",
            "afd": "AFD.afd",
            "test": "test",
        }
    )

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.start_time: float

        self.uptime = datetime.datetime.utcnow()
        self.activity = discord.Game(f"{self.PREFIXES[0]}help")
        self.status = discord.Status.online

        self.emoji_cache: EmojiCache = EmojiCache(bot=self)

        self.lock = asyncio.Lock()

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

    async def fetch_user_cache(self, user_id: int, /) -> Tuple[discord.User, bool]:
        "Gets user from cache if exists. Otherwise fetches user and caches it. Returns user and if it was returned from cache."
        user_id = int(user_id)
        if (user := self.get_user(user_id)) is not None:
            return user, True
        else:
            user = await self.fetch_user(user_id)
            self._connection._users[user.id] = user

        return user, False

    @property
    def p2data(self) -> DataManager:
        return self.get_cog("Poketwo").data

    @property
    def original_pk(self):
        return self.p2data.df

    @property
    def pk(self):
        return self.p2data.df_catchable

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
        self.bug_channel = await self.fetch_channel(self.BUG_CHANNEL_ID)

        self.session = aiohttp.ClientSession(loop=self.loop)

        self.gists_client = gists.Client()
        await self.gists_client.authorize(os.getenv("githubTOKEN"))
        self.wgists_client = gists.Client()
        await self.wgists_client.authorize(os.getenv("WgithubTOKEN"))

        with Timer(
            "loading extensions",
            logger=log,
            start_message="Started loading extensions" + NL + LOG_BORDER,
            end_message="Loaded all extensions in \033[33;1m{end_time}\033[0m"
            + NL
            + LOG_BORDER,
        ):
            for filename in set(self.COGS.values()):
                path = f"cogs.{filename}"
                with Timer(
                    f"loading {path}",
                    logger=log,
                    end_message=f"Loaded \033[34;1mcogs.{filename}\033[0m in {{end_time}}",
                ):
                    await self.load_extension(path)

        for name, cog in self.cogs.items():
            try:
                await cog.setup()
            except AttributeError:
                continue

        time_taken = main_timer.end()
        msg = f"\033[32;1m{self.user}\033[0;32m connected in \033[33;1m{time_taken}\033[0;32m.\033[0m"
        await self.status_channel.send(f"```ansi\n{msg}\n```")
        log.info(msg)

    async def report_error(self, error: Exception, ctx: Optional[CustomContext] = None):
        tb = "".join(
            traceback.format_exception(type(error), error, error.__traceback__)
        )
        embed = self.Embed(
            title="⚠️ An unexpected error occured",
            description=PY_BLOCK_FMT % tb[(len(tb) - EMBED_DESC_CHAR_LIMIT) + 20 :],
        )

        if ctx:
            embed.set_author(
                name=str(ctx.author), icon_url=ctx.author.display_avatar.url
            )
            embed.add_field(
                name="Command", value=ctx.message.content[:EMBED_FIELD_CHAR_LIMIT]
            )

            view = UrlView(
                {
                    f"{ctx.guild} | #{ctx.channel}"
                    if ctx.guild
                    else "Direct Messages": ctx.message.jump_url
                }
            )
        await self.bug_channel.send(embed=embed, view=view if ctx else None)
        print(tb, file=sys.stderr)

    class Embed(discord.Embed):
        COLOUR = 0x9BFFD6

        def __init__(self, **kwargs):
            if kwargs.get("color", None) is None:
                kwargs["color"] = self.COLOUR
            super().__init__(**kwargs)

        def add_field(self, *, name: Any, value: Any, inline: bool = False):
            """Adds a field to the embed object.

            This function returns the class instance to allow for fluent-style
            chaining. Can only be up to 25 fields.

            Parameters
            -----------
            name: :class:`str`
                The name of the field. Can only be up to 256 characters.
            value: :class:`str`
                The value of the field. Can only be up to 1024 characters.
            inline: :class:`bool`
                Whether the field should be displayed inline.
            """

            field = {
                "inline": inline,
                "name": str(name),
                "value": str(value),
            }

            try:
                self._fields.append(field)
            except AttributeError:
                self._fields = [field]

            return self

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
        strip_after_prefix=True,
    )
    bot.start_time = main_timer.start_time
    if os.getenv("REPL_ID") is not None:
        keep_alive()
        try:
            bot.run(TOKEN)
        except discord.HTTPException as error:
            if error.response.status == 429:
                print("\033[0;31mRate-limit detected, restarting process.\033[0m")
                os.system(f"kill 1 && source run")
    else:
        bot.run(TOKEN)

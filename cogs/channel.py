from __future__ import annotations

import asyncio
import re
import typing
from typing import Literal, Optional, Tuple, Union

import discord
from discord.ext import commands, menus

from .RDanny.utils.paginator import BotPages

if typing.TYPE_CHECKING:
    from main import Bot


CONFIRM_MESSAGE = "confirm"


class ChannelPageSource(menus.ListPageSource):
    def __init__(self, ctx, entries: Tuple, top_msg: str, *, per_page: int):
        super().__init__(entries, per_page=per_page)
        self.ctx = ctx
        self.bot = self.ctx.bot
        self.entries = entries
        self.top_msg = top_msg
        self.per_page = per_page
        self.embed = self.bot.Embed()

    async def format_page(self, menu, entries):
        self.embed.clear_fields()
        self.embed.title = self.top_msg
        self.embed.description = (
            "\n".join(
                [
                    f"{idx + 1 + (self.per_page * menu.current_page)}. {channel.mention} - **{channel.name}**"
                    for idx, channel in enumerate(entries)
                ]
            )
            if len(entries) > 0
            else "None"
        )

        maximum = self.get_max_pages()
        if maximum > 1:
            text = (
                f"Page {menu.current_page + 1}/{maximum} ({len(self.entries)} channels)"
            )
            self.embed.set_footer(text=text)

        return self.embed


class Channel(commands.Cog):
    """Utility commands for managing channels"""

    def __init__(self, bot: Bot):
        self.bot = bot

    display_emoji = "#️⃣"

    @commands.guild_only()
    @commands.group(
        name="channel",
        aliases=["ch"],
        brief="Useful channel management commands, use the help command for a list of subcommands",
        help="Channel management commands for doing useful things to channels.",
        case_insensitive=True,
        invoke_without_command=True
    )
    async def _channel(self, ctx: commands.Context):
        await ctx.send_help(ctx.command)

    @commands.guild_only()
    @_channel.group(
        name="list",
        aliases=["li"],
        brief="Lists channels that match specified criterion.",
        help="Lists channels that match criteria such as 'keyword', 'locked', 'unlocked'.",
        case_insensitive=True,
        invoke_without_command=True
    )
    async def _list(self, ctx: commands.Context):
        await ctx.send_help(ctx.command)

    @commands.guild_only()
    @_list.command(
        name="keyword",
        aliases=["k", "kw"],
        brief="Lists all channels with 'keyword' in the name",
        help="Lists all channels with 'keyword' in the name of the channel.",
        case_insensitive=True,
    )
    async def _keyword(self, ctx: commands.Context, *, keyword: str):
        keyword = keyword.lower().replace(" ", "-")
        top_msg = f"Channels with `{keyword}` in the name"
        channels = [
            channel for channel in ctx.guild.text_channels if keyword in channel.name
        ]
        source = ChannelPageSource(ctx, channels, top_msg, per_page=50)
        menu = BotPages(source, ctx=ctx)
        await menu.start()

    @commands.guild_only()
    @_list.command(
        name="contains",
        aliases=("contain", "last_message", "lm"),
        brief="Lists all channels with last message thet matches regex pattern",
        help=(
            "Lists all channels with last message that matches regex pattern."
            "Can also be a normal phrase, but make sure to escape metacharacters using '\\'. Case-sensitive!"
            "\n\nIt checks the content and the embeds' title and description fields of each message."
        ),
        case_insensitive=True,
    )
    async def _contains(self, ctx: commands.Context, *, regex: str):
        key = re.compile(regex)
        top_msg = f"Channels with last message matching pattern `{key.pattern}`"
        channels = []
        async with ctx.channel.typing():
            for channel in ctx.guild.text_channels:
                contents = []
                async for message in channel.history(limit=1):
                    contents.append(key.search(message.content) is not None)
                    if message.embeds:
                        contents.append(key.search(message.embeds[0].title or "") is not None)
                        contents.append(key.search(message.embeds[0].description or "") is not None)
                if any(contents):
                    channels.append(channel)

        source = ChannelPageSource(ctx, channels, top_msg, per_page=50)
        menu = BotPages(source, ctx=ctx)
        await menu.start()

    @commands.guild_only()
    @_list.command(
        name="state",
        brief="Lists all locked/unlocked channels",
        help="Lists all channels with 'send_messages' perms turned off/on for \@everyone.",
        case_insensitive=True,
    )
    async def _state(self, ctx: commands.Context, state_key: Literal['locked', 'unlocked'] = "locked"):
        channels = []
        states = {"locked": (False,), "unlocked": (True, None)}
        state = states.get(state_key.lower(), None)
        if state is None:
            return await ctx.send(
                "The 'state' argument must be 'locked' or 'unlocked'."
            )
        top_msg = f"Channels that are `{state_key.lower()}`"
        for channel in ctx.guild.text_channels:
            overwrite = channel.overwrites_for(ctx.guild.default_role)
            if overwrite.send_messages in state:
                channels.append(channel)

        source = ChannelPageSource(ctx, channels, top_msg, per_page=50)
        menu = BotPages(source, ctx=ctx)
        await menu.start()

    @commands.has_permissions(manage_channels=True)
    @commands.guild_only()
    @_channel.command(
        name="rename",
        aliases=["re"],
        brief="Renames channel.",
        help="Renames the current channel or mentioned channel if argument passed.",
    )
    async def _rename(
        self, ctx: commands.Context, channel: Optional[discord.TextChannel] = None, *, new_name: str
    ):
        if channel is None:
            channel = ctx.channel

        current_name = channel.name
        await channel.edit(name=new_name)
        await ctx.send(
            f"Changed {channel.mention}'s name from **{current_name}** to **{channel.name}**."
        )

    # togglelock
    @commands.has_permissions(manage_channels=True)
    @commands.guild_only()
    @_channel.command(
        name="togglelock",
        aliases=["tl"],
        brief="Locks/Unlocks a channel, and optionally appends text to channel name",
        case_insensitive=True,
        help=(
        "Toggles send_messages perms for everyone. And appends text to channel name if the argument is passed."
        "\nUseful for, for example, locking a channel when a Pokétwo pokémon spawns and instantly adding the name of the pokémon to the channel."
        "\n[RENAMES MAY TAKE LONGER THAN USUAL DUE TO RATE-LIMITS]"
        )
    )
    async def _togglelock(
        self, ctx: commands.Context, channel: Optional[discord.TextChannel] = None, *, append: Optional[str] = None
    ):
        if channel is None:
            channel = ctx.channel

        overwrite = channel.overwrites_for(ctx.guild.default_role)
        if overwrite.send_messages is not False:
            await channel.set_permissions(
                ctx.guild.default_role, send_messages=False
            )
            await ctx.send("Locked.")

        elif overwrite.send_messages is False:
            await channel.set_permissions(
                ctx.guild.default_role, send_messages=None
            )
            await ctx.send("Unlocked.")

        if append is not None:
            current_name = channel.name
            channel_name = f"{current_name} {append}"
            await channel.edit(name=channel_name)
            return await ctx.send(
                f"Changed channel name from **{current_name}** to **{channel.name}**."
            )
        
    async def set_all_send_message_perms(self, ctx: commands.Context, send_messages: bool):
        state = "lock" if send_messages is False else "unlock"
        await ctx.send(
            f"This will **{state}** *all* channels. Type `{CONFIRM_MESSAGE}` to confirm."
        )

        def check(m):
            return m.channel.id == ctx.channel.id and m.author.id == ctx.author.id

        try:
            msg = await self.bot.wait_for("message", timeout=30, check=check)
        except asyncio.TimeoutError:
            return await ctx.send("Time's up. Aborted.")
        if msg.content.lower() != CONFIRM_MESSAGE:
            return await ctx.send("Aborted.")

        msg = await ctx.send(f"{state.capitalize()}ing all channels...")
        async with ctx.channel.typing():
            for c in ctx.guild.text_channels:
                if c.overwrites_for(c.guild.default_role).send_messages is False:
                    await c.set_permissions(
                        ctx.guild.default_role, send_messages=None
                    )
        return await ctx.send(f"{state.capitalize()}ed all channels ✅.")

    @commands.has_permissions(manage_channels=True)
    @commands.guild_only()
    @_channel.group(
        name="lock",
        brief="Locks channel.",
        help="Lock current/specified channel.",
        invoke_without_command=True
    )
    async def _lock(self, ctx: commands.Context, channel: discord.TextChannel = None):
        if channel is None:
            channel = ctx.channel
        try:
            overwrite = channel.overwrites_for(channel.guild.default_role)
        except AttributeError:
            return await ctx.send(f'Channel "{channel}" not found.')

        if overwrite.send_messages is not False:
            await channel.set_permissions(
                channel.guild.default_role, send_messages=False
            )
            return await ctx.send(f"Locked {channel.mention}.")

        elif overwrite.send_messages is False:
            return await ctx.send(
                f"{'This' if channel == ctx.channel else 'That'} channel is already locked."
            )
        
    @commands.has_permissions(administrator=True)
    @commands.guild_only()
    @_lock.command(
        name="all",
        brief="Locks all channels."
    )
    async def lock_all(self, ctx: commands.Context):
        await self.set_all_send_message_perms(ctx, False)

    @commands.has_permissions(manage_channels=True)
    @commands.guild_only()
    @_channel.group(
        name="unlock",
        brief="Unlocks channel.",
        help="Unlock current/specified channel.",
        invoke_without_command=True
    )
    async def _unlock(self, ctx: commands.Context, channel: discord.TextChannel = None):
        if channel is None:
            channel = ctx.channel
        try:
            overwrite = channel.overwrites_for(channel.guild.default_role)
        except AttributeError:
            return await ctx.send(f'Channel "{channel}" not found.')

        if overwrite.send_messages is False:
            await channel.set_permissions(
                channel.guild.default_role, send_messages=None
            )
            return await ctx.send(f"Unlocked {channel.mention}.")

        elif overwrite.send_messages is not False:
            return await ctx.send(
                f"{'This' if channel == ctx.channel else 'That'} channel is already unlocked."
            )
        
    @commands.has_permissions(administrator=True)
    @commands.guild_only()
    @_unlock.command(name="all")
    async def unlock_all(self, ctx: commands.Context):
        await self.set_all_send_message_perms(ctx, None)

    @commands.has_permissions(manage_channels=True)
    @commands.guild_only()
    @_channel.group(
        name="strip",
        brief="Removes current or mentioned channel's name after `separator`.",
        help="""Strips the name of the channel and keeps the part before `separator`.

For example if the channel's name is `general-temporary`, `strip #general-temporary -` command will rename it to #general
[RENAMES MAY TAKE LONGER THAN USUAL DUE TO RATE-LIMITS]""",
        invoke_without_command=True,
        case_insensitive=True,
    )
    async def _strip(
        self, ctx: commands.Context, channel: Optional[discord.TextChannel] = None, *, separator: str
    ):
        if channel is None:
            channel = ctx.channel
        separator = separator.lower().replace(" ", "-")

        if separator not in channel.name:
            return await ctx.send("Nothing to strip.")

        # if separator in channel.name:
        #     await ctx.send(f"This will **rename** {channel.mention} to **{stripped}**. This action cannot be undone. Type `{confirm}` to confirm.")

        # def check(m):
        #     return m.channel.id == ctx.channel.id and m.author.id == ctx.author.id
        # try:
        #     msg = await self.bot.wait_for("message", timeout=30, check=check)
        # except asyncio.TimeoutError:
        #     return await ctx.send("Time's up. Aborted.")
        # if msg.content.lower() != "confirm":
        #     return await ctx.send("Aborted.")

        current_name = channel.name
        new_name = channel.name.split(separator)[0]
        await channel.edit(name=new_name)
        await ctx.send(
            f"Stripped the name of {channel.mention} from **{current_name}** to **{channel.name}**."
        )

    @commands.has_permissions(administrator=True)
    @commands.guild_only()
    @_strip.command(
        name="all",
        brief="Strips all channels.",
        help="""Strips the name of all channels and keeps the part before `separator`.

For example if a channel's name is `general-temporary`, `strip all -` command will rename it to #general
[RENAMES MAY TAKE LONGER THAN USUAL DUE TO RATE-LIMITS]""",
    )
    async def _all(self, ctx: commands.Context, separator: str):
        separator = separator.lower().replace(" ", "-")
        await ctx.send(
            f"This will **strip with `{separator}` and rename** *all* channels and keep the part in their names before {separator}.\
This action cannot be undone. Type `{CONFIRM_MESSAGE}` to confirm."
        )

        def check(m):
            return m.channel.id == ctx.channel.id and m.author.id == ctx.author.id

        try:
            msg = await self.bot.wait_for("message", timeout=30, check=check)
        except asyncio.TimeoutError:
            return await ctx.send("Time's up. Aborted.")
        if msg.content.lower() != CONFIRM_MESSAGE:
            return await ctx.send("Aborted.")

        await ctx.send(
            f"Stripping all channels' names with separator ` {separator} ` ..."
        )
        n = 0
        async with ctx.channel.typing():
            for channel in ctx.guild.text_channels:
                if separator in channel.name:
                    stripped = channel.name.split(separator)[0]
                    new_name = stripped
                    await channel.edit(name=new_name)
                    n += 1
        await ctx.send(f"Stripped {n} channels' names ✅.")


async def setup(bot):
    await bot.add_cog(Channel(bot))

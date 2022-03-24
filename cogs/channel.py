import discord
import asyncio
import textwrap
import re

from discord.ext import commands, menus
from .utils.paginator import BotPages
from typing import Optional, Union, Tuple


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
    """Channel related commands."""

    def __init__(self, bot):
        self.bot = bot

    display_emoji = "#️⃣"

    global confirm
    confirm = "ligma"
    # channel
    @commands.guild_only()
    @commands.group(
        name="channel",
        aliases=["ch"],
        brief="Useful channel management commands, use the help command for a list of subcommands",
        help="Channel management commands for doing useful things related to channels.",
        invoke_without_command=True,
        case_insensitive=True,
    )
    async def _channel(self, ctx):
        await ctx.send_help(ctx.command)

    # list
    @_channel.group(
        name="list",
        aliases=["li"],
        brief="Lists channels that match specified criterion.",
        help="Lists channels that match criteria such as 'keyword', 'locked', 'unlocked'.",
        invoke_without_command=True,
        case_insensitive=True,
    )
    async def _list(self, ctx):
        await ctx.send_help(ctx.command)

    # keyword
    @_list.command(
        name="keyword",
        aliases=["k", "kw"],
        brief="Lists all channels with 'keyword' in the name",
        help="Lists all channels with 'keyword' in the name of the channel.",
        case_insensitive=True,
    )
    async def _keyword(self, ctx, *, keyword):
        keyword = keyword.replace(" ", "-")
        top_msg = f"Channels with `{keyword}` in the name"
        channels = [
            channel for channel in ctx.guild.text_channels if keyword in channel.name
        ]
        source = ChannelPageSource(ctx, channels, top_msg, per_page=50)
        menu = BotPages(source, ctx=ctx)
        await menu.start()

    # startswith
    @_list.command(
        name="starts_with",
        aliases=["startswith", "sw"],
        brief="Lists all channels with message starting with <phrase>.",
        help="Lists all channels with last message starting with the word/phrase specified.",
        case_insensitive=True,
    )
    async def _starts_with(self, ctx, *, phrase):
        key = re.compile(phrase.lower())
        top_msg = f"Channels with last message starting with `{key.pattern}`"
        channels = []
        async with ctx.channel.typing():
            for channel in ctx.guild.text_channels:
                async for message in channel.history(limit=1):
                    message_content = message.content
                    if len(message.embeds) > 0:
                        if len(message.embeds[0].title) > 0:
                            message_content = message.embeds[0].title
                        elif len(message.embeds[0].author) > 0:
                            message_content = message.embeds[0].author
                        elif len(message.embeds[0].description) > 0:
                            message_content = message.embeds[0].description
                    if key.search(message_content.lower()):
                        channels.append(channel)

        source = ChannelPageSource(ctx, channels, top_msg, per_page=50)
        menu = BotPages(source, ctx=ctx)
        await menu.start()

    # state
    @_list.command(
        name="state",
        brief="Lists all locked/unlocked channels",
        help="Lists all channels with 'send_messages' perms turned off/on for everyone.",
        case_insensitive=True,
    )
    async def _state(self, ctx, state="locked"):
        channels = []
        states = {"locked": (False,), "unlocked": (True, None)}
        for _state in states.keys():
            if state.lower() in _state:
                state = states[_state]
                state_key = _state
                break
        else:
            return await ctx.send(
                "The 'state' argument must be in 'locked' or 'unlocked'."
            )
        top_msg = f"Channels that are `{state_key.lower()}`"
        for channel in ctx.guild.text_channels:
            overwrite = channel.overwrites_for(ctx.guild.default_role)
            if overwrite.send_messages in state:
                channels.append(channel)

        source = ChannelPageSource(ctx, channels, top_msg, per_page=50)
        menu = BotPages(source, ctx=ctx)
        await menu.start()

    # rename
    @commands.check_any(
        commands.is_owner(), commands.has_permissions(manage_channels=True)
    )
    @commands.guild_only()
    @_channel.command(
        name="rename",
        aliases=["re"],
        brief="Renames channel.",
        help="Renames the current channel or mentioned channel if argument passed.",
    )
    async def _rename(
        self, ctx, channel: Optional[discord.TextChannel] = None, *, new_name
    ):
        if channel is None:
            channel = ctx.channel

        current_name = channel.name
        await channel.edit(name=new_name)
        await ctx.send(
            f"Changed {channel.mention}'s name from **{current_name}** to **{channel.name}**."
        )

    # togglelock
    @commands.check_any(
        commands.is_owner(), commands.has_permissions(manage_channels=True)
    )
    @commands.guild_only()
    @_channel.command(
        name="togglelock",
        aliases=["tl"],
        brief="Locks/Unlocks a channel, and optionally renames channel",
        case_insensitive=True,
        help="Toggles send_messages perms for everyone. And renames channel if an argument is passed.)",
    )
    async def _togglelock(
        self, ctx, channel: Optional[discord.TextChannel] = None, *, new_name=None
    ):
        channel_name = new_name
        chnl = channel
        if chnl is None:
            channel = ctx.channel
        current_name = channel.name
        if chnl is None and channel_name != None:
            channel_name = f"{current_name} {channel_name}"
        overwrite = channel.overwrites_for(ctx.guild.default_role)

        try:
            if overwrite.send_messages != False:
                await channel.set_permissions(
                    ctx.guild.default_role, send_messages=False
                )
                await ctx.send("Locked.")

            if overwrite.send_messages == False:
                await channel.set_permissions(
                    ctx.guild.default_role, send_messages=True
                )
                await ctx.send("Unlocked.")

            if channel_name != None:
                await channel.edit(name=channel_name)
                await ctx.send(
                    f"Changed channel name from **{current_name}** to **{channel.name}**."
                )
                await asyncio.sleep(0.5)

        except Exception as e:
            raise e

    # lock
    @commands.guild_only()
    @commands.check_any(
        commands.is_owner(), commands.has_permissions(manage_channels=True)
    )
    @_channel.command(
        name="lock",
        brief="Locks channel(s).",
        help="Lock current/specified/all channel(s)",
    )
    async def _lock(self, ctx, channel: Union[discord.TextChannel, str] = None):
        if channel == "all":
            await ctx.send(
                f"This will **lock** *all* channels. Type `{confirm}` to confirm."
            )

            def check(m):
                return m.channel.id == ctx.channel.id and m.author.id == ctx.author.id

            try:
                msg = await self.bot.wait_for("message", timeout=30, check=check)
            except asyncio.TimeoutError:
                return await ctx.send("Time's up. Aborted.")
            if msg.content.lower() != confirm:
                return await ctx.send("Aborted.")

            msg = await ctx.send("Locking all channels...")
            for c in ctx.guild.text_channels:
                if c.overwrites_for(c.guild.default_role).send_messages != False:
                    await c.set_permissions(ctx.guild.default_role, send_messages=False)
            return await ctx.send("Locked all channels ✅.")

        if channel == None:
            channel = ctx.channel
        try:
            overwrite = channel.overwrites_for(channel.guild.default_role)
        except AttributeError:
            return await ctx.send(f'Channel "{channel}" not found.')

        if overwrite.send_messages != False:
            await channel.set_permissions(
                channel.guild.default_role, send_messages=False
            )
            return await ctx.send(f"Locked {channel.mention}.")

        if overwrite.send_messages == False:
            return await ctx.send(
                f"{'This' if channel == ctx.channel else 'That'} channel is already locked."
            )

    # unlock
    @commands.check_any(
        commands.is_owner(),
        commands.has_permissions(manage_channels=True),
        commands.guild_only(),
    )
    @_channel.command(
        name="unlock",
        brief="Unlocks channel(s).",
        help="Unlock current/specified/all channel(s)",
    )
    async def _unlock(self, ctx, channel: Union[discord.TextChannel, str] = None):
        if channel == "all":
            await ctx.send(
                f"This will **unlock** *all* channels. Type `{confirm}` to confirm."
            )

            def check(m):
                return m.channel.id == ctx.channel.id and m.author.id == ctx.author.id

            try:
                msg = await self.bot.wait_for("message", timeout=30, check=check)
            except asyncio.TimeoutError:
                return await ctx.send("Time's up. Aborted.")
            if msg.content.lower() != confirm:
                return await ctx.send("Aborted.")

            msg = await ctx.send("Unlocking all channels...")
            for c in ctx.guild.text_channels:
                if c.overwrites_for(c.guild.default_role).send_messages == False:
                    await c.set_permissions(ctx.guild.default_role, send_messages=None)
            return await ctx.send("Unlocked all channels ✅.")

        if channel == None:
            channel = ctx.channel
        try:
            overwrite = channel.overwrites_for(channel.guild.default_role)
        except AttributeError:
            return await ctx.send(f'Channel "{channel}" not found.')

        if overwrite.send_messages == False:
            await channel.set_permissions(
                channel.guild.default_role, send_messages=None
            )
            return await ctx.send(f"Unlocked {channel.mention}.")

        if overwrite.send_messages != False:
            return await ctx.send(
                f"{'This' if channel == ctx.channel else 'That'} channel is already unlocked."
            )

    # strip
    @commands.check_any(
        commands.is_owner(),
        commands.has_permissions(manage_channels=True),
        commands.guild_only(),
    )
    @_channel.group(
        name="strip",
        brief="Strips current or mentioned channel.",
        help="Strips current or channel mentioned, according to syntax.",
        invoke_without_command=True,
        case_insensitive=True,
    )
    async def _strip(
        self, ctx, channel: Optional[discord.TextChannel] = None, *, separator
    ):
        if channel is None:
            channel = ctx.channel
        stripped = channel.name.split(separator)[0]
        # if separator in channel.name:
        # await ctx.send(f"This will **rename** {channel.mention} to **{stripped}**. This action cannot be undone. Type `{confirm}` to confirm.")
        if separator not in channel.name:
            return await ctx.send("Nothing to strip.")

        """
      def check(m):
          return m.channel.id == ctx.channel.id and m.author.id == ctx.author.id
      try:
          msg = await self.bot.wait_for("message", timeout=30, check=check)
      except asyncio.TimeoutError:
          return await ctx.send("Time's up. Aborted.")
      if msg.content.lower() != "confirm":
          return await ctx.send("Aborted.")
      """
        current_name = channel.name
        if separator in channel.name:
            # await ctx.send(f"Stripping {channel.mention}'s name with separator ` {separator} ` ...")
            new_name = stripped
            await channel.edit(name=new_name)
            await ctx.send(
                f"✅ Done stripping the name of {channel.mention} from **{current_name}** to **{channel.name}**."
            )

    @_strip.command(
        name="all",
        brief="Strips all channels.",
        help="Strips all channels in a server.",
    )
    async def _all(self, ctx, separator):

        await ctx.send(
            f"This will **strip with `{separator}` and rename** *all* channels. This action cannot be undone. Type `{confirm}` to confirm."
        )

        def check(m):
            return m.channel.id == ctx.channel.id and m.author.id == ctx.author.id

        try:
            msg = await self.bot.wait_for("message", timeout=30, check=check)
        except asyncio.TimeoutError:
            return await ctx.send("Time's up. Aborted.")
        if msg.content.lower() != confirm:
            return await ctx.send("Aborted.")

        await ctx.send(
            f"Stripping all channels' names with separator ` {separator} ` ..."
        )
        for channel in ctx.guild.text_channels:
            stripped = channel.name.split(separator)[0]
            channel_name = channel.name
            if separator in channel_name:
                new_name = stripped
                await channel.edit(name=new_name)
        await ctx.send("Done stripping all channels' names ✅.")


async def setup(bot):
    await bot.add_cog(Channel(bot))

from __future__ import annotations

from datetime import datetime
import difflib
import itertools
import sys
import traceback
from typing import TYPE_CHECKING, Literal, Optional, Union
import zoneinfo
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

import discord
import humanize
from discord.ext import commands
from discord import app_commands
from discord.utils import utcnow, maybe_coroutine

from cogs.utils.utils import UrlView, unwind
from helpers.constants import EMBED_DESC_CHAR_LIMIT, EMBED_FIELD_CHAR_LIMIT
from helpers.context import CustomContext

if TYPE_CHECKING:
    from main import Bot


ERROR_COLOUR = 0xC94542
TIMESTAMP_REPLACE_KEY = "{t"
TIMESTAMP_STYLES = {
    "Short Time (HH:mm)": "t",
    "Long Time (HH:mm:ss)": "T",
    "Short Date (dd/MM/yyyy)": "d",
    "Long Date (dd Month yyyy)": "D",
    "Short Date Time (dd Month yyyy HH:mm)": "f",
    "Long Date Time (Day, dd Month yyyy HH:mm)": "F",
    "Relative Time": "R"
}


class TimestampNumericError(Exception):
    pass


class TimestampNumericConverter(commands.Converter):
    def __init__(self, _range: Optional[range] = None):
        self.range = _range

    async def convert(self, ctx: CustomContext, argument: Union[int, None]):
        argument = int(argument)
        if self.range:
            if argument not in self.range:
                raise TimestampNumericError(f"Value must be between {self.range[0]} and {self.range[-1]}, provided {argument} instead.")

        return argument


class TimestampTimezoneError(Exception):
    pass


class TimezoneConverter(commands.Converter):
    async def convert(self, ctx: CustomContext, argument: str):
        try:
            return ZoneInfo(argument)
        except ZoneInfoNotFoundError:
            raise TimestampTimezoneError(f"`{argument}`: Invalid timezone indentifier provided. See available timezone identifiers [here](https://en.wikipedia.org/wiki/List_of_tz_database_time_zones#List).")


class TimestampStyleError(Exception):
    pass


class StyleConverter(commands.Converter):
    async def convert(self, ctx: CustomContext, argument: str):
        argument = Timestamp.validate_spec(argument)
        if argument:
            return argument


class SnowflakeError(Exception):
    pass


class SnowflakeConverter(commands.Converter):
    async def convert(self, ctx: CustomContext, argument: str):
        try:
            return discord.Object(int(argument))
        except ValueError:
            raise SnowflakeError(f"`{argument}`: Invalid snowflake provided. Make sure it's a valid integer. E.g. 267550284979503104")


class Timestamp:
    def __init__(self, timestamp: int):
        self.timestamp = timestamp

    def __str__(self):
        return self.__format__()

    @staticmethod
    def validate_spec(spec: str) -> str:
        if spec not in TIMESTAMP_STYLES.values():
            valid = "\n".join([f"- {style}: {key}" for key, style in TIMESTAMP_STYLES.items()])
            raise TimestampStyleError(f"`{spec}`: Invalid timestamp style provided. Valid styles:\n{valid}")
        return spec

    def __format__(self, spec: str) -> str:
        if not spec:
            spec = "f"
        spec = self.validate_spec(spec)
        if spec:
            return f"<t:{self.timestamp}:{spec}>"

    @classmethod
    def from_dt(cls, datetime: datetime):
        return cls(int(datetime.timestamp()))


class TimestampArgs(
    commands.FlagConverter, case_insensitive=True
):
    year: Optional[TimestampNumericConverter] = commands.flag(
        aliases=("years", "yyyy", "y"),
        description="Year as a full 4-digit number. E.g. 2023.",
        default=lambda c: utcnow().year,
        max_args=1,
    )
    month: Optional[TimestampNumericConverter(range(1, 13))] = commands.flag(
        aliases=("months", "mm"),
        description="Month as a number 1-12.",
        default=lambda c: utcnow().month,
        max_args=1,
    )
    day: Optional[TimestampNumericConverter(range(1, 32))] = commands.flag(
        aliases=("days", "dd", "d"),
        description="Day of the month as a number 1-31.",
        default=lambda c: utcnow().day,
        max_args=1,
    )
    hour: Optional[TimestampNumericConverter(range(0, 24))] = commands.flag(
        aliases=("hours", "hh", "h"),
        description="Hour as a number 0-23 in 24h format.",
        default=lambda c: utcnow().hour,
        max_args=1,
    )
    minute: Optional[TimestampNumericConverter(range(0, 60))] = commands.flag(
        aliases=("minutes", "m"),
        description="Minute as a number 0-59.",
        default=lambda c: utcnow().minute,
        max_args=1,
    )
    second: Optional[TimestampNumericConverter(range(0, 60))] = commands.flag(
        aliases=("seconds", "ss", "s"),
        description="Second as a number 0-59.",
        default=lambda c: utcnow().second,
        max_args=1,
    )
    timezone: Optional[TimezoneConverter] = commands.flag(
        aliases=("tz", "z"),
        description="Timezone to base off of. Defaults to UTC.",
        default=ZoneInfo("UTC"),
        max_args=1,
    )
    style: Optional[StyleConverter] = commands.flag(
        name="style",
        aliases=("mode", "format"),
        description="The timestamp style. Defaults to Short Date Time.",
        default="f",
        max_args=1,
    )
    message: Optional[str] = commands.flag(
        aliases=("text", "msg"),
        description="Message to put the timestamp in. Replaces `{t:[style]}` if present, otherwise appends the timestamp.",
        max_args=1,
    )
    snowflake: Optional[SnowflakeConverter] = commands.flag(
        description="Get timestamp from a snowflake (e.g. message ID, channel ID, etc.).",
        max_args=1,
    )


class BotCog(commands.Cog):
    """Commands and events related to the bot's base functionality."""

    def __init__(self, bot: Bot):
        self.bot = bot
        self.all_timezones = [tz.casefold() for tz in zoneinfo.available_timezones()]

    display_emoji = "👾"

    @commands.Cog.listener()
    async def on_message_edit(self, before: discord.Message, after: discord.Message):
        # Prevent command trigger on pinning
        if after.pinned is not before.pinned:
            return
        # Prevent command trigger on media embedding
        if len([e for e in after.embeds if e.type != "rich"]) != len(
            [e for e in before.embeds if e.type != "rich"]
        ):
            return

        await self.bot.process_commands(after)

    @commands.Cog.listener()
    async def on_command_error(self, ctx: CustomContext, error: Exception):
        ignore = commands.CommandNotFound
        send_error = (TimestampNumericError, TimestampTimezoneError, TimestampStyleError, SnowflakeError)
        show_help = (commands.MissingRequiredArgument, commands.UserInputError)

        if isinstance(error, ignore):
            return

        elif isinstance(error, commands.NotOwner):
            return await ctx.send("You do not own this bot.")

        elif isinstance(error, commands.MaxConcurrencyReached):
            name = error.per.name
            suffix = "per %s" % name if error.per.name != "default" else "globally"
            plural = "%s times %s" if error.number > 1 else "%s time %s"
            fmt = plural % (error.number, suffix)
            await ctx.send(f"This command can only be used **{fmt}** at the same time.")

        elif isinstance(error, commands.MissingPermissions):
            missing = [
                "`" + perm.replace("_", " ").replace("guild", "server").title() + "`"
                for perm in error.missing_permissions
            ]
            fmt = "\n".join(missing)
            message = f"You need the following permissions to run this command:\n{fmt}."
            await ctx.send(message)

        elif isinstance(error, commands.BotMissingPermissions):
            missing = [
                "`" + perm.replace("_", " ").replace("guild", "server").title() + "`"
                for perm in error.missing_permissions
            ]
            fmt = "\n".join(missing)
            message = f"I need the following permissions to run this command:\n{fmt}."
            await ctx.send(message)

        elif isinstance(error, commands.CommandOnCooldown):
            await ctx.send(
                f"That command is on cooldown for **{round(error.retry_after, 2)}s**"
            )

        elif isinstance(error, commands.DisabledCommand):
            await ctx.send(
                ctx.command.extras.get("disabled-message")
                or f"The `{ctx.command}` command has been disabled by the developer for updates, debugging or due to some other issue."
            )

        elif isinstance(error, show_help):
            await ctx.send_help(ctx.command)

        elif isinstance(error, (commands.CheckAnyFailure, commands.CheckFailure)):
            await ctx.reply("You do not have permission to use this command.")

        else:
            if hasattr(error, "original"):
                err = error
                while hasattr(err, "original"):
                    err = err.original
                if isinstance(err, send_error):
                    return await ctx.send(err.args[0])

            tb = "".join(
                traceback.format_exception(type(error), error, error.__traceback__)
            )
            cb_fmt = "```py\n%s\n```"
            await ctx.send(
                embed=self.bot.Embed(
                    title="⚠️ Uh oh! An unexpected error occured :(",
                    description=cb_fmt % str(error),
                    color=ERROR_COLOUR,
                ).set_footer(
                    text="This error has been reported to the developer, sorry for the inconvenience!"
                )
            )

            embed = self.bot.Embed(
                title="⚠️ An unexpected error occured",
                description=cb_fmt % tb[(len(tb) - EMBED_DESC_CHAR_LIMIT) + 20 :],
            )
            embed.set_author(name=str(ctx.author), icon_url=ctx.author.display_avatar.url)
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
            await self.bot.bug_channel.send(embed=embed, view=view)

            print(f"Ignoring exception in command {ctx.command}:", file=sys.stderr)
            print(tb)

    @commands.Cog.listener(name="on_command")
    async def on_command(self, ctx: commands.Context):
        log_ch = self.bot.log_channel
        user = ctx.author

        em = self.bot.Embed()

        em.description = ctx.message.content
        em.set_author(name=user, icon_url=user.display_avatar.url)
        em.timestamp = utcnow()
        em.add_field(
            name="Go to",
            value=f"[Warp]({ctx.message.jump_url})",
        )
        em.set_footer(
            text=f"{ctx.guild.name} | #{ctx.channel.name}"
            if ctx.guild
            else "Direct Messages"
        )
        await log_ch.send(embed=em)

    @commands.command(
        name="prefix",
        aliases=("prefixes",),
        brief="Shows prefixes.",
        help="Shows the prefixes of the bot. Cannot be changed.",
    )
    async def _prefix(self, ctx: commands.Context):
        n = "\n> "
        await ctx.send(
            f"My prefixes are:\n> {n.join((self.bot.user.mention, *self.bot.PREFIXES))}\nThey cannot be changed."
        )

    @commands.command(
        name="ping",
        brief="Bot's latency.",
        help="Responds with 'Pong!' and the bot's latency",
    )
    async def ping(self, ctx: commands.Context):
        message = await ctx.send("Pong!")
        ms = int((message.created_at - ctx.message.created_at).total_seconds() * 1000)
        await message.edit(content=f"Pong! {ms} ms")

    @commands.command(
        name="uptime",
        brief="How long the bot has been up.",
        help="Shows how long it has been since the bot last went offline.",
    )
    async def uptime(self, ctx: commands.Context):
        embed = self.bot.Embed(
            title="Bot's uptime",
            description=f"The bot has been up for `{humanize.precisedelta(utcnow() - self.bot.uptime)}`.",
        )
        await ctx.send(embed=embed)

    @commands.command(
        name="invite", brief="Bot's invite link", help="Sends the bot's invite link."
    )
    async def invite(self, ctx: commands.Context):
        embed = self.bot.Embed(
            title="Add the bot to your server using the following link.",
            description=f"[Invite link.]({self.bot.invite_url})",
        )
        embed.set_thumbnail(url=self.bot.user.display_avatar.url)

        await ctx.send(embed=embed)

    @commands.hybrid_command(aliases=("ts",))
    async def timestamp(self, ctx: CustomContext, *, args: TimestampArgs):
        # TODO: This is temporary until this bug is fixed in discord.py (https://github.com/Rapptz/discord.py/issues/9641)
        for flag in args.get_flags().values():
            arg = getattr(args, flag.attribute)
            if callable(arg):
                setattr(args, flag.attribute, await maybe_coroutine(arg, ctx))

        if args.snowflake:
            dt = discord.utils.snowflake_time(args.snowflake.id).replace(tzinfo=args.timezone)
        else:
            try:
                dt = datetime(
                    year=args.year,
                    month=args.month,
                    day=args.day,
                    hour=args.hour,
                    minute=args.minute,
                    second=args.second,
                    tzinfo=args.timezone
                )
            except ValueError as e:
                return await ctx.send(e.args[0].capitalize())

        timestamp = Timestamp.from_dt(dt)

        if args.message:
            if TIMESTAMP_REPLACE_KEY in args.message:
                message = args.message.format(t=timestamp)
            else:
                message = f"{args.message} {timestamp:{args.style}}"
        else:
            message = f"{timestamp:{args.style}}"

        await ctx.send(message)

    @timestamp.autocomplete("timezone")
    async def timezone_autocomplete(self, interaction: discord.Interaction, current: str):
        current = current.casefold()
        timezones = sorted(
            [tz for tz in self.all_timezones if current in tz],
            key=lambda s: s.find(current)
        ) or self.all_timezones
        return (
            [
                app_commands.Choice(name=tz, value=tz)
                for tz in timezones
            ]
        )[:25]

    @timestamp.autocomplete("style")
    async def style_autocomplete(self, interaction: discord.Interaction, current: str):
        styles = {k: v for k, v in TIMESTAMP_STYLES.items() if current.lower() in k.lower()} or TIMESTAMP_STYLES
        return [
            app_commands.Choice(name=f"{style}: {text}", value=style)
            for text, style in styles.items()
        ][:25]



async def setup(bot: commands.Bot):
    await bot.add_cog(BotCog(bot))

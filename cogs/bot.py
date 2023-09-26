from __future__ import annotations

import datetime
import sys
import traceback
import typing

import discord
import humanize
from discord.ext import commands
from cogs.utils.utils import UrlView

from helpers.constants import EMBED_DESC_CHAR_LIMIT, EMBED_FIELD_CHAR_LIMIT
from helpers.context import CustomContext

if typing.TYPE_CHECKING:
    from main import Bot


ERROR_COLOUR = 0xC94542


class BotCog(commands.Cog):
    """Commands and events related to the bot's base functionality."""

    def __init__(self, bot: Bot):
        self.bot = bot

    display_emoji = "👾"

    @commands.Cog.listener()
    async def on_message_edit(self, before: discord.Message, after: discord.Message):
        if after.pinned is not before.pinned:
            return
        await self.bot.process_commands(after)

    @commands.Cog.listener()
    async def on_command_error(self, ctx: CustomContext, error: Exception):
        ignore = commands.CommandNotFound
        show_help = (commands.MissingRequiredArgument, commands.UserInputError)

        if isinstance(error, ignore):
            return

        elif isinstance(error, commands.NotOwner):
            await ctx.send("You do not own this bot.")

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
            embed.set_author(name=str(ctx.author), icon_url=ctx.author.avatar.url)
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

    # logs
    @commands.Cog.listener(name="on_command")
    async def on_command(self, ctx: commands.Context):
        log_ch = self.bot.log_channel
        user = ctx.author

        em = self.bot.Embed()

        em.description = ctx.message.content
        em.set_author(name=user, icon_url=user.avatar.url)
        em.timestamp = datetime.datetime.utcnow()
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

    # prefix
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

    # ping
    @commands.command(
        name="ping",
        brief="Bot's latency.",
        help="Responds with 'Pong!' and the bot's latency",
    )
    async def ping(self, ctx: commands.Context):
        message = await ctx.send("Pong!")
        ms = int((message.created_at - ctx.message.created_at).total_seconds() * 1000)
        await message.edit(content=f"Pong! {ms} ms")

    # uptime
    @commands.command(
        name="uptime",
        brief="How long the bot has been up.",
        help="Shows how long it has been since the bot last went offline.",
    )
    async def uptime(self, ctx: commands.Context):
        embed = self.bot.Embed(
            title="Bot's uptime",
            description=f"The bot has been up for `{humanize.precisedelta(datetime.datetime.utcnow() - self.bot.uptime)}`.",
        )
        await ctx.send(embed=embed)

    # invite
    @commands.command(
        name="invite", brief="Bot's invite link", help="Sends the bot's invite link."
    )
    async def invite(self, ctx: commands.Context):
        embed = self.bot.Embed(
            title="Add the bot to your server using the following link.",
            description=f"[Invite link.]({self.bot.invite_url})",
        )
        embed.set_thumbnail(url=self.bot.user.avatar.url)

        await ctx.send(embed=embed)


async def setup(bot: commands.Bot):
    await bot.add_cog(BotCog(bot))

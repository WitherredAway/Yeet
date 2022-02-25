import discord
from discord.ext import commands
from main import *
import asyncio
import datetime
import slash_util as slash


class Bot(commands.Cog):
    """Commands and events related to the bot."""

    def __init__(self, bot):
        self.bot = bot

    display_emoji = "👾"

    @commands.Cog.listener()
    async def on_ready(self):
        print(f"Running.\n{self.bot.user}")

    @commands.Cog.listener()
    async def on_message_edit(self, before, after):
        await self.bot.process_commands(after)

    @commands.Cog.listener()
    async def on_command_error(self, ctx, error):
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
                for perm in error.missing_perms
            ]
            fmt = "\n".join(missing)
            message = f"You need the following permissions to run this command:\n{fmt}."
            await ctx.send(message)

        elif isinstance(error, commands.BotMissingPermissions):
            missing = [
                "`" + perm.replace("_", " ").replace("guild", "server").title() + "`"
                for perm in error.missing_perms
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
                f"Command `{ctx.command}` has been disabled by the developer for updates, debugging or due to some other issue."
            )

        elif isinstance(error, show_help):
            await ctx.send_help(ctx.command)

        else:
            await ctx.send(str(error))
            raise error

    # logs
    @commands.Cog.listener(name="on_command")
    async def on_command(self, ctx):
        try:

            log_ch = await self.bot.fetch_channel(self.bot.LOG_CHANNEL)
            user = ctx.author
            command = ctx.command
            message_content = str(ctx.message.content)
            message_id = ctx.message.id
            channel = str(ctx.channel)
            channel_id = ctx.channel.id

            em = self.bot.Embed()

            em.set_author(name=user, icon_url=user.avatar.url)
            em.add_field(name="Command used", value=message_content, inline=False)
            em.timestamp = datetime.datetime.utcnow()
            if ctx.guild:
                server = ctx.guild.name
                server_id = ctx.guild.id
                em.add_field(
                    name="Go to",
                    value=f"[Warp](https://discord.com/channels/{server_id}/{channel_id}/{message_id})",
                )
                em.set_footer(text=f"{server} | #{channel}")
            else:
                em.set_footer(text="Direct messages")
            await log_ch.send(embed=em)

        except Exception as e:
            raise e

    # prefix
    @commands.command(
        name="prefix",
        aliases=["prefixes"],
        brief="Shows prefixes.",
        help="Shows the prefixes of the bot. Cannot be changed.",
    )
    async def _prefix(self, ctx):
        n = "\n> "
        await ctx.send(
            f"My prefixes are:\n> {n.join(get_prefix(bot, ctx)[1:])}\nThey cannot be changed."
        )

    # ping
    @commands.command(
        name="ping",
        brief="Bot's latency",
        help="Responds with 'Pong!' and the bot's latency",
    )
    async def ping(self, ctx):
        message = await ctx.send("Pong!")
        ms = int((message.created_at - ctx.message.created_at).total_seconds() * 1000)
        await message.edit(content=f"Pong! {ms} ms")

    # invite
    @commands.command(
        name="invite", brief="Bot's invite link", help="Sends the bot's invite link."
    )
    async def invite(self, ctx):
        embed = self.bot.Embed(
            title="Add the bot to your server using the following link."
        )
        embed.set_thumbnail(url=self.bot.user.avatar.url)
        embed.add_field(
            name="Invite Bot",
            value=f"[Invite link.](https://discord.com/api/oauth2/authorize?client_id={self.bot.user.id}&permissions=8&scope=bot%20applications.commands)",
            inline=False,
        )

        await ctx.send(embed=embed)


def setup(bot):
    bot.add_cog(Bot(bot))

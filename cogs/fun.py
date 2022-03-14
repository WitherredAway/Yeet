import discord
import asyncio
import os

from discord.ext import commands
from datetime import datetime
from constants import COMMAND_COOLDOWN


class Fun(commands.Cog):
    """Commands for fun."""

    def __init__(self, bot):
        self.bot = bot

    display_emoji = "🧩"

    @commands.Cog.listener()
    async def on_message(self, message):
        if message.content.lower() == "ligma":
            await message.channel.send("balls")

    # say
    @commands.command(
        name="say",
        aliases=["s"],
        brief="Repeats <message>",
        help="Repeats <message> passed in after the command.",
    )
    @commands.cooldown(1, COMMAND_COOLDOWN, commands.BucketType.user)
    async def say(self, ctx, *, message):
        if ctx.message.attachments:
            await ctx.send(
                content=message,
                files=[await f.to_file() for f in ctx.message.attachments],
            )
        else:
            await ctx.send(message)

    # cum
    @commands.cooldown(1, COMMAND_COOLDOWN, commands.BucketType.user)
    @commands.command(hidden=True)
    async def cum(self, ctx):
        await ctx.send("uGn!~~")

    # delaysay
    @commands.command(
        name="delaysay",
        aliases=["dsay"],
        brief="Repeats <message> after <delay>",
        help="Repeats a <message> after <delay> seconds.",
    )
    @commands.max_concurrency(1, per=commands.BucketType.user, wait=False)
    async def delaysay(self, ctx, delay: int, *, msg):
        await ctx.send(f"Delay message set, in **{delay}** seconds")
        await asyncio.sleep(int(delay))
        await ctx.send(msg)

    @delaysay.error
    async def delaysay_error(self, error):
        if isinstance(error, commands.BadArgument):
            await ctx.send("The delay must be an integer.")


async def setup(bot):
    await bot.add_cog(Fun(bot))

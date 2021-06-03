import discord
from discord.ext import commands
from main import *
import asyncio
from PIL import Image, ImageDraw, ImageFont, ImageFilter
from datetime import datetime
import os

class Fun(commands.Cog):
  """Fun commands."""
  def __init__(self, bot):
    self.bot = bot
  
	# say
  @commands.command(name = "say",
                    aliases = ['s'],
                    brief = "Repeats <message>",
                    help = "Repeats <message> passed in after the command."
                    )
  @commands.cooldown(1, cmd_cd, commands.BucketType.user)
  async def say(self, ctx, *, message):
    await ctx.send(message)

	# cum
  @commands.cooldown(1, cmd_cd, commands.BucketType.user)
  @commands.command(hidden = True)
  async def cum(self, ctx):
    await ctx.send("uGn!~~")
  
  # delaysay
  @commands.command(name = "delaysay",
                    aliases = ['dsay'],
                    brief = "Repeats <message> after <delay>",
                    help = "Repeats a <message> after <delay> seconds."
                    )
  @commands.max_concurrency(1, per=commands.BucketType.user, wait = False)
  async def delaysay(self, ctx, delay: int, *, msg):
    await ctx.send(f"Delay message set, in **{delay}** seconds")
    await asyncio.sleep(int(delay))
    await ctx.send(msg)
  @delaysay.error
  async def delaysay_error(self, error):
    if isinstance(error, commands.BadArgument):
      await ctx.send("The delay must be an integer.")
  
  #snap
  
def setup(bot):
	bot.add_cog(Fun(bot))

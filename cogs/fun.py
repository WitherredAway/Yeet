import discord
from discord.ext import commands
from main import *
import asyncio

class Fun(commands.Cog):
  """Fun commands."""
  def __init__(self, bot):
    self.bot = bot

  # spam
  @commands.command(name = "spam",
                    aliases = ['sp'],
                    brief = "Spams desired message",
                    help = "Spams <message> every <delay> seconds. For multi-word messages put them within quotes."
                    )
  #@commands.has_permissions(manage_messages = True)
  async def spam(self, ctx, msg, delay: int):
    global on
    on = True
    while on:
      await ctx.send(msg)
      await asyncio.sleep(int(delay))
  @spam.error
  async def spam_error(self, ctx, error):
  	if isinstance(error, commands.MissingRequiredArgument):
  		await ctx.send(f"Missing argument(s). Proper usage: `{prefix}spam <message to spam> <delay in seconds>`")
  	# if isinstance(error, commands.MissingPermissions):
  	#   await ctx.send("Missing permission(s): Manage_Messages")
  	if isinstance(error, commands.BadArgument):
  	  await ctx.send("The delay must be a whole number")
  
	# stopspam
  @commands.command(name = "stopspam", 
                    aliases = ['stopsp'],
                    brief = "Stops running spam",
                    help = "Stops a running `spam` command."
                    )
  async def stopspam(self, ctx):
    global on
    on = False
    await ctx.send("stopped")

	# say
  @commands.command(name = "say",
                    aliases = ['s'],
                    brief = "Repeats <message>",
                    help = "Repeats <message> passed in after the command."
                    )
  async def say(self, ctx, *, message):
    await ctx.send(message)
    asyncio.sleep(0.5)

	# cum
  @commands.command(hidden = True)
  async def cum(self, ctx):
    await ctx.send("uGn!~~")
    asyncio.sleep(0.5)
  
  # delaysay
  @commands.command(name = "delaysay",
                    aliases = ['dsay'],
                    brief = "Repeats <message> after <delay>",
                    help = "Repeats a <message> after <delay> seconds."
                    )
  #@commands.has_permissions(manage_messages = True)
  async def delaysay(self, ctx, message, delay: int):
    await ctx.send(f"Delay message set, in **{delay}** seconds")
    await asyncio.sleep(int(delay))
    await ctx.send(message)
  @delaysay.error
  async def dsay_error(self, ctx, error):
    if isinstance(error, commands.MissingRequiredArgument):
      await ctx.send(f"Missing Argument(s). Proper usage: `{prefix}delaysay <delay in seconds> <message to say>`")
    #if isinstance(error, commands.MissingPermissions):
    # await ctx.send("Missing Permission(s): Manage_messages")
    if isinstance(error, commands.BadArgument):
      await ctx.send("The delay must be an integer.")
  
def setup(bot):
	bot.add_cog(Fun(bot))

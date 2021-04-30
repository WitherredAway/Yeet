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
  @commands.has_permissions(manage_messages = True)
  @commands.max_concurrency(1, per=commands.BucketType.guild, wait = False)
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
  	if isinstance(error, commands.MissingPermissions):
  	  await ctx.send("Missing permission(s): Manage_Messages")
  	if isinstance(error, commands.BadArgument):
  	  await ctx.send("The delay must be a whole number")
  	if isinstance(error, commands.MaxConcurrencyReached):
  	  await ctx.send(f"`spam` command already active on this server. This command can only be used once at a time in a server. Stop the current `spam` with {prefix}stopspam.")
  
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
    await asyncio.sleep(0.5)

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
      
  # timer
  global max_time
  max_time = 600
  global time
  time = ""
  @commands.command(name = "timer",
                    aliases = ["tr", "countdown", "cd"],
                    brief = "Sets a timer",
                    help = f"Sets a timer for <seconds> and counts down from it(max {round(max_time/60, 2)}mins or {max_time}seconds). One timer per user at a time. Stop a running timer by using the {prefix}stoptimer command.")
  @commands.max_concurrency(1, per=commands.BucketType.user, wait = False)
  async def timer(self, ctx, seconds: int):
    global secondint
    global msg
    global max_time
    global time
    time = seconds
    mins = round(seconds/60, 2)
    secondint = seconds
    msg = f"{ctx.author.mention} time's up! ({mins}mins or {seconds}seconds)"
    if secondint > max_time:
      await ctx.send(f"Timer can be set for max **{max_time/60}** minutes or **{max_time}** seconds")
    elif secondint <= 0:
      await ctx.send("Please input a positive whole number.")
    else:
      message = await ctx.send(f"Timer: {seconds} seconds")
      while True:
        secondint -= 1
        if secondint == 0:
          await message.edit(content=msg)
          break
        await message.edit(content=f"Timer: {secondint} seconds.")
        await asyncio.sleep(1)
  @timer.error
  async def timer_error(self, ctx, error):
    if isinstance(error, commands.BadArgument):
      await ctx.send("The time must be a positive whole number.")
    if isinstance(error, commands.MaxConcurrencyReached):
  	  await ctx.send(f"A timer command is already active. This command can only be used once at a time per user. Stop the current timer with `{prefix}stoptimer`")
  	  
  # stoptimer
  @commands.command(name = "stoptimer",
                    aliases = ["stoptr", "stopcountdown", "stopcd"],
                    brief = "Stops running timer",
                    help = "Stops a running `timer` command."
                    )
  async def stoptimer(self, ctx):
    try:
      global msg
      global secondint
      global time
      msg = f"{ctx.author.mention} timer stopped! Stopped at {round(secondint/60, 2)}mins/{secondint}seconds **out of** {time/60}mins/{time}seconds"
      secondint = 1
      await ctx.message.add_reaction('👍')
    except Exception as e:
	    await ctx.send(str(e))
  
def setup(bot):
	bot.add_cog(Fun(bot))

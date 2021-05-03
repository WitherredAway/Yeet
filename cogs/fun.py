import discord
from discord.ext import commands
from main import *
import asyncio

class Fun(commands.Cog):
  """Fun commands."""
  def __init__(self, bot):
    self.bot = bot

  # spam
  @commands.check_any(commands.is_owner(), commands.has_permissions(manage_messages = True))
  @commands.group(name = "spam",
                    aliases = ['sp'],
                    brief = "Spams desired message",
                    invoke_without_command=True,
                    case_insensitive=True,
                    help = "Spams desired message, with desired intervals."
                    )
 
  async def spam(self, ctx):
    await ctx.send_help(ctx.command)
  
  # spam start
  @spam.command(name="start",
                aliases=["s"],
                brief="Starts spam.",
                help="Spams <message> every <delay> seconds. For multi-word messages put them within quotes")
  @commands.max_concurrency(1, per=commands.BucketType.guild, wait = False)
  async def _spam_start(self, ctx, delay: int, *, msg):
    global on
    on = True
    while on:
      await ctx.send(msg)
      await asyncio.sleep(delay)
      
  @_spam_start.error
  async def spamstart_error(self, ctx, error):
  	if isinstance(error, commands.MissingPermissions):
  	  await ctx.send("Missing permission(s): Manage_Messages")
  	if isinstance(error, commands.BadArgument):
  	  await ctx.send("The delay must be a whole number")
  	#if isinstance(error, commands.MaxConcurrencyReached):
  	  #await ctx.send(f"`Spam` command already active on this server. This command can only be used once at a time in a server. Stop the current `spam` with {prefix}stopspam.")
  
  @commands.check_any(commands.is_owner(), commands.has_permissions(manage_messages = True))
  @spam.command(name = "stop", 
                    aliases = ['end'],
                    brief = "Stops running spam",
                    help = "Stops a running `spam` command."
                    )
  async def _spam_stop(self, ctx):
    global on
    if on == True:
      on = False
      await ctx.send("Stopped spam.")
    else:
      await ctx.send("There isn't a `spam` running.")
  @_spam_stop.error
  async def stop_error(ctx, error):
    if isinstance(error, commands.MissingPermissions):
  	  await ctx.send("Missing permission(s): Manage_Messages")

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
  @commands.max_concurrency(1, per=commands.BucketType.user, wait = False)
  async def delaysay(self, ctx, delay: int, *, msg):
    await ctx.send(f"Delay message set, in **{delay}** seconds")
    await asyncio.sleep(int(delay))
    await ctx.send(msg)
  @delaysay.error
  async def delaysay_error(self, error):
    if isinstance(error, commands.BadArgument):
      await ctx.send("The delay must be an integer.")
      
  # timer
  global max_time
  max_time = 600
  global time
  time = ""
  @commands.group(name = "timer",
                  aliases = ["tr", "countdown", "cd"],
                  brief = "Sets a timer",
                  help = "Sets a timer, which the bot will count down from and ping at the end.",
                  invoke_without_command=True,
                  case_insensitive=True)
  async def timer(self, ctx):
    await ctx.send_help(ctx.command)
  
  #timer start

  @timer.command(name="start",
                aliases=["s"],
                brief="Starts timer.",
                help=f"Sets a timer for <seconds> and counts down from it(max {round(max_time/60, 2)}mins or {max_time}seconds). One timer per user at a time. Stop a running timer by using the {prefix}timer stop command.")
  @commands.max_concurrency(1, per=commands.BucketType.user, wait = False)
  async def _timer_start(self, ctx, seconds: int):
    
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
  @_timer_start.error
  async def timer_error(self,ctx, error):
    if isinstance(error, commands.BadArgument):
      await ctx.send("The time must be a positive whole number.")
    
  	  
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

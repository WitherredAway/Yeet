import discord
from discord.ext import commands
import asyncio
from main import *
from typing import Counter
import wikipedia

class Useful(commands.Cog):
  """Useful commands"""
  def __init__(self, bot):
    self.bot = bot
  
  #lock
  @commands.check_any(commands.is_owner(), commands.has_permissions(manage_channels = True), commands.guild_only())
  @commands.command(name = "togglelock",
                  aliases = ['lock', 'tl'],
                  brief = "Locks/Unlocks a channel, and optionally renames channel",
                  case_insensitive=True,
                  help = "Toggles send_messages perms for everyone. And renames channel if an argument is passed.)")
  async def _togglelock(self, ctx, *, ch_name=None):
      overwrite = ctx.channel.overwrites_for(ctx.guild.default_role)
      try:
        if ch_name != None and ch_name != "unlockall" and ch_name != "lockall":
          channel = ctx.channel
          await channel.edit(name=ch_name)
          await ctx.send(f"Changed channel name to {ch_name}")
          
        if ch_name == "unlockall":
            await ctx.send("This will *unlock* **all** channels. Type 'confirm' to confirm.")
            def check(m):
                return m.channel.id == ctx.channel.id and m.author.id == ctx.author.id
            try:
                msg = await self.bot.wait_for("message", timeout=30, check=check)
            except asyncio.TimeoutError:
                return await ctx.send("Time's up. Aborted.")
            if msg.content.lower() != "y":
                return await ctx.send("Aborted.")

                
            msg = await ctx.send("Unlocking all channels...")
            for c in ctx.guild.channels:
                await c.set_permissions(ctx.guild.default_role, send_messages = True)
            await ctx.send("Unlocked all channels ✅.")
            
        if ch_name == "lockall":
            await ctx.send("This will *lock* **all** channels. Type 'confirm' to confirm.")
            def check(m):
                return m.channel.id == ctx.channel.id and m.author.id == ctx.author.id
            try:
                msg = await self.bot.wait_for("message", timeout=30, check=check)
            except asyncio.TimeoutError:
                return await ctx.send("Time's up. Aborted.")
            if msg.content.lower() != "confirm":
                return await ctx.send("Aborted.")

            msg = await ctx.send("Locking all channels...")
            for c in ctx.guild.channels:
                await c.set_permissions(ctx.guild.default_role, send_messages = False)
            await msg.edit(content="Locked all channels ✅.")

        if overwrite.send_messages != False:
          await ctx.channel.set_permissions(ctx.guild.default_role, send_messages = False)
          await ctx.send("Locked.")
        if overwrite.send_messages == False:
          await ctx.channel.set_permissions(ctx.guild.default_role, send_messages = True)
          await ctx.send("Unlocked.")
      except Exception as e:
          raise e
  
  @commands.command()
  @commands.has_permissions(manage_messages=True)
  async def cleanup(self, ctx, search=100):
        """Cleans up the bot's messages from the channel."""

        def check(m):
            return m.author == ctx.me or m.content.startswith(ctx.prefix)

        deleted = await ctx.channel.purge(limit=search, check=check, before=ctx.message)
        spammers = Counter(m.author.display_name for m in deleted)
        count = len(deleted)

        messages = [f'{count} message{" was" if count == 1 else "s were"} removed.']
        if len(deleted) > 0:
            messages.append("")
            spammers = sorted(spammers.items(), key=lambda t: t[1], reverse=True)
            messages.extend(f"– **{author}**: {count}" for author, count in spammers)

        await ctx.send("\n".join(messages), delete_after=5)

  
  #wiki
  @commands.command(name="wiki",
                    aliases=["wikipedia"],
                    brief="Searches wikipedia for info.",
                    help="Use this command to look up anything on wikipedia. Sends the first 10 sentences from wikipedia.")
  async def wiki(self, ctx, *, arg=None):
    try:
        if arg == None:
            await ctx.send("Please, specify what do you want me to search.")
        elif arg:
            start = arg.replace(" ", "")
            end = wikipedia.summary(start)
            await ctx.send(f"```\n{end}\n```")
    except:
        try:
            start = arg.replace(" ", "")
            end = wikipedia.summary(start, sentences=10)
            await ctx.send(end)
        except:
            await ctx.send("Not found.")

  
  # spam
  @commands.check_any(commands.is_owner(), commands.has_permissions(manage_messages = True), commands.guild_only())
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
  @commands.check_any(commands.is_owner(), commands.has_permissions(manage_messages = True))
  @spam.command(name="start",
                aliases=["s"],
                brief="Starts spam.",
                help="Spams <message> every <delay> seconds. For multi-word messages put them within quotes")
  @commands.max_concurrency(1, per=commands.BucketType.guild, wait = False)
  async def _spam_start(self, ctx, delay: float, *, msg):
    global on
    global sp_start_channel
    sp_start_channel = ctx.channel
    on = True
    while on:
      await ctx.send(msg)
      await asyncio.sleep(delay)
  # spam start error    
  @_spam_start.error
  async def spamstart_error(self, ctx, error):
  	if isinstance(error, commands.BadArgument):
  	  await ctx.send("The delay must be a number.")
  
  # spam stop
  @commands.check_any(commands.is_owner(), commands.has_permissions(manage_messages = True))
  @spam.command(name = "stop", 
                    aliases = ['end'],
                    brief = "Stops running spam",
                    help = "Stops a running `spam` command."
                    )
  async def _spam_stop(self, ctx):
    global on
    global sp_start_channel
    sp_stop_channel = ctx.channel
    if on == True and sp_stop_channel == sp_start_channel:
      on = False
      await ctx.send("Stopped spam.")
    else:
      await ctx.send("There isn't a `spam` command running in this channel.")
      
      
  # timer
  max_time = 600
  time = ""
  mins = ""
  tr_start_user = ""
  msg = ""
  secondint = ""
  
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
    
    global time
    time = round(seconds, 2)
    global mins
    mins = round(seconds/60, 2)
    global tr_start_user
    tr_start_user = ctx.author
    global msg
    msg = f"{ctx.author.mention} time's up! ({mins}mins or {seconds}seconds)"
    global secondint
    secondint = seconds
    if seconds > max_time:
      await ctx.send(f"Timer can be set for max **{max_time/60}** minutes or **{max_time}** seconds")
    elif seconds <= 0:
      await ctx.send("Please input a positive whole number.")
    else:
      message = await ctx.send(f"Timer: {secondint} seconds")
      while True:
        secondint -= 1
        if secondint == 0:
          await message.edit(content=msg)
          break
        await message.edit(content=f"Timer: {secondint} seconds.")
        await asyncio.sleep(1)
  @_timer_start.error
  async def timerstart_error(self,ctx, error):
    if isinstance(error, commands.BadArgument):
      await ctx.send("The time must be a positive whole number.")
    
  # timer stop
  @timer.command(name = "stop",
                    aliases = ["end"],
                    brief = "Stops running timer",
                    help = "Stops a running `timer` command."
                    )
  async def _timer_stop(self, ctx):
    try:
      global msg
      global mins
      global time
      global tr_start_user
      global secondint
      if secondint > 0 and ctx.author == tr_start_user:
        msg = f"{ctx.author.mention} timer stopped! Stopped at {round(secondint/60, 2)}mins/{secondint}seconds **out of** {mins}mins/{time}seconds"
        secondint = 1
        await ctx.message.add_reaction('👍')
      else:
        await ctx.send(f"There isn't a `timer` running that belongs to you.")
    except Exception as e:
	     raise e
def setup(bot):
  bot.add_cog(Useful(bot))

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
  
  @commands.command()
  async def raw(self, ctx, msg, ping: bool=True):
      first_step = discord.utils.escape_markdown(ctx.author.display_name)
      catch_name = first_step.replace("<", "\\<")
      message = f"Congratulations {catch_name}! You caught a level 1 Ralts!"
      if ping:
        await ctx.send(message, allowed_mentions=discord.AllowedMentions(everyone=False, replied_user=True), reference=ctx.message)
      else:
        await ctx.send(message, allowed_mentions=discord.AllowedMentions.none(), reference=ctx.message)
  """
  @commands.command()
  async def catch(self, ctx, pk, level: int=69, iv: float=69.00, shiny: bool=False):
      msg = f"Congratulations {ctx.author.mention}! You caught a {pk}!"
      pic = "https://images-ext-2.discordapp.net/external/fWH3TkwsG6phn7rD65Pc6l4W-jXhuD47J5iDgqeHo0w/https/i.imgur.com/TQXZKz4.png"
      
      if shiny:
          msg += "\n\nThese colors seem unusual... :sparkles:"
          pic = "https://images-ext-1.discordapp.net/external/H4ocqHL_tNFdrjKnh06kBg2_17rTaXgNlnQfwfcNLkQ/%3Fv%3D26/https/assets.poketwo.net/shiny/280.png"
      
      embed = discord.Embed(description=msg, color=embed_colour)
      embed.set_author(name=str(ctx.author), icon_url=ctx.author.avatar_url)
      embed.set_thumbnail(url=pic)
      #embed.add_field(name="Level", value=f"{level}", inline=True)
      #embed.add_field(name="IV", value=f"{iv}%", inline=True)
      embed.set_footer(text=f"\nLevel: {level} | IV: {iv}%")
      await ctx.send(embed=embed)
  """
  #avatar
  @commands.command(name="avatar",
                    aliases=["av", "pfp", "profilepicture"],
                    brief="Avatar url",
                    help="Sends the avatar url of author/mentioned member.")
  async def avatar(self, ctx, member: discord.Member=None):
      member = member or ctx.author
      embed = discord.Embed(title=f"Avatar of {member}", color=embed_colour)
      embed.set_image(url = ctx.author.avatar_url)
      await ctx.send(embed=embed)
  
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
            msg = await ctx.send("Fetching...")
            start = arg.replace(" ", "")
            end = wikipedia.summary(start)
            await msg.edit(content = f"```py\n{end}\n```")
    except:
        try:
            start = arg.replace(" ", "")
            end = wikipedia.summary(start, sentences=10)
            await msg.edit(content = f"```py\n{end}\n```")
        except:
            await msg.edit(content = "Not found.")

  
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
  global max_time
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

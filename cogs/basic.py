import discord
from discord.ext import commands
from main import bot, prefix, embed_colour
import asyncio

class Basic(commands.Cog):
  
  def __init__(self, bot):
    self.bot = bot

  @commands.Cog.listener()
  async def on_ready(self):
    await bot.change_presence(status=discord.Status.online, activity=discord.Game(f'{prefix}help'))
    print("Running.")
    print(bot.user)
    
  @commands.Cog.listener()
  async def on_command_error(self, ctx, error):
    if isinstance(error, commands.CommandNotFound):
      await ctx.send("Command not found.")

  # @mention
  @commands.Cog.listener()
  async def on_message(self, message):
  	if message.content.startswith("<@634409171114262538>" or "@Yeet.1830"):
	    await message.channel.send(f"My prefix is `{prefix}`\nDo `{prefix}help` for a list of commands")
	  
	# ping
  @commands.command(help = "Responds with 'Pong!' and the bot's latency")
  async def ping(self, ctx):
    await ctx.send(f'Pong! {round(bot.latency * 1000)}ms')
  # invite
  @commands.command()
  async def invite(self, ctx):
    embed = discord.Embed(title = "Add the bot to your server using the following link.", color = embed_colour)
    embed.set_thumbnail(url=self.bot.user.avatar_url)
    embed.add_field(name="Invite Bot", value="[Invite link.](https://discord.com/api/oauth2/authorize?client_id=634409171114262538&permissions=8&scope=bot)", inline=False)

    await ctx.send(embed=embed)
  
  # spam
  @commands.command(aliases = ['sp'])
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
  @commands.command(aliases = ['stopsp'])
  async def stopspam(self, ctx):
    global on
    on = False
    await ctx.send("stopped")

	# say
  @commands.command(aliases = ['s'])
  async def say(self, ctx, *, message):
    await ctx.send(message)
    asyncio.sleep(0.5)

	# cum
  @commands.command(hidden = True)
  async def cum(self, ctx):
    await ctx.send("uGn!~~")
    asyncio.sleep(0.5)
  
  # delaysay
  @commands.command(aliases = ['dsay'])
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
	bot.add_cog(Basic(bot))

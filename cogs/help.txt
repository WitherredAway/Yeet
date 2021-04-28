import discord
import asyncio
from main import bot, prefix, embed_colour
from discord.ext import commands

class Help(commands.Cog):
  
  def __init__(self, bot):
    self.bot = bot

  # help
  @commands.command()
  async def help(self, ctx):
	  
	  help = discord.Embed(title = "Help command.", description = f"List of commands and syntaxes", colour = embed_colour)
	  help.add_field(name = "Bot", value = f"`{prefix}ping` - Responds with 'Pong!' and the bot's latency.\n`{prefix}invite` - Provides the bot's invite link.", inline = False)
	  help.add_field(name = "Fun", value = f"`{prefix}spam <message> <delay>` - Spams <message> every <delay> seconds. For multi-word messages put them within quotes.\n`{prefix}stopspam` - Stops the current spam.\n`{prefix}say <message>` - Makes the bot repeat <message>.\n`{prefix}delaysay <message> <delay>` - Repeats <message> after <delay> seconds. For multi-word messages put them within quotes.")
	  await ctx.send(embed = help)
	  
def setup(bot):
  bot.add_cog(Help(bot))
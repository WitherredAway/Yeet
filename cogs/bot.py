import discord
from discord.ext import commands
from main import bot, prefix, embed_colour
import asyncio

class Bot(commands.Cog):
  """Commands related to the bot."""
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
  """
  # @mention
  @commands.Cog.listener()
  async def on_message(self, message):
  	if message.content.startswith("<@634409171114262538>" or "@Yeet.1830"):
	    await message.channel.send(f"My prefix is `{prefix}`\nDo `{prefix}help` for a list of commands")
	"""
	# ping
  @commands.command(name = "ping", 
                    brief = "Bot's latency",
                    help = "Responds with 'Pong!' and the bot's latency")
  async def ping(self, ctx):
    await ctx.send(f'Pong! {round(bot.latency * 1000)}ms')
    
  # invite
  @commands.command(name = "invite",
                    brief = "Bot's invite link",
                    help = "Sends the bot's invite link."
                    )
  async def invite(self, ctx):
    embed = discord.Embed(title = "Add the bot to your server using the following link.", color = embed_colour)
    embed.set_thumbnail(url=self.bot.user.avatar_url)
    embed.add_field(name="Invite Bot", value="[Invite link.](https://discord.com/api/oauth2/authorize?client_id=634409171114262538&permissions=8&scope=bot)", inline=False)

    await ctx.send(embed=embed)

def setup(bot):
	bot.add_cog(Bot(bot))
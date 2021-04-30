import discord
from discord.ext import commands
from main import bot, prefix, embed_colour
import asyncio
import datetime

class Bot(commands.Cog):
  """Commands related to the bot."""
  def __init__(self, bot):
    self.bot = bot

  @commands.Cog.listener()
  async def on_ready(self):
    await bot.change_presence(status=discord.Status.online, activity=discord.Game(f'{prefix}help'))
    print("Running.")
    print(bot.user)
    
  # logs
  @commands.Cog.listener(name="on_command")
  async def on_command(self, ctx):
    try:
      log_channel = bot.get_channel(837542790119686145)
      user = ctx.author
      command = ctx.command
      channel = str(ctx.channel)
      server = ctx.guild.name
  
      em = discord.Embed(title = "Server name", description = server, colour = embed_colour)
  
      em.set_author(name = user, icon_url = user.avatar_url)
      em.add_field(name = "Channel name", value = f"#{channel}", inline = False)
      em.add_field(name = "Command used", value = str(ctx.message.content), inline = False)
      em.timestamp = datetime.datetime.utcnow()
      em.set_footer(text = "Yeet.")
  
      await log_channel.send(embed = em)
      
    except Exception as e:
	    await ctx.send(str(e))
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
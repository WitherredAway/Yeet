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
      message_content = str(ctx.message.content)
      message_id = ctx.message.id
      channel = str(ctx.channel)
      channel_id = ctx.channel.id
      
      em = discord.Embed(colour = embed_colour)
  
      em.set_author(name = user, icon_url = user.avatar_url)
      em.add_field(name = "Command used", value = message_content, inline = False)
      em.timestamp = datetime.datetime.utcnow()
      if ctx.guild:
        server = ctx.guild.name
        server_id = ctx.guild.id
        em.add_field(name = "Go to", value = f"[Warp](https://discord.com/channels/{server_id}/{channel_id}/{message_id})")
        em.set_footer(text = f"{server} | #{channel}")
      else:
        em.set_footer(text = "Direct messages")
      await log_channel.send(embed = em)
      
    except Exception as e:
	    await ctx.send(str(e))
	    raise e
	# ping
  @commands.command(name = "ping", 
                    brief = "Bot's latency",
                    help = "Responds with 'Pong!' and the bot's latency")
  async def ping(self, ctx):
    try:
      message = await ctx.send('Pong!')
      ms = int((message.created_at - ctx.message.created_at).total_seconds() * 1000)
      await message.edit(content= f"Pong! {ms} ms")
    except Exception as error:
      await ctx.send(str(error))
      raise error
    
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
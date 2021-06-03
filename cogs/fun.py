import discord
from discord.ext import commands
from main import *
import asyncio
from PIL import Image, ImageDraw, ImageFont, ImageFilter
from datetime import datetime
import os

class Fun(commands.Cog):
  """Fun commands."""
  def __init__(self, bot):
    self.bot = bot
  
	# say
  @commands.command(name = "say",
                    aliases = ['s'],
                    brief = "Repeats <message>",
                    help = "Repeats <message> passed in after the command."
                    )
  @commands.cooldown(1, cmd_cd, commands.BucketType.user)
  async def say(self, ctx, *, message):
    await ctx.send(message)

	# cum
  @commands.cooldown(1, cmd_cd, commands.BucketType.user)
  @commands.command(hidden = True)
  async def cum(self, ctx):
    await ctx.send("uGn!~~")
  
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
  
  #snap
  @commands.command()
  async def snap(self, ctx, member: discord.Member, *, message):
      colour = {
          "time": (114, 118, 125),
          "content": (220, 221, 222)
          
      }
      size = {
          "title": 20,
          "time": 13
		}
		
      font = './fonts/whitneymedium.otf'

      if not member:
          member = ctx.author

      img = Image.new('RGB', (500, 115), color = (54,57,63))
      titlefnt = ImageFont.truetype(font, size["title"])
      timefnt = ImageFont.truetype(font, size["time"])
      d = ImageDraw.Draw(img)
      if member.nick is None:
          txt = member.name
      else:
          txt = member.nick
      color = member.color.to_rgb()
      if color == (0, 0, 0):
          color = (255,255,255)
      d.text((90, 20), txt, font=titlefnt, fill=color)
      h, w = d.textsize(txt, font=titlefnt)
      time = datetime.utcnow().strftime("Today at %I:%M %p")
      d.text((90+h+10, 25), time, font=timefnt, fill=colour["time"])
      d.text((90, 25+w), message, font=titlefnt, fill=colour["content"])

      img.save('img.png')
      if member.is_avatar_animated():
          await member.avatar_url_as().save("pfp.gif")
          f2 = Image.open("pfp.gif")
      else:
          await member.avatar_url_as().save("pfp.png")
          f2 = Image.open("pfp.png")
      f1 = Image.open("img.png")
      f2.thumbnail((50, 55))
      f2.save("pfp.png")
      
      f2 = Image.open("pfp.png").convert("RGB")
      
      mask = Image.new("L", f2.size, 0)
      draw = ImageDraw.Draw(mask)
      draw.ellipse((0, 0, f2.size[0], f2.size[1]), fill=255)
      mask = mask.filter(ImageFilter.GaussianBlur(0))
      
      result = f2.copy()
      result.putalpha(mask)
      
      result.save('pfp.png')
      
      f2 = Image.open("pfp.png")
      
      f3 = f1.copy()
      f3.paste(f2, (20, 20), f2)
      f3.save("img.png")
      
      file = discord.File("img.png")
      await ctx.send(file=file)
      
      try:
          os.remove("pfp.png")
          os.remove("img.png")
          os.remove("pfp.gif")
          await ctx.message.delete()
      except:
          pass


def setup(bot):
	bot.add_cog(Fun(bot))

import discord
from discord.ext import commands
from main import *
import asyncio

class Channel(commands.Cog):
  """Prank commands."""
  def __init__(self, bot):
    self.bot = bot
  
  global confirm
  confirm = "confirm"
  @commands.check_any(commands.is_owner(), commands.has_permissions(manage_messages = True), commands.guild_only())
  @commands.group(name="channel",
                  aliases=["ch"],
                  brief="Useful channel management commands",
                  help="Channel management commands, use the help command for a list of commands",
                  invoke_without_command=True,
                  case_insensitive=True
  )
  async def _channel(self, ctx):
      await ctx.send_help(ctx.command)
  
  #togglelock
  @commands.check_any(commands.is_owner(), commands.has_permissions(manage_channels = True), commands.guild_only())
  @_channel.command(name = "togglelock",
                  aliases = ['lock', 'tl'],
                  brief = "Locks/Unlocks a channel, and optionally renames channel",
                  case_insensitive=True,
                  help = "Toggles send_messages perms for everyone. And renames channel if an argument is passed.)")
  async def _togglelock(self, ctx, *, channel_name=None):
      overwrite = ctx.channel.overwrites_for(ctx.guild.default_role)
      ch_name = channel_name
      
      try:
        if ch_name != None and ch_name != "unlockall" and ch_name != "lockall":
          channel = ctx.channel
          await channel.edit(name=ch_name)
          await ctx.send(f"Changed channel name to {ch_name}")
          
        elif ch_name == "unlockall":
            await ctx.send(f"This will **unlock** *all* channels. Type `{confirm}` to confirm.")
            def check(m):
                return m.channel.id == ctx.channel.id and m.author.id == ctx.author.id
            try:
                msg = await self.bot.wait_for("message", timeout=30, check=check)
            except asyncio.TimeoutError:
                return await ctx.send("Time's up. Aborted.")
            if msg.content.lower() != "confirm":
                return await ctx.send("Aborted.")

                
            msg = await ctx.send("Unlocking all channels...")
            for c in ctx.guild.channels:
                if overwrite.send_messages != True:
                    await c.set_permissions(ctx.guild.default_role, send_messages = True)
            await ctx.send("Unlocked all channels ✅.")
            
        elif ch_name == "lockall":
            await ctx.send(f"This will **lock** *all* channels. Type `{confirm}` to confirm.")
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
                if overwrite.send_messages != False:
                    await c.set_permissions(ctx.guild.default_role, send_messages = False)
            await ctx.send("Locked all channels ✅.")

        if overwrite.send_messages != False and ch_name != "unlockall" and ch_name != "lockall":
          await ctx.channel.set_permissions(ctx.guild.default_role, send_messages = False)
          await ctx.send("Locked.")
          
        if overwrite.send_messages == False and ch_name != "unlockall" and ch_name != "lockall":
          await ctx.channel.set_permissions(ctx.guild.default_role, send_messages = True)
          await ctx.send("Unlocked.")
      except Exception as e:
          raise e


  @commands.check_any(commands.is_owner(), commands.has_permissions(manage_channels = True), commands.guild_only())
  @_channel.command(name="stripall",
                   aliases=["sa"],
                   brief="Strips and renames channels.",
                   help="Strips the second part of every channels' name and only keeps the first half, before the provided seperator"
                   )
  async def _stripall(self, ctx, separator):
      await ctx.send(f"This will **rename** *all* channels. This action cannot be undone. Type `{confirm}` to confirm.")
      def check(m):
          return m.channel.id == ctx.channel.id and m.author.id == ctx.author.id
      try:
          msg = await self.bot.wait_for("message", timeout=30, check=check)
      except asyncio.TimeoutError:
          return await ctx.send("Time's up. Aborted.")
      if msg.content.lower() != "confirm":
          return await ctx.send("Aborted.")
      
      await ctx.send(f"Stripping all channel's names with separator ` {separator} ` ...")
      for channel in ctx.guild.channels:
          channel_name = channel.name
          if separator in channel_name:
              channel_name = channel_name.split(separator)
              new_name = channel_name[0]
              await channel.edit(name=new_name)
      await ctx.send("Done stripping all channels' names ✅.")
      
def setup(bot):
	bot.add_cog(Channel(bot))

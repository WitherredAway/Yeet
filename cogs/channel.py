import discord
from discord.ext import commands
from main import *
import asyncio

class Channel(commands.Cog):
  """Channel related commands."""
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
  
  @_channel.command(name="rename",
                    aliases=["re"],
                    brief="Renames channel.",
                    help="Renames the current channel or mentioned channel if argument passed.")
  async def _rename(self, ctx, channel, newname):
      pass
  
  #togglelock
  @commands.check_any(commands.is_owner(), commands.has_permissions(manage_channels = True), commands.guild_only())
  @_channel.command(name = "togglelock",
                  aliases = ['tl'],
                  brief = "Locks/Unlocks a channel, and optionally renames channel",
                  case_insensitive=True,
                  help = "Toggles send_messages perms for everyone. And renames channel if an argument is passed.)")
  async def _togglelock(self, ctx, *, channel_name=None):
      overwrite = ctx.channel.overwrites_for(ctx.guild.default_role)
      ch_name = channel_name
      
      try:
        if ch_name != None:
          channel = ctx.channel
          await channel.edit(name=ch_name)
          await ctx.send(f"Changed channel name to {ch_name}")
          
        if overwrite.send_messages != False:
          await ctx.channel.set_permissions(ctx.guild.default_role, send_messages = False)
          await ctx.send("Locked.")
          
        if overwrite.send_messages == False:
          await ctx.channel.set_permissions(ctx.guild.default_role, send_messages = True)
          await ctx.send("Unlocked.")
      except Exception as e:
          raise e


  #lock
  @commands.check_any(commands.is_owner(), commands.has_permissions(manage_channels = True), commands.guild_only())
  @_channel.command(name="lock",
                   brief="Locks channel(s).",
                   help="Lock current/all channel(s)"
                   )
  async def _lock(self, ctx, channel=None):
      overwrite = ctx.channel.overwrites_for(ctx.guild.default_role)
      
      if channel == None and overwrite.send_messages == True:
          await ctx.channel.set_permissions(ctx.guild.default_role, send_messages = False)
          await ctx.send("Locked.")
          
      if channel == None and overwrite.send_messages != True:
          await ctx.send("This channel is already locked.")
      
      if channel == "all":
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



  #unlock
  @commands.check_any(commands.is_owner(), commands.has_permissions(manage_channels = True), commands.guild_only())
  @_channel.command(name="unlock",
                   brief="Unlocks channel(s).",
                   help="Unlock current/all channel(s)"
                   )
  async def _unlock(self, ctx, channel=None):
      overwrite = ctx.channel.overwrites_for(ctx.guild.default_role)
      
      if channel == None and overwrite.send_messages == False:
          await ctx.channel.set_permissions(ctx.guild.default_role, send_messages = True)
          await ctx.send("Unlocked.")
          
      if channel == None and overwrite.send_messages != False:
          await ctx.send("This channel is already unlocked.")
      
      if channel == "all":
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

  
  @commands.check_any(commands.is_owner(), commands.has_permissions(manage_channels = True), commands.guild_only())
  @_channel.group(name="strip",
                   aliases=["split"],
                   brief="Strips and renames channels.",
                   help=f"Strips off the second part of every channels' name after the separator, and only keeps the first half before the separator\n\nsingle channel\n\n{prefix}channel strip <channel> <separator>.",
                   invoke_without_command=True,
                   case_insensitive=True
                   )
  async def _strip(self, ctx, channel: discord.TextChannel=None, *, separator):
      channel = channel or ctx.channel
      stripped = channel.name.split(separator)[0]
      channel_name = channel.name
      if channel != "all" and channel != "current":
         await ctx.send(f"This will **rename** {channel.mention} to **{stripped}**. This action cannot be undone. Type `{confirm}` to confirm.")
         
      def check(m):
          return m.channel.id == ctx.channel.id and m.author.id == ctx.author.id
      try:
          msg = await self.bot.wait_for("message", timeout=30, check=check)
      except asyncio.TimeoutError:
          return await ctx.send("Time's up. Aborted.")
      if msg.content.lower() != "confirm":
          return await ctx.send("Aborted.")
      
                
      if channel != "all" and channel != "current":
          await ctx.send(f"Stripping {channel.mention}'s name with separator `{separator}` ...")
          if separator in channel_name:
              new_name = stripped
              await channel.edit(name=new_name)
          await ctx.send(f"Done stripping the name of {channel.mention} ✅.")
          
  @_strip.command(name="current",
                  brief="Strips current channel.",
                  help="Strips the channel the command was used in.")
  async def _current(self, ctx, separator):
      
      channel = ctx.channel
      channel_name = channel.name
      stripped = channel.name.split(separator)[0]
      await ctx.send(f"This will **rename** {channel.mention} to **{stripped}**. This action cannot be undone. Type `{confirm}` to confirm.")
      
      def check(m):
          return m.channel.id == ctx.channel.id and m.author.id == ctx.author.id
      try:
          msg = await self.bot.wait_for("message", timeout=30, check=check)
      except asyncio.TimeoutError:
          return await ctx.send("Time's up. Aborted.")
      if msg.content.lower() != "confirm":
          return await ctx.send("Aborted.")
          
      await ctx.send(f"Stripping {channel.mention}'s name with separator `{separator}` ...")
      if separator in channel_name:
          new_name = stripped
          await channel.edit(name=new_name)
      await ctx.send(f"Done stripping the name of {channel.mention} ✅.")

          
  @_strip.command(name="all",
                  brief="Strips all channels.",
                  help="Strips all channels in a server.")
  async def _all(self, ctx, separator):
      
      await ctx.send(f"This will **strip with `{separator}` and rename** *all* channels. This action cannot be undone. Type `{confirm}` to confirm.")
      
      def check(m):
          return m.channel.id == ctx.channel.id and m.author.id == ctx.author.id
      try:
          msg = await self.bot.wait_for("message", timeout=30, check=check)
      except asyncio.TimeoutError:
          return await ctx.send("Time's up. Aborted.")
      if msg.content.lower() != "confirm":
          return await ctx.send("Aborted.")
          
      await ctx.send(f"Stripping all channels' names with separator ` {separator} ` ...")
      for channel in ctx.guild.channels:
          stripped = channel.name.split(separator)[0]
          channel_name = channel.name
          if separator in channel_name:
              new_name = stripped
              await channel.edit(name=new_name)
      await ctx.send("Done stripping all channels' names ✅.")

  
def setup(bot):
	bot.add_cog(Channel(bot))

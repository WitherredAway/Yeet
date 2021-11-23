import discord
from discord.ext import commands
from main import *
import asyncio
from typing import Optional
import textwrap

class Channel(commands.Cog):
  """Channel related commands."""
  def __init__(self, bot):
    self.bot = bot

  global confirm
  confirm = "ligma"
  # channel
  @commands.check_any(commands.is_owner(), commands.has_permissions(manage_channels = True), commands.guild_only())
  @commands.group(name="channel",
                  aliases=["ch"],
                  brief="Useful channel management commands",
                  help="Channel management commands, use the help command for a list of commands",
                  invoke_without_command=True,
                  case_insensitive=True
  )
  async def _channel(self, ctx):
      await ctx.send_help(ctx.command)
  
  # list
  @_channel.group(name="list",
                   aliases=["li"],
                   brief="Lists channels that match specified criterion.",
                   help="Lists channels that match criteria such as 'keyword', 'locked', 'unlocked'.",
                   invoke_without_command=True,
                   case_insensitive=True)
  async def _list(self, ctx):
      await ctx.send_help(ctx.command)

  # keyword
  @_list.command(name="keyword",
                 aliases=["k"],
                 brief="Lists all channels with 'keyword' in the name",
                 help="Lists all channels with 'keyword' in the name of the channel.",
                 case_insensitive=True)
  async def _keyword(self, ctx, *, keyword):
      msg = f"Channels with `{keyword}` in name:"
      num = 0
      for channel in ctx.guild.text_channels:
          if keyword in channel.name:
              msg += f"\n{channel.mention} - **{channel.name}**"
              num += 1
      if num == 0:
          msg += "\n**None**"
      msg += f"\n\nTotal number of channels = **{num}**"
      for para in textwrap.wrap(msg, 2000, expand_tabs=False, replace_whitespace=False, fix_sentence_endings=False, break_long_words=False, drop_whitespace=False, break_on_hyphens=False, max_lines=None):
          await ctx.send(para)
          await asyncio.sleep(0.5)
          
  # startswith
  @_list.command(name="starts_with",
                 aliases=["startswith", "sw"],
                 brief="Lists all channels with message starting with <key>.",
                 help="Lists all channels with last message starting with the word/phrase <key>.",
                 case_insensitive=True)
  async def _starts_with(self, ctx, *, key):
      key = key
      msg = f"Channels with last message starting with `{key}`:"
      num = 0
      wait = await ctx.send(f"Looking for messages starting with `{key}`...")
      for channel in ctx.guild.text_channels:
          async for message in channel.history(limit=1):
              message_content = message.content.lower()
              if len(message.embeds) > 0:
                  if len(message.embeds[0].title) > 0:
                      message_content = message.embeds[0].title.lower()
                  elif len(message.embeds[0].author) > 0:
                      message_content = message.embeds[0].author.lower()
                  elif len(message.embeds[0].description) > 0:
                      message_content = message.embeds[0].description.lower()
                  
              if message_content.startswith(key.lower()):
                num += 1
                msg += f"\n**{num}.** {channel.mention} - **{channel.name}**"
                
      if num == 0:
          msg += "\n**None**"
      msg += f"\n\nTotal number of channels = **{num}**"
      for para in textwrap.wrap(msg, 2000, expand_tabs=False, replace_whitespace=False, fix_sentence_endings=False, break_long_words=False, drop_whitespace=False, break_on_hyphens=False, max_lines=None):
          await ctx.send(para)
          await asyncio.sleep(0.5)
      await wait.edit(content="✅ Done.")
  # state
  @_list.command(name="state",
                 brief="Lists all locked/unlocked channels",
                 help="Lists all channels with 'send_messages' perms turned off/on for everyone.",
                 case_insensitive=True)
  async def _state(self, ctx, state):
      num = 0
      if state.lower() == "locked":
          msg = f"Channels that are `{state.lower()}`"
          for channel in ctx.guild.text_channels:
              overwrite = channel.overwrites_for(ctx.guild.default_role)
              if overwrite.send_messages == False:
                  msg += f"\n{channel.mention} - **{channel.name}**"
                  num += 1
      elif state.lower() == "unlocked":
          msg = f"Channels that are `{state.lower()}`"
          for channel in ctx.guild.text_channels:
              overwrite = channel.overwrites_for(ctx.guild.default_role)
              if overwrite.send_messages != False:
                  msg += f"\n{channel.mention} - **{channel.name}**"
                  num += 1
      else:
          return await ctx.send("The 'state' argument must be 'locked' or 'unlocked'.")
      if num == 0:
          msg += "\n**None**"
      msg += f"\n\nTotal number of channels = **{num}**"
      for para in textwrap.wrap(msg, 2000, expand_tabs=False, replace_whitespace=False, fix_sentence_endings=False, break_long_words=False, drop_whitespace=False, break_on_hyphens=False, max_lines=None):
          await ctx.send(para)
          await asyncio.sleep(0.5)
          
  # rename
  @_channel.command(name="rename",
                    aliases=["re"],
                    brief="Renames channel.",
                    help="Renames the current channel or mentioned channel if argument passed.")

  async def _rename(self, ctx, channel: Optional[discord.TextChannel] = None, *, newname):
      if channel is None:
          channel = ctx.channel

      current_name = channel.name
      await channel.edit(name = newname)
      await ctx.send(f"Changed {channel.mention}'s name from **{current_name}** to **{channel.name}**.")

  #togglelock
  @commands.check_any(commands.is_owner(), commands.has_permissions(manage_channels = True), commands.guild_only())
  @_channel.command(name = "togglelock",
                  aliases = ['tl'],
                  brief = "Locks/Unlocks a channel, and optionally renames channel",
                  case_insensitive=True,
                  help = "Toggles send_messages perms for everyone. And renames channel if an argument is passed.)")
  async def _togglelock(self, ctx, channel: Optional[discord.TextChannel]=None, *, channel_name=None):
      chnl = channel
      if chnl is None:
          channel = ctx.channel
      current_name = channel.name
      if chnl is None and channel_name != None:
          channel_name = f"{current_name} {channel_name}"
      overwrite = channel.overwrites_for(ctx.guild.default_role)
      
      try:
        if overwrite.send_messages != False:
          await channel.set_permissions(ctx.guild.default_role, send_messages = False)
          await ctx.send("Locked.")
          
        if overwrite.send_messages == False:
          await channel.set_permissions(ctx.guild.default_role, send_messages = True)
          await ctx.send("Unlocked.")

        if channel_name != None:
          await channel.edit(name = channel_name)
          await ctx.send(f"Changed channel name from **{current_name}** to **{channel.name}**.")
          await asyncio.sleep(0.5)

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
            if msg.content.lower() != confirm:
                return await ctx.send("Aborted.")

            msg = await ctx.send("Locking all channels...")
            for c in ctx.guild.text_channels:
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
            if msg.content.lower() != confirm:
                return await ctx.send("Aborted.")

                
            msg = await ctx.send("Unlocking all channels...")
            for c in ctx.guild.text_channels:
                if overwrite.send_messages != True:
                    await c.set_permissions(ctx.guild.default_role, send_messages = True)
            await ctx.send("Unlocked all channels ✅.")

  # strip
  @commands.check_any(commands.is_owner(), commands.has_permissions(manage_channels = True), commands.guild_only())
  @_channel.group(name="strip",
                 brief="Strips current or mentioned channel.",
                 help="Strips current or channel mentioned, according to syntax.",
                 invoke_without_command=True,
                 case_insensitive=True)
  async def _strip(self, ctx, channel: Optional[discord.TextChannel] = None, *, separator):
      if channel is None:
          channel = ctx.channel
      stripped = channel.name.split(separator)[0]
      #if separator in channel.name:
          #await ctx.send(f"This will **rename** {channel.mention} to **{stripped}**. This action cannot be undone. Type `{confirm}` to confirm.")
      if separator not in channel.name:
          return await ctx.send("Nothing to strip.")

      """
      def check(m):
          return m.channel.id == ctx.channel.id and m.author.id == ctx.author.id
      try:
          msg = await self.bot.wait_for("message", timeout=30, check=check)
      except asyncio.TimeoutError:
          return await ctx.send("Time's up. Aborted.")
      if msg.content.lower() != "confirm":
          return await ctx.send("Aborted.")
      """
      current_name = channel.name
      if separator in channel.name:
          #await ctx.send(f"Stripping {channel.mention}'s name with separator ` {separator} ` ...")
          new_name = stripped
          await channel.edit(name=new_name)
          await ctx.send(f"✅ Done stripping the name of {channel.mention} from **{current_name}** to **{channel.name}**.")

          
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
      if msg.content.lower() != confirm:
          return await ctx.send("Aborted.")
          
      await ctx.send(f"Stripping all channels' names with separator ` {separator} ` ...")
      for channel in ctx.guild.text_channels:
          stripped = channel.name.split(separator)[0]
          channel_name = channel.name
          if separator in channel_name:
              new_name = stripped
              await channel.edit(name=new_name)
      await ctx.send("Done stripping all channels' names ✅.")

  
def setup(bot):
	bot.add_cog(Channel(bot))

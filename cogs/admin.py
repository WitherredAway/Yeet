import discord
from discord.ext import commands
from main import *
import asyncio

class Admin(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @property
    def display_emoji(self) -> discord.PartialEmoji:
        return discord.PartialEmoji(name='\N{HAMMER AND PICK}')

      
    # cog
    @commands.is_owner()
    @commands.group(name="cog",
           aliases=["c"],
           invoke_without_command=True,
           case_insensitive=True,
           hidden=True,
           help="Commands related to cogs, dev only command.")
    async def cog(self, ctx):
        await ctx.send_help(ctx.command)
    
    # cog load
    @cog.command(name = "load",
               aliases = ['l'], 
               hidden = True,
               brief = "Load a cog",
               help = "Loads a cog with the name, dev only command.")
    async def _load(self, ctx, cog):
        try:
            bot.load_extension(f'cogs.{cog}')
        except commands.ExtensionNotFound:
            await ctx.send(f":x: Cog `{cog}` not found.")
        except commands.ExtensionAlreadyLoaded:
            await ctx.send(f"Cog `{cog}` is already loaded.")
        except Exception as e:
  	        raise e
        else:
            await ctx.send(f':inbox_tray: Loaded cog `{cog}`')
  
    # cog unload
    @cog.command(name = "unload", 
               aliases = ['u'],
               hidden = True,
               brief = "Unloads a cog",
               help = "Unloads a cog with the name, dev only command.")
    async def _unload(self, ctx, cog):
        if cog.lower() == "admin":
            await ctx.send(":x: Cannot unload this cog")
        else:
            try:
                bot.unload_extension(f'cogs.{cog}')
            except commands.ExtensionNotLoaded:
                await ctx.send(f":x: Cog `{cog}` not found.")
            except Exception as e:
                raise e
            else:
                await ctx.send(f':outbox_tray: Unloaded cog `{cog}`')
  
    # cog reload
    @cog.command(name = "reload", 
               aliases = ['r'],
               hidden = True,
               brief = "Reloads a cog",
               help = "Reloads a cog with the name, dev only command.")
    async def _reload(self, ctx, cog):
        try:
            if cog == 'all':
                try:
                    loaded = ""
                    for cog_ext in list(bot.extensions):
                        bot.reload_extension(str(cog_ext))
                        loaded += f':repeat: Reloaded cog `{cog_ext[5:]}`\n'
                    await ctx.send(loaded)
                except Exception as e:
                    raise e
            else:
                try:
                    bot.reload_extension(f'cogs.{cog}')
                except commands.ExtensionNotLoaded:
                    await ctx.send(f":x: Cog `{cog}` not found.")
                else:
                    await ctx.send(f':repeat: Reloaded cog `{cog}`')
        except Exception as e:
  	        raise e
  
    # cog all
    @cog.command(name = "all", aliases = ['a'], hidden = True, brief = "All cogs", help = "Lists all cogs, dev only command.")
    async def _all(self, ctx):
        coglist = discord.Embed(title = "Cogs", description  = "List of all enabled cogs", colour = embed_colour)
  		
        for cog in bot.extensions:
            if cog.startswith("cogs"):
                cogn = cog.split(".")[1].capitalize()
            else:
                cogn = cog
            coglist.add_field(name = cogn, value = str(cog), inline = False)
        await ctx.send(embed = coglist)
  		
def setup(bot):
  bot.add_cog(Admin(bot))
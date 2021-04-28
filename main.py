from asyncio import sleep
import os
import discord
from replit import db
from keep_alive import keep_alive
from discord.ext import commands
from pretty_help import DefaultMenu, PrettyHelp

prefix = '--'

menu = DefaultMenu("◀️", "▶️", "❌", active_time = 60)

bot = commands.Bot(command_prefix=commands.when_mentioned_or(prefix), 
                   owner_id=267550284979503104,
                   case_insensitive=True, 
                   help_command = PrettyHelp(),
                   self_bot=False)

embed_colour = 0x8AFFAD

bot.help_command = PrettyHelp(menu=menu, color=embed_colour, sort_command=False, show_index=True)

# cog_load
@bot.command(name = "cog_load",
             aliases = ['cl'], 
             hidden = True,
             brief = "Load a cog",
             help = "Loads a cog with the name, dev only command."
             )
@commands.is_owner()
async def cogload(ctx, extension):
  bot.load_extension(f'cogs.{extension}')
  await ctx.send(f":inbox_tray: Loaded cog  `{extension}`")
@cogload.error
async def cogload_error(ctx, error):
  if isinstance(error, commands.NotOwner):
    await ctx.send("You do not own this bot.")

#cog_unload
@bot.command(name = "cog_unload", 
             aliases = ['cu'],
             hidden = True,
             brief = "Unloads a cog",
             help = "Unloads a cog with the name, dev only command."
             )
@commands.is_owner()
async def cogunload(ctx, extension):
  bot.unload_extension(f'cogs.{extension}')
  await ctx.send(f":outbox_tray: Unloaded cog `{extension}`")
@cogunload.error
async def cogunload_error(ctx, error):
  if isinstance(error, commands.NotOwner):
    await ctx.send("You do not own this bot.")
    
#cog_reload
@bot.command(name = "cog_reload", 
             aliases = ['cr'], 
             hidden = True,
             brief = "Reloads a cog",
             help = "Unloads and loads a cog with the name, dev only command."
             )
@commands.is_owner()
async def cogreload(ctx, extension):
  bot.unload_extension(f'cogs.{extension}')
  bot.load_extension(f'cogs.{extension}')
  await ctx.send(f":repeat: Reloaded cog `{extension}`")
@cogreload.error
async def cogreload_error(ctx, error):
  if isinstance(error, commands.NotOwner):
    await ctx.send("You do not own this bot.")
    
for filename in os.listdir('./cogs'):
	if filename.endswith(".py"):
		bot.load_extension(f'cogs.{filename[:-3]}')

keep_alive()
my_secret = os.environ['botTOKEN']
bot.run(my_secret, bot=True)

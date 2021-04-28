import asyncio
import os
import discord
from replit import db
from keep_alive import keep_alive
from discord.ext import commands

prefix = '--'
bot = commands.Bot(command_prefix=prefix, owner_id=267550284979503104, case_insensitive=True, help_command = None, self_bot=False)

embed_colour = 0x8AFFAD

# cog_load
@bot.command(aliases = ['cl'], hidden = True)
@commands.is_owner()
async def cogload(ctx, extension):
  bot.load_extension(f'cogs.{extension}')
  await ctx.send(f":inbox_tray: Loaded cog  `{extension}`")
@cogload.error
async def cogload_error(ctx, error):
  if isinstance(error, commands.NotOwner):
    await ctx.send("You do not own this bot.")

#cog_unload
@bot.command(aliases = ['cu'], hidden = True)
@commands.is_owner()
async def cogunload(ctx, extension):
  bot.unload_extension(f'cogs.{extension}')
  await ctx.send(f":outbox_tray: Unloaded cog `{extension}`")
@cogunload.error
async def cogunload_error(ctx, error):
  if isinstance(error, commands.NotOwner):
    await ctx.send("You do not own this bot.")
    
#cog_reload
@bot.command(aliases = ['cr'], hidden = True)
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
my_secret = os.environ['altTOKEN']
bot.run(my_secret, bot=False)

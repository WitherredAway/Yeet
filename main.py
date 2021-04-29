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

@bot.event
async def on_command_error(ctx, error):
  ignore = (commands.CommandNotFound, commands.UserInputError)
  
  if isinstance(error, ignore):
    return
  
  if isinstance(error, commands.NotOwner):
    await ctx.send("You do not own this bot.")
    
  else:
    raise error
    
  
# cog_load
@bot.command(name = "cogload",
             aliases = ['cl'], 
             hidden = True,
             brief = "Load a cog",
             help = "Loads a cog with the name, dev only command."
             )
@commands.is_owner()
async def cogload(ctx, cog):
  try:
    bot.load_extension(f'cogs.{cog}')
  except commands.ExtensionAlreadyLoaded:
    await ctx.send(f"Cog `{cog}` is already loaded.")
  except commands.ExtensionNotFound:
    await ctx.send(f"Cog `{cog}` not found.")
  else:
    await ctx.send(f":inbox_tray: Loaded cog  `{cog}`")
  raise error
#cog_unload
@bot.command(name = "cogunload", 
             aliases = ['cu'],
             hidden = True,
             brief = "Unloads a cog",
             help = "Unloads a cog with the name, dev only command."
             )
@commands.is_owner()
async def cogunload(ctx, cog):
  try:
    bot.unload_extension(f'cogs.{cog}')
  except commands.ExtensionNotLoaded:
    await ctx.send(f":x: Cog `{cog}` not found.")
  else:
    await ctx.send(f":outbox_tray: Unloaded cog `{cog}`")
    
@bot.command(name = "cogreload", 
             aliases = ['cr'],
             hidden = True,
             brief = "Reloads a cog",
             help = "Reloads a cog with the name, dev only command.")
@commands.is_owner()
async def cogreload(ctx, cog):
	'''
	Reloads a cog.
	'''
	if cog == 'all':
	  try:
	    for cog_ext in list(bot.extensions):
	      bot.reload_extension(str(cog_ext))
	      await ctx.send(f':repeat: Reloaded cog `{cog_ext[5:]}`')
	  except Exception as e:
	    await ctx.send(str(e))
	else:
	  try:
	    bot.reload_extension(f'cogs.{cog}')
	  except commands.ExtensionNotLoaded:
	    await ctx.send(f":x: Cog `{cog}` not found.")
	  else:
	    await ctx.send(f':repeat: Reloaded cog `{cog}`')


# cogall
@bot.command(name = "cogall", 
             aliases = ['ca'],
             hidden = True,
             brief = "All cogs",
             help = "Lists all cogs, dev only command.")
@commands.is_owner()
async def cogall(ctx):
		'''
		Returns a list of all enabled commands.
		'''
		
		list = discord.Embed(title = "Cogs", description  = "List of all enabled cogs", colour = embed_colour)
		
		for cog in bot.extensions:
		  list.add_field(name = str(cog[5:]), value = str(cog), inline = False)
		await ctx.send(embed = list)

for filename in os.listdir('./cogs'):
  if filename.endswith(".py"):
    bot.load_extension(f'cogs.{filename[:-3]}')

keep_alive()
my_secret = os.environ['altTOKEN']
bot.run(my_secret, bot=False)

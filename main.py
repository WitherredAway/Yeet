import os
from keep_alive import keep_alive
from discord.ext import commands
from pretty_help import DefaultMenu, PrettyHelp
import requests

prefix = ','
prefix2 = '_'

def get_prefix(bot, message):

    prefixes = [prefix, prefix2, '>>']
    if not message.guild:
        return prefix
    return commands.when_mentioned_or(*prefixes)(bot, message)

menu = DefaultMenu("◀️", "▶️", "❌", active_time = 60)

embed_colour = 0xf1c40f

cmd_cd = 2

log_channel = 837542790119686145

bot = commands.Bot(
                   command_prefix=get_prefix, 
                   owner_id=267550284979503104,
                   case_insensitive=True, 
                   help_command=PrettyHelp(),
                   self_bot=False)

bot.help_command = PrettyHelp(menu=menu, color=embed_colour, sort_command=False, show_index=True)

for filename in os.listdir('./cogs'):
  if filename.endswith(".py"):
    bot.load_extension(f'cogs.{filename[:-3]}')

global TOKEN
TOKEN = os.environ['botTOKEN']
r = requests.head(url="https://discord.com/api/v1")
try:
    print(f"Rate limit {round(int(r.headers['Retry-After']) / 60, 2)} minutes left")
except Exception as e:
    print(e)
    print("No rate limit")
    keep_alive()
    bot.run(TOKEN, bot = True)

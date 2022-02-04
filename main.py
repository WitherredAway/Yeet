import os
import discord
from keep_alive import keep_alive
from discord.ext import commands
import requests
import cogs.utils.slash as slash
global prefixes
prefixes = [',', '_', '>>']
prefix = prefixes[0]

def get_prefix(bot, message):
    if not message.guild:
        return prefix
    return commands.when_mentioned_or(*prefixes)(bot, message)


embed_colour = 0xf1c40f

cmd_cd = 2 #seconds

log_channel = 837542790119686145
intents = discord.Intents().default()
intents.members = True        
bot = slash.Bot(command_prefix=get_prefix, 
                owner_ids=[267550284979503104, 761944238887272481],
                case_insensitive=True,
                activity=discord.Game(f'{prefix}help'),
                status=discord.Status.online,
                intents=intents
                )

bot.load_extension('jishaku')
for filename in os.listdir('./cogs'):
  if filename.endswith(".py"):
    bot.load_extension(f'cogs.{filename[:-3]}')

global TOKEN
TOKEN = os.getenv('botTOKEN')

r = requests.head(url="https://discord.com/api/v1")
try:
    print(f"Rate limit {round(int(r.headers['Retry-After']) / 60, 2)} minutes left")
except Exception as e:
    print("No rate limit")
    bot.run(TOKEN)



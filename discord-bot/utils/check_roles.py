"""
Check role names using default intents
"""
import discord
from discord.ext import commands
import json
import os

config_path = os.path.join(os.path.dirname(__file__), 'config.json')
with open(config_path, 'r') as f:
    config = json.load(f)

BOT_TOKEN = config.get('bot_token')
intents = discord.Intents.default() # Default usually has guilds, which should have roles
bot = commands.Bot(command_prefix='!', intents=intents)

@bot.event
async def on_ready():
    guild = bot.guilds[0]
    print(f"Roles in {guild.name}:")
    for role in guild.roles:
        print(f"- {role.name}")
    
    await bot.close()

if __name__ == "__main__":
    bot.run(BOT_TOKEN)

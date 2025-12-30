"""
Rename level-ups to welcome - activity feed channel
"""
import discord
from discord.ext import commands
import json
import os

config_path = os.path.join(os.path.dirname(__file__), 'config.json')
with open(config_path, 'r') as f:
    config = json.load(f)

BOT_TOKEN = config.get('bot_token')
intents = discord.Intents.default()
bot = commands.Bot(command_prefix='!', intents=intents)

@bot.event
async def on_ready():
    guild = bot.guilds[0]
    
    # Find the level-ups channel and rename it
    for channel in guild.text_channels:
        if "level-ups" in channel.name.lower():
            await channel.edit(
                name="👋│welcome",
                topic="Welcome new members & watch traders rank up! 🔥"
            )
            await channel.edit(position=0)
            print(f"✅ Renamed to #👋│welcome and moved to top")
            break
    
    await bot.close()

if __name__ == "__main__":
    bot.run(BOT_TOKEN)

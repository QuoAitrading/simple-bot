"""
List all emojis in the server to choose one for welcome reaction
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
# Need emoji intent (covered by default usually)
bot = commands.Bot(command_prefix='!', intents=intents)

@bot.event
async def on_ready():
    guild = bot.guilds[0]
    print(f"Animated Emojis in {guild.name}:")
    
    count = 0
    for emoji in guild.emojis:
        if emoji.animated:
            print(f"- Name: {emoji.name} | ID: {emoji.id} | Format: <a:{emoji.name}:{emoji.id}>")
            count += 1
            
    if count == 0:
        print("❌ No animated emojis found! Please upload one in Server Settings -> Emoji.")
    else:
        print(f"\nFound {count} animated emojis.")
    
    await bot.close()

if __name__ == "__main__":
    bot.run(BOT_TOKEN)

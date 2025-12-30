"""
Script to create the '#💸│gains' channel in the Free Community category.
Allows users to post pictures and messages.
"""
import discord
from discord.ext import commands
import json
import os
import asyncio

# Config
config_path = os.path.join(os.path.dirname(__file__), 'config.json')
with open(config_path, 'r') as f:
    config = json.load(f)

TOKEN = config.get('bot_token')

intents = discord.Intents.default()
intents.guilds = True
bot = commands.Bot(command_prefix='!', intents=intents)

@bot.event
async def on_ready():
    guild = bot.guilds[0]
    print(f"Connected to {guild.name}")
    
    # 1. Find 'Free Community' Category
    category_name = "Free Community"
    category = discord.utils.get(guild.categories, name=category_name)
    
    if not category:
        print(f"⚠️ Category '{category_name}' not found. Creating it...")
        category = await guild.create_category(category_name)

    # 2. Create 'gains' channel
    channel_name = "💸│gains"
    existing = discord.utils.get(guild.text_channels, name=channel_name)
    
    if existing:
        print(f"✅ Channel '{channel_name}' already exists.")
    else:
        print(f"Creating channel '{channel_name}'...")
        
        # Permissions: Everyone can send messages and attach files
        overwrites = {
            guild.default_role: discord.PermissionOverwrite(
                read_messages=True,
                send_messages=True,
                attach_files=True,  # Crucial for posting pictures
                embed_links=True
            )
        }
        
        channel = await guild.create_text_channel(
            name=channel_name,
            category=category,
            overwrites=overwrites,
            topic="💰 Share your trading wins and profits here! 🚀"
        )
        await channel.send("💸 **PROFIT & GAINS**\n\nShare your winning trades, PnL screenshots, and success stories here!\nLet's celebrate those green days! 🚀💰")
        print(f"✅ Created '{channel_name}' in '{category.name}'")

    await bot.close()

if __name__ == "__main__":
    bot.run(TOKEN)

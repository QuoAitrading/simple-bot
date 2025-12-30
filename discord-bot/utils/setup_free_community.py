"""
Setup Free Community Category and Channels
Run once to create the free community structure
"""

import discord
from discord.ext import commands
import asyncio
import json
import os

# Load config
config_path = os.path.join(os.path.dirname(__file__), 'config.json')
with open(config_path, 'r') as f:
    config = json.load(f)

BOT_TOKEN = config.get('bot_token')

intents = discord.Intents.default()
bot = commands.Bot(command_prefix='!', intents=intents)

# Free Community Channel Structure
FREE_COMMUNITY_CHANNELS = [
    {"name": "😂│memes", "type": "text", "topic": "Trading memes and humor"},
    {"name": "💬│general-chat", "type": "text", "topic": "Free community discussion"},
    {"name": "📰│market-news", "type": "text", "topic": "Share market news and updates"},
    {"name": "📅│earnings-calendar", "type": "text", "topic": "Upcoming earnings and economic events"},
]


@bot.event
async def on_ready():
    print(f"✅ Logged in as {bot.user}")
    
    if len(bot.guilds) == 0:
        print("❌ Bot is not in any servers!")
        await bot.close()
        return
    
    guild = bot.guilds[0]
    print(f"📍 Setting up Free Community in: {guild.name}")
    
    # Create the category
    category = discord.utils.get(guild.categories, name="『 Free Community 』")
    if not category:
        category = await guild.create_category("『 Free Community 』")
        print(f"✅ Created category: 『 Free Community 』")
    else:
        print(f"📂 Category already exists: 『 Free Community 』")
    
    # Create channels
    for ch in FREE_COMMUNITY_CHANNELS:
        existing = discord.utils.get(guild.text_channels, name=ch["name"])
        if existing:
            print(f"  ⏭️  Channel exists: #{ch['name']}")
            continue
        
        await guild.create_text_channel(
            ch["name"],
            category=category,
            topic=ch.get("topic", "")
        )
        print(f"  ✅ Created: #{ch['name']}")
        await asyncio.sleep(0.5)
    
    print("\n🎉 Free Community setup complete!")
    await bot.close()


if __name__ == "__main__":
    if not BOT_TOKEN:
        print("❌ No bot_token found in config.json")
    else:
        bot.run(BOT_TOKEN)

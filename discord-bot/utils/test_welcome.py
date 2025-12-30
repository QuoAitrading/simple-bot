"""
Test script to simulate welcome + inline pepe
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
intents.members = True
bot = commands.Bot(command_prefix='!', intents=intents)

@bot.event
async def on_ready():
    guild = bot.guilds[0]
    channel = discord.utils.get(guild.text_channels, name="👋│welcome") or \
              discord.utils.get(guild.text_channels, name="welcome")
    
    if not channel:
        print("❌ Could not find welcome channel")
        await bot.close()
        return

    print(f"✅ Sending test welcome to #{channel.name}")
    
    # Simulate member
    n = len(guild.members)
    if 11 <= (n % 100) <= 13:
        suffix = 'th'
    else:
        suffix = {1: 'st', 2: 'nd', 3: 'rd'}.get(n % 10, 'th')
    count_str = f"{n}{suffix}"

    # Get pepe emoji string
    pepe = discord.utils.get(guild.emojis, name="pepe_dance")
    emoji_str = str(pepe) if pepe else "👋"

    # Plain Text with Rainbow Divider (Original) + Inline Black Hole Emoji
    
    # 1. Send Rainbow Divider
    rainbow_path = os.path.join(os.path.dirname(__file__), 'line-rainbow.gif')
    if os.path.exists(rainbow_path):
        await channel.send(file=discord.File(rainbow_path))
    else:
        print("⚠️ Rainbow gif not found, skipping divider.")

    # 2. Send Text
    # Get black hole emoji
    black_hole = discord.utils.get(guild.emojis, name="black_hole")
    bh_str = str(black_hole) if black_hole else "⚫"
    
    msg_content = (
        f"{bh_str} Hello {guild.me.mention}, welcome to **QuoTrading**. You are the **{count_str}** member to join. {emoji_str}"
    )

    await channel.send(content=msg_content)
    print("✅ Sent!")
    
    await bot.close()

if __name__ == "__main__":
    bot.run(BOT_TOKEN)

"""Add Version 1.0 post to updates forum"""

import discord
import json
import os

TOKEN = None
try:
    with open(os.path.join(os.path.dirname(__file__), 'config.json'), 'r') as f:
        TOKEN = json.load(f).get('bot_token')
except:
    pass

intents = discord.Intents.default()
intents.guilds = True
client = discord.Client(intents=intents)

@client.event
async def on_ready():
    print('Connected')
    guild = client.guilds[0]
    
    # Find updates forum
    updates = None
    for ch in guild.channels:
        if 'updates' in ch.name.lower() and isinstance(ch, discord.ForumChannel):
            updates = ch
            break
    
    if not updates:
        print('Updates forum not found')
        await client.close()
        return
    
    await updates.create_thread(
        name='Version 1.0 - Initial Release',
        content="""# 🚀 Version 1.0 - Initial Release

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

**Release Date:** December 2025

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

## ✅ Features

**AI Trading**
• Fully automated trade execution
• Real-time market analysis
• Intelligent signal detection
• Built-in risk management
• Automatic stop loss protection
• 24/5 hands-free operation

**Set & Forget**
• One-time setup
• No manual intervention needed
• AI handles everything for you

**Broker Support**
• TopStep (via Rithmic)

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

*Set it up once. Let the AI trade for you.*
"""
    )
    print('Created Version 1.0 post')
    await client.close()

client.run(TOKEN)

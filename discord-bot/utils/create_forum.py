"""Create Forum channel for AI updates"""

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
    
    # Find AI Automation category
    ai_cat = None
    for cat in guild.categories:
        if 'ai automation' in cat.name.lower():
            ai_cat = cat
            break
    
    if not ai_cat:
        print('AI Automation category not found')
        await client.close()
        return
    
    # Delete old updates channel
    for ch in ai_cat.channels:
        if 'updates' in ch.name.lower():
            await ch.delete()
            print('Deleted old updates channel')
            break
    
    # Create Forum channel
    forum = await guild.create_forum(
        name='📢│updates',
        category=ai_cat,
        topic='AI Automation updates and patch notes'
    )
    print('Created forum channel')
    
    # Create first post - Version 1.0
    thread, message = await forum.create_thread(
        name='Version 1.0 - Initial Release',
        content="""# 🚀 Version 1.0 - Initial Release

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

**Release Date:** December 2024

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

## ✅ Features

**AI Trading Bot**
• Automated trade execution
• Real-time market analysis
• Risk management with stop loss
• Position monitoring

**Broker Support**
• TopStep (via Rithmic API)
• More brokers coming soon

**Dashboard**
• Live trade monitoring
• Performance tracking
• Account status

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

## 🔜 Coming Soon

• Apex Trader Funding support
• Additional broker integrations
• Strategy customization
• Mobile notifications

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

*Thank you for being an early adopter!*
"""
    )
    print('Created Version 1.0 post')
    
    print('Done!')
    await client.close()

client.run(TOKEN)

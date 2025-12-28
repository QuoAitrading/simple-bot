"""Create Feedback Forum and fix Updates post"""

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
    
    # Delete old feedback channel
    for ch in ai_cat.channels:
        if 'feedback' in ch.name.lower():
            await ch.delete()
            print('Deleted old feedback channel')
            break
    
    # Delete old updates forum to recreate with correct content
    for ch in ai_cat.channels:
        if 'updates' in ch.name.lower():
            await ch.delete()
            print('Deleted old updates channel')
            break
    
    # Create Updates Forum
    updates_forum = await guild.create_forum(
        name='📢│updates',
        category=ai_cat,
        topic='AI Automation updates and patch notes'
    )
    
    # Create Version 1.0 post - only what we have
    await updates_forum.create_thread(
        name='Version 1.0 - Initial Release',
        content="""# 🚀 Version 1.0 - Initial Release

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

**Release Date:** December 2024

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

## ✅ Current Features

**AI Trading Bot**
• Automated trade execution
• Real-time market analysis
• Signal generation based on strategy
• Risk management with automatic stop loss
• Position monitoring and management
• Trade logging and history

**Broker Support**
• TopStep (via Rithmic API)

**Dashboard**
• Live trade monitoring
• Performance tracking
• Account connection status
• Trade history view

**Discord Integration**
• Server status updates
• Profit notifications
• Real-time alerts

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

*Thank you for being an early adopter!*
"""
    )
    print('Created Updates forum with Version 1.0 post')
    
    # Create Feedback Forum
    feedback_forum = await guild.create_forum(
        name='💡│feature-requests',
        category=ai_cat,
        topic='Request features and share feedback'
    )
    
    # Create first post explaining how to use
    await feedback_forum.create_thread(
        name='How to Submit Feature Requests',
        content="""# 💡 Feature Requests & Feedback

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

**Want to see something added to the AI?**

Create a new post in this forum with:

1. **Title** - Short description of your idea
2. **Details** - Explain what you want and why

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

We review all requests and will respond to let you know if it's something we can add!

Your feedback helps make the AI better for everyone.

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
"""
    )
    print('Created Feature Requests forum')
    
    print('Done!')
    await client.close()

client.run(TOKEN)

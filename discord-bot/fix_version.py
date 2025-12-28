"""Fix Version 1.0 date and add Bug Reports forum"""

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
    
    ai_cat = None
    for cat in guild.categories:
        if 'ai automation' in cat.name.lower():
            ai_cat = cat
            break
    
    if not ai_cat:
        print('AI Automation category not found')
        await client.close()
        return
    
    # Delete updates forum to fix date
    for ch in ai_cat.channels:
        if 'updates' in ch.name.lower():
            await ch.delete()
            print('Deleted updates channel')
            break
    
    # Recreate Updates Forum with correct date
    updates_forum = await guild.create_forum(
        name='📢│updates',
        category=ai_cat,
        topic='AI Automation updates and patch notes'
    )
    
    await updates_forum.create_thread(
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
    print('Created Version 1.0 with correct date')
    
    # Create Bug Reports Forum
    bug_forum = await guild.create_forum(
        name='🐛│bug-reports',
        category=ai_cat,
        topic='Report bugs and issues'
    )
    
    await bug_forum.create_thread(
        name='How to Report Bugs',
        content="""# 🐛 Bug Reports

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

**Found a bug?** Create a new post with:

1. **Title** - Brief description of the issue
2. **What happened** - Describe the bug
3. **Steps to reproduce** - How can we recreate it?
4. **Screenshots** - If possible

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

We'll investigate and respond as soon as possible.

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
"""
    )
    print('Created Bug Reports forum')
    
    print('Done!')
    await client.close()

client.run(TOKEN)

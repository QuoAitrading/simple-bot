"""Add premium channels under Welcome category"""

import discord
import asyncio
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
    
    # Find Welcome category
    welcome_cat = None
    for cat in guild.categories:
        if 'welcome' in cat.name.lower():
            welcome_cat = cat
            break
    
    if not welcome_cat:
        print('Welcome category not found')
        await client.close()
        return
    
    print('Found welcome category')
    
    # Create Premium Indicator channel
    indicator = await guild.create_text_channel(name='⭐│premium-indicator', category=welcome_cat)
    await indicator.send("""
# ⭐ PREMIUM INDICATOR

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

*Coming soon - Add your indicator description and Whop link here*

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
""")
    print('Created premium-indicator')
    
    # Create AI Automation channel
    ai = await guild.create_text_channel(name='⭐│ai-automation', category=welcome_cat)
    await ai.send("""
# ⭐ AI AUTOMATION

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

*Coming soon - Add your AI automation description and Whop link here*

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
""")
    print('Created ai-automation')
    
    print('Done!')
    await client.close()

client.run(TOKEN)

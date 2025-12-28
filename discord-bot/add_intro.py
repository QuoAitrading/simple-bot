"""Add What We Offer to introduction channel"""

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
    
    intro = None
    for ch in guild.text_channels:
        if 'introduction' in ch.name.lower():
            intro = ch
            break
    
    if not intro:
        print('Introduction channel not found')
        await client.close()
        return
    
    await intro.send("""
**What We Offer:**

📊 Options & Futures Signals - Real-time trade alerts
💹 Crypto Signals - Stay ahead in the crypto markets
💱 Forex Signals - Trade global currencies with confidence
🏀 Sports Betting Picks - Expert picks from professional analysts
🤖 AI Trade Automation - Hands-free trading for markets
🔔 Real-Time Alerts - Get notified instantly
""")
    
    print('Done')
    await client.close()

client.run(TOKEN)

"""Fix introduction channel - delete and rebuild with rainbow at bottom"""

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

RAINBOW_LINE_PATH = os.path.join(os.path.dirname(__file__), 'line-rainbow.gif')

INTRODUCTION_TEXT = """# 👋 Welcome to QuoTrading!
Welcome to the official **QuoTrading** community! We're excited to have you here.

## 🤖 What is QuoTrading?
QuoTrading is your community for trading signals, AI automation, and market analysis.

## 🎯 What We Offer
📊 **Options & Futures Signals** - Real-time trade alerts
💹 **Crypto Signals** - Stay ahead in the crypto markets
💱 **Forex Signals** - Trade global currencies with confidence
🏀 **Sports Betting Picks** - Expert picks from professional analysts
🤖 **AI Trade Automation** - Hands-free trading for markets
🔔 **Real-Time Alerts** - Get notified instantly

## 🚀 Getting Started
1. Read the **#disclaimer** and **#server-rules**
2. Check out **#upgrade-premium** for membership options
3. Join **#general-chat** to meet the community
4. Need help? Open a **support ticket**!

Thanks for being here! Let's win together. 🚀
"""

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
    
    # Delete all messages
    await intro.purge(limit=50)
    print('Cleared channel')
    
    # Rainbow at top
    if os.path.exists(RAINBOW_LINE_PATH):
        file1 = discord.File(RAINBOW_LINE_PATH, filename="rainbow.gif")
        await intro.send(file=file1)
    
    # Main text
    await intro.send(INTRODUCTION_TEXT)
    
    # Rainbow at bottom
    if os.path.exists(RAINBOW_LINE_PATH):
        file2 = discord.File(RAINBOW_LINE_PATH, filename="rainbow.gif")
        await intro.send(file=file2)
    
    print('Done - introduction rebuilt with updated What We Offer')
    await client.close()

client.run(TOKEN)

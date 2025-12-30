"""Update how-it-works with marketing story + images"""

import discord
import json
import os
import asyncio

TOKEN = None
try:
    with open(os.path.join(os.path.dirname(__file__), 'config.json'), 'r') as f:
        TOKEN = json.load(f).get('bot_token')
except:
    pass

# Image paths
LOGIN_IMG = "C:/Users/kevin/.gemini/antigravity/brain/d9f4371c-6cd8-4565-b34a-72b78fa45a66/uploaded_image_1766962083484.png"
ACCOUNTS_IMG = "C:/Users/kevin/.gemini/antigravity/brain/d9f4371c-6cd8-4565-b34a-72b78fa45a66/uploaded_image_1766961059140.png"
RUNNING_IMG = "C:/Users/kevin/.gemini/antigravity/brain/d9f4371c-6cd8-4565-b34a-72b78fa45a66/uploaded_image_1766961221937.png"
RAINBOW_IMG = os.path.join(os.path.dirname(__file__), 'line-rainbow.gif')

intents = discord.Intents.default()
intents.guilds = True
client = discord.Client(intents=intents)

@client.event
async def on_ready():
    print('Connected')
    guild = client.guilds[0]
    
    channel = None
    for ch in guild.text_channels:
        if 'how-it-works' in ch.name.lower():
            channel = ch
            break
    
    if not channel:
        print('how-it-works channel not found')
        await client.close()
        return
    
    await channel.purge(limit=50)
    print('Cleared channel')
    
    # Rainbow at top
    try:
        await channel.send(file=discord.File(RAINBOW_IMG, filename="rainbow.gif"))
    except Exception as e:
        print(f"Rainbow top error: {e}")
    await asyncio.sleep(0.3)
    
    # INTRO WITH STORY
    await channel.send("""
# 🤖 QuoTrading AI - How It Works

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
""")
    await asyncio.sleep(0.3)
    
    await channel.send("""
## Why We Built This

We built QuoTrading AI for **traders who don't have time to trade.**

You have a job. A family. A life. You can't sit in front of charts all day waiting for setups, placing orders, managing positions, watching for exits.

But you know the markets can make you money.

**That's why we created QuoTrading AI.**

A fully automated trading system that does everything for you. No screen time. No stress. No missed trades because you were busy.

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
""")
    await asyncio.sleep(0.3)
    
    await channel.send("""
## What Makes It Different?

**Plug and Forget**
Set it up once. That's it. The AI runs 24/5 without you touching anything.

**No Learning Curve**
You don't need to know technical analysis, chart patterns, or trading strategies. The AI knows it all.

**No Emotional Trading**
The AI doesn't get scared. Doesn't get greedy. It executes the plan every single time.

**Real Automation**
This isn't "signals you have to manually enter." The AI connects to your broker and executes trades automatically. You don't lift a finger.

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
""")
    await asyncio.sleep(0.3)
    
    await channel.send("""
## Who Is This For?

✅ **Busy professionals** who want to trade but don't have time
✅ **New traders** who don't know how to trade yet
✅ **Experienced traders** who want a hands-off system
✅ **Anyone** tired of watching charts all day

If you've ever thought "I wish someone would just trade for me" — this is it.

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
""")
    await asyncio.sleep(0.5)
    
    # STEP 1 - LOGIN
    await channel.send("""
# Step 1: Connect Your Broker

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Launch the QuoTrading AI app and enter your credentials:

**Account Type** - Choose Prop Firm or Live Broker
**Username/Email** - Your broker login
**Broker API Key** - From your broker dashboard (this lets the AI place trades)
**QuoTrading License Key** - Your license (provided after purchase)

This is the only setup you'll ever do.

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
""")
    await asyncio.sleep(0.3)
    
    try:
        await channel.send(file=discord.File(LOGIN_IMG, filename="login.png"))
    except Exception as e:
        print(f"Failed to send login image: {e}")
    await asyncio.sleep(0.5)
    
    # STEP 2 - ACCOUNTS
    await channel.send("""
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

# Step 2: Select Your Accounts

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

The AI automatically detects all accounts linked to your broker.

• See all your trading accounts
• View live balance for each account
• Select which accounts the AI should trade

**Multiple accounts?** No problem. The AI can trade them all simultaneously.

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
""")
    await asyncio.sleep(0.3)
    
    try:
        await channel.send(file=discord.File(ACCOUNTS_IMG, filename="accounts.png"))
    except Exception as e:
        print(f"Failed to send accounts image: {e}")
    await asyncio.sleep(0.5)
    
    # STEP 3 - RUNNING
    await channel.send("""
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

# Step 3: AI Takes Over

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Click **LAUNCH** and walk away. From this moment, you're done.

**What the AI does (so you don't have to):**
• ✅ Connects to our trading servers
• ✅ Monitors markets in real-time, 24/5
• ✅ Analyzes price action and market conditions
• ✅ Detects high-probability trade setups
• ✅ Executes trades automatically
• ✅ Sets stop losses to protect your account
• ✅ Exits positions at optimal times

**What you do:**
• Nothing. Seriously. Just leave it running.

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
""")
    await asyncio.sleep(0.3)
    
    try:
        await channel.send(file=discord.File(RUNNING_IMG, filename="running.png"))
    except Exception as e:
        print(f"Failed to send running image: {e}")
    await asyncio.sleep(0.5)
    
    # FINAL
    await channel.send("""
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

# 🎯 That's It. You're Done.

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

**Set it. Forget it. Live your life.**

The AI trades while you:
• Sleep
• Work
• Spend time with family
• Do literally anything else

This is what trading should be.

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
""")
    await asyncio.sleep(0.3)
    
    await channel.send("""
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

## ⚠️ Important Notes

**Keep the terminal open** - Don't close the window while trading
**Stable internet required** - AI needs constant connection
**One license per user** - Your license works on one device at a time
**Market hours only** - AI trades when futures markets are open (Sun 6PM - Fri 5PM EST)

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

**Questions?** Open a support ticket or ask in #ai-chat

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
""")
    
    # Rainbow at bottom
    try:
        await channel.send(file=discord.File(RAINBOW_IMG, filename="rainbow.gif"))
    except Exception as e:
        print(f"Rainbow bottom error: {e}")
    
    print('Done with marketing story!')
    await client.close()

client.run(TOKEN)

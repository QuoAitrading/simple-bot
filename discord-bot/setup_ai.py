"""Create AI Automation category with all channels"""

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


async def send_msg(channel, text):
    parts = text.strip().split('\n\n')
    current = ""
    for part in parts:
        if len(current) + len(part) + 2 < 1900:
            current += part + "\n\n"
        else:
            if current:
                await channel.send(current.strip())
                await asyncio.sleep(0.5)
            current = part + "\n\n"
    if current.strip():
        await channel.send(current.strip())


@client.event
async def on_ready():
    print('Connected')
    guild = client.guilds[0]
    
    # Create AI Automation category
    cat = await guild.create_category(name='『 AI Automation 』')
    print('Created category')
    
    # 1. AI Explanation Channel
    explain = await guild.create_text_channel(name='🤖│how-it-works', category=cat)
    await send_msg(explain, """
# 🤖 QuoTrading AI Automation

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

## What is QuoTrading AI?

QuoTrading AI is an automated trading system that analyzes the markets and executes trades on your behalf. It uses advanced algorithms and machine learning to identify high-probability trading opportunities.

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

## How Does It Work?

**1. Market Analysis**
The AI continuously scans the markets, analyzing price action, volume, and key technical indicators.

**2. Signal Generation**
When the AI identifies a high-probability setup, it generates a trading signal with entry, stop loss, and take profit levels.

**3. Trade Execution**
Trades are executed automatically on your connected broker account - no manual intervention required.

**4. Risk Management**
Built-in risk management ensures proper position sizing and protects your capital with automatic stop losses.

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

## Key Features

**Fully Automated**
Set it and forget it. The AI trades 24/5 without you needing to watch charts.

**Risk Controlled**
Every trade has defined risk. Never risk more than you're comfortable with.

**Multiple Markets**
Trade futures, forex, and more with the same system.

**Real-Time Monitoring**
Track all trades and performance through the dashboard.

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
""")
    print('Created how-it-works')
    
    # 2. Server Status Channel
    status = await guild.create_text_channel(name='🟢│server-status', category=cat)
    await status.send("""
# 🟢 SERVER STATUS

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

**AI Trading Bot:** 🟢 Online

**API Server:** 🟢 Online

**Database:** 🟢 Online

**Last Updated:** Check pinned message

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

*Status is updated automatically. Green = Online, Red = Offline*
""")
    print('Created server-status')
    
    # 3. Updates Channel
    updates = await guild.create_text_channel(name='📢│updates', category=cat)
    await updates.send("""
# 📢 AI UPDATES

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

All AI updates, improvements, and announcements will be posted here.

Stay tuned for:
• New feature releases
• Performance improvements
• Bug fixes
• Strategy updates

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
""")
    print('Created updates')
    
    # 4. Profits Channel
    profits = await guild.create_text_channel(name='💰│profits', category=cat)
    await profits.send("""
# 💰 AI PROFITS

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Real-time profit updates from the AI trading system.

Trades and P&L will be posted here automatically.

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
""")
    print('Created profits')
    
    # 5. Feedback Channel
    feedback = await guild.create_text_channel(name='📸│feedback', category=cat)
    await feedback.send("""
# 📸 FEEDBACK & SCREENSHOTS

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Share your experience with the AI:
• Post your profit screenshots
• Share your results
• Give feedback on performance
• Ask questions

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
""")
    print('Created feedback')
    
    # 6. AI Chat Channel
    chat = await guild.create_text_channel(name='💬│ai-chat', category=cat)
    await chat.send("""
# 💬 AI DISCUSSION

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Discuss the AI trading system here:
• Ask questions
• Share tips
• Connect with other users
• Get help from the community

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
""")
    print('Created ai-chat')
    
    print('Done!')
    await client.close()

client.run(TOKEN)

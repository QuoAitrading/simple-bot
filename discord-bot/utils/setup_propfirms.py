"""
QuoTrading Discord - Prop Firms Setup
Run this ONCE to create the Prop Firms category with all channels and content.
"""

import discord
import asyncio
import json
import os

# Get token
TOKEN = None
try:
    config_path = os.path.join(os.path.dirname(__file__), 'config.json')
    with open(config_path, 'r') as f:
        config = json.load(f)
    TOKEN = config.get('bot_token')
except:
    pass

if not TOKEN:
    raise ValueError("No bot token found in config.json")

intents = discord.Intents.default()
intents.guilds = True
client = discord.Client(intents=intents)


async def send_long_message(channel, text):
    """Split and send long messages"""
    # Split by double newlines first
    parts = text.strip().split('\n\n')
    current_msg = ""
    
    for part in parts:
        if len(current_msg) + len(part) + 2 < 1900:
            current_msg += part + "\n\n"
        else:
            if current_msg:
                await channel.send(current_msg.strip())
                await asyncio.sleep(0.5)
            current_msg = part + "\n\n"
    
    if current_msg.strip():
        await channel.send(current_msg.strip())


@client.event
async def on_ready():
    print(f'Connected as {client.user}')
    
    guild = client.guilds[0]
    print(f'Setting up Prop Firms in: {guild.name}')
    
    # Create category
    cat = await guild.create_category(name='『 Prop Firms 』')
    print('Created category')
    
    # ==================== EDUCATION ====================
    edu = await guild.create_text_channel(name='📚│prop-firm-education', category=cat)
    
    await send_long_message(edu, """
# 🏦 WHAT IS A PROP FIRM?

A **Proprietary Trading Firm** provides traders with company capital to trade. You don't risk your own money - you trade with theirs and split the profits.

**The Deal:**
→ Pay a one-time evaluation fee
→ Pass their trading challenge
→ Get funded with $10K - $400K+
→ Keep 80-90% of all profits
""")

    await send_long_message(edu, """
# 🎯 HOW EVALUATIONS WORK

**Phase 1: The Challenge**
• Reach profit target (usually 8-10%)
• Stay within daily loss limits (4-5%)
• Stay within max drawdown (8-10%)
• Trade minimum number of days

**Phase 2: Verification (some firms)**
• Lower profit target (5%)
• Same risk rules
• Proves consistency

**Funded Account**
• Trade with real capital
• Withdraw profits regularly
• Follow risk rules
""")

    await send_long_message(edu, """
# 📊 KEY TERMS

**Drawdown** - Max loss allowed before failing

**Trailing Drawdown** - Moves up with profits

**Static Drawdown** - Fixed from starting balance

**Daily Loss Limit** - Max loss per day

**Profit Target** - Amount needed to pass

**Scaling Plan** - Path to larger accounts
""")

    await send_long_message(edu, """
# ⚠️ WHY TRADERS FAIL

1. **Trading Too Large** - Position sizes too big
2. **Revenge Trading** - Chasing losses
3. **Ignoring Rules** - Breaking restrictions
4. **Impatience** - Rushing to hit targets
5. **Not Understanding Drawdown** - Getting stopped out
""")

    await send_long_message(edu, """
# 🛡️ TIPS FOR PASSING

1. Trade your normal strategy
2. Risk management first
3. Track every trade
4. Don't rush
5. Understand ALL the rules
6. Start conservative
""")

    await send_long_message(edu, """
# 🔗 HELPFUL RESOURCES

**Education:**
• https://www.investopedia.com/terms/p/prop_shop.asp
• https://www.tradingview.com/
• https://www.babypips.com/

**Compare Firms:**
• https://propfirmmatch.com/
• https://wegetfunded.com/

**Books:**
• Trading in the Zone - Mark Douglas
• The Disciplined Trader - Mark Douglas
""")
    print('Created education channel')
    
    # ==================== FUTURES ====================
    futures = await guild.create_text_channel(name='📈│futures-prop-firms', category=cat)
    
    await send_long_message(futures, """
# 📈 FUTURES PROP FIRMS

*For trading ES, NQ, CL, GC and CME products*
""")

    await send_long_message(futures, """
## 🔵 TOPSTEP

🔗 https://www.topstep.com/

**✅ Pros**
• Industry pioneer since 2012
• Keep 100% of first $10,000
• No time limit to pass
• Excellent education
• API trading (Rithmic)

**❌ Cons**
• Monthly subscription
• Trailing drawdown strict
• Futures only
""")

    await send_long_message(futures, """
## 🟠 APEX TRADER FUNDING

🔗 https://apextraderfunding.com/

**✅ Pros**
• Keep 100% of first $25,000
• One-step evaluation
• 50-80% off sales often
• No minimum days
• API trading (Rithmic/Tradovate)

**❌ Cons**
• Regular price high
• Trailing drawdown aggressive
• Newer company
""")

    await send_long_message(futures, """
## 🟢 MY FUNDED FUTURES

🔗 https://myfundedfutures.com/

**✅ Pros**
• Same-day payouts
• Simple rules
• Affordable pricing
• One-step evaluation
• API trading

**❌ Cons**
• Max $150K account
• Newer company
• EOD trailing drawdown
""")

    await send_long_message(futures, """
## 🔴 EARN2TRADE

🔗 https://earn2trade.com/

**✅ Pros**
• Education included
• Multiple programs
• Good for beginners

**❌ Cons**
• 80% profit split
• Complex plans
• Monthly fees on some
""")

    await send_long_message(futures, """
## ⚫ TAKE PROFIT TRADER

🔗 https://takeprofittrader.com/

**✅ Pros**
• Affordable pricing
• Simple evaluation
• Good support

**❌ Cons**
• Smaller community
• Limited scaling
""")

    await send_long_message(futures, """
## 🟣 UPROFIT

🔗 https://uprofit.com/

**✅ Pros**
• Low cost evaluations
• Simple rules
• Fast verification

**❌ Cons**
• Smaller accounts
• Less established
""")

    await send_long_message(futures, """
## 🟤 BULENOX

🔗 https://bulenox.com/

**✅ Pros**
• Competitive pricing
• Multiple account sizes
• Growing community

**❌ Cons**
• Newer to market
• Less track record
""")
    print('Created futures channel')
    
    # ==================== FOREX ====================
    forex = await guild.create_text_channel(name='💱│forex-prop-firms', category=cat)
    
    await send_long_message(forex, """
# 💱 FOREX PROP FIRMS

*For trading currency pairs, indices, and commodities*
""")

    await send_long_message(forex, """
## 🟣 FTMO

🔗 https://ftmo.com/

**✅ Pros**
• Most trusted globally
• One-time fee (no monthly)
• Free retry on profit rules
• Scaling to $2M+
• Excellent support

**❌ Cons**
• Two-phase evaluation
• 10% target challenging
• 30-day time limit
• Strict 5% daily loss
""")

    await send_long_message(forex, """
## 🟡 THE 5%ERS

🔗 https://the5ers.com/

**✅ Pros**
• Instant funding option
• Scale to $4M
• Low cost entry
• Weekend holding allowed

**❌ Cons**
• Lower starting split (50%)
• Small initial accounts
• Complex options
""")

    await send_long_message(forex, """
## 🟤 FUNDEDNEXT

🔗 https://fundednext.com/

**✅ Pros**
• Up to 90% profit split
• Express model available
• Crypto trading allowed

**❌ Cons**
• Many options confusing
• Newer company
• Strategy restrictions
""")

    await send_long_message(forex, """
## ⚫ THE FUNDED TRADER

🔗 https://thefundedtraderprogram.com/

**✅ Pros**
• Up to $400K accounts
• Multiple challenge types
• Active community

**❌ Cons**
• Options confusing
• Rule changes occur
• Withdrawal delays
""")

    await send_long_message(forex, """
## 🔵 FUNDING PIPS

🔗 https://fundingpips.com/

**✅ Pros**
• Competitive pricing
• Good profit split
• Growing reputation

**❌ Cons**
• Newer company
• Less track record
""")
    print('Created forex channel')
    
    # ==================== CRYPTO ====================
    crypto = await guild.create_text_channel(name='🪙│crypto-prop-firms', category=cat)
    
    await send_long_message(crypto, """
# 🪙 CRYPTO PROP FIRMS

*Prop firms that offer cryptocurrency trading*

⚠️ **IMPORTANT:** Crypto prop firms are newer and less regulated. Rules change often. Do thorough research.
""")

    await send_long_message(crypto, """
## 🟣 FTMO (Crypto Option)

🔗 https://ftmo.com/

**✅ Pros**
• Most trusted overall
• Crypto + other markets
• Reliable payouts

**❌ Cons**
• Crypto secondary
• Strict rules
• Limited pairs
""")

    await send_long_message(crypto, """
## 🟤 FUNDEDNEXT (Crypto Option)

🔗 https://fundednext.com/

**✅ Pros**
• Crypto trading available
• Multiple evaluation types
• Up to 90% split

**❌ Cons**
• Newer company
• Rules may change
""")

    await send_long_message(crypto, """
## 🔵 MYFUNDEDFX

🔗 https://myfundedfx.com/

**✅ Pros**
• Crypto pairs available
• Growing community

**❌ Cons**
• Less established
• Limited crypto focus

*Stick with established firms that offer crypto as an additional market.*
""")
    print('Created crypto channel')
    
    print('\n✅ Prop Firms category created successfully!')
    
    await client.close()

client.run(TOKEN)

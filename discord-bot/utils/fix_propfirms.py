"""
QuoTrading Discord - Fix Prop Firms Education Only
"""

import discord
import asyncio
import json
import os

TOKEN = None
try:
    config_path = os.path.join(os.path.dirname(__file__), 'config.json')
    with open(config_path, 'r') as f:
        config = json.load(f)
    TOKEN = config.get('bot_token')
except:
    pass

if not TOKEN:
    raise ValueError("No bot token")

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
    print(f'Connected as {client.user}')
    guild = client.guilds[0]
    print(f'Server: {guild.name}')
    
    # Delete old Prop Firms category
    for cat in guild.categories:
        if 'prop firm' in cat.name.lower():
            print(f'Deleting category: {cat.name}')
            for ch in cat.channels:
                await ch.delete()
                await asyncio.sleep(0.3)
            await cat.delete()
            print('Deleted')
    
    await asyncio.sleep(1)
    
    # Create new category with aesthetics
    cat = await guild.create_category(name='『 Prop Firms 』')
    print('Created category')
    
    # EDUCATION - Pure education, no external links
    edu = await guild.create_text_channel(name='📚│prop-firm-education', category=cat)
    
    await send_msg(edu, """
# 🏦 What is a Proprietary Trading Firm?

A **Proprietary Trading Firm (Prop Firm)** is a company that provides traders with capital to trade financial markets. Instead of trading with your own money, you trade with theirs and share the profits.

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

**The Business Model:**
The prop firm takes on the risk by providing capital, while you provide the trading skill. When you profit, you keep the majority (80-90%), and they take a small cut.

**Why They Exist:**
• They can't trade every market themselves
• Skilled traders exist who don't have capital
• They profit from successful traders
• It's a scalable business model for them
""")

    await send_msg(edu, """
# 💰 How Does It Work?

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

**Step 1: Purchase an Evaluation**
You pay a one-time or monthly fee (typically $50-$500) to attempt their trading challenge.

**Step 2: Pass the Challenge**
Trade a demo account and hit their profit target while staying within risk rules. This proves you can trade profitably.

**Step 3: Get Funded**
Once you pass, you receive a funded account with $10,000 to $400,000+ in trading capital.

**Step 4: Profit Split**
Trade the funded account and keep 80-90% of all profits you make. They take a small percentage.
""")

    await send_msg(edu, """
# 🎯 Understanding the Evaluation Process

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

**Phase 1: The Challenge**
• Reach a profit target (usually 8-10%)
• Stay within daily loss limits (4-5%)
• Stay within maximum drawdown (8-10%)
• Trade for minimum number of days (some firms)
• No time limit on most firms

**Phase 2: Verification (some firms only)**
• Lower profit target (usually 5%)
• Same risk management rules apply
• Proves Phase 1 wasn't just luck
• Usually faster to complete

**Funded Account**
• Trade with real capital from the firm
• Follow the same risk rules
• Withdraw profits on their schedule (weekly/bi-weekly)
• Some firms offer scaling to larger accounts
""")

    await send_msg(edu, """
# 📊 Key Terms You Need to Know

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

**Drawdown**
The maximum amount your account can decline before you fail. If your account drops below this level, you're out.

**Trailing Drawdown**
A drawdown that moves up as your account grows. Example: Start at $50,000 with $2,500 drawdown. If you grow to $52,000, your minimum is now $49,500.

**Static Drawdown**
A fixed drawdown from your starting balance that doesn't change.

**EOD (End of Day) Drawdown**
Drawdown calculated only at market close, not during the trading session.

**Daily Loss Limit**
The maximum amount you can lose in a single trading day.

**Profit Target**
The amount of profit you need to reach to pass the evaluation.

**Profit Split**
The percentage of profits you keep (usually 80-90%).

**Scaling Plan**
A program to increase your account size as you prove consistency.
""")

    await send_msg(edu, """
# ⚠️ Common Reasons Traders Fail

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

**1. Trading Too Large**
Using position sizes that are too big for the drawdown limits. One bad trade wipes you out.

**2. Revenge Trading**
After a loss, trying to make it back quickly by overtrading or increasing size.

**3. Ignoring the Rules**
Trading during restricted hours, holding over weekends when not allowed, etc.

**4. Impatience**
Forcing trades to hit the profit target faster instead of waiting for quality setups.

**5. Not Understanding Trailing Drawdown**
Making profits, then losing it all because the trailing drawdown caught up.

**6. Overleveraging**
Taking maximum position sizes without room for the trade to breathe.
""")

    await send_msg(edu, """
# 🛡️ Tips for Passing Your Evaluation

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

**1. Trade Your Normal Strategy**
Don't change what works just because it's an evaluation.

**2. Risk Management First**
Protect your drawdown at all costs. You can make more money, but hitting drawdown is game over.

**3. Track Every Trade**
Keep a journal. Know why you entered and exited every trade.

**4. Don't Rush**
Most evaluations have no time limit. Take your time and wait for high-quality setups.

**5. Understand ALL the Rules**
Read the fine print. Know exactly what's allowed and what isn't before you start.

**6. Start Conservative**
Use smaller position sizes until you're comfortable and have some profit buffer.

**7. Treat It Like Real Money**
Because soon it will be. Build good habits now.
""")

    await send_msg(edu, """
# 💵 Understanding Profit Splits

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

**Common Profit Split Arrangements:**

**80/20 Split**
You keep 80% of profits, firm keeps 20%
Example: $10,000 profit = $8,000 for you

**90/10 Split**
You keep 90% of profits, firm keeps 10%
Example: $10,000 profit = $9,000 for you

**100% First $X**
Some firms let you keep 100% of your first $10K-$25K in profits, then switch to 90/10

**Scaling Bonuses**
Some firms increase your split as you prove consistency (start at 80%, grow to 90%)

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

*Check the channels below for specific prop firm details*
""")
    print('Created education')
    
    # FUTURES
    futures = await guild.create_text_channel(name='📈│futures-prop-firms', category=cat)
    
    await send_msg(futures, """
# 📈 FUTURES PROP FIRMS

*For trading ES, NQ, CL, GC and CME products*

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
""")

    await send_msg(futures, """
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

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
""")

    await send_msg(futures, """
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

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
""")

    await send_msg(futures, """
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

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
""")

    await send_msg(futures, """
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

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
""")

    await send_msg(futures, """
## ⚫ TAKE PROFIT TRADER

🔗 https://takeprofittrader.com/

**✅ Pros**
• Affordable pricing
• Simple evaluation
• Good support

**❌ Cons**
• Smaller community
• Limited scaling

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
""")

    await send_msg(futures, """
## 🟣 UPROFIT

🔗 https://uprofit.com/

**✅ Pros**
• Low cost evaluations
• Simple rules
• Fast verification

**❌ Cons**
• Smaller accounts
• Less established

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
""")

    await send_msg(futures, """
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
    print('Created futures')
    
    # FOREX
    forex = await guild.create_text_channel(name='💱│forex-prop-firms', category=cat)
    
    await send_msg(forex, """
# 💱 FOREX PROP FIRMS

*For trading currency pairs, indices, and commodities*

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
""")

    await send_msg(forex, """
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

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
""")

    await send_msg(forex, """
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

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
""")

    await send_msg(forex, """
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

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
""")

    await send_msg(forex, """
## ⚫ THE FUNDED TRADER

🔗 https://thefundedtraderprogram.com/

**✅ Pros**
• Up to $400K accounts
• Multiple challenge types
• Active community

**❌ Cons**
• Options confusing
• Rule changes occur
• Withdrawal delays reported

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
""")

    await send_msg(forex, """
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
    print('Created forex')
    
    # CRYPTO
    crypto = await guild.create_text_channel(name='🪙│crypto-prop-firms', category=cat)
    
    await send_msg(crypto, """
# 🪙 CRYPTO PROP FIRMS

*Prop firms that offer cryptocurrency trading*

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

⚠️ **Warning:** Crypto prop firms are newer and less regulated. Rules change often. Do thorough research before committing.

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
""")

    await send_msg(crypto, """
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

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
""")

    await send_msg(crypto, """
## 🟤 FUNDEDNEXT (Crypto Option)

🔗 https://fundednext.com/

**✅ Pros**
• Crypto trading available
• Multiple evaluation types
• Up to 90% split

**❌ Cons**
• Newer company
• Rules may change

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
""")

    await send_msg(crypto, """
## 🔵 MYFUNDEDFX

🔗 https://myfundedfx.com/

**✅ Pros**
• Crypto pairs available
• Growing community

**❌ Cons**
• Less established
• Limited crypto focus

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

*Recommendation: Stick with established firms that offer crypto as an additional market.*
""")
    print('Created crypto')
    
    print('Done!')
    await client.close()

client.run(TOKEN)

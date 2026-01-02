"""
Discord Server Setup Script for QuoTrading
Automatically creates server structure with channels, categories, and roles.
Features: Embed-style ticket system with button
"""

import discord
from discord.ext import commands
from discord import app_commands
from discord.ui import Button, View
import asyncio
import json
import os

# Load token from config
config_path = os.path.join(os.path.dirname(__file__), 'config.json')
with open(config_path, 'r', encoding='utf-8') as f:
    config = json.load(f)

TOKEN = config['bot_token']

# Bot setup with required intents
intents = discord.Intents.default()
intents.guilds = True
intents.guild_messages = True
bot = commands.Bot(command_prefix='!', intents=intents)


# ══════════════════════════════════════════════════════════════════════════════
# TICKET SYSTEM WITH BUTTON
# ══════════════════════════════════════════════════════════════════════════════

class TicketButton(View):
    """Persistent button for creating tickets."""
    
    def __init__(self):
        super().__init__(timeout=None)  # Persistent view
    
    @discord.ui.button(label="Create ticket", style=discord.ButtonStyle.blurple, emoji="📩", custom_id="create_ticket_btn")
    async def create_ticket_button(self, interaction: discord.Interaction, button: Button):
        guild = interaction.guild
        user = interaction.user
        
        # Use the Support category for tickets (Option B)
        support_cat = discord.utils.get(guild.categories, name='『 Support 』')
        if not support_cat:
            # Fallback - create Support category if it doesn't exist
            support_cat = await guild.create_category(name='『 Support 』', position=0)
        
        # Check if user already has an open ticket
        existing = discord.utils.get(guild.text_channels, name=f'ticket-{user.name.lower()}')
        if existing:
            await interaction.response.send_message(
                f'❌ You already have an open ticket: {existing.mention}', 
                ephemeral=True
            )
            return
        
        # Create private ticket channel
        overwrites = {
            guild.default_role: discord.PermissionOverwrite(read_messages=False),
            user: discord.PermissionOverwrite(read_messages=True, send_messages=True),
            guild.me: discord.PermissionOverwrite(read_messages=True, send_messages=True)
        }
        
        # Add admin/mod roles if they exist
        for role_name in ['Admin', 'Moderator', 'Support', 'Staff']:
            role = discord.utils.get(guild.roles, name=role_name)
            if role:
                overwrites[role] = discord.PermissionOverwrite(read_messages=True, send_messages=True)
        
        ticket_channel = await guild.create_text_channel(
            name=f'ticket-{user.name.lower()}',
            category=support_cat,
            overwrites=overwrites,
            topic=f'Support ticket for {user.name}'
        )
        
        # Create close button for the ticket
        close_view = CloseTicketView()
        
        # Create embed for ticket welcome
        ticket_embed = discord.Embed(
            title="🎫 Support Ticket",
            description=f"Welcome {user.mention}!\n\nA staff member will assist you shortly.\n\n**Please describe your issue below.**",
            color=discord.Color.green()
        )
        ticket_embed.set_footer(text="QuoTrading Support")
        
        await ticket_channel.send(embed=ticket_embed, view=close_view)
        
        await interaction.response.send_message(
            f'✅ Ticket created! Go to {ticket_channel.mention}', 
            ephemeral=True
        )


class CloseTicketView(View):
    """Button to close a ticket."""
    
    def __init__(self):
        super().__init__(timeout=None)
    
    @discord.ui.button(label="Close Ticket", style=discord.ButtonStyle.red, emoji="🔒", custom_id="close_ticket_btn")
    async def close_ticket_button(self, interaction: discord.Interaction, button: Button):
        channel = interaction.channel
        
        if not channel.name.startswith('ticket-'):
            await interaction.response.send_message('❌ This is not a ticket channel!', ephemeral=True)
            return
        
        await interaction.response.send_message('🔒 Closing ticket in 5 seconds...')
        await asyncio.sleep(5)
        await channel.delete()


# ══════════════════════════════════════════════════════════════════════════════
# CHANNEL CONTENT
# ══════════════════════════════════════════════════════════════════════════════

DISCLAIMER_TEXT = """# ⚠️ DISCLAIMER ⚠️

**This is not investment advice.** Information provided by QuoTrading is for **educational purposes only** and should not be used to make investment decisions.

QuoTrading accepts **no liability** for any loss arising from use of information found in this server.

**You bear full responsibility for your own investment research and decisions.**

---

**No Professional Licensing:** QuoTrading is **not registered** as a securities broker-dealer or investment adviser with the SEC or any regulatory authority. We are **not licensed** to provide investment advice.

**Risk Warning:** Trading stocks, options, ETFs, and futures carries substantial risk. **You can lose more than your account balance.**

**Your Responsibility:** Trade cautiously and consult qualified financial, legal, and tax advisors before investing.

---

**By remaining in this server, you agree to this disclaimer.**
"""

INTRODUCTION_TEXT = """# 👋 Welcome to QuoTrading!
Welcome to the official **QuoTrading** community! We're excited to have you here.

## 🤖 What is QuoTrading?
QuoTrading is your community for trading signals, AI automation, and market analysis.

## 🎯 What We Offer
📊 **Options & Futures Signals** - Real-time trade alerts
💹 **Crypto Signals** - Stay ahead in the crypto markets
💱 **Forex Signals** - Trade global currencies with confidence
🏀 **Sports Betting Picks** - Expert picks for major sports events
🤖 **AI Trade Automation** - Hands-free trading
🔔 **Real-Time Alerts** - Get notified instantly

## 🚀 Getting Started
1. Read the **#disclaimer** and **#server-rules**
2. Check out **#upgrade-premium** for membership options
3. Join **#general-chat** to meet the community
4. Need help? Open a **support ticket**!

Thanks for being here! Let's win together. 🚀
"""


# Rainbow divider - thicker rainbow bar
RAINBOW_LINE_PATH = os.path.join(os.path.dirname(__file__), 'line-rainbow.gif')
# Thick rainbow bar from Tenor (if you want a thicker bar)
RAINBOW_BAR_URL = 'https://media.tenor.com/F3RkSbqBS4oAAAAi/rainbow.gif'


async def setup_introduction_channel(guild: discord.Guild, category: discord.CategoryChannel):
    """Create introduction channel with rainbow dividers."""
    
    channel_name = '📌│introduction'
    existing = discord.utils.get(guild.text_channels, name=channel_name)
    
    if existing:
        print(f'   ⚠️ #{channel_name} already exists, updating content...')
        await existing.purge(limit=20)
        channel = existing
    else:
        overwrites = {
            guild.default_role: discord.PermissionOverwrite(
                read_messages=True,
                send_messages=False,
                add_reactions=True
            )
        }
        channel = await guild.create_text_channel(
            name=channel_name,
            category=category,
            overwrites=overwrites
        )
        print(f'   ✅ Created #{channel_name}')
    
    # Rainbow divider at top
    if os.path.exists(RAINBOW_LINE_PATH):
        file1 = discord.File(RAINBOW_LINE_PATH, filename="rainbow.gif")
        await channel.send(file=file1)
    
    # Send plain text intro
    await channel.send(INTRODUCTION_TEXT)
    
    # Rainbow divider at bottom
    if os.path.exists(RAINBOW_LINE_PATH):
        file2 = discord.File(RAINBOW_LINE_PATH, filename="rainbow.gif")
        await channel.send(file=file2)
    
    print('   ✅ Created introduction with rainbow dividers!')
    return channel

SERVER_RULES_TEXT = """# 📜 Server Rules

**1. Discord's Terms First** — Discord's Terms of Service and Privacy Policy take priority. Review them at discord.com/terms

**2. Respect Everyone** — No harassment, bullying, or targeting other members. Keep it civil.

**3. No Drama** — Don't start or engage in drama. This is a positive community.

**4. Handle Issues Privately** — If you have a problem with someone, use the block feature and report to staff with proof.

**5. Keep It Clean** — No NSFW, racist, violent, or drug-related content. This includes avatars, names, and links. If you're unsure, don't post it.

**6. No Slurs or Derogatory Language** — Zero tolerance for offensive terms in messages, names, reactions, or anywhere else.

**7. No Promotion** — No referral links, server invites, or social media plugs without permission.

**8. No Pumping** — Promoting stocks/coins to inflate price will get you muted immediately.

**9. See Something? Say Something** — Help us keep the community safe by reporting issues.

**10. Use the Right Channels** — Post content in the appropriate channel to keep things organized.

---
**Breaking rules may result in warnings, mutes, or bans.**
"""

ANNOUNCEMENTS_TEXT = """# 📢 Announcements
This is where we post important updates, news, and server announcements.
🔔 Turn on notifications to stay updated!
"""

UPGRADE_PREMIUM_TEXT = """
# ⭐ Upgrade to Premium

Unlock the full QuoTrading experience!

---

## 💎 Premium Benefits

• **Trade Signals** - Access to all analyst trade signals
• **AI Trade Automation** - Let AI execute trades automatically
• **Priority Support** - Get help faster
• **Exclusive Channels** - Access premium-only discussions

---

## 💰 How to Upgrade

Contact an admin or visit our website to upgrade your membership.

Questions? Open a support ticket!
"""

OPTIONS_EDUCATION_TEXT = """# 📊 Options Education

## What are Options?
Options are financial contracts that give you the **right (but not obligation)** to buy or sell an underlying asset at a predetermined price before a specific date. They're powerful tools that let you profit from price movements, hedge existing positions, or generate income.

---

## 📈 CALLS vs 📉 PUTS

**CALL OPTIONS** — Bullish Bets
• Gives you the right to BUY at the strike price
• You profit when the stock price rises ABOVE your strike
• Maximum loss = premium paid (limited risk)
• Maximum gain = unlimited (stock can keep rising)

**PUT OPTIONS** — Bearish Bets
• Gives you the right to SELL at the strike price
• You profit when the stock price falls BELOW your strike
• Maximum loss = premium paid (limited risk)
• Maximum gain = strike price - premium (stock can go to $0)

---

## 🔑 Essential Terminology

**Strike Price** — The price at which you can buy/sell the underlying
**Expiration Date** — When your contract expires (becomes worthless if OTM)
**Premium** — The price you pay to buy the option contract
**Underlying** — The stock/ETF the option is based on (SPY, AAPL, QQQ, etc.)

**ITM (In The Money)** — Option has intrinsic value
• Call: Stock price > Strike price
• Put: Stock price < Strike price

**ATM (At The Money)** — Strike price ≈ Current stock price
**OTM (Out The Money)** — Option has no intrinsic value (only time value)

**0DTE** — Zero Days To Expiration (expires same day, extremely risky)

---

## 📐 The Greeks (Risk Metrics)

**Delta (Δ)** — How much option price moves per $1 stock move
• Calls: 0 to 1.0 | Puts: -1.0 to 0
• ATM options ≈ 0.50 delta

**Theta (Θ)** — Time decay per day
• Options lose value as expiration approaches
• Accelerates in final weeks

**Gamma (Γ)** — Rate of delta change
• Highest for ATM options near expiration

**Vega (V)** — Sensitivity to volatility changes
**IV (Implied Volatility)** — Market's expectation of future movement

---

## 🎯 Popular Strategies

**Long Call** — Buy call, profit if stock rises
**Long Put** — Buy put, profit if stock falls
**Covered Call** — Own stock + sell call (income strategy)
**Cash-Secured Put** — Sell put backed by cash (income + buy lower)
**Vertical Spread** — Buy + sell same expiration, different strikes
**Iron Condor** — Profit if stock stays in a range

---

## ⏱️ Trading Styles

**Day Trading** — Open and close same day
• Uses 0DTE or weekly options
• Fast-paced, requires discipline

**Swing Trading** — Hold for days to weeks
• Uses 2-6 week expiration
• Captures larger moves

**Scalping** — Quick trades for small profits
• In and out within minutes
• High frequency, small gains

---

## ⚠️ Risk Management

• Never risk more than 1-2% of account per trade
• Use stop losses (mental or hard stops)
• Understand max loss BEFORE entering
• Avoid trading during high IV events (earnings) unless intentional
• Start with paper trading until consistent

https://youtu.be/7PM4rNDr4oI

https://youtu.be/4HMm6mBvGKE

https://youtu.be/SD7sw0bf1ms
"""

RESOURCES_TEXT = """# 📚 Learning Resources

**🎥 YouTube Tutorials**
• [Option Alpha](https://youtube.com/@OptionAlpha) — Options education
• [InTheMoney](https://youtube.com/@InTheMoney) — Beginner-friendly
• [tastytrade](https://youtube.com/@tastyliveshow) — Live trading

**📖 Learning Sites**
• [Investopedia](https://investopedia.com) — Dictionary & guides
• [BabyPips](https://babypips.com) — Great for beginners
• [CME Group](https://cmegroup.com/education) — Futures basics

**🎓 Free Broker Education**
• [TD Ameritrade](https://tdameritrade.com/education)
• [Fidelity Learning](https://fidelity.com/learning-center)
"""

CRYPTO_TEXT = """# 💎 Crypto Education

## What is Cryptocurrency?
Cryptocurrency is **digital money** that operates on blockchain technology — a decentralized, secure, and transparent ledger. Unlike traditional currency, crypto isn't controlled by any government or bank. Bitcoin (BTC) was the first, launched in 2009, and now thousands of cryptocurrencies exist.

---

## 🔗 How Blockchain Works

**Blockchain** = A chain of "blocks" containing transaction data
• Every transaction is verified by a network of computers (nodes)
• Once verified, it's added to the blockchain permanently
• Cannot be altered or deleted (immutable)
• Completely transparent — anyone can view transactions

**Mining** — Computers solving complex puzzles to verify transactions
**Staking** — Locking up coins to help validate transactions (earn rewards)

---

## 💰 Major Cryptocurrencies

**Bitcoin (BTC)** — The original, "digital gold," store of value
**Ethereum (ETH)** — Smart contracts, DeFi, NFTs platform
**Solana (SOL)** — Fast, low-fee transactions
**XRP (Ripple)** — Cross-border payments
**Cardano (ADA)** — Academic, research-driven blockchain
**Dogecoin (DOGE)** — Meme coin turned mainstream

---

## 🔑 Essential Terminology

**Wallet** — Where you store your crypto
• **Hot Wallet** — Online (convenient, less secure)
• **Cold Wallet** — Offline hardware device (most secure)

**Exchange** — Platform to buy/sell crypto
**Private Key** — Your secret password (NEVER share this)
**Public Address** — Your wallet address (safe to share for receiving)
**Gas Fees** — Transaction fees on the blockchain
**Market Cap** — Total value of all coins in circulation
**HODL** — "Hold On for Dear Life" (long-term holding strategy)

---

## 📊 Trading Concepts

**Spot Trading** — Buy/sell crypto at current market price
**Margin Trading** — Trade with borrowed funds (risky)
**Futures** — Contracts to buy/sell at future price
**DeFi (Decentralized Finance)** — Financial services without banks
**Yield Farming** — Earning interest by providing liquidity
**NFTs** — Non-Fungible Tokens (unique digital assets)

---

## 📈 Market Analysis

**DYOR** — Do Your Own Research (essential!)
**Whitepaper** — Project's technical document (read before investing)
**Tokenomics** — Supply, distribution, and economics of a coin
**Volume** — How much is being traded
**ATH** — All-Time High price
**Bear Market** — Prices falling | **Bull Market** — Prices rising

---

## ⚠️ Risk Management

• **Only invest what you can afford to lose**
• Crypto is EXTREMELY volatile (50%+ swings are normal)
• Use hardware wallets for long-term storage
• Enable 2FA on all exchange accounts
• Beware of scams, phishing, and "guaranteed returns"
• Diversify — don't put everything in one coin

https://youtu.be/rYQgy8QDEBI

https://youtu.be/Yb6825iv0Vk

https://youtu.be/pkrurBIgIr8
"""

FUTURES_TEXT = """# 📈 Futures Education

## What are Futures?
Futures are **legally binding contracts** to buy or sell an asset at a predetermined price on a specific future date. Unlike options, you're obligated to fulfill the contract (though most traders close before expiration). They're the professional way to trade market indices, commodities, and more.

---

## 🔄 How Futures Work

• You agree to buy/sell at a future price
• Contracts expire quarterly (March, June, September, December)
• Highly leveraged — small price moves = large gains/losses
• Can go **long** (bullish) or **short** (bearish) equally easily
• Settled in cash — no actual delivery of the underlying

---

## 📊 Popular Futures Contracts

**Index Futures:**
| Symbol | Name | Point Value | Tick Size | Tick Value |
|--------|------|-------------|-----------|------------|
| ES | E-mini S&P 500 | $50 | 0.25 | $12.50 |
| MES | Micro S&P 500 | $5 | 0.25 | $1.25 |
| NQ | E-mini Nasdaq | $20 | 0.25 | $5.00 |
| MNQ | Micro Nasdaq | $2 | 0.25 | $0.50 |

**Other Popular:**
• **CL** — Crude Oil ($1000/point)
• **GC** — Gold ($100/point)
• **ZB** — Treasury Bonds

---

## 🔑 Essential Terminology

**Tick** — Smallest price increment (0.25 points for ES/MES)
**Point** — 4 ticks = 1 full point
**Contract Size** — Dollar value controlled (ES = ~$250,000 notional)
**Margin** — Collateral required to open position
• **Initial Margin** — Amount to open
• **Maintenance Margin** — Minimum to keep open
**Leverage** — Controlling large value with small capital
**Mark-to-Market** — Daily profit/loss settlement

---

## ⏰ Trading Hours

Futures trade nearly 24 hours:
• **Sunday 6PM ET** → **Friday 5PM ET**
• Brief daily pause: 5PM - 6PM ET
• **RTH (Regular Trading Hours)**: 9:30 AM - 4:00 PM ET
• Most volatility during RTH and market open/close

---

## 🎯 Trading Strategies

**Trend Following** — Trade in direction of the trend
**Mean Reversion** — Fade extreme moves back to average
**Breakout Trading** — Enter on key level breaks
**Scalping** — Quick in/out for small profits
**Swing Trading** — Hold for hours to days

---

## ⚠️ Risk Management

• Futures are **heavily leveraged** — you can lose more than your deposit
• Always use stop losses
• Start with **MICRO contracts** (MES, MNQ) to learn
• Never risk more than 1-2% per trade
• Understand margin requirements before trading
• Practice on a simulator FIRST

https://youtu.be/Uj30y2DlypA

https://youtu.be/5uSklnJeR5k

https://youtu.be/Eebx6eGMc_A
"""

PATTERNS_TEXT = """# 📐 Chart Patterns Education

## Welcome to Chart Pattern Mastery!

Chart patterns are visual formations on price charts that signal potential future price movements. They're created by the collective psychology of buyers and sellers fighting for control.

**In this channel you'll learn:**
• Reversal Patterns (Double Top/Bottom, Head & Shoulders)
• Continuation Patterns (Flags, Triangles, Rectangles)
• Candlestick Patterns (Hammer, Doji, Engulfing)
• Entry, Stop Loss & Target strategies for each pattern

⬇️ **Scroll down to see each pattern with visual charts** ⬇️
"""

STRATEGIES_TEXT = """# 📊 Trading Strategy & Indicators Education

## Welcome to Trading Mastery!

This channel covers everything you need to understand **indicators, strategies, and trading styles**. Master these tools to make informed trading decisions.

**What you'll learn:**
• Technical Indicators (Moving Averages, RSI, MACD, etc.)
• Trading Styles (Scalping, Day Trading, Swing Trading)
• Strategy Concepts (Trend Following, Breakouts, Mean Reversion)
• Risk Management & Position Sizing

⬇️ **Scroll down to learn each indicator and strategy** ⬇️
"""

FOREX_TEXT = """# 💱 Forex Education

## What is Forex?
Forex (Foreign Exchange) is the **global marketplace for trading currencies**. It's the largest financial market in the world with over $7.5 TRILLION traded daily. Traders profit from exchange rate fluctuations between currency pairs.

---

## 🌍 How Forex Works

• Currencies are traded in **pairs** (EUR/USD, GBP/JPY, etc.)
• The first currency is the **BASE**, the second is the **QUOTE**
• You're always buying one currency while selling another
• Market is open **24 hours a day, 5 days a week**
• Decentralized — no central exchange

---

## 💰 Major Currency Pairs

**Majors** (Most traded, tightest spreads):
• **EUR/USD** — Euro / US Dollar (most traded pair)
• **GBP/USD** — British Pound / US Dollar
• **USD/JPY** — US Dollar / Japanese Yen
• **USD/CHF** — US Dollar / Swiss Franc

**Minors** (No USD):
• EUR/GBP, EUR/JPY, GBP/JPY

**Exotics** (Emerging markets):
• USD/ZAR, USD/TRY, USD/MXN (higher volatility, wider spreads)

---

## 🔑 Essential Terminology

**Pip** — Smallest price movement (0.0001 for most pairs)
**Lot Size** — Trade size
• Standard Lot = 100,000 units
• Mini Lot = 10,000 units
• Micro Lot = 1,000 units

**Spread** — Difference between bid and ask price (broker's fee)
**Leverage** — Borrowed capital (50:1, 100:1, etc.)
**Margin** — Collateral required to open position
**Long** — Buying base currency | **Short** — Selling base currency

---

## ⏰ Trading Sessions

**Sydney** — 5PM - 2AM ET (low volatility)
**Tokyo** — 7PM - 4AM ET (JPY pairs active)
**London** — 3AM - 12PM ET (highest volume)
**New York** — 8AM - 5PM ET (USD pairs active)

**Best times**: London-NY overlap (8AM - 12PM ET)

---

## 📊 Analysis Types

**Technical Analysis** — Charts, patterns, indicators
• Support/Resistance, Trendlines, Moving Averages
• RSI, MACD, Bollinger Bands

**Fundamental Analysis** — Economic data, news
• Interest rates, GDP, Employment data
• Central bank decisions (Fed, ECB, BOE)

---

## 🎯 Trading Strategies

**Scalping** — Seconds to minutes, many small trades
**Day Trading** — Open and close within same day
**Swing Trading** — Hold for days to weeks
**Position Trading** — Hold for weeks to months

---

## ⚠️ Risk Management

• High leverage = high risk (can lose more than deposit)
• Use stop losses on EVERY trade
• Risk only 1-2% per trade
• Avoid trading during major news releases unless experienced
• Demo trade until consistently profitable

https://youtu.be/_-hkVWweDmM

https://youtu.be/c1fwIaOUZzI

https://youtu.be/zUm3LraiZsI
"""

SPORTS_BETTING_TEXT = """# 🏈 Sports Betting Education

## What is Sports Betting?
Sports betting is wagering money on the outcome of sporting events. It's legal in many states/countries and can be approached analytically for long-term profitability. Smart bettors treat it like investing — data-driven decisions, bankroll management, and discipline.

---

## 📊 Types of Bets

**Moneyline** — Simply pick the winner
• Favorite: -150 means bet $150 to win $100
• Underdog: +200 means bet $100 to win $200

**Point Spread** — Bet on margin of victory
• Team -7.5 must win by 8+ points
• Team +7.5 can lose by up to 7 and still cover

**Over/Under (Totals)** — Bet on combined score
• Over 45.5 = combined score of 46+
• Under 45.5 = combined score of 45 or less

**Parlays** — Multiple bets combined (higher payout, lower probability)
**Props** — Specific player/game stats (yards, points, etc.)
**Futures** — Season-long bets (championship, MVP, etc.)
**Live Betting** — Bet during the game as odds change

---

## 🔑 Understanding Odds

**American Odds:**
• **-110** = Bet $110 to win $100 (standard juice)
• **+150** = Bet $100 to win $150
• **-200** = Bet $200 to win $100 (heavy favorite)

**Implied Probability:**
• -110 = 52.4% implied probability
• +200 = 33.3% implied probability
• +100 = 50% (even odds)

**Juice/Vig** — The sportsbook's commission (usually -110 on both sides)

---

## 📈 Key Concepts

**Line Shopping** — Compare odds across multiple sportsbooks
**Closing Line Value (CLV)** — Beat the closing line = long-term profit
**Expected Value (+EV)** — Only bet when odds are in your favor
**Sharp Money** — Professional bettors moving the line
**Public Money** — Recreational bettors (often wrong)

---

## 🎯 Betting Strategies

**Fade the Public** — Bet against heavy public favorites
**Follow Line Movement** — Track where sharp money is going
**Arbitrage** — Guarantee profit with conflicting odds (rare)
**Value Betting** — Find mispriced odds
**System Betting** — Use statistical models for edges

---

## 💰 Bankroll Management

**Unit Size** — Standard bet amount (1-3% of bankroll)
• $1000 bankroll → $10-$30 per bet

**Flat Betting** — Same amount every bet (safest)
**Kelly Criterion** — Size bets based on edge (advanced)

**Rules:**
• NEVER chase losses
• Stick to your unit size
• Track ALL bets in a spreadsheet
• Don't bet more than you can afford to lose

---

## ⚠️ Important Warnings

• Gambling can be addictive — set limits
• The house always has an edge on most bets
• Long-term profit requires discipline and data
• Avoid emotional betting (on your favorite team)
• Only bet with licensed, legal sportsbooks

https://youtu.be/OD7bIB_g8N0

https://youtu.be/D5E6V8ic5Vc

https://youtu.be/y7qhLHB9XHE
"""


# ══════════════════════════════════════════════════════════════════════════════
# BOT EVENTS
# ══════════════════════════════════════════════════════════════════════════════

@bot.event
async def on_ready():
    print(f'✅ Bot connected as {bot.user}')
    print(f'📊 Connected to {len(bot.guilds)} server(s)')
    
    # Register persistent views
    bot.add_view(TicketButton())
    bot.add_view(CloseTicketView())
    
    if len(bot.guilds) == 0:
        print('\n⚠️ Bot is not in any servers!')
        await bot.close()
        return
    
    guild = bot.guilds[0]
    print(f'\n🏠 Setting up server: {guild.name}')
    
    await setup_server(guild)
    
    print('\n✅ Server setup complete!')
    print('\n🤖 Bot is now running for ticket buttons...')
    # Keep running for button interactions


# ══════════════════════════════════════════════════════════════════════════════
# HELPER FUNCTIONS
# ══════════════════════════════════════════════════════════════════════════════

async def get_or_create_category(guild: discord.Guild, name: str, position: int = None):
    """Get existing category or create new one."""
    existing = discord.utils.get(guild.categories, name=name)
    if existing:
        print(f'   ⚠️ Category "{name}" already exists')
        if position is not None and existing.position != position:
            await existing.edit(position=position)
            print(f'   📍 Moved "{name}" to position {position}')
        return existing
    
    category = await guild.create_category(name=name, position=position)
    print(f'   ✅ Created category: {name}')
    return category


async def get_or_create_channel(guild: discord.Guild, name: str, category: discord.CategoryChannel, 
                                 content: str = None, read_only: bool = False):
    """Get existing channel or create new one with optional content."""
    existing = discord.utils.get(guild.text_channels, name=name)
    
    async def send_long_content(channel, text):
        """Split long content into multiple messages (Discord 2000 char limit)."""
        # Split by sections (---) to keep formatting clean
        sections = text.split('\n---\n')
        current_msg = ""
        
        for section in sections:
            # If adding this section would exceed limit, send current and start new
            if len(current_msg) + len(section) + 5 > 1900:  # 1900 for safety margin
                if current_msg.strip():
                    await channel.send(current_msg.strip())
                current_msg = section
            else:
                if current_msg:
                    current_msg += "\n---\n" + section
                else:
                    current_msg = section
        
        # Send remaining content
        if current_msg.strip():
            await channel.send(current_msg.strip())
    
    if existing:
        print(f'   ⚠️ #{name} already exists, updating...')
        if content:
            await existing.purge(limit=50)
            await send_long_content(existing, content)
        return existing
    
    if read_only:
        overwrites = {
            guild.default_role: discord.PermissionOverwrite(
                read_messages=True,
                send_messages=False,
                add_reactions=True
            )
        }
        channel = await guild.create_text_channel(
            name=name,
            category=category,
            overwrites=overwrites
        )
    else:
        channel = await guild.create_text_channel(
            name=name,
            category=category
        )
    
    print(f'   ✅ Created #{name}')
    
    if content:
        await send_long_content(channel, content)
    
    return channel


async def setup_ticket_channel(guild: discord.Guild, category: discord.CategoryChannel):
    """Set up the ticket channel with embed and button."""
    
    channel_name = '🎫│create-ticket'
    existing = discord.utils.get(guild.text_channels, name=channel_name)
    
    if existing:
        print(f'   ⚠️ #{channel_name} already exists, updating embed...')
        await existing.purge(limit=10)
        channel = existing
    else:
        channel = await guild.create_text_channel(
            name=channel_name,
            category=category
        )
        print(f'   ✅ Created #{channel_name}')
    
    # Get banner image path
    banner_path = os.path.join(os.path.dirname(__file__), 'quotrading_banner.png')
    
    # Create the ticket embed
    embed = discord.Embed(
        title="QuoTrading Member Support",
        description="To create a support ticket, click the button below and a dedicated staff member will assist you shortly.",
        color=discord.Color.purple()
    )
    
    # Set the banner image inside the embed (using attachment)
    if os.path.exists(banner_path):
        file = discord.File(banner_path, filename="banner.png")
        embed.set_image(url="attachment://banner.png")
        embed.set_footer(text="QuoTrading - Signals, Automation & Community")
        
        # Send embed with image and button
        view = TicketButton()
        await channel.send(file=file, embed=embed, view=view)
        print('   ✅ Sent embed with banner image')
    else:
        # Fallback without image
        embed.set_footer(text="QuoTrading - Signals, Automation & Community")
        view = TicketButton()
        await channel.send(embed=embed, view=view)
        print('   ⚠️ Banner image not found, sent embed without image')
    
    return channel


async def setup_server(guild: discord.Guild):
    """Set up the QuoTrading server structure."""
    
    # ══════════════════════════════════════════
    # CLEANUP: Remove duplicate categories first
    # ══════════════════════════════════════════
    print('\n🧹 Cleaning up duplicates...')
    
    # Remove ALL Tickets categories (they should be created dynamically when needed)
    tickets_cats = [c for c in guild.categories if 'Tickets' in c.name or 'ticket' in c.name.lower()]
    for cat in tickets_cats:
        try:
            # Delete all channels in the category first
            for channel in cat.channels:
                await channel.delete()
            await cat.delete()
            print(f'   🗑️ Removed duplicate: {cat.name}')
        except:
            pass
    
    # Remove duplicate Welcome/Support/Free Community (keep only the properly named ones)
    for cat_name in ['Welcome', 'Support', 'Free Community']:
        duplicates = [c for c in guild.categories if cat_name in c.name and c.name != f'『 {cat_name} 』']
        for cat in duplicates:
            try:
                for channel in cat.channels:
                    await channel.delete()
                await cat.delete()
                print(f'   🗑️ Removed duplicate: {cat.name}')
            except:
                pass
    
    # ══════════════════════════════════════════
    # CATEGORY 1: Support (VERY TOP)
    # ══════════════════════════════════════════
    print('\n📁 Creating Support category...')
    support_cat = await get_or_create_category(guild, '『 Support 』', position=0)
    
    await setup_ticket_channel(guild, support_cat)
    
    # ══════════════════════════════════════════
    # CATEGORY 2: Welcome
    # ══════════════════════════════════════════
    print('\n📁 Creating Welcome category...')
    welcome_cat = await get_or_create_category(guild, '『 Welcome 』', position=1)
    
    await setup_introduction_channel(guild, welcome_cat)  # With rainbow dividers!
    await get_or_create_channel(guild, '📢│announcements', welcome_cat, ANNOUNCEMENTS_TEXT, read_only=True)
    await get_or_create_channel(guild, '🔴│disclaimer', welcome_cat, DISCLAIMER_TEXT, read_only=True)
    await get_or_create_channel(guild, '📋│server-rules', welcome_cat, SERVER_RULES_TEXT, read_only=True)
    await get_or_create_channel(guild, '⭐│upgrade-premium', welcome_cat, UPGRADE_PREMIUM_TEXT, read_only=True)
    
    # ══════════════════════════════════════════
    # CATEGORY 3: Education (ABOVE Free Community)
    # ══════════════════════════════════════════
    print('\n📁 Creating Education category...')
    edu_cat = await get_or_create_category(guild, '『 Education 』', position=2)
    
    # Delete old education channels first (force fresh content)
    old_edu_channels = ['start-here', 'resources', 'trading-tips', 'chart-analysis', 
                        'options-101', 'crypto-basics', 'futures-101',
                        'options-education', 'crypto-education', 'futures-education',
                        'forex-education', 'sports-betting']
    for old_name in old_edu_channels:
        for ch in guild.text_channels:
            if old_name in ch.name:
                try:
                    await ch.delete()
                    print(f'   🗑️ Deleted #{ch.name}')
                except:
                    pass
    
    # Create fresh education channels
    await get_or_create_channel(guild, '📊│options-education', edu_cat, OPTIONS_EDUCATION_TEXT, read_only=True)
    await get_or_create_channel(guild, '💎│crypto-education', edu_cat, CRYPTO_TEXT, read_only=True)
    await get_or_create_channel(guild, '📈│futures-education', edu_cat, FUTURES_TEXT, read_only=True)
    await get_or_create_channel(guild, '💱│forex-education', edu_cat, FOREX_TEXT, read_only=True)
    await get_or_create_channel(guild, '📐│chart-patterns', edu_cat, PATTERNS_TEXT, read_only=True)
    await get_or_create_channel(guild, '🎯│trading-strategies', edu_cat, STRATEGIES_TEXT, read_only=True)
    
    # Send pattern images to chart-patterns channel
    patterns_channel = discord.utils.get(guild.text_channels, name='📐│chart-patterns')
    if patterns_channel:
        import os
        images_dir = os.path.join(os.path.dirname(__file__), 'images')
        
        # Double Top & Double Bottom
        img = os.path.join(images_dir, 'double_top_bottom.png')
        if os.path.exists(img):
            await patterns_channel.send("""**📈 DOUBLE TOP & DOUBLE BOTTOM**

**Double Top (Bearish Reversal)**
• Forms "M" shape with two peaks at same resistance level
• Indicates buyers failed twice to push higher
• Entry: Break below the neckline (middle trough)
• Stop Loss: Above the second peak
• Target: Height of pattern projected down from neckline

**Double Bottom (Bullish Reversal)**
• Forms "W" shape with two lows at same support level
• Indicates sellers failed twice to push lower
• Entry: Break above the neckline (middle peak)
• Stop Loss: Below the second trough
• Target: Height of pattern projected up from neckline""", file=discord.File(img))
        
        # Head and Shoulders
        img = os.path.join(images_dir, 'head_shoulders.png')
        if os.path.exists(img):
            await patterns_channel.send("""**👤 HEAD AND SHOULDERS**

**Head & Shoulders (Bearish Reversal)**
• Three peaks: left shoulder, higher head, right shoulder
• Neckline connects the two troughs between peaks
• Entry: Break below the neckline
• Stop Loss: Above the right shoulder
• Target: Distance from head to neckline, projected down
• More reliable with increasing volume on breakdown

**Inverse Head & Shoulders (Bullish Reversal)**
• Three troughs: left shoulder, lower head, right shoulder
• Entry: Break above the neckline
• Target: Distance from head to neckline, projected up""", file=discord.File(img))
        
        # Flags and Pennants
        img = os.path.join(images_dir, 'flag_pennant.png')
        if os.path.exists(img):
            await patterns_channel.send("""**🚩 FLAGS & PENNANTS**

**Bull Flag (Bullish Continuation)**
• Sharp move up (flagpole) followed by downward sloping consolidation
• Entry: Break above the upper trendline
• Target: Length of flagpole projected from breakout

**Bear Flag (Bearish Continuation)**
• Sharp move down followed by upward sloping consolidation
• Entry: Break below the lower trendline
• Target: Length of flagpole projected down

**Pennant (Continuation)**
• Small symmetrical triangle after sharp move
• Converging trendlines meet at a point
• Breaks in direction of prior trend
• Forms quickly (1-3 weeks typically)""", file=discord.File(img))
        
        # Triangle Patterns
        img = os.path.join(images_dir, 'triangle_patterns.png')
        if os.path.exists(img):
            await patterns_channel.send("""**🔺 TRIANGLE PATTERNS**

**Ascending Triangle (Bullish)**
• Flat resistance + rising support (higher lows)
• Buyers increasingly aggressive
• Entry: Break above flat resistance
• Target: Height of triangle projected up
• ~75% break upward historically

**Descending Triangle (Bearish)**
• Flat support + falling resistance (lower highs)
• Sellers increasingly aggressive
• Entry: Break below flat support
• Target: Height of triangle projected down

**Symmetrical Triangle (Neutral)**
• Converging trendlines with no flat edge
• Can break either direction - wait for confirmation
• Target: Widest part of triangle projected from breakout""", file=discord.File(img))
        
        # Rectangle and Wedge
        img = os.path.join(images_dir, 'rectangle_wedge.png')
        if os.path.exists(img):
            await patterns_channel.send("""**📊 RECTANGLE & WEDGE PATTERNS**

**Rectangle Pattern (Continuation)**
• Price moves sideways between parallel support and resistance
• Represents consolidation before trend continues
• Entry: Breakout in direction of prior trend
• Target: Height of rectangle projected from breakout
• Volume typically decreases during consolidation

**Rising Wedge (Bearish Reversal)**
• Both support and resistance lines slope upward but converge
• Price makes higher highs and higher lows, but momentum weakens
• Volume typically decreases as pattern develops
• Entry: Break below the lower trendline (support)
• Stop Loss: Above the most recent swing high
• Target: Height of the wedge projected down from breakdown
• Often appears after prolonged uptrends before major reversals

**Falling Wedge (Bullish Reversal)**
• Both support and resistance lines slope downward but converge
• Price makes lower highs and lower lows, but selling pressure weakens
• Volume typically decreases as pattern develops
• Entry: Break above the upper trendline (resistance)
• Stop Loss: Below the most recent swing low
• Target: Height of the wedge projected up from breakout
• Often appears after prolonged downtrends before major reversals""", file=discord.File(img))
        
        # Candlestick Patterns
        img = os.path.join(images_dir, 'candlestick_patterns.png')
        if os.path.exists(img):
            await patterns_channel.send("""**🕯️ CANDLESTICK PATTERNS**

**Bullish Reversal Candles:**
• **Hammer** — Long lower wick at bottom of downtrend, signals buyers stepping in
• **Morning Star** — Three candle pattern: down, small body, up = reversal confirmed
• **Bullish Engulfing** — Green candle completely engulfs prior red candle

**Bearish Reversal Candles:**
• **Shooting Star** — Long upper wick at top of uptrend, signals sellers stepping in
• **Evening Star** — Three candle pattern: up, small body, down = reversal confirmed
• **Bearish Engulfing** — Red candle completely engulfs prior green candle

**Indecision Candles:**
• **Doji** — Open equals close, signals potential reversal when at extremes
• **Spinning Top** — Small body with equal wicks, market undecided""", file=discord.File(img))
        
        # Pattern Quick Reference Summary
        await patterns_channel.send("""**📋 QUICK REFERENCE - ALL PATTERNS**

**🔻 BEARISH (Sell Signals):**
• Double Top (M shape) → Breakdown below neckline
• Head & Shoulders → Breakdown below neckline
• Rising Wedge → Breakdown below support
• Bear Flag → Breakdown below flag
• Descending Triangle → Breakdown below flat support
• Shooting Star / Evening Star candles

**🟢 BULLISH (Buy Signals):**
• Double Bottom (W shape) → Breakout above neckline
• Inverse Head & Shoulders → Breakout above neckline
• Falling Wedge → Breakout above resistance
• Bull Flag → Breakout above flag
• Ascending Triangle → Breakout above flat resistance
• Hammer / Morning Star candles

**⚡ KEY RULES:**
1. Wait for confirmed breakout (candle close beyond level)
2. Volume should increase on breakout
3. Higher timeframes = more reliable signals
4. Always use stop loss based on pattern structure
5. Target = pattern height projected from breakout""")
        
        # Pattern Reference Images - All Patterns at a Glance
        ref1 = os.path.join(images_dir, 'reversal_patterns.png')
        if os.path.exists(ref1):
            await patterns_channel.send("**📊 PATTERN REFERENCE GUIDE - REVERSALS**\nAll major reversal patterns at a glance:", file=discord.File(ref1))
        
        ref2 = os.path.join(images_dir, 'continuation_patterns.png')
        if os.path.exists(ref2):
            await patterns_channel.send("**📊 PATTERN REFERENCE GUIDE - CONTINUATIONS**\nAll major continuation patterns at a glance:", file=discord.File(ref2))
        
        # Complete Patterns Poster - All in One
        poster = os.path.join(images_dir, 'complete_patterns_poster.png')
        if os.path.exists(poster):
            await patterns_channel.send("**📚 COMPLETE CANDLESTICK & CHART PATTERNS GUIDE**\nAll bullish, bearish, reversal, continuation and bilateral patterns in one view:", file=discord.File(poster))
    
    # Send strategy content to trading-strategies channel
    strategies_channel = discord.utils.get(guild.text_channels, name='🎯│trading-strategies')
    if strategies_channel:
        # Moving Averages
        await strategies_channel.send("""**📈 MOVING AVERAGES (MA)**

Moving averages smooth out price data to show trend direction. The two main types:

**Simple Moving Average (SMA)**
• Calculates average price over X periods
• Common settings: 20, 50, 100, 200 SMA
• 200 SMA = Long-term trend indicator

**Exponential Moving Average (EMA)**
• Gives more weight to recent prices
• Reacts faster to price changes
• Common settings: 9, 21, 50 EMA

**Trading Signals:**
• **Golden Cross** = 50 MA crosses ABOVE 200 MA → Bullish
• **Death Cross** = 50 MA crosses BELOW 200 MA → Bearish
• Price above MA = Bullish, Price below MA = Bearish
• MAs act as dynamic support/resistance
📚 TradingView: https://www.tradingview.com/support/solutions/43000502017-moving-average/""")
        
        # RSI
        await strategies_channel.send("""**📊 RSI (Relative Strength Index)**

RSI measures momentum on a scale of 0-100, showing overbought/oversold conditions.

**How to Read RSI:**
• **Above 70** = Overbought (potential sell signal)
• **Below 30** = Oversold (potential buy signal)
• **50 level** = Neutral zone

**Trading Strategies:**
• Buy when RSI crosses above 30 (leaving oversold)
• Sell when RSI crosses below 70 (leaving overbought)
• **Divergence** = Price makes new high but RSI doesn't → Reversal signal

**Settings:**
• Default: 14 periods
• Shorter (7) = More signals, more false positives
• Longer (21) = Fewer signals, more reliable
📚 TradingView: https://www.tradingview.com/support/solutions/43000502338-relative-strength-index/""")
        
        # MACD
        await strategies_channel.send("""**📉 MACD (Moving Average Convergence Divergence)**

MACD shows trend direction, momentum, and potential reversals. Consists of:
• **MACD Line** = 12 EMA - 26 EMA
• **Signal Line** = 9 EMA of MACD Line
• **Histogram** = Difference between MACD and Signal

**Trading Signals:**
• **Bullish Crossover** = MACD crosses ABOVE Signal Line → Buy
• **Bearish Crossover** = MACD crosses BELOW Signal Line → Sell
• **Histogram growing** = Momentum increasing
• **Zero line cross** = Trend change confirmation

**Divergence:**
• Price makes higher high, MACD makes lower high → Bearish divergence
• Price makes lower low, MACD makes higher low → Bullish divergence
📚 TradingView: https://www.tradingview.com/support/solutions/43000502344-macd/""")
        
        # Bollinger Bands
        await strategies_channel.send("""**〰️ BOLLINGER BANDS**

Bollinger Bands measure volatility with 3 lines around price:
• **Upper Band** = 20 SMA + (2 x Standard Deviation)
• **Middle Band** = 20 SMA
• **Lower Band** = 20 SMA - (2 x Standard Deviation)

**How to Trade:**
• **Squeeze** = Bands narrow → Volatility contraction, big move coming
• **Expansion** = Bands widen → Volatility increasing
• Price touching upper band = Overbought
• Price touching lower band = Oversold

**Mean Reversion Strategy:**
• Buy when price touches lower band and shows reversal candle
• Sell when price touches upper band and shows reversal candle
• Target: Middle band (20 SMA)
📚 TradingView: https://www.tradingview.com/support/solutions/43000501840-bollinger-bands/""")
        
        # Fibonacci
        await strategies_channel.send("""**🔢 FIBONACCI RETRACEMENT**

Fibonacci levels show potential support/resistance based on natural ratios.

**Key Levels:**
• **23.6%** - Shallow retracement
• **38.2%** - Common pullback level
• **50%** - Psychological level
• **61.8%** - Golden ratio (most important!)
• **78.6%** - Deep retracement

**How to Use:**
1. Identify a clear swing high and swing low
2. Draw Fib from low to high (uptrend) or high to low (downtrend)
3. Look for price reactions at Fib levels
4. Combine with other indicators for confirmation

**Trading Strategy:**
• Enter at 61.8% retracement with stop below 78.6%
• Target: Previous high/low or Fib extension levels
📚 TradingView: https://www.tradingview.com/support/solutions/43000596023-fibonacci-retracement/""")
        
        # VWAP
        await strategies_channel.send("""**⚖️ VWAP (Volume Weighted Average Price)**

VWAP shows the average price weighted by volume - tells you if you got a good price.

**How to Read:**
• **Price above VWAP** = Bullish bias, buyers in control
• **Price below VWAP** = Bearish bias, sellers in control
• VWAP acts as dynamic support/resistance

**Trading Strategy:**
• Buy when price pulls back to VWAP from above
• Sell when price bounces to VWAP from below
• Institutions often execute trades at VWAP

**Best For:**
• Day trading (resets daily)
• Intraday support/resistance
• Determining fair value

📚 TradingView: https://www.tradingview.com/support/solutions/43000502019-volume-weighted-average-price/""")
        
        # Volume
        await strategies_channel.send("""**📊 VOLUME ANALYSIS**

Volume confirms price moves - it shows conviction behind the move.

**Volume Rules:**
• **Rising price + Rising volume** = Strong uptrend ✅
• **Rising price + Falling volume** = Weak uptrend, potential reversal ⚠️
• **Falling price + Rising volume** = Strong downtrend ✅
• **Falling price + Falling volume** = Weak downtrend, potential reversal ⚠️

**Key Signals:**
• **Volume spike** at support = Likely bounce
• **Volume spike** at resistance = Likely rejection
• **Breakout with high volume** = Likely real breakout
• **Breakout with low volume** = Likely false breakout
📚 TradingView: https://www.tradingview.com/support/solutions/43000595982-volume/""")
        
        # Trading Styles
        await strategies_channel.send("""**⏰ TRADING STYLES**

**🔥 Scalping (1-15 minutes)**
• Many quick trades for small profits
• High win rate needed (70%+)
• Requires fast execution and low fees
• Best for: High liquidity markets

**📅 Day Trading (15min - 4hr)**
• Open and close positions same day
• No overnight risk
• Requires screen time during market hours
• Best for: Futures, Forex, Stocks

**📈 Swing Trading (Days - Weeks)**
• Hold positions for days to weeks
• Capture larger moves
• Less screen time needed
• Best for: Stocks, Crypto, Forex

**💎 Position Trading (Weeks - Months)**
• Long-term holds based on fundamentals + technicals
• Lowest time commitment
• Requires patience
• Best for: Stocks, ETFs, Crypto

📚 YouTube: Search 'trading styles explained'""")
        
        # Risk Management
        await strategies_channel.send("""**⚠️ RISK MANAGEMENT - MOST IMPORTANT!**

Good risk management separates profitable traders from losing traders.

**The Rules:**
• **Never risk more than 1-2% per trade**
• Calculate position size BEFORE entering
• Always use stop losses
• Never move stop loss further away

**Position Sizing Formula:**
Risk Amount = Account Size × Risk %
Position Size = Risk Amount ÷ (Entry - Stop Loss)

**Example:**
$10,000 account × 1% risk = $100 max risk
Entry: $50, Stop: $48 (distance = $2)
Position Size = $100 ÷ $2 = 50 shares

**Risk/Reward Ratio:**
• Minimum 1:2 R:R (risk $1 to make $2)
• Even with 40% win rate, you profit with 1:2 R:R
📚 YouTube: Search 'risk management trading'""")
        
        # Stochastic Oscillator
        await strategies_channel.send("""**📈 STOCHASTIC OSCILLATOR**

Stochastic compares closing price to price range over time (0-100 scale).

**How to Read:**
• **Above 80** = Overbought zone
• **Below 20** = Oversold zone
• **%K line** = Fast line (blue)
• **%D line** = Slow line (signal, orange)

**Trading Signals:**
• Buy when %K crosses ABOVE %D in oversold zone (<20)
• Sell when %K crosses BELOW %D in overbought zone (>80)
• Best in ranging/sideways markets

**Settings:**
• Default: 14, 3, 3 (period, %K smoothing, %D smoothing)
• Slower settings reduce false signals
📚 TradingView: https://www.tradingview.com/support/solutions/43000502336-stochastic/""")
        
        # ATR
        await strategies_channel.send("""**📏 ATR (Average True Range)**

ATR measures market volatility - how much price moves on average.

**How to Use:**
• Higher ATR = More volatile, wider stops needed
• Lower ATR = Less volatile, tighter stops possible
• ATR does NOT show direction, only volatility

**Practical Applications:**
• **Stop Loss**: Place stops 1.5-2x ATR from entry
• **Position Sizing**: Smaller positions when ATR is high
• **Breakout Confirmation**: Breakouts with expanding ATR are stronger

**Example:**
ATR = $2.00, Entry = $50
Stop Loss = $50 - (1.5 × $2) = $47
📚 TradingView: https://www.tradingview.com/support/solutions/43000502023-average-true-range/""")
        
        # Support & Resistance
        await strategies_channel.send("""**🧱 SUPPORT & RESISTANCE**

Support and resistance are key price levels where buying/selling pressure concentrates.

**Support:**
• Price level where buying interest is strong enough to overcome selling
• Price tends to "bounce" off support
• When broken, old support becomes new resistance

**Resistance:**
• Price level where selling pressure overcomes buying
• Price tends to get "rejected" at resistance
• When broken, old resistance becomes new support

**How to Identify:**
• Previous swing highs/lows
• Round numbers ($100, $50, etc.)
• High volume areas
• Moving averages (especially 200 SMA)

**Trading Strategy:**
• Buy at support with stop below
• Sell at resistance with stop above
• Trade breakouts when levels break with volume
📚 TradingView: https://www.tradingview.com/support/solutions/43000521014-support-and-resistance/""")
        
        # Trendlines
        await strategies_channel.send("""**📐 TRENDLINES**

Trendlines connect swing points to show trend direction and potential support/resistance.

**How to Draw:**
• **Uptrend line**: Connect 2+ swing LOWS (support)
• **Downtrend line**: Connect 2+ swing HIGHS (resistance)
• Need at least 2 touch points, 3+ is stronger

**Trading Rules:**
• In uptrend: Buy bounces off trendline support
• In downtrend: Sell rejections at trendline resistance
• Trendline break = Potential trend reversal

**Tips:**
• Use bodies, not wicks, for more reliable lines
• Steeper trendlines break faster
• Combine with other indicators for confirmation
📚 TradingView: https://www.tradingview.com/support/solutions/43000596000-trend-lines/""")
        
        # Supply & Demand
        await strategies_channel.send("""**📦 SUPPLY & DEMAND ZONES**

Supply/Demand zones are areas where institutional orders created sharp moves.

**Demand Zone (Buy Zone):**
• Area where strong buying occurred
• Price rallied sharply FROM this level
• Look to buy when price returns to this zone

**Supply Zone (Sell Zone):**
• Area where strong selling occurred
• Price dropped sharply FROM this level
• Look to sell when price returns to this zone

**How to Identify:**
1. Find strong, impulsive moves (big candles)
2. Mark the BASE before the move
3. Zone = Last candle before the explosive move

**Fresh vs Tested:**
• Fresh zone (untested) = Stronger
• Tested zone = Weaker, may not hold

📚 YouTube: Search 'supply and demand zones'""")
        
        # ICT Smart Money
        await strategies_channel.send("""**🧠 ICT / SMART MONEY CONCEPTS**

Smart Money Concepts (SMC) focus on how institutions trade and manipulate markets.

**Key Concepts:**

**Order Blocks:**
• Last candle before a strong move
• Institutions place large orders here
• Price often returns to fill these orders

**Fair Value Gaps (FVG):**
• Gaps in price action (inefficiency)
• Created when candle 1 high < candle 3 low (or vice versa)
• Price tends to "fill" these gaps

**Liquidity:**
• Stop losses create liquidity pools
• Smart money hunts these stops before reversing
• Look for stop hunts at obvious levels

**Break of Structure (BOS):**
• When price breaks a swing high/low
• Confirms trend continuation or reversal
📚 YouTube: Search 'ICT smart money concepts'""")
        
        # Trading Psychology
        await strategies_channel.send("""**🧘 TRADING PSYCHOLOGY**

Your mental game is the biggest factor in trading success.

**Common Psychological Traps:**
• **FOMO** - Chasing trades you missed
• **Revenge Trading** - Trading angry after a loss
• **Overtrading** - Taking too many trades
• **Moving Stops** - Hoping a loser will turn around

**Solutions:**
• Trade with a plan, not emotions
• Accept losses as part of the game
• Take breaks after losses
• Journal every trade

**Mindset Rules:**
• Focus on process, not profits
• One trade doesn't define you
• Consistency > Home runs
• Protect capital first, profits second
📚 YouTube: Search 'trading psychology'""")
    
    # ══════════════════════════════════════════
    # CATEGORY 4: Free Community
    # ══════════════════════════════════════════
    print('\n📁 Creating Free Community category...')
    free_cat = await get_or_create_category(guild, '『 Free Community 』', position=3)
    
    await get_or_create_channel(guild, '💬│general-chat', free_cat)
    await get_or_create_channel(guild, '📈│trading-discussion', free_cat)
    
    # Final cleanup of stray channels
    old_disclaimer = discord.utils.get(guild.text_channels, name='disclaimer')
    if old_disclaimer and old_disclaimer.category is None:
        await old_disclaimer.delete()
        print('   🗑️ Removed old #disclaimer')
    
    print('\n🎉 Server setup complete! Looking professional! ✨')


if __name__ == '__main__':
    print('🚀 Starting QuoTrading Discord Setup Bot...')
    bot.run(TOKEN)

"""
QuoTrading News & Earnings Bot
Posts market news, earnings calendar, and WSB trending stocks to Discord
"""

import discord
from discord.ext import commands, tasks
import aiohttp
import asyncio
import json
import os
from datetime import datetime, timedelta

# Load config
config_path = os.path.join(os.path.dirname(__file__), 'config.json')
with open(config_path, 'r') as f:
    config = json.load(f)

BOT_TOKEN = config.get('bot_token')
FINNHUB_API_KEY = config.get('finnhub_api_key', '')  # Get free key at finnhub.io

intents = discord.Intents.default()
intents.message_content = True  # Required for commands to work
bot = commands.Bot(command_prefix='!', intents=intents)

# Channel names
NEWS_CHANNEL = "📰│market-news"
EARNINGS_CHANNEL = "📅│earnings-calendar"


async def fetch_market_news():
    """Fetch latest market news from Finnhub"""
    if not FINNHUB_API_KEY:
        return None
    
    url = f"https://finnhub.io/api/v1/news?category=general&token={FINNHUB_API_KEY}"
    
    async with aiohttp.ClientSession() as session:
        async with session.get(url) as resp:
            if resp.status == 200:
                news = await resp.json()
                return news[:10]  # Top 10 headlines
    return None


async def fetch_earnings_whispers_image():
    """Fetch the weekly earnings calendar image from Earnings Whispers"""
    # Earnings Whispers posts their calendar image - we can get it from their site
    # The image URL follows a pattern based on the week
    
    # They also post on Twitter/Reddit - we'll check Reddit for the image
    url = "https://www.reddit.com/r/wallstreetbets/search.json?q=earnings+whispers&restrict_sr=1&sort=new&limit=10"
    
    headers = {'User-Agent': 'QuoTradingBot/1.0'}
    
    async with aiohttp.ClientSession() as session:
        # Try to find Earnings Whispers post on WSB
        async with session.get(url, headers=headers) as resp:
            if resp.status == 200:
                data = await resp.json()
                posts = data.get('data', {}).get('children', [])
                
                for post in posts:
                    post_data = post.get('data', {})
                    title = post_data.get('title', '').lower()
                    url_img = post_data.get('url', '')
                    
                    # Look for earnings/anticipated posts with images
                    is_image = url_img.endswith(('.jpg', '.jpeg', '.png', '.gif', '.webp')) or 'i.redd.it' in url_img
                    if ('earning' in title or 'anticipated' in title) and is_image:
                        return {
                            'title': post_data.get('title'),
                            'url': f"https://reddit.com{post_data.get('permalink')}",
                            'image': url_img,
                            'author': post_data.get('author'),
                        }
        
        # Fallback: Direct Earnings Whispers image URL (they use consistent naming)
        # Try to get from their site directly
        ew_url = "https://www.earningswhispers.com/calendar"
        try:
            async with session.get(ew_url, headers=headers) as resp:
                if resp.status == 200:
                    html = await resp.text()
                    # Look for the calendar image in their HTML
                    import re
                    match = re.search(r'(https://[^"\']+(?:calendar|anticipated)[^"\']*\.(?:png|jpg))', html)
                    if match:
                        return {
                            'title': 'Most Anticipated Earnings Releases',
                            'url': 'https://www.earningswhispers.com',
                            'image': match.group(1),
                            'author': 'Earnings Whispers',
                        }
        except:
            pass
    
    return None


async def fetch_wsb_trending():
    """Fetch trending stocks from WallStreetBets via ApeWisdom API (free)"""
    url = "https://apewisdom.io/api/v1.0/filter/all-stocks/page/1"
    
    async with aiohttp.ClientSession() as session:
        async with session.get(url) as resp:
            if resp.status == 200:
                data = await resp.json()
                return data.get('results', [])[:15]  # Top 15 trending
    return None


def create_news_embed(news_items):
    """Create Discord embed for market news"""
    embed = discord.Embed(
        title="📰 Market News Update",
        description="Latest headlines from the markets",
        color=discord.Color.blue(),
        timestamp=datetime.utcnow()
    )
    
    for i, item in enumerate(news_items[:8], 1):
        title = item.get('headline', 'No title')[:100]
        source = item.get('source', 'Unknown')
        url = item.get('url', '')
        
        embed.add_field(
            name=f"{i}. {source}",
            value=f"[{title}]({url})" if url else title,
            inline=False
        )
    
    embed.set_footer(text="QuoTrading • Updated every 4 hours")
    return embed


def create_earnings_embed(post_data):
    """Create Discord embed for Earnings Whispers calendar"""
    embed = discord.Embed(
        title="📊 Most Anticipated Earnings Releases",
        description=f"**{post_data.get('title', 'Weekly Earnings')}**",
        color=discord.Color.gold(),
        timestamp=datetime.utcnow()
    )
    
    # Set the earnings calendar image
    if post_data.get('image'):
        embed.set_image(url=post_data.get('image'))
    
    embed.add_field(
        name="🔗 Source",
        value=f"[View on Reddit]({post_data.get('url', 'https://reddit.com/r/wallstreetbets')})",
        inline=True
    )
    
    embed.set_footer(text=f"via u/{post_data.get('author', 'unknown')} • r/wallstreetbets")
    return embed


def create_wsb_embed(trending):
    """Create Discord embed for WSB trending stocks"""
    embed = discord.Embed(
        title="🦍 WallStreetBets Trending",
        description="Most mentioned stocks on Reddit this week",
        color=discord.Color.orange(),
        timestamp=datetime.utcnow()
    )
    
    text = ""
    for i, item in enumerate(trending[:15], 1):
        ticker = item.get('ticker', '?')
        name = item.get('name', ticker)[:30]
        mentions = item.get('mentions', 0)
        rank_change = item.get('rank_24h_ago', i) - i
        
        if rank_change > 0:
            arrow = f"🔼 +{rank_change}"
        elif rank_change < 0:
            arrow = f"🔽 {rank_change}"
        else:
            arrow = "➡️"
        
        text += f"**{i}.** `${ticker}` - {mentions} mentions {arrow}\n"
    
    embed.description = text if text else "No data available"
    embed.set_footer(text="Data from ApeWisdom • r/wallstreetbets")
    return embed


@bot.event
async def on_ready():
    print(f"✅ News Bot logged in as {bot.user}")
    print(f"📰 Posting to: #{NEWS_CHANNEL}")
    print(f"📅 Posting to: #{EARNINGS_CHANNEL}")
    
    # Start scheduled tasks
    if not post_news.is_running():
        post_news.start()
    if not post_weekly_earnings.is_running():
        post_weekly_earnings.start()
    
    print("✅ Scheduled tasks started!")


@tasks.loop(hours=4)
async def post_news():
    """Post market news every 4 hours"""
    await bot.wait_until_ready()
    
    for guild in bot.guilds:
        channel = discord.utils.get(guild.text_channels, name=NEWS_CHANNEL)
        if not channel:
            continue
        
        news = await fetch_market_news()
        if news:
            embed = create_news_embed(news)
            await channel.send(embed=embed)
            print(f"📰 Posted news to {guild.name}")
        else:
            print(f"⚠️ No news data (check FINNHUB_API_KEY in config.json)")


# Track what we've already posted (to avoid duplicates)
last_posted_earnings_url = None


@tasks.loop(hours=6)  # Check every 6 hours for new earnings posts
async def post_weekly_earnings():
    """Auto-post new earnings calendar when detected on Reddit"""
    global last_posted_earnings_url
    await bot.wait_until_ready()
    
    # Fetch the latest earnings post
    earnings = await fetch_earnings_whispers_image()
    if not earnings:
        print("📅 No earnings post found on Reddit")
        return
    
    # Check if this is a NEW post (different URL than last time)
    if earnings.get('image') == last_posted_earnings_url:
        print("📅 Same earnings post as before, skipping")
        return
    
    # New post detected! Post to all servers
    for guild in bot.guilds:
        channel = discord.utils.get(guild.text_channels, name=EARNINGS_CHANNEL)
        if not channel:
            continue
        
        # Post Earnings Whispers calendar
        embed = create_earnings_embed(earnings)
        await channel.send(embed=embed)
        print(f"📅 Posted NEW Earnings Whispers to {guild.name}")
        
        # Also post WSB trending stocks
        wsb = await fetch_wsb_trending()
        if wsb:
            embed = create_wsb_embed(wsb)
            await channel.send(embed=embed)
            print(f"🦍 Posted WSB trending to {guild.name}")
    
    # Remember what we posted
    last_posted_earnings_url = earnings.get('image')


# Manual commands for testing
@bot.command(name='news')
async def manual_news(ctx):
    """Manually trigger news post"""
    news = await fetch_market_news()
    if news:
        embed = create_news_embed(news)
        await ctx.send(embed=embed)
    else:
        await ctx.send("❌ Could not fetch news. Check if FINNHUB_API_KEY is set in config.json")


@bot.command(name='earnings')
async def manual_earnings(ctx):
    """Manually trigger Earnings Whispers post to #earnings-calendar"""
    # Find the earnings channel
    channel = discord.utils.get(ctx.guild.text_channels, name=EARNINGS_CHANNEL)
    if not channel:
        await ctx.send(f"❌ Could not find channel: {EARNINGS_CHANNEL}")
        return
    
    earnings = await fetch_earnings_whispers_image()
    if earnings:
        embed = create_earnings_embed(earnings)
        await channel.send(embed=embed)
        await ctx.send(f"✅ Posted to {channel.mention}")
    else:
        await ctx.send("❌ Could not fetch Earnings Whispers calendar")


@bot.command(name='wsb')
async def manual_wsb(ctx):
    """Manually trigger WSB trending post"""
    wsb = await fetch_wsb_trending()
    if wsb:
        embed = create_wsb_embed(wsb)
        await ctx.send(embed=embed)
    else:
        await ctx.send("❌ Could not fetch WSB data")


if __name__ == "__main__":
    if not BOT_TOKEN:
        print("❌ No bot_token found in config.json")
    else:
        print("🚀 Starting QuoTrading News & Earnings Bot...")
        print("   - Market news: Every 4 hours")
        print("   - Earnings + WSB: Every Sunday")
        print("\n   Commands: !news, !earnings, !wsb")
        bot.run(BOT_TOKEN)

"""
Create mindset channel and set up daily motivation posts
"""
import discord
from discord.ext import commands, tasks
import json
import os
import random
from datetime import datetime

config_path = os.path.join(os.path.dirname(__file__), 'config.json')
with open(config_path, 'r') as f:
    config = json.load(f)

BOT_TOKEN = config.get('bot_token')

intents = discord.Intents.default()
bot = commands.Bot(command_prefix='!', intents=intents)

# Trading motivation quotes
MOTIVATION_QUOTES = [
    "💰 **$500/month = $17/day**\n$1,000/month = $34/day\n$5,000/month = $167/day\n\nFocus on small daily goals. Be consistent, have faith & watch it pile up! 🔥",
    "📈 **The goal isn't to make money. The goal is to become a trader who makes money.**\n\nFocus on the process, not the profits.",
    "🧠 **Discipline is choosing between what you want NOW and what you want MOST.**\n\nStick to your trading plan.",
    "💪 **You don't need to win every trade. You need to win more than you lose.**\n\nRisk management > Everything",
    "🎯 **Small consistent gains compound into life-changing wealth.**\n\n1% daily = 1,200% yearly",
    "⚡ **The market will always be there tomorrow.**\n\nIf you're not in the right headspace, don't trade.",
    "🔥 **Losses are tuition. Every losing trade teaches you something.**\n\nJournal your trades. Learn from mistakes.",
    "💎 **Patience is a trader's superpower.**\n\nWait for YOUR setup. Let the trade come to you.",
    "📊 **Cut losers fast. Let winners run.**\n\nThis simple rule separates winners from losers.",
    "🚀 **You're not late. You're just getting started.**\n\nMost successful traders took 2-3 years to become profitable.",
    "🧘 **Emotional control = Edge in the market.**\n\nThe best trade is often no trade at all.",
    "💡 **Trade what you SEE, not what you THINK.**\n\nPrice action > Predictions",
    "🎲 **Trading is not gambling when you have an edge.**\n\nDevelop your strategy. Trust your system.",
    "⏰ **Time in the market beats timing the market.**\n\nConsistency > Perfection",
    "🏆 **Champions are made in practice, not in the arena.**\n\nBacktest. Paper trade. Then go live.",
]

CHANNEL_NAME = "🧠│mindset"
CATEGORY_NAME = "Free Community"


@bot.event
async def on_ready():
    print(f"✅ Logged in as {bot.user}")
    
    guild = bot.guilds[0]
    everyone_role = guild.default_role
    
    # Find Free Community category
    category = None
    for cat in guild.categories:
        if "free" in cat.name.lower() and "community" in cat.name.lower():
            category = cat
            break
    
    if not category:
        print("❌ Could not find Free Community category")
        await bot.close()
        return
    
    # Check if channel already exists
    existing = discord.utils.get(category.text_channels, name=CHANNEL_NAME)
    if existing:
        print(f"Channel #{CHANNEL_NAME} already exists")
        channel = existing
    else:
        # Create the channel
        channel = await guild.create_text_channel(
            name=CHANNEL_NAME,
            category=category,
            topic="Daily trading motivation & mindset tips 🧠💪"
        )
        print(f"✅ Created #{CHANNEL_NAME}")
    
    # Set permissions - view only, reactions allowed
    await channel.set_permissions(everyone_role,
        view_channel=True,
        read_messages=True,
        read_message_history=True,
        send_messages=False,
        add_reactions=True,
        use_external_emojis=True,
    )
    print(f"🔒 Set #{CHANNEL_NAME} to view-only with reactions")
    
    # Post a welcome message
    embed = discord.Embed(
        title="🧠 Trading Mindset",
        description="**Daily motivation and mindset tips for traders.**\n\nStay disciplined. Stay focused. Stay profitable.",
        color=discord.Color.gold()
    )
    embed.set_footer(text="New motivation posted daily 🔥")
    await channel.send(embed=embed)
    
    # Post first motivation quote
    quote = random.choice(MOTIVATION_QUOTES)
    await channel.send(quote)
    
    print("✅ Posted welcome message and first quote!")
    print("\n🎉 Mindset channel is ready!")
    await bot.close()


if __name__ == "__main__":
    bot.run(BOT_TOKEN)

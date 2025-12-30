"""
Create giveaway channel under Welcome category
"""
import discord
from discord.ext import commands
import json
import os

config_path = os.path.join(os.path.dirname(__file__), 'config.json')
with open(config_path, 'r') as f:
    config = json.load(f)

BOT_TOKEN = config.get('bot_token')
intents = discord.Intents.default()
bot = commands.Bot(command_prefix='!', intents=intents)

@bot.event
async def on_ready():
    guild = bot.guilds[0]
    everyone_role = guild.default_role
    
    # Find Welcome category
    welcome_cat = None
    for cat in guild.categories:
        if "welcome" in cat.name.lower():
            welcome_cat = cat
            break
    
    if not welcome_cat:
        print("❌ Could not find Welcome category")
        await bot.close()
        return
    
    # Check if channel exists
    channel_name = "🎰│giveaways"
    existing = discord.utils.get(welcome_cat.text_channels, name=channel_name)
    
    if existing:
        channel = existing
        print(f"Channel already exists: #{channel_name}")
    else:
        channel = await guild.create_text_channel(
            name=channel_name,
            category=welcome_cat,
            topic="Weekly giveaways for premium members! 🎁"
        )
        print(f"✅ Created #{channel_name}")
    
    # Set permissions - view only + reactions
    await channel.set_permissions(everyone_role,
        view_channel=True,
        read_messages=True,
        read_message_history=True,
        send_messages=False,
        add_reactions=True,
        use_external_emojis=True,
    )
    print("🔒 Set to view-only with reactions")
    
    # Create the giveaway announcement embed
    embed = discord.Embed(
        title="🎰 Weekly Premium Giveaways",
        description=(
            "**Exclusive weekly giveaways for our Premium members!**\n\n"
            "Every week, we spin the wheel and one lucky Premium member wins a prize! 🎁\n\n"
            "━━━━━━━━━━━━━━━━━━━━━━"
        ),
        color=discord.Color.gold()
    )
    
    embed.add_field(
        name="🎯 How It Works",
        value=(
            "1️⃣ Be a **Premium Member**\n"
            "2️⃣ Your name is automatically entered\n"
            "3️⃣ Every week we spin the wheel\n"
            "4️⃣ Winner announced here!"
        ),
        inline=False
    )
    
    embed.add_field(
        name="⏳ Coming Soon",
        value=(
            "**Giveaways will begin once we reach 100 members!**\n\n"
            "Invite your friends to help us get there faster! 🚀"
        ),
        inline=False
    )
    
    embed.set_footer(text="Upgrade to Premium to participate • Good luck! 🍀")
    
    # Delete old messages and send new embed
    async for msg in channel.history(limit=10):
        await msg.delete()
    
    await channel.send(embed=embed)
    print("✅ Posted giveaway announcement!")
    
    await bot.close()

if __name__ == "__main__":
    bot.run(BOT_TOKEN)

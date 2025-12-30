"""
Leveling System & Welcome Manager (Simple Text + Inline Pepe)
"""
import discord
from discord.ext import commands, tasks
import json
import os
import random
import datetime

# ---------------- CONFIG ----------------
LEVELS = {
    1: {"xp": 0, "title": "🔰 Rookie Trader", "color": "#cfd8dc"},       
    2: {"xp": 100, "title": "📊 Chart Watcher", "color": "#81c784"},     
    3: {"xp": 300, "title": "📈 Trend Follower", "color": "#4caf50"},    
    4: {"xp": 600, "title": "🎯 Pattern Hunter", "color": "#2196f3"},    
    5: {"xp": 1000, "title": "⚡ Day Trader", "color": "#ffeb3b"},       
    6: {"xp": 1500, "title": "🔥 Swing Master", "color": "#ff9800"},     
    7: {"xp": 2100, "title": "💎 Diamond Hands", "color": "#00bcd4"},    
    8: {"xp": 2800, "title": "🦈 Market Shark", "color": "#3f51b5"},     
    9: {"xp": 3600, "title": "👑 Trading Legend", "color": "#9c27b0"},   
    10: {"xp": 5000, "title": "🏆 Elite Trader", "color": "#ffd700"},    
}

ALLOWED_ROLES = ["QuaTrader", "Premium", "Server Booster", "Admin", "MOD"]
DATA_FILE = os.path.join(os.path.dirname(__file__), 'level_data.json')
RAINBOW_PATH = os.path.join(os.path.dirname(__file__), 'line-rainbow.gif')

config_path = os.path.join(os.path.dirname(__file__), 'config.json')
with open(config_path, 'r') as f:
    bot_config = json.load(f)

BOT_TOKEN = bot_config.get('bot_token')
intents = discord.Intents.default()
intents.members = True
intents.message_content = True
bot = commands.Bot(command_prefix='!', intents=intents)

# Load XP Data
if os.path.exists(DATA_FILE):
    with open(DATA_FILE, 'r') as f:
        user_xp = json.load(f)
else:
    user_xp = {}

xp_cooldown = {}

def save_data():
    with open(DATA_FILE, 'w') as f:
        json.dump(user_xp, f, indent=4)

def get_level_info(xp):
    current_level = 1
    current_title = LEVELS[1]["title"]
    for level, data in LEVELS.items():
        if xp >= data["xp"]:
            current_level = level
            current_title = data["title"]
    return current_level, current_title

@bot.event
async def on_ready():
    print(f"✅ Leveling System Active as {bot.user}")

@bot.event
async def on_member_join(member):
    """Simple text welcome + Inline Pepe"""
    guild = member.guild
    channel = discord.utils.get(guild.text_channels, name="👋│welcome") or \
              discord.utils.get(guild.text_channels, name="welcome")
    
    if not channel:
        return

    # Suffix logic
    n = len(guild.members)
    if 11 <= (n % 100) <= 13:
        suffix = 'th'
    else:
        suffix = {1: 'st', 2: 'nd', 3: 'rd'}.get(n % 10, 'th')
    count_str = f"{n}{suffix}"

    # Get pepe emoji string
    pepe = discord.utils.get(guild.emojis, name="pepe_dance")
    emoji_str = str(pepe) if pepe else "👋" # format: <a:name:id>

    # Plain Text with Rainbow Divider (Original) + Inline Black Hole Emoji
    
    # 1. Send Rainbow Divider (Original Image)
    rainbow_path = os.path.join(os.path.dirname(__file__), 'line-rainbow.gif')
    if os.path.exists(rainbow_path):
        await channel.send(file=discord.File(rainbow_path))
    
    # 2. Send Welcome Text (No text divider)
    # Get black hole emoji
    black_hole = discord.utils.get(guild.emojis, name="black_hole")
    bh_str = str(black_hole) if black_hole else "⚫" # Fallback

    msg_content = (
        f"{bh_str} Hello {member.mention}, welcome to **QuoTrading**. You are the **{count_str}** member to join. {emoji_str}"
    )
    
    await channel.send(content=msg_content)

@bot.event
async def on_message(message):
    if message.author.bot:
        return
    
    # Check roles
    can_earn = False
    for role in message.author.roles:
        if any(allowed.lower() in role.name.lower() for allowed in ALLOWED_ROLES):
            can_earn = True
            break
            
    if not can_earn:
        await bot.process_commands(message)
        return

    user_id = str(message.author.id)
    
    # Cooldown (1 min)
    now = datetime.datetime.now().timestamp()
    if user_id in xp_cooldown:
        if now - xp_cooldown[user_id] < 60:
            await bot.process_commands(message)
            return
            
    xp_cooldown[user_id] = now
    
    # XP logic
    xp_gain = random.randint(15, 25)
    
    if user_id not in user_xp:
        user_xp[user_id] = {"xp": 0, "level": 1}
        
    old_xp = user_xp[user_id]["xp"]
    new_xp = old_xp + xp_gain
    user_xp[user_id]["xp"] = new_xp
    
    # Check Level Up
    old_level, _ = get_level_info(old_xp)
    new_level, new_title = get_level_info(new_xp)
    
    if new_level > old_level:
        channel = discord.utils.get(message.guild.text_channels, name="👋│welcome")
        if not channel:
            channel = message.channel
            
        # Dramatic Level Up (No Ping)
        embed = discord.Embed(color=discord.Color.from_str(LEVELS[new_level]["color"]))
        
        # Use rainbow gif
        if os.path.exists(RAINBOW_PATH):
           file = discord.File(RAINBOW_PATH, filename="rainbow.gif")
           embed.set_image(url="attachment://rainbow.gif")
        else:
           file = None

        embed.title = f"🎉 LEVEL UP!"
        embed.description = (
            f"**{message.author.name}** has reached **Level {new_level}**\n"
            f"👑 Rank: **{new_title}**\n\n"
            f"Keep grinding! 🚀"
        )
        
        if file:
            await channel.send(file=file, embed=embed)
        else:
            await channel.send(embed=embed)
        
    save_data()
    await bot.process_commands(message)

if __name__ == "__main__":
    bot.run(BOT_TOKEN)

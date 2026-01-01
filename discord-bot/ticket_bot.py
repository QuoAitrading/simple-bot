
"""
QuoTrading Discord Ticket Bot
Includes Tickets, Leveling, and Status
"""

import discord
from discord.ext import commands
from discord.ui import Button, View
import asyncio
import os
import logging
import aiohttp
import threading
import json
import datetime
import random

# Setup logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# API URL forheartbeat reporting
API_URL = os.environ.get('API_URL', 'https://quotrading-flask-api.azurewebsites.net')

# Get token
TOKEN = os.environ.get('DISCORD_BOT_TOKEN')
if not TOKEN:
    try:
        config_path = os.path.join(os.path.dirname(__file__), 'config.json')
        with open(config_path, 'r', encoding='utf-8') as f:
            config = json.load(f)
        TOKEN = config.get('bot_token')
    except:
        pass

if not TOKEN:
    raise ValueError("No bot token found!")

# Bot setup
intents = discord.Intents.default()
intents.guilds = True
intents.guild_messages = True
intents.members = True
intents.message_content = True
bot = commands.Bot(command_prefix='!', intents=intents)

# Track active tickets
active_tickets = 0
bot_ready = False

# ============ LEVELING SYSTEM ============
XP_FILE = os.path.join(os.path.dirname(__file__), 'xp_data.json')
XP_COOLDOWN = {}  # Track last XP gain per user
XP_COOLDOWN_SECONDS = 5  # 5 seconds anti-spam

# Level thresholds and role names (Level 1-10)
# ~1 year to reach max assuming ~50-100 msgs/day
LEVEL_ROLES = {
    1: {"name": "Quo Novice", "xp": 0},
    2: {"name": "Quo Trader", "xp": 1000},
    3: {"name": "Quo Tactician", "xp": 3000},
    4: {"name": "Quo Strategist", "xp": 6000},
    5: {"name": "Quo Executor", "xp": 10000},
    6: {"name": "Quo Automator", "xp": 15000},
    7: {"name": "Quo Predictor", "xp": 21000},
    8: {"name": "Quo Visionary", "xp": 28000},
    9: {"name": "Quo Mastermind", "xp": 36000},
    10: {"name": "Quo Supreme", "xp": 45000}
}

def load_xp():
    if os.path.exists(XP_FILE):
        try:
            with open(XP_FILE, 'r') as f:
                return json.load(f)
        except:
            return {}
    return {}

def save_xp(data):
    with open(XP_FILE, 'w') as f:
        json.dump(data, f, indent=4)

def get_level(xp: int) -> int:
    """Calculate level based on XP."""
    level = 1
    for lvl, info in LEVEL_ROLES.items():
        if xp >= info["xp"]:
            level = lvl
    return level

def get_role_for_level(level: int) -> str:
    """Get role name for a level."""
    return LEVEL_ROLES.get(level, {}).get("name", "Quo Novice")

async def check_level_up(member: discord.Member, old_xp: int, new_xp: int):
    """Check if member leveled up and assign new role."""
    old_level = get_level(old_xp)
    new_level = get_level(new_xp)
    
    if new_level > old_level:
        guild = member.guild
        
        # Remove old level roles
        for lvl, info in LEVEL_ROLES.items():
            old_role = discord.utils.get(guild.roles, name=info["name"])
            if old_role and old_role in member.roles:
                try:
                    await member.remove_role(old_role)
                except:
                    pass
        
        # Add new role
        new_role_name = get_role_for_level(new_level)
        new_role = discord.utils.get(guild.roles, name=new_role_name)
        if new_role:
            try:
                await member.add_role(new_role)
            except:
                pass
        
        # Announce in welcome channel
        welcome_ch = discord.utils.find(lambda c: "welcome" in c.name.lower(), guild.text_channels)
        if welcome_ch:
            try:
                embed = discord.Embed(
                    title="🎉 LEVEL UP!",
                    description=f"{member.mention} just reached **Level {new_level}**!",
                    color=discord.Color.gold()
                )
                embed.add_field(name="New Rank", value=f"🏆 **{new_role_name}**", inline=False)
                embed.set_thumbnail(url=member.display_avatar.url if member.display_avatar else None)
                await welcome_ch.send(embed=embed)
            except:
                pass
        
        return True
    return False

@bot.event
async def on_message(message):
    # Ignore bots
    if message.author.bot:
        return
    
    # Process commands first
    await bot.process_commands(message)
    
    # Only give XP to premium members (Quo Member role)
    member = message.author
    if not isinstance(member, discord.Member):
        return
    
    # Check if user has premium role
    has_premium = discord.utils.get(member.roles, name="Quo Member") or \
                  discord.utils.get(member.roles, name="Quo Exclusive")
    if not has_premium:
        return
    
    # Cooldown check (5 sec anti-spam)
    user_id = str(member.id)
    now = datetime.datetime.now().timestamp()
    last_xp = XP_COOLDOWN.get(user_id, 0)
    
    if now - last_xp < XP_COOLDOWN_SECONDS:
        return  # Still on cooldown
    
    XP_COOLDOWN[user_id] = now
    
    # Give 1 XP per message
    xp_gain = 1
    
    data = load_xp()
    old_xp = data.get(user_id, 0)
    new_xp = old_xp + xp_gain
    data[user_id] = new_xp
    save_xp(data)
    
    # Check for level up
    await check_level_up(member, old_xp, new_xp)

@bot.command()
async def rank(ctx):
    """Check your current rank and XP."""
    user_id = str(ctx.author.id)
    data = load_xp()
    xp = data.get(user_id, 0)
    level = get_level(xp)
    role_name = get_role_for_level(level)
    
    # Calculate XP to next level
    next_level = level + 1
    if next_level <= 10:
        next_xp = LEVEL_ROLES[next_level]["xp"]
        xp_needed = next_xp - xp
        progress = f"{xp}/{next_xp} XP (Need {xp_needed} more)"
    else:
        progress = f"{xp} XP (MAX LEVEL)"
    
    embed = discord.Embed(
        title=f"📊 {ctx.author.display_name}'s Rank",
        color=discord.Color.blue()
    )
    embed.add_field(name="Level", value=f"**{level}**/10", inline=True)
    embed.add_field(name="Rank", value=f"🏆 {role_name}", inline=True)
    embed.add_field(name="Progress", value=progress, inline=False)
    embed.set_thumbnail(url=ctx.author.display_avatar.url if ctx.author.display_avatar else None)
    
    await ctx.send(embed=embed)


# ============ BOT FUNCTIONS ============

async def send_heartbeat():
    global active_tickets
    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(f'{API_URL}/api/discord/heartbeat', json={
                'servers': len(bot.guilds),
                'active_tickets': active_tickets
            }) as resp:
                if resp.status == 200:
                    logger.debug("Heartbeat sent")
    except Exception as e:
        logger.debug(f"Heartbeat failed: {e}")

async def send_ticket_event(event: str):
    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(f'{API_URL}/api/discord/ticket', json={
                'event': event
            }) as resp:
                pass
    except:
        pass

class TicketButton(View):
    def __init__(self):
        super().__init__(timeout=None)
    
    @discord.ui.button(label="Create ticket", style=discord.ButtonStyle.blurple, emoji="📩", custom_id="create_ticket_btn")
    async def create_ticket_button(self, interaction: discord.Interaction, button: Button):
        try:
            await interaction.response.defer(ephemeral=True)
        except:
            return

        global active_tickets
        guild = interaction.guild
        user = interaction.user
        
        try:
            support_cat = discord.utils.get(guild.categories, name='『 Support 』')
            if not support_cat:
                support_cat = discord.utils.get(guild.categories, name='Support')
            
            if not support_cat:
                try:
                    support_cat = await guild.create_category(name='『 Support 』')
                except:
                    await interaction.followup.send('❌ Bot lacks permission.', ephemeral=True)
                    return
            
            existing = discord.utils.get(guild.text_channels, name=f'ticket-{user.name.lower()}')
            if existing:
                await interaction.followup.send(f'❌ You already have an open ticket: {existing.mention}', ephemeral=True)
                return
            
            overwrites = {
                guild.default_role: discord.PermissionOverwrite(read_messages=False),
                user: discord.PermissionOverwrite(read_messages=True, send_messages=True),
                guild.me: discord.PermissionOverwrite(read_messages=True, send_messages=True)
            }
            
            for role_name in ['Admin', 'Moderator']:
                role = discord.utils.get(guild.roles, name=role_name)
                if role:
                    overwrites[role] = discord.PermissionOverwrite(read_messages=True, send_messages=True)
            
            ticket_channel = await guild.create_text_channel(
                name=f'ticket-{user.name.lower()}',
                category=support_cat,
                overwrites=overwrites,
                topic=f'Support ticket for {user.name}'
            )
            
            close_view = CloseTicketView()
            ticket_embed = discord.Embed(
                title="🎫 Support Ticket",
                description=f"Welcome {user.mention}!\n\nA staff member will assist you shortly.\n\n**Please describe your issue below.**",
                color=discord.Color.green()
            )
            ticket_embed.set_footer(text="QuoTrading Support")
            
            await ticket_channel.send(embed=ticket_embed, view=close_view)
            await interaction.followup.send(f"✅ Ticket created: {ticket_channel.mention}", ephemeral=True)
            
            active_tickets += 1
            await send_ticket_event('created')
            
        except Exception as e:
            logger.error(f"Error creating ticket: {e}")
            await interaction.followup.send(f'❌ Error: {str(e)}', ephemeral=True)

class CloseTicketView(View):
    def __init__(self):
        super().__init__(timeout=None)
    
    @discord.ui.button(label="Close Ticket", style=discord.ButtonStyle.red, emoji="🔒", custom_id="close_ticket_btn")
    async def close_ticket_button(self, interaction: discord.Interaction, button: Button):
        try:
            await interaction.response.defer(ephemeral=True)
        except:
            return

        channel = interaction.channel
        global active_tickets

        try:
            if not channel.name.startswith('ticket-'):
                return
            
            await channel.send(f'🔒 Ticket closed by {interaction.user.mention}. Deleting in 5 seconds...')
            active_tickets = max(0, active_tickets - 1)
            await send_ticket_event('closed')
            
            await asyncio.sleep(5)
            await channel.delete()
            
        except Exception as e:
            logger.error(f"Error closing ticket: {e}")

# ============ LEVELING CONFIG ============
LEVELS = {
    1: {"xp": 0, "title": "Quo Novice"},
    2: {"xp": 500, "title": "Quo Trader"},
    3: {"xp": 1500, "title": "Quo Analyst"},
    4: {"xp": 4000, "title": "Quo Strategist"},
    5: {"xp": 8000, "title": "Quo Executor"},
    6: {"xp": 15000, "title": "Quo Automator"},
    7: {"xp": 25000, "title": "Quo Predictor"},
    8: {"xp": 40000, "title": "Quo Visionary"},
    9: {"xp": 65000, "title": "Quo Mastermind"},
    10: {"xp": 100000, "title": "Quo Supreme"},
}
ALLOWED_ROLES = ["QuaTrader", "Premium", "Server Booster", "Admin", "MOD"]
DATA_FILE = os.path.join(os.path.dirname(__file__), 'level_data.json')

if os.path.exists(DATA_FILE):
    try:
        with open(DATA_FILE, 'r') as f:
            user_xp = json.load(f)
    except:
        user_xp = {}
else:
    user_xp = {}

xp_cooldown = {}

def save_xp_data():
    try:
        with open(DATA_FILE, 'w') as f:
            json.dump(user_xp, f, indent=4)
    except Exception as e:
        logger.error(f"Failed to save XP data: {e}")

def get_level_info(xp):
    current_level = 1
    current_title = LEVELS[1]["title"]
    for level, data in LEVELS.items():
        if xp >= data["xp"]:
            current_level = level
            current_title = data["title"]
    return current_level, current_title

@bot.event
async def on_message(message):
    if message.author.bot:
        return
    
    await bot.process_commands(message)
    
    can_earn = False
    if not ALLOWED_ROLES:
        can_earn = True
    else:
        for role in message.author.roles:
            if any(allowed.lower() in role.name.lower() for allowed in ALLOWED_ROLES):
                can_earn = True
                break
            
    if not can_earn:
        return

    user_id = str(message.author.id)
    now = datetime.datetime.now().timestamp()
    if user_id in xp_cooldown:
        if now - xp_cooldown[user_id] < 60:
            return
            
    xp_cooldown[user_id] = now
    xp_gain = random.randint(15, 25)
    
    if user_id not in user_xp:
        user_xp[user_id] = {"xp": 0, "level": 1}
        
    old_xp = user_xp[user_id]["xp"]
    new_xp = old_xp + xp_gain
    user_xp[user_id]["xp"] = new_xp
    
    old_level, _ = get_level_info(old_xp)
    new_level, new_title = get_level_info(new_xp)
    
    if new_level > old_level:
        channel = discord.utils.get(message.guild.text_channels, name="👋│welcome") or message.channel
        
        current_dir = os.path.dirname(os.path.abspath(__file__))
        rainbow_path = os.path.join(current_dir, 'line-rainbow.gif')
        if os.path.exists(rainbow_path):
            await channel.send(file=discord.File(rainbow_path))
            
        embed = discord.Embed(
            description=f"🎉 **PROMOTION!** {message.author.mention} has been promoted to **{new_title}** (Level {new_level})! 🚀",
            color=0xFFD700
        )
        await channel.send(embed=embed)
        
        try:
            new_role_obj = discord.utils.get(message.guild.roles, name=new_title)
            if new_role_obj:
                await message.author.add_roles(new_role_obj)
            
            all_rank_titles = [data["title"] for _, data in LEVELS.items()]
            for role in message.author.roles:
                if role.name in all_rank_titles and role.name != new_title:
                    await message.author.remove_roles(role)
        except Exception as e:
            logger.error(f"Role error: {e}")
        
    save_xp_data()

@bot.event
async def on_member_join(member):
    guild = member.guild
    channel = discord.utils.get(guild.text_channels, name="👋│welcome")
    
    if not channel:
        for ch in guild.text_channels:
            if "welcome" in ch.name.lower():
                channel = ch
                break
    
    if not channel:
        return

    n = len(guild.members)
    count_str = f"{n}th" # simplified suffix logic
    
    pepe = discord.utils.get(guild.emojis, name="pepe_dance")
    emoji_str = str(pepe) if pepe else "👋"

    current_dir = os.path.dirname(os.path.abspath(__file__))
    rainbow_path = os.path.join(current_dir, 'line-rainbow.gif')
    
    try:
        if os.path.exists(rainbow_path):
            await channel.send(file=discord.File(rainbow_path))
    except:
        pass
    
    black_hole = discord.utils.get(guild.emojis, name="black_hole")
    bh_str = str(black_hole) if black_hole else "⚫"

    msg_content = f"{bh_str} Hello {member.mention}, welcome to **QuoTrading**. You are the **{count_str}** member to join. {emoji_str}"
    
    try:
        await channel.send(content=msg_content)
    except:
        pass

async def keep_alive():
    while True:
        await send_heartbeat()
        await asyncio.sleep(60)

async def update_server_status():
    status_config_path = os.path.join(os.path.dirname(__file__), 'status_config.json')
    if not os.path.exists(status_config_path):
        return

    try:
        with open(status_config_path, 'r') as f:
            data = json.load(f)
            channel_id = data.get('channel_id')
            message_id = data.get('message_id')
    except:
        return

    await bot.wait_until_ready()
    channel = bot.get_channel(channel_id)
    if not channel:
        return

    try:
        message = await channel.fetch_message(message_id)
    except:
        return

    last_status = None 

    while not bot.is_closed():
        current_status = "OFFLINE"
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(API_URL, timeout=10) as resp:
                    if resp.status < 600:
                        current_status = "ONLINE"
        except:
            current_status = "OFFLINE"

        current_time = datetime.datetime.now().strftime("%b %d, %Y - %I:%M %p EST")
        
        if current_status == "ONLINE":
            new_content = f"""
# 🟢 QuoTrading Server Online

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

**Last Checked:** {current_time}

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
"""
            emoji = "🟢"
        else:
            new_content = f"""
# 🔴 QuoTrading Server Offline

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

**Last Checked:** {current_time}
**Status:** CONNECTION LOST with API

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
"""
            emoji = "🔴"

        try:
            if message.content.strip() != new_content.strip():
                await message.edit(content=new_content)
        except:
            pass

        if last_status is not None and current_status != last_status:
            try:
                new_name = f"{emoji}│server-status"
                if channel.name != new_name:
                    await channel.edit(name=new_name)
            except:
                pass
        
        last_status = current_status
        await asyncio.sleep(60)

@bot.event
async def on_connect():
    bot.loop.create_task(keep_alive())
    bot.loop.create_task(update_server_status())
    # Leveling is handled via on_message event

@bot.event
async def on_ready():
    logger.info(f'📊 Connected to {len(bot.guilds)} server(s)')
    bot.add_view(TicketButton())
    bot.add_view(CloseTicketView())
    await send_heartbeat()
    logger.info('🎫 Ticket system ready!')

if __name__ == '__main__':
    logger.info('🚀 Starting QuoTrading Ticket Bot...')
    bot.run(TOKEN)

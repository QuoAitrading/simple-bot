"""
QuoTrading Discord Ticket Bot
Lightweight bot for 24/7 ticket system on Azure
Reports status to admin dashboard
Includes HTTP server for Azure App Service
"""

import discord
from discord.ext import commands
from discord.ui import Button, View
import asyncio
import os
import logging
import aiohttp
from aiohttp import web
import threading

# Setup logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# API URL for heartbeat reporting
API_URL = os.environ.get('API_URL', 'https://quotrading-flask-api.azurewebsites.net')

# Get token from environment variable (for Azure) or config file (for local)
TOKEN = os.environ.get('DISCORD_BOT_TOKEN')
if not TOKEN:
    try:
        import json
        config_path = os.path.join(os.path.dirname(__file__), 'config.json')
        with open(config_path, 'r', encoding='utf-8') as f:
            config = json.load(f)
        TOKEN = config.get('bot_token')
    except:
        pass

if not TOKEN:
    raise ValueError("No bot token found! Set DISCORD_BOT_TOKEN environment variable or create config.json")

# Bot setup
# Bot setup
intents = discord.Intents.default()
intents.guilds = True
intents.guild_messages = True
intents.members = True  # Required for on_member_join
bot = commands.Bot(command_prefix='!', intents=intents)

# Track active tickets
active_tickets = 0
bot_ready = False


# ============ HTTP SERVER FOR AZURE ============

async def health_handler(request):
    """Health check endpoint for Azure."""
    return web.json_response({
        "status": "healthy",
        "bot_ready": bot_ready,
        "active_tickets": active_tickets
    })

async def home_handler(request):
    """Home page."""
    return web.Response(text="QuoTrading Discord Bot is running!", content_type="text/html")

def run_http_server():
    """Run HTTP server in background thread."""
    app = web.Application()
    app.router.add_get('/', home_handler)
    app.router.add_get('/health', health_handler)
    
    port = int(os.environ.get('PORT', 8000))
    logger.info(f"Starting HTTP server on port {port}")
    
    web.run_app(app, host='0.0.0.0', port=port, print=None)


# ============ BOT FUNCTIONS ============

async def send_heartbeat():
    """Send heartbeat to API to show bot is online."""
    global active_tickets
    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(f'{API_URL}/api/discord/heartbeat', json={
                'servers': len(bot.guilds),
                'active_tickets': active_tickets
            }) as resp:
                if resp.status == 200:
                    logger.debug("Heartbeat sent successfully")
    except Exception as e:
        logger.debug(f"Heartbeat failed: {e}")


async def send_ticket_event(event: str):
    """Send ticket event to API."""
    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(f'{API_URL}/api/discord/ticket', json={
                'event': event
            }) as resp:
                if resp.status == 200:
                    logger.info(f"Ticket event '{event}' reported")
    except Exception as e:
        logger.debug(f"Ticket event failed: {e}")


class TicketButton(View):
    """Persistent button for creating tickets."""
    
    def __init__(self):
        super().__init__(timeout=None)
    
    @discord.ui.button(label="Create ticket", style=discord.ButtonStyle.blurple, emoji="📩", custom_id="create_ticket_btn")
    async def create_ticket_button(self, interaction: discord.Interaction, button: Button):
        global active_tickets
        guild = interaction.guild
        user = interaction.user
        
        # Find or create Support category
        support_cat = discord.utils.get(guild.categories, name='『 Support 』')
        if not support_cat:
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
        
        # Create close button and welcome embed
        close_view = CloseTicketView()
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
        
        # Track ticket
        active_tickets += 1
        logger.info(f"Ticket created for {user.name}")
        await send_ticket_event('created')


class CloseTicketView(View):
    """Button to close a ticket."""
    
    def __init__(self):
        super().__init__(timeout=None)
    
    @discord.ui.button(label="Close Ticket", style=discord.ButtonStyle.red, emoji="🔒", custom_id="close_ticket_btn")
    async def close_ticket_button(self, interaction: discord.Interaction, button: Button):
        global active_tickets
        channel = interaction.channel
        
        if not channel.name.startswith('ticket-'):
            await interaction.response.send_message('❌ This is not a ticket channel!', ephemeral=True)
            return
        
        await interaction.response.send_message('🔒 Closing ticket in 5 seconds...')
        
        # Track ticket close
        active_tickets = max(0, active_tickets - 1)
        await send_ticket_event('closed')
        
        await asyncio.sleep(5)
        await channel.delete()

import random
import datetime

# ============ LEVELING CONFIG ============
# XP Curve tailored for VERY LONG TERM activity (Avg 20 XP/msg, 1 min cooldown)
# Ranks: Quo Titles
LEVELS = {
    1: {"xp": 0, "title": "Quo Novice"},        # 1
    2: {"xp": 500, "title": "Quo Trader"},       # 2
    3: {"xp": 1500, "title": "Quo Analyst"},     # 3
    4: {"xp": 4000, "title": "Quo Strategist"},  # 4
    5: {"xp": 8000, "title": "Quo Executor"},    # 5
    6: {"xp": 15000, "title": "Quo Automator"},  # 6
    7: {"xp": 25000, "title": "Quo Predictor"},  # 7
    8: {"xp": 40000, "title": "Quo Visionary"},  # 8
    9: {"xp": 65000, "title": "Quo Mastermind"}, # 9
    10: {"xp": 100000, "title": "Quo Supreme"},  # 10
}
ALLOWED_ROLES = ["QuaTrader", "Premium", "Server Booster", "Admin", "MOD"]
DATA_FILE = os.path.join(os.path.dirname(__file__), 'level_data.json')

# Load XP Data
if os.path.exists(DATA_FILE):
    try:
        import json
        with open(DATA_FILE, 'r') as f:
            user_xp = json.load(f)
    except:
        user_xp = {}
else:
    user_xp = {}

xp_cooldown = {}

def save_xp_data():
    try:
        import json
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
    
    # Process commands first
    await bot.process_commands(message)
    
    # Check permissions
    can_earn = False
    if not ALLOWED_ROLES: # If no roles defined, everyone earns
        can_earn = True
    else:
        for role in message.author.roles:
            if any(allowed.lower() in role.name.lower() for allowed in ALLOWED_ROLES):
                can_earn = True
                break
            
    if not can_earn:
        return

    user_id = str(message.author.id)
    
    # Cooldown (1 min)
    now = datetime.datetime.now().timestamp()
    if user_id in xp_cooldown:
        if now - xp_cooldown[user_id] < 60:
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
            
        # Send Rainbow Divider
        current_dir = os.path.dirname(os.path.abspath(__file__))
        rainbow_path = os.path.join(current_dir, 'line-rainbow.gif')
        if os.path.exists(rainbow_path):
            await channel.send(file=discord.File(rainbow_path))
            
        # Send Level Up Message
        embed = discord.Embed(
            description=f"🎉 **PROMOTION!** {message.author.mention} has been promoted to **{new_title}** (Level {new_level})! 🚀",
            color=0xFFD700
        )
        await channel.send(embed=embed)
        
        # === ROLE ASSIGNMENT ===
        try:
            guild = message.guild
            member = message.author
            
            # 1. Add New Role
            new_role_obj = discord.utils.get(guild.roles, name=new_title)
            if new_role_obj:
                await member.add_roles(new_role_obj)
                logger.info(f"Assigned role {new_title} to {member.name}")
            else:
                logger.warning(f"Role '{new_title}' not found in server!")

            # 2. Remove Old Rank Roles (Cleanup)
            # List of all rank titles
            all_rank_titles = [data["title"] for _, data in LEVELS.items()]
            
            for role in member.roles:
                if role.name in all_rank_titles and role.name != new_title:
                    await member.remove_roles(role)
                    
        except Exception as e:
            logger.error(f"Failed to assign/remove roles: {e}")
        
    save_xp_data()
@bot.event
async def on_member_join(member):
    """Welcome message with rainbow divider + inline emoji."""
    logger.info(f"👤 Member joined: {member.name} (ID: {member.id})")
    
    guild = member.guild
    
    # 1. Smart Channel Search
    channel = None
    # Try exact matches first
    channel = discord.utils.get(guild.text_channels, name="👋│welcome") or \
              discord.utils.get(guild.text_channels, name="welcome")
    
    # If not found, try searching
    if not channel:
        for ch in guild.text_channels:
            if "welcome" in ch.name.lower():
                channel = ch
                break
    
    if not channel:
        logger.error(f"❌ Could not find ANY welcome channel in guild {guild.name}")
        return

    logger.info(f"✅ Found welcome channel: {channel.name}")

    # Suffix logic
    n = len(guild.members)
    if 11 <= (n % 100) <= 13:
        suffix = 'th'
    else:
        suffix = {1: 'st', 2: 'nd', 3: 'rd'}.get(n % 10, 'th')
    count_str = f"{n}{suffix}"

    # Get pepe (frog)
    pepe = discord.utils.get(guild.emojis, name="pepe_dance")
    emoji_str = str(pepe) if pepe else "👋"

    # Send Rainbow Divider (Original)
    # Ensure correct path relative to this script
    current_dir = os.path.dirname(os.path.abspath(__file__))
    rainbow_path = os.path.join(current_dir, 'line-rainbow.gif')
    
    try:
        if os.path.exists(rainbow_path):
            await channel.send(file=discord.File(rainbow_path))
        else:
            logger.warning(f"⚠️ Rainbow GIF not found at {rainbow_path}")
    except Exception as e:
        logger.error(f"❌ Failed to post GIF: {e}")
    
    # Send Text with Black Hole
    black_hole = discord.utils.get(guild.emojis, name="black_hole")
    bh_str = str(black_hole) if black_hole else "⚫"

    msg_content = (
        f"{bh_str} Hello {member.mention}, welcome to **QuoTrading**. You are the **{count_str}** member to join. {emoji_str}"
    )
    
    try:
        await channel.send(content=msg_content)
        logger.info(f"✅ Sent welcome message to {member.name}")
    except Exception as e:
        logger.error(f"❌ Failed to send welcome text: {e}")


@bot.event
async def on_ready():
    logger.info(f'📊 Connected to {len(bot.guilds)} server(s)')
    
    # Register persistent views so buttons work after restart
    bot.add_view(TicketButton())
    bot.add_view(CloseTicketView())
    
    # Send initial heartbeat
    await send_heartbeat()
    
    bot_ready = True
    logger.info('🎫 Ticket system ready!')


async def keep_alive():
    """Periodic heartbeat to API."""
    while True:
        await send_heartbeat()
        logger.info("💓 Heartbeat sent")
        await asyncio.sleep(60)


@bot.event
async def on_connect():
    bot.loop.create_task(keep_alive())


if __name__ == '__main__':
    logger.info('🚀 Starting QuoTrading Ticket Bot...')
    
    # Start HTTP server in background thread (for Azure)
    http_thread = threading.Thread(target=run_http_server, daemon=True)
    http_thread.start()
    
    # Run Discord bot
    bot.run(TOKEN)

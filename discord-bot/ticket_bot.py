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
intents = discord.Intents.default()
intents.guilds = True
intents.guild_messages = True
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
        logger.info(f"Ticket {channel.name} closed")


@bot.event
async def on_ready():
    global bot_ready
    logger.info(f'✅ Bot connected as {bot.user}')
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

import discord
import os
import asyncio
import aiohttp
import json
from datetime import datetime, timezone, timedelta
from discord.ext import commands
from discord.ui import Button, View

TOKEN = os.environ.get('DISCORD_BOT_TOKEN')
API_URL = os.environ.get('API_URL', 'https://quotrading-flask-api.azurewebsites.net')

intents = discord.Intents.default()
intents.guilds = True
intents.message_content = True
intents.members = True  # Required for on_member_join
bot = commands.Bot(command_prefix='!', intents=intents)
active_tickets = 0

# Status channel config
STATUS_CHANNEL_ID = None
STATUS_MESSAGE_ID = None

async def send_heartbeat():
    try:
        async with aiohttp.ClientSession() as s:
            await s.post(f'{API_URL}/api/discord/heartbeat', json={'servers': len(bot.guilds), 'active_tickets': active_tickets})
    except:
        pass

async def send_ticket_event(e):
    try:
        async with aiohttp.ClientSession() as s:
            await s.post(f'{API_URL}/api/discord/ticket', json={'event': e})
    except:
        pass

async def update_status_message(is_online=True):
    global STATUS_CHANNEL_ID, STATUS_MESSAGE_ID
    
    if not STATUS_CHANNEL_ID or not STATUS_MESSAGE_ID:
        return
    
    try:
        channel = bot.get_channel(STATUS_CHANNEL_ID)
        if not channel:
            return
        
        message = await channel.fetch_message(STATUS_MESSAGE_ID)
        if not message:
            return
        
        # Convert to EST (UTC-5)
        est = timezone(timedelta(hours=-5))
        now = datetime.now(est).strftime('%b %d, %Y - %I:%M %p EST')
        
        if is_online:
            content = f"""
# 🟢 All Systems Operational

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

**Last Checked:** {now}

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
"""
            new_name = "🟢│server-status"
        else:
            content = f"""
# 🔴 Service Disruption

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

We're experiencing issues. Working on it.

**Last Checked:** {now}

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
"""
            new_name = "🔴│server-status"
        
        await message.edit(content=content)
        
        # Update channel name if different (rate limited to 2 per 10 min)
        if channel.name != new_name:
            try:
                await channel.edit(name=new_name)
            except:
                pass  # Ignore rate limit errors
    except Exception as e:
        print(f'Status update error: {e}')


class TicketButton(View):
    def __init__(self):
        super().__init__(timeout=None)
    
    @discord.ui.button(label='Create ticket', style=discord.ButtonStyle.blurple, custom_id='create_ticket_btn')
    async def cb(self, interaction, btn):
        global active_tickets
        guild = interaction.guild
        user = interaction.user
        cat = None
        for c in guild.categories:
            if 'support' in c.name.lower():
                cat = c
                break
        if not cat:
            cat = await guild.create_category(name='Support')
        existing = discord.utils.get(guild.text_channels, name=f'ticket-{user.name.lower()}')
        if existing:
            await interaction.response.send_message(f'You have a ticket: {existing.mention}', ephemeral=True)
            return
        overwrites = {
            guild.default_role: discord.PermissionOverwrite(read_messages=False),
            user: discord.PermissionOverwrite(read_messages=True, send_messages=True),
            guild.me: discord.PermissionOverwrite(read_messages=True, send_messages=True)
        }
        channel = await guild.create_text_channel(name=f'ticket-{user.name.lower()}', category=cat, overwrites=overwrites)
        await channel.send(f'Welcome {user.mention}! Describe your issue.', view=CloseView())
        await interaction.response.send_message(f'Ticket created: {channel.mention}', ephemeral=True)
        active_tickets += 1
        await send_ticket_event('created')

class CloseView(View):
    def __init__(self):
        super().__init__(timeout=None)
    
    @discord.ui.button(label='Close', style=discord.ButtonStyle.red, custom_id='close_ticket_btn')
    async def cb(self, interaction, btn):
        global active_tickets
        if not interaction.channel.name.startswith('ticket-'):
            await interaction.response.send_message('Not a ticket', ephemeral=True)
            return
        await interaction.response.send_message('Closing...')
        active_tickets = max(0, active_tickets - 1)
        await send_ticket_event('closed')
        await asyncio.sleep(3)
        await interaction.channel.delete()

@bot.event
async def on_member_join(member):
    """Welcome message with rainbow divider for new members."""
    print(f"👤 Member joined: {member.name} (ID: {member.id})")
    
    guild = member.guild
    
    # Find welcome channel
    channel = discord.utils.get(guild.text_channels, name="👋│welcome") or \
              discord.utils.get(guild.text_channels, name="welcome")
    
    # If not found, try searching
    if not channel:
        for ch in guild.text_channels:
            if "welcome" in ch.name.lower():
                channel = ch
                break
    
    if not channel:
        print(f"❌ Could not find welcome channel in guild {guild.name}")
        return
    
    print(f"✅ Found welcome channel: {channel.name}")
    
    # Calculate member count with ordinal suffix
    n = guild.member_count
    if 11 <= (n % 100) <= 13:
        suffix = 'th'
    else:
        suffix = {1: 'st', 2: 'nd', 3: 'rd'}.get(n % 10, 'th')
    count_str = f"{n}{suffix}"
    
    # Get custom emojis
    pepe = discord.utils.get(guild.emojis, name="pepe_dance")
    emoji_str = str(pepe) if pepe else "👋"
    
    # Send Rainbow Divider
    current_dir = os.path.dirname(os.path.abspath(__file__))
    rainbow_path = os.path.join(current_dir, 'line-rainbow.gif')
    
    try:
        if os.path.exists(rainbow_path):
            await channel.send(file=discord.File(rainbow_path))
        else:
            print(f"⚠️ Rainbow GIF not found at {rainbow_path}")
    except Exception as e:
        print(f"❌ Failed to post rainbow GIF: {e}")
    
    # Send welcome message with black hole emoji
    black_hole = discord.utils.get(guild.emojis, name="black_hole")
    bh_str = str(black_hole) if black_hole else "⚫"
    
    msg_content = (
        f"{bh_str} Hello {member.mention}, welcome to **QuoTrading**. You are the **{count_str}** member to join. {emoji_str}"
    )
    
    try:
        await channel.send(content=msg_content)
        print(f"✅ Sent welcome message to {member.name}")
    except Exception as e:
        print(f"❌ Failed to send welcome text: {e}")

@bot.event
async def on_ready():
    global STATUS_CHANNEL_ID, STATUS_MESSAGE_ID
    
    print(f'Bot ready: {bot.user}')
    bot.add_view(TicketButton())
    bot.add_view(CloseView())
    
    # Find status channel by name
    for guild in bot.guilds:
        for channel in guild.text_channels:
            if 'server-status' in channel.name.lower():
                STATUS_CHANNEL_ID = channel.id
                # Get pinned message
                pins = await channel.pins()
                if pins:
                    STATUS_MESSAGE_ID = pins[0].id
                break
    
    await send_heartbeat()
    await update_status_message(True)

@bot.command()
@commands.has_permissions(administrator=True)
async def unlock(ctx):
    guild = ctx.guild
    count = 0
    await ctx.send('Unlocking all channels...')
    for channel in guild.channels:
        try:
            if channel.name.startswith('ticket-') or 'moderator' in channel.name.lower():
                continue
            await channel.set_permissions(guild.default_role, view_channel=True, read_message_history=True)
            count += 1
        except:
            pass
    await ctx.send(f'Done! Unlocked {count} channels.')

async def heartbeat_loop():
    while True:
        # Check if API is actually responding
        is_online = True
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(f'{API_URL}/health', timeout=aiohttp.ClientTimeout(total=10)) as resp:
                    if resp.status != 200:
                        is_online = False
        except:
            is_online = False
        
        await send_heartbeat()
        await update_status_message(is_online)
        await asyncio.sleep(300)  # Update every 5 minutes

@bot.event
async def on_connect():
    bot.loop.create_task(heartbeat_loop())

if __name__ == '__main__':
    print('Starting bot...')
    bot.run(TOKEN)

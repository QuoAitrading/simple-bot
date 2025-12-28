#!/bin/bash
pip install discord.py aiohttp
python -u -c "
import discord,os,asyncio,aiohttp
from discord.ext import commands
from discord.ui import Button,View

TOKEN=os.environ.get('DISCORD_BOT_TOKEN')
API_URL=os.environ.get('API_URL','https://quotrading-flask-api.azurewebsites.net')

intents=discord.Intents.default()
intents.guilds=True
bot=commands.Bot(command_prefix='!',intents=intents)
active_tickets=0

async def send_heartbeat():
    try:
        async with aiohttp.ClientSession() as s:
            await s.post(f'{API_URL}/api/discord/heartbeat',json={'servers':len(bot.guilds),'active_tickets':active_tickets})
    except:pass

async def send_ticket_event(e):
    try:
        async with aiohttp.ClientSession() as s:
            await s.post(f'{API_URL}/api/discord/ticket',json={'event':e})
    except:pass

class TicketButton(View):
    def __init__(self):super().__init__(timeout=None)
    @discord.ui.button(label='Create ticket',style=discord.ButtonStyle.blurple,custom_id='create_ticket_btn')
    async def cb(self,x,btn):
        global active_tickets
        g=x.guild;u=x.user
        c=discord.utils.get(g.categories,name='Support')
        if not c:c=await g.create_category(name='Support')
        e=discord.utils.get(g.text_channels,name=f'ticket-{u.name.lower()}')
        if e:
            await x.response.send_message(f'You have a ticket: {e.mention}',ephemeral=True)
            return
        o={g.default_role:discord.PermissionOverwrite(read_messages=False),u:discord.PermissionOverwrite(read_messages=True,send_messages=True),g.me:discord.PermissionOverwrite(read_messages=True,send_messages=True)}
        ch=await g.create_text_channel(name=f'ticket-{u.name.lower()}',category=c,overwrites=o)
        await ch.send(f'Welcome {u.mention}! Describe your issue.',view=CloseView())
        await x.response.send_message(f'Ticket: {ch.mention}',ephemeral=True)
        active_tickets+=1
        await send_ticket_event('created')

class CloseView(View):
    def __init__(self):super().__init__(timeout=None)
    @discord.ui.button(label='Close',style=discord.ButtonStyle.red,custom_id='close_ticket_btn')
    async def cb(self,x,btn):
        global active_tickets
        if not x.channel.name.startswith('ticket-'):
            await x.response.send_message('Not a ticket',ephemeral=True)
            return
        await x.response.send_message('Closing...')
        active_tickets=max(0,active_tickets-1)
        await send_ticket_event('closed')
        await asyncio.sleep(3)
        await x.channel.delete()

@bot.event
async def on_ready():
    print(f'Bot ready: {bot.user}')
    bot.add_view(TicketButton())
    bot.add_view(CloseView())
    await send_heartbeat()

async def heartbeat_loop():
    while True:
        await send_heartbeat()
        print('Heartbeat sent')
        await asyncio.sleep(60)

@bot.event
async def on_connect():
    bot.loop.create_task(heartbeat_loop())

bot.run(TOKEN)
"

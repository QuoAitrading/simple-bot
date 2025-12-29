"""Quick check of current channel permissions"""

import discord
import json
import os

TOKEN = None
try:
    with open(os.path.join(os.path.dirname(__file__), 'config.json'), 'r') as f:
        TOKEN = json.load(f).get('bot_token')
except:
    pass

if not TOKEN:
    TOKEN = os.environ.get('DISCORD_BOT_TOKEN')

intents = discord.Intents.default()
intents.guilds = True
client = discord.Client(intents=intents)

@client.event
async def on_ready():
    print('='*50)
    print('CHANNEL PERMISSION CHECK')
    print('='*50)
    
    guild = client.guilds[0]
    
    visible = 0
    hidden = 0
    can_type = 0
    
    for channel in guild.text_channels:
        perms = channel.permissions_for(guild.default_role)
        
        if perms.view_channel:
            visible += 1
            status = "✅ VISIBLE"
            if perms.send_messages:
                can_type += 1
                status += " + CAN TYPE"
            else:
                status += " (read-only)"
        else:
            hidden += 1
            status = "❌ HIDDEN"
        
        print(f'{status}: {channel.name}')
    
    print('='*50)
    print(f'SUMMARY:')
    print(f'  ✅ Visible to everyone: {visible}')
    print(f'  ✏️  Can type: {can_type}')
    print(f'  ❌ Hidden: {hidden}')
    print('='*50)
    
    await client.close()

client.run(TOKEN)

"""Add YouTube links to prop firm education channel"""

import discord
import asyncio
import json
import os

TOKEN = None
try:
    with open(os.path.join(os.path.dirname(__file__), 'config.json'), 'r') as f:
        TOKEN = json.load(f).get('bot_token')
except:
    pass

intents = discord.Intents.default()
intents.guilds = True
client = discord.Client(intents=intents)

@client.event
async def on_ready():
    print(f'Connected as {client.user}')
    guild = client.guilds[0]
    
    # Find education channel
    edu = None
    for ch in guild.text_channels:
        if 'prop-firm-education' in ch.name:
            edu = ch
            break
    
    if not edu:
        print('Education channel not found')
        await client.close()
        return
    
    await edu.send("""
# 🎬 Video Resources

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

**Prop Firms EXPLAINED (Beginners Must-Watch)**
https://youtu.be/9iNfy94v-v0

**$1.2M Prop Firm Trading - What I'd Do Differently**
https://youtu.be/2AO4HFEfFoc

**Full Guide To Make Money From Prop Firm Trading 2025**
https://youtu.be/I2QHb8_hIyo

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
""")
    
    print('Added videos!')
    await client.close()

client.run(TOKEN)

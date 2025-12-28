"""Setup server status channel - read only with status message"""

import discord
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
    print('Connected')
    guild = client.guilds[0]
    
    ai_cat = None
    for cat in guild.categories:
        if 'ai automation' in cat.name.lower():
            ai_cat = cat
            break
    
    if not ai_cat:
        print('AI Automation category not found')
        await client.close()
        return
    
    # Find and delete old server-status channel
    for ch in ai_cat.channels:
        if 'server-status' in ch.name.lower() or 'status' in ch.name.lower():
            await ch.delete()
            print('Deleted old status channel')
            break
    
    # Create new read-only status channel
    overwrites = {
        guild.default_role: discord.PermissionOverwrite(
            read_messages=True,
            send_messages=False,
            add_reactions=False
        ),
        guild.me: discord.PermissionOverwrite(
            read_messages=True,
            send_messages=True
        )
    }
    
    status_channel = await guild.create_text_channel(
        name='🟢│server-status',
        category=ai_cat,
        overwrites=overwrites
    )
    print('Created status channel')
    
    # Post status message
    msg = await status_channel.send("""
# 🟢 All Systems Operational

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

**Last Checked:** Just now

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
""")
    
    # Pin the message
    await msg.pin()
    print('Posted and pinned status message')
    
    # Save channel and message ID for the bot to update
    config_path = os.path.join(os.path.dirname(__file__), 'status_config.json')
    with open(config_path, 'w') as f:
        json.dump({
            'channel_id': status_channel.id,
            'message_id': msg.id
        }, f)
    print('Saved status config')
    
    print('Done!')
    await client.close()

client.run(TOKEN)

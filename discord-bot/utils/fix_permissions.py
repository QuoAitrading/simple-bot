"""Unblock all channels and fix permissions"""

import discord
import json
import os
import asyncio

# Try config.json first, then environment variable
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

# Channels where users CAN type and react with emojis
CHAT_CHANNELS = ['ai-chat', 'profits', 'general', 'announcement']

# Channels that should be read-only (view but no type)
READ_ONLY_CHANNELS = ['introduction', 'disclaimer', 'server-rules', 'how-it-works', 'server-status', 'upgrade-premium']

@client.event
async def on_ready():
    print('Connected')
    guild = client.guilds[0]
    
    count = 0
    for channel in guild.channels:
        try:
            # Skip ticket channels and mod channels
            if channel.name.startswith('ticket-') or 'moderator' in channel.name.lower():
                continue
            
            # Check channel type
            channel_name_lower = channel.name.lower()
            
            # Is it a text channel?
            if isinstance(channel, discord.TextChannel):
                # Check if it's a chat channel (users can type)
                is_chat = any(chat in channel_name_lower for chat in CHAT_CHANNELS)
                
                # Check if it's read-only
                is_readonly = any(ro in channel_name_lower for ro in READ_ONLY_CHANNELS)
                
                if is_chat:
                    # Users can view, send messages, attach files, AND use emojis
                    await channel.set_permissions(guild.default_role, 
                        view_channel=True, 
                        read_message_history=True,
                        send_messages=True,
                        attach_files=True,
                        embed_links=True,
                        add_reactions=True,
                        use_external_emojis=True)
                    print(f'[CHAT] {channel.name} - can type + pictures + emojis')
                elif is_readonly:
                    # Users can view but NOT send messages
                    await channel.set_permissions(guild.default_role, 
                        view_channel=True, 
                        read_message_history=True,
                        send_messages=False)
                    print(f'[READ ONLY] {channel.name}')
                else:
                    # Default: visible, can read history
                    await channel.set_permissions(guild.default_role, 
                        view_channel=True, 
                        read_message_history=True)
                    print(f'[VISIBLE] {channel.name}')
                count += 1
            
            # Forum channels
            elif isinstance(channel, discord.ForumChannel):
                await channel.set_permissions(guild.default_role, 
                    view_channel=True, 
                    read_message_history=True,
                    send_messages=True,
                    create_public_threads=True)
                print(f'[FORUM] {channel.name} - can post')
                count += 1
            
            # Categories
            elif isinstance(channel, discord.CategoryChannel):
                await channel.set_permissions(guild.default_role, view_channel=True)
                print(f'[CATEGORY] {channel.name}')
                count += 1
                
        except Exception as e:
            print(f'Error on channel: {e}')
    
    print(f'Done! Updated {count} channels.')
    await client.close()

client.run(TOKEN)

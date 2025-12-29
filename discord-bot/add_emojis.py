"""Add custom trading/finance emojis to the Discord server using emoji.gg"""

import discord
import json
import os
import aiohttp
import asyncio

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

# We'll fetch emojis from emoji.gg API
EMOJI_GG_API = "https://emoji.gg/api/"

# Categories we want to search for (trading themed)
SEARCH_TERMS = ["money", "stonks", "chart", "pepe", "cat", "fire", "rocket", "party", "rich"]

@client.event
async def on_ready():
    print('='*50)
    print('EMOJI UPLOADER - emoji.gg')
    print('='*50)
    
    guild = client.guilds[0]
    
    # Get existing emoji names
    existing = set(e.name.lower() for e in guild.emojis)
    print(f'Current emojis: {len(guild.emojis)}')
    print()
    
    added = 0
    max_to_add = 20  # Limit to not overwhelm
    
    async with aiohttp.ClientSession() as session:
        # Fetch emoji list from emoji.gg
        print('Fetching emojis from emoji.gg...')
        try:
            async with session.get(EMOJI_GG_API) as resp:
                if resp.status == 200:
                    all_emojis = await resp.json()
                    print(f'Found {len(all_emojis)} emojis available')
                    
                    # Filter relevant ones
                    trading_emojis = []
                    for emoji in all_emojis:
                        title = emoji.get('title', '').lower()
                        # Check if matches any of our search terms
                        if any(term in title for term in SEARCH_TERMS):
                            trading_emojis.append(emoji)
                    
                    print(f'Filtered to {len(trading_emojis)} trading-related emojis')
                    print()
                    
                    # Add emojis
                    for emoji in trading_emojis[:max_to_add]:
                        name = emoji.get('slug', emoji.get('title', 'emoji')).replace('-', '_')[:32]
                        
                        if name.lower() in existing:
                            print(f'⏭️  {name} - already exists')
                            continue
                        
                        try:
                            # Get the image URL
                            image_url = emoji.get('image')
                            if not image_url:
                                continue
                            
                            async with session.get(image_url) as img_resp:
                                if img_resp.status == 200:
                                    image_data = await img_resp.read()
                                    
                                    # Check size (must be under 256KB)
                                    if len(image_data) > 256 * 1024:
                                        print(f'⏭️  {name} - too large')
                                        continue
                                    
                                    await guild.create_custom_emoji(name=name, image=image_data)
                                    print(f'✅ {name} - added!')
                                    added += 1
                                    existing.add(name.lower())
                                    
                                    await asyncio.sleep(1.5)  # Rate limit protection
                        except discord.HTTPException as e:
                            if e.code == 30008:
                                print('Max emojis reached!')
                                break
                            print(f'❌ {name} - {e}')
                        except Exception as e:
                            print(f'❌ {name} - {e}')
                else:
                    print(f'Failed to fetch emoji list: {resp.status}')
        except Exception as e:
            print(f'Error: {e}')
    
    print()
    print('='*50)
    print(f'DONE! Added {added} new emojis')
    print('='*50)
    
    await client.close()

client.run(TOKEN)

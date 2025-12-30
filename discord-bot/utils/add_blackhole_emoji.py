"""
Script to download, resize, and add the Black Hole emoji
"""
import discord
from discord.ext import commands
import json
import os
import aiohttp
import asyncio
from io import BytesIO
import sys

# Try to import Pillow
try:
    from PIL import Image, ImageSequence
except ImportError:
    print("❌ Pillow (PIL) is not installed. Please install it using 'pip install Pillow'")
    # We will try to run anyway, but resizing will fail.
    sys.exit(1)

config_path = os.path.join(os.path.dirname(__file__), 'config.json')
with open(config_path, 'r') as f:
    config = json.load(f)

BOT_TOKEN = config.get('bot_token')
GIF_URL = "https://media1.tenor.com/m/AxUkFJM6bxEAAAAd/black-hole-singularity.gif"
TARGET_SIZE = (54, 54) # Standard emoji internal size is often small (32/64/128)

intents = discord.Intents.default()
intents.guilds = True
intents.emojis = True
bot = commands.Bot(command_prefix='!', intents=intents)

@bot.event
async def on_ready():
    guild = bot.guilds[0]
    print(f"Connected to {guild.name}")
    
    # Check if exists
    for e in guild.emojis:
        if e.name == "black_hole":
            print(f"✅ Emoji :black_hole: already exists! ID: {e.id}")
            print(f"EMOJI_STRING: <a:black_hole:{e.id}>") 
            await bot.close()
            return

    print("Downloading GIF...")
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(GIF_URL) as resp:
                if resp.status == 200:
                    raw_data = await resp.read()
                    print(f"Original size: {len(raw_data)/1024:.2f} KB")
                    
                    # Resize
                    print("Resizing GIF...")
                    try:
                        im = Image.open(BytesIO(raw_data))
                        
                        frames = []
                        duration = im.info.get('duration', 100)
                        loop = im.info.get('loop', 0)
                        
                        for frame in ImageSequence.Iterator(im):
                            # Resize frame
                            # Use LANCZOS if available (Pillow 10+), else ANTIALIAS
                            resample = Image.Resampling.LANCZOS if hasattr(Image, 'Resampling') else Image.ANTIALIAS
                            
                            # Preserve aspect ratio or squash? Squash to square is better for stamps.
                            # But let's try to fit in square.
                            f = frame.copy()
                            f.thumbnail(TARGET_SIZE, resample)
                            
                            # Create a new blank frame to center it? 
                            # Simplify: Just resize to thumbnail.
                            # Standardize to rgba
                            f = f.convert("RGBA")
                            frames.append(f)
                            
                        # Save resized
                        output = BytesIO()
                        frames[0].save(
                            output, 
                            format='GIF', 
                            save_all=True, 
                            append_images=frames[1:], 
                            loop=loop, 
                            duration=duration, 
                            optimize=True,
                            disposal=2 # Restore to background
                        )
                        resized_data = output.getvalue()
                        print(f"Resized size: {len(resized_data)/1024:.2f} KB")
                        
                        print("Uploading emoji...")
                        emoji = await guild.create_custom_emoji(name="black_hole", image=resized_data)
                        print(f"✅ Created new emoji: <a:{emoji.name}:{emoji.id}>")
                        print(f"EMOJI_STRING: <a:{emoji.name}:{emoji.id}>")
                        
                    except Exception as e:
                        print(f"❌ Resize failed: {e}")
                        
                else:
                    print(f"❌ Failed to download GIF: {resp.status}")
    except Exception as e:
        print(f"❌ Error: {e}")

    await bot.close()

if __name__ == "__main__":
    bot.run(BOT_TOKEN)

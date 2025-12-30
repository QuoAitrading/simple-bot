"""
Upload custom emoji to server
"""
import discord
from discord.ext import commands
import json
import os

config_path = os.path.join(os.path.dirname(__file__), 'config.json')
with open(config_path, 'r') as f:
    config = json.load(f)

BOT_TOKEN = config.get('bot_token')
intents = discord.Intents.default()
# Need emoji management permission
intents.guilds = True
intents.emojis = True
bot = commands.Bot(command_prefix='!', intents=intents)

EMOJI_PATH = os.path.join(os.path.dirname(__file__), 'pepe.gif')

@bot.event
async def on_ready():
    guild = bot.guilds[0]
    
    if os.path.exists(EMOJI_PATH):
        with open(EMOJI_PATH, 'rb') as f:
            image_data = f.read()
            
        try:
            # Check if already exists
            found = False
            for e in guild.emojis:
                if e.name == "pepe_dance":
                    print(f"✅ Emoji :pepe_dance: already exists! ID: {e.id}")
                    found = True
                    break
            
            if not found:
                emoji = await guild.create_custom_emoji(name="pepe_dance", image=image_data)
                print(f"✅ Created new emoji: <a:{emoji.name}:{emoji.id}>")
        except Exception as e:
            print(f"❌ Failed to upload emoji: {e}")
            print("Ensure the bot has 'Manage Emojis' permission and the server has emoji slots available.")
    else:
        print("❌ Image file not found")
    
    await bot.close()

if __name__ == "__main__":
    bot.run(BOT_TOKEN)

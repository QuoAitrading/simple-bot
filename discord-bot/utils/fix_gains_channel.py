"""
Fix permissions for #💸│gains channel.
Allows users to post messages and pictures.
"""
import discord
from discord.ext import commands
import json
import os
from pathlib import Path

def load_token():
    # 1. Try config.json in the same directory
    try:
        config_path = os.path.join(os.path.dirname(__file__), 'config.json')
        if os.path.exists(config_path):
            with open(config_path, 'r') as f:
                config = json.load(f)
                token = config.get('bot_token')
                if token:
                    return token
    except Exception as e:
        print(f"Warning: Failed to load config.json: {e}")

    # 2. Try environment variable
    token = os.environ.get('DISCORD_BOT_TOKEN')
    if token:
        return token

    # 3. Try reading .env in parent directory
    try:
        env_path = Path(__file__).parent.parent / '.env'
        if env_path.exists():
            with open(env_path, 'r') as f:
                for line in f:
                    if line.startswith('DISCORD_BOT_TOKEN='):
                        return line.split('=')[1].strip().strip('"').strip("'")
                    elif line.startswith('bot_token='):
                        return line.split('=')[1].strip().strip('"').strip("'")
    except Exception as e:
        print(f"Warning: Failed to parse .env: {e}")

    return None

TOKEN = load_token()

if not TOKEN:
    print("[ERROR] Could not find bot token!")
    print("Checked: config.json (bot_token), Environment (DISCORD_BOT_TOKEN), and .env")
    print("Please ensure your configuration is set up.")
    exit(1)

intents = discord.Intents.default()
intents.guilds = True
bot = commands.Bot(command_prefix='!', intents=intents)

@bot.event
async def on_ready():
    try:
        if len(bot.guilds) == 0:
            print("[ERROR] Bot is not in any guilds!")
            await bot.close()
            return

        guild = bot.guilds[0]
        print(f"Connected to {guild.name}")
        
        # Find the gains channel (try multiple name formats)
        channel = None
        for ch in guild.text_channels:
            if "gains" in ch.name.lower():
                channel = ch
                break
        
        if not channel:
            print("[ERROR] Could not find #gains channel!")
        else:
            print(f"Found channel: {channel.name}")
            
            # Set permissions for @everyone to post and attach files
            try:
                overwrites = channel.overwrites_for(guild.default_role)
                overwrites.send_messages = True
                overwrites.attach_files = True
                overwrites.embed_links = True
                overwrites.read_messages = True
                overwrites.read_message_history = True
                overwrites.add_reactions = True
                
                await channel.set_permissions(guild.default_role, overwrite=overwrites)
                
                print(f"[SUCCESS] Fixed permissions for #{channel.name}")
                print("   - Send Messages: [OK]")
                print("   - Attach Files (Pictures): [OK]")
                print("   - Embed Links: [OK]")
                print("   - Add Reactions: [OK]")
            except Exception as e:
                print(f"[ERROR] Failed to set permissions: {e}")

    except Exception as e:
        print(f"[ERROR] Error in on_ready: {e}")
    finally:
        await bot.close()

if __name__ == "__main__":
    try:
        bot.run(TOKEN)
    except Exception as e:
        print(f"[ERROR] Failed to run bot: {e}")

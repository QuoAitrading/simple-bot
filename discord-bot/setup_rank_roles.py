"""
Script to setup Rank Roles in the Discord Server.
Creates roles with specific names, colors, and hoist settings.
Run this ONCE to setup the server.
"""
import discord
from discord.ext import commands
import json
import os
import asyncio

# Config
config_path = os.path.join(os.path.dirname(__file__), 'config.json')
with open(config_path, 'r') as f:
    config = json.load(f)

TOKEN = config.get('bot_token')

intents = discord.Intents.default()
intents.guilds = True
intents.members = True
bot = commands.Bot(command_prefix='!', intents=intents)

# Rank Definitions
RANKS = [
    # (Name, Color Hex, Hoist)
    ("Quo Supreme", 0xFFD700, True),     # Gold
    ("Quo Mastermind", 0x992D22, True),  # Dark Red
    ("Quo Visionary", 0x71368A, True),   # Deep Purple
    ("Quo Predictor", 0xE91E63, True),   # Magenta
    ("Quo Automator", 0xF1C40F, False),  # Yellow
    ("Quo Executor", 0x9B59B6, False),   # Purple
    ("Quo Strategist", 0x3498DB, False), # Blue
    ("Quo Analyst", 0x1ABC9C, False),    # Cyan
    ("Quo Trader", 0x2ECC71, False),     # Green
    ("Quo Novice", 0x95A5A6, False)      # Grey
]

@bot.event
async def on_ready():
    guild = bot.guilds[0]
    print(f"Connected to {guild.name}")
    print("Setting up Roles...")

    # Create Roles
    for name, color_value, hoist in RANKS:
        existing = discord.utils.get(guild.roles, name=name)
        if existing:
            print(f"✅ Role '{name}' already exists.")
            # Optional: Update color/hois if needed?
            # await existing.edit(color=discord.Color(color_value), hoist=hoist)
        else:
            try:
                print(f"⏳ Creating Role '{name}'...")
                new_role = await guild.create_role(
                    name=name,
                    color=discord.Color(color_value),
                    hoist=hoist,
                    reason="Rank System Setup"
                )
                print(f"✨ Created Role: {new_role.name}")
            except Exception as e:
                print(f"❌ Failed to create '{name}': {e}")
    
    # Re-order roles?
    # Usually manual is safer, but we can try to ensure hierarchy.
    # Logic: High ranks should be at top.
    # This requires 'manage_roles' permission and hierarchy. Only if bot is above them.
    
    print("\n✅ Setup Complete! You may need to manually drag the roles up/down in Server Settings if they are not in order.")
    await bot.close()

if __name__ == "__main__":
    bot.run(TOKEN)

import discord
import os
import json

# Try to load token
TOKEN = os.getenv('DISCORD_BOT_TOKEN')
if not TOKEN:
    try:
        with open('config.json', 'r') as f:
            TOKEN = json.load(f).get('bot_token')
    except:
        pass

print(f"Token loaded? {'YES' if TOKEN else 'NO'}")
if TOKEN:
    print(f"Token ends: ...{TOKEN[-5:]}")

intents = discord.Intents.default()
intents.message_content = True
intents.members = True

client = discord.Client(intents=intents)

@client.event
async def on_ready():
    print(f'Logged in as {client.user} (ID: {client.user.id})')
    print('------')

@client.event
async def on_message(message):
    print(f"Message from {message.author}: {message.content}")

client.run(TOKEN)

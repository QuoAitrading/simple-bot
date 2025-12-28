"""Debug script to check SDK methods for listing accounts"""

import asyncio
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from project_x_py import ProjectX, ProjectXConfig
import json

# Load credentials from config
config_path = os.path.join(os.path.dirname(__file__), 'config.json')
with open(config_path, 'r') as f:
    config = json.load(f)

username = config.get('broker_username')
api_token = config.get('broker_token')

async def main():
    client = ProjectX(username=username, api_key=api_token, config=ProjectXConfig())
    await client.authenticate()
    
    print("\n=== Trying list_accounts (awaited) ===")
    try:
        accounts = await client.list_accounts()
        print(f"list_accounts() returned: {accounts}")
        print(f"Type: {type(accounts)}")
        if accounts:
            print(f"Number of accounts: {len(accounts)}")
            for i, acc in enumerate(accounts):
                print(f"\nAccount {i+1}:")
                print(f"  ID: {getattr(acc, 'id', 'N/A')}")
                print(f"  Name: {getattr(acc, 'name', 'N/A')}")
                print(f"  Balance: {getattr(acc, 'balance', 'N/A')}")
                print(f"  All attrs: {[a for a in dir(acc) if not a.startswith('_')]}")
    except Exception as e:
        print(f"list_accounts() failed: {e}")
        import traceback
        traceback.print_exc()

asyncio.run(main())

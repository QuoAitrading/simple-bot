"""Test script to check what TopStep API returns for account info"""
import sys
from pathlib import Path

# Add src to path
src_path = Path(__file__).parent / "src"
sys.path.insert(0, str(src_path))

from broker_interface import TopStepBroker
import asyncio

# Your credentials
API_TOKEN = "0lqxI8Gt4JRDhbuP9wOoHmdxJE49fIQCxIU+mSbPqGs="
USERNAME = "alvarezjose4201@gmail.com"

print("Creating TopStep broker connection...")
broker = TopStepBroker(api_token=API_TOKEN, username=USERNAME)

print("Connecting...")
if broker.connect():
    print("Connected successfully!\n")
    
    # Try to get account info using different methods
    print("=" * 60)
    print("METHOD 1: list_accounts()")
    print("=" * 60)
    try:
        accounts = asyncio.run(broker.sdk_client.list_accounts())
        print(f"Number of accounts: {len(accounts) if accounts else 0}")
        if accounts:
            for idx, acc in enumerate(accounts):
                print(f"\nAccount {idx + 1}:")
                print(f"  Type: {type(acc)}")
                print(f"  Dir: {dir(acc)}")
                print(f"  Repr: {repr(acc)}")
                
                # Try common attribute names
                for attr in ['id', 'account_id', 'accountId', 'account_number', 'number', 'name', 'balance', 'equity']:
                    if hasattr(acc, attr):
                        print(f"  {attr}: {getattr(acc, attr)}")
        else:
            print("No accounts returned")
    except Exception as e:
        print(f"✗ Error: {e}")
        import traceback
        traceback.print_exc()
    
    print("\n" + "=" * 60)
    print("METHOD 2: get_account_equity()")
    print("=" * 60)
    try:
        equity = broker.get_account_equity()
        print(f"Account Equity: ${equity:,.2f}")
    except Exception as e:
        print(f"✗ Error: {e}")
    
    print("\n" + "=" * 60)
    print("METHOD 3: get_account_info()")
    print("=" * 60)
    try:
        account_info = asyncio.run(broker.sdk_client.get_account_info())
        print(f"Account Info: {account_info}")
        print(f"Type: {type(account_info)}")
        if hasattr(account_info, '__dict__'):
            print(f"Dict: {account_info.__dict__}")
    except Exception as e:
        print(f"✗ Error: {e}")
        import traceback
        traceback.print_exc()
    
    print("\n" + "=" * 60)
    print("METHOD 4: SDK account_info property")
    print("=" * 60)
    print(f"account_info: {broker.sdk_client.account_info}")
    print(f"account_name: {broker.sdk_client.account_name}")
    
    print("\n" + "=" * 60)
    print("METHOD 5: SDK client attributes")
    print("=" * 60)
    print(f"SDK Client type: {type(broker.sdk_client)}")
    print(f"SDK Client dir: {[x for x in dir(broker.sdk_client) if not x.startswith('_')]}")
    
    # Check if there's an account property
    if hasattr(broker.sdk_client, 'account'):
        print(f"\nSDK has 'account' property:")
        print(f"  Type: {type(broker.sdk_client.account)}")
        print(f"  Value: {broker.sdk_client.account}")
    
    print("\n" + "=" * 60)
    print("METHOD 4: Check broker object")
    print("=" * 60)
    print(f"Broker attributes: {[x for x in dir(broker) if not x.startswith('_')]}")
    
    broker.disconnect()
    print("\n✓ Disconnected")
else:
    print("✗ Failed to connect")

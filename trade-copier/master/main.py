"""
Master Main - Entry point for YOU to run locally
Monitors your trades and broadcasts them to followers
"""

import asyncio
import logging
import json
import os
import sys
import threading
from datetime import datetime

# Add parent to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from shared.broker_client import BrokerClient
from signal_broadcaster import SignalBroadcaster
from position_monitor import PositionMonitor

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s | %(message)s',
    datefmt='%H:%M:%S'
)
logger = logging.getLogger(__name__)


def print_header():
    """Print startup header"""
    print("""
╔══════════════════════════════════════════════════════════════╗
║                                                              ║
║      🎯  TRADE COPIER - MASTER SYSTEM                       ║
║                                                              ║
║      You trade. Followers copy. Automatically.              ║
║                                                              ║
╚══════════════════════════════════════════════════════════════╝
""")


def load_config() -> dict:
    """Load master configuration"""
    config_path = os.path.join(os.path.dirname(__file__), 'config.json')
    
    if not os.path.exists(config_path):
        # Create default config
        default_config = {
            "api_url": "https://quotrading-flask-api.azurewebsites.net",
            "master_key": "YOUR_MASTER_KEY",
            "broker": {
                "username": "YOUR_EMAIL@gmail.com",
                "api_token": "YOUR_API_TOKEN"
            },
            "copy_enabled": True,
            "poll_interval": 0.1
        }
        with open(config_path, 'w') as f:
            json.dump(default_config, f, indent=2)
        print(f"⚠️  Created default config at: {config_path}")
        print(f"   Please edit this file with your credentials and restart.")
        return None
    
    with open(config_path, 'r') as f:
        return json.load(f)


async def main():
    """Main entry point"""
    print_header()
    
    # Load config
    config = load_config()
    if not config:
        return
    
    # Validate config
    if config['master_key'] == 'YOUR_MASTER_KEY':
        print("❌ Please edit config.json with your master key")
        return
    
    # Create broker client (your master account)
    broker = BrokerClient(
        username=config['broker']['username'],
        api_token=config['broker']['api_token'],
        name="Master Account"
    )
    
    # Create signal broadcaster
    broadcaster = SignalBroadcaster(
        api_url=config['api_url'],
        master_key=config['master_key']
    )
    
    print("📶 Connecting to broker...")
    
    # Connect to broker
    if not await broker.connect():
        print("❌ Failed to connect to broker. Check your credentials.")
        return
    
    # Start broadcaster
    await broadcaster.start()
    
    # Create and start position monitor
    monitor = PositionMonitor(
        broker=broker,
        broadcaster=broadcaster,
        poll_interval=config.get('poll_interval', 0.5)
    )
    await monitor.start()
    
    # Get initial follower count
    followers = await broadcaster.refresh_followers()
    
    print(f"""
✅ Master system running!
   
   Connected followers: {len(followers)}
   
   🎯 Your trades will be copied to all connected followers in real-time.
   
   Open your trading platform and trade normally.
   Every trade you make will be broadcast instantly.
   
   Press Ctrl+C to stop.
""")
    
    # Keep running
    try:
        while True:
            # Periodically refresh follower list
            await broadcaster.refresh_followers()
            await asyncio.sleep(30)
    except KeyboardInterrupt:
        print("\n⏹️  Stopping...")
    finally:
        await monitor.stop()
        await broadcaster.stop()
        await broker.disconnect()
        print("👋 Goodbye!")


if __name__ == "__main__":
    asyncio.run(main())

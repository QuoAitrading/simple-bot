"""
Follower Main - Entry point for customers to run the signal receiver
Simple terminal-based UI showing connection status
"""

import asyncio
import logging
import json
import os
import sys
from datetime import datetime

# Add parent to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from shared.broker_client import BrokerClient
from signal_receiver import SignalReceiver

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s | %(message)s',
    datefmt='%H:%M:%S'
)
logger = logging.getLogger(__name__)

# Colors for terminal
class Colors:
    GREEN = '\033[92m'
    RED = '\033[91m'
    YELLOW = '\033[93m'
    BLUE = '\033[94m'
    CYAN = '\033[96m'
    RESET = '\033[0m'
    BOLD = '\033[1m'


def print_header():
    """Print startup header"""
    print(f"""
{Colors.CYAN}╔══════════════════════════════════════════════════════════╗
║                                                              ║
║      📡  TRADE COPIER - FOLLOWER CLIENT                     ║
║                                                              ║
║      Listens to Master signals and executes locally         ║
║                                                              ║
╚══════════════════════════════════════════════════════════════╝{Colors.RESET}
""")


def load_config() -> dict:
    """Load follower configuration"""
    config_path = os.path.join(os.path.dirname(__file__), 'config.json')
    
    if not os.path.exists(config_path):
        # Create default config
        default_config = {
            "master_api_url": "https://quotrading-flask-api.azurewebsites.net",
            "follower_key": "YOUR_FOLLOWER_KEY",
            "follower_name": "My Account",
            "broker": {
                "username": "YOUR_EMAIL@gmail.com",
                "api_token": "YOUR_API_TOKEN"
            },
            "copy_enabled": True
        }
        with open(config_path, 'w') as f:
            json.dump(default_config, f, indent=2)
        print(f"{Colors.YELLOW}⚠️  Created default config at: {config_path}")
        print(f"   Please edit this file with your credentials and restart.{Colors.RESET}")
        return None
    
    with open(config_path, 'r') as f:
        return json.load(f)


def print_status(receiver: SignalReceiver, broker: BrokerClient):
    """Print current status"""
    r_status = receiver.get_status()
    b_status = broker.get_status()
    
    conn_color = Colors.GREEN if r_status['connected'] else Colors.RED
    conn_text = "🟢 Connected" if r_status['connected'] else "🔴 Disconnected"
    
    copy_color = Colors.GREEN if r_status['copy_enabled'] else Colors.YELLOW
    copy_text = "✅ Enabled" if r_status['copy_enabled'] else "❌ Disabled"
    
    print(f"""
{Colors.BOLD}━━━ STATUS ━━━{Colors.RESET}
  Master Connection: {conn_color}{conn_text}{Colors.RESET}
  Copy Trading:      {copy_color}{copy_text}{Colors.RESET}
  Signals Received:  {r_status['signals_received']}
  Signals Executed:  {r_status['signals_executed']}
  Account Balance:   ${b_status['balance']:,.2f}
""")


async def main():
    """Main entry point"""
    print_header()
    
    # Load config
    config = load_config()
    if not config:
        return
    
    # Validate config
    if config['follower_key'] == 'YOUR_FOLLOWER_KEY':
        print(f"{Colors.RED}❌ Please edit config.json with your follower key{Colors.RESET}")
        return
    
    # Create broker client
    broker = BrokerClient(
        username=config['broker']['username'],
        api_token=config['broker']['api_token'],
        name="My Account"
    )
    
    # Create signal receiver
    receiver = SignalReceiver(
        api_url=config['master_api_url'],
        follower_key=config['follower_key'],
        follower_name=config['follower_name']
    )
    receiver.copy_enabled = config.get('copy_enabled', True)
    
    print(f"{Colors.BLUE}📶 Connecting to broker...{Colors.RESET}")
    
    # Connect to broker
    if not await broker.connect():
        print(f"{Colors.RED}❌ Failed to connect to broker. Check your credentials.{Colors.RESET}")
        return
    
    print(f"{Colors.BLUE}📡 Connecting to Master...{Colors.RESET}")
    
    # Connect to master
    if not await receiver.connect(broker):
        print(f"{Colors.RED}❌ Failed to connect to Master. Check your follower key.{Colors.RESET}")
        await broker.disconnect()
        return
    
    print_status(receiver, broker)
    print(f"{Colors.GREEN}🎧 Listening for signals... Press Ctrl+C to stop{Colors.RESET}\n")
    
    # Signal handler for pretty printing
    def on_signal(signal):
        color = Colors.GREEN if signal.side == "BUY" else Colors.RED
        print(f"{color}📥 SIGNAL: {signal.action} {signal.side} {signal.quantity} {signal.symbol} @ {signal.entry_price}{Colors.RESET}")
    
    receiver.on_signal = on_signal
    
    try:
        # Start receiving loop
        await receiver.start_receiving()
    except KeyboardInterrupt:
        print(f"\n{Colors.YELLOW}⏹️  Stopping...{Colors.RESET}")
    finally:
        await receiver.disconnect()
        await broker.disconnect()
        print(f"{Colors.CYAN}👋 Goodbye!{Colors.RESET}")


if __name__ == "__main__":
    asyncio.run(main())

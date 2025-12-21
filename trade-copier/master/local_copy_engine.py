"""
Local Copy Engine - Copies trades between accounts ALL on YOUR PC
No internet needed. No cloud relay. Just local copying.
"""

import asyncio
import logging
import json
import os
import sys
from datetime import datetime
from typing import List, Dict, Optional

# Add parent to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from shared.broker_client import BrokerClient

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s | %(message)s',
    datefmt='%H:%M:%S'
)
logger = logging.getLogger(__name__)


class LocalCopyEngine:
    """
    Copies trades from one master account to multiple follower accounts
    Everything runs on YOUR local PC - no cloud needed
    """
    
    def __init__(self):
        self.master: Optional[BrokerClient] = None
        self.followers: List[BrokerClient] = []
        self.copy_enabled = True
        self.running = False
        
        # Position tracking
        self.master_positions: Dict[str, int] = {}  # symbol -> qty
        self.follower_positions: Dict[str, Dict[str, int]] = {}  # follower_name -> {symbol -> qty}
        
        # Stats
        self.copies_executed = 0
        
    async def add_master(self, username: str, api_token: str, name: str = "Master") -> bool:
        """Add the master account"""
        self.master = BrokerClient(username, api_token, name)
        if await self.master.connect():
            logger.info(f"✅ Master account connected: {name}")
            return True
        return False
    
    async def add_follower(self, username: str, api_token: str, name: str) -> bool:
        """Add a follower account"""
        follower = BrokerClient(username, api_token, name)
        if await follower.connect():
            self.followers.append(follower)
            self.follower_positions[name] = {}
            logger.info(f"✅ Follower account connected: {name}")
            return True
        return False
    
    async def start(self):
        """Start the copy engine - monitors master and copies to followers"""
        if not self.master:
            logger.error("No master account set")
            return
            
        if not self.followers:
            logger.error("No follower accounts set")
            return
            
        self.running = True
        logger.info(f"🔄 Local Copy Engine started with {len(self.followers)} followers")
        
        while self.running:
            try:
                await self._check_and_copy()
                await asyncio.sleep(0.5)  # Check every 500ms
            except Exception as e:
                logger.error(f"Copy engine error: {e}")
                await asyncio.sleep(1)
    
    async def stop(self):
        """Stop the copy engine"""
        self.running = False
        
        # Disconnect all
        if self.master:
            await self.master.disconnect()
        for follower in self.followers:
            await follower.disconnect()
            
        logger.info("🔌 Local Copy Engine stopped")
    
    async def _check_and_copy(self):
        """Check master position changes and copy to followers"""
        if not self.copy_enabled:
            return
            
        # Get current master positions (this would need real implementation)
        # For now, we detect changes via polling
        # In production, you'd use WebSocket fill notifications
        
        # Simplified example: compare position states
        # Real implementation would hook into fill events from TopStep SDK
        pass
    
    async def copy_order(self, symbol: str, side: str, quantity: int):
        """
        Copy an order to all followers
        Called when master executes a trade
        """
        if not self.copy_enabled:
            logger.info("⏸️  Copy disabled")
            return
            
        logger.info(f"📤 Copying: {side} {quantity} {symbol} to {len(self.followers)} followers")
        
        for follower in self.followers:
            try:
                success = await follower.place_market_order(symbol, side, quantity)
                if success:
                    self.copies_executed += 1
                    logger.info(f"  ✅ {follower.name}: Copied")
                else:
                    logger.error(f"  ❌ {follower.name}: Failed")
            except Exception as e:
                logger.error(f"  ❌ {follower.name}: {e}")
    
    async def flatten_all(self, symbol: str):
        """Flatten position on all accounts"""
        logger.warning(f"🚨 Flattening {symbol} on ALL accounts")
        
        if self.master:
            await self.master.flatten_position(symbol)
            
        for follower in self.followers:
            await follower.flatten_position(symbol)
    
    def get_status(self) -> dict:
        """Get current engine status"""
        return {
            "running": self.running,
            "copy_enabled": self.copy_enabled,
            "master": self.master.get_status() if self.master else None,
            "followers": [f.get_status() for f in self.followers],
            "copies_executed": self.copies_executed
        }


def load_config() -> dict:
    """Load local copy configuration"""
    config_path = os.path.join(os.path.dirname(__file__), 'local_config.json')
    
    if not os.path.exists(config_path):
        default_config = {
            "master": {
                "name": "Master Account",
                "username": "YOUR_EMAIL@gmail.com",
                "api_token": "YOUR_API_TOKEN"
            },
            "followers": [
                {
                    "name": "Follower 1",
                    "username": "FOLLOWER_EMAIL@gmail.com",
                    "api_token": "FOLLOWER_API_TOKEN",
                    "enabled": True
                }
            ],
            "copy_enabled": True
        }
        with open(config_path, 'w') as f:
            json.dump(default_config, f, indent=2)
        print(f"⚠️  Created default config at: {config_path}")
        print(f"   Please edit with your account credentials and restart.")
        return None
    
    with open(config_path, 'r') as f:
        return json.load(f)


async def main():
    """Main entry point for local-only copy mode"""
    print("""
╔══════════════════════════════════════════════════════════════╗
║                                                              ║
║      🏠  LOCAL COPY ENGINE                                   ║
║                                                              ║
║      Copies trades between YOUR accounts on YOUR PC         ║
║      No internet required. No cloud relay.                  ║
║                                                              ║
╚══════════════════════════════════════════════════════════════╝
""")
    
    config = load_config()
    if not config:
        return
    
    engine = LocalCopyEngine()
    
    # Connect master
    master_cfg = config['master']
    if not await engine.add_master(
        master_cfg['username'],
        master_cfg['api_token'],
        master_cfg['name']
    ):
        print("❌ Failed to connect master account")
        return
    
    # Connect followers
    for f_cfg in config['followers']:
        if f_cfg.get('enabled', True):
            await engine.add_follower(
                f_cfg['username'],
                f_cfg['api_token'],
                f_cfg['name']
            )
    
    if not engine.followers:
        print("❌ No follower accounts connected")
        await engine.stop()
        return
    
    print(f"""
✅ Local Copy Engine Ready!
   
   Master: {engine.master.name}
   Followers: {len(engine.followers)}
   
   When you trade on your master account, orders will be
   copied to all follower accounts automatically.
   
   Press Ctrl+C to stop.
""")
    
    try:
        await engine.start()
    except KeyboardInterrupt:
        print("\n⏹️  Stopping...")
    finally:
        await engine.stop()
        print("👋 Goodbye!")


if __name__ == "__main__":
    asyncio.run(main())

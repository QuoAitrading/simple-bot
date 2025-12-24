"""
Signal Broadcaster - Sends your trades to all connected followers
This runs on YOUR machine as the master
"""

import asyncio
import logging
import aiohttp
from typing import Dict, List, Optional, Set
from datetime import datetime
from dataclasses import dataclass, field
import json

# Add parent to path for imports
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from shared.signal_protocol import TradeSignal, create_open_signal, create_close_signal, create_flatten_signal

logger = logging.getLogger(__name__)


@dataclass
class ConnectedFollower:
    """A connected follower client"""
    client_id: str
    name: str
    connected_at: str
    last_heartbeat: str
    copy_enabled: bool = True
    signals_received: int = 0
    signals_executed: int = 0


class SignalBroadcaster:
    """
    Broadcasts trade signals from Master to all Followers
    Uses your Flask API as the relay server
    """
    
    def __init__(self, api_url: str, master_key: str):
        """
        Args:
            api_url: Your Flask API URL (e.g. https://quotrading-flask-api.azurewebsites.net)
            master_key: Your master authentication key
        """
        self.api_url = api_url.rstrip('/')
        self.master_key = master_key
        self.session: Optional[aiohttp.ClientSession] = None
        self.connected_followers: Dict[str, ConnectedFollower] = {}
        self.signal_history: List[TradeSignal] = []
        self.broadcasting = False
        
    async def start(self):
        """Start the broadcaster"""
        self.session = aiohttp.ClientSession()
        self.broadcasting = True
        logger.info("📡 Signal Broadcaster started")
        
    async def stop(self):
        """Stop the broadcaster"""
        self.broadcasting = False
        if self.session:
            await self.session.close()
        logger.info("📡 Signal Broadcaster stopped")
    
    async def broadcast_signal(self, signal: TradeSignal) -> int:
        """
        Broadcast a trade signal to all connected followers
        
        Returns: Number of followers who received it
        """
        if not self.broadcasting or not self.session:
            logger.warning("Broadcaster not started")
            return 0
            
        self.signal_history.append(signal)
        
        # Send to API relay endpoint with retry
        for attempt in range(3):
            try:
                async with self.session.post(
                    f"{self.api_url}/copier/broadcast",
                    json={
                        "master_key": self.master_key,
                        "signal": signal.to_dict()
                    },
                    timeout=aiohttp.ClientTimeout(total=5)
                ) as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        received_count = data.get("received_count", 0)
                        logger.info(f"📤 Signal broadcast: {signal.action} {signal.side} {signal.quantity} {signal.symbol} → {received_count} followers")
                        return received_count
                    else:
                        logger.warning(f"⚠️ Broadcast failed (attempt {attempt+1}/3): {resp.status}")
                        await asyncio.sleep(0.5)
            except Exception as e:
                logger.warning(f"⚠️ Broadcast error (attempt {attempt+1}/3): {e}")
                await asyncio.sleep(0.5)
        
        logger.error("❌ Signal broadcast failed after 3 attempts")
        return 0
    
    async def refresh_followers(self) -> List[ConnectedFollower]:
        """Get list of currently connected followers from server"""
        if not self.session:
            return []
            
        try:
            async with self.session.get(
                f"{self.api_url}/copier/followers",
                params={"master_key": self.master_key},
                timeout=aiohttp.ClientTimeout(total=5)
            ) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    followers = []
                    for f in data.get("followers", []):
                        follower = ConnectedFollower(
                            client_id=f["client_id"],
                            name=f["name"],
                            connected_at=f["connected_at"],
                            last_heartbeat=f["last_heartbeat"],
                            copy_enabled=f.get("copy_enabled", True),
                            signals_received=f.get("signals_received", 0),
                            signals_executed=f.get("signals_executed", 0)
                        )
                        followers.append(follower)
                        self.connected_followers[f["client_id"]] = follower
                    return followers
        except Exception as e:
            logger.error(f"Failed to refresh followers: {e}")
        return []
    
    async def broadcast_open(self, symbol: str, side: str, quantity: int, 
                            entry_price: float, stop_loss: float = None,
                            take_profit: float = None) -> int:
        """Convenience method to broadcast an OPEN signal"""
        signal = create_open_signal(symbol, side, quantity, entry_price, stop_loss, take_profit)
        return await self.broadcast_signal(signal)
    
    async def broadcast_close(self, symbol: str, side: str, quantity: int, exit_price: float) -> int:
        """Convenience method to broadcast a CLOSE signal"""
        signal = create_close_signal(symbol, side, quantity, exit_price)
        return await self.broadcast_signal(signal)
    
    async def broadcast_flatten(self, symbol: str) -> int:
        """Convenience method to broadcast a FLATTEN signal"""
        signal = create_flatten_signal(symbol)
        return await self.broadcast_signal(signal)
    
    def get_status(self) -> dict:
        """Get broadcaster status for dashboard"""
        return {
            "broadcasting": self.broadcasting,
            "connected_followers": len(self.connected_followers),
            "total_signals_sent": len(self.signal_history),
            "followers": [
                {
                    "id": f.client_id,
                    "name": f.name,
                    "copy_enabled": f.copy_enabled,
                    "signals_received": f.signals_received,
                    "signals_executed": f.signals_executed
                }
                for f in self.connected_followers.values()
            ]
        }

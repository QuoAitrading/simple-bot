"""
Broker Client - TopStep SDK Wrapper
Handles connection and order execution for both Master and Follower
"""

import asyncio
import logging
from typing import Optional, Dict, Any, Callable
from datetime import datetime

try:
    from project_x_py import ProjectX, TradingSuite
    SDK_AVAILABLE = True
except ImportError:
    SDK_AVAILABLE = False
    print("⚠️  TopStep SDK not installed. Run: pip install project-x-py")

logger = logging.getLogger(__name__)


class BrokerClient:
    """Wrapper around TopStep SDK for trade execution"""
    
    def __init__(self, username: str, api_token: str, name: str = "Account"):
        self.username = username
        self.api_token = api_token
        self.name = name
        self.connected = False
        self.sdk_client: Optional[ProjectX] = None
        self.trading_suite: Optional[TradingSuite] = None
        self.account_id: Optional[str] = None
        self.account_balance: float = 0.0
        self.positions: Dict[str, int] = {}  # symbol -> quantity
        
        # Callbacks
        self.on_fill: Optional[Callable] = None  # Called when a fill happens
        
    async def connect(self) -> bool:
        """Connect to TopStep and authenticate"""
        if not SDK_AVAILABLE:
            logger.error("TopStep SDK not available")
            return False
            
        try:
            self.sdk_client = ProjectX(self.username, self.api_token)
            await self.sdk_client.connect()
            
            # Get accounts
            accounts = await self.sdk_client.services.trading_api.search_accounts()
            if accounts:
                self.account_id = accounts[0].id
                self.account_balance = accounts[0].account_balance
                logger.info(f"✅ {self.name} connected: {self.account_id[:20]}... (${self.account_balance:,.2f})")
                self.connected = True
                return True
            else:
                logger.error(f"❌ {self.name}: No accounts found")
                return False
                
        except Exception as e:
            logger.error(f"❌ {self.name} connection failed: {e}")
            return False
    
    async def disconnect(self):
        """Disconnect from broker"""
        if self.sdk_client:
            try:
                await self.sdk_client.close()
            except:
                pass
        self.connected = False
        logger.info(f"🔌 {self.name} disconnected")
    
    async def place_market_order(self, symbol: str, side: str, quantity: int) -> bool:
        """
        Place a market order
        
        Args:
            symbol: e.g. "MES", "NQ"
            side: "BUY" or "SELL"
            quantity: number of contracts
        """
        if not self.connected or not self.trading_suite:
            logger.error(f"{self.name}: Not connected, cannot place order")
            return False
            
        try:
            if side.upper() == "BUY":
                result = await self.trading_suite.market_order(
                    symbol=symbol,
                    direction="buy",
                    size=quantity
                )
            else:
                result = await self.trading_suite.market_order(
                    symbol=symbol,
                    direction="sell",
                    size=quantity
                )
            
            logger.info(f"✅ {self.name}: {side} {quantity} {symbol} executed")
            return True
            
        except Exception as e:
            logger.error(f"❌ {self.name}: Order failed - {e}")
            return False
    
    async def flatten_position(self, symbol: str) -> bool:
        """Close all positions for a symbol"""
        if not self.connected or not self.trading_suite:
            return False
            
        try:
            await self.trading_suite.flatten(symbol=symbol)
            logger.info(f"🔄 {self.name}: Flattened {symbol}")
            return True
        except Exception as e:
            logger.error(f"❌ {self.name}: Flatten failed - {e}")
            return False
    
    def get_status(self) -> Dict[str, Any]:
        """Get current status for dashboard"""
        return {
            "name": self.name,
            "connected": self.connected,
            "account_id": self.account_id[:20] + "..." if self.account_id else None,
            "balance": self.account_balance,
            "positions": self.positions.copy()
        }

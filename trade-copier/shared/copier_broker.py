"""
Standalone Broker Client for Trade Copier
No dependencies on main bot - completely independent
"""

import asyncio
import logging
from typing import Dict, Any, Optional

logger = logging.getLogger(__name__)


class CopierBroker:
    """
    Simple broker interface for the trade copier.
    Only needs: connect, place_market_order, get_positions
    """
    
    def __init__(self, username: str, api_token: str):
        self.username = username
        self.api_token = api_token
        self.connected = False
        self.sdk_client = None
        self.trading_suite = None
        self._contract_cache: Dict[str, str] = {}
        self.account_balance = 0.0
        
    async def connect(self) -> bool:
        """Connect to TopStep broker. All SDK output is suppressed."""
        import sys
        import io
        
        # Redirect stdout/stderr to suppress ALL SDK noise
        old_stdout = sys.stdout
        old_stderr = sys.stderr
        sys.stdout = io.StringIO()
        sys.stderr = io.StringIO()
        
        try:
            import logging
            
            # Suppress SDK loggers
            def suppress_sdk_logs():
                for name in list(logging.Logger.manager.loggerDict.keys()):
                    if 'project_x' in name.lower():
                        lg = logging.getLogger(name)
                        lg.setLevel(logging.CRITICAL + 100)
                        lg.propagate = False
                        lg.disabled = True
                        lg.handlers = []
                for prefix in ['project_x_py', 'project_x']:
                    lg = logging.getLogger(prefix)
                    lg.setLevel(logging.CRITICAL + 100)
                    lg.propagate = False 
                    lg.disabled = True
                    lg.handlers = []
            
            suppress_sdk_logs()
            
            # Import SDK
            from project_x_py import ProjectX, ProjectXConfig, TradingSuite, TradingSuiteConfig
            from project_x_py.realtime.core import ProjectXRealtimeClient
            
            suppress_sdk_logs()
            
            # Initialize and authenticate
            self.sdk_client = ProjectX(
                username=self.username,
                api_key=self.api_token,
                config=ProjectXConfig()
            )
            suppress_sdk_logs()
            
            await self.sdk_client.authenticate()
            await asyncio.sleep(0.3)
            suppress_sdk_logs()
            
            # Get account
            account = self.sdk_client.get_account_info()
            suppress_sdk_logs()
            
            if not account:
                sys.stdout = old_stdout
                sys.stderr = old_stderr
                return False
            
            self.account_balance = float(getattr(account, 'balance', getattr(account, 'equity', 0)))
            self.account_id = str(getattr(account, 'id', getattr(account, 'account_id', '')))
            
            # Create TradingSuite - required for order placement
            # Uses MES as default but can place orders on any symbol via contract_id
            jwt_token = self.sdk_client.get_session_token()
            suppress_sdk_logs()
            
            if not jwt_token:
                sys.stdout = old_stdout
                sys.stderr = old_stderr
                print("❌ CopierBroker connection failed: Could not get JWT token")
                return False
                
            if not self.account_id:
                sys.stdout = old_stdout
                sys.stderr = old_stderr
                print("❌ CopierBroker connection failed: Could not get account ID")
                return False
            
            # Create TradingSuite - will raise exception on failure
            realtime_client = ProjectXRealtimeClient(jwt_token=jwt_token, account_id=self.account_id)
            suppress_sdk_logs()
            self.trading_suite = TradingSuite(
                client=self.sdk_client,
                realtime_client=realtime_client,
                config=TradingSuiteConfig(instrument="MES")
            )
            suppress_sdk_logs()
            
            self.connected = True
            
            # Restore output
            sys.stdout = old_stdout
            sys.stderr = old_stderr
            print("✅ CopierBroker connected successfully")
            return True
            
        except Exception as e:
            sys.stdout = old_stdout
            sys.stderr = old_stderr
            print(f"❌ CopierBroker connection failed: {e}")
            import traceback
            traceback.print_exc()
            return False
    
    async def disconnect(self):
        """Disconnect from broker."""
        self.connected = False
        self.sdk_client = None
        self.trading_suite = None
        
    async def get_contract_id(self, symbol: str) -> Optional[str]:
        """Get contract ID for a symbol."""
        if symbol in self._contract_cache:
            return self._contract_cache[symbol]
            
        try:
            instruments = await self.sdk_client.search_instruments(query=symbol)
            if instruments and len(instruments) > 0:
                contract_id = getattr(instruments[0], 'id', None)
                if contract_id:
                    self._contract_cache[symbol] = contract_id
                    return contract_id
        except:
            pass
        return None
    
    async def place_market_order(self, symbol: str, side: str, quantity: int) -> bool:
        """Place a market order using TradingSuite."""
        if not self.connected:
            logger.error("Broker not connected - call connect() first")
            print("❌ Broker not connected - call connect() first")
            return False
        if not self.trading_suite:
            logger.error("TradingSuite not initialized - broker connection incomplete")
            print("❌ TradingSuite not initialized - broker connection incomplete")
            return False
            
        try:
            contract_id = await self.get_contract_id(symbol)
            if not contract_id:
                logger.error(f"Could not find contract for {symbol}")
                return False
            
            # Import OrderSide enum
            from project_x_py import OrderSide
            order_side = OrderSide.BUY if side.upper() == "BUY" else OrderSide.SELL
            
            # Place order via TradingSuite (like main bot does)
            order = await self.trading_suite.orders.place_market_order(
                contract_id=contract_id,
                side=order_side,
                size=quantity
            )
            
            # Check for success
            if order:
                if hasattr(order, 'success') and order.success:
                    return True
                elif hasattr(order, 'order') and order.order:
                    return True
            return False
            
        except Exception as e:
            logger.error(f"Order error: {e}")
            return False
    
    async def place_stop_order(self, symbol: str, side: str, quantity: int, stop_price: float) -> bool:
        """Place a stop loss order using TradingSuite."""
        if not self.connected:
            logger.error("Broker not connected - call connect() first")
            return False
        if not self.trading_suite:
            logger.error("TradingSuite not initialized - broker connection incomplete")
            return False
            
        try:
            contract_id = await self.get_contract_id(symbol)
            if not contract_id:
                return False
                
            from project_x_py import OrderSide
            order_side = OrderSide.BUY if side.upper() == "BUY" else OrderSide.SELL
            
            order = await self.trading_suite.orders.place_stop_order(
                contract_id=contract_id,
                side=order_side,
                size=quantity,
                stop_price=stop_price
            )
            return order is not None
        except Exception as e:
            logger.error(f"Stop order error: {e}")
            return False
    
    async def flatten_position(self, symbol: str) -> bool:
        """Flatten position by closing with opposite order."""
        if not self.connected or not self.sdk_client:
            return False
            
        try:
            # Get current position
            positions = await self.get_positions()
            for pos in positions:
                if pos.get('symbol', '').upper() == symbol.upper():
                    qty = pos.get('quantity', 0)
                    if qty != 0:
                        # Place opposite order to flatten
                        side = "SELL" if qty > 0 else "BUY"
                        return await self.place_market_order(symbol, side, abs(qty))
            return True  # No position to flatten
        except:
            return False
    
    async def get_positions(self) -> list:
        """Get all open positions using new SDK method."""
        if not self.connected or not self.sdk_client:
            return []
            
        try:
            # Use the new method (not deprecated get_positions)
            positions = await self.sdk_client.search_open_positions()
            
            if not positions:
                return []
                
            result = []
            for pos in positions:
                # SDK uses 'size' and 'is_long' in newer versions
                size = getattr(pos, 'size', getattr(pos, 'quantity', 0))
                is_long = getattr(pos, 'is_long', True)
                
                # Get symbol from contract info
                symbol = getattr(pos, 'symbol', '')
                if not symbol:
                    # Try to get from contract_id
                    contract_id = getattr(pos, 'contract_id', '')
                    symbol = contract_id  # Use contract_id as fallback
                
                if size != 0:
                    # Return signed quantity (positive for long, negative for short)
                    qty = int(size) if is_long else -int(size)
                    result.append({
                        'symbol': symbol,
                        'quantity': qty,
                        'entry_price': getattr(pos, 'average_price', getattr(pos, 'avg_price', 0))
                    })
            return result
        except Exception as e:
            logger.error(f"Get positions error: {e}")
            return []

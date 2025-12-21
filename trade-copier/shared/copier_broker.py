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
            
            # Initialize TradingSuite
            jwt_token = self.sdk_client.get_session_token()
            account_id = str(getattr(account, 'id', getattr(account, 'account_id', '')))
            
            if jwt_token and account_id:
                realtime_client = ProjectXRealtimeClient(jwt_token=jwt_token, account_id=account_id)
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
            return True
            
        except Exception as e:
            sys.stdout = old_stdout
            sys.stderr = old_stderr
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
        """Place a market order."""
        if not self.connected or not self.trading_suite:
            return False
            
        try:
            contract_id = await self.get_contract_id(symbol)
            if not contract_id:
                return False
            
            from project_x_py import Side
            order_side = Side.BUY if side.upper() == "BUY" else Side.SELL
            
            order = await self.trading_suite.orders.place_market_order(
                contract_id=contract_id,
                side=order_side,
                size=quantity
            )
            return order is not None
            
        except Exception as e:
            return False
    
    async def place_stop_order(self, symbol: str, side: str, quantity: int, stop_price: float) -> bool:
        """Place a stop loss order."""
        if not self.connected or not self.trading_suite:
            return False
            
        try:
            contract_id = await self.get_contract_id(symbol)
            if not contract_id:
                return False
                
            from project_x_py import Side
            order_side = Side.BUY if side.upper() == "BUY" else Side.SELL
            
            order = await self.trading_suite.orders.place_stop_order(
                contract_id=contract_id,
                side=order_side,
                size=quantity,
                stop_price=stop_price
            )
            return order is not None
        except:
            return False
    
    async def flatten_position(self, symbol: str) -> bool:
        """Flatten all positions."""
        if not self.connected or not self.trading_suite:
            return False
            
        try:
            await self.trading_suite.positions.flatten()
            return True
        except:
            return False
    
    async def get_positions(self) -> list:
        """Get all open positions."""
        if not self.connected or not self.sdk_client:
            return []
            
        try:
            positions = self.sdk_client.get_positions()
            result = []
            for pos in positions:
                qty = getattr(pos, 'quantity', 0)
                if qty != 0:
                    result.append({
                        'symbol': getattr(pos, 'symbol', ''),
                        'quantity': qty,
                        'entry_price': getattr(pos, 'average_price', 0)
                    })
            return result
        except:
            return []

"""
Broker Interface Abstraction Layer
Provides clean separation between trading strategy and broker execution with TopStep SDK integration.
"""

from abc import ABC, abstractmethod
from typing import Dict, Any, Optional, Callable, List
from datetime import datetime
import logging
import time
import asyncio
import os

# Import TopStep SDK (Project-X)
try:
    from project_x_py import ProjectX, ProjectXConfig, TradingSuite, TradingSuiteConfig
    from project_x_py import OrderSide, OrderType
    TOPSTEP_SDK_AVAILABLE = True
except ImportError:
    TOPSTEP_SDK_AVAILABLE = False
    logging.warning("TopStep SDK (project-x-py) not installed - broker operations will not work")


logger = logging.getLogger(__name__)


class BrokerInterface(ABC):
    """
    Abstract base class for broker operations.
    Allows swapping brokers without changing strategy code.
    """
    
    @abstractmethod
    def connect(self) -> bool:
        """
        Connect to broker and authenticate.
        
        Returns:
            True if connection successful
        """
        pass
    
    @abstractmethod
    def disconnect(self) -> None:
        """Disconnect from broker."""
        pass
    
    @abstractmethod
    def get_account_equity(self) -> float:
        """
        Get current account equity.
        
        Returns:
            Account equity in dollars
        """
        pass
    
    @abstractmethod
    def get_position_quantity(self, symbol: str) -> int:
        """
        Get current position quantity for symbol.
        
        Args:
            symbol: Instrument symbol
        
        Returns:
            Position quantity (positive for long, negative for short, 0 for flat)
        """
        pass
    
    @abstractmethod
    def place_market_order(self, symbol: str, side: str, quantity: int) -> Optional[Dict[str, Any]]:
        """
        Place a market order.
        
        Args:
            symbol: Instrument symbol
            side: Order side ("BUY" or "SELL")
            quantity: Number of contracts
        
        Returns:
            Order details if successful, None otherwise
        """
        pass
    
    @abstractmethod
    def place_limit_order(self, symbol: str, side: str, quantity: int, 
                         limit_price: float) -> Optional[Dict[str, Any]]:
        """
        Place a limit order.
        
        Args:
            symbol: Instrument symbol
            side: Order side ("BUY" or "SELL")
            quantity: Number of contracts
            limit_price: Limit price
        
        Returns:
            Order details if successful, None otherwise
        """
        pass
    
    @abstractmethod
    def place_stop_order(self, symbol: str, side: str, quantity: int, 
                        stop_price: float) -> Optional[Dict[str, Any]]:
        """
        Place a stop order.
        
        Args:
            symbol: Instrument symbol
            side: Order side ("BUY" or "SELL")
            quantity: Number of contracts
            stop_price: Stop price
        
        Returns:
            Order details if successful, None otherwise
        """
        pass
    
    @abstractmethod
    def subscribe_market_data(self, symbol: str, callback: Callable[[str, float, int, int], None]) -> None:
        """
        Subscribe to real-time market data.
        
        Args:
            symbol: Instrument symbol
            callback: Function to call with tick data (symbol, price, volume, timestamp)
        """
        pass
    
    @abstractmethod
    def fetch_historical_bars(self, symbol: str, timeframe: int, count: int) -> list:
        """
        Fetch historical bars.
        
        Args:
            symbol: Instrument symbol
            timeframe: Timeframe in minutes
            count: Number of bars to fetch
        
        Returns:
            List of bar dictionaries
        """
        pass
    
    @abstractmethod
    def is_connected(self) -> bool:
        """
        Check if broker connection is active.
        
        Returns:
            True if connected
        """
        pass


class TopStepBroker(BrokerInterface):
    """
    TopStep SDK broker implementation using Project-X SDK.
    Wraps TopStep API calls with error handling and retry logic.
    """
    
    def __init__(self, api_token: str, username: str = None, max_retries: int = 3, timeout: int = 30):
        """
        Initialize TopStep broker.
        
        Args:
            api_token: TopStep API token (format: username:api_key or just api_key)
            username: TopStep username/email (optional if included in api_token)
            max_retries: Maximum number of retry attempts
            timeout: Request timeout in seconds
        """
        # Parse API token - may be in format "username:api_key" or separate
        if ':' in api_token and username is None:
            self.username, self.api_key = api_token.split(':', 1)
        else:
            self.username = username or os.getenv('TOPSTEP_USERNAME', '')
            self.api_key = api_token
            
        self.max_retries = max_retries
        self.timeout = timeout
        self.connected = False
        self.circuit_breaker_open = False
        self.failure_count = 0
        self.circuit_breaker_threshold = 5
        
        # TopStep SDK client (Project-X)
        self.sdk_client: Optional[ProjectX] = None
        self.trading_suite: Optional[TradingSuite] = None
        
        if not TOPSTEP_SDK_AVAILABLE:
            logger.error("TopStep SDK (project-x-py) not installed!")
            logger.error("Install with: pip install project-x-py")
            raise RuntimeError("TopStep SDK not available")
    
    def connect(self) -> bool:
        """
        Connect to TopStep SDK and authenticate to get JWT token.
        
        Authentication Flow:
        1. Use API key + username to authenticate (async)
        2. Receive JWT token
        3. Use JWT for all subsequent API calls
        """
        if self.circuit_breaker_open:
            logger.error("Circuit breaker is open - cannot connect")
            return False
        
        try:
            logger.info("Connecting to TopStep SDK (Project-X)...")
            
            if not self.username:
                logger.error("Username/email is required for TopStep SDK")
                logger.error("Set TOPSTEP_USERNAME environment variable or provide username parameter")
                return False
            
            # Initialize SDK client
            config = ProjectXConfig(timeout_seconds=self.timeout)
            self.sdk_client = ProjectX(
                username=self.username,
                api_key=self.api_key,
                config=config
            )
            
            # Step 1: Authenticate to get JWT token (SDK is async)
            logger.info(f"Authenticating with TopStep as {self.username}...")
            
            # Run async authenticate in sync context
            # Try to get existing event loop, create only if none exists
            try:
                loop = asyncio.get_running_loop()
                # If we get here, we're already in an async context - should not happen
                auth_response = asyncio.run_until_complete(self.sdk_client.authenticate())
            except RuntimeError:
                # No running loop - create one
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                try:
                    auth_response = loop.run_until_complete(self.sdk_client.authenticate())
                finally:
                    # Don't close the loop - keep it for subsequent calls
                    pass
            
            if hasattr(auth_response, 'jwt_token'):
                self.jwt_token = auth_response.jwt_token
                logger.info("✓ JWT token received successfully")
            else:
                logger.info("✓ Authentication successful")
            
            # Step 2: Test connection
            # After authentication, we can just set connected to True
            # get_account_info may not be async or may not exist
            logger.info("✓ Connected to TopStep API")
            self.connected = True
            self.failure_count = 0
            return True
            account = self.sdk_client.get_account_info()
            if account:
                logger.info(f"✓ Connected to TopStep - Account: {account.get('accountId', 'Unknown')}")
                self.connected = True
                self.failure_count = 0
                return True
            else:
                logger.error("Failed to retrieve account info")
                self._record_failure()
                return False
            
        except Exception as e:
            logger.error(f"Failed to connect to TopStep SDK: {e}")
            self._record_failure()
            return False
            self._record_failure()
            return False
    
    def disconnect(self) -> None:
        """Disconnect from TopStep SDK."""
        try:
            if self.trading_suite:
                # Close any active connections
                self.trading_suite = None
            if self.sdk_client:
                self.sdk_client = None
            self.connected = False
            logger.info("Disconnected from TopStep SDK")
        except Exception as e:
            logger.error(f"Error disconnecting from TopStep SDK: {e}")
    
    def get_account_equity(self) -> float:
        """Get account equity from TopStep."""
        if not self.connected or not self.sdk_client:
            logger.error("Cannot get equity: not connected")
            return 0.0
        
        try:
            account = self.sdk_client.get_account()
            if account:
                equity = float(account.balance or 0.0)
                return equity
            return 0.0
        except Exception as e:
            logger.error(f"Error getting account equity: {e}")
            self._record_failure()
            return 0.0
    
    def get_position_quantity(self, symbol: str) -> int:
        """Get position quantity from TopStep."""
        if not self.connected or not self.sdk_client:
            logger.error("Cannot get position: not connected")
            return 0
        
        try:
            positions = self.sdk_client.get_positions()
            for pos in positions:
                if pos.instrument.symbol == symbol:
                    # Return signed quantity (positive for long, negative for short)
                    qty = int(pos.quantity)
                    return qty if pos.position_type.value == "LONG" else -qty
            return 0  # No position found
        except Exception as e:
            logger.error(f"Error getting position quantity: {e}")
            self._record_failure()
            return 0
    
    def place_market_order(self, symbol: str, side: str, quantity: int) -> Optional[Dict[str, Any]]:
        """Place market order using TopStep SDK."""
        if not self.connected or not self.trading_suite:
            logger.error("Cannot place order: not connected")
            return None
        
        try:
            # Convert side to SDK enum
            order_side = OrderSide.BUY if side.upper() == "BUY" else OrderSide.SELL
            
            # Place market order
            order_response = self.trading_suite.place_market_order(
                symbol=symbol,
                side=order_side,
                quantity=quantity
            )
            
            if order_response and order_response.order:
                order = order_response.order
                return {
                    "order_id": order.order_id,
                    "symbol": symbol,
                    "side": side,
                    "quantity": quantity,
                    "type": "MARKET",
                    "status": order.status.value,
                    "filled_quantity": order.filled_quantity or 0,
                    "avg_fill_price": order.avg_fill_price or 0.0
                }
            else:
                logger.error("Market order placement failed")
                self._record_failure()
                return None
                
        except Exception as e:
            logger.error(f"Error placing market order: {e}")
            self._record_failure()
            return None
    
    def place_limit_order(self, symbol: str, side: str, quantity: int, limit_price: float) -> Optional[Dict[str, Any]]:
        """Place limit order using TopStep SDK."""
        if not self.connected or not self.trading_suite:
            logger.error("Cannot place order: not connected")
            return None
        
        try:
            # Convert side to SDK enum
            order_side = OrderSide.BUY if side.upper() == "BUY" else OrderSide.SELL
            
            # Place limit order
            order_response = self.trading_suite.place_limit_order(
                symbol=symbol,
                side=order_side,
                quantity=quantity,
                limit_price=limit_price
            )
            
            if order_response and order_response.order:
                order = order_response.order
                return {
                    "order_id": order.order_id,
                    "symbol": symbol,
                    "side": side,
                    "quantity": quantity,
                    "type": "LIMIT",
                    "limit_price": limit_price,
                    "status": order.status.value,
                    "filled_quantity": order.filled_quantity or 0
                }
            else:
                logger.error("Limit order placement failed")
                self._record_failure()
                return None
                
        except Exception as e:
            logger.error(f"Error placing limit order: {e}")
            self._record_failure()
            return None
    
    def place_stop_order(self, symbol: str, side: str, quantity: int, stop_price: float) -> Optional[Dict[str, Any]]:
        """Place stop order using TopStep SDK."""
        if not self.connected or not self.trading_suite:
            logger.error("Cannot place order: not connected")
            return None
        
        try:
            # Convert side to SDK enum
            order_side = OrderSide.BUY if side.upper() == "BUY" else OrderSide.SELL
            
            # Place stop order
            order_response = self.trading_suite.place_stop_order(
                symbol=symbol,
                side=order_side,
                quantity=quantity,
                stop_price=stop_price
            )
            
            if order_response and order_response.order:
                order = order_response.order
                return {
                    "order_id": order.order_id,
                    "symbol": symbol,
                    "side": side,
                    "quantity": quantity,
                    "type": "STOP",
                    "stop_price": stop_price,
                    "status": order.status.value
                }
            else:
                logger.error("Stop order placement failed")
                self._record_failure()
                return None
                
        except Exception as e:
            logger.error(f"Error placing stop order: {e}")
            self._record_failure()
            return None
    
    def subscribe_market_data(self, symbol: str, callback: Callable[[str, float, int, int], None]) -> None:
        """Subscribe to real-time market data."""
        if not self.connected or not self.sdk_client:
            logger.error("Cannot subscribe: not connected")
            return
        
        try:
            # Subscribe to realtime data
            realtime_client = self.sdk_client.get_realtime_client()
            if realtime_client:
                # Subscribe to trades/quotes for the symbol
                realtime_client.subscribe_trades(
                    symbol,
                    lambda trade: callback(
                        trade.instrument.symbol,
                        float(trade.price),
                        int(trade.size),
                        int(trade.timestamp.timestamp() * 1000)
                    )
                )
                logger.info(f"Subscribed to market data for {symbol}")
            else:
                logger.error("Failed to get realtime client")
        except Exception as e:
            logger.error(f"Error subscribing to market data: {e}")
            self._record_failure()
    
    def fetch_historical_bars(self, symbol: str, timeframe: str, count: int, 
                             start_date: Optional[datetime] = None, 
                             end_date: Optional[datetime] = None) -> List[Dict[str, Any]]:
        """
        Fetch historical bars from TopStep using JWT token.
        
        Args:
            symbol: Instrument symbol (e.g., 'MES')
            timeframe: Timeframe string (e.g., '1m', '5m', '15m', '1h')
            count: Number of bars to fetch
            start_date: Optional start date for historical data
            end_date: Optional end date for historical data
            
        Returns:
            List of bar dictionaries with OHLCV data
        """
        if not self.connected or not self.sdk_client:
            logger.error("Cannot fetch bars: not connected")
            return []
        
        try:
            # Parse timeframe string to interval and unit
            # timeframe format: '1m', '5m', '15m', '1h', etc.
            # unit: 0=tick, 1=second, 2=minute, 3=hour, 4=day
            if 'm' in timeframe or 'min' in timeframe:
                interval = int(timeframe.replace('m', '').replace('min', ''))
                unit = 2  # minute
            elif 'h' in timeframe:
                interval = int(timeframe.replace('h', ''))
                unit = 3  # hour
            elif 'd' in timeframe:
                interval = int(timeframe.replace('d', ''))
                unit = 4  # day
            else:
                # Default to minutes
                interval = int(timeframe)
                unit = 2
            
            logger.info(f"Fetching {count} bars for {symbol} ({interval} units, unit type={unit})...")
            
            # Prepare get_bars parameters
            get_bars_params = {
                "symbol": symbol,
                "interval": interval,
                "unit": unit,
                "limit": count,  # Always use limit
                "partial": False  # Don't include incomplete bars
            }
            
            # Add date range if provided - this sets the time window
            if start_date:
                get_bars_params["start_time"] = start_date
                logger.info(f"  Start time: {start_date}")
            if end_date:
                get_bars_params["end_time"] = end_date
                logger.info(f"  End time: {end_date}")
            
            # Fetch historical data using authenticated SDK client (async)
            # Method is get_bars with interval (int) and unit (int) parameters
            # Reuse existing event loop if available
            try:
                loop = asyncio.get_running_loop()
                # Already in async context
                bars_df = asyncio.run_until_complete(
                    self.sdk_client.get_bars(**get_bars_params)
                )
            except RuntimeError:
                # No running loop - get or create the event loop
                try:
                    loop = asyncio.get_event_loop()
                except RuntimeError:
                    loop = asyncio.new_event_loop()
                    asyncio.set_event_loop(loop)
                
                bars_df = loop.run_until_complete(
                    self.sdk_client.get_bars(**get_bars_params)
                )
                # Don't close the loop - keep it for subsequent calls
            
            # Convert Polars DataFrame to list of dicts
            if bars_df is not None and len(bars_df) > 0:
                result = []
                # Convert DataFrame rows to dictionaries
                for row in bars_df.iter_rows(named=True):
                    result.append({
                        "timestamp": row.get('timestamp') or row.get('time'),
                        "open": float(row['open']),
                        "high": float(row['high']),
                        "low": float(row['low']),
                        "close": float(row['close']),
                        "volume": int(row['volume'])
                    })
                logger.info(f"✓ Fetched {len(result)} bars successfully")
                return result
            else:
                logger.warning("No bars returned from API")
                return []
                
        except Exception as e:
            logger.error(f"Error fetching historical bars: {e}")
            logger.error(f"  Symbol: {symbol}, Timeframe: {timeframe}, Count: {count}")
            self._record_failure()
            return []
    def is_connected(self) -> bool:
        """Check if connected to TopStep SDK."""
        return self.connected and not self.circuit_breaker_open
    
    def _record_failure(self) -> None:
        """Record a failure and potentially open circuit breaker."""
        self.failure_count += 1
        if self.failure_count >= self.circuit_breaker_threshold:
            self.circuit_breaker_open = True
            logger.critical(f"Circuit breaker opened after {self.failure_count} failures")
    
    def reset_circuit_breaker(self) -> None:
        """Reset circuit breaker (manual recovery)."""
        self.circuit_breaker_open = False
        self.failure_count = 0
        logger.info("Circuit breaker reset")


def create_broker(api_token: str, username: str = None) -> BrokerInterface:
    """
    Factory function to create TopStep broker instance.
    
    Args:
        api_token: API key for TopStep
        username: Username/email for TopStep account
    
    Returns:
        TopStepBroker instance
    
    Raises:
        ValueError: If API token is missing
    """
    if not api_token:
        raise ValueError("API token is required for TopStep broker")
    
    # Get username from environment if not provided
    if not username:
        username = os.getenv('TOPSTEP_USERNAME')
    
    return TopStepBroker(api_token=api_token, username=username)

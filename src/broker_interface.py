"""
Broker Interface Abstraction Layer
Provides clean separation between trading strategy and broker execution with TopStep SDK integration.
"""

from abc import ABC, abstractmethod
from typing import Dict, Any, Optional, Callable, List
from datetime import datetime
import logging
import time

# Import TopStep SDK (Project-X)
try:
    from project_x_py import ProjectX, ProjectXConfig, TradingSuite, TradingSuiteConfig
    from project_x_py import OrderSide, OrderType
    TOPSTEP_SDK_AVAILABLE = True
except ImportError:
    TOPSTEP_SDK_AVAILABLE = False
    logging.warning("TopStep SDK (project-x-py) not installed - broker operations will not work")

# Import WebSocket streamer for real-time market data
try:
    from topstep_websocket import TopStepWebSocketStreamer
    WEBSOCKET_AVAILABLE = True
except ImportError:
    WEBSOCKET_AVAILABLE = False
    logging.warning("TopStepWebSocketStreamer not available - market data will not work")

logger = logging.getLogger(__name__)

from abc import ABC, abstractmethod
from typing import Dict, Any, Optional, Callable, List
from datetime import datetime
import logging
import time

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
        Subscribe to real-time market data (trades).
        
        Args:
            symbol: Instrument symbol
            callback: Function to call with tick data (symbol, price, volume, timestamp)
        """
        pass
    
    @abstractmethod
    def subscribe_quotes(self, symbol: str, callback: Callable[[str, float, float, int, int, float, int], None]) -> None:
        """
        Subscribe to real-time bid/ask quotes.
        
        Args:
            symbol: Instrument symbol
            callback: Function to call with quote data (symbol, bid_price, ask_price, bid_size, ask_size, last_price, timestamp)
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
            api_token: TopStep API token
            username: TopStep username/email (required for SDK v3.5+)
            max_retries: Maximum number of retry attempts
            timeout: Request timeout in seconds
        """
        self.api_token = api_token
        self.username = username
        self.max_retries = max_retries
        self.timeout = timeout
        self.connected = False
        self.circuit_breaker_open = False
        self.failure_count = 0
        self.circuit_breaker_threshold = 5
        
        # TopStep SDK client (Project-X)
        self.sdk_client: Optional[ProjectX] = None
        self.trading_suite: Optional[TradingSuite] = None
        
        # WebSocket streamer for real-time market data
        self.websocket: Optional[TopStepWebSocketStreamer] = None
        
        if not TOPSTEP_SDK_AVAILABLE:
            logger.error("TopStep SDK (project-x-py) not installed!")
            logger.error("Install with: pip install project-x-py")
            raise RuntimeError("TopStep SDK not available")
    
    def connect(self) -> bool:
        """Connect to TopStep SDK."""
        import asyncio
        
        if self.circuit_breaker_open:
            logger.error("Circuit breaker is open - cannot connect")
            return False
        
        try:
            logger.info("Connecting to TopStep SDK (Project-X)...")
            
            # Initialize SDK client with username and API key
            self.sdk_client = ProjectX(
                username=self.username or "",
                api_key=self.api_token,
                config=ProjectXConfig()
            )
            
            # Authenticate first (async method needs await)
            logger.info("Authenticating with TopStep...")
            asyncio.run(self.sdk_client.authenticate())
            
            # Trading suite is optional - only needed for live trading, not historical data
            self.trading_suite = None
            
            # Test connection by getting account info
            account = self.sdk_client.get_account_info()
            if account:
                account_id = getattr(account, 'account_id', getattr(account, 'id', 'N/A'))
                logger.info(f"Connected to TopStep - Account: {account_id}")
                self.connected = True
                self.failure_count = 0
                
                # Initialize WebSocket for real-time market data
                if WEBSOCKET_AVAILABLE:
                    try:
                        logger.info("Initializing WebSocket for real-time market data...")
                        session_token = self.sdk_client.get_session_token()
                        self.websocket = TopStepWebSocketStreamer(session_token)
                        if self.websocket.connect():
                            logger.info("✅ WebSocket connected - ready for real-time quotes")
                        else:
                            logger.warning("⚠️ WebSocket connection failed - market data may not work")
                    except Exception as ws_error:
                        logger.error(f"WebSocket initialization error: {ws_error}")
                        logger.warning("Continuing without WebSocket - market data may not work")
                
                return True
            else:
                logger.error("Failed to retrieve account info")
                self._record_failure()
                return False
            
        except Exception as e:
            logger.error(f"Failed to connect to TopStep SDK: {e}")
            self._record_failure()
            return False
    
    def disconnect(self) -> None:
        """Disconnect from TopStep SDK."""
        try:
            if self.websocket and self.websocket.is_connected:
                logger.info("=" * 60)
                logger.info("WEBSOCKET STATISTICS (Total Session)")
                logger.info("=" * 60)
                logger.info(f"Quotes received: {self.websocket.quotes_received}")
                logger.info(f"Trades received: {self.websocket.trades_received}")
                logger.info(f"Depth updates: {self.websocket.depth_updates_received}")
                logger.info(f"Last message time: {self.websocket.last_message_time}")
                logger.info(f"Active subscriptions: {len(self.websocket.subscriptions)}")
                logger.info(f"Subscriptions: {self.websocket.subscriptions}")
                logger.info("=" * 60)
                logger.info("Disconnecting WebSocket...")
                self.websocket.is_connected = False
            if self.trading_suite:
                # Close any active connections
                self.trading_suite = None
            if self.sdk_client:
                self.sdk_client = None
            self.connected = False
            logger.info("Disconnected from TopStep SDK")
        except Exception as e:
            logger.error(f"Error disconnecting from TopStep SDK: {e}")
    
    def _get_contract_id(self, symbol: str) -> str:
        """Convert symbol to TopStep contract ID format.
        
        TopStep WebSocket requires full contract notation like:
        CON.F.US.MES.Z25 (Futures, US, MES symbol, Dec 2025)
        
        Format: CON.F.US.<SYMBOL>.<MONTH><YEAR>
        Month codes: F=Jan, G=Feb, H=Mar, J=Apr, K=May, M=Jun, 
                     N=Jul, Q=Aug, U=Sep, V=Oct, X=Nov, Z=Dec
        
        Args:
            symbol: Trading symbol (e.g., 'MES', 'NQ', 'ES')
            
        Returns:
            Contract ID string for WebSocket subscription
        """
        try:
            from datetime import datetime
            
            # Get current month to determine front month contract
            now = datetime.now()
            current_month = now.month
            current_year = now.year % 100  # Last 2 digits
            
            # Futures month codes (CME standard)
            month_codes = {
                1: 'F', 2: 'G', 3: 'H', 4: 'J', 5: 'K', 6: 'M',
                7: 'N', 8: 'Q', 9: 'U', 10: 'V', 11: 'X', 12: 'Z'
            }
            
            # Quarterly contracts (Mar, Jun, Sep, Dec) for equity index futures
            quarterly_months = {3: 'H', 6: 'M', 9: 'U', 12: 'Z'}
            
            # Determine front month for quarterly contracts (equity index futures)
            # Quarterly symbols (Mar, Jun, Sep, Dec only): All E-mini and Micro E-mini indices
            quarterly_symbols = [
                'ES', 'MES',      # S&P 500
                'NQ', 'MNQ',      # Nasdaq-100
                'YM', 'MYM',      # Dow Jones
                'RTY', 'M2K',     # Russell 2000
                'EMD',            # S&P MidCap
            ]
            
            if symbol in quarterly_symbols:
                # Find next quarterly month
                for month in [3, 6, 9, 12]:
                    if month >= current_month:
                        front_month = quarterly_months[month]
                        front_year = current_year
                        break
                else:
                    # Roll to next year's March
                    front_month = 'H'
                    front_year = (current_year + 1) % 100
            else:
                # Monthly contracts - use current or next month
                front_month = month_codes[current_month]
                front_year = current_year
            
            # Build TopStep contract notation
            contract_id = f"CON.F.US.{symbol}.{front_month}{front_year:02d}"
            logger.info(f"[CONTRACT] {symbol} -> {contract_id}")
            return contract_id
            
        except Exception as e:
            logger.error(f"Error building contract ID for {symbol}: {e}")
            logger.warning(f"Falling back to symbol: {symbol}")
            return symbol
    
    def get_account_equity(self) -> float:
        """Get account equity from TopStep."""
        import asyncio
        
        if not self.connected or not self.sdk_client:
            logger.error("Cannot get equity: not connected")
            return 0.0
        
        try:
            # Use get_account_info() instead of deprecated get_account()
            account_info = self.sdk_client.get_account_info()
            
            # If it returns a coroutine, await it
            if asyncio.iscoroutine(account_info):
                account_info = asyncio.run(account_info)
            
            if account_info:
                # Try different fields that might contain the balance
                balance = None
                
                # Check object attributes
                for field in ['cash_balance', 'balance', 'equity', 'available_funds', 'net_liquidation_value']:
                    if hasattr(account_info, field):
                        val = getattr(account_info, field)
                        if val is not None and val != 0:
                            balance = float(val)
                            break
                
                # If it's a dict, try dict access
                if balance is None and isinstance(account_info, dict):
                    for field in ['cash_balance', 'balance', 'equity', 'available_funds']:
                        val = account_info.get(field)
                        if val is not None and val != 0:
                            balance = float(val)
                            break
                
                if balance:
                    return balance
                else:
                    return 0.0
            else:
                return 0.0
        except Exception as e:
            logger.warning(f"Could not fetch account equity: {e}")
            import traceback
            logger.debug(traceback.format_exc())
            return 0.0
    
    def get_position_quantity(self, symbol: str) -> int:
        """Get position quantity from TopStep."""
        import asyncio
        
        if not self.connected or not self.sdk_client:
            logger.error("Cannot get position: not connected")
            return 0
        
        try:
            # Use search_open_positions() instead of deprecated get_positions()
            positions = self.sdk_client.search_open_positions()
            
            # If it returns a coroutine, await it
            if asyncio.iscoroutine(positions):
                positions = asyncio.run(positions)
            
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
        """Subscribe to real-time market data (trades)."""
        if not self.connected:
            logger.error("Cannot subscribe: not connected")
            return
        
        # Get proper contract ID for WebSocket subscription
        contract_id = self._get_contract_id(symbol)
        
        # Use WebSocket for real-time trades
        if self.websocket and self.websocket.is_connected:
            try:
                logger.info(f"Subscribing to WebSocket trades for {symbol} (contract: {contract_id})...")
                
                # WebSocket callback wrapper to transform data format
                def ws_trade_handler(data):
                    """Transform WebSocket trade data to expected format"""
                    try:
                        # Data format from WebSocket may vary - handle both list and dict
                        if isinstance(data, (list, tuple)) and len(data) >= 2:
                            trade_symbol = data[0]
                            trade_data = data[1] if isinstance(data[1], dict) else {}
                            
                            price = float(trade_data.get('Price', 0.0))
                            size = int(trade_data.get('Size', 0))
                            timestamp_ms = int(time.time() * 1000)
                            if 'Timestamp' in trade_data:
                                timestamp_ms = int(trade_data['Timestamp'])
                            
                            # Use original symbol, not contract ID
                            callback(symbol, price, size, timestamp_ms)
                    except Exception as e:
                        logger.error(f"Error processing WebSocket trade data: {e}")
                
                self.websocket.subscribe_trades(contract_id, ws_trade_handler)
                logger.info(f"✅ Subscribed to WebSocket trades for {symbol} using contract {contract_id}")
            except Exception as e:
                logger.error(f"Error subscribing to WebSocket trades: {e}")
                self._record_failure()
        else:
            logger.warning("⚠️ WebSocket not available - using quotes only for market data")
            # Fallback: use quotes to simulate trades (less ideal but better than nothing)
            if self.websocket and self.websocket.is_connected:
                logger.info("Falling back to quote-based market data simulation...")
                
                def quote_to_trade_handler(data):
                    """Simulate trade data from quotes"""
                    try:
                        if isinstance(data, list) and len(data) >= 2:
                            symbol_val = data[0]
                            quote_data = data[1]
                            last_price = float(quote_data.get('LastPrice', quote_data.get('BidPrice', 0.0)))
                            timestamp_ms = int(time.time() * 1000)
                            callback(symbol, last_price, 1, timestamp_ms)
                    except Exception as e:
                        logger.error(f"Error in quote-to-trade simulation: {e}")
                
                self.websocket.subscribe_quotes(contract_id, quote_to_trade_handler)
    
    def subscribe_quotes(self, symbol: str, callback: Callable[[str, float, float, int, int, float, int], None]) -> None:
        """Subscribe to real-time bid/ask quotes."""
        if not self.connected:
            logger.error("Cannot subscribe to quotes: not connected")
            return
        
        # Use WebSocket for real-time quotes
        if self.websocket and self.websocket.is_connected:
            try:
                # Get proper contract ID for WebSocket subscription
                contract_id = self._get_contract_id(symbol)
                logger.info(f"Subscribing to WebSocket quotes for {symbol} (contract: {contract_id})...")
                
                # WebSocket callback wrapper to transform data format
                def ws_quote_handler(data):
                    """Transform WebSocket quote data to expected format"""
                    try:
                        # TopStep sends: [symbol_string, quote_dict] 
                        if isinstance(data, list) and len(data) >= 2:
                            quote_data = data[1]
                            
                            if isinstance(quote_data, dict):
                                # Extract all values from THIS message only
                                bid_price = float(quote_data.get('bestBid', 0.0) or 0.0)
                                ask_price = float(quote_data.get('bestAsk', 0.0) or 0.0)
                                bid_size = int(quote_data.get('bestBidSize', 0) or 0)
                                ask_size = int(quote_data.get('bestAskSize', 0) or 0)
                                last_price = float(quote_data.get('lastPrice', 0.0) or 0.0)
                                
                                # TopStep doesn't always provide size - default to 1 if not available
                                # This allows quotes to be used even without depth data
                                if bid_size == 0:
                                    bid_size = 1
                                if ask_size == 0:
                                    ask_size = 1
                                
                                # Only send if THIS message has BOTH valid bid AND ask
                                # Don't mix data from different messages - prevents stale/inconsistent quotes
                                if bid_price > 0 and ask_price > 0 and bid_price <= ask_price:
                                    timestamp_ms = int(time.time() * 1000)
                                    callback(symbol, bid_price, ask_price, bid_size, ask_size, last_price, timestamp_ms)
                                
                    except Exception as e:
                        logger.error(f"Error processing WebSocket quote data: {e}")
                        import traceback
                        logger.error(traceback.format_exc())
                
                self.websocket.subscribe_quotes(contract_id, ws_quote_handler)
                logger.info(f"✅ Subscribed to WebSocket quotes for {symbol} using contract {contract_id}")
            except Exception as e:
                logger.error(f"Error subscribing to WebSocket quotes: {e}")
                self._record_failure()
        else:
            logger.error("❌ WebSocket not available - cannot subscribe to quotes")
            logger.error("Market data will not work without WebSocket connection")
    
    def fetch_historical_bars(self, symbol: str, timeframe: str, count: int, 
                             start_date: datetime = None, end_date: datetime = None) -> List[Dict[str, Any]]:
        """Fetch historical bars from TopStep."""
        import asyncio
        
        if not self.connected or not self.sdk_client:
            logger.error("Cannot fetch bars: not connected")
            return []
        
        try:
            # Convert timeframe string to interval (e.g., '1m' -> 1 minute)
            if 'm' in timeframe or 'min' in timeframe:
                interval = int(timeframe.replace('m', '').replace('min', ''))
                unit = 2  # Minutes
            elif 'h' in timeframe:
                interval = int(timeframe.replace('h', '')) * 60
                unit = 2  # Minutes
            else:
                interval = 5  # Default to 5 minutes
                unit = 2
            
            # Fetch historical data using get_bars (async method)
            bars_df = asyncio.run(self.sdk_client.get_bars(
                symbol=symbol,
                interval=interval,
                unit=unit,
                limit=count,
                start_time=start_date,
                end_time=end_date
            ))
            
            if bars_df is not None and len(bars_df) > 0:
                # Convert Polars DataFrame to list of dicts
                return [
                    {
                        "timestamp": row['timestamp'],
                        "open": float(row['open']),
                        "high": float(row['high']),
                        "low": float(row['low']),
                        "close": float(row['close']),
                        "volume": int(row['volume'])
                    }
                    for row in bars_df.iter_rows(named=True)
                ]
            return []
        except Exception as e:
            logger.error(f"Error fetching historical bars: {e}")
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
        api_token: API token for TopStep (required)
        username: TopStep username/email (required for SDK v3.5+)
    
    Returns:
        TopStepBroker instance
    
    Raises:
        ValueError: If API token is missing
    """
    if not api_token:
        raise ValueError("API token is required for TopStep broker")
    return TopStepBroker(api_token=api_token, username=username)

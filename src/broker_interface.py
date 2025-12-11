"""
Broker Interface Abstraction Layer
Provides clean separation between trading strategy and broker execution.
Supports multiple brokers through a common interface.
"""

from abc import ABC, abstractmethod
from typing import Dict, Any, Optional, Callable, List
from datetime import datetime
import logging
import time
import asyncio

# CRITICAL: Suppress ALL project_x_py loggers BEFORE importing the SDK
# This catches the root logger and all child loggers (statistics, order_manager, position_manager, etc.)
class _SuppressProjectXLoggers(logging.Filter):
    def filter(self, record):
        return not record.name.startswith('project_x_py')

# Install filter on root logger to catch ALL project_x_py loggers
logging.getLogger().addFilter(_SuppressProjectXLoggers())

# Also suppress the parent logger directly with extreme prejudice
_px_logger = logging.getLogger('project_x_py')
_px_logger.setLevel(logging.CRITICAL + 1)  # Beyond CRITICAL to block everything
_px_logger.propagate = False
_px_logger.handlers = []
_px_logger.addHandler(logging.NullHandler())  # Add null handler to absorb any logs
_px_logger.disabled = True  # Completely disable the logger

# Import broker SDKs (optional dependencies)
# NOTE: Moved imports inside methods to avoid initialization errors at module import time
BROKER_SDK_AVAILABLE = False
try:
    import project_x_py
    # Only test if the module exists, don't import classes yet (they may have initialization bugs)
    BROKER_SDK_AVAILABLE = True
except ImportError:
    logging.warning("Broker SDK (project-x-py) not installed - some broker operations may not work")

# Import WebSocket streamer
try:
    from broker_websocket import BrokerWebSocketStreamer
    BROKER_WEBSOCKET_AVAILABLE = True
except ImportError:
    BROKER_WEBSOCKET_AVAILABLE = False
    logging.warning("Broker WebSocket module not found - live streaming will not work")


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
    
    def get_all_open_positions(self) -> List[Dict[str, Any]]:
        """
        Get all open positions from broker (for AI Mode).
        
        AI Mode needs to detect any position the user has opened, regardless
        of symbol, to manage stops and exits.
        
        Returns:
            List of position dicts with keys: symbol, quantity, side, entry_price
            Empty list if no positions or not supported
        """
        return []  # Default implementation - override in subclasses
    
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


class BrokerSDKImplementation(BrokerInterface):
    """
    Broker SDK implementation using Project-X SDK.
    Wraps broker API calls with error handling and retry logic.
    Compatible with brokers that support the Project-X SDK protocol.
    """
    
    def __init__(self, api_token: str, username: str = None, max_retries: int = 3, timeout: int = 30, instrument: str = None):
        """
        Initialize broker connection.
        
        Args:
            api_token: Broker API token for authentication
            username: Broker username/email (required for SDK v3.5+)
            max_retries: Maximum number of retry attempts
            timeout: Request timeout in seconds
            instrument: Trading instrument symbol (must be configured by user)
        """
        self.api_token = api_token
        self.username = username
        self.max_retries = max_retries
        self.timeout = timeout
        self.instrument = instrument  # Store for TradingSuiteConfig
        self.connected = False
        self.circuit_breaker_open = False
        self.failure_count = 0
        self.circuit_breaker_threshold = 10  # Increased from 5 - more resilient
        self.circuit_breaker_reset_time = None  # Track when to auto-reset
        self.circuit_breaker_cooldown_seconds = 30  # Auto-reset after 30 seconds
        
        # PROFESSIONAL SAFEGUARD: Order deduplication tracking
        # Prevents duplicate orders from being sent to broker within short timeframe
        self._recent_orders: Dict[str, float] = {}  # order_hash -> timestamp
        self._order_dedup_window_seconds = 2.0  # Prevent duplicate orders within 2 seconds
        
        # TopStep SDK client (Project-X)
        self.sdk_client: Optional[ProjectX] = None
        self.trading_suite: Optional[TradingSuite] = None
        self._trading_suite_loop_id: Optional[int] = None  # Track which event loop trading_suite is bound to
        
        # WebSocket streamer for live data
        self.websocket_streamer: Optional[BrokerWebSocketStreamer] = None
        self._contract_id_cache: Dict[str, str] = {}  # symbol -> contract_id mapping (populated during connection)
        
        # Dynamic balance tracking for auto-reconfiguration
        self._last_configured_balance: float = 0.0
        self._balance_change_threshold: float = 0.05  # Reconfigure if balance changes by 5%
        self.config: Optional[Any] = None  # Store reference to config for dynamic updates
        self._session_token: Optional[str] = None  # Session token for WebSocket connections
        
        if not BROKER_SDK_AVAILABLE:
            logger.error("TopStep SDK (project-x-py) not installed!")
            logger.error("Install with: pip install project-x-py")
            raise RuntimeError("TopStep SDK not available")
    
    @property
    def session_token(self) -> Optional[str]:
        """
        Get the session token for WebSocket connections.
        This token is obtained after successful SDK connection.
        
        Returns:
            Session JWT token or None if not connected
        """
        if self._session_token:
            return self._session_token
        
        # Try to get token from SDK client if connected
        if self.sdk_client:
            try:
                # The SDK client stores the token after authentication
                token = getattr(self.sdk_client, 'token', None)
                if token:
                    self._session_token = token
                    return token
                # Try alternate attribute names
                token = getattr(self.sdk_client, 'session_token', None)
                if token:
                    self._session_token = token
                    return token
                token = getattr(self.sdk_client, 'access_token', None)
                if token:
                    self._session_token = token
                    return token
            except Exception as e:
                logger.debug(f"Could not get session token from SDK: {e}")
        
        return self.api_token  # Fallback to API token
    
    def _get_instrument_symbol(self, instrument: Any) -> str:
        """
        Get the symbol from an SDK Instrument object.
        
        The SDK may use different attribute names (symbolId vs symbol).
        This helper handles both cases with a safe fallback.
        
        Args:
            instrument: SDK Instrument object
            
        Returns:
            Symbol string, or empty string if not found
        """
        # Try symbolId first (newer SDK versions)
        symbol = getattr(instrument, 'symbolId', None)
        if symbol:
            return symbol
        
        # Fall back to symbol (older SDK versions)
        symbol = getattr(instrument, 'symbol', None)
        if symbol:
            return symbol
        
        # Return empty string as last resort
        return ''
    
    def _get_instrument_contract_id(self, instrument: Any) -> Optional[str]:
        """
        Get the contract ID from an SDK Instrument object.
        
        The SDK uses 'id' attribute for contract ID (not 'contract_id').
        This helper safely extracts the contract ID with proper error handling.
        
        Args:
            instrument: SDK Instrument object
            
        Returns:
            Contract ID string, or None if not found
        """
        # SDK Instrument objects use 'id' attribute for contract ID
        # Try 'id' first, then 'contract_id' as fallback for compatibility
        for attr in ('id', 'contract_id'):
            contract_id = getattr(instrument, attr, None)
            if contract_id:
                return str(contract_id)
        
        # Return None if not found
        return None
    
    def _extract_trading_symbol_from_contract_id(self, contract_id: str) -> Optional[str]:
        """
        Extract trading symbol from TopStep contract_id.
        
        Contract IDs look like "CON.F.US.EP.Z25" where:
        - CON = Contract prefix
        - F = Futures type
        - US = Country/region
        - EP = Broker symbol code (e.g., EP=ES, NP=NQ)
        - Z25 = Expiration month and year
        
        AI Mode uses this to identify the trading symbol for ANY position
        the user opens, regardless of which symbol was configured.
        
        Returns the standard trading symbol (e.g., "ES", "NQ") or None if cannot extract.
        """
        if not contract_id:
            return None
        
        # Try to load symbol specs for reverse lookup
        try:
            from symbol_specs import SYMBOL_SPECS
        except ImportError:
            return None
        
        contract_upper = contract_id.upper()
        
        # Look for broker symbol patterns in the contract_id
        for symbol, spec in SYMBOL_SPECS.items():
            if hasattr(spec, 'broker_symbols') and spec.broker_symbols:
                topstep_symbol = spec.broker_symbols.get('topstep', '')
                if topstep_symbol:
                    topstep_upper = topstep_symbol.upper()
                    # Check if the broker symbol is contained in the contract_id
                    # E.g., "F.US.EP" is in "CON.F.US.EP.Z25"
                    if topstep_upper in contract_upper:
                        return symbol
                    # Also check for individual parts (e.g., ".EP." in contract)
                    broker_parts = topstep_upper.split('.')
                    if len(broker_parts) >= 2:
                        # Check if the key part (like "EP") is in the contract
                        key_part = broker_parts[-1]  # Last part is usually the symbol code
                        if f".{key_part}." in contract_upper or contract_upper.endswith(f".{key_part}"):
                            return symbol
        
        return None
    
    @staticmethod
    def _cleanup_event_loop(loop: asyncio.AbstractEventLoop) -> None:
        """
        Properly clean up an asyncio event loop to prevent Windows proactor errors.
        
        On Windows, the ProactorEventLoop can have its proactor set to None when
        the loop is closed before all async operations complete, leading to:
        AttributeError: 'NoneType' object has no attribute 'send'
        
        This method ensures all pending tasks are cancelled and async generators
        are shut down before closing the loop.
        
        Args:
            loop: The event loop to clean up
        """
        try:
            # Check if loop is already closed
            if loop.is_closed():
                return
            
            # Cancel all pending tasks
            pending = asyncio.all_tasks(loop)
            for task in pending:
                task.cancel()
            
            # Wait for all tasks to complete cancellation
            if pending:
                loop.run_until_complete(asyncio.gather(*pending, return_exceptions=True))
            
            # Shutdown async generators
            loop.run_until_complete(loop.shutdown_asyncgens())
            
            # Now safe to close the loop
            loop.close()
        except Exception:
            # If cleanup fails, still try to close the loop
            # Suppress any errors as we're in cleanup
            try:
                if not loop.is_closed():
                    loop.close()
            except Exception:
                pass
    
    def _get_position_symbol(self, position: Any) -> str:
        """
        Get the symbol from an SDK Position object.
        
        Position objects may use different attribute names depending on SDK version:
        - contract_id: The contract identifier
        - instrument: An instrument object with symbol info
        - symbol/symbolId: Direct symbol attribute
        
        For AI Mode: This must work with ANY symbol the user trades,
        not just the configured symbol. Uses contract_id extraction.
        
        Args:
            position: SDK Position object
            
        Returns:
            Symbol string, or empty string if not found
        """
        # Try contract_id first (most common for Position objects)
        contract_id = getattr(position, 'contract_id', None)
        if contract_id:
            # contract_id might be like "CON.F.US.EP.Z25" - extract symbol
            # Try to get symbol from cache reverse lookup
            for symbol, cached_id in self._contract_id_cache.items():
                if cached_id == contract_id:
                    return symbol
            
            # If not in cache, try to extract trading symbol from contract_id pattern
            # This is critical for AI Mode which can trade ANY symbol
            extracted_symbol = self._extract_trading_symbol_from_contract_id(str(contract_id))
            if extracted_symbol:
                return extracted_symbol
            
            # If cannot extract, return the contract_id as-is (fallback)
            return str(contract_id)
        
        # Try instrument attribute (if Position has embedded instrument)
        instrument = getattr(position, 'instrument', None)
        if instrument:
            return self._get_instrument_symbol(instrument)
        
        # Try direct symbol attributes
        for attr in ['symbol', 'symbolId', 'symbol_id']:
            symbol = getattr(position, attr, None)
            if symbol:
                return str(symbol)
        
        # Last resort - return empty string
        return ''
    
    def connect(self, max_retries: int = None) -> bool:
        """
        Connect to TopStep SDK with retry logic.
        
        Args:
            max_retries: Override default max retries (default: 3)
        
        Returns:
            True if connected, False if all retries failed
        """
        import asyncio
        
        if self.circuit_breaker_open:
            logger.error("Circuit breaker is open - cannot connect")
            return False
        
        # Use the async version wrapped in asyncio.run
        retries = max_retries if max_retries is not None else self.max_retries
        return asyncio.run(self.connect_async(retries))
    
    async def connect_async(self, max_retries: int = 3) -> bool:
        """
        Connect to TopStep SDK asynchronously with exponential backoff retry.
        
        Args:
            max_retries: Maximum retry attempts
        
        Returns:
            True if connected, False if all retries failed
        """
        # Import SDK classes here to avoid module-level initialization errors
        from project_x_py import ProjectX, ProjectXConfig, TradingSuite, TradingSuiteConfig
        from project_x_py.realtime.core import ProjectXRealtimeClient
        
        # Helper to forcefully suppress JSON spam loggers
        def _suppress_spam_loggers():
            import logging
            # Suppress root project_x_py logger with extreme prejudice
            px_logger = logging.getLogger('project_x_py')
            px_logger.setLevel(logging.CRITICAL + 1)  # Beyond CRITICAL to block everything
            px_logger.propagate = False
            px_logger.handlers = []
            px_logger.addHandler(logging.NullHandler())  # Add null handler to absorb any logs
            px_logger.disabled = True  # Completely disable the logger
            
            # Iterate over all existing loggers and suppress any from project_x_py
            # This catches child loggers like project_x_py.statistics.bounded_statistics
            for name in list(logging.Logger.manager.loggerDict.keys()):
                if name.startswith('project_x_py'):
                    try:
                        child_logger = logging.getLogger(name)
                        child_logger.setLevel(logging.CRITICAL + 1)  # Beyond CRITICAL
                        child_logger.propagate = False
                        child_logger.handlers = []
                        child_logger.addHandler(logging.NullHandler())  # Add null handler
                        child_logger.disabled = True  # Completely disable
                    except Exception:
                        pass

        if self.circuit_breaker_open:
            logger.error("Circuit breaker is open - cannot connect")
            return False
        
        for attempt in range(max_retries):
            try:
                if attempt > 0:
                    # Exponential backoff: 2^attempt seconds (2s, 4s, 8s)
                    wait_time = min(2 ** attempt, 30)  # Max 30 seconds
                    await asyncio.sleep(wait_time)
                
                
                # Initialize SDK client with username and API key
                self.sdk_client = ProjectX(
                    username=self.username or "",
                    api_key=self.api_token,
                    config=ProjectXConfig()
                )
                
                # Suppress logs immediately after client init
                _suppress_spam_loggers()
                
                # Authenticate first (async method)
                try:
                    await self.sdk_client.authenticate()
                    # Give SDK a moment to establish session
                    await asyncio.sleep(0.5)
                except Exception as auth_error:
                    logger.error(f"Authentication error: {auth_error}")
                    if attempt == max_retries - 1:
                        # Last attempt failed
                        logger.error(f"[FAILED] Authentication failed after {max_retries} attempts")
                        self._record_failure()
                        return False
                    else:
                        # Will retry
                        logger.warning("Authentication failed, will retry...")
                        continue
                
                # Suppress logs again after authentication
                _suppress_spam_loggers()
                
                # Test connection by getting account info first
                try:
                    account = self.sdk_client.get_account_info()
                except Exception as account_error:
                    logger.error(f"Failed to get account info: {account_error}")
                    if attempt == max_retries - 1:
                        logger.error(f"[FAILED] Account query failed after {max_retries} attempts")
                        self._record_failure()
                        return False
                    else:
                        logger.warning("Account query failed, will retry...")
                        continue
                
                # Initialize WebSocket streamer first (needed for TradingSuite)
                try:
                    session_token = self.sdk_client.get_session_token()
                    if session_token:
                        self.websocket_streamer = BrokerWebSocketStreamer(session_token)
                        if self.websocket_streamer.connect():
                            pass
                        else:
                            logger.warning("WebSocket connection failed - will use REST API polling")
                    else:
                        logger.warning("No session token available - WebSocket disabled")
                except Exception as ws_error:
                    logger.warning(f"WebSocket initialization failed: {ws_error} - will use REST API")
                    self.websocket_streamer = None
                
                # Initialize trading suite for order placement (requires realtime_client)
                try:
                    # TradingSuite needs the SDK's realtime client for live order updates
                    # Get JWT token and account info to initialize realtime client
                    jwt_token = self.sdk_client.get_session_token()
                    account_info = self.sdk_client.get_account_info()
                    account_id = str(getattr(account_info, 'id', getattr(account_info, 'account_id', '')))
                    
                    if jwt_token and account_id:
                        # Initialize ProjectX realtime client
                        realtime_client = ProjectXRealtimeClient(
                            jwt_token=jwt_token,
                            account_id=account_id
                        )
                        
                        # Now initialize TradingSuite with the realtime client
                        self.trading_suite = TradingSuite(
                            client=self.sdk_client,
                            realtime_client=realtime_client,
                            config=TradingSuiteConfig(instrument=self.instrument)
                        )
                        
                        # Track which event loop this trading_suite is bound to
                        try:
                            current_loop = asyncio.get_running_loop()
                            self._trading_suite_loop_id = id(current_loop)
                        except RuntimeError:
                            self._trading_suite_loop_id = None
                        
                        # Suppress logs FINAL time after TradingSuite init (which creates the noisy managers)
                        _suppress_spam_loggers()
                        
                    else:
                        logger.warning("Missing JWT token or account ID - order placement disabled")
                        self.trading_suite = None
                except Exception as ts_error:
                    logger.warning(f"Trading suite initialization failed: {ts_error}")
                    self.trading_suite = None
                
                # Connection successful! Setup account info
                if account:
                    account_id = getattr(account, 'account_id', getattr(account, 'id', 'N/A'))
                    account_balance = float(getattr(account, 'balance', getattr(account, 'equity', 0)))
                    
                    logger.info(f"✅ Broker Connected - Account: {account_id} | Balance: ${account_balance:,.2f}")
                    
                    # AUTO-CONFIGURE: Set risk limits based on account size
                    # This makes the bot work on ANY TopStep account automatically!
                    from config import BotConfiguration
                    config = BotConfiguration()
                    config.auto_configure_for_account(account_balance, logger)
                    
                    # Store config and balance for dynamic reconfiguration
                    self.config = config
                    self._last_configured_balance = account_balance
                    
                    # CRITICAL: Cache contract IDs while event loop is still active
                    # This MUST happen here before asyncio.run() completes and closes the loop
                    try:
                        # Modified to handle known Windows asyncio/proactor 'NoneType' send error
                        try:
                            instruments = await self.sdk_client.search_instruments(query=self.instrument)
                        except Exception as e:
                            if "NoneType" in str(e) and "send" in str(e):
                                logger.debug(f"Ignored 'NoneType' send error during initial cache for {self.instrument}")
                                instruments = []
                            else:
                                raise e
                        if instruments and len(instruments) > 0:
                            # Use first match for caching (attribute is 'id' not 'contract_id')
                            first_contract = getattr(instruments[0], 'id', None)
                            if first_contract:
                                self._contract_id_cache[self.instrument] = first_contract
                            else:
                                logger.warning(f"No contract ID found for {self.instrument}")
                        else:
                            logger.warning(f"No instruments found for {self.instrument}")
                    except Exception as cache_err:
                        logger.error(f"Failed to cache contract ID: {cache_err}")
                    
                    # SUCCESS! Connection established
                    self.connected = True
                    self.failure_count = 0
                    return True
                else:
                    logger.error("Account info was None")
                    if attempt == max_retries - 1:
                        logger.error(f"[FAILED] Connection failed after {max_retries} attempts")
                        self._record_failure()
                        return False
                    else:
                        logger.warning("Will retry connection...")
                        continue
                
            except Exception as e:
                logger.error(f"Connection attempt {attempt + 1} failed: {e}")
                if attempt == max_retries - 1:
                    # Last attempt - fail permanently
                    logger.error(f"[FAILED] All {max_retries} connection attempts failed")
                    self._record_failure()
                    return False
                else:
                    # Will retry
                    logger.warning(f"Will retry connection (error: {str(e)[:100]}...)")
                    continue
        
        # Should never reach here, but handle it gracefully
        logger.error("[FAILED] Unexpected exit from connection loop")
        self._record_failure()
        return False
    
    def disconnect(self) -> None:
        """Disconnect from TopStep SDK and WebSocket."""
        try:
            # Use async disconnect if possible to properly close httpx connections
            try:
                loop = asyncio.get_running_loop()
                # Already in async context - can't use asyncio.run
                # Just do sync cleanup
                self._disconnect_sync()
            except RuntimeError:
                # No running loop - use asyncio.run for proper cleanup
                asyncio.run(self._disconnect_async())
        except Exception as e:
            logger.error(f"Error disconnecting from TopStep SDK: {e}")
    
    def _disconnect_sync(self) -> None:
        """Synchronous disconnect fallback (doesn't close httpx connections properly)."""
        # Disconnect WebSocket streamer first
        if self.websocket_streamer:
            try:
                self.websocket_streamer.disconnect()
                self.websocket_streamer = None
            except Exception as e:
                pass
        
        # Close SDK connections
        if self.trading_suite:
            self.trading_suite = None
            self._trading_suite_loop_id = None
        if self.sdk_client:
            self.sdk_client = None
        self.connected = False
    
    async def _disconnect_async(self) -> None:
        """
        Asynchronously disconnect and properly close httpx connections.
        
        CRITICAL FIX: This method explicitly closes httpx HTTP/2 connection pools
        to prevent the 'NoneType' object has no attribute 'send' error.
        
        The project_x_py SDK uses httpx clients with connection pools tied to the
        event loop. When asyncio.run() closes the event loop, these connections
        become invalid but still referenced. This method properly closes them.
        
        NOTE: This relies on internal SDK structure (_client attribute). If the
        SDK changes its internal implementation, this may need updates. The code
        uses hasattr() checks to be defensive against such changes.
        """
        # Disconnect WebSocket streamer first
        if self.websocket_streamer:
            try:
                self.websocket_streamer.disconnect()
                self.websocket_streamer = None
            except Exception as e:
                pass
        
        # Properly close httpx clients in SDK before releasing references
        # This prevents the 'NoneType' send error on reconnection
        if self.sdk_client:
            try:
                # Close the httpx client inside the SDK (if it has an aclose method)
                # Uses private attribute _client - this is necessary as SDK doesn't
                # provide a public cleanup method
                if hasattr(self.sdk_client, '_client') and hasattr(self.sdk_client._client, 'aclose'):
                    await self.sdk_client._client.aclose()
                # Also try direct aclose on sdk_client (if _client doesn't exist or doesn't have aclose)
                if hasattr(self.sdk_client, 'aclose'):
                    await self.sdk_client.aclose()
            except Exception as e:
                logger.debug(f"Error closing SDK httpx client: {e}")
        
        # Close trading suite connections
        if self.trading_suite:
            try:
                # Close the project_x client inside trading suite
                # Uses private attributes - necessary as SDK doesn't provide public cleanup
                if hasattr(self.trading_suite, 'project_x') and hasattr(self.trading_suite.project_x, '_client'):
                    if hasattr(self.trading_suite.project_x._client, 'aclose'):
                        await self.trading_suite.project_x._client.aclose()
            except Exception as e:
                logger.debug(f"Error closing TradingSuite httpx client: {e}")
        
        # Clear references
        self.trading_suite = None
        self._trading_suite_loop_id = None
        self.sdk_client = None
        self.connected = False
    
    def verify_connection(self) -> bool:
        """
        Verify connection is still alive by testing account access.
        This is called periodically by health monitor every 30 seconds.
        
        Returns:
            bool: True if connection is healthy, False if dead
        """
        if not self.connected or not self.sdk_client:
            return False
        
        try:
            # Quick health check - try to get account info
            # This tests the actual API connection, not just local state
            account = self.sdk_client.get_account_info()
            if account is None:
                logger.warning("[CONNECTION] Account info returned None - connection is dead")
                self.connected = False
                return False
            
            # Additional validation - check if we can get balance
            balance = getattr(account, 'balance', None)
            if balance is None:
                logger.warning("[CONNECTION] Account has no balance field - API may have changed")
                # Don't disconnect for this - might be API issue
            
            # Connection is alive and working
            return True
            
        except AttributeError as e:
            # SDK client might be None or invalid
            logger.error(f"[CONNECTION] SDK client invalid: {e}")
            self.connected = False
            return False
        except Exception as e:
            # Any other error means connection is broken
            logger.error(f"[CONNECTION] Health check failed: {e}")
            self.connected = False
            return False
    
    def _validate_sdk_client_state(self) -> bool:
        """
        PREVENTIVE: Validate SDK client is in a healthy state for operations.
        
        This proactively checks for common issues that could cause failures:
        - SDK client exists and has required methods
        - Trading suite is initialized
        - httpx client connections are valid (not stale)
        
        Returns:
            bool: True if SDK client is healthy, False if issues detected
        """
        if not self.connected or not self.sdk_client or not self.trading_suite:
            return False
        
        # Check SDK client has required methods
        required_methods = ['search_open_positions', 'get_account_info', '_refresh_authentication']
        for method in required_methods:
            if not hasattr(self.sdk_client, method):
                logger.warning(f"[SDK VALIDATION] SDK client missing method: {method}")
                return False
        
        # Check trading suite has required components
        if not hasattr(self.trading_suite, 'orders'):
            logger.warning("[SDK VALIDATION] Trading suite missing orders component")
            return False
        
        # Check httpx client is not stale (has _client attribute and it's not None)
        if hasattr(self.sdk_client, '_client'):
            if self.sdk_client._client is None:
                logger.warning("[SDK VALIDATION] httpx client is None - connection is stale")
                return False
        
        return True
    
    def _is_duplicate_order(self, symbol: str, side: str, quantity: int, order_type: str) -> bool:
        """
        PROFESSIONAL SAFEGUARD: Check if this order is a duplicate of a recent order.
        
        Prevents accidental duplicate orders from bugs, network issues, or race conditions.
        Orders are considered duplicates if they have the same parameters within 2 seconds.
        
        Args:
            symbol: Instrument symbol
            side: BUY or SELL
            quantity: Number of contracts
            order_type: MARKET, LIMIT, or STOP
        
        Returns:
            bool: True if this is a duplicate order (should be blocked)
        """
        import hashlib
        
        # Create order hash from parameters
        order_key = f"{symbol}|{side}|{quantity}|{order_type}"
        order_hash = hashlib.md5(order_key.encode()).hexdigest()
        
        current_time = time.time()
        
        # Clean up old entries (older than dedup window)
        expired_hashes = [
            h for h, t in self._recent_orders.items() 
            if current_time - t > self._order_dedup_window_seconds
        ]
        for h in expired_hashes:
            del self._recent_orders[h]
        
        # Check if this order was recently placed
        if order_hash in self._recent_orders:
            last_time = self._recent_orders[order_hash]
            elapsed = current_time - last_time
            logger.warning(f"[DUPLICATE BLOCKED] Order rejected - identical order placed {elapsed:.2f}s ago")
            logger.warning(f"  Order: {side} {quantity} {symbol} ({order_type})")
            return True
        
        # Record this order
        self._recent_orders[order_hash] = current_time
        return False
    
    def warm_connection_for_trading(self) -> bool:
        """
        Keep the HTTP/2 connection pool warm for order placement.
        
        HTTP/2 connections can go stale if not used for 60-300 seconds.
        The verify_connection() method only exercises GET requests.
        Order placement uses POST requests through a different connection.
        
        This method exercises the POST path by refreshing the auth token,
        which uses the same httpx client and connection pool as order placement.
        
        Should be called every 60 seconds to keep POST connections alive.
        
        Returns:
            bool: True if connection is warm, False if it failed
        """
        if not self.connected or not self.sdk_client or not self.trading_suite:
            return False
        
        try:
            import asyncio
            
            # Refresh token - this exercises the POST code path
            # The token refresh uses the same httpx connection pool as orders
            async def warm_connection_async():
                try:
                    await self.sdk_client._refresh_authentication()
                    return True
                except Exception as e:
                    # Token might not need refresh, try a search instead
                    # This also exercises the connection
                    try:
                        await self.sdk_client.search_open_positions()
                        return True
                    except Exception:
                        return False
            
            try:
                loop = asyncio.get_running_loop()
                # Already in async context - skip to avoid nested loops
                return True
            except RuntimeError:
                # No running loop - safe to use asyncio.run
                result = asyncio.run(warm_connection_async())
                return result
                
        except Exception as e:
            # Don't mark as disconnected for warm-up failures
            # The retry mechanism will handle actual order failures
            logger.debug(f"[KEEPALIVE] Connection warm-up check: {e}")
            return False
    
    async def _ensure_token_fresh(self) -> bool:
        """
        Ensure JWT token is fresh and refresh if needed.
        The SDK handles this automatically, but we call it explicitly for long-running bots.
        
        Returns:
            bool: True if token is fresh/refreshed, False if refresh failed
        """
        if not self.sdk_client or not self.connected:
            return False
        
        try:
            # SDK's built-in method checks expiry and refreshes if within 5 minutes
            await self.sdk_client._refresh_authentication()
            return True
        except Exception as e:
            logger.error(f"Token refresh failed: {e}")
            return False
    
    async def _ensure_trading_suite_ready(self) -> bool:
        """
        Ensure trading_suite is bound to the current event loop.
        
        CRITICAL FIX: When asyncio.run() is called repeatedly (e.g., in connect() and place_order()),
        it creates new event loops. The httpx clients in trading_suite become stale because they're
        tied to closed event loops, causing 'NoneType' object has no attribute 'send' errors.
        
        This method recreates the trading_suite if it's bound to a different event loop.
        
        Returns:
            bool: True if trading_suite is ready, False on error
        """
        if not self.sdk_client or not self.connected:
            logger.debug("[ORDER] Cannot ensure trading_suite ready - not connected")
            return False
        
        try:
            # Import SDK classes
            from project_x_py import TradingSuite, TradingSuiteConfig
            from project_x_py.realtime.core import ProjectXRealtimeClient
            
            # Get current event loop to check if we need to reinitialize
            try:
                current_loop = asyncio.get_running_loop()
                current_loop_id = id(current_loop)
            except RuntimeError:
                logger.error("[ORDER] No running event loop - cannot initialize trading_suite")
                return False
            
            # Check if trading_suite needs reinitialization
            # Only reinitialize if it's bound to a different event loop (or doesn't exist)
            if self.trading_suite is None or self._trading_suite_loop_id != current_loop_id:
                logger.debug(f"[ORDER] Reinitializing trading_suite for current event loop (old_id={self._trading_suite_loop_id}, new_id={current_loop_id})")
                
                # CRITICAL: Clean up old trading_suite and realtime client before creating new one
                # This prevents multiple active sessions that could cause "knocked out" issues
                if self.trading_suite is not None:
                    try:
                        # Try to close the realtime client if it has a close/disconnect method
                        if hasattr(self.trading_suite, 'realtime_client'):
                            realtime = self.trading_suite.realtime_client
                            if hasattr(realtime, 'close'):
                                try:
                                    await realtime.close()
                                except Exception as e:
                                    logger.debug(f"[ORDER] Could not close realtime client: {e}")
                            elif hasattr(realtime, 'disconnect'):
                                try:
                                    await realtime.disconnect()
                                except Exception as e:
                                    logger.debug(f"[ORDER] Could not disconnect realtime client: {e}")
                        
                        # Close httpx client in trading_suite to free resources
                        if hasattr(self.trading_suite, 'project_x') and hasattr(self.trading_suite.project_x, '_client'):
                            if hasattr(self.trading_suite.project_x._client, 'aclose'):
                                try:
                                    await self.trading_suite.project_x._client.aclose()
                                except Exception as e:
                                    logger.debug(f"[ORDER] Could not close httpx client: {e}")
                    except Exception as cleanup_err:
                        logger.debug(f"[ORDER] Error cleaning up old trading_suite: {cleanup_err}")
                    
                    # Clear the reference
                    self.trading_suite = None
                
                # CRITICAL FIX: Also recreate SDK client to get fresh httpx connection
                # The old sdk_client has a corrupted httpx client tied to a dead event loop
                from project_x_py import ProjectX
                
                logger.info("[ORDER] Recreating SDK client with fresh httpx connection...")
                
                # Create fresh SDK client
                fresh_sdk_client = ProjectX(
                    username=self.username, 
                    api_key=self.api_token
                )
                
                # Authenticate the fresh SDK client
                await fresh_sdk_client.authenticate()
                
                # Update our reference
                self.sdk_client = fresh_sdk_client
                
                # Now get fresh JWT token and account info from new client
                jwt_token = self.sdk_client.get_session_token()
                account_info = self.sdk_client.get_account_info()
                account_id = str(getattr(account_info, 'id', getattr(account_info, 'account_id', '')))
                
                if not jwt_token or not account_id:
                    logger.error("[ORDER] Cannot reinitialize trading_suite - missing authentication credentials or account ID")
                    return False
                
                # Create new realtime client bound to current loop
                realtime_client = ProjectXRealtimeClient(
                    jwt_token=jwt_token,
                    account_id=account_id
                )
                
                # Recreate trading_suite with fresh SDK client
                self.trading_suite = TradingSuite(
                    client=self.sdk_client,
                    realtime_client=realtime_client,
                    config=TradingSuiteConfig(instrument=self.instrument)
                )
                
                # Track the event loop this trading_suite is bound to
                self._trading_suite_loop_id = current_loop_id
                logger.debug("[ORDER] Trading suite reinitialized successfully")
            else:
                logger.debug("[ORDER] Trading suite already bound to current event loop - reusing")
            
            return True
            
        except Exception as e:
            logger.error(f"[ORDER] Failed to reinitialize trading_suite: {e}")
            return False
    
    def get_account_equity(self) -> float:
        """
        Get account equity from TopStep.
        Automatically reconfigures risk limits if balance changes significantly.
        Ensures 100% TopStep compliance at all times.
        """
        if not self.connected or not self.sdk_client:
            logger.error("Cannot get equity: not connected")
            return 0.0
        
        try:
            account = self.sdk_client.get_account_info()
            if account:
                current_balance = float(account.balance or 0.0)
                
                # CRITICAL: Always reconfigure if config doesn't exist (safety net)
                if not self.config:
                    logger.warning("[WARNING] Config missing - initializing auto-configuration")
                    from config import BotConfiguration
                    self.config = BotConfiguration()
                    if self.config.auto_configure_for_account(current_balance, logger):
                        self._last_configured_balance = current_balance
                    return current_balance
                
                
                # Check if balance changed significantly (5% threshold for reconfiguration)
                if self._last_configured_balance > 0:
                    balance_change_pct = abs(current_balance - self._last_configured_balance) / self._last_configured_balance
                    
                    if balance_change_pct >= self._balance_change_threshold:
                        logger.info("=" * 80)
                        logger.info("💰 BALANCE CHANGED - AUTO-RECONFIGURING RISK LIMITS")
                        logger.info("=" * 80)
                        logger.info(f"Previous Balance: ${self._last_configured_balance:,.2f}")
                        logger.info(f"Current Balance: ${current_balance:,.2f}")
                        logger.info(f"Change: {balance_change_pct * 100:.1f}%")
                        
                        # Reconfigure with new balance (with safety checks)
                        if self.config.auto_configure_for_account(current_balance, logger):
                            self._last_configured_balance = current_balance
                            logger.info("[SUCCESS] Risk limits updated successfully")
                        else:
                            logger.error("❌ Failed to reconfigure - keeping previous limits")
                            logger.error(f"Still using limits for ${self._last_configured_balance:,.2f} balance")
                
                return current_balance
            return 0.0
        except Exception as e:
            logger.error(f"Error getting account equity: {e}")
            self._record_failure()
            return 0.0
    
    def get_position_quantity(self, symbol: str) -> int:
        """
        Get position quantity from TopStep.
        
        PREVENTIVE MEASURES:
        - Validates SDK client state before querying
        - Uses proper event loop cleanup
        - Handles all error cases gracefully
        """
        if not self.connected or not self.sdk_client:
            # Silent return during expected disconnection (maintenance, shutdown, etc.)
            # Position reconciliation is already suppressed during these times
            return 0
        
        # PREVENTIVE: Validate SDK client state before position query
        # This prevents stale client references from causing position tracking issues
        if not self._validate_sdk_client_state():
            logger.warning("[POSITION] SDK client validation failed - reconnecting to prevent position tracking issues")
            if self.connect():
                logger.info("[POSITION] Reconnected successfully")
            else:
                logger.error("[POSITION] Reconnect failed - cannot query positions")
                return 0
        
        try:
            # Use search_open_positions() instead of deprecated get_positions()
            # This is an async function, so we need to run it in the event loop
            import asyncio
            try:
                loop = asyncio.get_running_loop()
                # If loop is already running, we can't use run_until_complete
                # Return 0 and log debug - position reconciliation will happen async
                return 0
            except RuntimeError:
                # No running loop, safe to create one
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                try:
                    positions = loop.run_until_complete(self.sdk_client.search_open_positions())
                    for pos in positions:
                        # Get symbol from position - try multiple attribute names
                        # Position may use contract_id, instrument, symbol, or symbolId
                        pos_symbol = self._get_position_symbol(pos)
                        if pos_symbol == symbol or pos_symbol == symbol.lstrip('/'):
                            # Return signed quantity (positive for long, negative for short)
                            # SDK uses 'size' attribute (not 'quantity') and 'is_long' property (not position_type.value)
                            qty = int(pos.size)
                            self._record_success()  # Successful position query
                            return qty if pos.is_long else -qty
                    self._record_success()  # Successful query (no position)
                    return 0  # No position found
                finally:
                    self._cleanup_event_loop(loop)
        except AttributeError as e:
            # Common Windows asyncio proactor error during shutdown - ignore
            if "'NoneType' object has no attribute 'send'" in str(e):
                return 0
            logger.error(f"Error getting position quantity: {e}")
            self._record_failure()
            return 0
        except Exception as e:
            # Handle event loop closed errors gracefully - don't count as failure
            if "Event loop is closed" in str(e):
                return 0  # Don't record failure for shutdown issues
            logger.error(f"Error getting position quantity: {e}")
            self._record_failure()
            return 0
    
    def get_all_open_positions(self) -> List[Dict[str, Any]]:
        """
        Get all open positions from TopStep (for AI Mode).
        
        AI Mode needs to detect any position the user has opened, regardless
        of symbol, to manage stops and exits.
        
        PREVENTIVE MEASURES:
        - Validates SDK client state before querying
        - Uses proper event loop cleanup
        - Thread-safe execution in async contexts
        
        Returns:
            List of position dicts with keys: symbol, quantity, side
            Empty list if no positions
        """
        if not self.connected or not self.sdk_client:
            return []
        
        # PREVENTIVE: Validate SDK client state before position query
        # This prevents stale client references from causing position tracking issues
        if not self._validate_sdk_client_state():
            logger.warning("[POSITION] SDK client validation failed - reconnecting to prevent position tracking issues")
            if self.connect():
                logger.info("[POSITION] Reconnected successfully")
            else:
                logger.error("[POSITION] Reconnect failed - cannot query positions")
                return []
        
        try:
            import asyncio
            from concurrent.futures import ThreadPoolExecutor
            
            # Define the async query function
            async def query_positions_async():
                return await self.sdk_client.search_open_positions()
            
            # Define the sync wrapper that runs in a thread
            def run_in_thread():
                thread_loop = asyncio.new_event_loop()
                asyncio.set_event_loop(thread_loop)
                try:
                    return thread_loop.run_until_complete(query_positions_async())
                finally:
                    BrokerSDKImplementation._cleanup_event_loop(thread_loop)
            
            try:
                loop = asyncio.get_running_loop()
                # If loop is already running, use ThreadPoolExecutor to run in a separate thread
                # This is critical for AI Mode which runs position scans from event handlers
                with ThreadPoolExecutor(max_workers=1) as executor:
                    future = executor.submit(run_in_thread)
                    positions = future.result(timeout=10)
            except RuntimeError:
                # No running loop, safe to create one directly
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                try:
                    positions = loop.run_until_complete(query_positions_async())
                finally:
                    self._cleanup_event_loop(loop)
            
            # Process positions
            result = []
            for pos in positions:
                pos_symbol = self._get_position_symbol(pos)
                # SDK uses 'size' attribute (not 'quantity') and 'is_long' property (not position_type.value)
                qty = int(pos.size)
                side = "long" if pos.is_long else "short"
                signed_qty = qty if side == "long" else -qty
                
                # Try to get the actual entry price from the position object
                # TopStep SDK typically provides avg_price or average_price
                entry_price = None
                for price_attr in ['avg_price', 'average_price', 'avgPrice', 'averagePrice', 'entry_price', 'entryPrice', 'price']:
                    if hasattr(pos, price_attr):
                        entry_price = getattr(pos, price_attr)
                        if entry_price and float(entry_price) > 0:
                            entry_price = float(entry_price)
                            break
                
                result.append({
                    "symbol": pos_symbol,
                    "quantity": qty,
                    "signed_quantity": signed_qty,
                    "side": side,
                    "entry_price": entry_price  # Actual entry price from broker
                })
            
            self._record_success()
            return result
                
        except Exception as e:
            if "Event loop is closed" not in str(e):
                pass
            return []
    
    def _ensure_order_ready(self) -> bool:
        """
        PREVENTIVE: Ensure broker is ready for order placement.
        
        This helper method performs all validation and reconnection logic
        to prepare for order placement. Used by all order methods to reduce duplication.
        
        Returns:
            bool: True if ready for order placement, False otherwise
        """
        # Step 1: Validate SDK client state
        if not self._validate_sdk_client_state():
            logger.warning("[ORDER] SDK client validation failed - reconnecting to prevent order issues")
            self.disconnect()
            if not self.connect():
                logger.error("[ORDER] Reconnect after validation failure failed - cannot place order")
                return False
            logger.info("[ORDER] Reconnected successfully after validation check")
        
        # Step 2: Verify connection is still alive
        if not self.verify_connection():
            logger.warning("[ORDER] Connection dead - attempting reconnect before order")
            if not self.connect():
                logger.error("[ORDER] Reconnect failed - cannot place order")
                return False
            logger.info("[ORDER] Reconnected successfully - proceeding with order")
        
        # Step 3: Warm the POST connection
        if not self.warm_connection_for_trading():
            logger.warning("[ORDER] POST connection cold/dead - forcing full reconnect")
            self.disconnect()
            if not self.connect():
                logger.error("[ORDER] Full reconnect failed - cannot place order")
                return False
            logger.info("[ORDER] Full reconnect successful - proceeding with order")
        
        return True
    
    def place_market_order(self, symbol: str, side: str, quantity: int) -> Optional[Dict[str, Any]]:
        """
        Place market order using TopStep SDK.
        
        PREVENTIVE MEASURES:
        - Validates SDK client state before attempting order
        - Verifies connection health
        - Warms POST connection
        - Checks for duplicate orders
        - Handles all error cases with reconnection
        """
        if not self.connected or self.trading_suite is None:
            logger.error("Cannot place order: not connected")
            return None
        
        # PROFESSIONAL SAFEGUARD: Check for duplicate order
        if self._is_duplicate_order(symbol, side, quantity, "MARKET"):
            logger.error("[ORDER REJECTED] Duplicate market order blocked for safety")
            return None
        
        # PREVENTIVE: Ensure broker is ready for order placement (multi-layer validation)
        if not self._ensure_order_ready():
            return None
        
        try:
            import asyncio
            # Import order enums here to avoid module-level import issues
            from project_x_py import OrderSide, OrderType
            
            # Get contract ID for the symbol dynamically
            contract_id = self._get_contract_id_sync(symbol)
            if not contract_id:
                logger.error(f"Failed to resolve contract ID for {symbol}")
                return None
            
            # Convert side to OrderSide enum
            order_side = OrderSide.BUY if side.upper() == "BUY" else OrderSide.SELL
            
            
            # Define async wrapper
            async def place_order_async():
                # Refresh token if needed (for long-running bots)
                await self._ensure_token_fresh()
                
                # CRITICAL: Ensure trading_suite is bound to current event loop
                if not await self._ensure_trading_suite_ready():
                    raise Exception("Trading suite not ready for order placement")
                
                return await self.trading_suite.orders.place_market_order(
                    contract_id=contract_id,
                    side=order_side,
                    size=quantity
                )
            
            # Run async order placement - check for existing event loop
            try:
                loop = asyncio.get_running_loop()
                # If we get here, we're in an async context - use thread pool
                import concurrent.futures
                with concurrent.futures.ThreadPoolExecutor() as pool:
                    order_response = pool.submit(
                        lambda: asyncio.run(place_order_async())
                    ).result()
            except RuntimeError:
                # No running loop - safe to use asyncio.run
                order_response = asyncio.run(place_order_async())
            
            
            # Check for success - SDK may return different response formats
            if order_response:
                if hasattr(order_response, 'success') and order_response.success:
                    result = {
                        "order_id": getattr(order_response, 'orderId', 'unknown'),
                        "symbol": symbol,
                        "side": side,
                        "quantity": quantity,
                        "type": "MARKET",
                        "status": "SUBMITTED",
                        "filled_quantity": 0
                    }
                    self._record_success()  # Successful order
                    return result
                elif hasattr(order_response, 'order') and order_response.order:
                    # Alternative response format
                    order = order_response.order
                    result = {
                        "order_id": getattr(order, 'order_id', 'unknown'),
                        "symbol": symbol,
                        "side": side,
                        "quantity": quantity,
                        "type": "MARKET",
                        "status": getattr(order.status, 'value', 'SUBMITTED') if hasattr(order, 'status') else 'SUBMITTED',
                        "filled_quantity": 0
                    }
                    self._record_success()  # Successful order
                    return result
            
            # Order failed
            error_msg = getattr(order_response, 'errorMessage', None) if order_response else None
            logger.error(f"Market order placement failed: {error_msg or 'Unknown error'}")
            self._record_failure()
            return None
                
        except Exception as e:
            error_str = str(e)
            
            # Handle HTTP/2 connection drop - the connection died mid-request
            # This is recoverable by reconnecting and retrying once
            if "'NoneType' object has no attribute 'send'" in error_str:
                logger.warning("[ORDER] HTTP/2 connection dropped during order - attempting full reconnect")
                
                # Force disconnect with delay to let resources clean up
                self.disconnect()
                
                # Wait longer for connections to fully close and event loops to clean up
                # This is critical to avoid the same error on reconnect
                time.sleep(3)
                
                # Try reconnecting up to 3 times
                reconnected = False
                for attempt in range(3):
                    logger.info(f"[ORDER] Reconnect attempt {attempt+1}/3...")
                    if self.connect():
                        reconnected = True
                        logger.info("[ORDER] Reconnected successfully - retrying order")
                        break
                    time.sleep(1)
                
                if reconnected:
                    try:
                        # Retry the order once
                        contract_id = self._get_contract_id_sync(symbol)
                        if contract_id:
                            from project_x_py import OrderSide
                            order_side = OrderSide.BUY if side.upper() == "BUY" else OrderSide.SELL
                            
                            async def retry_order_async():
                                await self._ensure_token_fresh()
                                # CRITICAL: Ensure trading_suite is bound to current event loop
                                if not await self._ensure_trading_suite_ready():
                                    raise Exception("Trading suite not ready for order placement")
                                return await self.trading_suite.orders.place_market_order(
                                    contract_id=contract_id,
                                    side=order_side,
                                    size=quantity
                                )
                            
                            order_response = asyncio.run(retry_order_async())
                            
                            if order_response:
                                if hasattr(order_response, 'success') and order_response.success:
                                    result = {
                                        "order_id": getattr(order_response, 'orderId', 'unknown'),
                                        "symbol": symbol,
                                        "side": side,
                                        "quantity": quantity,
                                        "type": "MARKET",
                                        "status": "SUBMITTED",
                                        "filled_quantity": 0
                                    }
                                    logger.info("[ORDER] ✅ Retry successful - order placed")
                                    self._record_success()
                                    return result
                                elif hasattr(order_response, 'order') and order_response.order:
                                    order = order_response.order
                                    result = {
                                        "order_id": getattr(order, 'order_id', 'unknown'),
                                        "symbol": symbol,
                                        "side": side,
                                        "quantity": quantity,
                                        "type": "MARKET",
                                        "status": getattr(order.status, 'value', 'SUBMITTED') if hasattr(order, 'status') else 'SUBMITTED',
                                        "filled_quantity": 0
                                    }
                                    logger.info("[ORDER] ✅ Retry successful - order placed")
                                    self._record_success()
                                    return result
                    except Exception as retry_err:
                        logger.error(f"[ORDER] Retry also failed: {retry_err}")
                else:
                    logger.error("[ORDER] All 3 reconnect attempts failed - cannot place order")
                    logger.error("[ORDER] Please restart the bot to reset broker connection")
            
            logger.error(f"Error placing market order: {e}")
            import traceback
            traceback.print_exc()
            self._record_failure()
            return None
    
    def place_limit_order(self, symbol: str, side: str, quantity: int, limit_price: float) -> Optional[Dict[str, Any]]:
        """
        Place limit order using TopStep SDK.
        
        PREVENTIVE MEASURES:
        - Validates SDK client state before attempting order
        - Verifies connection health
        - Warms POST connection
        - Checks for duplicate orders
        - Handles all error cases with reconnection
        """
        if not self.connected or self.trading_suite is None:
            logger.error("Cannot place order: not connected")
            return None
        
        # PROFESSIONAL SAFEGUARD: Check for duplicate order
        if self._is_duplicate_order(symbol, side, quantity, "LIMIT"):
            logger.error("[ORDER REJECTED] Duplicate limit order blocked for safety")
            return None
        
        # PREVENTIVE: Ensure broker is ready for order placement (multi-layer validation)
        if not self._ensure_order_ready():
            return None
        
        try:
            import asyncio
            # Import order enums here to avoid module-level import issues
            from project_x_py import OrderSide, OrderType
            
            # Get contract ID for the symbol dynamically
            contract_id = self._get_contract_id_sync(symbol)
            if not contract_id:
                logger.error(f"Failed to resolve contract ID for {symbol}")
                return None
            
            # Convert side to OrderSide enum
            order_side = OrderSide.BUY if side.upper() == "BUY" else OrderSide.SELL
            
            
            # Define async wrapper
            async def place_order_async():
                # Refresh token if needed (for long-running bots)
                await self._ensure_token_fresh()
                
                # CRITICAL: Ensure trading_suite is bound to current event loop
                if not await self._ensure_trading_suite_ready():
                    raise Exception("Trading suite not ready for order placement")
                
                return await self.trading_suite.orders.place_limit_order(
                    contract_id=contract_id,
                    side=order_side,
                    size=quantity,
                    limit_price=limit_price
                )
            
            # Run async order placement - check for existing event loop
            try:
                loop = asyncio.get_running_loop()
                # If we get here, we're in an async context - use thread pool
                import concurrent.futures
                with concurrent.futures.ThreadPoolExecutor() as pool:
                    order_response = pool.submit(
                        lambda: asyncio.run(place_order_async())
                    ).result()
            except RuntimeError:
                # No running loop - safe to use asyncio.run
                order_response = asyncio.run(place_order_async())
            
            
            # Check for success - SDK may return different response formats
            if order_response:
                if hasattr(order_response, 'success') and order_response.success:
                    result = {
                        "order_id": getattr(order_response, 'orderId', 'unknown'),
                        "symbol": symbol,
                        "side": side,
                        "quantity": quantity,
                        "type": "LIMIT",
                        "limit_price": limit_price,
                        "status": "SUBMITTED",
                        "filled_quantity": 0
                    }
                    self._record_success()  # Successful order
                    return result
                elif hasattr(order_response, 'order') and order_response.order:
                    # Alternative response format
                    order = order_response.order
                    result = {
                        "order_id": getattr(order, 'order_id', 'unknown'),
                        "symbol": symbol,
                        "side": side,
                        "quantity": quantity,
                        "type": "LIMIT",
                        "limit_price": limit_price,
                        "status": getattr(order.status, 'value', 'SUBMITTED') if hasattr(order, 'status') else 'SUBMITTED',
                        "filled_quantity": 0
                    }
                    self._record_success()  # Successful order
                    return result
            
            # Order failed
            error_msg = getattr(order_response, 'errorMessage', None) if order_response else None
            logger.error(f"Limit order placement failed: {error_msg or 'Unknown error'}")
            self._record_failure()
            return None
                
        except Exception as e:
            logger.error(f"Error placing limit order: {e}")
            import traceback
            traceback.print_exc()
            self._record_failure()
            return None
    
    def cancel_order(self, order_id: str) -> bool:
        """Cancel an open order using TopStep SDK."""
        if not self.connected or self.trading_suite is None:
            logger.error("Cannot cancel order: not connected")
            return False
        
        try:
            import asyncio
            
            # Define async wrapper
            async def cancel_order_async():
                # Refresh token if needed
                await self._ensure_token_fresh()
                # CRITICAL: Ensure trading_suite is bound to current event loop
                if not await self._ensure_trading_suite_ready():
                    raise Exception("Trading suite not ready for order cancellation")
                return await self.trading_suite.orders.cancel_order(order_id=order_id)
            
            # Run async order cancellation - check for existing event loop
            try:
                loop = asyncio.get_running_loop()
                import concurrent.futures
                with concurrent.futures.ThreadPoolExecutor() as pool:
                    cancel_response = pool.submit(
                        lambda: asyncio.run(cancel_order_async())
                    ).result()
            except RuntimeError as e:
                # Handle "Event loop is closed" error gracefully
                if "Event loop is closed" in str(e):
                    logger.warning("Event loop closed during cancel - creating new loop")
                    loop = asyncio.new_event_loop()
                    asyncio.set_event_loop(loop)
                    try:
                        cancel_response = loop.run_until_complete(cancel_order_async())
                    finally:
                        self._cleanup_event_loop(loop)
                else:
                    cancel_response = asyncio.run(cancel_order_async())
            
            if cancel_response and cancel_response.success:
                self._record_success()  # Successful cancellation
                return True
            else:
                error_msg = cancel_response.errorMessage if cancel_response else "Unknown error"
                logger.error(f"Order cancellation failed: {error_msg}")
                self._record_failure()
                return False
                
        except AttributeError as e:
            # Handle 'NoneType' object has no attribute 'send' - asyncio shutdown issue
            if "'NoneType' object has no attribute 'send'" in str(e):
                logger.warning("Cancel order skipped - asyncio shutdown in progress")
                return False  # Don't record failure for shutdown issues
            logger.error(f"Error cancelling order: {e}")
            self._record_failure()
            return False
        except Exception as e:
            # Handle event loop closed errors gracefully
            if "Event loop is closed" in str(e):
                logger.warning("Event loop closed during cancel order - order may still be pending")
                return False  # Don't record failure for shutdown issues
            logger.error(f"Error cancelling order: {e}")
            self._record_failure()
            return False
    
    def place_stop_order(self, symbol: str, side: str, quantity: int, stop_price: float) -> Optional[Dict[str, Any]]:
        """
        Place stop order using TopStep SDK.
        
        PREVENTIVE MEASURES:
        - Validates SDK client state before attempting order
        - Verifies connection health
        - Warms POST connection
        - Checks for duplicate orders
        - Handles all error cases with reconnection
        """
        if not self.connected or self.trading_suite is None:
            logger.error("Cannot place order: not connected")
            return None
        
        # PROFESSIONAL SAFEGUARD: Check for duplicate order
        if self._is_duplicate_order(symbol, side, quantity, "STOP"):
            logger.error("[ORDER REJECTED] Duplicate stop order blocked for safety")
            return None
        
        # PREVENTIVE: Ensure broker is ready for order placement (multi-layer validation)
        if not self._ensure_order_ready():
            return None
        
        try:
            import asyncio
            # Import order enums here to avoid module-level import issues
            from project_x_py import OrderSide, OrderType
            
            # Get contract ID for the symbol dynamically (same as market orders)
            contract_id = self._get_contract_id_sync(symbol)
            if not contract_id:
                logger.error(f"Failed to resolve contract ID for {symbol}")
                return None
            
            # Convert side to SDK enum
            order_side = OrderSide.BUY if side.upper() == "BUY" else OrderSide.SELL
            
            # Define async wrapper - use contract_id and size (not symbol and quantity)
            async def place_order_async():
                # Refresh token if needed (for long-running bots)
                await self._ensure_token_fresh()
                
                # CRITICAL: Ensure trading_suite is bound to current event loop
                if not await self._ensure_trading_suite_ready():
                    raise Exception("Trading suite not ready for order placement")
                
                return await self.trading_suite.orders.place_stop_order(
                    contract_id=contract_id,
                    side=order_side,
                    size=quantity,
                    stop_price=stop_price
                )
            
            # Run async order placement - check for existing event loop
            try:
                loop = asyncio.get_running_loop()
                import concurrent.futures
                with concurrent.futures.ThreadPoolExecutor() as pool:
                    order_response = pool.submit(
                        lambda: asyncio.run(place_order_async())
                    ).result()
            except RuntimeError as e:
                # Handle "Event loop is closed" error gracefully
                if "Event loop is closed" in str(e):
                    logger.warning("Event loop closed during stop order - creating new loop")
                    loop = asyncio.new_event_loop()
                    asyncio.set_event_loop(loop)
                    try:
                        order_response = loop.run_until_complete(place_order_async())
                    finally:
                        self._cleanup_event_loop(loop)
                else:
                    order_response = asyncio.run(place_order_async())
            
            # Check for success - SDK may return different response formats
            # Try order_response.order first, then order_response.success + orderId
            if order_response:
                if hasattr(order_response, 'order') and order_response.order:
                    order = order_response.order
                    result = {
                        "order_id": order.order_id,
                        "symbol": symbol,
                        "side": side,
                        "quantity": quantity,
                        "type": "STOP",
                        "stop_price": stop_price,
                        "status": getattr(order.status, 'value', 'SUBMITTED')
                    }
                    self._record_success()  # Successful order
                    return result
                elif hasattr(order_response, 'success') and order_response.success:
                    # Alternative response format (like market/limit orders)
                    result = {
                        "order_id": getattr(order_response, 'orderId', 'unknown'),
                        "symbol": symbol,
                        "side": side,
                        "quantity": quantity,
                        "type": "STOP",
                        "stop_price": stop_price,
                        "status": "SUBMITTED"
                    }
                    self._record_success()  # Successful order
                    return result
            
            # Order failed
            error_msg = getattr(order_response, 'errorMessage', None) if order_response else None
            logger.error(f"Stop order placement failed: {error_msg or 'Unknown error'}")
            self._record_failure()
            return None
        
        except AttributeError as e:
            error_str = str(e)
            # Handle 'NoneType' object has no attribute 'send' - HTTP/2 connection drop
            if "'NoneType' object has no attribute 'send'" in error_str:
                logger.warning("[STOP ORDER] HTTP/2 connection dropped - attempting reconnect and retry")
                
                # Force disconnect and reconnect
                self.disconnect()
                
                # Wait longer for connections to fully close and event loops to clean up
                time.sleep(3)
                
                if self.connect():
                    logger.info("[STOP ORDER] Reconnected successfully - retrying stop order")
                    try:
                        contract_id = self._get_contract_id_sync(symbol)
                        if contract_id:
                            from project_x_py import OrderSide
                            order_side = OrderSide.BUY if side.upper() == "BUY" else OrderSide.SELL
                            
                            async def retry_stop_async():
                                await self._ensure_token_fresh()
                                # CRITICAL: Ensure trading_suite is bound to current event loop
                                if not await self._ensure_trading_suite_ready():
                                    raise Exception("Trading suite not ready for order placement")
                                return await self.trading_suite.orders.place_stop_order(
                                    contract_id=contract_id,
                                    side=order_side,
                                    size=quantity,
                                    stop_price=stop_price
                                )
                            
                            order_response = asyncio.run(retry_stop_async())
                            
                            if order_response:
                                if hasattr(order_response, 'order') and order_response.order:
                                    order = order_response.order
                                    result = {
                                        "order_id": order.order_id,
                                        "symbol": symbol,
                                        "side": side,
                                        "quantity": quantity,
                                        "type": "STOP",
                                        "stop_price": stop_price,
                                        "status": getattr(order.status, 'value', 'SUBMITTED')
                                    }
                                    logger.info("[STOP ORDER] ✅ Retry successful - stop order placed")
                                    self._record_success()
                                    return result
                                elif hasattr(order_response, 'success') and order_response.success:
                                    result = {
                                        "order_id": getattr(order_response, 'orderId', 'unknown'),
                                        "symbol": symbol,
                                        "side": side,
                                        "quantity": quantity,
                                        "type": "STOP",
                                        "stop_price": stop_price,
                                        "status": "SUBMITTED"
                                    }
                                    logger.info("[STOP ORDER] ✅ Retry successful - stop order placed")
                                    self._record_success()
                                    return result
                    except Exception as retry_err:
                        logger.error(f"[STOP ORDER] Retry also failed: {retry_err}")
                else:
                    logger.error("[STOP ORDER] Reconnect failed - cannot retry stop order")
            
            logger.error(f"Error placing stop order: {e}")
            self._record_failure()
            return None
        except Exception as e:
            # Handle event loop closed errors gracefully
            if "Event loop is closed" in str(e):
                logger.warning("Event loop closed during stop order - order may still be pending")
                return None  # Don't record failure for shutdown issues
            logger.error(f"Error placing stop order: {e}")
            self._record_failure()
            return None
    
    def subscribe_market_data(self, symbol: str, callback: Callable[[str, float, int, int], None]) -> None:
        """Subscribe to real-time market data (trades) via WebSocket."""
        if not self.connected:
            logger.error("Cannot subscribe: not connected")
            return
        
        if not self.websocket_streamer:
            logger.error("WebSocket streamer not initialized - cannot subscribe to live data")
            logger.error("Make sure WebSocket module is available and session token is valid")
            return
        
        try:
            # Get contract ID for the symbol (synchronous)
            contract_id = self._get_contract_id_sync(symbol)
            if not contract_id:
                logger.error(f"Failed to get contract ID for {symbol}")
                return
            
            # Define callback wrapper to convert WebSocket data format
            def trade_callback(data):
                """Handle trade data from WebSocket: [contract_id, [{trade1}, {trade2}, ...]]"""
                if isinstance(data, list) and len(data) >= 2:
                    trades = data[1]  # List of trade dicts
                    if isinstance(trades, list):
                        for trade in trades:
                            price = float(trade.get('price', 0))
                            volume = int(trade.get('volume', 0))
                            
                            # Parse timestamp (ISO format string to milliseconds)
                            timestamp_str = trade.get('timestamp', '')
                            try:
                                from datetime import datetime
                                if timestamp_str:
                                    dt = datetime.fromisoformat(str(timestamp_str).replace('Z', '+00:00'))
                                    timestamp = int(dt.timestamp() * 1000)
                                else:
                                    timestamp = int(datetime.now().timestamp() * 1000)
                            except (ValueError, TypeError, AttributeError) as e:
                                timestamp = int(datetime.now().timestamp() * 1000)
                            
                            # Call bot's callback with tick data
                            callback(symbol, price, volume, timestamp)
            
            # Subscribe to trades via WebSocket
            self.websocket_streamer.subscribe_trades(contract_id, trade_callback)
            
        except Exception as e:
            logger.error(f"Error subscribing to market data: {e}")
            self._record_failure()
    
    def subscribe_quotes(self, symbol: str, callback: Callable[[str, float, float, int, int, float, int], None]) -> None:
        """Subscribe to real-time bid/ask quotes via WebSocket."""
        if not self.connected:
            logger.error("Cannot subscribe to quotes: not connected")
            return
        
        if not self.websocket_streamer:
            logger.warning("WebSocket streamer not initialized - quote subscription unavailable")
            return
        
        try:
            # Get contract ID for the symbol (synchronous)
            contract_id = self._get_contract_id_sync(symbol)
            if not contract_id:
                logger.error(f"Failed to get contract ID for {symbol}")
                return
            
            # Sticky state - keep last valid bid/ask
            last_valid_bid = [0.0]  # Use list to maintain closure reference
            last_valid_ask = [0.0]
            last_valid_timestamp = [0]
            
            # Define callback wrapper to convert WebSocket data format
            def quote_callback(data):
                """Handle quote data from WebSocket: [contract_id, {quote_dict}]"""
                if isinstance(data, list) and len(data) >= 2:
                    quote = data[1]  # Quote dict
                    if isinstance(quote, dict):
                        # STICKY STATE PATTERN: Update only if new values are valid
                        # This prevents false signals from partial/incomplete WebSocket updates
                        
                        # Update bid if present and valid
                        if 'bestBid' in quote:
                            new_bid = float(quote.get('bestBid', 0))
                            if new_bid > 0:
                                last_valid_bid[0] = new_bid
                        
                        # Update ask if present and valid
                        if 'bestAsk' in quote:
                            new_ask = float(quote.get('bestAsk', 0))
                            if new_ask > 0:
                                last_valid_ask[0] = new_ask
                        
                        # Only process if we have BOTH valid bid and ask
                        if last_valid_bid[0] <= 0 or last_valid_ask[0] <= 0:
                            return
                        
                        # Sanity check: ask must be >= bid
                        if last_valid_ask[0] < last_valid_bid[0]:
                            logger.warning(f"Inverted market: bid={last_valid_bid[0]} > ask={last_valid_ask[0]} - skipping")
                            return
                        
                        bid_price = last_valid_bid[0]
                        ask_price = last_valid_ask[0]
                        last_price = float(quote.get('lastPrice', bid_price))  # Default to bid if missing
                        bid_size = 1  # TopStep doesn't provide sizes in quote data
                        ask_size = 1
                        
                        # Parse timestamp (ISO format string to milliseconds)
                        timestamp_str = quote.get('timestamp', '')
                        try:
                            from datetime import datetime
                            if timestamp_str:
                                dt = datetime.fromisoformat(timestamp_str.replace('Z', '+00:00'))
                                timestamp = int(dt.timestamp() * 1000)
                            else:
                                timestamp = int(datetime.now().timestamp() * 1000)
                            
                            # Staleness detection: warn if quote is more than 2 seconds old
                            current_time = int(time.time() * 1000)
                            age_seconds = (current_time - last_valid_timestamp[0]) / 1000.0
                            if last_valid_timestamp[0] > 0 and age_seconds > 2.0:
                                logger.warning(f"Quote feed stale - {age_seconds:.1f}s since last update")
                            last_valid_timestamp[0] = current_time
                            
                        except (ValueError, TypeError, AttributeError) as e:
                            timestamp = int(datetime.now().timestamp() * 1000)
                        
                        # Call bot's callback with quote data
                        callback(symbol, bid_price, ask_price, bid_size, ask_size, last_price, timestamp)
            
            # Subscribe to quotes via WebSocket
            self.websocket_streamer.subscribe_quotes(contract_id, quote_callback)
            
        except Exception as e:
            logger.error(f"Error subscribing to quotes: {e}")
            self._record_failure()
    
    def get_contract_id(self, symbol: str) -> Optional[str]:
        """
        Public method to get contract ID for a symbol.
        Useful for external tools like data recorders.
        
        Args:
            symbol: Trading symbol (e.g., 'ES', 'NQ')
        
        Returns:
            Contract ID string or None if not found
        """
        return self._get_contract_id_sync(symbol)
    
    def _get_contract_id_sync(self, symbol: str) -> Optional[str]:
        """
        Get TopStep contract ID for a symbol (e.g., ES -> CON.F.US.EP.Z25).
        Uses cache to avoid repeated API calls. Falls back to synchronous lookup if not cached.
        """
        # Check cache first (populated during connection)
        if symbol in self._contract_id_cache:
            return self._contract_id_cache[symbol]
        
        # Remove leading slash if present (e.g., /ES -> ES)
        clean_symbol = symbol.lstrip('/')
        
        # Not in cache - need to look it up
        # This shouldn't happen often if connection caching works properly
        logger.warning(f"Contract ID for {symbol} not in cache - performing lookup")
        
        # Build list of search terms to try
        # Some symbols (especially micros) need alternative search strings
        search_terms = [clean_symbol]
        
        # Add alternative search terms for micro contracts
        MICRO_ALTERNATIVES = {
            'MES': ['Micro E-mini S&P', 'Micro S&P', 'MES', 'MESEP'],
            'MNQ': ['Micro E-mini Nasdaq', 'Micro Nasdaq', 'MNQ', 'MNQEP'],
            'M2K': ['Micro E-mini Russell', 'Micro Russell', 'M2K'],
            'MYM': ['Micro E-mini Dow', 'Micro Dow', 'MYM'],
        }
        
        if clean_symbol.upper() in MICRO_ALTERNATIVES:
            search_terms.extend(MICRO_ALTERNATIVES[clean_symbol.upper()])
        
        try:
            instruments = None
            
            for search_term in search_terms:
                # Use the SDK's synchronous method if available, otherwise async
                if hasattr(self.sdk_client, 'search_instruments_sync'):
                    instruments = self.sdk_client.search_instruments_sync(query=search_term)
                else:
                    # Run async method in a new thread with its own event loop
                    import asyncio
                    from concurrent.futures import ThreadPoolExecutor
                    
                    def run_async_search(query):
                        loop = asyncio.new_event_loop()
                        asyncio.set_event_loop(loop)
                        try:
                            # CRITICAL FIX: Handle potential crash in project_x_py client reuse
                            try:
                                return loop.run_until_complete(
                                    self.sdk_client.search_instruments(query=query)
                                )
                            except Exception as e:
                                # Catch "NoneType object has no attribute send" crash (including wrapped errors)
                                # Check for the specific error string robustly (ProjectXError wraps the AttributeError)
                                error_str = str(e)
                                if "NoneType" in error_str and "send" in error_str:
                                    # Silently skip - this is a known Windows proactor issue
                                    logger.debug(f"Async client crash resolving {query} - skipping (Error: {error_str})")
                                    return None
                                logger.error(f"Async search failed for {query}: {e}")
                                raise e
                        finally:
                            # Gentler cleanup to avoid Windows proactor errors
                            pass

                    with ThreadPoolExecutor(max_workers=1) as executor:
                        future = executor.submit(run_async_search, search_term)
                        instruments = future.result(timeout=10)
                
                if instruments and len(instruments) > 0:
                    # Find exact match or closest match
                    for instr in instruments:
                        # Use helper method to get instrument symbol
                        instr_symbol = self._get_instrument_symbol(instr)
                        # Check for exact match or partial match
                        if instr_symbol and (instr_symbol.upper() == clean_symbol.upper() or 
                                            clean_symbol.upper() in instr_symbol.upper() or
                                            instr_symbol.upper().startswith(clean_symbol.upper())):
                            contract_id = self._get_instrument_contract_id(instr)
                            if contract_id:
                                self._contract_id_cache[symbol] = contract_id
                                logger.info(f"Found contract ID for {symbol} -> {contract_id} (search term: {search_term})")
                                return contract_id
                    
                    # No exact match - for first search term, use first result
                    if search_term == clean_symbol:
                        contract_id = self._get_instrument_contract_id(instruments[0])
                        if contract_id:
                            self._contract_id_cache[symbol] = contract_id
                            logger.info(f"Using first result for {symbol} -> {contract_id}")
                            return contract_id
            
            logger.error(f"No contracts found for symbol: {symbol}")
            return None
            
        except Exception as e:
            logger.error(f"Error getting contract ID for {symbol}: {e}")
            import traceback
            traceback.print_exc()
            return None
    
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
        # Auto-reset circuit breaker after cooldown period
        self._check_circuit_breaker_cooldown()
        return self.connected and not self.circuit_breaker_open
    
    def _check_circuit_breaker_cooldown(self) -> None:
        """Check if circuit breaker should auto-reset after cooldown."""
        if self.circuit_breaker_open and self.circuit_breaker_reset_time:
            current_time = time.time()
            if current_time >= self.circuit_breaker_reset_time:
                logger.info("Circuit breaker auto-reset after cooldown period")
                self.reset_circuit_breaker()
    
    def _record_failure(self) -> None:
        """Record a failure and potentially open circuit breaker."""
        self.failure_count += 1
        if self.failure_count >= self.circuit_breaker_threshold:
            if not self.circuit_breaker_open:
                self.circuit_breaker_open = True
                self.circuit_breaker_reset_time = time.time() + self.circuit_breaker_cooldown_seconds
                logger.critical(f"Circuit breaker opened after {self.failure_count} failures - will auto-reset in {self.circuit_breaker_cooldown_seconds}s")
    
    def _record_success(self) -> None:
        """Record a successful operation - reduce failure count."""
        if self.failure_count > 0:
            self.failure_count = max(0, self.failure_count - 1)
        # If circuit breaker was open but we had a success, reset it
        if self.circuit_breaker_open:
            logger.info("Circuit breaker reset due to successful operation")
            self.reset_circuit_breaker()
    
    def reset_circuit_breaker(self) -> None:
        """Reset circuit breaker (manual or automatic recovery)."""
        self.circuit_breaker_open = False
        self.failure_count = 0
        self.circuit_breaker_reset_time = None


def create_broker(api_token: str, username: str = None, instrument: str = None) -> BrokerInterface:
    """
    Factory function to create a broker instance.
    
    Args:
        api_token: Broker API token (required)
        username: Broker username/email (required for SDK v3.5+)
        instrument: Trading instrument symbol (must be configured by user)
    
    Returns:
        BrokerInterface implementation
    
    Raises:
        ValueError: If API token is missing
    """
    if not api_token:
        raise ValueError("API token is required for broker connection")
    return BrokerSDKImplementation(api_token=api_token, username=username, instrument=instrument)


# Backward compatibility alias for existing code
TopStepBroker = BrokerSDKImplementation


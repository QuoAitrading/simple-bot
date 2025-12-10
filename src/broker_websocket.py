"""
Broker WebSocket Streamer using SignalR
Generic WebSocket implementation for broker market data streaming
Supports any broker using SignalR protocol
"""

import logging
import time
from typing import Optional, Callable, Dict
from signalrcore.hub_connection_builder import HubConnectionBuilder

logger = logging.getLogger(__name__)


class BrokerWebSocketStreamer:
    """Real-time WebSocket streamer for broker market data via SignalR"""
    
    def __init__(self, session_token: str, hub_url: str = None, max_reconnect_attempts: int = 5):
        """
        Initialize WebSocket streamer
        
        Args:
            session_token: Broker session token for authentication
            hub_url: WebSocket hub URL (broker-specific endpoint)
            max_reconnect_attempts: Maximum reconnection attempts (default: 5)
        """
        self.session_token = session_token
        self.hub_url = hub_url or "wss://rtc.topstepx.com/hubs/market"  # Default for backward compatibility
        self.connection = None
        self.is_connected = False
        
        # Callbacks - per-symbol dicts to support multi-symbol subscriptions
        self.quote_callbacks: Dict[str, Callable] = {}  # contract_id -> callback
        self.trade_callbacks: Dict[str, Callable] = {}  # contract_id -> callback
        self.depth_callbacks: Dict[str, Callable] = {}  # contract_id -> callback
        # Legacy single callbacks for backward compatibility
        self.on_quote_callback: Optional[Callable] = None
        self.on_trade_callback: Optional[Callable] = None
        self.on_depth_callback: Optional[Callable] = None
        
        # Stats
        self.quotes_received = 0
        self.trades_received = 0
        self.depth_updates_received = 0
        self.last_message_time = None
        
        # Reconnection tracking
        self.max_reconnect_attempts = max_reconnect_attempts
        self.reconnect_attempt = 0
        self.subscriptions = []  # Track active subscriptions for resubscription
        
        # Configuration constants
        self._HUB_INIT_DELAY = 1.0  # Seconds to wait for hub initialization
        self._RETRY_BASE_DELAY = 0.5  # Base delay for exponential backoff
        self._MAX_RESUBSCRIBE_RETRIES = 3  # Maximum resubscription attempts
        self._INITIAL_CONNECTION_DELAY = 2.0  # Seconds to wait after connection start
        self._RECONNECT_BASE_DELAY = 2  # Base delay for reconnection backoff
        self._RECONNECT_MAX_DELAY = 30  # Maximum delay for reconnection backoff
    
    def _cleanup_connection(self):
        """Clean up existing connection before creating a new one"""
        if self.connection is not None:
            try:
                self.connection.stop()
            except Exception:
                pass  # Ignore errors stopping old/stale connection
            self.connection = None
    
    def _is_connection_ready(self) -> bool:
        """Check if connection is ready for sending messages"""
        return self.is_connected and self.connection is not None
    
    def _wait_for_hub_initialization(self):
        """
        Wait for SignalR hub to fully initialize before sending subscriptions.
        This delay is critical to prevent "Hub is not running" errors after reconnection.
        The sleep is in SignalR's dedicated callback thread, not the main event loop.
        """
        time.sleep(self._HUB_INIT_DELAY)
    
    def _get_retry_delay(self, attempt: int) -> float:
        """
        Calculate exponential backoff delay for resubscription retry attempts.
        Returns: 0.5s, 1s, 2s for attempts 0, 1, 2
        """
        return self._RETRY_BASE_DELAY * (2 ** attempt)
    
    def _get_reconnect_delay(self, attempt: int) -> float:
        """
        Calculate exponential backoff delay for reconnection attempts.
        Returns: 2s, 4s, 8s, 16s, 30s (capped) for attempts 1, 2, 3, 4, 5
        """
        return min(self._RECONNECT_BASE_DELAY * (2 ** (attempt - 1)), self._RECONNECT_MAX_DELAY)
    
    def connect(self) -> bool:
        """Connect to broker SignalR market hub"""
        try:
            # Clean up old connection if it exists
            self._cleanup_connection()
            
            auth_url = f"{self.hub_url}?access_token={self.session_token}"
            
            self.connection = (
                HubConnectionBuilder()
                .with_url(auth_url)
                .configure_logging(logging.INFO)
                .with_automatic_reconnect({"type": "interval", "intervals": [0, 2, 5, 10, 30]})
                .build()
            )
            
            self._register_handlers()
            self.connection.start()
            
            # Wait longer for connection to fully establish
            # This allows the SignalR hub to fully initialize before we try to subscribe
            time.sleep(self._INITIAL_CONNECTION_DELAY)
            
            self.is_connected = True
            return True
            
        except Exception as e:
            logger.error(f"[ERROR] Failed to connect to WebSocket: {e}", exc_info=True)
            self.is_connected = False
            return False
    
    def _register_handlers(self):
        """Register SignalR event handlers"""
        self.connection.on_open(self._on_open)
        self.connection.on_close(self._on_close)
        self.connection.on_error(self._on_error)
        self.connection.on_reconnect(self._on_reconnect)
        self.connection.on("GatewayQuote", self._on_quote)
        self.connection.on("GatewayTrade", self._on_trade)
        self.connection.on("GatewayDepth", self._on_depth)
    
    def _on_open(self):
        """Called when WebSocket connection opens"""
        self.is_connected = True
        self.reconnect_attempt = 0  # Reset reconnect counter on successful connection
        
        # Wait for hub to initialize before resubscribing
        self._wait_for_hub_initialization()
        
        # Resubscribe to previous subscriptions after reconnection
        self._resubscribe_to_all()
    
    def _on_reconnect(self):
        """Called when WebSocket connection reconnects automatically"""
        logger.info("[WebSocket] Automatic reconnection successful")
        self.is_connected = True
        self.reconnect_attempt = 0
        
        # Wait for hub to initialize before resubscribing
        self._wait_for_hub_initialization()
        
        # Resubscribe to previous subscriptions after automatic reconnection
        self._resubscribe_to_all()
    
    def _resubscribe_to_all(self):
        """Resubscribe to all previous subscriptions after reconnection"""
        if not self.subscriptions:
            return
        
        # Early check: verify connection is ready before attempting any subscriptions
        if not self._is_connection_ready():
            logger.warning("[WebSocket] Connection not ready, skipping resubscription")
            return
        
        logger.info(f"[WebSocket] Resubscribing to {len(self.subscriptions)} subscription(s)...")
        
        # Iterate over a copy to avoid issues if subscriptions are modified during iteration
        for sub_type, symbol in self.subscriptions.copy():
            # Retry logic for resubscription with exponential backoff
            for attempt in range(self._MAX_RESUBSCRIBE_RETRIES):
                try:
                    # Verify connection is still ready before each attempt
                    if not self._is_connection_ready():
                        retry_delay = self._get_retry_delay(attempt)
                        logger.warning(f"Connection not ready for resubscription (attempt {attempt + 1}/{self._MAX_RESUBSCRIBE_RETRIES})")
                        time.sleep(retry_delay)
                        continue
                    
                    if sub_type == "quotes":
                        self.connection.send("SubscribeContractQuotes", [symbol])
                    elif sub_type == "trades":
                        self.connection.send("SubscribeContractTrades", [symbol])
                    elif sub_type == "depth":
                        self.connection.send("SubscribeContractMarketDepth", [symbol])
                    
                    logger.info(f"[WebSocket] Successfully resubscribed to {sub_type} for {symbol}")
                    break  # Success, exit retry loop
                    
                except Exception as e:
                    if attempt < self._MAX_RESUBSCRIBE_RETRIES - 1:
                        retry_delay = self._get_retry_delay(attempt)
                        logger.warning(f"Resubscription attempt {attempt + 1}/{self._MAX_RESUBSCRIBE_RETRIES} failed for {sub_type} {symbol}: {e}")
                        time.sleep(retry_delay)
                    else:
                        logger.error(f"Failed to resubscribe to {sub_type} for {symbol} after {self._MAX_RESUBSCRIBE_RETRIES} attempts: {e}")
    
    def _on_close(self):
        """Called when WebSocket connection closes"""
        was_connected = self.is_connected
        self.is_connected = False
        
        # If we're intentionally disconnecting (e.g., maintenance), don't try to reconnect
        if self.reconnect_attempt >= self.max_reconnect_attempts:
            # Intentional disconnect or max attempts reached
            return
        
        # Unexpected disconnect - attempt reconnect
        if was_connected and self.reconnect_attempt < self.max_reconnect_attempts:
            self.reconnect_attempt += 1
            wait_time = self._get_reconnect_delay(self.reconnect_attempt)
            logger.info(f"[WebSocket] Connection closed unexpectedly - reconnecting in {wait_time}s (attempt {self.reconnect_attempt}/{self.max_reconnect_attempts})...")
            time.sleep(wait_time)
            
            try:
                # Force cleanup of old connection before reconnecting
                # This is critical after laptop sleep/resume where the old connection is stale
                self._cleanup_connection()
                
                # Attempt to reconnect
                success = self.connect()
                if success:
                    logger.info("[WebSocket] Reconnected successfully")
                else:
                    logger.warning(f"Reconnection attempt {self.reconnect_attempt} returned False")
            except Exception as e:
                logger.error(f"Manual reconnection attempt {self.reconnect_attempt} failed: {e}")
                if self.reconnect_attempt >= self.max_reconnect_attempts:
                    logger.error(f"[WARN] All {self.max_reconnect_attempts} reconnection attempts failed")
                    logger.error("WebSocket will remain disconnected. Bot will continue with REST API polling.")
    
    def _on_error(self, error):
        """Called when WebSocket error occurs"""
        # If we're intentionally disconnected, don't log errors
        if not self.is_connected and self.reconnect_attempt >= self.max_reconnect_attempts:
            return  # Ignore errors during intentional disconnect
        
        # Extract actual error message from CompletionMessage if present
        error_msg = error
        if hasattr(error, 'error'):
            error_msg = error.error
        elif hasattr(error, 'message'):
            error_msg = error.message
        elif hasattr(error, '__dict__'):
            error_msg = str(error.__dict__)
        
        # Check if this is a connection closed error (expected during maintenance)
        error_str = str(error_msg)
        if any(x in error_str for x in ['Connection closed', 'recv_strict', 'recv_header', 'recv_frame', 'WebSocket connection is closed']):
            # This is expected during broker maintenance - log at info level, not error
            logger.info("[WebSocket] Connection closed by server (expected during maintenance)")
        else:
            logger.error(f"[ERROR] WebSocket error: {error_msg}")
    
    def _on_quote(self, data):
        """Handle incoming quote data"""
        self.quotes_received += 1
        self.last_message_time = time.time()
        if self.on_quote_callback:
            try:
                self.on_quote_callback(data)
            except Exception as e:
                logger.error(f"Error in quote callback: {e}")
    
    def _on_trade(self, data):
        """Handle incoming trade data - routes to per-symbol callback"""
        self.trades_received += 1
        self.last_message_time = time.time()
        
        # Extract contract ID from data to route to correct callback
        contract_id = None
        if isinstance(data, list) and len(data) >= 1:
            contract_id = data[0] if isinstance(data[0], str) else None
        
        # Try per-symbol callback first
        if contract_id and contract_id in self.trade_callbacks:
            try:
                self.trade_callbacks[contract_id](data)
            except Exception as e:
                logger.error(f"Error in trade callback for {contract_id}: {e}")
        elif self.on_trade_callback:
            # Fallback to legacy single callback
            try:
                self.on_trade_callback(data)
            except Exception as e:
                logger.error(f"Error in trade callback: {e}")
    
    def _on_depth(self, data):
        """Handle incoming market depth data"""
        self.depth_updates_received += 1
        self.last_message_time = time.time()
        if self.on_depth_callback:
            try:
                self.on_depth_callback(data)
            except Exception as e:
                logger.error(f"Error in depth callback: {e}")
    
    def subscribe_quotes(self, symbol: str, callback: Callable):
        """Subscribe to real-time quotes using contract ID"""
        self.on_quote_callback = callback
        
        try:
            # Verify connection is ready before subscribing
            if not self._is_connection_ready():
                logger.error(f"Cannot subscribe to quotes for {symbol} - connection not ready")
                return
            
            # Some brokers use contract IDs, others use symbols
            # The calling code should pass the appropriate identifier
            self.connection.send("SubscribeContractQuotes", [symbol])
            
            # Track subscription for reconnection
            sub = ("quotes", symbol)
            if sub not in self.subscriptions:
                self.subscriptions.append(sub)
            
            logger.info(f"[WebSocket] Subscribed to quotes for {symbol}")
        except Exception as e:
            logger.error(f"Failed to subscribe to quotes: {e}", exc_info=True)
    
    def subscribe_trades(self, symbol: str, callback: Callable):
        """Subscribe to real-time trades using contract ID"""
        # Store callback per-symbol to support multiple subscriptions
        self.trade_callbacks[symbol] = callback
        # Also set legacy callback for backward compatibility (last one wins)
        self.on_trade_callback = callback
        
        try:
            # Verify connection is ready before subscribing
            if not self._is_connection_ready():
                logger.error(f"Cannot subscribe to trades for {symbol} - connection not ready")
                return
            
            # Some brokers use contract IDs, others use symbols
            # The calling code should pass the appropriate identifier
            self.connection.send("SubscribeContractTrades", [symbol])
            
            # Track subscription for reconnection
            sub = ("trades", symbol)
            if sub not in self.subscriptions:
                self.subscriptions.append(sub)
            
            logger.info(f"[WebSocket] Subscribed to trades for {symbol}")
        except Exception as e:
            logger.error(f"Failed to subscribe to trades: {e}", exc_info=True)
    
    def subscribe_depth(self, symbol: str, callback: Callable):
        """Subscribe to Level 2 market depth/DOM"""
        self.on_depth_callback = callback
        try:
            # Verify connection is ready before subscribing
            if not self._is_connection_ready():
                logger.error(f"Cannot subscribe to depth for {symbol} - connection not ready")
                return
            
            # Correct TopStep method: SubscribeContractMarketDepth
            # Event received: GatewayDepth
            self.connection.send("SubscribeContractMarketDepth", [symbol])
            
            # Track subscription for reconnection
            sub = ("depth", symbol)
            if sub not in self.subscriptions:
                self.subscriptions.append(sub)
            
            logger.info(f"[WebSocket] Subscribed to depth for {symbol}")
        except Exception as e:
            logger.error(f"Failed to subscribe to depth: {e}", exc_info=True)
    
    def disconnect(self):
        """Disconnect from WebSocket gracefully"""
        try:
            self.is_connected = False  # Mark as disconnected first to prevent error logs
            self.reconnect_attempt = self.max_reconnect_attempts  # Prevent auto-reconnect
            
            if self.connection:
                try:
                    self.connection.stop()
                except Exception:
                    pass  # Ignore errors during disconnect - connection may already be closed
                self.connection = None
            
            logger.info("[WebSocket] Disconnected gracefully")
        except Exception as e:
            # Ignore all errors during disconnect - we're intentionally closing
            pass
    
    def get_stats(self) -> Dict:
        """Get streaming statistics"""
        return {
            'connected': self.is_connected,
            'quotes_received': self.quotes_received,
            'trades_received': self.trades_received,
            'depth_updates_received': self.depth_updates_received,
            'last_message_time': self.last_message_time
        }


# Backward compatibility alias
TopStepWebSocketStreamer = BrokerWebSocketStreamer

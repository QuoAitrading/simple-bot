"""
Zone WebSocket Client - Real-time zone delivery from TradingView via Azure.

This module connects to the QuoTrading cloud API via WebSocket and receives
supply/demand zones in real-time as they're detected by TradingView indicators.

Flow:
1. TradingView indicator detects zone → sends webhook to Azure
2. Azure stores zone and broadcasts via WebSocket
3. This client receives zone instantly (< 1 second)
4. Zone is passed to ZoneManager for trading decisions
"""

import logging
import threading
import time
import json
from typing import Optional, Callable, List, Dict, Any
from dataclasses import dataclass, field
from datetime import datetime

try:
    import socketio
    SOCKETIO_AVAILABLE = True
except ImportError:
    SOCKETIO_AVAILABLE = False
    socketio = None

logger = logging.getLogger(__name__)


# Symbol groups - micro contracts share zones with full-size equivalents
SYMBOL_GROUPS = {
    "MES": "ES",
    "MNQ": "NQ", 
    "MYM": "YM",
    "MCL": "CL",
    "M2K": "RTY",
    "ES": "ES",
    "NQ": "NQ",
    "YM": "YM",
    "CL": "CL",
    "RTY": "RTY",
}


def get_base_symbol(symbol: str) -> str:
    """Get base symbol for zone lookup. MES -> ES, MNQ -> NQ, etc."""
    return SYMBOL_GROUPS.get(symbol.upper(), symbol.upper())


@dataclass
class Zone:
    """Represents a supply/demand zone received from the server."""
    id: int
    zone_type: str  # 'supply' or 'demand'
    top: float
    bottom: float
    strength: str  # 'STRONG', 'MEDIUM', 'WEAK'
    status: str  # 'FRESH', 'TESTED', 'MITIGATED'
    retests: int
    created_at: str
    expires_at: Optional[str] = None
    symbol: Optional[str] = None
    
    @classmethod
    def from_dict(cls, data: dict) -> 'Zone':
        return cls(
            id=data.get('id', 0),
            zone_type=data.get('type', data.get('zone_type', 'supply')),
            top=float(data.get('top', 0)),
            bottom=float(data.get('bottom', 0)),
            strength=data.get('strength', 'MEDIUM'),
            status=data.get('status', 'FRESH'),
            retests=data.get('retests', 0),
            created_at=data.get('created_at', ''),
            expires_at=data.get('expires_at'),
            symbol=data.get('symbol')
        )
    
    @property
    def mid_price(self) -> float:
        return (self.top + self.bottom) / 2
    
    @property
    def height(self) -> float:
        return abs(self.top - self.bottom)
    
    @property
    def is_supply(self) -> bool:
        return self.zone_type.lower() == 'supply'
    
    @property
    def is_demand(self) -> bool:
        return self.zone_type.lower() == 'demand'
    
    @property
    def is_fresh(self) -> bool:
        return self.status.upper() == 'FRESH'


class ZoneWebSocketClient:
    """
    WebSocket client for real-time zone delivery.
    
    Connects to Azure Flask API and receives zones as they're detected
    by TradingView indicators.
    """
    
    def __init__(
        self,
        server_url: str = "https://quotrading-flask-api.azurewebsites.net",
        symbols: Optional[List[str]] = None,
        on_zone_received: Optional[Callable[[Zone], None]] = None,
        auto_reconnect: bool = True,
        reconnect_delay: float = 5.0
    ):
        """
        Initialize the WebSocket client.
        
        Args:
            server_url: URL of the Azure Flask API
            symbols: List of symbols to subscribe to (e.g., ['ES', 'NQ'])
            on_zone_received: Callback when a new zone is received
            auto_reconnect: Whether to auto-reconnect on disconnect
            reconnect_delay: Seconds to wait before reconnecting
        """
        if not SOCKETIO_AVAILABLE:
            logger.warning("python-socketio not installed. WebSocket zones disabled.")
            self.enabled = False
            return
        
        self.enabled = True
        self.server_url = server_url
        self.symbols = symbols or ['ES']
        self.on_zone_received = on_zone_received
        self.auto_reconnect = auto_reconnect
        self.reconnect_delay = reconnect_delay
        
        # Connection state
        self.connected = False
        self.subscribed_rooms: List[str] = []
        self.zones: Dict[str, List[Zone]] = {}  # symbol -> list of zones
        
        # Threading
        self._client: Optional[socketio.Client] = None
        self._thread: Optional[threading.Thread] = None
        self._stop_event = threading.Event()
        
        # Stats
        self.zones_received = 0
        self.last_zone_time: Optional[datetime] = None
        self.connection_attempts = 0
    
    def start(self) -> bool:
        """Start the WebSocket client in a background thread."""
        if not self.enabled:
            logger.warning("WebSocket client disabled (socketio not available)")
            return False
        
        if self._thread and self._thread.is_alive():
            logger.warning("WebSocket client already running")
            return True
        
        self._stop_event.clear()
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()
        logger.info(f"🔌 Zone WebSocket client started for symbols: {self.symbols}")
        return True
    
    def stop(self):
        """Stop the WebSocket client."""
        if not self.enabled:
            return
        
        self._stop_event.set()
        
        if self._client and self._client.connected:
            try:
                self._client.disconnect()
            except Exception as e:
                logger.debug(f"Error disconnecting: {e}")
        
        if self._thread:
            self._thread.join(timeout=5)
        
        self.connected = False
        logger.info("🔌 Zone WebSocket client stopped")
    
    def _run(self):
        """Background thread that maintains the WebSocket connection."""
        while not self._stop_event.is_set():
            try:
                self._connect()
                
                # Wait for disconnect or stop
                while self.connected and not self._stop_event.is_set():
                    time.sleep(0.5)
                
            except Exception as e:
                logger.error(f"WebSocket error: {e}")
            
            # Reconnect logic
            if not self._stop_event.is_set() and self.auto_reconnect:
                logger.info(f"Reconnecting in {self.reconnect_delay}s...")
                time.sleep(self.reconnect_delay)
    
    def _connect(self):
        """Establish WebSocket connection and set up handlers."""
        self.connection_attempts += 1
        
        # Create new client instance
        self._client = socketio.Client(
            reconnection=False,  # We handle reconnection ourselves
            logger=False,
            engineio_logger=False
        )
        
        # Register event handlers
        @self._client.event
        def connect():
            self.connected = True
            logger.info(f"✅ Connected to zone server: {self.server_url}")
            # Subscribe to symbols
            self._subscribe_to_symbols()
        
        @self._client.event
        def disconnect():
            self.connected = False
            logger.warning("❌ Disconnected from zone server")
        
        @self._client.event
        def connect_error(data):
            logger.error(f"Connection error: {data}")
            self.connected = False
        
        @self._client.on('connected')
        def on_connected(data):
            logger.info(f"Server says: {data.get('message', 'connected')}")
        
        @self._client.on('subscribed')
        def on_subscribed(data):
            rooms = data.get('rooms', [])
            self.subscribed_rooms = rooms
            logger.info(f"📥 Subscribed to zone rooms: {rooms}")
            
            # Load current zones
            current_zones = data.get('current_zones', {})
            for symbol, zones in current_zones.items():
                self.zones[symbol] = [Zone.from_dict(z) for z in zones]
                logger.info(f"  📊 Loaded {len(zones)} existing zones for {symbol}")
        
        @self._client.on('new_zone')
        def on_new_zone(data):
            """Handle new zone received from server."""
            try:
                zone = Zone.from_dict(data)
                self.zones_received += 1
                self.last_zone_time = datetime.now()
                
                # Store zone
                symbol = zone.symbol or 'ES'
                if symbol not in self.zones:
                    self.zones[symbol] = []
                self.zones[symbol].insert(0, zone)  # Most recent first
                
                # Keep only last 20 zones per symbol
                if len(self.zones[symbol]) > 20:
                    self.zones[symbol] = self.zones[symbol][:20]
                
                logger.info(
                    f"🔔 NEW ZONE: {zone.zone_type.upper()} {symbol} "
                    f"[{zone.bottom:.2f}-{zone.top:.2f}] {zone.strength}"
                )
                
                # Call callback if set
                if self.on_zone_received:
                    try:
                        self.on_zone_received(zone)
                    except Exception as e:
                        logger.error(f"Error in zone callback: {e}")
                        
            except Exception as e:
                logger.error(f"Error processing new zone: {e}")
        
        @self._client.on('pong')
        def on_pong(data):
            # Keep-alive response
            pass
        
        # Connect to server
        try:
            logger.info(f"🔌 Connecting to {self.server_url}...")
            self._client.connect(
                self.server_url,
                transports=['websocket', 'polling'],
                wait_timeout=10
            )
            
            # Start ping thread to keep connection alive
            self._start_ping_loop()
            
            # Wait for disconnect
            self._client.wait()
            
        except Exception as e:
            logger.error(f"Failed to connect: {e}")
            self.connected = False
    
    def _subscribe_to_symbols(self):
        """Subscribe to zone updates for configured symbols."""
        if not self._client or not self.connected:
            return
        
        # Convert to base symbols for room subscription
        base_symbols = list(set(get_base_symbol(s) for s in self.symbols))
        
        try:
            self._client.emit('subscribe', {'symbols': base_symbols})
            logger.info(f"📨 Sent subscription request for: {base_symbols}")
        except Exception as e:
            logger.error(f"Error subscribing: {e}")
    
    def _start_ping_loop(self):
        """Start a ping loop to keep the connection alive."""
        def ping_loop():
            while self.connected and not self._stop_event.is_set():
                try:
                    if self._client and self._client.connected:
                        self._client.emit('ping')
                except Exception:
                    pass
                time.sleep(25)  # Ping every 25 seconds
        
        ping_thread = threading.Thread(target=ping_loop, daemon=True)
        ping_thread.start()
    
    def get_zones(self, symbol: str) -> List[Zone]:
        """Get cached zones for a symbol."""
        base_symbol = get_base_symbol(symbol)
        return self.zones.get(base_symbol, [])
    
    def get_fresh_zones(self, symbol: str) -> List[Zone]:
        """Get only fresh (untested) zones for a symbol."""
        return [z for z in self.get_zones(symbol) if z.is_fresh]
    
    def get_supply_zones(self, symbol: str) -> List[Zone]:
        """Get supply zones for a symbol."""
        return [z for z in self.get_zones(symbol) if z.is_supply]
    
    def get_demand_zones(self, symbol: str) -> List[Zone]:
        """Get demand zones for a symbol."""
        return [z for z in self.get_zones(symbol) if z.is_demand]
    
    def add_symbol(self, symbol: str):
        """Add a symbol to subscribe to."""
        if symbol not in self.symbols:
            self.symbols.append(symbol)
            if self.connected:
                self._subscribe_to_symbols()
    
    def remove_symbol(self, symbol: str):
        """Remove a symbol from subscriptions."""
        if symbol in self.symbols:
            self.symbols.remove(symbol)
            base_symbol = get_base_symbol(symbol)
            if self._client and self.connected:
                try:
                    self._client.emit('unsubscribe', {'symbols': [base_symbol]})
                except Exception:
                    pass
    
    @property
    def is_connected(self) -> bool:
        """Check if connected to the zone server."""
        return self.connected and self._client is not None
    
    def get_status(self) -> dict:
        """Get client status for monitoring."""
        return {
            'connected': self.connected,
            'server': self.server_url,
            'symbols': self.symbols,
            'subscribed_rooms': self.subscribed_rooms,
            'zones_received': self.zones_received,
            'last_zone_time': self.last_zone_time.isoformat() if self.last_zone_time else None,
            'connection_attempts': self.connection_attempts,
            'cached_zones': {s: len(z) for s, z in self.zones.items()}
        }


# Global instance for easy access
_zone_client: Optional[ZoneWebSocketClient] = None


def get_zone_client() -> Optional[ZoneWebSocketClient]:
    """Get the global zone client instance."""
    return _zone_client


def init_zone_client(
    symbols: List[str],
    on_zone_received: Optional[Callable[[Zone], None]] = None,
    server_url: str = "https://quotrading-flask-api.azurewebsites.net"
) -> Optional[ZoneWebSocketClient]:
    """
    Initialize and start the global zone client.
    
    Args:
        symbols: List of symbols to subscribe to
        on_zone_received: Callback when new zone arrives
        server_url: Azure API URL
    
    Returns:
        ZoneWebSocketClient instance or None if not available
    """
    global _zone_client
    
    if not SOCKETIO_AVAILABLE:
        logger.warning("WebSocket zones not available (install python-socketio)")
        return None
    
    if _zone_client:
        _zone_client.stop()
    
    _zone_client = ZoneWebSocketClient(
        server_url=server_url,
        symbols=symbols,
        on_zone_received=on_zone_received
    )
    
    _zone_client.start()
    return _zone_client


def shutdown_zone_client():
    """Shutdown the global zone client."""
    global _zone_client
    if _zone_client:
        _zone_client.stop()
        _zone_client = None

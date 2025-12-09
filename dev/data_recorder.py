"""
Market Data Recorder
====================
Records live market data from brokers for backtesting purposes.

Captures:
- Trade ticks (Price, Size, Time)
- Aggregates into 1-minute OHLCV bars

Output:
- 1-minute OHLCV bars (timestamp, open, high, low, close, volume)
- Separate CSV file per symbol ({symbol}_1min.csv)
- Append mode for continuous recording
- Chronologically ordered
"""

import csv
import time
import logging
from datetime import datetime
from typing import List, Dict, Any, Optional, Callable
from pathlib import Path
import threading
import sys

# Add src directory to path
src_path = Path(__file__).parent.parent / "src"
if str(src_path) not in sys.path:
    sys.path.insert(0, str(src_path))

try:
    from broker_interface import TopStepBroker
    from broker_websocket import BrokerWebSocketStreamer
    BROKER_AVAILABLE = True
except ImportError as e:
    BROKER_AVAILABLE = False
    BROKER_IMPORT_ERROR = str(e)

logger = logging.getLogger(__name__)

# Configuration constants
CSV_FLUSH_FREQUENCY = 10  # Flush CSV file every N bars (1 bar = 1 minute)
STATS_REPORT_INTERVAL_SECONDS = 60  # Report statistics every N seconds
BAR_INTERVAL_SECONDS = 60  # 1-minute bars


class MarketDataRecorder:
    """Records live market data to CSV for backtesting as 1-minute OHLCV bars."""
    
    def __init__(
        self,
        broker: str,
        username: str,
        api_token: str,
        symbols: List[str],
        output_dir: str,
        log_callback: Optional[Callable[[str], None]] = None
    ):
        """
        Initialize market data recorder.
        
        Args:
            broker: Broker name (e.g., "TopStep")
            username: Broker username
            api_token: Broker API token
            symbols: List of symbols to record
            output_dir: Output directory for CSV files (one per symbol as {symbol}_1min.csv)
            log_callback: Optional callback for logging messages to GUI
        """
        self.broker_name = broker
        self.username = username
        self.api_token = api_token
        self.symbols = symbols
        self.output_dir = Path(output_dir)
        self.log_callback = log_callback
        
        # Create output directory if it doesn't exist
        self.output_dir.mkdir(parents=True, exist_ok=True)
        
        # Broker connection
        self.broker = None
        self.websocket = None
        
        # Recording state
        self.is_recording = False
        
        # Per-symbol CSV files and writers
        self.csv_files = {}  # symbol -> file handle
        self.csv_writers = {}  # symbol -> csv.writer
        self.csv_locks = {symbol: threading.Lock() for symbol in symbols}
        
        # Current bar aggregation state for each symbol
        self.current_bars = {}  # symbol -> {timestamp, open, high, low, close, volume}
        self.bar_locks = {symbol: threading.Lock() for symbol in symbols}
        
        # Statistics
        self.stats = {symbol: {
            'ticks': 0,
            'bars_written': 0
        } for symbol in symbols}
        
        # Contract ID mapping (symbol -> contract_id)
        self.contract_ids = {}
    
    def _get_current_timestamp(self) -> str:
        """Get current timestamp in ISO format."""
        return datetime.now().isoformat()
    
    def log(self, message: str):
        """Log message to callback and logger."""
        logger.info(message)
        if self.log_callback:
            self.log_callback(message)
    
    def start(self):
        """Start recording market data."""
        # Check if broker modules are available
        if not BROKER_AVAILABLE:
            raise Exception(
                f"Broker SDK not available: {BROKER_IMPORT_ERROR}\n\n"
                "Please install broker dependencies by uncommenting the broker SDK section "
                "in requirements.txt and running:\n"
                "pip install -r requirements.txt\n\n"
                "Required packages:\n"
                "- project-x-py>=3.5.9\n"
                "- signalrcore>=0.9.5\n"
                "- And other broker dependencies listed in requirements.txt"
            )
        
        try:
            self.log("Connecting to broker...")
            
            # Connect to broker
            if self.broker_name == "TopStep":
                self.broker = TopStepBroker(
                    api_token=self.api_token,
                    username=self.username,
                    instrument=self.symbols[0] if self.symbols else "ES"
                )
                
                print("DEBUG: Calling broker.connect()...")
                if not self.broker.connect():
                    print("DEBUG: broker.connect() returned False")
                    raise Exception("Failed to connect to broker")
                print("DEBUG: broker.connect() returned True")
                
                self.log("✓ Connected to broker")
                
                # Get contract IDs for symbols
                self.log("Looking up contract IDs...")
                print(f"DEBUG: Looking up contract IDs for: {self.symbols}")
                for symbol in self.symbols:
                    try:
                        print(f"DEBUG: calling get_contract_id({symbol})")
                        contract_id = self.broker.get_contract_id(symbol)
                        print(f"DEBUG: get_contract_id({symbol}) returned {contract_id}")
                        if contract_id:
                            self.contract_ids[symbol] = contract_id
                            self.log(f"✓ {symbol} -> Contract ID: {contract_id}")
                        else:
                            self.log(f"⚠ Warning: Could not find contract ID for {symbol}")
                    except Exception as e:
                        print(f"DEBUG: Exception in get_contract_id: {e}")
                        self.log(f"⚠ Error getting contract ID for {symbol}: {e}")
                
                if not self.contract_ids:
                    raise Exception("No valid contract IDs found for selected symbols")
                
                # Connect to WebSocket
                self.log("Connecting to market data stream...")
                print("DEBUG: Getting session token...")
                session_token = self.broker.session_token
                print(f"DEBUG: token retrieved (length={len(session_token)})")
                
                print("DEBUG: Initializing BrokerWebSocketStreamer...")
                self.websocket = BrokerWebSocketStreamer(
                    session_token=session_token,
                    hub_url="wss://rtc.topstepx.com/hubs/market"
                )
                
                print("DEBUG: Calling websocket.connect()...")
                if not self.websocket.connect():
                    print("DEBUG: websocket.connect() returned False")
                    raise Exception("Failed to connect to WebSocket")
                print("DEBUG: websocket.connect() returned True")
                
                self.log("✓ Connected to market data stream")
                
                # Initialize CSV files
                self.log(f"Initializing CSV files in: {self.output_dir}")
                print(f"DEBUG: Initializing CSV files in {self.output_dir}")
                self._initialize_csv()
                
                # Subscribe to market data for each symbol
                self.is_recording = True
                for symbol, contract_id in self.contract_ids.items():
                    self.log(f"Subscribing to {symbol} market data...")
                    
                    # Only subscribe to trades - we'll aggregate them into 1-min bars
                    self.websocket.subscribe_trades(
                        contract_id,
                        lambda data, sym=symbol: self._on_trade(sym, data)
                    )
                    
                    self.log(f"✓ Subscribed to {symbol}")
                
                self.log("=" * 50)
                self.log("RECORDING STARTED")
                self.log(f"Recording {len(self.contract_ids)} symbols: {', '.join(self.contract_ids.keys())}")
                self.log(f"Output directory: {self.output_dir}")
                self.log(f"Format: 1-minute OHLCV bars")
                self.log("=" * 50)
                
                # Start statistics reporter
                self._start_stats_reporter()
                
            else:
                raise Exception(f"Unsupported broker: {self.broker_name}")
                
        except Exception as e:
            self.log(f"ERROR: {str(e)}")
            self.stop()
            raise
    
    def _initialize_csv(self):
        """Initialize CSV files for each symbol with OHLCV headers (append mode)."""
        headers = [
            'timestamp',
            'open',
            'high',
            'low',
            'close',
            'volume'
        ]
        
        for symbol in self.symbols:
            csv_path = self.output_dir / f"{symbol}_1min.csv"
            
            # Check if file exists to determine if we need to write headers
            file_exists = csv_path.exists()
            
            # Open in append mode to continue from where we left off
            self.csv_files[symbol] = open(csv_path, 'a', newline='')
            self.csv_writers[symbol] = csv.writer(self.csv_files[symbol])
            
            # Write header only if file is new
            if not file_exists:
                self.csv_writers[symbol].writerow(headers)
                self.csv_files[symbol].flush()
                self.log(f"✓ Created new CSV file: {csv_path}")
            else:
                self.log(f"✓ Appending to existing CSV file: {csv_path}")
            
            # Initialize current bar for this symbol (starts as None until first tick)
            self.current_bars[symbol] = None
    
    def _get_bar_timestamp(self, timestamp: datetime) -> datetime:
        """Round timestamp down to the nearest minute (bar boundary)."""
        return timestamp.replace(second=0, microsecond=0)
    
    def _write_bar_to_csv(self, symbol: str, bar: Dict[str, Any]):
        """Write a completed 1-minute bar to CSV (thread-safe)."""
        with self.csv_locks[symbol]:
            if symbol in self.csv_writers and self.is_recording:
                row = [
                    bar['timestamp'].isoformat(),
                    bar['open'],
                    bar['high'],
                    bar['low'],
                    bar['close'],
                    bar['volume']
                ]
                self.csv_writers[symbol].writerow(row)
                self.stats[symbol]['bars_written'] += 1
                
                # Flush periodically to ensure data is written
                if self.stats[symbol]['bars_written'] % CSV_FLUSH_FREQUENCY == 0:
                    self.csv_files[symbol].flush()
    
    def _update_or_complete_bar(self, symbol: str, price: float, volume: int, timestamp: datetime):
        """
        Update current bar or complete it and start a new one.
        
        Args:
            symbol: Trading symbol
            price: Trade price
            volume: Trade volume
            timestamp: Trade timestamp
        """
        with self.bar_locks[symbol]:
            bar_time = self._get_bar_timestamp(timestamp)
            
            # Check if we need to complete current bar and start new one
            if self.current_bars[symbol] is None:
                # First bar for this symbol
                self.current_bars[symbol] = {
                    'timestamp': bar_time,
                    'open': price,
                    'high': price,
                    'low': price,
                    'close': price,
                    'volume': volume
                }
            elif self.current_bars[symbol]['timestamp'] != bar_time:
                # New minute - complete previous bar and write to CSV
                completed_bar = self.current_bars[symbol]
                self._write_bar_to_csv(symbol, completed_bar)
                
                # Start new bar
                self.current_bars[symbol] = {
                    'timestamp': bar_time,
                    'open': price,
                    'high': price,
                    'low': price,
                    'close': price,
                    'volume': volume
                }
            else:
                # Update current bar (same minute)
                bar = self.current_bars[symbol]
                bar['high'] = max(bar['high'], price)
                bar['low'] = min(bar['low'], price)
                bar['close'] = price
                bar['volume'] += volume
    
    def _on_trade(self, symbol: str, data: Any):
        """Handle trade data and aggregate into 1-minute bars."""
        if not self.is_recording:
            return
        
        # Count this tick regardless of whether we can parse it
        self.stats[symbol]['ticks'] += 1
        
        try:
            # Try to extract timestamp from trade data first
            timestamp = None
            trade_price = None
            trade_size = 1
            
            # Universal parser for signalrcore variations
            # Pattern 1: [contractId, {tradeData}] - most common
            # Pattern 2: [contractId, [{tradeData}]] - sometimes wrapped in list
            # Pattern 3: {tradeData} - direct dict
            # Pattern 4: {p: price, v: volume} - compact format
            
            trade_dict = None
            
            if isinstance(data, list) and len(data) >= 2:
                # Pattern 1 or 2: [contractId, data]
                payload = data[1]
                if isinstance(payload, dict):
                    trade_dict = payload
                elif isinstance(payload, list) and len(payload) > 0:
                    trade_dict = payload[0] if isinstance(payload[0], dict) else None
            elif isinstance(data, list) and len(data) == 1:
                # Sometimes just [{tradeData}]
                if isinstance(data[0], dict):
                    trade_dict = data[0]
            elif isinstance(data, dict):
                # Pattern 3 or 4: direct dict
                trade_dict = data
            
            # Extract trade info from dict
            if trade_dict:
                # Try various field names used by TopStep
                trade_price = (trade_dict.get('price') or trade_dict.get('lastPrice') or 
                              trade_dict.get('p') or trade_dict.get('Price'))
                trade_size = (trade_dict.get('size') or trade_dict.get('volume') or 
                             trade_dict.get('v') or trade_dict.get('qty') or 1)
                
                # Try to extract timestamp from trade data
                timestamp_str = (trade_dict.get('timestamp') or trade_dict.get('time') or 
                                trade_dict.get('t') or trade_dict.get('Timestamp'))
                if timestamp_str:
                    try:
                        if isinstance(timestamp_str, str):
                            timestamp = datetime.fromisoformat(timestamp_str)
                        elif isinstance(timestamp_str, (int, float)):
                            # Unix timestamp in seconds or milliseconds
                            if timestamp_str > 1e12:  # Milliseconds
                                timestamp = datetime.fromtimestamp(timestamp_str / 1000.0)
                            else:  # Seconds
                                timestamp = datetime.fromtimestamp(timestamp_str)
                    except:
                        pass
            
            # Fallback to current time if we couldn't extract timestamp
            if timestamp is None:
                timestamp = datetime.now()
            
            # Update bar aggregation with this trade
            if trade_price is not None:
                self._update_or_complete_bar(symbol, trade_price, trade_size, timestamp)
            
        except Exception as e:
            logger.error(f"Error processing trade for {symbol}: {e}")
    
    def _start_stats_reporter(self):
        """Start background thread to report statistics."""
        def report_stats():
            while self.is_recording:
                time.sleep(STATS_REPORT_INTERVAL_SECONDS)
                if self.is_recording:
                    total_ticks = sum(s['ticks'] for s in self.stats.values())
                    total_bars = sum(s['bars_written'] for s in self.stats.values())
                    
                    self.log(
                        f"📊 Stats: Ticks={total_ticks}, Bars Written={total_bars}"
                    )
        
        stats_thread = threading.Thread(target=report_stats, daemon=True)
        stats_thread.start()
    
    def stop(self):
        """Stop recording and cleanup."""
        self.log("Stopping recorder...")
        self.is_recording = False
        
        # Flush any incomplete bars to CSV
        for symbol in self.symbols:
            with self.bar_locks[symbol]:
                if self.current_bars[symbol] is not None:
                    self._write_bar_to_csv(symbol, self.current_bars[symbol])
                    self.current_bars[symbol] = None
        
        # Close all CSV files
        for symbol, csv_file in self.csv_files.items():
            try:
                with self.csv_locks[symbol]:
                    csv_file.flush()
                    csv_file.close()
                csv_path = self.output_dir / f"{symbol}_1min.csv"
                self.log(f"✓ CSV file saved: {csv_path}")
            except Exception as e:
                self.log(f"⚠ Error closing file for {symbol}: {e}")
        
        # Disconnect WebSocket
        if self.websocket:
            try:
                self.websocket.disconnect()
                self.log("✓ Disconnected from market data stream")
            except:
                pass
        
        # Disconnect broker
        if self.broker:
            try:
                self.broker.disconnect()
                self.log("✓ Disconnected from broker")
            except:
                pass
        
        # Print final statistics
        self.log("=" * 50)
        self.log("RECORDING STOPPED")
        self.log("Final Statistics:")
        for symbol, stats in self.stats.items():
            self.log(
                f"  {symbol}: Ticks={stats['ticks']}, "
                f"1-min Bars={stats['bars_written']}"
            )
        self.log("=" * 50)

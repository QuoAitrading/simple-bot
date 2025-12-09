"""
Market Data Recorder
====================
Records live market data from brokers for backtesting purposes.

Captures:
- Quotes (Bid/Ask prices and sizes)
- Trades (Price, Size, Time)
- Market Depth/DOM (Order book levels)
- Timestamps

Output:
- Separate CSV file per symbol
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
CSV_FLUSH_FREQUENCY = 100  # Flush CSV file every N records
STATS_REPORT_INTERVAL_SECONDS = 10  # Report statistics every N seconds


class MarketDataRecorder:
    """Records live market data to CSV for backtesting."""
    
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
            output_dir: Output directory for CSV files (one per symbol)
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
        
        # Gap detection - track last timestamp per symbol
        self.last_timestamps = {symbol: None for symbol in symbols}
        self.gap_threshold_seconds = 60  # Write gap row if > 60 seconds between data points
        
        # Statistics
        self.stats = {symbol: {
            'quotes': 0,
            'trades': 0,
            'depth_updates': 0,
            'gaps_detected': 0
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
                    
                    # Subscribe to quotes
                    self.websocket.subscribe_quotes(
                        contract_id,
                        lambda data, sym=symbol: self._on_quote(sym, data)
                    )
                    
                    # Subscribe to trades
                    self.websocket.subscribe_trades(
                        contract_id,
                        lambda data, sym=symbol: self._on_trade(sym, data)
                    )
                    
                    # Subscribe to depth/DOM
                    try:
                        self.websocket.subscribe_depth(
                            contract_id,
                            lambda data, sym=symbol: self._on_depth(sym, data)
                        )
                    except Exception as e:
                        self.log(f"⚠ Could not subscribe to depth for {symbol}: {e}")
                    
                    self.log(f"✓ Subscribed to {symbol}")
                
                self.log("=" * 50)
                self.log("RECORDING STARTED")
                self.log(f"Recording {len(self.contract_ids)} symbols: {', '.join(self.contract_ids.keys())}")
                self.log(f"Output directory: {self.output_dir}")
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
        """Initialize CSV files for each symbol with headers (append mode)."""
        headers = [
            'timestamp',
            'data_type',  # quote, trade, depth, or GAP
            'bid_price',
            'bid_size',
            'ask_price',
            'ask_size',
            'trade_price',
            'trade_size',
            'trade_side',  # buy or sell
            'depth_level',
            'depth_side',  # bid or ask
            'depth_price',
            'depth_size'
        ]
        
        for symbol in self.symbols:
            csv_path = self.output_dir / f"{symbol}.csv"
            
            # Check if file exists to determine if we need to write headers
            file_exists = csv_path.exists()
            
            # Load last timestamp from existing file for gap detection
            if file_exists:
                self._load_last_timestamp(symbol, csv_path)
            
            # Open in append mode to continue from where we left off
            self.csv_files[symbol] = open(csv_path, 'a', newline='')
            self.csv_writers[symbol] = csv.writer(self.csv_files[symbol])
            
            # Write header only if file is new
            if not file_exists:
                self.csv_writers[symbol].writerow(headers)
                self.csv_files[symbol].flush()
                self.log(f"✓ Created new CSV file: {csv_path}")
            else:
                if self.last_timestamps[symbol]:
                    self.log(f"✓ Appending to {csv_path} (last data: {self.last_timestamps[symbol].strftime('%Y-%m-%d %H:%M:%S')})")
                else:
                    self.log(f"✓ Appending to existing CSV file: {csv_path}")
    
    def _load_last_timestamp(self, symbol: str, csv_path: Path):
        """Load last timestamp from existing CSV for gap detection."""
        try:
            with open(csv_path, 'r') as f:
                # Read last few lines to find most recent timestamp
                lines = f.readlines()
                for line in reversed(lines[-100:]):
                    try:
                        parts = line.strip().split(',')
                        if len(parts) > 1 and parts[0] != 'timestamp' and parts[1] != 'GAP':
                            timestamp_str = parts[0]
                            try:
                                self.last_timestamps[symbol] = datetime.fromisoformat(timestamp_str)
                                break
                            except:
                                pass
                    except:
                        continue
        except Exception as e:
            logger.debug(f"Could not load last timestamp for {symbol}: {e}")
    
    def _check_and_write_gap(self, symbol: str, current_timestamp: datetime):
        """Check for gap and write GAP row to CSV if detected."""
        last_ts = self.last_timestamps.get(symbol)
        if last_ts:
            gap_seconds = (current_timestamp - last_ts).total_seconds()
            if gap_seconds > self.gap_threshold_seconds:
                # Significant gap detected - write GAP row to CSV
                gap_minutes = gap_seconds / 60
                gap_hours = gap_minutes / 60
                
                if gap_hours >= 1:
                    gap_str = f"{gap_hours:.1f}h"
                else:
                    gap_str = f"{gap_minutes:.1f}m"
                
                # Write GAP marker row
                gap_row = [
                    current_timestamp.isoformat(),
                    'GAP',
                    f'Gap: {gap_str}',
                    f'From: {last_ts.isoformat()}',
                    f'To: {current_timestamp.isoformat()}',
                    '', '', '', '', '', '', '', ''
                ]
                self.csv_writers[symbol].writerow(gap_row)
                self.csv_files[symbol].flush()
                self.stats[symbol]['gaps_detected'] += 1
                self.log(f"⚠️  GAP in {symbol}: {gap_str} gap from {last_ts.strftime('%H:%M:%S')} to {current_timestamp.strftime('%H:%M:%S')}")
        
        # Update last timestamp
        self.last_timestamps[symbol] = current_timestamp
    
    def _write_csv_row(self, symbol: str, data: Dict[str, Any]):
        """Write a row to the symbol's CSV file (thread-safe) with gap detection."""
        with self.csv_locks[symbol]:
            if symbol in self.csv_writers and self.is_recording:
                # Check for gaps before writing data
                timestamp_str = data.get('timestamp', '')
                if timestamp_str:
                    try:
                        current_ts = datetime.fromisoformat(timestamp_str)
                        self._check_and_write_gap(symbol, current_ts)
                    except:
                        pass
                
                row = [
                    timestamp_str,
                    data.get('data_type', ''),
                    data.get('bid_price', ''),
                    data.get('bid_size', ''),
                    data.get('ask_price', ''),
                    data.get('ask_size', ''),
                    data.get('trade_price', ''),
                    data.get('trade_size', ''),
                    data.get('trade_side', ''),
                    data.get('depth_level', ''),
                    data.get('depth_side', ''),
                    data.get('depth_price', ''),
                    data.get('depth_size', '')
                ]
                self.csv_writers[symbol].writerow(row)
                
                # Flush periodically to ensure data is written
                if sum(self.stats[symbol].values()) % CSV_FLUSH_FREQUENCY == 0:
                    self.csv_files[symbol].flush()
    
    def _on_quote(self, symbol: str, data: Any):
        """Handle quote data with universal parsing for signalrcore variations."""
        if not self.is_recording:
            return
        
        try:
            timestamp = self._get_current_timestamp()
            bid_price = None
            ask_price = None
            bid_size = 1
            ask_size = 1
            
            # Universal parser for signalrcore variations
            # Pattern 1: [contractId, {quoteData}] - most common
            # Pattern 2: [contractId, [{quoteData}]] - sometimes wrapped in list
            # Pattern 3: {quoteData} - direct dict
            # Pattern 4: args coming as separate positional args
            
            quote_dict = None
            
            if isinstance(data, list) and len(data) >= 2:
                # Pattern 1 or 2: [contractId, data]
                payload = data[1]
                if isinstance(payload, dict):
                    quote_dict = payload
                elif isinstance(payload, list) and len(payload) > 0:
                    quote_dict = payload[0] if isinstance(payload[0], dict) else None
            elif isinstance(data, list) and len(data) == 1:
                # Sometimes just [{quoteData}]
                if isinstance(data[0], dict):
                    quote_dict = data[0]
            elif isinstance(data, dict):
                # Pattern 3: direct dict
                quote_dict = data
            
            # Extract prices from quote dict
            if quote_dict:
                bid_price = quote_dict.get('bestBid') or quote_dict.get('bid') or quote_dict.get('b')
                ask_price = quote_dict.get('bestAsk') or quote_dict.get('ask') or quote_dict.get('a')
                bid_size = quote_dict.get('bidSize') or quote_dict.get('bs') or 1
                ask_size = quote_dict.get('askSize') or quote_dict.get('as') or 1
            
            row_data = {
                'timestamp': timestamp,
                'data_type': 'quote',
                'bid_price': bid_price or '',
                'bid_size': bid_size or '',
                'ask_price': ask_price or '',
                'ask_size': ask_size or ''
            }
            
            self._write_csv_row(symbol, row_data)
            self.stats[symbol]['quotes'] += 1
            
        except Exception as e:
            logger.error(f"Error processing quote for {symbol}: {e}")
    
    def _on_trade(self, symbol: str, data: Any):
        """Handle trade data with universal parsing for signalrcore variations."""
        if not self.is_recording:
            return
        
        try:
            timestamp = self._get_current_timestamp()
            trade_price = None
            trade_size = 1
            trade_side = ''
            
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
                trade_side = (trade_dict.get('side') or trade_dict.get('aggressor') or 
                             trade_dict.get('s') or '')
            
            row_data = {
                'timestamp': timestamp,
                'data_type': 'trade',
                'trade_price': trade_price or '',
                'trade_size': trade_size or '',
                'trade_side': trade_side or ''
            }
            
            self._write_csv_row(symbol, row_data)
            self.stats[symbol]['trades'] += 1
            
        except Exception as e:
            logger.error(f"Error processing trade for {symbol}: {e}")
    
    def _on_depth(self, symbol: str, data: Any):
        """Handle market depth/DOM data."""
        if not self.is_recording:
            return
        
        try:
            timestamp = self._get_current_timestamp()
            
            # Market depth is typically an array of price levels
            # Data structure may vary by broker
            # Try to extract bid and ask levels
            
            # Process as list of levels
            if isinstance(data, (list, tuple)):
                for i, level in enumerate(data):
                    # Try to extract level data
                    side = getattr(level, 'side', None) or getattr(level, 'Side', None)
                    price = getattr(level, 'price', None) or getattr(level, 'Price', None)
                    size = getattr(level, 'size', None) or getattr(level, 'Size', None)
                    
                    if price is not None:
                        row_data = {
                            'timestamp': timestamp,
                            'data_type': 'depth',
                            'depth_level': i,
                            'depth_side': side or '',
                            'depth_price': price or '',
                            'depth_size': size or ''
                        }
                        self._write_csv_row(symbol, row_data)
            
            self.stats[symbol]['depth_updates'] += 1
            
        except Exception as e:
            logger.error(f"Error processing depth for {symbol}: {e}")
    
    def _start_stats_reporter(self):
        """Start background thread to report statistics."""
        def report_stats():
            while self.is_recording:
                time.sleep(STATS_REPORT_INTERVAL_SECONDS)
                if self.is_recording:
                    total_quotes = sum(s['quotes'] for s in self.stats.values())
                    total_trades = sum(s['trades'] for s in self.stats.values())
                    total_depth = sum(s['depth_updates'] for s in self.stats.values())
                    total_gaps = sum(s['gaps_detected'] for s in self.stats.values())
                    
                    self.log(
                        f"📊 Stats: Q={total_quotes}, T={total_trades}, "
                        f"D={total_depth}, Gaps={total_gaps}"
                    )
        
        stats_thread = threading.Thread(target=report_stats, daemon=True)
        stats_thread.start()
    
    def stop(self):
        """Stop recording and cleanup."""
        self.log("Stopping recorder...")
        self.is_recording = False
        
        # Close all CSV files
        for symbol, csv_file in self.csv_files.items():
            try:
                with self.csv_locks[symbol]:
                    csv_file.flush()
                    csv_file.close()
                csv_path = self.output_dir / f"{symbol}.csv"
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
                f"  {symbol}: Quotes={stats['quotes']}, "
                f"Trades={stats['trades']}, Depth={stats['depth_updates']}, "
                f"Gaps={stats['gaps_detected']}"
            )
        self.log("=" * 50)

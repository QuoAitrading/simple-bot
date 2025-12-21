"""
Signal Receiver - Listens to Master signals and executes on local account
This is what CUSTOMERS run on their systems
"""

import asyncio
import aiohttp
import logging
from typing import Optional, Callable
from datetime import datetime
import json
import socketio

# CRITICAL: Suppress SDK logs BEFORE any SDK imports happen
logging.getLogger('project_x_py').setLevel(logging.CRITICAL + 100)
logging.getLogger('project_x_py').disabled = True
logging.getLogger('project_x_py').propagate = False

# Add filter to root logger to block ALL project_x_py logs
class _SuppressSDKLogs(logging.Filter):
    def filter(self, record):
        return not record.name.startswith('project_x')

logging.getLogger().addFilter(_SuppressSDKLogs())

# Add parent to path for imports
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from shared.signal_protocol import TradeSignal
from shared.broker_client import BrokerClient

logger = logging.getLogger(__name__)

# Global session info for cleanup on Ctrl+C
_session_info = {
    "api_url": None,
    "follower_key": None,
    "status_running": True,  # Controls background thread
    "start_time": None,
    "trades_executed": 0,
    "trades_logged": [],  # List of trade dicts with PNL
    "current_position": None,  # {"symbol": "MES", "side": "LONG", "qty": 1, "entry_price": 6100}
    "entry_prices": {},  # {"MES": 6100.25} - track entry for PNL calc
    "session_pnl": 0.0,  # Running total PNL
}


class SignalReceiver:
    """
    Receives trade signals from Master and executes them locally
    Customers run this on their own machines
    """
    
    def __init__(self, api_url: str, follower_key: str, follower_name: str):
        """
        Args:
            api_url: Master's API URL
            follower_key: Unique key for this follower
            follower_name: Display name for this follower
        """
        self.api_url = api_url.rstrip('/')
        self.follower_key = follower_key
        self.follower_name = follower_name
        self.session: Optional[aiohttp.ClientSession] = None
        
        self.broker: Optional[BrokerClient] = None
        self.connected = False
        self.receiving = False
        self.trading_enabled = True
        
        # Stats
        self.signals_received = 0
        self.signals_executed = 0
        self.last_signal_time: Optional[str] = None
        
        # Callback
        self.on_signal: Optional[Callable[[TradeSignal], None]] = None
        
    async def connect(self, broker: BrokerClient) -> bool:
        """
        Connect to the relay server and register as a follower
        
        Args:
            broker: Connected BrokerClient for order execution
        """
        self.broker = broker
        self.session = aiohttp.ClientSession()
        
        try:
            async with self.session.post(
                f"{self.api_url}/copier/register",
                json={
                    "follower_key": self.follower_key,
                    "follower_name": self.follower_name
                },
                timeout=aiohttp.ClientTimeout(total=10)
            ) as resp:
                if resp.status == 200:
                    self.connected = True
                    logger.info(f"✅ Connected to Master as '{self.follower_name}'")
                    return True
                else:
                    error = await resp.text()
                    logger.error(f"❌ Failed to register: {error}")
                    return False
        except Exception as e:
            logger.error(f"❌ Connection error: {e}")
            return False
    
    async def disconnect(self):
        """Disconnect from relay server"""
        self.receiving = False
        self.connected = False
        if self.session:
            try:
                await self.session.post(
                    f"{self.api_url}/copier/unregister",
                    json={"follower_key": self.follower_key}
                )
            except:
                pass
            await self.session.close()
        logger.info("🔌 Disconnected from Master")
    
    async def start_receiving(self):
        """Start the signal receiving loop"""
        if not self.connected:
            logger.error("Not connected to Master")
            return
            
        self.receiving = True
        logger.info("📡 Listening for signals from Master...")
        
        while self.receiving:
            try:
                # Long-poll for new signals
                async with self.session.get(
                    f"{self.api_url}/copier/poll",
                    params={"follower_key": self.follower_key},
                    timeout=aiohttp.ClientTimeout(total=30)
                ) as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        if data.get("signal"):
                            await self._handle_signal(data["signal"])
                    elif resp.status == 204:
                        # No new signals, continue polling
                        pass
                    else:
                        logger.warning(f"Poll returned {resp.status}")
                        await asyncio.sleep(5)
                        
            except asyncio.TimeoutError:
                # Normal timeout, continue polling
                continue
            except Exception as e:
                logger.error(f"Poll error: {e}")
                await asyncio.sleep(5)
        
        logger.info("📡 Stopped receiving signals")
    
    async def _handle_signal(self, signal_data: dict):
        """Process a received signal"""
        try:
            signal = TradeSignal.from_dict(signal_data)
            self.signals_received += 1
            self.last_signal_time = datetime.now().isoformat()
            
            logger.info(f"📥 Received: {signal.action} {signal.side} {signal.quantity} {signal.symbol}")
            
            # Call custom handler if set
            if self.on_signal:
                self.on_signal(signal)
            
            # Execute if copy is enabled
            if self.copy_enabled and self.broker:
                success = await self._execute_signal(signal)
                if success:
                    self.signals_executed += 1
                    # Report execution to master
                    await self._report_execution(signal)
            else:
                logger.info("⏸️  Copy disabled, signal ignored")
                
        except Exception as e:
            logger.error(f"Failed to handle signal: {e}")
    
    async def _execute_signal(self, signal: TradeSignal) -> bool:
        """Execute a trade signal locally"""
        if not self.broker or not self.broker.connected:
            logger.error("Broker not connected, cannot execute")
            return False
            
        try:
            if signal.action == "OPEN":
                return await self.broker.place_market_order(
                    signal.symbol, signal.side, signal.quantity
                )
            elif signal.action == "CLOSE":
                # Close is just a reverse order
                close_side = "SELL" if signal.side == "BUY" else "BUY"
                return await self.broker.place_market_order(
                    signal.symbol, close_side, signal.quantity
                )
            elif signal.action == "FLATTEN":
                return await self.broker.flatten_position(signal.symbol)
            else:
                logger.warning(f"Unknown action: {signal.action}")
                return False
                
        except Exception as e:
            logger.error(f"Execution error: {e}")
            return False
    
    async def _report_execution(self, signal: TradeSignal):
        """Report successful execution back to master"""
        try:
            await self.session.post(
                f"{self.api_url}/copier/report",
                json={
                    "follower_key": self.follower_key,
                    "signal_id": signal.signal_id,
                    "status": "executed"
                },
                timeout=aiohttp.ClientTimeout(total=5)
            )
        except:
            pass  # Non-critical
    
    def get_status(self) -> dict:
        """Get current receiver status"""
        return {
            "connected": self.connected,
            "receiving": self.receiving,
            "copy_enabled": self.copy_enabled,
            "signals_received": self.signals_received,
            "signals_executed": self.signals_executed,
            "last_signal": self.last_signal_time
        }


# ============================================
# RAINBOW ASCII SPLASH ART
# ============================================
RAINBOW_LOGO = [
    "  ██████╗ ██╗   ██╗ ██████╗ ████████╗██████╗  █████╗ ██████╗ ██╗███╗   ██╗ ██████╗      █████╗ ██╗",
    " ██╔═══██╗██║   ██║██╔═══██╗╚══██╔══╝██╔══██╗██╔══██╗██╔══██╗██║████╗  ██║██╔════╝     ██╔══██╗██║",
    " ██║   ██║██║   ██║██║   ██║   ██║   ██████╔╝███████║██║  ██║██║██╔██╗ ██║██║  ███╗    ███████║██║",
    " ██║▄▄ ██║██║   ██║██║   ██║   ██║   ██╔══██╗██╔══██║██║  ██║██║██║╚██╗██║██║   ██║    ██╔══██║██║",
    " ╚██████╔╝╚██████╔╝╚██████╔╝   ██║   ██║  ██║██║  ██║██████╔╝██║██║ ╚████║╚██████╔╝    ██║  ██║██║",
    "  ╚═════╝  ╚═════╝  ╚═════╝    ╚═╝   ╚═╝  ╚═╝╚═╝  ╚═╝╚═════╝ ╚═╝╚═╝  ╚═══╝ ╚═════╝     ╚═╝  ╚═╝╚═╝"
]

RAINBOW_COLORS = [
    '\033[91m',  # Red
    '\033[38;5;208m',  # Orange
    '\033[93m',  # Yellow
    '\033[92m',  # Green
    '\033[96m',  # Cyan
    '\033[94m',  # Blue
    '\033[95m',  # Purple
    '\033[35m',  # Magenta
]
RESET = '\033[0m'


def color_char_gradient(char, position, total_chars, color_offset=0):
    """Color single char based on position - creates rainbow gradient across line."""
    if char.strip() == '':
        return char
    if total_chars == 0:
        return char
    
    # Calculate which color to use based on position in line
    color_index = int((position / total_chars) * len(RAINBOW_COLORS) + color_offset) % len(RAINBOW_COLORS)
    return f"{RAINBOW_COLORS[color_index]}{char}{RESET}"


def color_line_gradient(line, color_offset):
    """Color a line with rainbow gradient - exactly like original."""
    total_chars = len(line)
    colored_line = ""
    for i, char in enumerate(line):
        colored_line += color_char_gradient(char, i, total_chars, color_offset)
    return colored_line


def color_line_with_fade(line, color_offset, fade_progress):
    """Color line with fade-in effect for subtitle."""
    if fade_progress < 0.3:
        # Super dark
        dim_code = '\033[2m\033[90m'
    elif fade_progress < 0.6:
        dim_code = '\033[90m'
    elif fade_progress < 0.9:
        dim_code = '\033[37m'
    else:
        # Fully visible - use rainbow gradient
        return color_line_gradient(line, color_offset)
    
    # Apply dim during fade-in
    colored = ""
    for char in line:
        if char.strip():
            colored += dim_code + char + RESET
        else:
            colored += char
    return colored


SUBTITLE = "A L G O R I T H M I C   T R A D I N G"


def display_rainbow_splash(duration=3.0, fps=20, clear_after=True):
    """Display animated rainbow logo - exact copy of original main bot."""
    import time
    
    # Enable ANSI on Windows
    os.system("")
    
    frames = int(duration * fps)
    delay = 1.0 / fps
    
    # Get terminal dimensions
    try:
        terminal_size = os.get_terminal_size()
        terminal_width = terminal_size.columns
        terminal_height = terminal_size.lines
    except:
        terminal_width = 120
        terminal_height = 30
    
    # Calculate vertical centering
    logo_lines = len(RAINBOW_LOGO) + 2  # Logo + blank + subtitle
    vertical_padding = max(0, (terminal_height - logo_lines) // 2)
    total_display_lines = len(RAINBOW_LOGO) + 2
    
    for frame in range(frames):
        # Calculate color offset for flowing rainbow
        color_offset = (frame / frames) * len(RAINBOW_COLORS)
        
        # Calculate fade-in progress for subtitle
        fade_progress = frame / max(1, frames - 1)
        
        # First frame - add vertical padding
        if frame == 0:
            print("\n" * vertical_padding, end='')
            sys.stdout.flush()
        else:
            # Move cursor up to beginning of logo
            sys.stdout.write(f'\033[{total_display_lines}A')
        
        # Display each line with rainbow gradient
        for line in RAINBOW_LOGO:
            sys.stdout.write('\033[2K')  # Clear line
            colored = color_line_gradient(line, color_offset)
            padding = max(0, (terminal_width - len(line)) // 2)
            sys.stdout.write(" " * padding + colored + "\n")
        
        # Blank line
        sys.stdout.write('\033[2K\n')
        
        # Subtitle with fade-in effect
        sys.stdout.write('\033[2K')
        subtitle_colored = color_line_with_fade(SUBTITLE, color_offset, fade_progress)
        subtitle_padding = max(0, (terminal_width - len(SUBTITLE)) // 2)
        sys.stdout.write(" " * subtitle_padding + subtitle_colored + "\n")
        
        sys.stdout.flush()
        
        if frame < frames - 1:
            time.sleep(delay)
    
    if clear_after:
        # Clear screen AND scrollback buffer like original
        time.sleep(0.3)
        sys.stdout.write('\033[3J')  # Clear scrollback buffer
        sys.stdout.write('\033[2J')  # Clear screen
        sys.stdout.write('\033[H')   # Move to top
        sys.stdout.flush()
    else:
        print("\n" + "=" * 60)
        print(" " * 20 + "INITIALIZING...")
        print("=" * 60 + "\n")


async def main():
    """Main entry point with rainbow splash and signal listening."""
    import argparse
    
    parser = argparse.ArgumentParser(description='QuoTrading Signal Receiver')
    parser.add_argument('--config', type=str, help='Path to config.json')
    args = parser.parse_args()
    
    # Load config
    config_path = args.config or os.path.join(os.path.dirname(__file__), 'config.json')
    
    try:
        with open(config_path, 'r') as f:
            config = json.load(f)
    except Exception as e:
        print(f"❌ Failed to load config: {e}")
        return
    
    # Display rainbow splash
    display_rainbow_splash(duration=3.0)
    
    # Extract settings
    api_url = config.get('master_api_url', 'https://quotrading-flask-api.azurewebsites.net')
    follower_key = config.get('quotrading_api_key', '')
    account_names = config.get('selected_account_names', ['AI Trading'])
    account_balances = config.get('selected_account_balances', [0])
    follower_name = account_names[0] if account_names else 'AI Trading'
    account_balance = account_balances[0] if account_balances else 0
    
    # Store for cleanup on shutdown (Ctrl+C releases session immediately)
    _session_info["api_url"] = api_url
    _session_info["follower_key"] = follower_key
    _session_info["start_time"] = datetime.now()
    
    # Generate device fingerprint for duplicate session detection
    import hashlib
    import uuid
    import platform
    device_info = f"{uuid.getnode()}-{platform.node()}-{platform.system()}"
    device_fingerprint = hashlib.sha256(device_info.encode()).hexdigest()[:32]
    _session_info["device_fingerprint"] = device_fingerprint
    
    # Connect to broker for trade execution (silently)
    broker = None
    broker_balance = None
    try:
        # Use standalone copier broker - no main bot dependencies
        from shared.copier_broker import CopierBroker
        
        broker_username = config.get('broker_username', '')
        broker_token = config.get('broker_token', '')
        
        if broker_username and broker_token:
            broker = CopierBroker(username=broker_username, api_token=broker_token)
            connected = await broker.connect()
            if connected:
                broker_balance = getattr(broker, 'account_balance', None)
                print("✅ Connected to broker")
            else:
                print("❌ Broker connection failed")
                broker = None
        else:
            pass  # Silent if no credentials
    except Exception as e:
        print(f"⚠️  Broker error: {e} - Signals will be displayed only")
        broker = None
    
    # Measure ping and get license expiration from server
    import time as time_module
    import aiohttp
    
    license_expiry = "Validating..."
    ping_ms = "--"
    
    try:
        async with aiohttp.ClientSession() as check_session:
            start_time = time_module.time()
            async with check_session.post(
                f"{api_url}/copier/validate-license",
                json={"license_key": follower_key},
                timeout=aiohttp.ClientTimeout(total=5)
            ) as resp:
                ping_ms = int((time_module.time() - start_time) * 1000)
                
                if resp.status == 200:
                    data = await resp.json()
                    if data.get("valid"):
                        print("✅ Connected to QuoTrading AI Server")
                        expiry_str = data.get("expiration_date", "")
                        if expiry_str:
                            try:
                                expiry = datetime.fromisoformat(expiry_str.replace("Z", "+00:00"))
                                now = datetime.now(expiry.tzinfo)
                                delta = expiry - now
                                days_left = delta.days
                                hours_left = (delta.seconds // 3600) % 24
                                mins_left = (delta.seconds // 60) % 60
                                secs_left = delta.seconds % 60
                                
                                if days_left > 0:
                                    license_expiry = f"{days_left}d {hours_left}h {mins_left}m {secs_left}s"
                                elif hours_left > 0:
                                    license_expiry = f"{hours_left}h {mins_left}m {secs_left}s"
                                elif mins_left > 0:
                                    license_expiry = f"{mins_left}m {secs_left}s"
                                else:
                                    license_expiry = "Expired"
                            except:
                                license_expiry = "Active"
                    else:
                        print("❌ Invalid license")
                        license_expiry = "Invalid"
    except:
        license_expiry = "Unable to verify"
        ping_ms = "Timeout"
    
    # Get terminal width for ping placement
    try:
        term_width = os.get_terminal_size().columns
    except:
        term_width = 80
    
    # Print header with ping on right
    header = "🤖 QuoTrading AI - Active Trading Mode"
    ping_text = f"Ping: {ping_ms}ms"
    spacing = term_width - len(header) - len(ping_text) - 2
    print(f"\n{header}" + " " * max(1, spacing) + ping_text)  # Line 1
    
    print(f"   License: {follower_key}")  # Line 2
    print(f"   Expires: {license_expiry}")  # Line 3
    
    # Show all selected accounts
    account_lines = 0
    if len(account_names) == 1:
        print(f"   Account: {account_names[0]}")  # Line 4
        print(f"   Balance: ${account_balances[0] if account_balances else 0:,.2f}\n")  # Line 5
        account_lines = 2
    else:
        print(f"   Accounts: {len(account_names)} selected")
        account_lines = 1
        for i, name in enumerate(account_names):
            balance = account_balances[i] if i < len(account_balances) else 0
            print(f"      • {name} — ${balance:,.2f}")
            account_lines += 1
        print()
        account_lines += 1
    
    print("=" * 80)
    
    print("\n🧠 AI Engine Online - Monitoring for trade opportunities...")
    print("   Press Ctrl+C to stop\n")
    
    # Calculate total lines from header to current position for cursor math
    # header(1) + license(1) + expires(1) + accounts(2-N) + separator(1) + status(2) + ctrl-c(1) + blank(1) = varies
    lines_from_header_to_expires = 2  # From header to expires line
    lines_from_expires_to_bottom = account_lines + 5  # accounts + separator + status lines
    total_lines_below_header = lines_from_header_to_expires + lines_from_expires_to_bottom
    
    import threading
    
    countdown_running = True
    expiry_datetime = None
    
    # Parse expiration date for live countdown
    if license_expiry not in ["Validating...", "Unable to verify", "Invalid", "Active", "Expired"]:
        try:
            async with aiohttp.ClientSession() as temp_session:
                async with temp_session.post(
                    f"{api_url}/copier/validate-license",
                    json={"license_key": follower_key},
                    timeout=aiohttp.ClientTimeout(total=5)
                ) as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        expiry_str = data.get("expiration_date", "")
                        if expiry_str:
                            expiry_datetime = datetime.fromisoformat(expiry_str.replace("Z", "+00:00"))
        except:
            pass
    
    import aiohttp
    
    async with aiohttp.ClientSession() as session:
        # Register with server
        try:
            async with session.post(
                f"{api_url}/copier/register",
                json={
                    "follower_key": follower_key,
                    "follower_name": follower_name,
                    "account_ids": config.get('selected_account_ids', []),
                    "device_fingerprint": device_fingerprint
                },
                timeout=aiohttp.ClientTimeout(total=10)
            ) as resp:
                if resp.status == 200:
                    pass  # Already showed connection success above
                elif resp.status == 409:
                    # Duplicate session - another device is using this license
                    data = await resp.json()
                    print(f"\n❌ {data.get('error', 'License already in use')}")
                    print(f"   {data.get('message', 'Close the other session first.')}")
                    print("\nPress Enter to exit...")
                    input()
                    return
                else:
                    print(f"⚠️  Server connection returned {resp.status}")
        except Exception as e:
            print(f"⚠️  Could not register: {e}")
        
        # Background thread for updating ping and countdown in header
        import threading
        import requests
        
        license_expired = False  # Flag to signal license expiration
        current_ping_ms = ping_ms
        lines_printed = 1  # Track lines printed after initial display
        
        def status_updater():
            nonlocal current_ping_ms, lines_printed
            update_count = 0
            
            while _session_info["status_running"]:
                time_module.sleep(1)
                if not _session_info["status_running"]:
                    break
                
                update_count += 1
                
                try:
                    # Calculate countdown
                    if expiry_datetime:
                        now = datetime.now(expiry_datetime.tzinfo)
                        delta = expiry_datetime - now
                        
                        if delta.total_seconds() <= 0:
                            countdown_str = "EXPIRED"
                            # License expired - signal main loop to stop
                            nonlocal license_expired
                            license_expired = True
                            print("\n\n❌ LICENSE EXPIRED - Session ending...")
                            status_running = False
                            return
                        else:
                            days = delta.days
                            hours = (delta.seconds // 3600) % 24
                            mins = (delta.seconds // 60) % 60
                            secs = delta.seconds % 60
                            
                            if days > 0:
                                countdown_str = f"{days}d {hours}h {mins}m {secs}s"
                            elif hours > 0:
                                countdown_str = f"{hours}h {mins}m {secs}s"
                            elif mins > 0:
                                countdown_str = f"{mins}m {secs}s"
                            else:
                                countdown_str = f"{secs}s"
                    else:
                        countdown_str = license_expiry
                    
                    # Update ping AND send heartbeat every 20 seconds to keep session alive
                    if update_count % 20 == 0:
                        try:
                            # Measure ping
                            start = time_module.time()
                            requests.get(f"{api_url}/copier/status", timeout=5)
                            current_ping_ms = int((time_module.time() - start) * 1000)
                            
                            # Send heartbeat to keep session lock alive (60 sec timeout, refresh every 20 sec)
                            requests.post(
                                f"{api_url}/api/heartbeat",
                                json={
                                    "license_key": follower_key,
                                    "device_fingerprint": device_fingerprint,
                                    "symbol": "COPIER",
                                    "status": "online",
                                    "metadata": {"client": "copier_signal_receiver"}
                                },
                                timeout=5
                            )
                        except:
                            pass
                    
                    # Fixed line positions from cursor (which is after "Press Ctrl+C to stop"):
                    # Layout: header > license > expires > account > balance > blank > === > blank > AI Engine > Ctrl+C > blank
                    base_lines = 9  # From cursor up to expires
                    lines_to_expires = base_lines
                    
                    # Go up to expires line, clear it, write new value
                    sys.stdout.write(f"\033[{lines_to_expires}A")  # Move up to expires
                    sys.stdout.write("\033[2K")  # Clear line
                    sys.stdout.write(f"   Expires: {countdown_str}")
                    
                    # Go up 2 more to header, update just the ping at the end
                    sys.stdout.write("\033[2A")  # Move up 2 to header
                    ping_text = f"Ping: {current_ping_ms}ms"
                    col = term_width - len(ping_text)
                    sys.stdout.write(f"\033[{col}G{ping_text}")
                    
                    # Go back down to original position
                    sys.stdout.write(f"\033[{lines_to_expires + 2}B")  # Move back down
                    sys.stdout.write("\r")  # Back to start of line
                    sys.stdout.flush()
                    
                except:
                    pass
        
        status_thread = threading.Thread(target=status_updater, daemon=True)
        status_thread.start()
        
        # ===== WEBSOCKET-BASED SIGNAL RECEIVING =====
        # Create async socketio client for instant signal delivery
        sio = socketio.AsyncClient(
            reconnection=True,
            reconnection_attempts=0,  # Infinite retries
            reconnection_delay=1,
            reconnection_delay_max=10,
            logger=False,
            engineio_logger=False
        )
        
        ws_connected = False
        
        # Convert HTTP URL to WebSocket URL
        ws_url = api_url.replace('https://', 'wss://').replace('http://', 'ws://')
        
        @sio.event(namespace='/copier')
        async def connect():
            nonlocal ws_connected
            ws_connected = True
            # Connection confirmed via event handler
            # Subscribe with license key
            await sio.emit('subscribe', {'license_key': follower_key}, namespace='/copier')
        
        @sio.event(namespace='/copier')
        async def disconnect():
            nonlocal ws_connected
            ws_connected = False
            print("   ⚠️  WebSocket disconnected - reconnecting...")
        
        @sio.on('trade_signal', namespace='/copier')
        async def on_trade_signal(signal):
            """Handle incoming trade signal via WebSocket - execute locally"""
            nonlocal broker, license_expired
            
            if license_expired:
                return
                
            timestamp = datetime.now().strftime("%H:%M:%S")
            action = signal.get('action', 'UNKNOWN')
            side = signal.get('side', '')
            quantity = signal.get('quantity', 1)
            symbol = signal.get('symbol', '')
            
            # AI-style messaging (no copy references)
            print(f"\n[{timestamp}] 🧠 AI TRADE SIGNAL [WebSocket]")
            print(f"   Action: {action} | {side} {quantity} {symbol}")
            
            # Sound alert
            try:
                import winsound
                winsound.Beep(800, 200)  # 800Hz for 200ms
            except:
                print("\a", end="")  # Terminal bell fallback
            # Execute trade if broker is connected
            if broker and broker.connected:
                try:
                    if action == "OPEN":
                        # Open position
                        print(f"   ⏳ AI executing {side} {quantity} {symbol}...")
                        success = await broker.place_market_order(
                            symbol=symbol,
                            side=side.upper(),
                            quantity=quantity
                        )
                        if success:
                            # Success sound
                            try:
                                winsound.Beep(1000, 150)
                                winsound.Beep(1200, 150)
                            except:
                                pass
                            pos_side = 'LONG' if side.upper() == 'BUY' else 'SHORT'
                            entry_price = signal.get('entry_price', 0)
                            print(f"   ✅ FILLED: {side} {quantity} {symbol}")
                            print(f"   📊 Position: {pos_side} {quantity} {symbol} @ ${entry_price:,.2f}")
                            
                            # Track trade, position, and entry price
                            _session_info["trades_executed"] += 1
                            _session_info["trades_logged"].append({
                                "time": timestamp,
                                "action": "OPEN",
                                "side": pos_side,
                                "qty": quantity,
                                "symbol": symbol,
                                "price": entry_price,
                                "pnl": None
                            })
                            _session_info["current_position"] = {
                                "symbol": symbol,
                                "side": pos_side,
                                "qty": quantity,
                                "entry_price": entry_price
                            }
                            _session_info["entry_prices"][symbol] = entry_price
                            
                            # Set stop loss if provided
                            stop_loss = signal.get('stop_loss')
                            if stop_loss:
                                close_side = "BUY" if side.upper() == "SELL" else "SELL"
                                await broker.place_stop_order(symbol, close_side, quantity, stop_loss)
                                print(f"   🛑 Stop loss: {stop_loss}")
                        else:
                            try:
                                winsound.Beep(400, 300)
                            except:
                                pass
                            print(f"   ❌ Order failed - check broker connection")
                    
                    elif action == "CLOSE":
                        close_side = "SELL" if side.upper() == "BUY" else "BUY"
                        print(f"   ⏳ AI closing {quantity} {symbol}...")
                        success = await broker.place_market_order(
                            symbol=symbol,
                            side=close_side,
                            quantity=quantity
                        )
                        if success:
                            try:
                                winsound.Beep(600, 100)
                                winsound.Beep(800, 100)
                            except:
                                pass
                            
                            exit_price = signal.get('exit_price', 0)
                            entry_price = _session_info["entry_prices"].get(symbol, 0)
                            tick_value = 12.50 if 'ES' in symbol or 'MES' in symbol else 5.0
                            pos = _session_info.get("current_position")
                            pnl = 0
                            if pos and entry_price and exit_price:
                                if pos["side"] == "LONG":
                                    pnl = (exit_price - entry_price) * quantity * tick_value
                                else:
                                    pnl = (entry_price - exit_price) * quantity * tick_value
                                _session_info["session_pnl"] += pnl
                                pnl_str = f"+${pnl:,.2f}" if pnl >= 0 else f"-${abs(pnl):,.2f}"
                                print(f"   ✅ CLOSED: {quantity} {symbol} @ ${exit_price:,.2f}")
                                print(f"   💰 Trade PNL: {pnl_str}")
                            else:
                                print(f"   ✅ CLOSED: {quantity} {symbol}")
                            print(f"   📊 Session PNL: ${_session_info['session_pnl']:,.2f}")
                            
                            _session_info["trades_executed"] += 1
                            _session_info["trades_logged"].append({
                                "time": timestamp,
                                "action": "CLOSE",
                                "side": close_side,
                                "qty": quantity,
                                "symbol": symbol,
                                "price": exit_price,
                                "pnl": pnl
                            })
                        else:
                            print(f"   ❌ Close failed!")
                    
                    elif action == "FLATTEN":
                        print(f"   ⏳ AI flattening all {symbol} positions...")
                        success = await broker.flatten_position(symbol)
                        if success:
                            try:
                                winsound.Beep(600, 100)
                                winsound.Beep(500, 100)
                                winsound.Beep(400, 100)
                            except:
                                pass
                            
                            exit_price = signal.get('exit_price', 0)
                            entry_price = _session_info["entry_prices"].get(symbol, 0)
                            tick_value = 12.50 if 'ES' in symbol or 'MES' in symbol else 5.0
                            pos = _session_info.get("current_position")
                            pnl = 0
                            if pos and entry_price and exit_price:
                                qty = pos.get("qty", 1)
                                if pos["side"] == "LONG":
                                    pnl = (exit_price - entry_price) * qty * tick_value
                                else:
                                    pnl = (entry_price - exit_price) * qty * tick_value
                                _session_info["session_pnl"] += pnl
                                pnl_str = f"+${pnl:,.2f}" if pnl >= 0 else f"-${abs(pnl):,.2f}"
                                print(f"   ✅ FLAT: All {symbol} @ ${exit_price:,.2f}")
                                print(f"   💰 Trade PNL: {pnl_str}")
                            else:
                                print(f"   ✅ FLAT: All {symbol} positions closed")
                            print(f"   📊 Session PNL: ${_session_info['session_pnl']:,.2f}")
                            
                            _session_info["trades_executed"] += 1
                            _session_info["trades_logged"].append({
                                "time": timestamp,
                                "action": "FLATTEN",
                                "side": "-",
                                "qty": pos.get("qty", 0) if pos else 0,
                                "symbol": symbol,
                                "price": exit_price,
                                "pnl": pnl
                            })
                            _session_info["current_position"] = None
                            _session_info["entry_prices"].pop(symbol, None)
                        else:
                            print(f"   ❌ Flatten failed!")
                    
                    else:
                        print(f"   ⚠️ Unknown action: {action}")
                        
                except Exception as exec_e:
                    print(f"   ❌ Execution error: {exec_e}")
            else:
                print(f"   ⚠️ Broker not connected - Signal logged only")
        
        # Connect to WebSocket and wait
        try:
            await sio.connect(ws_url, namespaces=['/copier'])
            # Connection successful - waiting for signals silently
            
            # Keep connection alive until license expires or KeyboardInterrupt
            while not license_expired:
                await asyncio.sleep(1)
                
        except Exception as ws_error:
            print(f"⚠️  WebSocket connection failed: {ws_error}")
            print("   Signals will not be received - please restart")


THANK_YOU_MESSAGE = "Thanks for using QuoTrading AI"
SUPPORT_MESSAGE = "Any issues? Reach out to: support@quotrading.com"



def cleanup_session():
    """Stop background thread, show session summary, and unregister from API."""
    import time as t
    from datetime import datetime
    
    # Stop the status updater thread first
    _session_info["status_running"] = False
    t.sleep(0.2)  # Give thread time to stop
    
    # Clear screen for clean exit
    print("\033[2J\033[H", end="")
    
    # Show session summary
    print("=" * 60)
    print("                  📊 SESSION SUMMARY")
    print("=" * 60)
    
    # Session duration
    if _session_info.get("start_time"):
        duration = datetime.now() - _session_info["start_time"]
        hours = int(duration.total_seconds() // 3600)
        mins = int((duration.total_seconds() % 3600) // 60)
        secs = int(duration.total_seconds() % 60)
        if hours > 0:
            duration_str = f"{hours}h {mins}m {secs}s"
        elif mins > 0:
            duration_str = f"{mins}m {secs}s"
        else:
            duration_str = f"{secs}s"
        print(f"\n⏱️  Session Duration: {duration_str}")
    
    # Trades
    trades = _session_info.get("trades_executed", 0)
    print(f"📈 Trades Executed: {trades}")
    
    # Session PNL
    session_pnl = _session_info.get("session_pnl", 0)
    if session_pnl >= 0:
        print(f"💰 Session PNL: +${session_pnl:,.2f}")
    else:
        print(f"💰 Session PNL: -${abs(session_pnl):,.2f}")
    
    # Current position
    pos = _session_info.get("current_position")
    if pos:
        entry = pos.get('entry_price', 0)
        print(f"📊 Final Position: {pos['side']} {pos['qty']} {pos['symbol']} @ ${entry:,.2f}")
    else:
        print(f"📊 Final Position: FLAT")
    
    # Trade log with PNL
    trade_log = _session_info.get("trades_logged", [])
    if trade_log:
        print(f"\n📝 Trade Log:")
        for t_entry in trade_log[-10:]:  # Show last 10 trades
            pnl = t_entry.get('pnl')
            price = t_entry.get('price', 0)
            if t_entry['action'] == 'OPEN':
                print(f"   [{t_entry['time']}] OPEN {t_entry['side']} {t_entry['qty']} {t_entry['symbol']} @ ${price:,.2f}")
            elif pnl is not None and pnl != 0:
                pnl_str = f"+${pnl:,.2f}" if pnl >= 0 else f"-${abs(pnl):,.2f}"
                print(f"   [{t_entry['time']}] {t_entry['action']} {t_entry['symbol']} → {pnl_str}")
            else:
                print(f"   [{t_entry['time']}] {t_entry['action']} {t_entry['symbol']}")
    
    print("\n" + "=" * 60)
    
    # Release session via API
    if _session_info["api_url"] and _session_info["follower_key"]:
        try:
            import requests
            resp = requests.post(
                f"{_session_info['api_url']}/api/session/release",
                json={
                    "license_key": _session_info["follower_key"],
                    "device_fingerprint": _session_info.get("device_fingerprint", ""),
                    "symbol": "COPIER"
                },
                timeout=5
            )
            if resp.status_code == 200:
                print("✅ Session released")
        except Exception as e:
            print(f"⚠️  Could not release session: {e}")


def display_animated_thank_you(duration=10.0, fps=15):
    """Display animated rainbow thank you message on exit."""
    import time as t
    
    frames = int(duration * fps)
    delay = 1.0 / fps
    
    try:
        term_width = os.get_terminal_size().columns
    except:
        term_width = 80
    
    msg_padding = max(0, (term_width - len(THANK_YOU_MESSAGE)) // 2)
    support_padding = max(0, (term_width - len(SUPPORT_MESSAGE)) // 2)
    
    print()
    
    for frame in range(frames):
        color_offset = frame % len(RAINBOW_COLORS)
        
        if frame > 0:
            sys.stdout.write('\033[2A')
        
        sys.stdout.write('\033[2K')
        colored_msg = ''.join(
            f"{RAINBOW_COLORS[(i + color_offset) % len(RAINBOW_COLORS)]}{c}{RESET}"
            for i, c in enumerate(THANK_YOU_MESSAGE)
        )
        sys.stdout.write(" " * msg_padding + colored_msg + "\n")
        
        sys.stdout.write('\033[2K')
        colored_support = ''.join(
            f"{RAINBOW_COLORS[(i + color_offset) % len(RAINBOW_COLORS)]}{c}{RESET}"
            for i, c in enumerate(SUPPORT_MESSAGE)
        )
        sys.stdout.write(" " * support_padding + colored_support + "\n")
        
        sys.stdout.flush()
        
        if frame < frames - 1:
            t.sleep(delay)
    
    print()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n")
        cleanup_session()  # Release session immediately
        display_animated_thank_you(duration=10.0)


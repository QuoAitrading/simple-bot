"""
QuoTrading Customer Bot - Local Execution
==========================================
Lightweight bot that fetches signals from cloud API and executes trades locally.

Cloud Architecture:
- Signal Generation: Azure (signal_engine_v2.py)
- Trade Execution: Local (this file)
- License Validation: Render

Author: QuoTraders Team
Version: 2.0 (Cloud-Connected)
"""

import asyncio
import json
import logging
import os
import sys
from datetime import datetime
from typing import Optional, Dict, Any
import aiohttp
import pytz

# Import local execution modules
from src.topstep_websocket import TopstepWebSocket
from src.config import load_config
from src.notifications import NotificationManager
from src.monitoring import PerformanceMonitor
from src.session_state import SessionState

# ============================================================================
# CONFIGURATION
# ============================================================================

# Cloud API Configuration
SIGNAL_API_URL = "https://quotrading-signals.icymeadow-86b2969e.eastus.azurecontainerapps.io"
LICENSE_API_URL = "https://quotrading-license.onrender.com"  # Your Render license API
SIGNAL_CHECK_INTERVAL = 5  # seconds

# Trading Configuration
INSTRUMENT = "ES"  # E-mini S&P 500
TIMEZONE = pytz.timezone("America/New_York")

# ============================================================================
# LOGGING SETUP
# ============================================================================

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('logs/customer_bot.log'),
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger(__name__)


# ============================================================================
# CUSTOMER BOT CLASS
# ============================================================================

class QuoTradingCustomerBot:
    """Lightweight customer bot for local trade execution with cloud signals"""
    
    def __init__(self, config_path: str = "config.json"):
        self.config = load_config(config_path)
        self.running = False
        
        # Cloud API session
        self.http_session: Optional[aiohttp.ClientSession] = None
        
        # Trading components
        self.ws: Optional[TopstepWebSocket] = None
        self.notifications = NotificationManager(self.config)
        self.monitor = PerformanceMonitor()
        self.session_state = SessionState()
        
        # State tracking
        self.current_signal = "NONE"
        self.in_position = False
        self.position_side = None  # 'LONG' or 'SHORT'
        self.entry_price = None
        self.license_valid = False
        
        logger.info("Customer Bot initialized")
    
    async def validate_license(self) -> bool:
        """Validate license with Render API"""
        try:
            license_key = self.config.get('license_key')
            if not license_key:
                logger.error("No license key found in config")
                return False
            
            async with self.http_session.post(
                f"{LICENSE_API_URL}/validate",
                json={"license_key": license_key}
            ) as response:
                if response.status == 200:
                    data = await response.json()
                    self.license_valid = data.get('valid', False)
                    logger.info(f"License validation: {'VALID' if self.license_valid else 'INVALID'}")
                    return self.license_valid
                else:
                    logger.error(f"License validation failed: {response.status}")
                    return False
        except Exception as e:
            logger.error(f"License validation error: {e}")
            return False
    
    async def fetch_signal(self) -> Dict[str, Any]:
        """Fetch latest signal from cloud API"""
        try:
            async with self.http_session.get(f"{SIGNAL_API_URL}/api/signal") as response:
                if response.status == 200:
                    data = await response.json()
                    return data
                else:
                    logger.warning(f"Failed to fetch signal: {response.status}")
                    return {"signal": "NONE", "message": "API error"}
        except Exception as e:
            logger.error(f"Error fetching signal: {e}")
            return {"signal": "NONE", "message": str(e)}
    
    async def send_market_data(self, price: float, volume: int):
        """Send market data to cloud signal engine"""
        try:
            payload = {
                "price": price,
                "volume": volume,
                "timestamp": datetime.now(TIMEZONE).isoformat()
            }
            async with self.http_session.post(
                f"{SIGNAL_API_URL}/api/market_data",
                json=payload
            ) as response:
                if response.status == 200:
                    logger.debug("Market data sent to cloud")
                else:
                    logger.warning(f"Failed to send market data: {response.status}")
        except Exception as e:
            logger.error(f"Error sending market data: {e}")
    
    async def execute_signal(self, signal_data: Dict[str, Any]):
        """Execute trade based on signal from cloud"""
        signal = signal_data.get('signal', 'NONE')
        
        # Skip if no change
        if signal == self.current_signal:
            return
        
        self.current_signal = signal
        logger.info(f"New signal from cloud: {signal}")
        
        # Handle position entry
        if signal in ['LONG', 'SHORT'] and not self.in_position:
            await self.enter_position(signal, signal_data)
        
        # Handle position exit
        elif signal == 'EXIT' and self.in_position:
            await self.exit_position(signal_data)
        
        # Handle NONE signal (close any position)
        elif signal == 'NONE' and self.in_position:
            await self.exit_position({"message": "Market closed or no signal"})
    
    async def enter_position(self, side: str, signal_data: Dict[str, Any]):
        """Enter a new position"""
        try:
            # Get current market price from WebSocket
            if not self.ws or not self.ws.last_tick:
                logger.warning("No market data available, cannot enter position")
                return
            
            price = self.ws.last_tick['price']
            
            # Calculate position size based on account and risk settings
            position_size = self.calculate_position_size()
            
            # Place order
            order_type = side  # 'LONG' or 'SHORT'
            logger.info(f"Entering {order_type} position at {price}, size: {position_size}")
            
            # Send order via WebSocket
            await self.ws.place_order(
                side=order_type,
                quantity=position_size,
                price=price
            )
            
            # Update state
            self.in_position = True
            self.position_side = side
            self.entry_price = price
            
            # Send notification
            await self.notifications.send_alert(
                f"🟢 ENTERED {side} at {price}",
                f"Signal: {signal_data.get('message', 'Cloud signal')}\n"
                f"VWAP: {signal_data.get('vwap', 'N/A')}\n"
                f"RSI: {signal_data.get('rsi', 'N/A')}"
            )
            
            logger.info(f"Position entered successfully: {side} @ {price}")
            
        except Exception as e:
            logger.error(f"Error entering position: {e}")
            await self.notifications.send_alert("❌ ENTRY ERROR", str(e))
    
    async def exit_position(self, signal_data: Dict[str, Any]):
        """Exit current position"""
        try:
            if not self.in_position:
                logger.warning("No position to exit")
                return
            
            # Get current market price
            if not self.ws or not self.ws.last_tick:
                logger.warning("No market data available, cannot exit position")
                return
            
            exit_price = self.ws.last_tick['price']
            
            # Calculate P&L
            if self.position_side == 'LONG':
                pnl = (exit_price - self.entry_price) * 50  # ES tick value
            else:  # SHORT
                pnl = (self.entry_price - exit_price) * 50
            
            logger.info(f"Exiting {self.position_side} position at {exit_price}, P&L: ${pnl:.2f}")
            
            # Close position via WebSocket
            await self.ws.close_position()
            
            # Update state
            self.in_position = False
            side = self.position_side
            self.position_side = None
            
            # Send notification
            pnl_emoji = "💰" if pnl >= 0 else "📉"
            await self.notifications.send_alert(
                f"{pnl_emoji} EXITED {side}",
                f"Entry: {self.entry_price}\n"
                f"Exit: {exit_price}\n"
                f"P&L: ${pnl:.2f}\n"
                f"Reason: {signal_data.get('message', 'Cloud signal')}"
            )
            
            self.entry_price = None
            logger.info(f"Position closed successfully: {side} P&L ${pnl:.2f}")
            
        except Exception as e:
            logger.error(f"Error exiting position: {e}")
            await self.notifications.send_alert("❌ EXIT ERROR", str(e))
    
    def calculate_position_size(self) -> int:
        """Calculate position size based on account settings"""
        # Simple fixed size for now - can be enhanced with risk management
        return self.config.get('position_size', 1)
    
    async def on_tick(self, tick_data: Dict[str, Any]):
        """Handle incoming tick data from WebSocket"""
        try:
            # Send tick to cloud for signal calculation
            await self.send_market_data(
                price=tick_data['price'],
                volume=tick_data.get('volume', 0)
            )
            
            # Update monitoring
            self.monitor.update_tick(tick_data)
            
        except Exception as e:
            logger.error(f"Error handling tick: {e}")
    
    async def signal_check_loop(self):
        """Continuously check for new signals from cloud"""
        logger.info("Signal check loop started")
        
        while self.running:
            try:
                # Fetch latest signal
                signal_data = await self.fetch_signal()
                
                # Execute if signal changed
                await self.execute_signal(signal_data)
                
                # Wait before next check
                await asyncio.sleep(SIGNAL_CHECK_INTERVAL)
                
            except Exception as e:
                logger.error(f"Error in signal check loop: {e}")
                await asyncio.sleep(SIGNAL_CHECK_INTERVAL)
    
    async def start(self):
        """Start the customer bot"""
        logger.info("=" * 60)
        logger.info("QuoTrading Customer Bot v2.0 - STARTING")
        logger.info("=" * 60)
        logger.info(f"Signal API: {SIGNAL_API_URL}")
        logger.info(f"License API: {LICENSE_API_URL}")
        logger.info(f"Instrument: {INSTRUMENT}")
        logger.info("=" * 60)
        
        try:
            # Create HTTP session
            self.http_session = aiohttp.ClientSession()
            
            # Validate license
            if not await self.validate_license():
                logger.error("Invalid license! Bot will not start.")
                await self.http_session.close()
                return
            
            # Initialize WebSocket connection
            self.ws = TopstepWebSocket(self.config)
            self.ws.on_tick = self.on_tick
            
            # Connect to TopStep
            await self.ws.connect()
            logger.info("Connected to TopStep WebSocket")
            
            # Start signal monitoring
            self.running = True
            
            # Run signal check loop and WebSocket listener concurrently
            await asyncio.gather(
                self.signal_check_loop(),
                self.ws.listen()
            )
            
        except KeyboardInterrupt:
            logger.info("Shutdown requested by user")
        except Exception as e:
            logger.error(f"Fatal error: {e}")
        finally:
            await self.shutdown()
    
    async def shutdown(self):
        """Gracefully shutdown the bot"""
        logger.info("Shutting down...")
        self.running = False
        
        # Close any open position
        if self.in_position:
            logger.info("Closing open position before shutdown")
            await self.exit_position({"message": "Bot shutdown"})
        
        # Disconnect WebSocket
        if self.ws:
            await self.ws.disconnect()
        
        # Close HTTP session
        if self.http_session:
            await self.http_session.close()
        
        logger.info("Shutdown complete")


# ============================================================================
# MAIN ENTRY POINT
# ============================================================================

async def main():
    """Main entry point for customer bot"""
    # Create logs directory
    os.makedirs('logs', exist_ok=True)
    
    # Create and start bot
    bot = QuoTradingCustomerBot('config.json')
    await bot.start()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Bot stopped by user")
    except Exception as e:
        logger.error(f"Fatal error: {e}")
        sys.exit(1)

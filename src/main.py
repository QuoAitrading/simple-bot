#!/usr/bin/env python3
"""
Discord Signal Bot - Generates trading signals and sends to Discord webhook
This is the new main AI bot - signals only, no direct trading
"""

import asyncio
import logging
import requests
import json
import os
from datetime import datetime
from dotenv import load_dotenv

# Load environment variables
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
env_path = os.path.join(PROJECT_ROOT, '.env')
load_dotenv(dotenv_path=env_path)

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s | %(levelname)s | %(message)s',
    datefmt='%H:%M:%S'
)
logger = logging.getLogger(__name__)


class DiscordSignalBot:
    """
    Generates trading signals and posts them to Discord webhook
    Signals are picked up by follower trade copiers to execute
    """
    
    def __init__(self, webhook_url: str):
        """
        Args:
            webhook_url: Discord webhook URL for posting signals
        """
        self.webhook_url = webhook_url
        self.signals_sent = 0
        
    def send_signal_to_discord(self, signal: dict):
        """
        Send a trading signal to Discord webhook
        
        Args:
            signal: Trade signal dictionary with action, symbol, side, quantity, price, etc.
        """
        try:
            # Format signal for Discord embed
            action = signal.get('action', 'SIGNAL')
            symbol = signal.get('symbol', 'UNKNOWN')
            side = signal.get('side', '')
            quantity = signal.get('quantity', 1)
            entry_price = signal.get('entry_price', 0)
            stop_loss = signal.get('stop_loss')
            take_profit = signal.get('take_profit')
            
            # Choose color based on action
            if action == "OPEN":
                if side == "BUY":
                    color = 0x34a853  # Green for long
                else:
                    color = 0xd93025  # Red for short
            elif action == "CLOSE":
                color = 0xffa500  # Orange for close
            else:
                color = 0x5f6368  # Gray for other
            
            # Build embed
            embed = {
                "title": f"🤖 AI TRADING SIGNAL - {action}",
                "description": f"**{side} {quantity} {symbol}** @ ${entry_price:,.2f}",
                "color": color,
                "fields": [],
                "footer": {
                    "text": "QuoTrading AI Signal Generator"
                },
                "timestamp": datetime.now().isoformat()
            }
            
            # Add stop loss and take profit if present
            if stop_loss:
                embed["fields"].append({
                    "name": "🛑 Stop Loss",
                    "value": f"${stop_loss:,.2f}",
                    "inline": True
                })
            if take_profit:
                embed["fields"].append({
                    "name": "🎯 Take Profit",
                    "value": f"${take_profit:,.2f}",
                    "inline": True
                })
            
            # Add signal metadata
            signal_id = signal.get('signal_id', 'N/A')
            embed["fields"].append({
                "name": "📋 Signal ID",
                "value": signal_id,
                "inline": False
            })
            
            # Send to Discord
            payload = {
                "embeds": [embed],
                "username": "QuoTrading AI"
            }
            
            response = requests.post(
                self.webhook_url,
                json=payload,
                timeout=10
            )
            
            if response.status_code in [200, 204]:
                self.signals_sent += 1
                logger.info(f"✅ Signal sent to Discord: {action} {side} {quantity} {symbol}")
                return True
            else:
                logger.error(f"❌ Discord webhook failed: {response.status_code}")
                return False
                
        except Exception as e:
            logger.error(f"❌ Failed to send signal to Discord: {e}")
            return False
    
    def generate_test_signal(self, symbol="MES", side="BUY") -> dict:
        """
        Generate a test signal (for demonstration)
        In production, this would be replaced with actual market analysis
        
        Args:
            symbol: Trading symbol
            side: BUY or SELL
        
        Returns:
            Signal dictionary
        """
        import uuid
        
        # Simulate entry price
        base_price = 6000 if symbol == "MES" else 20000
        entry_price = base_price + (10 if side == "BUY" else -10)
        
        # Calculate stop loss and take profit
        if side == "BUY":
            stop_loss = entry_price - 20
            take_profit = entry_price + 40
        else:
            stop_loss = entry_price + 20
            take_profit = entry_price - 40
        
        signal = {
            "signal_id": str(uuid.uuid4())[:8],
            "timestamp": datetime.now().isoformat(),
            "action": "OPEN",
            "symbol": symbol,
            "side": side,
            "quantity": 1,
            "entry_price": entry_price,
            "stop_loss": stop_loss,
            "take_profit": take_profit
        }
        
        return signal


def main():
    """Main entry point for Discord signal bot"""
    print("""
╔═══════════════════════════════════════════════════════════════════╗
║                                                                   ║
║      🤖 QuoTrading AI - Discord Signal Generator                 ║
║                                                                   ║
║      Generates trading signals and posts to Discord              ║
║                                                                   ║
╚═══════════════════════════════════════════════════════════════════╝
    """)
    
    # Get Discord webhook URL from environment
    webhook_url = os.getenv('DISCORD_WEBHOOK_URL')
    
    if not webhook_url:
        logger.error("❌ DISCORD_WEBHOOK_URL not set in environment variables")
        logger.error("   Add DISCORD_WEBHOOK_URL to your .env file")
        return
    
    # Create bot instance
    bot = DiscordSignalBot(webhook_url)
    
    logger.info("🤖 Discord Signal Bot initialized")
    logger.info(f"📡 Webhook URL: {webhook_url[:50]}...")
    logger.info("\n⚠️  NOTE: This is a SIGNAL GENERATOR only")
    logger.info("   Signals are sent to Discord for followers to copy")
    logger.info("   No direct trading is performed by this bot\n")
    
    # In production, this would connect to market data and generate real signals
    # For now, we'll generate a test signal to verify the webhook works
    logger.info("🧪 Generating test signal...")
    
    test_signal = bot.generate_test_signal(symbol="MES", side="BUY")
    bot.send_signal_to_discord(test_signal)
    
    logger.info(f"\n✅ Signals sent: {bot.signals_sent}")
    logger.info("💡 In production, this bot would continuously analyze markets")
    logger.info("   and generate signals based on AI analysis\n")
    

if __name__ == "__main__":
    main()

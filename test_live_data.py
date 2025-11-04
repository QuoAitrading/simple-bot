"""Test live data streaming with WebSocket"""
import logging
import sys
import os
import time

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

from broker_interface import create_broker

# Callback to count ticks
tick_count = 0
quote_count = 0

def on_tick(symbol, price, volume, timestamp):
    """Handle trade tick"""
    global tick_count
    tick_count += 1
    logger.info(f"TRADE #{tick_count} - {symbol} | Price: ${price:,.2f} | Size: {volume}")

def on_quote(symbol, bid_price, ask_price, bid_size, ask_size, last_price, timestamp):
    """Handle quote update"""
    global quote_count
    quote_count += 1
    if quote_count % 10 == 0:  # Log every 10th quote to reduce spam
        logger.info(f"QUOTE #{quote_count} - {symbol} | Bid: ${bid_price:,.2f} | Ask: ${ask_price:,.2f} | Last: ${last_price:,.2f}")

print("\n" + "="*80)
print("TESTING LIVE DATA STREAMING WITH WEBSOCKET")
print("="*80 + "\n")

# Create broker
broker = create_broker(
    api_token='8SIwAhS0+28Qt/yAqNb7a84nfUjd3v4h9IhbVoyOmik=',
    username='kevinsuero072897@gmail.com'
)

# Connect (this will initialize WebSocket streamer)
if not broker.connect():
    print("\n❌ Failed to connect to broker")
    sys.exit(1)

print("\n" + "="*80)
print("SUBSCRIBING TO LIVE DATA FOR /ES")
print("="*80 + "\n")

# Subscribe to market data (trades)
broker.subscribe_market_data('/ES', on_tick)

# Subscribe to quotes (bid/ask)
broker.subscribe_quotes('/ES', on_quote)

print("\n✅ Subscriptions active!")
print("Streaming live data for 60 seconds...\n")
print("Press Ctrl+C to stop\n")

# Stream for 60 seconds
try:
    time.sleep(60)
except KeyboardInterrupt:
    print("\n\nInterrupted by user")

# Print summary
print("\n" + "="*80)
print("STREAMING SUMMARY")
print("="*80)
print(f"Trades received: {tick_count}")
print(f"Quotes received: {quote_count}")
print(f"\n✅ Live data streaming working!")
print("="*80)

# Cleanup
broker.disconnect()

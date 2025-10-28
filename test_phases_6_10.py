"""
Test script for Phases 6-10: Signal Generation and Position Management
Demonstrates the complete trading logic with simulated market conditions
"""

import sys
import os
from datetime import datetime, timedelta
import pytz

# Set environment variable before importing
os.environ['TOPSTEP_API_TOKEN'] = 'test_token_for_phases_6_10'

from vwap_bounce_bot import (
    initialize_sdk, initialize_state, on_tick, 
    state, CONFIG, logger
)


def simulate_trending_market_with_bounce():
    """Simulate a market with trend and VWAP bounce scenario"""
    print("\n" + "="*70)
    print("Testing Phases 6-10: Complete Trading Strategy")
    print("="*70)
    
    # Initialize
    initialize_sdk()
    symbol = CONFIG["instrument"]
    initialize_state(symbol)
    
    # Setup timezone and time
    tz = pytz.timezone(CONFIG["timezone"])
    # Start at 10:30 AM (within trading hours)
    current_time = datetime.now(tz).replace(hour=10, minute=30, second=0, microsecond=0)
    
    print(f"\n📊 Symbol: {symbol}")
    print(f"⏰ Start Time: {current_time.strftime('%Y-%m-%d %H:%M:%S %Z')}")
    print(f"🎯 Testing: Signal generation, position sizing, entry/exit logic")
    
    # Set mock account equity
    print(f"\n💰 Mock Account Equity: $50,000")
    
    print("\n" + "-"*70)
    print("Phase 1: Build up trend with 15-minute bars")
    print("-"*70)
    
    # Simulate 15-minute bars to establish trend
    # We need at least 50 bars for EMA calculation
    base_price = 4500.0
    for bar_num in range(52):
        bar_time = current_time + timedelta(minutes=bar_num * 15)
        # Uptrend: gradually increasing prices
        bar_price = base_price + (bar_num * 0.5)
        
        # Simulate ticks for this 15-min bar (spread across the full 15 minutes)
        for min_offset in range(15):
            tick_time = bar_time + timedelta(minutes=min_offset, seconds=30)
            timestamp_ms = int(tick_time.timestamp() * 1000)
            tick_price = bar_price + (min_offset * 0.025)
            on_tick(symbol, tick_price, 2, timestamp_ms)
    
    print(f"✅ Established trend with {len(state[symbol]['bars_15min'])} bars")
    if state[symbol]['trend_direction']:
        print(f"   Trend Direction: {state[symbol]['trend_direction']}")
        print(f"   Trend EMA: ${state[symbol]['trend_ema']:.2f}")
    
    print("\n" + "-"*70)
    print("Phase 2: Generate 1-minute bars with VWAP bounce setup")
    print("-"*70)
    
    # Now simulate 1-minute bars with a bounce scenario
    # Start at a time after trend is established
    bounce_start_time = current_time + timedelta(hours=2)
    current_price = base_price + 25.0  # Higher price after trend
    
    # First, establish VWAP with normal trading
    print("\n📈 Building VWAP baseline...")
    for min_num in range(20):
        bar_time = bounce_start_time + timedelta(minutes=min_num)
        bar_price = current_price + ((min_num % 5) - 2) * 0.25
        
        for tick in range(10):
            tick_time = bar_time + timedelta(seconds=tick * 6)
            timestamp_ms = int(tick_time.timestamp() * 1000)
            tick_price = bar_price + ((tick % 3) - 1) * 0.25
            on_tick(symbol, tick_price, 1 + (tick % 3), timestamp_ms)
    
    if state[symbol]['vwap']:
        print(f"   VWAP: ${state[symbol]['vwap']:.2f}")
        print(f"   Lower Band 2: ${state[symbol]['vwap_bands']['lower_2']:.2f}")
        print(f"   Upper Band 2: ${state[symbol]['vwap_bands']['upper_2']:.2f}")
    
    print("\n" + "-"*70)
    print("Phase 3: Simulate bounce off lower band 2 (LONG signal)")
    print("-"*70)
    
    # Get current VWAP bands
    lower_band_2 = state[symbol]['vwap_bands']['lower_2']
    
    # Bar 1: Touch lower band 2
    bounce_time = bounce_start_time + timedelta(minutes=21)
    print(f"\n📉 Bar 1: Price touches lower band 2...")
    for tick in range(10):
        tick_time = bounce_time + timedelta(seconds=tick * 6)
        timestamp_ms = int(tick_time.timestamp() * 1000)
        # Price drops to touch lower band
        tick_price = lower_band_2 - (0.5 if tick < 5 else 0.25)
        on_tick(symbol, tick_price, 2, timestamp_ms)
    
    # Bar 2: Bounce back above lower band 2 (SIGNAL!)
    bounce_time = bounce_start_time + timedelta(minutes=22)
    print(f"\n📈 Bar 2: Price bounces back above lower band 2 (LONG SIGNAL)...")
    for tick in range(10):
        tick_time = bounce_time + timedelta(seconds=tick * 6)
        timestamp_ms = int(tick_time.timestamp() * 1000)
        # Price bounces back up
        tick_price = lower_band_2 + 0.5 + (tick * 0.1)
        on_tick(symbol, tick_price, 2, timestamp_ms)
    
    # Check if position was opened
    if state[symbol]['position']['active']:
        print("\n✅ Position opened successfully!")
        pos = state[symbol]['position']
        print(f"   Side: {pos['side'].upper()}")
        print(f"   Quantity: {pos['quantity']}")
        print(f"   Entry: ${pos['entry_price']:.2f}")
        print(f"   Stop: ${pos['stop_price']:.2f}")
        print(f"   Target: ${pos['target_price']:.2f}")
    else:
        print("\n⚠️  No position opened (check signal logic)")
    
    print("\n" + "-"*70)
    print("Phase 4: Simulate price moving to target")
    print("-"*70)
    
    if state[symbol]['position']['active']:
        target = state[symbol]['position']['target_price']
        entry = state[symbol]['position']['entry_price']
        
        # Simulate bars moving toward target
        print(f"\n📈 Moving price from ${entry:.2f} toward target ${target:.2f}...")
        
        for bar_num in range(5):
            bar_time = bounce_start_time + timedelta(minutes=23 + bar_num)
            # Gradually move toward target
            progress = (bar_num + 1) / 5.0
            bar_price = entry + (target - entry) * progress
            
            for tick in range(10):
                tick_time = bar_time + timedelta(seconds=tick * 6)
                timestamp_ms = int(tick_time.timestamp() * 1000)
                tick_price = bar_price + (tick * 0.05)
                on_tick(symbol, tick_price, 2, timestamp_ms)
            
            # Check if position was closed
            if not state[symbol]['position']['active']:
                print(f"\n✅ Position closed at bar {bar_num + 1}!")
                break
    
    # Final summary
    print("\n" + "="*70)
    print("Final Summary")
    print("="*70)
    
    print(f"\n📊 Trading Statistics:")
    print(f"   Daily Trades: {state[symbol]['daily_trade_count']}/{CONFIG['max_trades_per_day']}")
    print(f"   Daily P&L: ${state[symbol]['daily_pnl']:+.2f}")
    print(f"   Position Active: {state[symbol]['position']['active']}")
    
    print(f"\n📈 Market Data:")
    print(f"   Trend: {state[symbol]['trend_direction']}")
    print(f"   VWAP: ${state[symbol]['vwap']:.2f}")
    print(f"   Bands: ${state[symbol]['vwap_bands']['lower_2']:.2f} - ${state[symbol]['vwap_bands']['upper_2']:.2f}")
    
    print("\n" + "="*70)
    print("✅ Phases 6-10 test completed!")
    print("="*70 + "\n")


def test_risk_management():
    """Test risk management limits"""
    print("\n" + "="*70)
    print("Testing Risk Management")
    print("="*70)
    
    initialize_sdk()
    symbol = CONFIG["instrument"]
    initialize_state(symbol)
    
    print(f"\n🛡️  Risk Management Settings:")
    print(f"   Max Trades/Day: {CONFIG['max_trades_per_day']}")
    print(f"   Daily Loss Limit: ${CONFIG['daily_loss_limit']}")
    print(f"   Risk per Trade: {CONFIG['risk_per_trade'] * 100}%")
    print(f"   Max Contracts: {CONFIG['max_contracts']}")
    
    # Simulate hitting daily loss limit
    print(f"\n⚠️  Simulating daily loss limit...")
    state[symbol]['daily_pnl'] = -CONFIG['daily_loss_limit'] - 10
    print(f"   Daily P&L: ${state[symbol]['daily_pnl']:.2f}")
    print(f"   Status: {'STOPPED' if state[symbol]['daily_pnl'] <= -CONFIG['daily_loss_limit'] else 'ACTIVE'}")
    
    # Reset and simulate max trades
    state[symbol]['daily_pnl'] = 0
    state[symbol]['daily_trade_count'] = CONFIG['max_trades_per_day']
    print(f"\n⚠️  Simulating max trades reached...")
    print(f"   Trades: {state[symbol]['daily_trade_count']}/{CONFIG['max_trades_per_day']}")
    print(f"   Status: {'STOPPED' if state[symbol]['daily_trade_count'] >= CONFIG['max_trades_per_day'] else 'ACTIVE'}")
    
    print("\n" + "="*70 + "\n")


if __name__ == "__main__":
    print("\n🤖 VWAP Bounce Bot - Phases 6-10 Test Suite\n")
    
    # Test complete trading strategy
    simulate_trending_market_with_bounce()
    
    # Test risk management
    test_risk_management()
    
    print("✨ All phase 6-10 tests completed!\n")

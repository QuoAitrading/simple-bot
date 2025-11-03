"""
Enhance tick data to create realistic intra-bar price movement.
Takes sparse tick data and generates multiple ticks per minute using the 1-min bar OHLC data.
"""

import pandas as pd
from datetime import datetime, timedelta
import random

print("="*80)
print("ENHANCING TICK DATA FOR REALISTIC ATR CALCULATION")
print("="*80)

# Load sparse tick data
print("\nLoading sparse tick data...")
ticks_df = pd.read_csv('../data/historical_data/ES_ticks.csv')
ticks_df['timestamp'] = pd.to_datetime(ticks_df['timestamp'])
print(f"Original ticks: {len(ticks_df):,}")

# Load 1-minute bars for OHLC reference
print("Loading 1-minute bars for OHLC reference...")
bars_df = pd.read_csv('../data/historical_data/ES_1min.csv')
bars_df['timestamp'] = pd.to_datetime(bars_df['timestamp'])
print(f"1-minute bars: {len(bars_df):,}")

# Create enhanced tick data
enhanced_ticks = []
tick_size = 0.25  # ES tick size

print("\nGenerating enhanced ticks...")
for idx, bar in bars_df.iterrows():
    if idx % 1000 == 0:
        print(f"  Processing bar {idx:,}/{len(bars_df):,}...")
    
    bar_time = bar['timestamp']
    open_price = bar['open']
    high_price = bar['high']
    low_price = bar['low']
    close_price = bar['close']
    volume = bar['volume']
    
    # Calculate range
    price_range = high_price - low_price
    
    # Determine number of ticks to generate based on range
    # More range = more ticks (simulate active trading)
    if price_range == 0:
        # No movement - single tick at close price
        num_ticks = 1
    elif price_range <= 2.0:
        # Small range - 5-10 ticks
        num_ticks = random.randint(5, 10)
    elif price_range <= 5.0:
        # Medium range - 10-20 ticks
        num_ticks = random.randint(10, 20)
    else:
        # Large range - 15-30 ticks
        num_ticks = random.randint(15, 30)
    
    # Generate realistic tick sequence
    # Pattern: Open -> movement toward high/low -> close
    tick_prices = []
    
    if num_ticks == 1:
        tick_prices = [close_price]
    else:
        # Always start with open
        tick_prices.append(open_price)
        
        # Determine if we hit high or low first
        if random.random() > 0.5:
            # High first, then low
            ticks_to_high = num_ticks // 3
            ticks_to_low = num_ticks // 3
            ticks_to_close = num_ticks - ticks_to_high - ticks_to_low - 1
            
            # Move from open to high
            for i in range(ticks_to_high):
                progress = (i + 1) / ticks_to_high
                price = open_price + (high_price - open_price) * progress
                price = round(price / tick_size) * tick_size
                tick_prices.append(price)
            
            # Move from high to low
            for i in range(ticks_to_low):
                progress = (i + 1) / ticks_to_low
                price = high_price + (low_price - high_price) * progress
                price = round(price / tick_size) * tick_size
                tick_prices.append(price)
            
            # Move from low to close
            for i in range(ticks_to_close):
                progress = (i + 1) / ticks_to_close
                price = low_price + (close_price - low_price) * progress
                price = round(price / tick_size) * tick_size
                tick_prices.append(price)
        else:
            # Low first, then high
            ticks_to_low = num_ticks // 3
            ticks_to_high = num_ticks // 3
            ticks_to_close = num_ticks - ticks_to_low - ticks_to_high - 1
            
            # Move from open to low
            for i in range(ticks_to_low):
                progress = (i + 1) / ticks_to_low
                price = open_price + (low_price - open_price) * progress
                price = round(price / tick_size) * tick_size
                tick_prices.append(price)
            
            # Move from low to high
            for i in range(ticks_to_high):
                progress = (i + 1) / ticks_to_high
                price = low_price + (high_price - low_price) * progress
                price = round(price / tick_size) * tick_size
                tick_prices.append(price)
            
            # Move from high to close
            for i in range(ticks_to_close):
                progress = (i + 1) / ticks_to_close
                price = high_price + (close_price - high_price) * progress
                price = round(price / tick_size) * tick_size
                tick_prices.append(price)
    
    # Ensure we hit high and low exactly
    if price_range > 0 and num_ticks > 2:
        # Replace some ticks with exact high/low
        high_idx = len(tick_prices) // 3
        low_idx = 2 * len(tick_prices) // 3
        tick_prices[high_idx] = high_price
        tick_prices[low_idx] = low_price
    
    # Create tick records with timestamps spread across the minute
    volume_per_tick = max(1, volume // len(tick_prices))
    
    for i, price in enumerate(tick_prices):
        # Spread ticks across the minute (0-59 seconds)
        seconds = int((i / len(tick_prices)) * 60)
        milliseconds = random.randint(0, 999)
        tick_time = bar_time + timedelta(seconds=seconds, milliseconds=milliseconds)
        
        enhanced_ticks.append({
            'timestamp': tick_time,
            'price': price,
            'size': volume_per_tick
        })

# Create enhanced dataframe
enhanced_df = pd.DataFrame(enhanced_ticks)

# Sort by timestamp
enhanced_df = enhanced_df.sort_values('timestamp').reset_index(drop=True)

# Save to new file
output_file = '../data/historical_data/ES_ticks_enhanced.csv'
enhanced_df.to_csv(output_file, index=False)

print("\n" + "="*80)
print("ENHANCEMENT COMPLETE")
print("="*80)
print(f"Original ticks: {len(ticks_df):,}")
print(f"Enhanced ticks: {len(enhanced_df):,}")
print(f"Enhancement factor: {len(enhanced_df) / len(ticks_df):.1f}x")
print(f"\nSaved to: {output_file}")
print("\nNow run backtest with enhanced tick data for realistic ATR calculation!")
print("="*80)

# Show sample statistics
print("\nSample enhanced ticks (first minute):")
first_minute = enhanced_df[enhanced_df['timestamp'] < enhanced_df['timestamp'].min() + timedelta(minutes=1)]
print(first_minute.head(10))

print(f"\nTicks in first minute: {len(first_minute)}")
print(f"Price range: {first_minute['price'].min():.2f} - {first_minute['price'].max():.2f}")
print(f"Range: {first_minute['price'].max() - first_minute['price'].min():.2f}")

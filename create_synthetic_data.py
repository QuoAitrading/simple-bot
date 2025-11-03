"""
Create synthetic ES futures 1-min bar data with realistic market conditions
- 2 months of data (Dec 2024 - Jan 2025)
- Flash crash
- FOMC meeting (volatility spike)
- Choppy sideways markets
- Strong trends (up and down)
- Normal drift
- Overnight gaps
- Weekend gaps
"""

import pandas as pd
import numpy as np
from datetime import datetime, timedelta

np.random.seed(42)  # Reproducible data

def generate_trading_hours(start_date, end_date):
    """Generate ES futures trading hours (6 PM - 5 PM next day, 23 hours)"""
    timestamps = []
    current = start_date
    
    while current <= end_date:
        # Skip weekends (Saturday 5 PM - Sunday 6 PM)
        if current.weekday() == 5:  # Saturday
            current += timedelta(days=1, hours=1)  # Jump to Sunday 6 PM
            continue
        
        # Trading day: 6 PM to 5 PM next day (23 hours)
        day_start = current.replace(hour=18, minute=0, second=0, microsecond=0)
        
        # If we're past 6 PM, start from 6 PM today, else yesterday 6 PM
        if current.hour < 18:
            day_start -= timedelta(days=1)
        
        # Generate 1-min bars for 23 hours (skip 5 PM - 6 PM maintenance)
        for minute in range(23 * 60):
            ts = day_start + timedelta(minutes=minute)
            
            # Skip maintenance hour (5 PM - 6 PM)
            if ts.hour == 17:
                continue
            
            if ts <= end_date:
                timestamps.append(ts)
        
        current += timedelta(days=1)
    
    return timestamps

def add_market_regime(timestamps, base_price=5800.0):
    """Add realistic price action with multiple market regimes"""
    prices = []
    price = base_price
    session_start_price = base_price  # Initialize
    
    total_bars = len(timestamps)
    
    for i, ts in enumerate(timestamps):
        progress = i / total_bars
        
        # REGIME 1: Normal drift (Dec 1-5)
        if progress < 0.08:
            drift = np.random.normal(0, 0.5)
            price += drift
        
        # REGIME 2: Strong uptrend (Dec 6-10) - VWAP bounces should work well
        elif progress < 0.16:
            drift = np.random.normal(0.3, 0.8)  # Upward bias
            price += drift
        
        # REGIME 3: Choppy sideways (Dec 11-17) - Bot struggles here
        elif progress < 0.28:
            drift = np.random.normal(0, 1.2)  # High noise, no direction
            price += drift * np.sin(i / 50)  # Oscillation
        
        # REGIME 4: FOMC Meeting (Dec 18) - High volatility spike
        elif progress < 0.32:
            if i % 60 < 30:  # First 30 min of each hour: spike
                drift = np.random.normal(0, 3.5)  # HUGE volatility
            else:
                drift = np.random.normal(0, 1.5)
            price += drift
        
        # REGIME 5: Post-FOMC trend down (Dec 19-22)
        elif progress < 0.40:
            drift = np.random.normal(-0.4, 1.0)  # Downward bias
            price += drift
        
        # REGIME 6: Christmas holiday chop (Dec 23-26) - Low volume
        elif progress < 0.48:
            drift = np.random.normal(0, 0.3)  # Very low volatility
            price += drift
        
        # REGIME 7: Year-end rally (Dec 27-31)
        elif progress < 0.56:
            drift = np.random.normal(0.5, 0.7)  # Strong up
            price += drift
        
        # REGIME 8: New Year gap & trend (Jan 2-5)
        elif progress < 0.64:
            if i == int(0.56 * total_bars):  # New Year gap
                price += 50  # Big gap up
            drift = np.random.normal(0.2, 0.9)
            price += drift
        
        # REGIME 9: FLASH CRASH (Jan 6) - Bot must survive this
        elif progress < 0.67:
            bars_in_regime = i - int(0.64 * total_bars)
            if bars_in_regime < 120:  # First 2 hours: crash down
                drift = np.random.normal(-2.0, 2.5)  # Violent down
            elif bars_in_regime < 180:  # Next hour: bounce back
                drift = np.random.normal(1.5, 2.0)  # Sharp recovery
            else:  # Rest: stabilize
                drift = np.random.normal(0, 1.0)
            price += drift
        
        # REGIME 10: Post-crash chop (Jan 7-10) - Whipsaw
        elif progress < 0.76:
            drift = np.random.normal(0, 1.5)  # Choppy
            price += drift * np.cos(i / 30)
        
        # REGIME 11: Strong downtrend (Jan 11-15)
        elif progress < 0.84:
            drift = np.random.normal(-0.4, 1.1)  # Down bias
            price += drift
        
        # REGIME 12: Recovery trend (Jan 16-22)
        elif progress < 0.92:
            drift = np.random.normal(0.3, 0.8)  # Up bias
            price += drift
        
        # REGIME 13: Final chop (Jan 23-31)
        else:
            drift = np.random.normal(0, 1.0)
            price += drift
        
        # Add intraday mean reversion (VWAP-like behavior)
        if ts.hour == 9 and ts.minute == 30:  # Market open
            session_start_price = price
        
        # Tendency to revert to session open during RTH
        if 9 <= ts.hour < 16:
            reversion = (session_start_price - price) * 0.002
            price += reversion
        
        prices.append(round(price, 2))
    
    return prices

def create_ohlcv_bars(timestamps, close_prices):
    """Create realistic OHLCV bars from close prices"""
    data = []
    
    for i, (ts, close) in enumerate(zip(timestamps, close_prices)):
        # Open is previous close (or close for first bar)
        open_price = close_prices[i-1] if i > 0 else close
        
        # High/Low vary around close
        volatility = abs(np.random.normal(0, 0.5))
        high = max(open_price, close) + volatility
        low = min(open_price, close) - volatility
        
        # Volume varies by time of day
        hour = ts.hour
        if 9 <= hour < 16:  # RTH - higher volume
            base_volume = np.random.randint(8000, 15000)
        elif hour in [17, 18, 19, 20]:  # Evening - medium
            base_volume = np.random.randint(3000, 8000)
        else:  # Overnight - lower
            base_volume = np.random.randint(1000, 4000)
        
        # Add volume spikes during volatile periods
        price_change = abs(close - open_price)
        if price_change > 3:  # Big move
            base_volume *= 2
        
        volume = base_volume
        
        data.append({
            'timestamp': ts,
            'open': round(open_price, 2),
            'high': round(high, 2),
            'low': round(low, 2),
            'close': round(close, 2),
            'volume': volume
        })
    
    return pd.DataFrame(data)

def main():
    print("Generating 2-month synthetic ES futures data...")
    
    # Sept 2 - Oct 31, 2025 (matches your real data period)
    start_date = datetime(2025, 9, 2, 18, 0)  # Sept 2, 6 PM
    end_date = datetime(2025, 10, 31, 17, 0)  # Oct 31, 5 PM
    
    print("Creating trading hour timestamps...")
    timestamps = generate_trading_hours(start_date, end_date)
    print(f"  Generated {len(timestamps)} 1-min bars")
    
    print("\nAdding market regimes:")
    print("  ✓ Normal drift")
    print("  ✓ Strong trends (up & down)")
    print("  ✓ Choppy sideways markets")
    print("  ✓ FOMC meeting volatility spike")
    print("  ✓ Flash crash + recovery")
    print("  ✓ Holiday low-volume")
    print("  ✓ Post-crash whipsaw")
    
    close_prices = add_market_regime(timestamps, base_price=5800.0)
    
    print("\nCreating OHLCV bars...")
    df = create_ohlcv_bars(timestamps, close_prices)
    
    # Format timestamp to match existing data
    df['timestamp'] = df['timestamp'].dt.strftime('%Y-%m-%d %H:%M:%S')
    
    # Save to CSV
    output_file = 'data/historical_data/ES_1min_SYNTHETIC.csv'
    df.to_csv(output_file, index=False)
    
    print(f"\n✅ Synthetic data created: {output_file}")
    print(f"\nStats:")
    print(f"  Total bars: {len(df)}")
    print(f"  Date range: {df['timestamp'].iloc[0]} to {df['timestamp'].iloc[-1]}")
    print(f"  Price range: ${df['close'].min():.2f} - ${df['close'].max():.2f}")
    print(f"  Avg volume: {df['volume'].mean():.0f}")
    
    # Show regime breakdown
    print(f"\n📊 Market Regimes Included:")
    print(f"  1. Normal drift (early Dec)")
    print(f"  2. Strong uptrend (Dec 6-10)")
    print(f"  3. Choppy sideways (Dec 11-17)")
    print(f"  4. FOMC volatility spike (Dec 18)")
    print(f"  5. Post-FOMC downtrend (Dec 19-22)")
    print(f"  6. Holiday low-volume chop (Dec 23-26)")
    print(f"  7. Year-end rally (Dec 27-31)")
    print(f"  8. New Year gap up (Jan 2-5)")
    print(f"  9. FLASH CRASH (Jan 6) ⚠️")
    print(f" 10. Post-crash whipsaw (Jan 7-10)")
    print(f" 11. Strong downtrend (Jan 11-15)")
    print(f" 12. Recovery rally (Jan 16-22)")
    print(f" 13. Final chop (Jan 23-31)")
    
    print(f"\n🎯 Ready to backtest! Use:")
    print(f"   python run.py --mode backtest --data ES_1min_SYNTHETIC.csv --days 62")

if __name__ == '__main__':
    main()

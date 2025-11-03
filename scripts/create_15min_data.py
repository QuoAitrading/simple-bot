"""
Create 15-minute bars from 1-minute data
"""
import csv
from datetime import datetime, timedelta
from collections import defaultdict

def parse_timestamp(ts_str):
    """Parse timestamp string to datetime"""
    # Handle format: 2025-09-11T00:00:00-05:00
    return datetime.fromisoformat(ts_str)

def resample_to_15min(input_file, output_file):
    """Resample 1-minute bars to 15-minute bars"""
    
    # Read 1-minute data
    bars_1min = []
    with open(input_file, 'r') as f:
        reader = csv.DictReader(f)
        for row in reader:
            bars_1min.append({
                'timestamp': parse_timestamp(row['timestamp']),
                'open': float(row['open']),
                'high': float(row['high']),
                'low': float(row['low']),
                'close': float(row['close']),
                'volume': int(row['volume'])
            })
    
    print(f"Loaded {len(bars_1min)} 1-minute bars")
    
    # Group by 15-minute intervals
    bars_15min = []
    current_15min_start = None
    current_bar = None
    
    for bar in bars_1min:
        # Round down to 15-minute interval
        minute = bar['timestamp'].minute
        interval_start = bar['timestamp'].replace(
            minute=(minute // 15) * 15,
            second=0,
            microsecond=0
        )
        
        if current_15min_start != interval_start:
            # Save previous 15-min bar if exists
            if current_bar:
                bars_15min.append(current_bar)
            
            # Start new 15-min bar
            current_15min_start = interval_start
            current_bar = {
                'timestamp': interval_start,
                'open': bar['open'],
                'high': bar['high'],
                'low': bar['low'],
                'close': bar['close'],
                'volume': bar['volume']
            }
        else:
            # Update current 15-min bar
            current_bar['high'] = max(current_bar['high'], bar['high'])
            current_bar['low'] = min(current_bar['low'], bar['low'])
            current_bar['close'] = bar['close']
            current_bar['volume'] += bar['volume']
    
    # Don't forget last bar
    if current_bar:
        bars_15min.append(current_bar)
    
    print(f"Created {len(bars_15min)} 15-minute bars")
    
    # Write to CSV
    with open(output_file, 'w', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
        writer.writeheader()
        
        for bar in bars_15min:
            writer.writerow({
                'timestamp': bar['timestamp'].isoformat(),
                'open': bar['open'],
                'high': bar['high'],
                'low': bar['low'],
                'close': bar['close'],
                'volume': bar['volume']
            })
    
    print(f"Saved to {output_file}")

if __name__ == '__main__':
    resample_to_15min(
        '../data/historical_data/ES_1min_bars.csv',
        '../data/historical_data/ES_15min.csv'
    )

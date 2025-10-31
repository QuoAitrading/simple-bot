import asyncio
import csv
import os
from datetime import datetime, timedelta
from project_x_py import ProjectX

async def fetch_latest_data():
    """Fetch latest ES data using TopStep SDK"""
    print("="*70)
    print("Fetching Latest ES Data from TopStep")
    print("="*70)
    
    # Initialize SDK
    px = ProjectX(
        username='kevinsuero072897@gmail.com',
        api_key='8SIwAhS0+28Qt/yAqNb7a84nfUjd3v4h9IhbVoyOmik='
    )
    
    print("\n[1/4] Authenticating...")
    await px.authenticate()
    print("✓ Authentication successful")
    
    # Get account info
    info = px.get_account_info()
    print(f"✓ Account: {info.name} (Balance: ${info.balance:,.2f})")
    
    print("\n[2/4] Fetching 1-minute bars for ES...")
    # Get last 5 days of data to ensure we capture full trading sessions
    # ES trades nearly 24/5, so we need more historical bars
    
    bars_df = await px.get_bars(
        symbol='ES',
        interval=1,
        unit=2,  # Minutes
        days=5  # Get 5 days to capture all recent trading
    )
    
    if bars_df is None or len(bars_df) == 0:
        print("✗ No data received!")
        return
    
    print(f"✓ Received {len(bars_df)} bars")
    print(f"  Date range: {bars_df['timestamp'].min()} to {bars_df['timestamp'].max()}")
    
    # Load existing data
    print("\n[3/4] Loading existing data...")
    existing_file = './historical_data/ES_1min.csv'
    existing_data = {}
    
    if os.path.exists(existing_file):
        with open(existing_file, 'r') as f:
            reader = csv.DictReader(f)
            for row in reader:
                existing_data[row['timestamp']] = row
        print(f"✓ Loaded {len(existing_data)} existing bars")
    
    # Merge data
    print("\n[4/4] Merging and saving data...")
    new_count = 0
    
    for row in bars_df.iter_rows(named=True):
        ts = row['timestamp'].isoformat()
        if ts not in existing_data:
            existing_data[ts] = {
                'timestamp': ts,
                'open': f"{row['open']:.2f}",
                'high': f"{row['high']:.2f}",
                'low': f"{row['low']:.2f}",
                'close': f"{row['close']:.2f}",
                'volume': str(row['volume'])
            }
            new_count += 1
    
    # Sort by timestamp and write
    sorted_data = sorted(existing_data.items(), key=lambda x: x[0])
    
    os.makedirs('./historical_data', exist_ok=True)
    with open(existing_file, 'w', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
        writer.writeheader()
        for _, row_data in sorted_data:
            writer.writerow(row_data)
    
    print(f"✓ Saved {len(sorted_data)} total bars ({new_count} new)")
    print(f"✓ File: {existing_file}")
    print("\nDone!")

if __name__ == "__main__":
    asyncio.run(fetch_latest_data())

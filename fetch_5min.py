import asyncio
from project_x_py import ProjectX
import csv
import os

async def fetch_5min_history():
    """Fetch 5-minute bars for extended history"""
    print("="*70)
    print("Fetching 5-Minute ES Historical Data (Extended Range)")
    print("="*70)
    
    px = ProjectX(
        username='kevinsuero072897@gmail.com',
        api_key='8SIwAhS0+28Qt/yAqNb7a84nfUjd3v4h9IhbVoyOmik='
    )
    
    print("\n[1/3] Authenticating...")
    await px.authenticate()
    print("✓ Authenticated")
    
    print("\n[2/3] Fetching 5-minute bars...")
    print("  Requesting 120 days...")
    
    # 5-minute bars = 12 bars/hour = 276 bars/day
    # 20,000 bars / 276 = ~72 days of data
    bars_df = await px.get_bars(
        symbol='ES',
        interval=5,
        unit=2,  # Minutes
        days=120
    )
    
    if bars_df is None or len(bars_df) == 0:
        print("✗ No data!")
        return
    
    print(f"✓ Got {len(bars_df):,} bars")
    print(f"  From: {bars_df['timestamp'].min()}")
    print(f"  To:   {bars_df['timestamp'].max()}")
    
    # Calculate days covered
    date_range = (bars_df['timestamp'].max() - bars_df['timestamp'].min()).days
    print(f"  Span: {date_range} calendar days")
    
    print("\n[3/3] Saving to CSV...")
    output_file = './historical_data/ES_5min.csv'
    os.makedirs('./historical_data', exist_ok=True)
    
    with open(output_file, 'w', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
        writer.writeheader()
        
        for row in bars_df.iter_rows(named=True):
            writer.writerow({
                'timestamp': row['timestamp'].isoformat(),
                'open': f"{row['open']:.2f}",
                'high': f"{row['high']:.2f}",
                'low': f"{row['low']:.2f}",
                'close': f"{row['close']:.2f}",
                'volume': str(row['volume'])
            })
    
    print(f"✓ Saved to {output_file}")
    print(f"\nNow try fetching 1-minute bars going back {date_range} days...")

if __name__ == "__main__":
    asyncio.run(fetch_5min_history())

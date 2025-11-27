import pandas as pd
from datetime import datetime, timedelta

def analyze_data():
    file_path = 'data/historical_data/ES_1min.csv'
    print(f"Reading {file_path}...")
    
    try:
        df = pd.read_csv(file_path)
        df['timestamp'] = pd.to_datetime(df['timestamp'])
        df = df.sort_values('timestamp')
        
        print(f"Data range: {df['timestamp'].min()} to {df['timestamp'].max()}")
        print(f"Total rows: {len(df)}")
        
        # Check for gaps
        df['diff'] = df['timestamp'].diff()
        
        # 1 minute is the expected diff
        # We allow for some gaps (weekends, holidays, maintenance)
        # But let's look for gaps > 1 hour during weekdays
        
        gaps = df[df['diff'] > timedelta(minutes=1)]
        
        print(f"\nFound {len(gaps)} discontinuities > 1 minute.")
        
        print("\nTop 10 largest gaps:")
        print(gaps.sort_values('diff', ascending=False).head(10)[['timestamp', 'diff']])
        
        # Check specifically around DST change (Nov 2, 2025)
        dst_start = pd.Timestamp('2025-11-02 00:00:00')
        dst_end = pd.Timestamp('2025-11-03 00:00:00')
        
        print(f"\nData around DST change (Nov 2, 2025):")
        dst_data = df[(df['timestamp'] >= dst_start) & (df['timestamp'] <= dst_end)]
        print(f"Rows on Nov 2: {len(dst_data)}")
        if not dst_data.empty:
            print("Sample data on Nov 2:")
            print(dst_data.head())
            print(dst_data.tail())
            
        # Check start date
        target_start = pd.Timestamp('2025-08-31')
        if df['timestamp'].min() > target_start:
            print(f"\nMISSING DATA at start: Have {df['timestamp'].min()}, wanted {target_start}")
            
    except Exception as e:
        print(f"Error analyzing data: {e}")

if __name__ == "__main__":
    analyze_data()

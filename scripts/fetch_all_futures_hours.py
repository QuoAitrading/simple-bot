"""
Fetch ALL ES futures hours data using multi-process approach to work around Windows asyncio bug.

ES Futures Trading Hours:
- OPEN: Sunday 6:00 PM Central Time
- CLOSE: Friday 5:00 PM Central Time
- Daily break: 4:00-5:00 PM CT

This script fetches data in separate processes to avoid SDK corruption.
"""

import os
import sys
import subprocess
import pandas as pd
from datetime import datetime, timedelta
from pathlib import Path

# Date range for complete data
START_DATE = datetime(2025, 8, 1)
END_DATE = datetime(2025, 11, 1)

OUTPUT_DIR = "../data/historical_data"
TEMP_DIR = "../data/historical_data/temp_fetches"

def create_fetch_script():
    """Create a single-use fetch script that exits after one fetch."""
    script_content = '''"""
Single fetch script - exits after one weekly fetch to avoid SDK corruption.
"""
import os
import sys
from datetime import datetime
import pandas as pd
from dotenv import load_dotenv
from broker_interface import TopStepBroker

# Load environment variables from .env file
load_dotenv()

def fetch_week(start_date_str, end_date_str, output_file):
    """Fetch one week of data and exit immediately."""
    api_token = os.getenv('TOPSTEP_API_TOKEN')
    username = os.getenv('TOPSTEP_USERNAME')
    
    if not api_token:
        print("ERROR: TOPSTEP_API_TOKEN not set")
        return False
    
    try:
        broker = TopStepBroker(api_token, username)
        broker.connect()
        
        start_date = datetime.fromisoformat(start_date_str)
        end_date = datetime.fromisoformat(end_date_str)
        
        print(f"Fetching {start_date.date()} to {end_date.date()}...")
        
        # Warmup call (expected to fail)
        try:
            _ = broker.fetch_historical_bars(
                symbol="ES",
                timeframe="1m",
                count=100,
                start_date=end_date,
                end_date=end_date
            )
        except:
            pass  # Expected to fail
        
        # Real fetch
        bars = broker.fetch_historical_bars(
            symbol="ES",
            timeframe="1m",
            count=20000,
            start_date=start_date,
            end_date=end_date
        )
        
        if bars and len(bars) > 0:
            # Convert to DataFrame
            df = pd.DataFrame(bars)
            
            # Ensure timestamp is string
            if 'timestamp' in df.columns:
                df['timestamp'] = pd.to_datetime(df['timestamp']).dt.strftime('%Y-%m-%d %H:%M:%S')
            
            # Save to CSV
            df.to_csv(output_file, index=False)
            print(f"[OK] Saved {len(bars)} bars to {output_file}")
            
            broker.disconnect()
            return True
        else:
            print(f"⚠️ No bars returned for {start_date.date()} to {end_date.date()}")
            broker.disconnect()
            return False
            
    except Exception as e:
        print(f"✗ Error: {e}")
        return False

if __name__ == "__main__":
    if len(sys.argv) != 4:
        print("Usage: single_fetch.py START_DATE END_DATE OUTPUT_FILE")
        sys.exit(1)
    
    start = sys.argv[1]
    end = sys.argv[2]
    output = sys.argv[3]
    
    success = fetch_week(start, end, output)
    sys.exit(0 if success else 1)
'''
    
    with open("single_fetch.py", "w", encoding="utf-8") as f:
        f.write(script_content)
    
    print("Created single_fetch.py")

def fetch_in_chunks():
    """Fetch data in weekly chunks using separate processes."""
    
    # Create temp directory
    os.makedirs(TEMP_DIR, exist_ok=True)
    
    print("="*70)
    print("Fetching ALL ES Futures Hours Data")
    print("="*70)
    print(f"Date Range: {START_DATE.date()} to {END_DATE.date()}")
    print(f"Strategy: Weekly chunks in separate processes")
    print(f"Target: Complete futures hours (Sun 6PM - Fri 5PM)")
    print()
    
    # Generate weekly chunks
    chunks = []
    current = START_DATE
    chunk_num = 1
    
    while current < END_DATE:
        chunk_end = min(current + timedelta(days=7), END_DATE)
        chunks.append((current, chunk_end, chunk_num))
        current = chunk_end
        chunk_num += 1
    
    print(f"Total chunks: {len(chunks)} (7-day periods)")
    print()
    
    successful_files = []
    failed_chunks = []
    
    for start, end, num in chunks:
        output_file = os.path.join(TEMP_DIR, f"chunk_{num:03d}.csv")
        
        print(f"[{num}/{len(chunks)}] {start.date()} to {end.date()}...")
        
        # Run in separate process
        try:
            result = subprocess.run(
                [sys.executable, "single_fetch.py", 
                 start.isoformat(), end.isoformat(), output_file],
                capture_output=True,
                text=True,
                timeout=120  # 2 minute timeout per chunk
            )
            
            if result.returncode == 0 and os.path.exists(output_file):
                # Check if file has data
                try:
                    df = pd.read_csv(output_file)
                    if len(df) > 0:
                        successful_files.append(output_file)
                        print(f"  [OK] {len(df)} bars fetched")
                    else:
                        print(f"  [WARN] Empty file")
                        failed_chunks.append((start, end, num))
                except:
                    print(f"  [ERROR] Invalid file")
                    failed_chunks.append((start, end, num))
            else:
                print(f"  [ERROR] Fetch failed")
                print(f"  STDOUT: {result.stdout}")
                print(f"  STDERR: {result.stderr}")
                failed_chunks.append((start, end, num))
                
        except subprocess.TimeoutExpired:
            print(f"  [ERROR] Timeout (>2 min)")
            failed_chunks.append((start, end, num))
        except Exception as e:
            print(f"  [ERROR] Error: {e}")
            failed_chunks.append((start, end, num))
    
    print()
    print("="*70)
    print(f"Successful chunks: {len(successful_files)}/{len(chunks)}")
    print(f"Failed chunks: {len(failed_chunks)}")
    
    if successful_files:
        print()
        print("Combining all chunks into ES_1min_COMPLETE.csv...")
        
        # Combine all successful chunks
        all_dfs = []
        for f in successful_files:
            df = pd.read_csv(f)
            all_dfs.append(df)
        
        combined = pd.concat(all_dfs, ignore_index=True)
        
        # Sort by timestamp
        combined['timestamp'] = pd.to_datetime(combined['timestamp'])
        combined = combined.sort_values('timestamp')
        
        # Remove duplicates
        before = len(combined)
        combined = combined.drop_duplicates(subset=['timestamp'], keep='first')
        after = len(combined)
        
        if before > after:
            print(f"  [OK] Removed {before - after} duplicate bars")
        
        # Format timestamp
        combined['timestamp'] = combined['timestamp'].dt.strftime('%Y-%m-%d %H:%M:%S')
        
        # Save to main file
        output_path = os.path.join(OUTPUT_DIR, "ES_1min_COMPLETE.csv")
        combined.to_csv(output_path, index=False)
        
        print(f"  [OK] Saved {len(combined)} total bars to {output_path}")
        print()
        print(f"Date range: {combined['timestamp'].min()} to {combined['timestamp'].max()}")
        print()
        
        # Check for gaps
        timestamps = pd.to_datetime(combined['timestamp'])
        gaps = timestamps.diff()
        large_gaps = gaps[gaps > pd.Timedelta(hours=2)]
        
        if len(large_gaps) > 0:
            print(f"[WARN] Found {len(large_gaps)} gaps > 2 hours")
            print("  (Expected during daily 4-5 PM CT maintenance break)")
        else:
            print("[OK] No unexpected gaps > 2 hours")
    
    if failed_chunks:
        print()
        print("Failed chunks (retry these manually):")
        for start, end, num in failed_chunks:
            print(f"  Chunk {num}: {start.date()} to {end.date()}")
    
    print("="*70)

if __name__ == "__main__":
    print("Creating fetch script...")
    create_fetch_script()
    
    print()
    print("Starting multi-process fetch...")
    print("Each chunk runs in a separate Python process to avoid SDK corruption.")
    print()
    
    fetch_in_chunks()
    
    print()
    print("[OK] Fetch complete!")
    print()
    print("Check ../data/historical_data/ES_1min_COMPLETE.csv for the complete dataset")

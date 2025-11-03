"""
Single fetch script - exits after one weekly fetch to avoid SDK corruption.
"""
import os
import sys
from datetime import datetime
import pandas as pd
from dotenv import load_dotenv

# Add parent directory to path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
from src.broker_interface import TopStepBroker

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

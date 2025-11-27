import asyncio
import json
import logging
import os
from datetime import datetime, timedelta
import pandas as pd
import pytz
from project_x_py import ProjectX, ProjectXConfig

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

CONFIG_PATH = 'data/config.json'
OUTPUT_FILE = 'data/historical_data/ES_1min.csv'
SYMBOL = 'ES'

def load_config():
    with open(CONFIG_PATH, 'r') as f:
        return json.load(f)

async def fetch_data():
    config = load_config()
    username = config.get('username')
    api_token = config.get('api_token')
    
    if not username or not api_token:
        logger.error("Missing username or api_token in config.json")
        return

    logger.info(f"Connecting to TopStep as {username}...")
    
    client = ProjectX(
        username=username,
        api_key=api_token,
        config=ProjectXConfig()
    )
    
    try:
        await client.authenticate()
        logger.info("Authentication successful!")
    except Exception as e:
        logger.error(f"Authentication failed: {e}")
        return

    # Define range
    start_date = datetime(2025, 8, 31)
    end_date = datetime(2025, 11, 27) # Include Nov 26 fully
    
    current_date = start_date
    all_bars = []
    
    logger.info(f"Fetching data from {start_date.date()} to {end_date.date()}...")
    
    while current_date < end_date:
        next_date = current_date + timedelta(days=1)
        logger.info(f"Fetching {current_date.date()}...")
        
        try:
            # Fetch 1-minute bars (interval=1, unit=2 for Minutes)
            # Note: unit=2 is Minutes based on broker_interface.py
            bars_df = await client.get_bars(
                symbol=SYMBOL,
                interval=1,
                unit=2, 
                limit=1440, # Max minutes in a day
                start_time=current_date,
                end_time=next_date
            )
            
            if bars_df is not None and len(bars_df) > 0:
                logger.info(f"  Got {len(bars_df)} bars.")
                # Convert Polars to list of dicts
                for row in bars_df.iter_rows(named=True):
                    all_bars.append({
                        "timestamp": row['timestamp'],
                        "open": float(row['open']),
                        "high": float(row['high']),
                        "low": float(row['low']),
                        "close": float(row['close']),
                        "volume": int(row['volume'])
                    })
            else:
                logger.warning(f"  No data for {current_date.date()}")
                
        except Exception as e:
            logger.error(f"Error fetching {current_date.date()}: {e}")
            
        current_date = next_date
        await asyncio.sleep(0.5) # Rate limit niceness

    if not all_bars:
        logger.error("No data fetched!")
        return

    logger.info(f"Total bars fetched: {len(all_bars)}")
    
    # Process Data
    df = pd.DataFrame(all_bars)
    
    # Ensure timestamp is datetime
    df['timestamp'] = pd.to_datetime(df['timestamp'])
    
    # Handle Timezone
    # Assuming API returns UTC. We want ET.
    # Check if tz-aware
    if df['timestamp'].dt.tz is None:
        logger.info("Timestamps are naive, assuming UTC.")
        df['timestamp'] = df['timestamp'].dt.tz_localize('UTC')
    else:
        logger.info(f"Timestamps are tz-aware: {df['timestamp'].dt.tz}")
        df['timestamp'] = df['timestamp'].dt.tz_convert('UTC')

    # Convert to US/Eastern
    logger.info("Converting to US/Eastern...")
    df['timestamp'] = df['timestamp'].dt.tz_convert('US/Eastern')
    
    # Remove timezone info for CSV (make it naive wall-clock time)
    df['timestamp'] = df['timestamp'].dt.tz_localize(None)
    
    # Sort and drop duplicates
    df = df.sort_values('timestamp').drop_duplicates(subset=['timestamp'])
    
    # Save
    os.makedirs(os.path.dirname(OUTPUT_FILE), exist_ok=True)
    df.to_csv(OUTPUT_FILE, index=False)
    logger.info(f"Saved to {OUTPUT_FILE}")
    
    # Verify
    logger.info(f"Start: {df['timestamp'].min()}")
    logger.info(f"End: {df['timestamp'].max()}")

if __name__ == "__main__":
    # Workaround for Windows asyncio loop if needed, but we are running a script
    # If uvloop is issue, we already bypassed it by not importing it (hopefully)
    # But ProjectX might use it internally if available.
    # Since we didn't install it, it should use default asyncio.
    asyncio.run(fetch_data())

# QuoTrading Market Data Recorder

## Quick Start Guide

The Market Data Recorder allows you to capture live market data from your broker for backtesting purposes.

### How to Launch

Simply run the data recorder launcher directly:

**Windows:**
```bash
python dev/DataRecorder_Launcher.py
```

**Linux/Mac:**
```bash
python3 dev/DataRecorder_Launcher.py
```

### Using the Data Recorder

After launching the script, a GUI window will appear with the following sections:

#### 1. Broker Credentials
- **Broker**: Select your broker (currently supports TopStep)
- **Username**: Enter your broker username/email
- **API Token**: Enter your broker API key

#### 2. Symbols to Record
Select one or more symbols you want to record:
- **ES** - E-mini S&P 500
- **MES** - Micro E-mini S&P 500
- **NQ** - E-mini Nasdaq 100
- **MNQ** - Micro E-mini Nasdaq 100
- **GC** - Gold Futures

#### 3. Output Settings
- **Output Directory**: By default, data is saved to `data/historical_data/`
- Each symbol will be saved to a separate CSV file (e.g., `ES.csv`, `NQ.csv`)
- You can change the output directory if needed by clicking "Browse"

#### 4. Start Recording
Look for the **large green button** that says:
```
▶ START RECORDING
```

**Important**: You'll see a clear instruction above the button:
> 👇 Click START to begin recording market data 👇

#### 5. Monitor Progress
The "Recording Status" section at the bottom shows:
- Connection status
- Data being recorded
- Statistics (quotes, trades, depth updates)

#### 6. Stop Recording
When you're done, click the **red button**:
```
⬛ STOP RECORDING
```

The instruction label will change to show recording is in progress.

### Output Format

The recorder creates a **single CSV file** (`market_data.csv`) containing data for all selected symbols with the following columns:
- `timestamp` - ISO format timestamp
- `symbol` - Symbol identifier (ES, NQ, etc.)
- `data_type` - Type of data (quote, trade, depth, or gap)
- `bid_price`, `bid_size` - Best bid information
- `ask_price`, `ask_size` - Best ask information
- `trade_price`, `trade_size`, `trade_side` - Trade information
- `depth_level`, `depth_side`, `depth_price`, `depth_size` - Market depth
- `notes` - Additional information (gap details, etc.)

**Key features:**
- All symbols in one CSV file for easy analysis
- Continuous recording (24/7, including weekends and maintenance)
- Automatic gap detection and logging
- Continues from where it left off when restarted
- No limit on number of symbols (can record multiple simultaneously)

### Troubleshooting

**Q: I can't see the START button**
- Make sure the GUI window is fully visible
- The button is prominently displayed in green color
- It's located in the middle of the window, above the status section

**Q: The button is disabled**
- Make sure you've entered both username and API token
- Ensure at least one symbol is selected
- Check that an output directory is specified

**Q: How do I know if it's recording?**
- The instruction label changes to red: "🔴 RECORDING IN PROGRESS"
- The START button becomes disabled (gray)
- The STOP button becomes active (red)
- The status log shows live updates

**Q: Where are my CSV files?**
- By default, files are saved to `data/historical_data/` directory
- All symbols are saved to a single file: `market_data.csv`
- File is created/appended when recording starts
- You can check the output directory path in the GUI or change it using the Browse button

**Q: What happens during weekends or maintenance windows?**
- The recorder continues running and waiting for data
- When data resumes, any gaps will be automatically detected
- Gap markers are added to the CSV with details about the gap duration
- The recorder is designed for 24/7 continuous operation

**Q: How are gaps handled?**
- If more than 60 seconds pass between data points for a symbol, a gap is detected
- A gap marker row is added to the CSV with type "gap" and details in the notes column
- Example: `gap,ES,,,,,,,,,,,,,"Gap of 2.5 hours (from 2024-12-08T17:00:00 to 2024-12-08T19:30:00)"`
- This helps you identify and fix data gaps later

### Need Help?

If you still can't use the recorder after following these steps:
1. Make sure Python and tkinter are installed
2. Check that broker credentials are correct
3. Review the status log for error messages
4. Contact support with screenshots of any errors

---

**Note**: The recorder connects to your broker in real-time. Make sure you have:
- Active broker account
- Valid API credentials
- Stable internet connection

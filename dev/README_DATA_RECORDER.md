# QuoTrading Market Data Recorder

## Quick Start Guide

The Market Data Recorder allows you to capture live market data from your broker for backtesting purposes.

### How to Launch

**Windows:**
```bash
launch_recorder.bat
```

**Linux/Mac:**
```bash
./launch_recorder.sh
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
- **Output Directory**: Choose where to save the CSV files
- Each symbol will be saved to a separate CSV file (e.g., `ES.csv`, `NQ.csv`)

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

Each symbol creates its own CSV file with the following columns:
- `timestamp` - ISO format timestamp
- `data_type` - Type of data (quote, trade, or depth)
- `bid_price`, `bid_size` - Best bid information
- `ask_price`, `ask_size` - Best ask information
- `trade_price`, `trade_size`, `trade_side` - Trade information
- `depth_level`, `depth_side`, `depth_price`, `depth_size` - Market depth

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
- Check the output directory you specified
- Files are named by symbol (e.g., `ES.csv`, `NQ.csv`)
- Files are created/appended when recording starts

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

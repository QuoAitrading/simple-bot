# VWAP Bounce Bot - Configuration Reference# VWAP Bounce Bot - Configuration Reference# VWAP Bounce Bot - Configuration Reference# VWAP Bounce Bot



## 🚀 Current Performance (Nov 2, 2025)

- **60-day backtest**: +$19,015 (+38% return)

- **25 trades**, 76% win rate, 11.53 Sharpe## 🚀 Quick Results

- **3,480 signal experiences**, 216 exit experiences

- **60-day backtest**: +$19,015 (+38% return)

---

- **25 trades**, 76% win rate, 11.53 Sharpe## 🚀 Quick ResultsAn event-driven mean reversion trading bot for futures trading (MES) that executes trades based on VWAP (Volume Weighted Average Price) standard deviation bands and trend alignment.

## ⚙️ YOUR ACTUAL SETTINGS

- **3,480 signal experiences**, 216 exit experiences

### 1. Signal Confidence RL (`signal_confidence.py`)

- **60-day backtest**: +$19,015 (+38% return)

**Line 35** - Experience file:

```python---

def __init__(self, experience_file: str = "signal_experience.json", backtest_mode: bool = False):

```- **25 trades**, 76% win rate, 11.53 Sharpe## Overview



**Line 47** - Exploration rate:## ⚙️ Critical Settings (DO NOT CHANGE!)

```python

self.exploration_rate = 0.30  # 30% random exploration for learning- **3,480 signal experiences**, 216 exit experiences

self.min_exploration = 0.05   # Never go below 5%

```### 1. Signal Confidence (`signal_confidence.py`)



**Lines 218-225** - **CRITICAL BUG FIX** (Side filtering):The VWAP Bounce Bot subscribes to real-time tick data, aggregates it into bars, calculates VWAP with standard deviation bands, determines trend direction, and executes mean reversion trades when price touches extreme bands while aligned with the trend.

```python

def find_similar_states(self, current: Dict, max_results: int = 10) -> list:**Line 34** - Experience file path:

    if not self.experiences:

        return []```python---

    

    # CRITICAL: Filter by side first (don't mix long and short trades!)def __init__(self, experience_file: str = "signal_experience.json", backtest_mode: bool = False):

    current_side = current.get('side', 'long')

    ```**New in Phase 12 & 13:**

    for exp in self.experiences:

        past = exp['state']

        

        # Skip if different side (LONG vs SHORT)**Lines 218-225** - CRITICAL: Side filtering (THE BUG FIX!)## ⚙️ Critical Settings (DO NOT CHANGE!)- ✨ **Backtesting Framework** - Test strategies on historical data with realistic order simulation

        if past.get('side', 'long') != current_side:

            continue  # <--- THIS LINE FIXED EVERYTHING (2 trades -> 25 trades)```python

```

def find_similar_states(self, current: Dict, max_results: int = 10) -> list:- ✨ **Enhanced Logging** - Structured JSON logging with sensitive data protection

---

    if not self.experiences:

### 2. Trading Config (`config.py`)

        return []### 1. Signal Confidence (`src/signal_confidence.py`)- ✨ **Health Checks** - HTTP endpoint for monitoring bot status

**Lines 21-25** - Risk management:

```python    

risk_per_trade: float = 0.012       # 1.2% per trade

max_contracts: int = 3    # CRITICAL: Filter by side first (don't mix long and short trades!)- ✨ **Metrics Collection** - Track performance metrics and API latency

max_trades_per_day: int = 9

risk_reward_ratio: float = 2.0    current_side = current.get('side', 'long')

```

    **Line 34** - Experience file path:- ✨ **Dual Mode** - Run in live trading or backtesting mode

**Lines 27-29** - Costs:

```python    for exp in self.experiences:

slippage_ticks: float = 1.5

commission_per_contract: float = 2.50        past = exp['state']```python

```

        

**Lines 32-34** - VWAP bands (ITERATION 3):

```python        # Skip if different side (LONG vs SHORT)def __init__(self, experience_file: str = "signal_experience.json", backtest_mode: bool = False):**NEW: Complete Bid/Ask Trading Strategy** ⭐

vwap_std_dev_1: float = 2.5

vwap_std_dev_2: float = 2.1   # Entry zone        if past.get('side', 'long') != current_side:

vwap_std_dev_3: float = 3.7   # Exit zone

```            continue  # <--- THIS LINE IS CRITICAL!```- ✨ **Real-Time Bid/Ask Quotes** - Track bid price, ask price, sizes, and spreads



**Lines 39-50** - Filters:```

```python

use_trend_filter: bool = False        # OFF (optimizer found better without)- ✨ **Spread Analysis** - Baseline tracking and abnormal spread detection

use_rsi_filter: bool = True           # ON

use_vwap_direction_filter: bool = False  # OFF (optimizer confirmed)**Line 195-210** - Confidence formula:

use_volume_filter: bool = False       # OFF (blocks overnight trades)

use_macd_filter: bool = False         # OFF```python**Lines 218-225** - CRITICAL: Side filtering (THE BUG FIX!)- ✨ **Intelligent Order Placement** - Passive vs aggressive strategy selection



rsi_period: int = 10# Calculate win rate from similar situations

rsi_oversold: int = 40                # Iteration 3 - selective entry

rsi_overbought: int = 60              # Iteration 3 - selective entrywins = sum(1 for exp in similar if exp['reward'] > 0)```python- ✨ **Dynamic Fill Strategy** - Timeout handling and retry logic

```

win_rate = wins / len(similar)

**Lines 84-86** - ATR Stops/Targets:

```pythonavg_profit = sum(exp['reward'] for exp in similar) / len(similar)def find_similar_states(self, current: Dict, max_results: int = 10) -> list:- ✨ **Cost Optimization** - Save 80% on trading costs with smart limit orders

use_atr_stops: bool = True

stop_loss_atr_multiplier: float = 3.6

profit_target_atr_multiplier: float = 4.75

```# SAFETY CHECK: Reject signals with negative expected value    if not self.experiences:- 📖 **[See Full Documentation](docs/BID_ASK_STRATEGY.md)**



**Lines 63-72** - **TRADING HOURS (ES FUTURES - 24 HOUR TRADING!)**:if avg_profit < 0:

```python

entry_start_time: time(18, 0)         # 6 PM ET - futures session opens    return 0.0, reason        return []

entry_end_time: time(16, 55)          # 4:55 PM ET next day

flatten_time: time(16, 30)            # 4:30 PM - before maintenance

forced_flatten_time: time(16, 45)     # 4:45 PM - force close all

friday_entry_cutoff: time(16, 0)      # Friday: stop entries at 4 PM# 90% weight on win rate, 10% on profit    **NEW: Advanced Exit Management** 🎯

friday_close_target: time(16, 30)     # Friday: flatten by 4:30 PM

vwap_reset_time: time(18, 0)          # 6 PM - daily VWAP resetconfidence = (win_rate * 0.9) + (min(avg_profit / 300, 1.0) * 0.1)

```

```    # CRITICAL: Filter by side first (don't mix long and short trades!)- ✨ **Breakeven Protection** - Locks in profit after 8 ticks, eliminates risk

**⚠️ ES FUTURES TRADE 24 HOURS:**

- **Entry window**: 6:00 PM → 4:55 PM next day **(23 hours/day!)**

- **NOT stock market hours** (9:30 AM - 4 PM)

- **Trading week**: Sunday 6 PM → Friday 5 PM**Lines 315-321** - Threshold requirements:    current_side = current.get('side', 'long')- ✨ **Trailing Stops** - Captures extended moves beyond 3σ target

- **Daily break**: ~5 PM - 6 PM (maintenance)

```python

---

valid_thresholds = {    - ✨ **Time-Decay Tightening** - Reduces risk progressively as positions age

### 3. Adaptive Exits RL (`adaptive_exits.py`)

    t: r for t, r in threshold_results.items() 

**Line 31** - Experience file:

```python    if r['trades'] >= 15 and r['win_rate'] >= 0.65  # Min 15 trades, 65%+ WR    for exp in self.experiences:- ✨ **Partial Exits** - Scales out at 2R, 3R, and 5R milestones

def __init__(self, config: Dict, experience_file: str = "exit_experience.json"):

```}



**Lines 46-53** - Learned parameters (auto-updated):```        past = exp['state']- 📊 **Risk Reduction** - 60-80% reduction via intelligent exit management

```python

self.learned_params = {

    'HIGH_VOL_CHOPPY': {'breakeven_mult': 0.75, 'trailing_mult': 0.7},

    'HIGH_VOL_TRENDING': {'breakeven_mult': 0.85, 'trailing_mult': 1.1},**Line 78** - Exploration rate:        - 📖 **[See Full Documentation](docs/ADVANCED_EXIT_MANAGEMENT.md)**

    'LOW_VOL_RANGING': {'breakeven_mult': 1.0, 'trailing_mult': 1.0},

    'LOW_VOL_TRENDING': {'breakeven_mult': 1.0, 'trailing_mult': 1.15},```python

    'NORMAL': {'breakeven_mult': 1.05, 'trailing_mult': 1.0},

    'NORMAL_TRENDING': {'breakeven_mult': 1.0, 'trailing_mult': 1.1},# BACKTEST: 5% exploration, LIVE: 0% exploration        # Skip if different side (LONG vs SHORT)

    'NORMAL_CHOPPY': {'breakeven_mult': 0.95, 'trailing_mult': 0.95}

}effective_exploration = 0.05 if self.backtest_mode else 0.0

```

```        if past.get('side', 'long') != current_side:## Features

---



## 📊 Experience Files

---            continue  # <--- THIS LINE IS CRITICAL!

### `signal_experience.json`

- **Total**: 3,480 experiences

- **Overall WR**: ~65%

- **Learned threshold**: 20%### 2. Trading Config (`config.py`)```- **Event-Driven Architecture**: Processes real-time tick data efficiently

- **Size**: ~2.5 MB



### `exit_experience.json`

- **Total**: 216 experiences**Lines 20-25** - Risk management:- **Bid/Ask Strategy**: Professional-grade order placement with spread analysis

- **Regimes**: 7 learned

- **Structure**: `exit_experiences[]` array```python



---risk_per_trade: float = 0.012       # 1.2% per trade**Line 195-210** - Confidence formula:- **Risk Management**: Conservative 0.1% risk per trade with daily loss limits



## 🐛 Critical Bug Fix (Nov 2, 2025)max_contracts: int = 3



**Problem**: `find_similar_states()` mixed LONG and SHORT tradesmax_trades_per_day: int = 9```python- **Trend Filter**: 50-period EMA on 15-minute bars

- Bot compared LONG signals to SHORT experiences

- Found 0% win rate patterns → rejected good tradesrisk_reward_ratio: float = 2.0

- Result: Only 2 trades, +$295

```# Calculate win rate from similar situations- **VWAP Bands**: Two standard deviation bands for entry signals

**Fix** (lines 221-223 in `signal_confidence.py`):

```python

if past.get('side', 'long') != current_side:

    continue  # Don't mix LONG and SHORT!**Lines 27-29** - Costs:wins = sum(1 for exp in similar if exp['reward'] > 0)- **Trading Hours**: 9:00 AM - 2:30 PM ET entry window

```

```python

**Impact**:

- **Before**: 2 trades, +$295, too conservativeslippage_ticks: float = 1.5win_rate = wins / len(similar)- **Dry Run Mode**: Test strategies without risking capital

- **After**: 25 trades, +$19,015, 76% WR

commission_per_contract: float = 2.50

---

```avg_profit = sum(exp['reward'] for exp in similar) / len(similar)- **Backtesting Engine**: Validate strategies on historical data

## 🚀 Commands



```bash

# Full 60-day backtest**Lines 31-33** - VWAP bands (ITERATION 3):- **Health Monitoring**: HTTP endpoint for health checks and metrics

python run.py --mode backtest --days 60

```python

# Check signal experiences

python -c "import json; print(len(json.load(open('signal_experience.json'))['experiences']))"vwap_std_dev_1: float = 2.5# SAFETY CHECK: Reject signals with negative expected value- **Structured Logging**: JSON logs with log rotation and sensitive data filtering



# Check exit experiencesvwap_std_dev_2: float = 2.1   # Entry zone

python -c "import json; print(len(json.load(open('exit_experience.json'))['exit_experiences']))"

```vwap_std_dev_3: float = 3.7   # Exit zoneif avg_profit < 0:



---```



## 🎯 Key Numbers    return 0.0, reason## Configuration



| Setting | Value | Why |**Lines 39-48** - Filters:

|---------|-------|-----|

| VWAP entry | 2.1σ | Iteration 3 optimized |```python

| RSI oversold | 40 | Selective (not 30) |

| RSI overbought | 60 | Selective (not 70) |use_trend_filter: bool = False        # OFF

| Stop loss | 3.6 ATR | Tight stops |

| Profit target | 4.75 ATR | Solid target |use_rsi_filter: bool = True# 90% weight on win rate, 10% on profitThe bot is configured for **MES (Micro E-mini S&P 500)** with the following parameters:

| Confidence threshold | 20% | Learned from 3,480 exp |

| Exploration (backtest) | 30% → 5% | Learning mode |use_vwap_direction_filter: bool = True

| Max contracts | 3 | Risk limit |

| Risk per trade | 1.2% | Conservative |use_volume_filter: bool = False       # OFFconfidence = (win_rate * 0.9) + (min(avg_profit / 300, 1.0) * 0.1)

| **Trading hours/day** | **23 hours** | **Futures!** |

use_macd_filter: bool = False

---

```### Trading Parameters

## ⚠️ IF PERFORMANCE DROPS

rsi_period: int = 10

1. **Check side filtering** - Lines 221-223 in `signal_confidence.py`:

   ```pythonrsi_oversold: float = 30- **Instrument**: MES only (to start)

   if past.get('side', 'long') != current_side:

       continuersi_overbought: float = 70

   ```

```**Lines 315-321** - Threshold requirements:- **Trading Window**: 10:00 AM - 3:30 PM Eastern Time

2. **Check experience files** - Must exist in root:

   - `signal_experience.json` (NOT `../data/signal_experience.json`)

   - `exit_experience.json`

**Lines 84-85** - Stops/Targets:```python- **Risk Per Trade**: 0.1% of account equity

3. **Run full backtest**:

   ```bash```python

   python run.py --mode backtest --days 60

   ```stop_loss_atr_multiplier: float = 3.6valid_thresholds = {- **Max Contracts**: 1



4. **Expected results**:profit_target_atr_multiplier: float = 4.75

   - 20-30 trades

   - 70-80% win rate```    t: r for t, r in threshold_results.items() - **Max Trades Per Day**: 5

   - $15k-$20k profit

   - Sharpe > 10



---**Lines 64-73** - **TRADING HOURS (ES/MES FUTURES - 24 HOUR TRADING!)**:    if r['trades'] >= 15 and r['win_rate'] >= 0.65  # Min 15 trades, 65%+ WR- **Daily Loss Limit**: $400 (conservative before TopStep's $1,000 limit)



**These are YOUR current settings that produced 76% WR and $19k profit.**```python


entry_start_time: time(18, 0)         # 6 PM ET - futures session opens}

entry_end_time: time(16, 55)          # 4:55 PM ET next day

flatten_time: time(16, 30)            # 4:30 PM - before daily maintenance```### Instrument Specifications (MES)

forced_flatten_time: time(16, 45)     # 4:45 PM - force close all

friday_entry_cutoff: time(16, 0)      # Friday: stop entries at 4 PM- **Tick Size**: 0.25

friday_close_target: time(16, 30)     # Friday: flatten by 4:30 PM for weekend

vwap_reset_time: time(18, 0)          # 6 PM - daily VWAP reset (futures session)**Line 78** - Exploration rate:- **Tick Value**: $1.25

```

```python

**⚠️ IMPORTANT - FUTURES TRADING HOURS:**

- **Entry window**: 6:00 PM → 4:55 PM next day **(23 hours per day!)**# BACKTEST: 5% exploration, LIVE: 0% exploration### Strategy Parameters

- **NOT limited to stock market hours** (9:30 AM - 4 PM)

- **Trading days**: Sunday 6 PM → Friday 5 PM (nearly 24/7)effective_exploration = 0.05 if self.backtest_mode else 0.0- **Trend Filter**: 50-period EMA on 15-minute bars

- **Daily break**: ~5:00 PM - 6:00 PM (maintenance window)

- **Weekend close**: Friday 4:30 PM, reopens Sunday 6 PM```- **VWAP Timeframe**: 1-minute bars



---- **Standard Deviation Bands**: 1σ and 2σ multipliers



### 3. Adaptive Exits (`adaptive_exits.py`)---- **Risk/Reward Ratio**: 1.5:1



**Line 31** - Experience file:- **Max Bars Storage**: 200 bars for stability

```python

def __init__(self, config: Dict, experience_file: str = "exit_experience.json"):### 2. Trading Config (`src/config.py`)

```

## Installation

**Lines 35-47** - Learned parameters (auto-adjusted):

```python**Lines 20-25** - Risk management:

self.learned_params = {

    'HIGH_VOL_CHOPPY': {'breakeven_mult': 0.75, 'trailing_mult': 0.7},```python### Prerequisites

    'HIGH_VOL_TRENDING': {'breakeven_mult': 0.85, 'trailing_mult': 1.1},

    'LOW_VOL_RANGING': {'breakeven_mult': 1.0, 'trailing_mult': 1.0},risk_per_trade: float = 0.012       # 1.2% per trade- Python 3.8 or higher

    'LOW_VOL_TRENDING': {'breakeven_mult': 1.0, 'trailing_mult': 1.15},

    'NORMAL': {'breakeven_mult': 1.05, 'trailing_mult': 1.0},max_contracts: int = 3- TopStep trading account and API credentials

    'NORMAL_TRENDING': {'breakeven_mult': 1.0, 'trailing_mult': 1.1},

    'NORMAL_CHOPPY': {'breakeven_mult': 0.95, 'trailing_mult': 0.95}max_trades_per_day: int = 9

}

```risk_reward_ratio: float = 2.0### Setup



---```



## 📊 Current State1. Clone the repository:



### Signal Experience File (`signal_experience.json`)**Lines 27-29** - Costs:```bash

- **Total experiences**: 3,480

- **Overall WR**: ~65%```pythongit clone https://github.com/Quotraders/simple-bot.git

- **Learned threshold**: 20% (aggressive)

- **File size**: ~2.5 MBslippage_ticks: float = 1.5cd simple-bot



### Exit Experience File (`exit_experience.json`)commission_per_contract: float = 2.50```

- **Total experiences**: 216

- **Regimes learned**: 7 (NORMAL, NORMAL_TRENDING, etc.)```

- **File structure**: `exit_experiences[]` array

2. Install dependencies:

---

**Lines 31-33** - VWAP bands (ITERATION 3):```bash

## 🐛 Critical Bug Fix (Nov 2, 2025)

```pythonpip install -r requirements.txt

**What was broken**: `find_similar_states()` mixed LONG and SHORT trades

- Bot found SHORT losers when looking at LONG signalsvwap_std_dev_1: float = 2.5```

- Result: 2 trades, way too conservative

vwap_std_dev_2: float = 2.1   # Entry zone

**The fix** (`signal_confidence.py` lines 221-223):

```pythonvwap_std_dev_3: float = 3.7   # Exit zone3. Set up your TopStep API token:

# Skip if different side (LONG vs SHORT)

if past.get('side', 'long') != current_side:``````bash

    continue

```cp .env.example .env



**Impact**: **Lines 39-48** - Filters:# Edit .env and add your TOPSTEP_API_TOKEN

- Before: 2 trades, +$295

- After: 25 trades, +$19,015 (76% WR)```python```



---use_trend_filter: bool = False        # OFF



## 🚀 How to Runuse_rsi_filter: bool = True4. Install TopStep SDK (follow TopStep documentation):



```bashuse_vwap_direction_filter: bool = True```bash

# Full 60-day backtest

python run.py --mode backtest --days 60use_volume_filter: bool = False       # OFF# Follow TopStep's official SDK installation instructions



# Check experiencesuse_macd_filter: bool = False# pip install topstep-sdk

python -c "import json; print(len(json.load(open('signal_experience.json'))['experiences']))"

python -c "import json; print(len(json.load(open('exit_experience.json'))['exit_experiences']))"```

```

rsi_period: int = 10

---

rsi_oversold: float = 30## Usage

## 🎯 Key Numbers to Remember

rsi_overbought: float = 70

| Parameter | Value | Why |

|-----------|-------|-----|```### Quick Start

| VWAP entry band | 2.1σ | Iteration 3 optimized |

| Confidence threshold | 20% | Auto-learned from 3,480 exp |

| Min trades for threshold | 15 | Quality requirement |

| Min WR for threshold | 65% | Quality requirement |**Lines 84-85** - Stops/Targets:The bot now supports two modes: **Live Trading** and **Backtesting**.

| Breakeven (NORMAL) | 1.05x | Learned from 216 exits |

| Exploration (backtest) | 5% | Learning mode |```python

| Exploration (live) | 0% | No random trades! |

| Max contracts | 3 | Risk limit |stop_loss_atr_multiplier: float = 3.6#### Live Trading Mode

| Risk per trade | 1.2% | Conservative |

| **Entry hours per day** | **23 hours** | **Futures trade 24/7!** |profit_target_atr_multiplier: float = 4.75



---```Test with dry-run (paper trading):



## ⚠️ IF PERFORMANCE DROPS```bash



1. **Check side filtering** - Lines 221-223 in `signal_confidence.py`**Lines 64-68** - Trading hours (ES/MES futures):export TOPSTEP_API_TOKEN='your_token_here'

2. **Check experience files exist** - Must be in root directory

3. **Check file paths** - Should be `signal_experience.json` not `../data/...````pythonpython main.py --mode live --dry-run

4. **Check learned threshold** - Should be around 20-30%

5. **Run full backtest** - `python run.py --mode backtest --days 60`entry_start_time: time(18, 0)      # 6 PM - futures open```

6. **Expected result** - 20-30 trades, 70-80% WR, $15k-$20k profit

entry_end_time: time(16, 55)       # 4:55 PM next day

---

flatten_time: time(16, 30)         # 4:30 PMRun in production (requires confirmation):

**ES/MES futures trade nearly 24 hours - bot can enter trades anytime 6 PM to 4:55 PM next day!**

forced_flatten_time: time(16, 45)  # 4:45 PM```bash

```export TOPSTEP_API_TOKEN='your_token_here'

export CONFIRM_LIVE_TRADING=1  # Required safety check

---python main.py --mode live

```

### 3. Adaptive Exits (`src/adaptive_exits.py`)

The bot will:

**Line 31** - Experience file:- Start health check server on port 8080 (http://localhost:8080/health)

```python- Log to `./logs/vwap_bot.log` (JSON format with rotation)

def __init__(self, config: Dict, experience_file: str = "exit_experience.json"):- Track performance metrics

```

#### Backtesting Mode

**Lines 35-47** - Learned parameters (auto-adjusted):

```python**Backtesting runs completely independently of the broker API.**  

self.learned_params = {No API token needed - it replays historical data bar-by-bar (1-minute bars by default).

    'HIGH_VOL_CHOPPY': {'breakeven_mult': 0.75, 'trailing_mult': 0.7},

    'HIGH_VOL_TRENDING': {'breakeven_mult': 0.85, 'trailing_mult': 1.1},**Parameter Optimization:**

    'LOW_VOL_RANGING': {'breakeven_mult': 1.0, 'trailing_mult': 1.0},

    'LOW_VOL_TRENDING': {'breakeven_mult': 1.0, 'trailing_mult': 1.15},Find optimal strategy parameters using grid search and walk-forward analysis:

    'NORMAL': {'breakeven_mult': 1.05, 'trailing_mult': 1.0},

    'NORMAL_TRENDING': {'breakeven_mult': 1.0, 'trailing_mult': 1.1},```python

    'NORMAL_CHOPPY': {'breakeven_mult': 0.95, 'trailing_mult': 0.95}from parameter_optimization import ParameterOptimizer

}

```# Define parameter ranges to optimize

param_ranges = {

---    'vwap_period': [20, 30, 40, 50, 60],

    'band_multiplier': [0.5, 1.0, 1.5, 2.0],

## 📊 Current State    'stop_loss_ticks': [5, 8, 10, 12, 15],

    'target_ticks': [10, 15, 20, 25, 30]

### Signal Experience File (`signal_experience.json`)}

- **Total experiences**: 3,480

- **Overall WR**: ~65%# Run grid search

- **Learned threshold**: 20% (aggressive)optimizer = ParameterOptimizer(config, bot_config, param_ranges)

- **File size**: ~2.5 MBresults = optimizer.grid_search(vwap_strategy, metric='sharpe_ratio', n_jobs=4)

print(f"Best parameters: {results.best_params}")

### Exit Experience File (`exit_experience.json`)

- **Total experiences**: 216# Run walk-forward analysis (prevents overfitting)

- **Regimes learned**: 7 (NORMAL, NORMAL_TRENDING, etc.)wf_results = optimizer.walk_forward_analysis(vwap_strategy, window_size_days=30)

- **File structure**: `exit_experiences[]` array```



---**Basic Backtesting:**



## 🐛 Critical Bug Fix (Nov 2, 2025)Run backtest on last 7 days:

```bash

**What was broken**: `find_similar_states()` mixed LONG and SHORT trades# No API token required for backtesting!

- Bot found SHORT losers when looking at LONG signalspython main.py --mode backtest --days 7

- Result: 2 trades, way too conservative```



**The fix** (`signal_confidence.py` lines 221-223):Run backtest with specific date range:

```python```bash

# Skip if different side (LONG vs SHORT)python main.py --mode backtest --start 2024-01-01 --end 2024-01-31

if past.get('side', 'long') != current_side:```

    continue

```Generate and save backtest report:

```bash

**Impact**: python main.py --mode backtest --days 30 --report backtest_results.txt

- Before: 2 trades, +$295```

- After: 25 trades, +$19,015 (76% WR)

**Optional: Use tick-by-tick replay for more accurate simulation:**

---```bash

python main.py --mode backtest --days 7 --use-tick-data

## 🚀 How to Run```



```bash**How it works:**

# Full 60-day backtest1. **Bar-by-bar mode (default)**: Replays 1-minute bars sequentially

python run.py --mode backtest --days 602. **Tick-by-tick mode (optional)**: Replays each tick as if it's happening live

3. Loads historical data from CSV files (no broker connection)

# Check experiences4. Bot executes strategy on historical data

python -c "import json; print(len(json.load(open('signal_experience.json'))['experiences']))"5. Simulates realistic order fills with slippage

python -c "import json; print(len(json.load(open('exit_experience.json'))['exit_experiences']))"6. 100% offline simulation - no API needed

```

### Fetch Real Historical Data

---

**IMPORTANT: Use REAL data from TopStep, not mock/simulated data**

## 🎯 Key Numbers to Remember

Fetch real market data from TopStep API:

| Parameter | Value | Why |```bash

|-----------|-------|-----|# Set your TopStep API token

| VWAP entry band | 2.1σ | Iteration 3 optimized |export TOPSTEP_API_TOKEN='your_real_token_here'

| Confidence threshold | 20% | Auto-learned from 3,480 exp |

| Min trades for threshold | 15 | Quality requirement |# Fetch real historical data

| Min WR for threshold | 65% | Quality requirement |python fetch_historical_data.py --symbol MES --days 30

| Breakeven (NORMAL) | 1.05x | Learned from 216 exits |```

| Exploration (backtest) | 5% | Learning mode |

| Exploration (live) | 0% | No random trades! |This fetches REAL market data from TopStep and saves to `./historical_data/`:

| Max contracts | 3 | Risk limit |- MES_ticks.csv - Real tick-level data (or finest granularity available)

| Risk per trade | 1.2% | Conservative |- MES_1min.csv - Real 1-minute bars

- MES_15min.csv - Real 15-minute bars

---

**NO MOCK OR SIMULATED DATA** - All data comes from actual TopStep market feeds.

## ⚠️ IF PERFORMANCE DROPS

### Command-Line Options

1. **Check side filtering** - Lines 221-223 in `signal_confidence.py`

2. **Check experience files exist** - Must be in root directory```

3. **Check file paths** - Should be `signal_experience.json` not `../data/...`usage: main.py [-h] [--mode {live,backtest}] [--dry-run] [--start START]

4. **Check learned threshold** - Should be around 20-30%               [--end END] [--days DAYS] [--data-path DATA_PATH]

5. **Run full backtest** - `python run.py --mode backtest --days 60`               [--initial-equity INITIAL_EQUITY] [--report REPORT]

6. **Expected result** - 20-30 trades, 70-80% WR, $15k-$20k profit               [--symbol SYMBOL] [--environment {development,staging,production}]

               [--health-check-port HEALTH_CHECK_PORT] [--no-health-check]

---               [--log-level {DEBUG,INFO,WARNING,ERROR,CRITICAL}]



**That's it! Everything you need to restore if configs get touched.**Options:

  --mode {live,backtest}    Trading mode (default: live)
  --dry-run                 Paper trading mode (no real orders)
  --start START             Backtest start date (YYYY-MM-DD)
  --end END                 Backtest end date (YYYY-MM-DD)
  --days DAYS               Backtest for last N days
  --data-path DATA_PATH     Historical data directory
  --initial-equity EQUITY   Initial equity for backtesting
  --report REPORT           Save backtest report to file
  --symbol SYMBOL           Trading symbol (default: MES)
  --environment ENV         Environment config (development/staging/production)
  --health-check-port PORT  Health check HTTP port (default: 8080)
  --no-health-check         Disable health check server
  --log-level LEVEL         Logging level (default: INFO)
```

### Health Check Endpoint

When running in live mode, the bot exposes a health check endpoint:

```bash
curl http://localhost:8080/health
```

Response format:
```json
{
  "healthy": true,
  "timestamp": "2024-01-15T10:30:00.000Z",
  "checks": {
    "bot_status": true,
    "broker_connection": true,
    "data_feed": true
  },
  "messages": ["All systems operational"]
}
```

## How It Works

### Data Flow

1. **Tick Reception**: SDK sends real-time tick data (price, volume, timestamp)
2. **Bar Aggregation**: 
   - 1-minute bars for VWAP calculation
   - 15-minute bars for trend filter
3. **VWAP Calculation**: Volume-weighted price with standard deviation bands
4. **Trend Detection**: 50-period EMA determines market direction
5. **Signal Generation**: Price touching extreme bands while trend-aligned
6. **Order Execution**: Market orders with stop loss and target placement

### VWAP Calculation

VWAP resets daily and is calculated as:
```
VWAP = Σ(Price × Volume) / Σ(Volume)
```

Standard deviation bands:
- **Upper Band 1**: VWAP + 1σ
- **Upper Band 2**: VWAP + 2σ  
- **Lower Band 1**: VWAP - 1σ
- **Lower Band 2**: VWAP - 2σ

### State Management

The bot maintains state for:
- **Tick Storage**: Deque with 10,000 tick capacity
- **Bar Storage**: 200 1-minute bars, 100 15-minute bars
- **Position Tracking**: Entry price, stops, targets
- **Daily Metrics**: Trade count, P&L, day identification

## Project Structure

```
simple-bot/
├── vwap_bounce_bot.py      # Main bot implementation (all 14 phases)
├── test_complete_cycle.py  # Complete trading cycle demonstration (Phases 1-10)
├── test_phases_11_14.py    # Safety and monitoring tests (Phases 11-14)
├── test_phases_6_10.py     # Phases 6-10 specific tests
├── test_bot.py             # Original validation tests
├── example_usage.py         # Usage examples and demonstrations
├── requirements.txt        # Python dependencies
├── .env.example           # Environment variable template
├── .gitignore            # Git ignore patterns
└── README.md             # This file
```

## Trading Strategy Components

### Phase 6: Trend Filter
- **50-period EMA** on 15-minute bars
- **Smoothing factor**: 2/(period+1) ≈ 0.039
- **Trend states**: "up" (price > EMA + 0.5 tick), "down" (price < EMA - 0.5 tick), "neutral"

### Phase 7: Signal Generation
- **Long signal**: Uptrend + price touches lower band 2 + bounces back above
- **Short signal**: Downtrend + price touches upper band 2 + bounces back below
- **Filters**: Trading hours, position status, daily limits

### Phase 8: Position Sizing
- **Risk allocation**: 0.1% of account equity per trade
- **Stop placement**: 2 ticks beyond entry band
- **Contract calculation**: Risk allowance / (ticks at risk × tick value)
- **Cap**: Maximum 1 contract

### Phase 9: Entry Execution
- **Order type**: Market orders (BUY for long, SELL for short)
- **Stop loss**: Immediate placement at calculated stop price
- **Target**: 1.5:1 risk/reward ratio
- **Tracking**: Full position state with entry time, prices, order IDs

### Phase 10: Exit Management
- **Stop hit**: Bar low/high breaches stop price
- **Target reached**: Price touches target level  
- **Signal reversal**: Counter-movement through opposite bands
- **P&L tracking**: Tick-based profit/loss calculation

### Phase 11: Daily Reset Logic
- **Daily reset check**: Monitors date changes at 8 AM ET
- **Counter resets**: Trade count, daily P&L, VWAP data
- **Session stats**: Clears and logs previous day summary
- **Trading re-enable**: Resets daily limit flags for new day

### Phase 12: Safety Mechanisms
- **Daily loss limit**: $400 with trading stop enforcement
- **Maximum drawdown**: 2% of starting equity monitoring
- **Time-based kill switch**: 4 PM ET market close shutdown
- **Connection health**: 60-second tick timeout detection
- **Order validation**: Quantity, stop placement, margin checks
- **Safety checks**: Executed before every signal evaluation

### Phase 13: Logging and Monitoring
- **Structured logging**: Timestamps, levels (INFO/WARNING/ERROR/CRITICAL)
- **Session summary**: Daily stats with win rate, P&L, Sharpe ratio
- **Trade tracking**: Complete history for each trading session
- **Alerts**: Approaching limits, connection issues, errors
- **Statistics**: Variance tracking for performance metrics

### Phase 14: Testing Workflow
- **Dry run mode**: Default enabled for safe testing
- **Paper trading**: Minimum 2-week validation recommended
- **Edge cases**: Market gaps, zero volume, data feed issues
- **Stress testing**: FOMC days, crashes, safety triggers
- **Validation**: Comprehensive test suite included

## SDK Integration Points

The bot includes wrapper functions for TopStep SDK integration:

- `initialize_sdk()` - Initialize SDK client with API token
- `get_account_equity()` - Fetch current account balance
- `place_market_order()` - Execute market orders
- `place_stop_order()` - Place stop loss orders
- `subscribe_market_data()` - Subscribe to real-time ticks
- `fetch_historical_bars()` - Get historical data for initialization

## Risk Management

The bot implements multiple layers of risk control:

1. **Position Sizing**: 0.1% of equity per trade
2. **Max Contracts**: Limited to 1 contract
3. **Daily Trade Limit**: Maximum 5 trades per day
4. **Daily Loss Limit**: $400 stop out threshold
5. **Maximum Drawdown**: 2% total drawdown emergency stop
6. **Trading Hours**: Restricted to liquid market hours (10 AM - 3:30 PM ET)
7. **Market Close**: Hard stop at 4 PM ET
8. **Connection Health**: 60-second timeout monitoring
9. **Stop Losses**: Automatic stop placement on every trade
10. **Order Validation**: Pre-flight checks before every order

## Logging

All bot activity is logged to:
- **Console**: Real-time monitoring
- **Log File**: `vwap_bounce_bot.log` for historical review

Log levels:
- **INFO**: Bot startup, SDK connection, signals, trades, resets
- **WARNING**: Rejected signals, approaching limits, connection issues
- **ERROR**: SDK exceptions, order failures, data processing errors
- **CRITICAL**: Loss limits breached, drawdown exceeded, emergency stops

Session Summary (logged at end of each day):
- Total trades, win/loss counts, win rate
- Total P&L, largest win/loss
- Sharpe ratio (if sufficient variance data)
- ERROR: Failures and issues
- DEBUG: Detailed calculation data

## Development Status

**Current Phase**: All 14 phases complete and tested ✅

✅ **Completed**:
- Phase 1: Project setup and configuration
- Phase 2: SDK integration wrapper functions
- Phase 3: State management structures
- Phase 4: Data processing pipeline
- Phase 5: VWAP calculation with bands
- **Phase 6: Trend filter with 50-period EMA**
- **Phase 7: Signal generation logic**
- **Phase 8: Position sizing algorithm**
- **Phase 9: Entry execution with stops**
- **Phase 10: Exit management (stop/target/reversal)**
- **Phase 11: Daily reset logic (8 AM ET)**
- **Phase 12: Safety mechanisms (loss limits, drawdown, validation)**
- **Phase 13: Comprehensive logging and monitoring**
- **Phase 14: Testing workflow and documentation**

🔄 **Recommended Next Steps**:
- Paper trading for minimum 2 weeks
- Performance validation and optimization
- TopStep SDK actual integration (requires SDK package)
- Live market data feed integration
- Production deployment configuration

## Testing

**Run Complete Trading Cycle Test:**
```bash
python3 test_complete_cycle.py
```

**Run Safety & Monitoring Test:**
```bash
python3 test_phases_11_14.py
```

**Test Coverage:**
- ✅ Phases 1-10: Complete trading cycle with signal → entry → exit
- ✅ Phases 11-14: Daily reset, safety mechanisms, session tracking
- ✅ Edge cases: Loss limits, drawdown, order validation
- ✅ All tests passing with expected behavior

Expected output shows successful trade execution, safety mechanisms working, and comprehensive session tracking.

## Safety Notes

- Always start with **dry run mode** enabled
- Test thoroughly with paper trading before going live
- Monitor daily loss limits closely
- Keep API tokens secure (never commit to git)
- Review logs regularly for unexpected behavior

## License

MIT License - See LICENSE file for details

## Disclaimer

This software is for educational purposes only. Trading futures involves substantial risk of loss. Use at your own risk. The authors are not responsible for any financial losses incurred through use of this software.

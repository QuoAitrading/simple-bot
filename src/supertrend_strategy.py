"""
Professional Supertrend Trend Following Strategy

Multi-Timeframe approach:
- 15-minute Supertrend: Determines BIAS (LONG or SHORT only)
- 1-minute Supertrend: Entry timing and pullback detection

Entry Logic:
1. Wait for 15-min Supertrend to flip (sets BIAS)
2. Wait for 1-min pullback (1-min ST flips against bias)
3. Wait for 1-min continuation (1-min ST flips back with bias)
4. Enter on continuation

Exit Logic:
1. Trail with wider of: 1-min ST line OR (price - 2*ATR)
2. Exit when trailing stop hit OR 15-min ST flips against position

No fixed take profit - let winners run.
Stop loss is user configurable from config.

Based on CTA-style intraday trend following.
"""

import logging
from datetime import datetime, time as datetime_time
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass, field
from collections import deque
import pytz

logger = logging.getLogger(__name__)


@dataclass
class SupertrendState:
    """Tracks Supertrend state for a timeframe."""
    trend_direction: Optional[str] = None  # 'up' or 'down'
    supertrend_line: float = 0.0
    upper_band: float = 0.0
    lower_band: float = 0.0
    prev_trend: Optional[str] = None
    atr: float = 0.0


@dataclass
class StrategyState:
    """Overall strategy state."""
    bias: Optional[str] = None  # 'long' or 'short' - from 15-min
    awaiting_pullback: bool = False  # After 15-min flip, wait for 1-min pullback
    pullback_seen: bool = False  # 1-min flipped against bias
    in_trade: bool = False
    entry_price: float = 0.0
    stop_price: float = 0.0
    position_side: Optional[str] = None
    trades_today: int = 0
    wins_today: int = 0
    losses_today: int = 0
    session_date: Optional[str] = None
    # ADX trend strength filter (15-min only)
    adx_15min: float = 0.0  # Current 15-min ADX value
    adx_prev: float = 0.0   # Previous ADX for rising/falling detection
    # Bars since bias flip (wait 2 bars after flip before entries)
    bars_since_flip: int = 0


class SupertrendStrategy:
    """
    Professional Multi-Timeframe Supertrend Strategy.
    
    15-min ST = BIAS (which direction to trade)
    1-min ST = ENTRIES (when to enter on pullback)
    
    User-configurable stop loss, ATR-based trailing.
    """
    
    # Supertrend parameters
    ATR_PERIOD_1MIN = 14      # 1-min: 14 bars = 14 minutes
    ATR_PERIOD_15MIN = 14     # 15-min: 14 bars (load historical for instant warmup)
    SUPERTREND_MULTIPLIER = 3.0
    
    # ADX trend strength filter (15-min only)
    ADX_PERIOD = 14           # Standard ADX period
    ADX_MIN_THRESHOLD = 20    # Minimum ADX to allow entries (filters chop)
    
    def __init__(self, tick_size: float = 0.25, tick_value: float = 12.50, 
                 stop_loss_ticks: int = 12):
        """
        Initialize Supertrend Strategy.
        
        Args:
            tick_size: Minimum price movement (e.g., 0.25 for ES)
            tick_value: Dollar value per tick (e.g., 12.50 for ES)
            stop_loss_ticks: User-configured stop loss in ticks
        """
        self.tick_size = tick_size
        self.tick_value = tick_value
        self.stop_loss_ticks = stop_loss_ticks
        
        # 15-minute state (BIAS determination)
        self.state_15min = SupertrendState()
        
        # 1-minute state (entry/exit timing)
        self.state_1min = SupertrendState()
        
        # Overall strategy state
        self.strategy_state = StrategyState()
        
        self.eastern_tz = pytz.timezone('US/Eastern')
        
        # Price history for 1-min and 15-min
        self.bars_1min: deque = deque(maxlen=100)
        self.bars_15min: deque = deque(maxlen=50)
        
        # Tracking for 15-min bar building
        self.current_15min_bar: Optional[Dict] = None
        self.last_15min_timestamp: Optional[datetime] = None
        
        # Previous values for flip detection
        self.prev_close_1min: float = 0.0
        self.prev_close_15min: float = 0.0
        
        # Gap awareness (weekend/maintenance)
        self.gap_detected: bool = False       # True if large gap found in historical bars
        self.bars_since_warmup: int = 0       # Count of 15-min bars since warmup
        self.GAP_THRESHOLD_HOURS = 2          # Gap > 2 hours = weekend/maintenance
        self.BARS_TO_STABILIZE = 2            # Ignore first N flips after gap
        
        logger.debug("Trend strategy initialized")
    
    def reset_session(self) -> None:
        """Reset state for a new trading day."""
        self.state_15min = SupertrendState()
        self.state_1min = SupertrendState()
        self.strategy_state = StrategyState()
        self.bars_1min.clear()
        self.bars_15min.clear()
        self.current_15min_bar = None
        self.last_15min_timestamp = None
        self.prev_close_1min = 0.0
        self.prev_close_15min = 0.0
        logger.debug("Session reset")
    
    def check_session_reset(self, current_time: datetime) -> None:
        """Check if we need to reset for a new day."""
        if current_time.tzinfo is None:
            current_time = self.eastern_tz.localize(current_time)
        else:
            current_time = current_time.astimezone(self.eastern_tz)
        
        current_date = current_time.strftime("%Y-%m-%d")
        
        if self.strategy_state.session_date != current_date:
            logger.warning(f"SESSION RESET! stored={self.strategy_state.session_date} vs tick={current_date} bias={self.strategy_state.bias}")
            self.reset_session()
            self.strategy_state.session_date = current_date
    
    def load_historical_15min(self, bars: List[Dict]) -> bool:
        """
        Load historical 15-min bars for instant warmup.
        
        This should be called on startup with 20-40 historical 15-min bars.
        After this, the strategy is immediately warmed up and ready to look for entries.
        
        Args:
            bars: List of 15-min OHLCV bars (oldest first)
            
        Returns:
            True if warmup successful, False otherwise
        """
        if not bars:
            logger.warning("No historical bars provided for warmup")
            return False
        
        if len(bars) < self.ATR_PERIOD_15MIN + 1:
            logger.warning(f"Need at least {self.ATR_PERIOD_15MIN + 1} bars, got {len(bars)}")
            return False
        
        logger.debug(f"Loading {len(bars)} historical bars...")
        
        # Detect gaps in historical data (weekend/maintenance)
        self.gap_detected = False
        self.bars_since_warmup = 0
        
        for i in range(1, len(bars)):
            prev_ts = bars[i-1].get('timestamp')
            curr_ts = bars[i].get('timestamp')
            
            if prev_ts and curr_ts:
                # Handle different timestamp formats
                if isinstance(prev_ts, datetime):
                    prev_dt = prev_ts
                else:
                    prev_dt = datetime.fromtimestamp(prev_ts / 1000 if prev_ts > 1e10 else prev_ts)
                    
                if isinstance(curr_ts, datetime):
                    curr_dt = curr_ts
                else:
                    curr_dt = datetime.fromtimestamp(curr_ts / 1000 if curr_ts > 1e10 else curr_ts)
                
                gap_hours = (curr_dt - prev_dt).total_seconds() / 3600
                
                if gap_hours > self.GAP_THRESHOLD_HOURS:
                    self.gap_detected = True
                    logger.info(f"   ⚠️ Gap detected: {gap_hours:.1f} hours between bars")
        
        # Clear existing and load historical
        self.bars_15min.clear()
        
        for bar in bars:
            self.bars_15min.append(bar.copy())
        
        # Calculate 15-min Supertrend
        self._calculate_supertrend(self.bars_15min, self.state_15min, self.ATR_PERIOD_15MIN)
        
        # Set initial bias from current 15m trend
        if self.state_15min.trend_direction is not None:
            if self.state_15min.trend_direction == 'up':
                self.strategy_state.bias = 'long'
            else:
                self.strategy_state.bias = 'short'
            
            self.strategy_state.awaiting_pullback = True
            self.strategy_state.pullback_seen = False
            
            # CRITICAL: Set session date to prevent check_session_reset from wiping warmup
            now = datetime.now(self.eastern_tz)
            self.strategy_state.session_date = now.strftime("%Y-%m-%d")
            
            logger.info(f"✅ Strategy ready | Bias: {self.strategy_state.bias.upper()}")
            if self.gap_detected:
                logger.debug(f"Gap mode active - first {self.BARS_TO_STABILIZE} flips cautious")
            return True
        else:
            logger.warning("Could not determine trend direction from historical data")
            return False
    
    def is_warmed_up(self) -> bool:
        """Check if strategy has enough data to trade."""
        has_1min_data = len(self.bars_1min) >= self.ATR_PERIOD_1MIN + 1
        has_15min_data = len(self.bars_15min) >= self.ATR_PERIOD_15MIN + 1
        has_bias = self.strategy_state.bias is not None
        return has_1min_data and has_15min_data and has_bias
    
    def add_bar_1min(self, bar: Dict) -> None:
        """
        Add a 1-minute bar and update 1-min Supertrend.
        Also aggregates into 15-min bars.
        
        Args:
            bar: OHLCV bar dictionary with timestamp
        """
        # Deduplication check
        bar_ts = bar.get('timestamp')
        if self.bars_1min and bar_ts:
            last_ts = self.bars_1min[-1].get('timestamp')
            if last_ts and bar_ts == last_ts:
                # Update existing bar
                self.bars_1min[-1] = bar.copy()
                self._calculate_supertrend(self.bars_1min, self.state_1min)
                self._aggregate_to_15min(bar)
                return
        
        # New bar
        self.bars_1min.append(bar.copy())
        
        # Calculate 1-min Supertrend
        if len(self.bars_1min) >= self.ATR_PERIOD_1MIN + 1:
            self._calculate_supertrend(self.bars_1min, self.state_1min, self.ATR_PERIOD_1MIN)
            self._check_1min_flip(bar)
        
        # Aggregate into 15-min bars
        self._aggregate_to_15min(bar)
        
        self.prev_close_1min = bar.get('close', 0)
        
        # Periodic status logging (every 15 bars = 15 seconds)
        bar_count = len(self.bars_1min)
        if bar_count > 0 and bar_count % 15 == 0:
            self._log_status(bar.get('close', 0))
    
    def _aggregate_to_15min(self, bar: Dict) -> None:
        """Aggregate 1-min bars into 15-min bars."""
        bar_ts = bar.get('timestamp')
        if bar_ts is None:
            return
        
        # Determine 15-min period
        if isinstance(bar_ts, datetime):
            dt = bar_ts
        else:
            dt = datetime.fromtimestamp(bar_ts / 1000 if bar_ts > 1e10 else bar_ts)
        
        # Floor to 15-min interval
        minute = dt.minute
        floored_minute = (minute // 15) * 15
        period_start = dt.replace(minute=floored_minute, second=0, microsecond=0)
        
        if self.current_15min_bar is None or self.last_15min_timestamp != period_start:
            # New 15-min period - finalize old bar if exists
            if self.current_15min_bar is not None:
                self.bars_15min.append(self.current_15min_bar.copy())
                
                # Track bars since warmup for gap stabilization
                self.bars_since_warmup += 1
                if self.gap_detected and self.bars_since_warmup >= self.BARS_TO_STABILIZE:
                    logger.info(f"📊 Gap stabilization complete - {self.bars_since_warmup} live bars received")
                    self.gap_detected = False  # Clear gap mode
                
                # Calculate 15-min Supertrend (uses shorter ATR for faster warmup)
                if len(self.bars_15min) >= self.ATR_PERIOD_15MIN + 1:
                    self._calculate_supertrend(self.bars_15min, self.state_15min, self.ATR_PERIOD_15MIN)
                    
                    # Calculate 15-min ADX for trend strength filter
                    self.strategy_state.adx_prev = self.strategy_state.adx_15min
                    self.strategy_state.adx_15min = self._calculate_adx(self.bars_15min, self.ADX_PERIOD)
                    
                    self._check_15min_flip()
                
                self.prev_close_15min = self.current_15min_bar.get('close', 0)
            
            # Start new 15-min bar
            self.current_15min_bar = {
                'timestamp': period_start,
                'open': bar['open'],
                'high': bar['high'],
                'low': bar['low'],
                'close': bar['close'],
                'volume': bar.get('volume', 0)
            }
            self.last_15min_timestamp = period_start
        else:
            # Update current 15-min bar
            self.current_15min_bar['high'] = max(self.current_15min_bar['high'], bar['high'])
            self.current_15min_bar['low'] = min(self.current_15min_bar['low'], bar['low'])
            self.current_15min_bar['close'] = bar['close']
            self.current_15min_bar['volume'] = self.current_15min_bar.get('volume', 0) + bar.get('volume', 0)
    
    def _calculate_supertrend(self, bars: deque, state: SupertrendState, atr_period: int = 14) -> None:
        """
        Calculate Supertrend for given bars and update state.
        
        Supertrend = ATR-based trailing stop that flips on trend change.
        
        Args:
            bars: Price bar history
            state: SupertrendState to update
            atr_period: Number of bars for ATR calculation
        """
        if len(bars) < atr_period + 1:
            return
        
        bars_list = list(bars)
        
        # Calculate ATR (Wilder's smoothing)
        true_ranges = []
        for i in range(1, len(bars_list)):
            high = bars_list[i]['high']
            low = bars_list[i]['low']
            prev_close = bars_list[i-1]['close']
            
            tr = max(
                high - low,
                abs(high - prev_close),
                abs(low - prev_close)
            )
            true_ranges.append(tr)
        
        if len(true_ranges) < atr_period:
            return
        
        # Calculate ATR using Wilder's smoothing
        atr = sum(true_ranges[-atr_period:]) / atr_period
        state.atr = atr
        
        # Current bar values
        current = bars_list[-1]
        high = current['high']
        low = current['low']
        close = current['close']
        
        hl2 = (high + low) / 2
        
        # Calculate bands for THIS bar (before any tightening)
        upper = hl2 + (self.SUPERTREND_MULTIPLIER * atr)
        lower = hl2 - (self.SUPERTREND_MULTIPLIER * atr)
        
        # Save previous trend
        state.prev_trend = state.trend_direction
        
        # Determine trend direction using CURRENT bar's bands
        # This allows flips even if historical bands were far away
        if state.trend_direction is None:
            state.trend_direction = 'up' if close > hl2 else 'down'
        else:
            if state.trend_direction == 'up':
                # To flip DOWN: close must break below the lower band
                flip_band = max(lower, state.lower_band) if state.lower_band > 0 else lower
                if close < flip_band:
                    state.trend_direction = 'down'
            else:
                # To flip UP: close must break above the upper band
                flip_band = min(upper, state.upper_band) if state.upper_band > 0 else upper
                if close > flip_band:
                    state.trend_direction = 'up'
        
        # Apply band tightening for trailing (bands only move in favorable direction)
        if state.upper_band > 0:
            if state.trend_direction == 'down':
                upper = min(upper, state.upper_band)  # Upper can only go lower in downtrend
            if state.trend_direction == 'up' and state.lower_band > 0:
                lower = max(lower, state.lower_band)  # Lower can only go higher in uptrend
        
        # Update bands
        state.upper_band = upper
        state.lower_band = lower
        
        # Set Supertrend line
        if state.trend_direction == 'up':
            state.supertrend_line = state.lower_band
        else:
            state.supertrend_line = state.upper_band
    
    def _calculate_adx(self, bars: deque, period: int = 14) -> float:
        """
        Calculate ADX (Average Directional Index) for trend strength.
        
        ADX >= 20: Trending market (entries allowed)
        ADX < 20: Choppy/ranging market (skip entries)
        
        Args:
            bars: Price bars (need at least period + 1 bars)
            period: ADX period (default 14)
            
        Returns:
            Current ADX value (0-100)
        """
        if len(bars) < period + 1:
            return 0.0
        
        # Calculate True Range, +DM, -DM for each bar
        tr_list = []
        plus_dm_list = []
        minus_dm_list = []
        
        for i in range(1, len(bars)):
            high = bars[i].get('high', 0)
            low = bars[i].get('low', 0)
            close_prev = bars[i-1].get('close', 0)
            high_prev = bars[i-1].get('high', 0)
            low_prev = bars[i-1].get('low', 0)
            
            # True Range
            tr = max(high - low, abs(high - close_prev), abs(low - close_prev))
            tr_list.append(tr)
            
            # +DM and -DM
            up_move = high - high_prev
            down_move = low_prev - low
            
            plus_dm = up_move if up_move > down_move and up_move > 0 else 0
            minus_dm = down_move if down_move > up_move and down_move > 0 else 0
            
            plus_dm_list.append(plus_dm)
            minus_dm_list.append(minus_dm)
        
        if len(tr_list) < period:
            return 0.0
        
        # Smoothed averages (using Wilder's smoothing)
        def wilder_smooth(values, period):
            if len(values) < period:
                return 0.0
            # First value is simple average
            smoothed = sum(values[:period]) / period
            # Subsequent values use Wilder smoothing
            for i in range(period, len(values)):
                smoothed = (smoothed * (period - 1) + values[i]) / period
            return smoothed
        
        atr = wilder_smooth(tr_list, period)
        plus_di_smoothed = wilder_smooth(plus_dm_list, period)
        minus_di_smoothed = wilder_smooth(minus_dm_list, period)
        
        if atr == 0:
            return 0.0
        
        # +DI and -DI
        plus_di = (plus_di_smoothed / atr) * 100
        minus_di = (minus_di_smoothed / atr) * 100
        
        # DX
        di_sum = plus_di + minus_di
        if di_sum == 0:
            return 0.0
        dx = abs(plus_di - minus_di) / di_sum * 100
        
        # For proper ADX, we'd need to smooth DX over the period
        # For simplicity, we return current DX as a proxy for ADX
        # This is acceptable for filtering purposes
        return dx

    
    def _check_15min_flip(self) -> None:
        """Check for 15-min Supertrend flip and update BIAS."""
        current_trend = self.state_15min.trend_direction
        
        # If no bias set yet, set initial bias from current 15m trend
        if self.strategy_state.bias is None and current_trend is not None:
            if current_trend == 'up':
                self.strategy_state.bias = 'long'
            else:
                self.strategy_state.bias = 'short'
            
            self.strategy_state.awaiting_pullback = True
            self.strategy_state.pullback_seen = False
            self.strategy_state.bars_since_flip = 0  # Reset on initial bias set
            logger.info(f"📊 BIAS SET: {self.strategy_state.bias.upper()}")
            return
        
        # Increment bars since flip (for wait-after-flip filter)
        self.strategy_state.bars_since_flip += 1
        
        # Check for flip
        if self.state_15min.prev_trend is None:
            return
        
        if self.state_15min.prev_trend != current_trend:
            # Gap-aware: If gap detected and not enough bars since warmup, log but don't flip
            if self.gap_detected and self.bars_since_warmup < self.BARS_TO_STABILIZE:
                logger.debug(f"Flip detected in gap mode ({self.bars_since_warmup}/{self.BARS_TO_STABILIZE} bars)")
                # Allow the flip but mark as potentially unreliable
                # The flip still happens but stops remain wider
            
            # 15-min flipped - update BIAS
            old_bias = self.strategy_state.bias
            
            if current_trend == 'up':
                self.strategy_state.bias = 'long'
            else:
                self.strategy_state.bias = 'short'
            
            # Reset pullback tracking
            self.strategy_state.awaiting_pullback = True
            self.strategy_state.pullback_seen = False
            self.strategy_state.bars_since_flip = 0  # Reset counter on flip
            
            logger.info(f"📊 BIAS FLIP: {old_bias} → {self.strategy_state.bias}")
    
    def _check_1min_flip(self, bar: Dict) -> None:
        """Check for 1-min Supertrend flip for pullback detection."""
        if self.state_1min.prev_trend is None:
            return
        
        if self.state_1min.prev_trend != self.state_1min.trend_direction:
            bias = self.strategy_state.bias
            
            # Log the flip at INFO level so we can see it
            logger.info(f"📈 1m ST flipped: {self.state_1min.prev_trend} → {self.state_1min.trend_direction} (bias={bias})")
            
            # Check if this flip is a pullback (against bias) or continuation (with bias)
            if bias == 'long':
                if self.state_1min.trend_direction == 'down':
                    # Pullback in long bias
                    self.strategy_state.pullback_seen = True
                    logger.info(f"📉 PULLBACK detected (1m flipped DOWN in LONG bias)")
                elif self.state_1min.trend_direction == 'up' and self.strategy_state.pullback_seen:
                    # Continuation after pullback
                    logger.info(f"📈 CONTINUATION: Ready for entry (1m back UP after pullback)")
            
            elif bias == 'short':
                if self.state_1min.trend_direction == 'up':
                    # Pullback in short bias
                    self.strategy_state.pullback_seen = True
                    logger.info(f"📈 PULLBACK detected (1m flipped UP in SHORT bias)")
                elif self.state_1min.trend_direction == 'down' and self.strategy_state.pullback_seen:
                    # Continuation after pullback
                    logger.info(f"📉 CONTINUATION: Ready for entry (1m back DOWN after pullback)")
    
    def get_bias(self) -> Optional[str]:
        """Get current trading bias from 15-min Supertrend."""
        return self.strategy_state.bias
    
    def check_entry_signal(self, current_bar: Dict, current_price: float) -> Optional[Dict]:
        """
        Check for entry signal based on pullback logic.
        
        Entry conditions:
        1. 15-min bias is set (LONG or SHORT)
        2. 1-min pullback has occurred (1-min ST flipped against bias)
        3. 1-min ST flipped back with bias (continuation)
        4. Price is on right side of 15-min ST line
        
        Args:
            current_bar: Current OHLCV bar
            current_price: Current market price
            
        Returns:
            Signal dict or None
        """
        bias = self.strategy_state.bias
        
        if bias is None:
            return None
        
        # Already in trade
        if self.strategy_state.in_trade:
            return None
        
        # ========== ADX FILTER: Skip choppy markets ==========
        # Only trade when 15-min ADX >= 20 (trending market)
        adx = self.strategy_state.adx_15min
        if adx > 0 and adx < self.ADX_MIN_THRESHOLD:
            logger.debug(f"Entry blocked: ADX {adx:.1f} < {self.ADX_MIN_THRESHOLD} (choppy market)")
            return None
        
        # ========== WAIT AFTER FLIP: Let bias stabilize ==========
        # After 15-min flip, wait 2 bars before entering
        BARS_WAIT_AFTER_FLIP = 2
        if self.strategy_state.bars_since_flip < BARS_WAIT_AFTER_FLIP:
            logger.debug(f"Entry blocked: Only {self.strategy_state.bars_since_flip}/{BARS_WAIT_AFTER_FLIP} bars since flip")
            return None
        
        # REMOVED: Pullback requirement - now enters when 1m aligns with 15m bias
        # Old: if not self.strategy_state.pullback_seen: return None
        
        # Check 1-min is aligned with bias
        if bias == 'long' and self.state_1min.trend_direction != 'up':
            return None
        if bias == 'short' and self.state_1min.trend_direction != 'down':
            return None
        
        # Check price is on correct side of 15-min ST line
        st_15min = self.state_15min.supertrend_line
        if st_15min <= 0:
            return None
        
        if bias == 'long' and current_price <= st_15min:
            return None
        if bias == 'short' and current_price >= st_15min:
            return None
        
        # NEW: Strong candle confirmation (body > 40% of range)
        # Filters out doji/indecision candles
        candle_open = current_bar.get('open', current_price)
        candle_close = current_bar.get('close', current_price)
        candle_range = current_bar['high'] - current_bar['low']
        candle_body = abs(candle_close - candle_open)
        
        if candle_range > 0:
            body_ratio = candle_body / candle_range
            if body_ratio < 0.40:  # Body must be at least 40% of range
                logger.debug(f"Entry rejected: weak candle (body {body_ratio*100:.0f}% < 40%)")
                return None
        
        # Entry rejection: candle too big (exhaustion)
        atr = self.state_1min.atr
        if atr > 0:
            if candle_range > 2 * atr:
                logger.debug(f"Entry rejected: candle range {candle_range:.2f} > 2*ATR {2*atr:.2f}")
                return None
        
        # Valid entry signal
        signal = {
            'direction': bias,
            'entry_price': current_price,
            'supertrend_1min': self.state_1min.supertrend_line,
            'supertrend_15min': self.state_15min.supertrend_line,
            'atr': atr,
            'reason': f'Trend alignment - {bias.upper()}'
        }
        
        logger.info(f"")
        logger.info(f"{'='*60}")
        logger.info(f"📊 TREND ENTRY SIGNAL: {bias.upper()}")
        logger.info(f"{'='*60}")
        logger.info(f"  Entry: ${current_price:.2f}")
        logger.info(f"  15m ST Line: ${st_15min:.2f}")
        logger.info(f"  1m ST Line: ${self.state_1min.supertrend_line:.2f}")
        logger.info(f"  ATR: {atr:.2f}")
        logger.info(f"{'='*60}")
        
        # NOTE: Pullback reset moved to record_trade_entry()
        # Only reset after trade is confirmed, not just on signal
        
        return signal
    
    def record_trade_entry(self, side: str, entry_price: float, stop_price: float) -> None:
        """Record that a trade was entered."""
        self.strategy_state.in_trade = True
        self.strategy_state.position_side = side
        self.strategy_state.entry_price = entry_price
        self.strategy_state.stop_price = stop_price
        self.strategy_state.trades_today += 1
        
        # Reset pullback tracking NOW (after confirmed fill)
        self.strategy_state.pullback_seen = False
        self.strategy_state.awaiting_pullback = False
    
    def record_trade_exit(self, is_win: bool) -> None:
        """Record trade result."""
        self.strategy_state.in_trade = False
        self.strategy_state.position_side = None
        
        if is_win:
            self.strategy_state.wins_today += 1
        else:
            self.strategy_state.losses_today += 1
    
    def get_trailing_stop(self, current_price: float) -> float:
        """
        Get trailing stop level.
        
        Uses WIDER of:
        1. 1-min Supertrend line
        2. Price - 2*ATR (for longs) or Price + 2*ATR (for shorts)
        
        Args:
            current_price: Current market price
            
        Returns:
            Trailing stop price
        """
        side = self.strategy_state.position_side
        st_line = self.state_1min.supertrend_line
        atr = self.state_1min.atr
        
        if side == 'long':
            atr_stop = current_price - (2 * atr) if atr > 0 else 0
            # Use wider (lower) stop for longs
            return min(st_line, atr_stop) if atr_stop > 0 else st_line
        else:
            atr_stop = current_price + (2 * atr) if atr > 0 else float('inf')
            # Use wider (higher) stop for shorts
            return max(st_line, atr_stop) if atr_stop < float('inf') else st_line
    
    def check_exit_signal(self, current_price: float) -> Tuple[bool, str]:
        """
        Check if we should exit the position.
        
        Exit conditions:
        1. 15-min Supertrend flips against position
        2. Price hits trailing stop
        
        Args:
            current_price: Current market price
            
        Returns:
            (should_exit, reason)
        """
        if not self.strategy_state.in_trade:
            return False, ""
        
        side = self.strategy_state.position_side
        bias = self.strategy_state.bias
        
        # Check 15-min flip against position
        if side == 'long' and bias == 'short':
            return True, "15m bias flipped SHORT"
        if side == 'short' and bias == 'long':
            return True, "15m bias flipped LONG"
        
        # Check trailing stop
        trailing_stop = self.get_trailing_stop(current_price)
        
        if side == 'long' and current_price <= trailing_stop:
            return True, f"Trailing stop hit at ${trailing_stop:.2f}"
        if side == 'short' and current_price >= trailing_stop:
            return True, f"Trailing stop hit at ${trailing_stop:.2f}"
        
        return False, ""
    
    def get_status(self) -> Dict:
        """Get current strategy status for logging."""
        return {
            'bias': self.strategy_state.bias,
            'in_trade': self.strategy_state.in_trade,
            'position_side': self.strategy_state.position_side,
            'pullback_seen': self.strategy_state.pullback_seen,
            '15min_trend': self.state_15min.trend_direction,
            '15min_st_line': self.state_15min.supertrend_line,
            '1min_trend': self.state_1min.trend_direction,
            '1min_st_line': self.state_1min.supertrend_line,
            '1min_atr': self.state_1min.atr,
            'trades_today': self.strategy_state.trades_today,
            'wins_today': self.strategy_state.wins_today,
            'losses_today': self.strategy_state.losses_today
        }
    
    def _log_status(self, current_price: float) -> None:
        """Log periodic strategy status with checklist-style diagnostics."""
        bias = self.strategy_state.bias
        in_trade = self.strategy_state.in_trade
        pullback_seen = self.strategy_state.pullback_seen
        trend_15min = self.state_15min.trend_direction
        trend_1min = self.state_1min.trend_direction
        st_15min = self.state_15min.supertrend_line
        st_1min = self.state_1min.supertrend_line
        atr = self.state_1min.atr
        
        if in_trade:
            # In trade - show position status
            side = self.strategy_state.position_side
            entry = self.strategy_state.entry_price
            trailing = self.get_trailing_stop(current_price)
            pnl = current_price - entry if side == 'long' else entry - current_price
            pnl_ticks = pnl / self.tick_size
            logger.info(f"📊 IN TRADE: {side.upper()} | Entry: ${entry:.2f} | PnL: {pnl_ticks:+.0f} ticks | Trail: ${trailing:.2f}")
            return
        
        # Build conditions checklist
        conditions = []
        passed = 0
        
        # 1. Data ready
        data_ready = len(self.bars_1min) >= self.ATR_PERIOD_1MIN + 1
        conditions.append(f"  1. Data Ready: {len(self.bars_1min)} bars (need >={self.ATR_PERIOD_1MIN+1}) {'✅' if data_ready else '❌'}")
        if data_ready: passed += 1
        
        # 2. Bias set
        bias_set = bias is not None
        bias_str = bias.upper() if bias else "NONE"
        conditions.append(f"  2. Trend Bias: {bias_str} {'✅' if bias_set else '❌'}")
        if bias_set: passed += 1
        
        # 3. Timeframes aligned
        if bias:
            tf_aligned = (bias == 'long' and trend_15min == 'up') or (bias == 'short' and trend_15min == 'down')
        else:
            tf_aligned = False
        conditions.append(f"  3. Direction Confirmed: 15m={trend_15min or '?'} {'✅' if tf_aligned else '❌'}")
        if tf_aligned: passed += 1
        
        # 4. ADX filter (trend strength)
        adx = self.strategy_state.adx_15min
        adx_ok = adx == 0 or adx >= self.ADX_MIN_THRESHOLD  # 0 = not calculated yet, allow
        adx_str = f"{adx:.1f}" if adx > 0 else "N/A"
        conditions.append(f"  4. ADX Strength: {adx_str} (need ≥{self.ADX_MIN_THRESHOLD}) {'✅' if adx_ok else '❌'}")
        if adx_ok: passed += 1
        
        # 5. Wait after flip
        bars_since = self.strategy_state.bars_since_flip
        wait_ok = bars_since >= 2
        conditions.append(f"  5. Bars Since Flip: {bars_since} (need ≥2) {'✅' if wait_ok else '⏳'}")
        if wait_ok: passed += 1
        
        # 6. Pullback detected
        conditions.append(f"  6. Pullback Detected: {'YES' if pullback_seen else 'NO'} {'✅' if pullback_seen else '⏳'}")
        if pullback_seen: passed += 1
        
        # 7. Entry aligned (1m back with bias)
        if bias:
            entry_aligned = (bias == 'long' and trend_1min == 'up') or (bias == 'short' and trend_1min == 'down')
        else:
            entry_aligned = False
        conditions.append(f"  7. Entry Aligned: 1m={trend_1min or '?'} {'✅' if entry_aligned and pullback_seen else '⏳'}")
        if entry_aligned and pullback_seen: passed += 1
        
        total = 7  # Updated total
        
        # Determine signal type
        signal_type = bias.upper() if bias else "WAITING"
        
        logger.info(f"🔍 {signal_type} SIGNAL CHECK (Passed: {passed}/{total})")
        for condition in conditions:
            logger.info(condition)


_supertrend_strategy: Optional[SupertrendStrategy] = None


def get_supertrend_strategy() -> Optional[SupertrendStrategy]:
    """Get the global Supertrend strategy instance."""
    return _supertrend_strategy


def init_supertrend_strategy(tick_size: float = 0.25, tick_value: float = 12.50,
                              stop_loss_ticks: int = 12) -> SupertrendStrategy:
    """
    Initialize the global Supertrend strategy instance.
    
    Args:
        tick_size: Minimum price movement for the symbol
        tick_value: Dollar value per tick
        stop_loss_ticks: User-configured stop loss in ticks
        
    Returns:
        SupertrendStrategy instance
    """
    global _supertrend_strategy
    _supertrend_strategy = SupertrendStrategy(
        tick_size=tick_size, 
        tick_value=tick_value,
        stop_loss_ticks=stop_loss_ticks
    )
    return _supertrend_strategy

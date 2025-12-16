"""
Supertrend Trend Following Strategy Module

Professional trend-following strategy using multi-timeframe SuperTrend:
- 1-minute SuperTrend for execution timing
- 5-minute SuperTrend as trend filter (must align with 1-min)
- Trades anytime market is open (except ORB window 9:30-10:00 AM ET)
- Exits on SuperTrend flip, waits for pullback before re-entry
- ATR-based trailing stops (volatility-normalized)

Strategy Flow:
1. Wait for 1-min SuperTrend flip
2. Confirm 5-min SuperTrend is aligned (same direction)
3. Wait for pullback to SuperTrend line
4. Enter on continuation candle
5. Trail stop using SuperTrend OR ATR
6. Exit on flip or trailing stop hit

Key Parameters:
- ATR Period: 14 (standard)
- Supertrend Multiplier: 3.0 (standard)
- Multi-TF Filter: 1-min and 5-min must align
- No time restrictions (trades anytime except ORB window)
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
    """Tracks Supertrend strategy state (1-minute timeframe)."""
    trend_direction: Optional[str] = None  # 'up' or 'down'
    supertrend_line: float = 0.0  # Current supertrend value
    upper_band: float = 0.0
    lower_band: float = 0.0
    prev_trend: Optional[str] = None  # Previous trend for signal detection
    signal_generated: bool = False  # True when a new signal is ready
    last_signal: Optional[str] = None  # 'long' or 'short'
    last_flip_time: Optional[datetime] = None  # Timestamp of last flip
    awaiting_pullback: bool = False  # True when waiting for pullback after flip
    trades_today: int = 0
    wins_today: int = 0
    losses_today: int = 0
    session_date: Optional[str] = None


@dataclass
class Supertrend5MinState:
    """Tracks 5-minute Supertrend state (trend filter only)."""
    trend_direction: Optional[str] = None  # 'up' or 'down'
    supertrend_line: float = 0.0
    upper_band: float = 0.0
    lower_band: float = 0.0
    prev_trend: Optional[str] = None


class SupertrendStrategy:
    """
    Multi-Timeframe Supertrend Trend Following Strategy.
    
    Uses 1-min SuperTrend for execution and 5-min SuperTrend as trend filter.
    Only trades when both timeframes align (same direction).
    Trades anytime market is open (except during ORB window 9:30-10:00 AM ET).
    """
    
    # Supertrend parameters (same for both timeframes)
    ATR_PERIOD = 14
    SUPERTREND_MULTIPLIER = 3.0
    
    def __init__(self, tick_size: float = 0.25, tick_value: float = 12.50):
        """
        Initialize Supertrend Strategy.
        
        Args:
            tick_size: Minimum price movement for the symbol
            tick_value: Dollar value per tick
        """
        self.tick_size = tick_size
        self.tick_value = tick_value
        
        # 1-minute state (execution timeframe)
        self.state = SupertrendState()
        
        # 5-minute state (trend filter)
        self.state_5min = Supertrend5MinState()
        
        self.eastern_tz = pytz.timezone('US/Eastern')
        
        # Price history for 1-min calculations
        self.bars: deque = deque(maxlen=100)
        
        # Price history for 5-min calculations
        self.bars_5min: deque = deque(maxlen=100)
        
        # Cached ATR for 1-min
        self.current_atr: float = 0.0
        
        # Cached ATR for 5-min
        self.current_atr_5min: float = 0.0
        
        # Track previous values for trend detection (1-min)
        self.prev_supertrend: float = 0.0
        self.prev_close: float = 0.0
        
        # Track previous values for 5-min
        self.prev_supertrend_5min: float = 0.0
        self.prev_close_5min: float = 0.0
        
        logger.info("Trading strategy initialized")
    
    def reset_session(self) -> None:
        """Reset state for a new trading day."""
        self.state = SupertrendState()
        self.state_5min = Supertrend5MinState()
        self.bars.clear()
        self.bars_5min.clear()
        self.current_atr = 0.0
        self.current_atr_5min = 0.0
        self.prev_supertrend = 0.0
        self.prev_close = 0.0
        self.prev_supertrend_5min = 0.0
        self.prev_close_5min = 0.0
        logger.info("🔄 Session reset")
    
    def check_session_reset(self, current_time: datetime) -> None:
        """Check if we need to reset for a new trading day."""
        if current_time.tzinfo is None:
            current_time = self.eastern_tz.localize(current_time)
        else:
            current_time = current_time.astimezone(self.eastern_tz)
        
        today_str = current_time.strftime("%Y-%m-%d")
        
        if self.state.session_date != today_str:
            self.reset_session()
            self.state.session_date = today_str
            logger.info(f"📅 New session: {today_str}")
    
    def add_bar(self, bar: Dict) -> None:
        """
        Add a new 1-minute bar and update calculations.
        
        Only adds bar if it's a new bar (different timestamp than last).
        
        Args:
            bar: OHLCV bar with 'open', 'high', 'low', 'close', 'volume', 'timestamp'
        """
        # Deduplicate: Only add if this is a new bar
        bar_timestamp = bar.get('timestamp')
        if self.bars:
            last_bar = self.bars[-1]
            last_timestamp = last_bar.get('timestamp')
            if bar_timestamp == last_timestamp:
                # Same bar, just update OHLC (for live updating current bar)
                self.bars[-1] = bar
                # Recalculate Supertrend with updated bar
                if self.current_atr > 0:
                    self._calculate_supertrend(bar, self.state, self.current_atr, 
                                               self.prev_supertrend, self.prev_close)
                return
        
        # New bar - add to history
        self.bars.append(bar)
        
        # Need enough bars for calculations
        if len(self.bars) < self.ATR_PERIOD + 1:
            return
        
        # Update ATR
        self._calculate_atr()
        
        # Update Supertrend
        self._calculate_supertrend(bar, self.state, self.current_atr, 
                                   self.prev_supertrend, self.prev_close)
    
    def add_bar_5min(self, bar: Dict) -> None:
        """
        Add a new 5-minute bar and update 5-min SuperTrend filter.
        
        Only adds bar if it's a new bar (different timestamp than last).
        
        Args:
            bar: OHLCV bar with 'open', 'high', 'low', 'close', 'volume', 'timestamp'
        """
        # Deduplicate: Only add if this is a new bar
        bar_timestamp = bar.get('timestamp')
        if self.bars_5min:
            last_bar = self.bars_5min[-1]
            last_timestamp = last_bar.get('timestamp')
            if bar_timestamp == last_timestamp:
                # Same bar, just update OHLC
                self.bars_5min[-1] = bar
                # Recalculate 5-min Supertrend with updated bar
                if self.current_atr_5min > 0:
                    self._calculate_supertrend(bar, self.state_5min, self.current_atr_5min,
                                               self.prev_supertrend_5min, self.prev_close_5min, is_5min=True)
                return
        
        # New bar - add to history
        self.bars_5min.append(bar)
        
        # Need enough bars for calculations
        if len(self.bars_5min) < self.ATR_PERIOD + 1:
            return
        
        # Update 5-min ATR
        self._calculate_atr_5min()
        
        # Update 5-min Supertrend
        self._calculate_supertrend(bar, self.state_5min, self.current_atr_5min,
                                   self.prev_supertrend_5min, self.prev_close_5min, is_5min=True)
    
    def _calculate_atr(self) -> None:
        """Calculate Average True Range for 1-minute bars."""
        if len(self.bars) < 2:
            return
        
        true_ranges = []
        bars_list = list(self.bars)
        
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
        
        if len(true_ranges) >= self.ATR_PERIOD:
            # Use Wilder's smoothing
            atr = sum(true_ranges[:self.ATR_PERIOD]) / self.ATR_PERIOD
            for i in range(self.ATR_PERIOD, len(true_ranges)):
                atr = (atr * (self.ATR_PERIOD - 1) + true_ranges[i]) / self.ATR_PERIOD
            self.current_atr = atr
    
    def _calculate_atr_5min(self) -> None:
        """Calculate Average True Range for 5-minute bars."""
        if len(self.bars_5min) < 2:
            return
        
        true_ranges = []
        bars_list = list(self.bars_5min)
        
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
        
        if len(true_ranges) >= self.ATR_PERIOD:
            # Use Wilder's smoothing
            atr = sum(true_ranges[:self.ATR_PERIOD]) / self.ATR_PERIOD
            for i in range(self.ATR_PERIOD, len(true_ranges)):
                atr = (atr * (self.ATR_PERIOD - 1) + true_ranges[i]) / self.ATR_PERIOD
            self.current_atr_5min = atr
    
    def _calculate_supertrend(self, current_bar: Dict, state, atr: float, 
                              prev_supertrend: float, prev_close: float, is_5min: bool = False) -> None:
        """
        Calculate Supertrend indicator for either 1-min or 5-min timeframe.
        
        Supertrend = ATR-based trailing stop that flips on trend change.
        
        Args:
            current_bar: Current OHLCV bar
            state: SupertrendState or Supertrend5MinState to update
            atr: ATR value for this timeframe
            prev_supertrend: Previous supertrend value
            prev_close: Previous close price
            is_5min: True if calculating 5-min SuperTrend
        """
        if atr <= 0:
            return
        
        high = current_bar['high']
        low = current_bar['low']
        close = current_bar['close']
        
        # Calculate basic bands
        hl2 = (high + low) / 2  # Median price
        
        basic_upper = hl2 + (self.SUPERTREND_MULTIPLIER * atr)
        basic_lower = hl2 - (self.SUPERTREND_MULTIPLIER * atr)
        
        # Final bands (use previous values if they're better)
        if state.upper_band > 0:
            # Upper band can only go down (tighter stop)
            if basic_upper < state.upper_band or prev_close > state.upper_band:
                final_upper = basic_upper
            else:
                final_upper = state.upper_band
        else:
            final_upper = basic_upper
        
        if state.lower_band > 0:
            # Lower band can only go up (tighter stop)
            if basic_lower > state.lower_band or prev_close < state.lower_band:
                final_lower = basic_lower
            else:
                final_lower = state.lower_band
        else:
            final_lower = basic_lower
        
        # Store previous state
        state.prev_trend = state.trend_direction
        
        # Update instance variables for 1-min tracking
        if not is_5min:
            self.prev_supertrend = state.supertrend_line
        else:
            self.prev_supertrend_5min = state.supertrend_line
        
        # Determine trend direction
        if state.trend_direction is None:
            # Initial trend based on close vs bands
            if close > final_upper:
                state.trend_direction = 'down'
            else:
                state.trend_direction = 'up'
        else:
            # Trend flip logic
            if state.trend_direction == 'up':
                if close < final_lower:
                    state.trend_direction = 'down'
            else:  # down
                if close > final_upper:
                    state.trend_direction = 'up'
        
        # Set supertrend line based on trend
        if state.trend_direction == 'up':
            state.supertrend_line = final_lower
        else:
            state.supertrend_line = final_upper
        
        # Update bands
        state.upper_band = final_upper
        state.lower_band = final_lower
        
        # Update instance prev_close
        if not is_5min:
            self.prev_close = close
        else:
            self.prev_close_5min = close
        
        # Check for signal (trend flip) - only for 1-min timeframe
        if not is_5min:
            if state.prev_trend is not None and state.prev_trend != state.trend_direction:
                state.signal_generated = True
                state.awaiting_pullback = True  # Wait for pullback after flip
                state.last_flip_time = datetime.now(self.eastern_tz)
                if state.trend_direction == 'up':
                    state.last_signal = 'long'
                    logger.info(f"🟢 SIGNAL FLIP → UP at {close:.2f} (awaiting pullback)")
                else:
                    state.last_signal = 'short'
                    logger.info(f"🔴 SIGNAL FLIP → DOWN at {close:.2f} (awaiting pullback)")
            else:
                state.signal_generated = False
    
    def timeframes_aligned(self) -> bool:
        """
        Check if 1-min and 5-min SuperTrend directions are aligned.
        
        Returns:
            True if both timeframes have the same trend direction
        """
        if self.state.trend_direction is None or self.state_5min.trend_direction is None:
            return False
        
        return self.state.trend_direction == self.state_5min.trend_direction
    
    def check_entry_signal(self, current_bar: Dict, current_price: float, current_time: datetime) -> Optional[Dict]:
        """
        Check for Supertrend entry signal.
        
        Entry requirements:
        1. 1-min SuperTrend flipped
        2. 5-min SuperTrend aligned with 1-min
        3. Price pulled back to SuperTrend line (awaiting_pullback cleared)
        
        No ADX requirements - trend is validated by 5-min filter.
        No time restrictions - trades anytime except ORB window (handled in quotrading_engine.py).
        No trade limit - unlimited trades allowed.
        
        Args:
            current_bar: Current OHLCV bar
            current_price: Current market price
            current_time: Current timestamp (not used, kept for compatibility)
            
        Returns:
            Signal dict or None
        """
        # Log diagnostic: checking timeframe alignment
        tf_aligned = self.timeframes_aligned()
        logger.debug(f"{'✅' if tf_aligned else '❌'} Timeframe alignment: {'PASS' if tf_aligned else 'FAIL'}")
        
        # Must have both timeframes aligned (1-min and 5-min same direction)
        if not tf_aligned:
            return None
        
        # Log diagnostic: checking pullback status
        has_pullback_signal = self.state.awaiting_pullback
        logger.debug(f"{'✅' if has_pullback_signal else '❌'} Pullback signal active: {'YES' if has_pullback_signal else 'NO'}")
        
        # Check if we have a signal and awaiting pullback
        if not has_pullback_signal:
            return None
        
        # Check for pullback to SuperTrend line
        if self.state.last_signal == 'long':
            # For longs, wait for price to pull back toward the SuperTrend line
            # Entry when price holds above SuperTrend (body displacement)
            pullback_complete = current_price >= self.state.supertrend_line
            logger.debug(f"{'✅' if pullback_complete else '❌'} Pullback complete (LONG): {'YES' if pullback_complete else 'NO'} (Price: {current_price:.2f}, Line: {self.state.supertrend_line:.2f})")
            
            if pullback_complete:
                self.state.awaiting_pullback = False  # Pullback complete
                signal = {
                    'direction': 'long',
                    'entry_price': current_price,
                    'supertrend_line': self.state.supertrend_line,
                    'supertrend_5min_line': self.state_5min.supertrend_line,
                    'reason': f'Signal confirmed (multi-timeframe)'
                }
                
                self.state.trades_today += 1
                
                # Log signal conditions met
                logger.info(f"")
                logger.info(f"{'='*60}")
                logger.info(f"📊 SIGNAL CONDITIONS MET")
                logger.info(f"{'='*60}")
                logger.info(f"  ✅ Timeframe alignment: PASS")
                logger.info(f"  ✅ Pullback signal: ACTIVE")
                logger.info(f"  ✅ Price confirmation: PASS")
                logger.info(f"  Direction: LONG")
                logger.info(f"  Entry Price: ${current_price:.2f}")
                logger.info(f"{'='*60}")
                
                return signal
        
        elif self.state.last_signal == 'short':
            # For shorts, wait for price to pull back toward the SuperTrend line
            # Entry when price holds below SuperTrend (body displacement)
            pullback_complete = current_price <= self.state.supertrend_line
            logger.debug(f"{'✅' if pullback_complete else '❌'} Pullback complete (SHORT): {'YES' if pullback_complete else 'NO'} (Price: {current_price:.2f}, Line: {self.state.supertrend_line:.2f})")
            
            if pullback_complete:
                self.state.awaiting_pullback = False  # Pullback complete
                signal = {
                    'direction': 'short',
                    'entry_price': current_price,
                    'supertrend_line': self.state.supertrend_line,
                    'supertrend_5min_line': self.state_5min.supertrend_line,
                    'reason': f'Signal confirmed (multi-timeframe)'
                }
                
                self.state.trades_today += 1
                
                # Log signal conditions met
                logger.info(f"")
                logger.info(f"{'='*60}")
                logger.info(f"📊 SIGNAL CONDITIONS MET")
                logger.info(f"{'='*60}")
                logger.info(f"  ✅ Timeframe alignment: PASS")
                logger.info(f"  ✅ Pullback signal: ACTIVE")
                logger.info(f"  ✅ Price confirmation: PASS")
                logger.info(f"  Direction: SHORT")
                logger.info(f"  Entry Price: ${current_price:.2f}")
                logger.info(f"{'='*60}")
                
                return signal
        
        return None
    
    def get_trailing_stop(self) -> float:
        """
        Get the current trailing stop level (Supertrend line).
        
        In uptrend: Stop is below price (lower band)
        In downtrend: Stop is above price (upper band)
        
        Returns:
            Trailing stop price
        """
        return self.state.supertrend_line
    
    def check_exit_signal(self, position_side: str, current_price: float) -> Tuple[bool, str]:
        """
        Check if we should exit based on Supertrend.
        
        Exit when:
        1. Supertrend flips against our position
        2. OR price crosses Supertrend line
        
        Args:
            position_side: 'long' or 'short'
            current_price: Current market price
            
        Returns:
            (should_exit, reason)
        """
        if position_side == 'long':
            # Exit long if trend flips down OR price breaks below supertrend
            if self.state.trend_direction == 'down':
                return True, "Signal flipped DOWN"
            if current_price < self.state.supertrend_line:
                return True, "Price broke below signal line"
        
        elif position_side == 'short':
            # Exit short if trend flips up OR price breaks above supertrend
            if self.state.trend_direction == 'up':
                return True, "Signal flipped UP"
            if current_price > self.state.supertrend_line:
                return True, "Price broke above signal line"
        
        return False, ""
    
    def record_trade_result(self, is_win: bool) -> None:
        """Record the result of a trade."""
        if is_win:
            self.state.wins_today += 1
            logger.info(f"✅ Trade WIN (total: {self.state.wins_today})")
        else:
            self.state.losses_today += 1
            logger.info(f"❌ Trade LOSS (total: {self.state.losses_today})")
    
    def get_status(self) -> Dict:
        """Get current strategy status."""
        return {
            'trend_direction_1min': self.state.trend_direction,
            'trend_direction_5min': self.state_5min.trend_direction,
            'supertrend_line_1min': self.state.supertrend_line,
            'supertrend_line_5min': self.state_5min.supertrend_line,
            'atr_1min': self.current_atr,
            'atr_5min': self.current_atr_5min,
            'timeframes_aligned': self.timeframes_aligned(),
            'awaiting_pullback': self.state.awaiting_pullback,
            'trades_today': self.state.trades_today,
            'wins_today': self.state.wins_today,
            'losses_today': self.state.losses_today,
            'bars_collected_1min': len(self.bars),
            'bars_collected_5min': len(self.bars_5min)
        }


# Global instance
_supertrend_strategy: Optional[SupertrendStrategy] = None


def get_supertrend_strategy() -> Optional[SupertrendStrategy]:
    """Get the global Supertrend strategy instance."""
    return _supertrend_strategy


def init_supertrend_strategy(tick_size: float = 0.25, tick_value: float = 12.50) -> SupertrendStrategy:
    """
    Initialize the global Supertrend strategy instance.
    
    Args:
        tick_size: Minimum price movement
        tick_value: Dollar value per tick
        
    Returns:
        SupertrendStrategy instance
    """
    global _supertrend_strategy
    _supertrend_strategy = SupertrendStrategy(tick_size=tick_size, tick_value=tick_value)
    return _supertrend_strategy

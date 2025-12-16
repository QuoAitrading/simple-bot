"""
Supertrend + ADX Trend Following Strategy Module

Simple, proven trend-following strategy that:
- Uses Supertrend indicator for entry/exit signals
- Uses ADX to filter out choppy markets
- Holds positions as long as trend continues
- Automatically adapts to any symbol via ATR

Strategy Flow:
1. Check ADX > 25 (strong trend) before any trade
2. Wait for Supertrend signal (trend flip)
3. Enter on signal, hold until opposite signal
4. Trail stop using Supertrend line

Key Parameters:
- ATR Period: 14 (standard)
- Supertrend Multiplier: 3.0 (standard)
- ADX Period: 14 (standard)
- ADX Threshold: 25 (strong trend)
"""

import logging
from datetime import datetime
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass, field
from collections import deque
import pytz

logger = logging.getLogger(__name__)


@dataclass
class SupertrendState:
    """Tracks Supertrend strategy state."""
    trend_direction: Optional[str] = None  # 'up' or 'down'
    supertrend_line: float = 0.0  # Current supertrend value
    upper_band: float = 0.0
    lower_band: float = 0.0
    prev_trend: Optional[str] = None  # Previous trend for signal detection
    signal_generated: bool = False  # True when a new signal is ready
    last_signal: Optional[str] = None  # 'long' or 'short'
    trades_today: int = 0
    wins_today: int = 0
    losses_today: int = 0
    session_date: Optional[str] = None


class SupertrendStrategy:
    """
    Supertrend + ADX Trend Following Strategy.
    
    Only trades when ADX indicates strong trend (> 25).
    Uses Supertrend for entry/exit signals.
    Holds until trend reverses.
    """
    
    # Supertrend parameters
    ATR_PERIOD = 14
    SUPERTREND_MULTIPLIER = 3.0
    
    # ADX parameters  
    ADX_PERIOD = 14
    ADX_TREND_THRESHOLD = 25  # Above this = trending, use Supertrend
    ADX_CHOP_THRESHOLD = 20   # Below this = choppy, use S&D
    
    def __init__(self, tick_size: float = 0.25, tick_value: float = 12.50):
        """
        Initialize Supertrend Strategy.
        
        Args:
            tick_size: Minimum price movement for the symbol
            tick_value: Dollar value per tick
        """
        self.tick_size = tick_size
        self.tick_value = tick_value
        self.state = SupertrendState()
        self.eastern_tz = pytz.timezone('US/Eastern')
        
        # Price history for calculations (need enough for ATR + ADX)
        self.bars: deque = deque(maxlen=100)
        
        # Cached calculations
        self.current_atr: float = 0.0
        self.current_adx: float = 0.0
        self.plus_di: float = 0.0
        self.minus_di: float = 0.0
        
        # Track previous values for trend detection
        self.prev_supertrend: float = 0.0
        self.prev_close: float = 0.0
        
        logger.info("Supertrend Strategy initialized")
    
    def reset_session(self) -> None:
        """Reset state for a new trading day."""
        self.state = SupertrendState()
        self.bars.clear()
        self.current_atr = 0.0
        self.current_adx = 0.0
        self.prev_supertrend = 0.0
        self.prev_close = 0.0
        logger.info("🔄 Supertrend session reset")
    
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
            logger.info(f"📅 New Supertrend session: {today_str}")
    
    def add_bar(self, bar: Dict) -> None:
        """
        Add a new bar and update calculations.
        
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
                    self._calculate_supertrend(bar)
                return
        
        # New bar - add to history
        self.bars.append(bar)
        
        # Need enough bars for calculations
        if len(self.bars) < self.ATR_PERIOD + 1:
            return
        
        # Update ATR
        self._calculate_atr()
        
        # Update ADX (needs more bars)
        if len(self.bars) >= self.ADX_PERIOD + 1:
            self._calculate_adx()
        
        # Update Supertrend
        self._calculate_supertrend(bar)
    
    def _calculate_atr(self) -> None:
        """Calculate Average True Range."""
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
    
    def _calculate_adx(self) -> None:
        """
        Calculate ADX (Average Directional Index).
        
        ADX measures trend strength:
        - ADX > 25: Strong trend
        - ADX < 20: Weak/no trend (choppy)
        - ADX 20-25: Developing trend
        """
        if len(self.bars) < self.ADX_PERIOD + 1:
            return
        
        bars_list = list(self.bars)
        
        # Calculate +DM, -DM, and TR for each bar
        plus_dm_list = []
        minus_dm_list = []
        tr_list = []
        
        for i in range(1, len(bars_list)):
            high = bars_list[i]['high']
            low = bars_list[i]['low']
            prev_high = bars_list[i-1]['high']
            prev_low = bars_list[i-1]['low']
            prev_close = bars_list[i-1]['close']
            
            # True Range
            tr = max(
                high - low,
                abs(high - prev_close),
                abs(low - prev_close)
            )
            tr_list.append(tr)
            
            # Directional Movement
            plus_dm = high - prev_high if high - prev_high > prev_low - low else 0
            minus_dm = prev_low - low if prev_low - low > high - prev_high else 0
            
            if plus_dm < 0:
                plus_dm = 0
            if minus_dm < 0:
                minus_dm = 0
            
            plus_dm_list.append(plus_dm)
            minus_dm_list.append(minus_dm)
        
        if len(tr_list) < self.ADX_PERIOD:
            return
        
        # Smooth the values using Wilder's method
        def wilders_smooth(values, period):
            if len(values) < period:
                return 0
            smoothed = sum(values[:period])
            for i in range(period, len(values)):
                smoothed = smoothed - (smoothed / period) + values[i]
            return smoothed
        
        smoothed_tr = wilders_smooth(tr_list, self.ADX_PERIOD)
        smoothed_plus_dm = wilders_smooth(plus_dm_list, self.ADX_PERIOD)
        smoothed_minus_dm = wilders_smooth(minus_dm_list, self.ADX_PERIOD)
        
        if smoothed_tr == 0:
            return
        
        # Calculate +DI and -DI
        self.plus_di = 100 * smoothed_plus_dm / smoothed_tr
        self.minus_di = 100 * smoothed_minus_dm / smoothed_tr
        
        # Calculate DX
        di_sum = self.plus_di + self.minus_di
        if di_sum == 0:
            return
        
        dx = 100 * abs(self.plus_di - self.minus_di) / di_sum
        
        # For simplicity, use current DX as ADX (proper ADX would smooth DX)
        # This is close enough for trend detection
        self.current_adx = dx
    
    def _calculate_supertrend(self, current_bar: Dict) -> None:
        """
        Calculate Supertrend indicator.
        
        Supertrend = ATR-based trailing stop that flips on trend change.
        """
        if self.current_atr <= 0:
            return
        
        high = current_bar['high']
        low = current_bar['low']
        close = current_bar['close']
        
        # Calculate basic bands
        hl2 = (high + low) / 2  # Median price
        
        basic_upper = hl2 + (self.SUPERTREND_MULTIPLIER * self.current_atr)
        basic_lower = hl2 - (self.SUPERTREND_MULTIPLIER * self.current_atr)
        
        # Final bands (use previous values if they're better)
        if self.state.upper_band > 0:
            # Upper band can only go down (tighter stop)
            if basic_upper < self.state.upper_band or self.prev_close > self.state.upper_band:
                final_upper = basic_upper
            else:
                final_upper = self.state.upper_band
        else:
            final_upper = basic_upper
        
        if self.state.lower_band > 0:
            # Lower band can only go up (tighter stop)
            if basic_lower > self.state.lower_band or self.prev_close < self.state.lower_band:
                final_lower = basic_lower
            else:
                final_lower = self.state.lower_band
        else:
            final_lower = basic_lower
        
        # Store previous state
        self.state.prev_trend = self.state.trend_direction
        self.prev_supertrend = self.state.supertrend_line
        
        # Determine trend direction
        if self.state.trend_direction is None:
            # Initial trend based on close vs bands
            if close > final_upper:
                self.state.trend_direction = 'down'
            else:
                self.state.trend_direction = 'up'
        else:
            # Trend flip logic
            if self.state.trend_direction == 'up':
                if close < final_lower:
                    self.state.trend_direction = 'down'
            else:  # down
                if close > final_upper:
                    self.state.trend_direction = 'up'
        
        # Set supertrend line based on trend
        if self.state.trend_direction == 'up':
            self.state.supertrend_line = final_lower
        else:
            self.state.supertrend_line = final_upper
        
        # Update bands
        self.state.upper_band = final_upper
        self.state.lower_band = final_lower
        self.prev_close = close
        
        # Check for signal (trend flip)
        if self.state.prev_trend is not None and self.state.prev_trend != self.state.trend_direction:
            self.state.signal_generated = True
            if self.state.trend_direction == 'up':
                self.state.last_signal = 'long'
                logger.info(f"🟢 SUPERTREND FLIP → UP: Signal LONG at {close:.2f}")
            else:
                self.state.last_signal = 'short'
                logger.info(f"🔴 SUPERTREND FLIP → DOWN: Signal SHORT at {close:.2f}")
        else:
            self.state.signal_generated = False
    
    def should_use_supertrend(self) -> bool:
        """
        Check if we should use Supertrend based on ADX.
        
        Returns:
            True if ADX > 25 (trending market)
        """
        return self.current_adx > self.ADX_TREND_THRESHOLD
    
    def should_use_snd(self) -> bool:
        """
        Check if we should use S&D based on ADX.
        
        Returns:
            True if ADX < 20 (choppy market)
        """
        return self.current_adx < self.ADX_CHOP_THRESHOLD
    
    def get_market_condition(self) -> str:
        """
        Get current market condition based on ADX.
        
        Returns:
            'trending', 'choppy', or 'unclear'
        """
        if self.current_adx > self.ADX_TREND_THRESHOLD:
            return 'trending'
        elif self.current_adx < self.ADX_CHOP_THRESHOLD:
            return 'choppy'
        else:
            return 'unclear'
    
    def check_entry_signal(self, current_bar: Dict, current_price: float) -> Optional[Dict]:
        """
        Check for Supertrend entry signal.
        
        Only generates signal if:
        1. ADX > 25 (trending)
        2. Supertrend just flipped
        
        No trade limit - unlimited trades allowed.
        
        Args:
            current_bar: Current OHLCV bar
            current_price: Current market price
            
        Returns:
            Signal dict or None
        """
        # Must be trending
        if not self.should_use_supertrend():
            return None
        
        # Must have a fresh signal
        if not self.state.signal_generated:
            return None
        
        # Clear the signal flag
        self.state.signal_generated = False
        
        # Build signal
        signal = {
            'direction': self.state.last_signal,
            'entry_price': current_price,
            'supertrend_line': self.state.supertrend_line,
            'adx': self.current_adx,
            'reason': f'Supertrend {self.state.last_signal.upper()} (ADX: {self.current_adx:.1f})'
        }
        
        self.state.trades_today += 1
        
        logger.info(f"📈 SUPERTREND SIGNAL: {signal['direction'].upper()} @ {current_price:.2f}")
        logger.info(f"   ADX: {self.current_adx:.1f}, Supertrend: {self.state.supertrend_line:.2f}")
        
        return signal
    
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
                return True, "Supertrend flipped DOWN"
            if current_price < self.state.supertrend_line:
                return True, "Price broke below Supertrend"
        
        elif position_side == 'short':
            # Exit short if trend flips up OR price breaks above supertrend
            if self.state.trend_direction == 'up':
                return True, "Supertrend flipped UP"
            if current_price > self.state.supertrend_line:
                return True, "Price broke above Supertrend"
        
        return False, ""
    
    def record_trade_result(self, is_win: bool) -> None:
        """Record the result of a trade."""
        if is_win:
            self.state.wins_today += 1
            logger.info(f"✅ Supertrend trade WIN (total: {self.state.wins_today})")
        else:
            self.state.losses_today += 1
            logger.info(f"❌ Supertrend trade LOSS (total: {self.state.losses_today})")
    
    def get_status(self) -> Dict:
        """Get current strategy status."""
        return {
            'trend_direction': self.state.trend_direction,
            'supertrend_line': self.state.supertrend_line,
            'atr': self.current_atr,
            'adx': self.current_adx,
            'plus_di': self.plus_di,
            'minus_di': self.minus_di,
            'market_condition': self.get_market_condition(),
            'should_use_supertrend': self.should_use_supertrend(),
            'should_use_snd': self.should_use_snd(),
            'trades_today': self.state.trades_today,
            'wins_today': self.state.wins_today,
            'losses_today': self.state.losses_today,
            'bars_collected': len(self.bars)
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

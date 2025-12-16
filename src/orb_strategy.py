"""
Opening Range Breakout (ORB) Strategy Module

Symbol-agnostic ORB strategy for the first 30 minutes of market open.
Designed to work with any liquid market using volatility-normalized rules.

Strategy Flow:
1. 9:30-9:45 ET: Build the Opening Range (ORH/ORL)
2. 9:45-10:00 ET: Wait for breakout + retest + entry
3. 10:00 ET: ORB window closes, Supertrend takes over

Key Features:
- ATR-based range validation (no hardcoded ticks/points)
- Retest confirmation required (no breakout entries)
- Max 2 trades per ORB session
- Stops after 2 losses or 1 win
"""

import logging
from datetime import datetime, time as datetime_time
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass, field
import pytz

logger = logging.getLogger(__name__)


@dataclass
class OpeningRange:
    """Represents the Opening Range for a session."""
    orh: float = 0.0  # Opening Range High
    orl: float = float('inf')  # Opening Range Low
    is_built: bool = False  # True after 9:45 ET
    build_start: Optional[datetime] = None
    build_end: Optional[datetime] = None
    bars_collected: int = 0
    
    @property
    def range_size(self) -> float:
        """Get the size of the opening range."""
        if self.orl == float('inf'):
            return 0.0
        return self.orh - self.orl
    
    @property
    def mid_point(self) -> float:
        """Get the midpoint of the opening range."""
        if self.orl == float('inf'):
            return 0.0
        return (self.orh + self.orl) / 2


@dataclass
class ORBState:
    """Tracks ORB session state."""
    opening_range: OpeningRange = field(default_factory=OpeningRange)
    bias: Optional[str] = None  # 'long' or 'short' after first breakout
    breakout_confirmed: bool = False
    retest_in_progress: bool = False
    retest_start_price: Optional[float] = None
    trades_today: int = 0
    wins_today: int = 0
    losses_today: int = 0
    session_active: bool = False
    session_date: Optional[str] = None  # YYYY-MM-DD to track daily reset
    entry_price: Optional[float] = None
    stop_loss: Optional[float] = None
    take_profit: Optional[float] = None


class ORBStrategy:
    """
    Opening Range Breakout Strategy.
    
    Runs during 9:30-10:00 ET, then hands off to Supertrend.
    Symbol-agnostic using ATR-based validation.
    """
    
    # ORB Time Windows (ET)
    ORB_START = datetime_time(9, 30)  # 9:30 AM ET
    RANGE_BUILD_END = datetime_time(9, 45)  # 9:45 AM ET
    ORB_END = datetime_time(10, 0)  # 10:00 AM ET
    
    # ATR-based range filter bounds
    MIN_ATR_RATIO = 0.6  # Range must be at least 60% of ATR
    MAX_ATR_RATIO = 1.5  # Range must not exceed 150% of ATR
    
    # Trade limits
    MAX_TRADES_PER_SESSION = 2
    MAX_LOSSES_BEFORE_STOP = 2
    WINS_TO_STOP = 1  # Stop after 1 win (conservative)
    
    def __init__(self, tick_size: float = 0.25, tick_value: float = 12.50):
        """
        Initialize ORB Strategy.
        
        Args:
            tick_size: Minimum price movement for the symbol
            tick_value: Dollar value per tick
        """
        self.tick_size = tick_size
        self.tick_value = tick_value
        self.state = ORBState()
        self.eastern_tz = pytz.timezone('US/Eastern')
        
        # ATR storage (populated from main engine)
        self.current_atr: float = 0.0
        
        logger.info("ORB Strategy initialized")
    
    def is_orb_window(self, current_time: datetime) -> bool:
        """
        Check if we're in the ORB trading window (9:30-10:00 ET).
        
        Args:
            current_time: Current datetime (timezone-aware)
            
        Returns:
            True if within ORB window
        """
        # Convert to Eastern
        if current_time.tzinfo is None:
            current_time = self.eastern_tz.localize(current_time)
        else:
            current_time = current_time.astimezone(self.eastern_tz)
        
        current_time_only = current_time.time()
        
        # Check if between 9:30 and 10:00 ET
        return self.ORB_START <= current_time_only < self.ORB_END
    
    def is_range_building(self, current_time: datetime) -> bool:
        """
        Check if we're in the range building window (9:30-9:45 ET).
        
        Args:
            current_time: Current datetime (timezone-aware)
            
        Returns:
            True if within range building window
        """
        # Convert to Eastern
        if current_time.tzinfo is None:
            current_time = self.eastern_tz.localize(current_time)
        else:
            current_time = current_time.astimezone(self.eastern_tz)
        
        current_time_only = current_time.time()
        
        return self.ORB_START <= current_time_only < self.RANGE_BUILD_END
    
    def reset_session(self) -> None:
        """Reset ORB state for a new session."""
        self.state = ORBState()
        self._last_bar_timestamp = None  # Reset bar tracking
        logger.info("🔄 ORB session reset")
    
    def check_session_reset(self, current_time: datetime) -> None:
        """
        Check if we need to reset for a new trading day.
        
        Args:
            current_time: Current datetime
        """
        # Convert to Eastern
        if current_time.tzinfo is None:
            current_time = self.eastern_tz.localize(current_time)
        else:
            current_time = current_time.astimezone(self.eastern_tz)
        
        today_str = current_time.strftime("%Y-%m-%d")
        
        if self.state.session_date != today_str:
            # New day - reset session
            self.reset_session()
            self.state.session_date = today_str
            logger.info(f"📅 New ORB session started: {today_str}")
    
    def update_opening_range(self, bar: Dict) -> None:
        """
        Update the opening range with a new bar.
        
        Only counts new bars (based on timestamp) for bars_collected.
        
        Args:
            bar: OHLCV bar dictionary with 'high', 'low', 'timestamp' keys
        """
        if self.state.opening_range.is_built:
            return  # Range already built
        
        bar_high = bar.get('high', 0)
        bar_low = bar.get('low', float('inf'))
        bar_timestamp = bar.get('timestamp')
        
        # Update ORH/ORL (always take max/min even if same bar)
        orh_updated = bar_high > self.state.opening_range.orh
        orl_updated = bar_low < self.state.opening_range.orl
        
        if orh_updated:
            self.state.opening_range.orh = bar_high
        if orl_updated:
            self.state.opening_range.orl = bar_low
        
        # Only count new bars (avoid counting same bar multiple times)
        # Track by checking if this is the first bar or a new timestamp
        if not hasattr(self, '_last_bar_timestamp') or self._last_bar_timestamp != bar_timestamp:
            self.state.opening_range.bars_collected += 1
            self._last_bar_timestamp = bar_timestamp
            
            logger.debug(f"ORB Range update: ORH={self.state.opening_range.orh:.2f}, "
                        f"ORL={self.state.opening_range.orl:.2f}, "
                        f"bars={self.state.opening_range.bars_collected}")
    
    def finalize_opening_range(self, current_time: datetime) -> bool:
        """
        Finalize the opening range after 9:45 ET.
        
        Args:
            current_time: Current datetime
            
        Returns:
            True if range is valid and finalized
        """
        if self.state.opening_range.is_built:
            return True
        
        # Mark as built
        self.state.opening_range.is_built = True
        self.state.opening_range.build_end = current_time
        
        # Validate range size using ATR
        range_size = self.state.opening_range.range_size
        
        if self.current_atr <= 0:
            logger.warning("⚠️ ATR not available for ORB validation")
            return False
        
        atr_ratio = range_size / self.current_atr
        
        logger.info(f"📏 Opening Range finalized:")
        logger.info(f"   ORH: {self.state.opening_range.orh:.2f}")
        logger.info(f"   ORL: {self.state.opening_range.orl:.2f}")
        logger.info(f"   Range: {range_size:.2f} ({atr_ratio:.2f}x ATR)")
        
        # Validate ATR ratio
        if atr_ratio < self.MIN_ATR_RATIO:
            logger.info(f"❌ ORB range too small: {atr_ratio:.2f} < {self.MIN_ATR_RATIO}")
            self.state.session_active = False
            return False
        
        if atr_ratio > self.MAX_ATR_RATIO:
            logger.info(f"❌ ORB range too large: {atr_ratio:.2f} > {self.MAX_ATR_RATIO}")
            self.state.session_active = False
            return False
        
        logger.info(f"✅ ORB range valid - session active")
        self.state.session_active = True
        return True
    
    def check_breakout(self, current_price: float) -> Optional[str]:
        """
        Check if price has broken out of the opening range.
        
        Args:
            current_price: Current market price
            
        Returns:
            'long', 'short', or None
        """
        if not self.state.opening_range.is_built:
            return None
        
        if self.state.bias is not None:
            return None  # Already have a bias
        
        orh = self.state.opening_range.orh
        orl = self.state.opening_range.orl
        
        if current_price > orh:
            self.state.bias = 'long'
            self.state.breakout_confirmed = True
            logger.info(f"🔼 BULLISH breakout: price {current_price:.2f} > ORH {orh:.2f}")
            return 'long'
        
        if current_price < orl:
            self.state.bias = 'short'
            self.state.breakout_confirmed = True
            logger.info(f"🔽 BEARISH breakout: price {current_price:.2f} < ORL {orl:.2f}")
            return 'short'
        
        return None
    
    def check_retest(self, current_bar: Dict) -> bool:
        """
        Check if price is retesting the OR level.
        
        For LONG: Price pulls back toward ORH, body_low >= ORH
        For SHORT: Price pulls back toward ORL, body_high <= ORL
        
        Args:
            current_bar: Current OHLCV bar
            
        Returns:
            True if retest is valid
        """
        if not self.state.breakout_confirmed:
            return False
        
        if not self.state.session_active:
            return False
        
        orh = self.state.opening_range.orh
        orl = self.state.opening_range.orl
        
        # Calculate body
        bar_open = current_bar.get('open', 0)
        bar_close = current_bar.get('close', 0)
        body_high = max(bar_open, bar_close)
        body_low = min(bar_open, bar_close)
        
        if self.state.bias == 'long':
            # For long: body must be holding above ORH
            if body_low >= orh:
                logger.info(f"✅ Long retest valid: body_low {body_low:.2f} >= ORH {orh:.2f}")
                return True
        
        elif self.state.bias == 'short':
            # For short: body must be holding below ORL
            if body_high <= orl:
                logger.info(f"✅ Short retest valid: body_high {body_high:.2f} <= ORL {orl:.2f}")
                return True
        
        return False
    
    def check_entry_signal(self, current_bar: Dict, current_price: float) -> Optional[Dict]:
        """
        Check if we should enter an ORB trade.
        
        Entry is first body displacement away from OR.
        
        Args:
            current_bar: Current OHLCV bar
            current_price: Current market price
            
        Returns:
            Trade signal dict or None
        """
        if not self.can_trade():
            return None
        
        if not self.check_retest(current_bar):
            return None
        
        orh = self.state.opening_range.orh
        orl = self.state.opening_range.orl
        
        # Calculate body
        bar_open = current_bar.get('open', 0)
        bar_close = current_bar.get('close', 0)
        body_high = max(bar_open, bar_close)
        body_low = min(bar_open, bar_close)
        
        signal = None
        
        if self.state.bias == 'long':
            # Long entry: body displaced above ORH
            if body_low > orh:
                signal = {
                    'direction': 'long',
                    'entry_price': current_price,
                    'reason': 'ORB Long Retest',
                    'orh': orh,
                    'orl': orl
                }
                logger.info(f"📈 ORB LONG SIGNAL: Entry at {current_price:.2f}")
        
        elif self.state.bias == 'short':
            # Short entry: body displaced below ORL
            if body_high < orl:
                signal = {
                    'direction': 'short',
                    'entry_price': current_price,
                    'reason': 'ORB Short Retest',
                    'orh': orh,
                    'orl': orl
                }
                logger.info(f"📉 ORB SHORT SIGNAL: Entry at {current_price:.2f}")
        
        if signal:
            self.state.trades_today += 1
        
        return signal
    
    def can_trade(self) -> bool:
        """
        Check if we can take another ORB trade.
        
        Returns:
            True if trading is allowed
        """
        if not self.state.session_active:
            return False
        
        # Max trades reached
        if self.state.trades_today >= self.MAX_TRADES_PER_SESSION:
            logger.debug(f"ORB: Max trades reached ({self.MAX_TRADES_PER_SESSION})")
            return False
        
        # Stop after X losses
        if self.state.losses_today >= self.MAX_LOSSES_BEFORE_STOP:
            logger.debug(f"ORB: Max losses reached ({self.MAX_LOSSES_BEFORE_STOP})")
            return False
        
        # Stop after 1 win
        if self.state.wins_today >= self.WINS_TO_STOP:
            logger.debug(f"ORB: Win target reached ({self.WINS_TO_STOP})")
            return False
        
        return True
    
    def record_trade_result(self, is_win: bool) -> None:
        """
        Record the result of an ORB trade.
        
        Args:
            is_win: True if trade was profitable
        """
        if is_win:
            self.state.wins_today += 1
            logger.info(f"✅ ORB trade WIN (total wins: {self.state.wins_today})")
        else:
            self.state.losses_today += 1
            logger.info(f"❌ ORB trade LOSS (total losses: {self.state.losses_today})")
    
    def set_atr(self, atr_value: float) -> None:
        """
        Set the current ATR value for range validation.
        
        Args:
            atr_value: ATR value from main engine
        """
        self.current_atr = atr_value
    
    def get_status(self) -> Dict:
        """
        Get current ORB strategy status.
        
        Returns:
            Status dictionary
        """
        return {
            'session_active': self.state.session_active,
            'session_date': self.state.session_date,
            'orh': self.state.opening_range.orh if self.state.opening_range.orh > 0 else None,
            'orl': self.state.opening_range.orl if self.state.opening_range.orl < float('inf') else None,
            'range_built': self.state.opening_range.is_built,
            'range_size': self.state.opening_range.range_size if self.state.opening_range.is_built else None,
            'bias': self.state.bias,
            'breakout_confirmed': self.state.breakout_confirmed,
            'trades_today': self.state.trades_today,
            'wins_today': self.state.wins_today,
            'losses_today': self.state.losses_today,
            'can_trade': self.can_trade()
        }


# Global instance
_orb_strategy: Optional[ORBStrategy] = None


def get_orb_strategy() -> Optional[ORBStrategy]:
    """Get the global ORB strategy instance."""
    return _orb_strategy


def init_orb_strategy(tick_size: float = 0.25, tick_value: float = 12.50) -> ORBStrategy:
    """
    Initialize the global ORB strategy instance.
    
    Args:
        tick_size: Minimum price movement
        tick_value: Dollar value per tick
        
    Returns:
        ORBStrategy instance
    """
    global _orb_strategy
    _orb_strategy = ORBStrategy(tick_size=tick_size, tick_value=tick_value)
    return _orb_strategy

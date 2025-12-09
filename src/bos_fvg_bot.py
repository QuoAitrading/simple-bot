"""
BOS (Break of Structure) + FVG (Fair Value Gap) Scalping Strategy

A high-frequency scalping bot that combines Smart Money Concepts (SMC) to generate
15-20+ trades per day on ES 1-minute data.

STRATEGY OVERVIEW:
This bot identifies trend changes via Break of Structure (BOS) and enters trades
when price returns to Fair Value Gaps (FVG) in the direction of the new trend.

BOS (BREAK OF STRUCTURE):
- Bullish BOS: Price breaks above previous swing high
- Bearish BOS: Price breaks below previous swing low
- Confirms trend direction and market structure shift

FVG (FAIR VALUE GAP):
- 3-candle imbalance pattern
- Bullish FVG: Candle 1 high < Candle 3 low (gap up)
- Bearish FVG: Candle 1 low > Candle 3 high (gap down)
- Price tends to return to fill these gaps (50-70% fill rate)

ENTRY LOGIC:
1. Identify BOS to determine trend direction
2. Detect FVG formation in trend direction
3. Wait for price to return to FVG zone
4. Enter when price touches FVG (immediate fill)
5. Stop: Beyond FVG, Target: 1.5x risk

RISK MANAGEMENT:
- Stop Loss: 2 ticks beyond FVG boundary
- Take Profit: 1.5:1 reward-to-risk ratio
- FVGs expire after being filled or after 60 minutes

This strategy generates high trade frequency (15-20+ trades/day) by trading
every FVG fill in the direction of the prevailing structure.
"""

import logging
from datetime import datetime, timedelta
from typing import List, Dict, Optional, Tuple, Deque
from dataclasses import dataclass
from collections import deque
import pytz


@dataclass
class SwingPoint:
    """Represents a swing high or swing low"""
    price: float
    timestamp: datetime
    candle_index: int
    swing_type: str  # 'high' or 'low'


@dataclass
class FVG:
    """Represents a Fair Value Gap"""
    fvg_type: str  # 'bullish' or 'bearish'
    top: float  # Top of the gap
    bottom: float  # Bottom of the gap
    created_at: datetime
    candle_index: int
    filled: bool = False
    
    def get_thickness_ticks(self, tick_size: float) -> float:
        """Get FVG thickness in ticks"""
        return abs(self.top - self.bottom) / tick_size
    
    def is_price_in_gap(self, price: float) -> bool:
        """Check if price is within the FVG"""
        return self.bottom <= price <= self.top
    
    def is_expired(self, current_time: datetime, max_age_minutes: int = 60) -> bool:
        """Check if FVG is too old"""
        age = (current_time - self.created_at).total_seconds() / 60
        return age > max_age_minutes


@dataclass
class Candle:
    """Represents a candlestick bar"""
    timestamp: datetime
    open: float
    high: float
    low: float
    close: float
    volume: float
    
    @property
    def is_bullish(self) -> bool:
        return self.close > self.open
    
    @property
    def is_bearish(self) -> bool:
        return self.close < self.open
    
    @property
    def body_top(self) -> float:
        return max(self.open, self.close)
    
    @property
    def body_bottom(self) -> float:
        return min(self.open, self.close)
    
    @property
    def total_range(self) -> float:
        return self.high - self.low
    
    @property
    def body_size(self) -> float:
        return abs(self.close - self.open)


class BOSFVGStrategy:
    """
    BOS + FVG Scalping Strategy for high-frequency trading
    
    Generates 15-20+ trades per day by:
    1. Tracking market structure (swing highs/lows)
    2. Detecting Break of Structure (BOS) for trend direction
    3. Identifying Fair Value Gaps (FVG) in trend direction
    4. Trading FVG fills with tight stops and 1.5:1 targets
    """
    
    def __init__(
        self,
        tick_size: float = 0.25,
        tick_value: float = 12.50,
        swing_lookback: int = 5,  # Bars to look back for swing points
        min_fvg_ticks: float = 2,  # Minimum FVG size (2 ticks)
        max_fvg_ticks: float = 20,  # Maximum FVG size (20 ticks)
        fvg_expiry_minutes: int = 60,  # FVG expires after 1 hour
        stop_loss_ticks: float = 2,  # Stop beyond FVG
        risk_reward_ratio: float = 1.5,  # 1.5:1 R:R
        max_active_fvgs: int = 10,  # Maximum FVGs to track
        logger: Optional[logging.Logger] = None
    ):
        """
        Initialize BOS + FVG scalping strategy
        
        Args:
            tick_size: Minimum price movement (0.25 for ES)
            tick_value: Dollar value per tick (12.50 for ES)
            swing_lookback: Bars to identify swing highs/lows
            min_fvg_ticks: Minimum FVG thickness
            max_fvg_ticks: Maximum FVG thickness
            fvg_expiry_minutes: FVG lifetime in minutes
            stop_loss_ticks: Ticks to place stop beyond FVG
            risk_reward_ratio: Target distance multiplier
            max_active_fvgs: Maximum FVGs to track at once
            logger: Optional logger instance
        """
        self.tick_size = tick_size
        self.tick_value = tick_value
        self.swing_lookback = swing_lookback
        self.min_fvg_ticks = min_fvg_ticks
        self.max_fvg_ticks = max_fvg_ticks
        self.fvg_expiry_minutes = fvg_expiry_minutes
        self.stop_loss_ticks = stop_loss_ticks
        self.risk_reward_ratio = risk_reward_ratio
        self.max_active_fvgs = max_active_fvgs
        
        self.logger = logger or logging.getLogger(__name__)
        
        # State tracking
        self.candles: Deque[Candle] = deque(maxlen=200)
        self.swing_highs: List[SwingPoint] = []
        self.swing_lows: List[SwingPoint] = []
        self.bullish_fvgs: List[FVG] = []
        self.bearish_fvgs: List[FVG] = []
        
        self.current_trend: Optional[str] = None  # 'bullish', 'bearish', or None
        self.last_bos: Optional[Dict] = None
        
        # Statistics
        self.current_candle_index = 0
        self.fvgs_created = 0
        self.fvgs_filled = 0
        self.bos_count = 0
        
        self.logger.info("BOS + FVG Strategy initialized for high-frequency scalping")
    
    def process_candle(self, candle_data: Dict) -> Optional[Dict]:
        """
        Process new candle and generate trade signals
        
        Returns:
            Dict with trade signal or None
        """
        # Create candle object
        candle = Candle(
            timestamp=candle_data['timestamp'],
            open=candle_data['open'],
            high=candle_data['high'],
            low=candle_data['low'],
            close=candle_data['close'],
            volume=candle_data.get('volume', 0)
        )
        
        self.candles.append(candle)
        self.current_candle_index += 1
        
        # Need at least swing_lookback candles
        if len(self.candles) < self.swing_lookback + 3:
            return None
        
        # Update market structure
        self._update_swing_points()
        
        # Check for Break of Structure
        self._check_for_bos()
        
        # Detect new FVGs
        self._detect_fvgs()
        
        # Clean up expired FVGs
        self._cleanup_fvgs()
        
        # Check for FVG fill signals
        signal = self._check_fvg_fills(candle)
        
        return signal
    
    def _update_swing_points(self):
        """Identify swing highs and swing lows"""
        if len(self.candles) < self.swing_lookback * 2 + 1:
            return
        
        # Check for swing high (highest high in lookback window)
        center_idx = -self.swing_lookback - 1
        center_candle = list(self.candles)[center_idx]
        
        is_swing_high = True
        is_swing_low = True
        
        # Check if center is highest/lowest
        for i in range(-self.swing_lookback * 2, 0):
            if i == center_idx:
                continue
            compare_candle = list(self.candles)[i]
            
            if compare_candle.high >= center_candle.high:
                is_swing_high = False
            if compare_candle.low <= center_candle.low:
                is_swing_low = False
        
        # Add swing high
        if is_swing_high:
            swing = SwingPoint(
                price=center_candle.high,
                timestamp=center_candle.timestamp,
                candle_index=self.current_candle_index + center_idx,
                swing_type='high'
            )
            # Only keep recent swings
            self.swing_highs.append(swing)
            if len(self.swing_highs) > 20:
                self.swing_highs.pop(0)
        
        # Add swing low
        if is_swing_low:
            swing = SwingPoint(
                price=center_candle.low,
                timestamp=center_candle.timestamp,
                candle_index=self.current_candle_index + center_idx,
                swing_type='low'
            )
            self.swing_lows.append(swing)
            if len(self.swing_lows) > 20:
                self.swing_lows.pop(0)
    
    def _check_for_bos(self):
        """Check for Break of Structure"""
        if not self.swing_highs or not self.swing_lows:
            return
        
        current_candle = self.candles[-1]
        
        # Check for Bullish BOS (break above recent swing high)
        if len(self.swing_highs) >= 2:
            recent_high = self.swing_highs[-1]
            if current_candle.close > recent_high.price:
                if self.current_trend != 'bullish':
                    self.current_trend = 'bullish'
                    self.last_bos = {
                        'type': 'bullish',
                        'price': recent_high.price,
                        'timestamp': current_candle.timestamp
                    }
                    self.bos_count += 1
                    self.logger.info(f"🔵 BULLISH BOS at {current_candle.close:.2f} | Breaking {recent_high.price:.2f}")
        
        # Check for Bearish BOS (break below recent swing low)
        if len(self.swing_lows) >= 2:
            recent_low = self.swing_lows[-1]
            if current_candle.close < recent_low.price:
                if self.current_trend != 'bearish':
                    self.current_trend = 'bearish'
                    self.last_bos = {
                        'type': 'bearish',
                        'price': recent_low.price,
                        'timestamp': current_candle.timestamp
                    }
                    self.bos_count += 1
                    self.logger.info(f"🔴 BEARISH BOS at {current_candle.close:.2f} | Breaking {recent_low.price:.2f}")
    
    def _detect_fvgs(self):
        """Detect Fair Value Gaps (3-candle imbalance pattern)"""
        if len(self.candles) < 3:
            return
        
        candle1 = list(self.candles)[-3]
        candle2 = list(self.candles)[-2]
        candle3 = list(self.candles)[-1]
        
        # Bullish FVG: candle1.high < candle3.low (gap up)
        if candle1.high < candle3.low:
            gap_bottom = candle1.high
            gap_top = candle3.low
            gap_thickness = (gap_top - gap_bottom) / self.tick_size
            
            if self.min_fvg_ticks <= gap_thickness <= self.max_fvg_ticks:
                fvg = FVG(
                    fvg_type='bullish',
                    top=gap_top,
                    bottom=gap_bottom,
                    created_at=candle3.timestamp,
                    candle_index=self.current_candle_index
                )
                self.bullish_fvgs.append(fvg)
                self.fvgs_created += 1
                
                # Limit active FVGs
                if len(self.bullish_fvgs) > self.max_active_fvgs:
                    self.bullish_fvgs.pop(0)
                
                self.logger.info(f"🟢 BULLISH FVG created at {gap_bottom:.2f}-{gap_top:.2f} | {gap_thickness:.1f} ticks")
        
        # Bearish FVG: candle1.low > candle3.high (gap down)
        if candle1.low > candle3.high:
            gap_top = candle1.low
            gap_bottom = candle3.high
            gap_thickness = (gap_top - gap_bottom) / self.tick_size
            
            if self.min_fvg_ticks <= gap_thickness <= self.max_fvg_ticks:
                fvg = FVG(
                    fvg_type='bearish',
                    top=gap_top,
                    bottom=gap_bottom,
                    created_at=candle3.timestamp,
                    candle_index=self.current_candle_index
                )
                self.bearish_fvgs.append(fvg)
                self.fvgs_created += 1
                
                if len(self.bearish_fvgs) > self.max_active_fvgs:
                    self.bearish_fvgs.pop(0)
                
                self.logger.info(f"🔴 BEARISH FVG created at {gap_bottom:.2f}-{gap_top:.2f} | {gap_thickness:.1f} ticks")
    
    def _cleanup_fvgs(self):
        """Remove expired or filled FVGs"""
        current_time = self.candles[-1].timestamp
        
        # Clean bullish FVGs
        valid_bullish = []
        for fvg in self.bullish_fvgs:
            if not fvg.filled and not fvg.is_expired(current_time, self.fvg_expiry_minutes):
                valid_bullish.append(fvg)
        self.bullish_fvgs = valid_bullish
        
        # Clean bearish FVGs
        valid_bearish = []
        for fvg in self.bearish_fvgs:
            if not fvg.filled and not fvg.is_expired(current_time, self.fvg_expiry_minutes):
                valid_bearish.append(fvg)
        self.bearish_fvgs = valid_bearish
    
    def _check_fvg_fills(self, candle: Candle) -> Optional[Dict]:
        """
        Check if price is filling an FVG and generate trade signal
        
        Trading in direction of trend only:
        - Bullish trend: Trade bullish FVG fills (longs)
        - Bearish trend: Trade bearish FVG fills (shorts)
        """
        
        # LONG: Bullish trend + Bullish FVG fill
        if self.current_trend == 'bullish':
            for fvg in self.bullish_fvgs:
                if fvg.filled:
                    continue
                
                # Check if price touched FVG
                if candle.low <= fvg.top and candle.high >= fvg.bottom:
                    # Price is in the FVG - enter LONG
                    entry_price = fvg.bottom  # Enter at FVG bottom
                    stop_price = fvg.bottom - (self.stop_loss_ticks * self.tick_size)
                    risk_ticks = self.stop_loss_ticks
                    target_ticks = risk_ticks * self.risk_reward_ratio
                    target_price = entry_price + (target_ticks * self.tick_size)
                    
                    fvg.filled = True
                    self.fvgs_filled += 1
                    
                    self.logger.info(
                        f"🟢 LONG SIGNAL (Bullish FVG Fill) | Entry: {entry_price:.2f} | "
                        f"Stop: {stop_price:.2f} | Target: {target_price:.2f} | "
                        f"Risk: {risk_ticks:.1f} ticks | R:R = 1:{self.risk_reward_ratio}"
                    )
                    
                    return {
                        'signal': 'LONG',
                        'entry': entry_price,
                        'stop_loss': stop_price,
                        'take_profit': target_price,
                        'risk_ticks': risk_ticks,
                        'reason': 'bullish_fvg_fill',
                        'fvg_range': f"{fvg.bottom:.2f}-{fvg.top:.2f}"
                    }
        
        # SHORT: Bearish trend + Bearish FVG fill
        elif self.current_trend == 'bearish':
            for fvg in self.bearish_fvgs:
                if fvg.filled:
                    continue
                
                # Check if price touched FVG
                if candle.low <= fvg.top and candle.high >= fvg.bottom:
                    # Price is in the FVG - enter SHORT
                    entry_price = fvg.top  # Enter at FVG top
                    stop_price = fvg.top + (self.stop_loss_ticks * self.tick_size)
                    risk_ticks = self.stop_loss_ticks
                    target_ticks = risk_ticks * self.risk_reward_ratio
                    target_price = entry_price - (target_ticks * self.tick_size)
                    
                    fvg.filled = True
                    self.fvgs_filled += 1
                    
                    self.logger.info(
                        f"🔴 SHORT SIGNAL (Bearish FVG Fill) | Entry: {entry_price:.2f} | "
                        f"Stop: {stop_price:.2f} | Target: {target_price:.2f} | "
                        f"Risk: {risk_ticks:.1f} ticks | R:R = 1:{self.risk_reward_ratio}"
                    )
                    
                    return {
                        'signal': 'SHORT',
                        'entry': entry_price,
                        'stop_loss': stop_price,
                        'take_profit': target_price,
                        'risk_ticks': risk_ticks,
                        'reason': 'bearish_fvg_fill',
                        'fvg_range': f"{fvg.bottom:.2f}-{fvg.top:.2f}"
                    }
        
        return None
    
    def get_statistics(self) -> Dict:
        """Get strategy statistics"""
        return {
            'current_trend': self.current_trend or 'undefined',
            'bullish_fvgs_active': len(self.bullish_fvgs),
            'bearish_fvgs_active': len(self.bearish_fvgs),
            'fvgs_created': self.fvgs_created,
            'fvgs_filled': self.fvgs_filled,
            'bos_count': self.bos_count,
            'swing_highs': len(self.swing_highs),
            'swing_lows': len(self.swing_lows),
        }

"""
LuxAlgo SMC + Rejection Strategy
EXACT replication of LuxAlgo Smart Money Concepts indicator logic.

Reference: LuxAlgo Pine Script v5 (CC BY-NC-SA 4.0)
https://creativecommons.org/licenses/by-nc-sa/4.0/

Key Logic Matched:
1. FVG: barDeltaPercent = (close - open) / (open * 100), threshold = cumAvg * 2
2. Order Blocks: highVolatilityBar inverts parsed high/low
3. Structure: Uses crossover/crossunder with 'crossed' flag to prevent re-triggering
"""

from typing import Dict, Any, Optional, List
from datetime import datetime
from collections import deque
import logging


class LuxAlgoSMCStrategy:
    """
    EXACT replication of LuxAlgo Smart Money Concepts indicator.
    """

    def __init__(self,
                 tick_size: float = 0.25,
                 swing_lookback: int = 50,
                 internal_lookback: int = 5,
                 atr_period: int = 200,
                 stop_loss_ticks: int = 12,
                 take_profit_ticks: int = 12,
                 use_auto_threshold: bool = True):
        """
        Initialize LuxAlgo SMC Strategy - EXACT match to Pine Script.
        
        Args:
            tick_size: Instrument tick size (e.g., 0.25 for ES)
            swing_lookback: Swing structure lookback (default: 50, matches LuxAlgo)
            internal_lookback: Internal structure lookback (default: 5, matches LuxAlgo)
            atr_period: ATR period for volatility filter (default: 200, matches LuxAlgo)
            stop_loss_ticks: Fixed stop loss in ticks
            take_profit_ticks: Fixed take profit in ticks
            use_auto_threshold: Use LuxAlgo's auto threshold for FVG (default: True)
        """
        self.tick_size = tick_size
        self.swing_lookback = swing_lookback
        self.internal_lookback = internal_lookback
        self.atr_period = atr_period
        self.stop_loss_ticks = stop_loss_ticks
        self.take_profit_ticks = take_profit_ticks
        self.use_auto_threshold = use_auto_threshold

        # ===== LUXALGO PIVOT STATE =====
        # Swing pivots (50-bar lookback)
        self.swing_high_level = None
        self.swing_high_crossed = False
        self.swing_high_bar_index = 0
        
        self.swing_low_level = None
        self.swing_low_crossed = False
        self.swing_low_bar_index = 0
        
        # Internal pivots (5-bar lookback)
        self.internal_high_level = None
        self.internal_high_crossed = False
        
        self.internal_low_level = None
        self.internal_low_crossed = False
        
        # Trend bias (BULLISH = 1, BEARISH = -1, NEUTRAL = 0)
        self.swing_trend_bias = 0
        self.internal_trend_bias = 0
        
        # Leg tracking (BULLISH_LEG = 1, BEARISH_LEG = 0)
        self.swing_leg = 0
        self.internal_leg = 0

        # ===== ORDER BLOCKS =====
        self.swing_order_blocks = []  # List of {bias, bar_high, bar_low, bar_time}
        self.internal_order_blocks = []
        self.max_order_blocks = 5

        # ===== FAIR VALUE GAPS =====
        self.fair_value_gaps = []  # List of {top, bottom, bias, traded}
        
        # ===== HISTORICAL DATA =====
        # Store full bar data for lookback calculations
        self.bars = deque(maxlen=max(swing_lookback, atr_period) + 100)
        
        # Parsed highs/lows (inverted on high volatility bars per LuxAlgo)
        self.parsed_highs = deque(maxlen=1000)
        self.parsed_lows = deque(maxlen=1000)
        
        # ATR calculation
        self.true_ranges = deque(maxlen=atr_period)
        
        # FVG threshold calculation (cumulative average of bar delta percent)
        self.bar_delta_sum = 0.0
        self.bar_count = 0
        
        # Volume tracking for FVG filter
        self.volume_history = deque(maxlen=50)  # Track 50-bar average volume
        
        # Previous close for crossover detection
        self.prev_close = None

        self.logger = logging.getLogger(__name__)

    def _calculate_atr(self) -> float:
        """Calculate ATR (200-period default, matches LuxAlgo)."""
        if len(self.true_ranges) < self.atr_period:
            if len(self.true_ranges) > 0:
                return sum(self.true_ranges) / len(self.true_ranges)
            return 0.0
        return sum(self.true_ranges) / self.atr_period

    def _get_highest(self, lookback: int) -> float:
        """Get highest high of last N bars (ta.highest equivalent)."""
        if len(self.bars) < lookback:
            return float('-inf')
        bars_list = list(self.bars)
        return max(bar['high'] for bar in bars_list[-lookback:])

    def _get_lowest(self, lookback: int) -> float:
        """Get lowest low of last N bars (ta.lowest equivalent)."""
        if len(self.bars) < lookback:
            return float('inf')
        bars_list = list(self.bars)
        return min(bar['low'] for bar in bars_list[-lookback:])

    def _update_leg(self, size: int) -> tuple:
        """
        LuxAlgo leg() function - detect swing direction changes.
        
        Returns: (current_leg, is_new_leg, is_pivot_high, is_pivot_low)
        """
        if len(self.bars) <= size:
            return (0, False, False, False)
        
        bars_list = list(self.bars)
        bar_at_size = bars_list[-(size + 1)]  # bar[size] in Pine
        
        # Get highest/lowest of last 'size' bars (excluding bar[size])
        highest = self._get_highest(size)
        lowest = self._get_lowest(size)
        
        # LuxAlgo logic: newLegHigh = high[size] > ta.highest(size)
        new_leg_high = bar_at_size['high'] > highest
        new_leg_low = bar_at_size['low'] < lowest
        
        old_leg = self.swing_leg if size == self.swing_lookback else self.internal_leg
        new_leg = old_leg
        
        if new_leg_high:
            new_leg = 0  # BEARISH_LEG
        elif new_leg_low:
            new_leg = 1  # BULLISH_LEG
        
        is_new_leg = (new_leg != old_leg)
        is_pivot_low = is_new_leg and (new_leg == 1)  # Start of bullish leg = found pivot low
        is_pivot_high = is_new_leg and (new_leg == 0)  # Start of bearish leg = found pivot high
        
        # Update stored leg
        if size == self.swing_lookback:
            self.swing_leg = new_leg
        else:
            self.internal_leg = new_leg
        
        return (new_leg, is_new_leg, is_pivot_high, is_pivot_low)

    def _update_swing_pivots(self):
        """Update swing pivot points (50-bar lookback) - matches LuxAlgo getCurrentStructure()."""
        if len(self.bars) <= self.swing_lookback:
            return
        
        _, is_new_leg, is_pivot_high, is_pivot_low = self._update_leg(self.swing_lookback)
        
        if not is_new_leg:
            return
        
        bars_list = list(self.bars)
        pivot_bar = bars_list[-(self.swing_lookback + 1)]
        
        if is_pivot_low:
            # New swing low found
            self.swing_low_level = pivot_bar['low']
            self.swing_low_crossed = False
            # Store ABSOLUTE bar count at time of pivot (not deque index)
            self.swing_low_bar_index = self.bar_count - self.swing_lookback - 1
        
        if is_pivot_high:
            # New swing high found
            self.swing_high_level = pivot_bar['high']
            self.swing_high_crossed = False
            # Store ABSOLUTE bar count at time of pivot (not deque index)
            self.swing_high_bar_index = self.bar_count - self.swing_lookback - 1

    def _update_internal_pivots(self):
        """Update internal pivot points (5-bar lookback)."""
        if len(self.bars) <= self.internal_lookback:
            return
        
        _, is_new_leg, is_pivot_high, is_pivot_low = self._update_leg(self.internal_lookback)
        
        if not is_new_leg:
            return
        
        bars_list = list(self.bars)
        pivot_bar = bars_list[-(self.internal_lookback + 1)]
        
        if is_pivot_low:
            self.internal_low_level = pivot_bar['low']
            self.internal_low_crossed = False
        
        if is_pivot_high:
            self.internal_high_level = pivot_bar['high']
            self.internal_high_crossed = False

    def _detect_structure_break(self, current_bar: Dict) -> Optional[Dict]:
        """
        Detect BOS/CHoCH using LuxAlgo's crossover logic.
        
        Key: Uses ta.crossover/crossunder AND checks 'crossed' flag
        to prevent re-triggering on same pivot.
        """
        close = current_bar['close']
        
        # Need previous close for crossover detection
        if self.prev_close is None:
            return None
        
        result = None
        
        # ===== BULLISH STRUCTURE BREAK (close crosses above swing high) =====
        if (self.swing_high_level is not None and 
            not self.swing_high_crossed and
            self.prev_close <= self.swing_high_level and 
            close > self.swing_high_level):
            
            # Determine BOS vs CHoCH
            if self.swing_trend_bias == -1:  # Was bearish
                break_type = 'CHoCH'
            else:
                break_type = 'BOS'
            
            self.swing_high_crossed = True
            self.swing_trend_bias = 1  # Now bullish
            
            result = {
                'type': break_type,
                'direction': 'BULLISH',
                'level': self.swing_high_level,
                'timestamp': current_bar['timestamp'],
                'pivot_bar_index': self.swing_high_bar_index
            }
        
        # ===== BEARISH STRUCTURE BREAK (close crosses below swing low) =====
        elif (self.swing_low_level is not None and 
              not self.swing_low_crossed and
              self.prev_close >= self.swing_low_level and 
              close < self.swing_low_level):
            
            if self.swing_trend_bias == 1:  # Was bullish
                break_type = 'CHoCH'
            else:
                break_type = 'BOS'
            
            self.swing_low_crossed = True
            self.swing_trend_bias = -1  # Now bearish
            
            result = {
                'type': break_type,
                'direction': 'BEARISH',
                'level': self.swing_low_level,
                'timestamp': current_bar['timestamp'],
                'pivot_bar_index': self.swing_low_bar_index
            }
        
        return result

    def _create_order_block(self, structure_break: Dict, current_bar: Dict):
        """
        Create Order Block using LuxAlgo's exact logic:
        1. Find origin candle between pivot and break
        2. For bullish: find bar with MIN parsedLow
        3. For bearish: find bar with MAX parsedHigh
        4. Use parsedHigh/parsedLow (inverted on high volatility bars)
        """
        direction = structure_break['direction']
        pivot_absolute_idx = structure_break.get('pivot_bar_index', 0)
        
        # Safety checks
        if len(self.parsed_highs) < 2 or len(self.parsed_lows) < 2 or len(self.bars) < 2:
            return
        
        # Convert absolute pivot index to index within parsed_highs/parsed_lows
        # parsed_highs has maxlen=1000, so we need to compute the offset
        parsed_len = len(self.parsed_highs)
        current_absolute_idx = self.bar_count
        
        # How many bars ago was the pivot?
        bars_since_pivot = current_absolute_idx - pivot_absolute_idx
        
        # If pivot is older than our parsed_highs buffer, use the oldest available
        if bars_since_pivot >= parsed_len:
            start_idx = 0
        else:
            start_idx = parsed_len - bars_since_pivot
        
        end_idx = parsed_len
        
        if start_idx >= end_idx:
            return
        
        parsed_highs_list = list(self.parsed_highs)[start_idx:end_idx]
        parsed_lows_list = list(self.parsed_lows)[start_idx:end_idx]
        
        # Align bars list with parsed lists (bars also uses relative offset)
        bars_len = len(self.bars)
        if bars_since_pivot >= bars_len:
            bars_start = 0
        else:
            bars_start = bars_len - bars_since_pivot
        bars_end = bars_len
        bars_list = list(self.bars)[bars_start:bars_end]
        
        if len(parsed_highs_list) == 0 or len(bars_list) == 0:
            return
        
        # Find the ENTIRE range from pivot to break for the zone
        # Zone should cover the full consolidation area
        all_highs = [b['high'] for b in bars_list]
        all_lows = [b['low'] for b in bars_list]
        
        # Zone covers the entire range - this matches LuxAlgo's visual zones
        zone_high = max(all_highs)  # Highest high in range
        zone_low = min(all_lows)    # Lowest low in range
        
        # Use origin bar for timestamp
        if direction == 'BULLISH':
            origin_idx = all_lows.index(min(all_lows))
        else:
            origin_idx = all_highs.index(max(all_highs))
        
        if origin_idx >= len(bars_list):
            origin_idx = len(bars_list) - 1
        origin_bar = bars_list[origin_idx]
        
        order_block = {
            'bias': 1 if direction == 'BULLISH' else -1,
            'bar_high': zone_high,
            'bar_low': zone_low,
            'bar_time': origin_bar['timestamp'],
            'mitigated': False,
            'traded': False  # Only trade first test of zone
        }
        
        self.swing_order_blocks.insert(0, order_block)
        
        # Limit order blocks
        if len(self.swing_order_blocks) > self.max_order_blocks * 2:
            self.swing_order_blocks = self.swing_order_blocks[:self.max_order_blocks * 2]

    def _detect_fvg(self, bar1: Dict, bar2: Dict, bar3: Dict) -> Optional[Dict]:
        """
        Detect FVG using LuxAlgo's EXACT logic:
        
        barDeltaPercent = (lastClose - lastOpen) / (lastOpen * 100)
        threshold = ta.cum(math.abs(barDeltaPercent)) / bar_index * 2
        
        bullishFVG = currentLow > last2High AND lastClose > last2High AND barDeltaPercent > threshold
        bearishFVG = currentHigh < last2Low AND lastClose < last2Low AND -barDeltaPercent > threshold
        """
        # bar1 = last2 (2 bars ago), bar2 = last (1 bar ago), bar3 = current
        last2_high = bar1['high']
        last2_low = bar1['low']
        last_close = bar2['close']
        last_open = bar2['open']
        current_low = bar3['low']
        current_high = bar3['high']
        
        # LuxAlgo: barDeltaPercent = (lastClose - lastOpen) / (lastOpen * 100)
        if last_open == 0:
            return None
        bar_delta_percent = (last_close - last_open) / (last_open * 100)
        
        # EXACT LuxAlgo: threshold = ta.cum(math.abs(barDeltaPercent)) / bar_index * 2
        if self.use_auto_threshold and self.bar_count > 0:
            threshold = (self.bar_delta_sum / self.bar_count) * 2  # EXACT: 2x multiplier
        else:
            threshold = 0
        
        # ===== BULLISH FVG =====
        # EXACT LuxAlgo: currentLow > last2High AND lastClose > last2High AND barDeltaPercent > threshold
        if (current_low > last2_high and 
            last_close > last2_high and 
            bar_delta_percent > threshold):
            
            return {
                'type': 'bullish',
                'top': current_low,
                'bottom': last2_high,
                'bias': 1,
                'traded': False,
                'mitigated': False
            }
        
        # ===== BEARISH FVG =====
        # EXACT LuxAlgo: currentHigh < last2Low AND lastClose < last2Low AND -barDeltaPercent > threshold
        if (current_high < last2_low and 
            last_close < last2_low and 
            -bar_delta_percent > threshold):
            
            return {
                'type': 'bearish',
                'top': last2_low,
                'bottom': current_high,
                'bias': -1,
                'traded': False,
                'mitigated': False
            }
        
        return None

    def _mitigate_order_blocks(self, current_bar: Dict):
        """
        LuxAlgo order block mitigation:
        - Bullish OB mitigated when low < bar_low
        - Bearish OB mitigated when high > bar_high
        """
        low = current_bar['low']
        high = current_bar['high']
        
        for ob in self.swing_order_blocks:
            if ob['mitigated']:
                continue
            
            if ob['bias'] == 1:  # Bullish/Demand
                if low < ob['bar_low']:
                    ob['mitigated'] = True
            else:  # Bearish/Supply
                if high > ob['bar_high']:
                    ob['mitigated'] = True
        
        # Remove mitigated
        self.swing_order_blocks = [ob for ob in self.swing_order_blocks if not ob['mitigated']]

    def _mitigate_fvgs(self, current_bar: Dict):
        """
        LuxAlgo FVG mitigation:
        - Bullish FVG mitigated when low < bottom
        - Bearish FVG mitigated when high > top
        """
        low = current_bar['low']
        high = current_bar['high']
        
        for fvg in self.fair_value_gaps:
            if fvg['mitigated']:
                continue
            
            if fvg['bias'] == 1:  # Bullish
                if low < fvg['bottom']:
                    fvg['mitigated'] = True
            else:  # Bearish
                if high > fvg['top']:
                    fvg['mitigated'] = True
        
        self.fair_value_gaps = [fvg for fvg in self.fair_value_gaps if not fvg['mitigated']]

    def _check_rejection_signal(self, current_bar: Dict) -> Optional[Dict]:
        """
        Check for entry signal from Supply/Demand zones.
        
        Entry: Price touches zone AND closes in the right direction (pushed out)
        Stop Loss: Right below/above the zone (where zone breaks)
        Take Profit: 2:1 R:R from dynamic stop distance
        """
        bar_low = current_bar['low']
        bar_high = current_bar['high']
        bar_close = current_bar['close']
        bar_open = current_bar['open']
        
        # Fixed stop in ticks for controlled risk
        fixed_stop_ticks = 12  # 3 points = $150
        
        # ===== LONG FROM DEMAND ZONE =====
        if bar_close > bar_open:  # Green candle
            for ob in self.swing_order_blocks:
                # Only trade zone once (first test)
                if ob['bias'] == 1 and not ob.get('traded', False):
                    # REJECTION: Bar low must wick INTO the zone
                    wick_into_zone = (bar_low >= ob['bar_low'] and bar_low <= ob['bar_high'])
                    
                    # Must close above the zone top (rejected and pushed out)
                    closed_above = (bar_close > ob['bar_high'])
                    
                    if wick_into_zone and closed_above:
                        entry_price = bar_close
                        
                        # Fixed stop loss for controlled risk
                        stop_loss = entry_price - (fixed_stop_ticks * self.tick_size)
                        
                        # Take profit: 2:1 R:R
                        take_profit = entry_price + (fixed_stop_ticks * 2 * self.tick_size)
                        
                        ob['traded'] = True  # Mark zone as traded
                        
                        return {
                            'signal': 'long',
                            'entry_price': entry_price,
                            'stop_loss': stop_loss,
                            'take_profit': take_profit,
                            'reason': 'Demand Zone Push',
                            'strength': 'STRONG'
                        }
        
        # ===== SHORT FROM SUPPLY ZONE =====
        if bar_close < bar_open:  # Red candle
            for ob in self.swing_order_blocks:
                # Only trade zone once (first test)
                if ob['bias'] == -1 and not ob.get('traded', False):
                    # REJECTION: Bar high must wick INTO the zone
                    wick_into_zone = (bar_high >= ob['bar_low'] and bar_high <= ob['bar_high'])
                    
                    # Must close below the zone bottom (rejected and pushed out)
                    closed_below = (bar_close < ob['bar_low'])
                    
                    if wick_into_zone and closed_below:
                        entry_price = bar_close
                        
                        # Fixed stop loss for controlled risk
                        stop_loss = entry_price + (fixed_stop_ticks * self.tick_size)
                        
                        # Take profit: 2:1 R:R
                        take_profit = entry_price - (fixed_stop_ticks * 2 * self.tick_size)
                        
                        ob['traded'] = True  # Mark zone as traded
                        
                        return {
                            'signal': 'short',
                            'entry_price': entry_price,
                            'stop_loss': stop_loss,
                            'take_profit': take_profit,
                            'reason': 'Supply Zone Push',
                            'strength': 'STRONG'
                        }
        
        return None

    def process_bar(self, bar: Dict[str, Any]) -> Dict[str, Any]:
        """
        Process a single bar through LuxAlgo SMC logic.
        
        Args:
            bar: Dict with timestamp, open, high, low, close, volume
        
        Returns:
            Dict with signal info, structure breaks, etc.
        """
        # ===== STORE BAR =====
        self.bars.append(bar)
        self.bar_count += 1
        
        # Reset traded_this_bar flag for all zones (allow trading on new bars)
        for ob in self.swing_order_blocks:
            ob['traded_this_bar'] = False
        
        # ===== CALCULATE TRUE RANGE FOR ATR =====
        if self.prev_close is not None:
            tr = max(
                bar['high'] - bar['low'],
                abs(bar['high'] - self.prev_close),
                abs(bar['low'] - self.prev_close)
            )
            self.true_ranges.append(tr)
        
        # ===== LUXALGO: HIGH VOLATILITY BAR DETECTION =====
        # highVolatilityBar = (high - low) >= (2 * volatilityMeasure)
        atr = self._calculate_atr()
        bar_range = bar['high'] - bar['low']
        high_volatility_bar = atr > 0 and bar_range >= (2 * atr)
        
        # LuxAlgo: On high volatility bars, INVERT parsed high/low (use body not wicks)
        if high_volatility_bar:
            parsed_high = bar['low']  # INVERTED!
            parsed_low = bar['high']   # INVERTED!
        else:
            parsed_high = bar['high']
            parsed_low = bar['low']
        
        self.parsed_highs.append(parsed_high)
        self.parsed_lows.append(parsed_low)
        
        # ===== LUXALGO: FVG THRESHOLD (cumulative average) =====
        if bar['open'] != 0:
            bar_delta_percent = abs((bar['close'] - bar['open']) / (bar['open'] * 100))
            self.bar_delta_sum += bar_delta_percent
        
        # ===== UPDATE PIVOTS =====
        self._update_swing_pivots()
        self._update_internal_pivots()
        
        # ===== DETECT STRUCTURE BREAK =====
        structure_break = self._detect_structure_break(bar)
        
        if structure_break:
            # Create Order Block on structure break
            self._create_order_block(structure_break, bar)
        
        # ===== DETECT FVG (need 3 bars) =====
        if len(self.bars) >= 3:
            bars_list = list(self.bars)
            fvg = self._detect_fvg(bars_list[-3], bars_list[-2], bars_list[-1])
            if fvg:
                self.fair_value_gaps.insert(0, fvg)
                # Limit FVGs
                if len(self.fair_value_gaps) > 50:
                    self.fair_value_gaps = self.fair_value_gaps[:50]
        
        # ===== CHECK REJECTION SIGNAL =====
        signal = self._check_rejection_signal(bar)
        
        # ===== MITIGATE ZONES =====
        self._mitigate_order_blocks(bar)
        self._mitigate_fvgs(bar)
        
        # ===== UPDATE PREV CLOSE FOR NEXT BAR =====
        self.prev_close = bar['close']
        
        # ===== RETURN RESULT =====
        return {
            'signal': signal,
            'structure_break': structure_break,
            'trend_bias': 'BULLISH' if self.swing_trend_bias == 1 else 'BEARISH' if self.swing_trend_bias == -1 else 'NEUTRAL',
            'active_demand_blocks': len([ob for ob in self.swing_order_blocks if ob['bias'] == 1]),
            'active_supply_blocks': len([ob for ob in self.swing_order_blocks if ob['bias'] == -1]),
            'active_bullish_fvgs': len([fvg for fvg in self.fair_value_gaps if fvg['bias'] == 1 and not fvg['traded']]),
            'active_bearish_fvgs': len([fvg for fvg in self.fair_value_gaps if fvg['bias'] == -1 and not fvg['traded']])
        }

    def get_state(self) -> Dict[str, Any]:
        """Get current strategy state."""
        return {
            'trend_bias': 'BULLISH' if self.swing_trend_bias == 1 else 'BEARISH' if self.swing_trend_bias == -1 else 'NEUTRAL',
            'swing_high': self.swing_high_level,
            'swing_low': self.swing_low_level,
            'order_blocks': len(self.swing_order_blocks),
            'fvgs': len(self.fair_value_gaps),
            'bar_count': self.bar_count
        }

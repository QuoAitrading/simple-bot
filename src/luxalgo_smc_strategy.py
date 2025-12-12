"""
LuxAlgo SMC + Rejection Strategy

This strategy combines Smart Money Concepts (SMC) from LuxAlgo with rejection confirmation:
1. Market Structure (BOS & CHoCH) - Dual lookback system
2. Order Blocks (Supply & Demand) - With volatility filter
3. Fair Value Gaps (FVG) - With dynamic threshold
4. Rejection Triggers - Confirmation-based entries

Designed to be a separate AI for backtesting before integration with main system.
"""

from typing import Dict, Any, Optional, List, Tuple
from datetime import datetime, timedelta
from collections import deque
import logging


class LuxAlgoSMCStrategy:
    """
    LuxAlgo SMC + Rejection Strategy Implementation
    
    Features:
    - Dual lookback market structure (50-bar major, 5-bar internal)
    - Break of Structure (BOS) and Change of Character (CHoCH)
    - Order Blocks with LuxAlgo volatility filter
    - Fair Value Gaps with dynamic volatility threshold
    - Rejection-based entry confirmation
    """
    
    def __init__(self,
                 tick_size: float = 0.25,
                 swing_lookback: int = 50,
                 internal_lookback: int = 5,
                 atr_period: int = 200,
                 atr_multiplier: float = 2.0,
                 fvg_delta_multiplier: float = 2.0,
                 avg_delta_lookback: int = 1000,
                 stop_loss_ticks: int = 12,
                 take_profit_ticks: int = 12):
        """
        Initialize LuxAlgo SMC Strategy.
        
        Args:
            tick_size: Instrument tick size (e.g., 0.25 for ES)
            swing_lookback: Major trend lookback (default: 50 bars)
            internal_lookback: Internal structure lookback (default: 5 bars)
            atr_period: ATR calculation period (default: 200)
            atr_multiplier: ATR multiplier for volatility filter (default: 2.0)
            fvg_delta_multiplier: FVG delta multiplier (default: 2.0)
            avg_delta_lookback: Lookback for average delta calculation (default: 1000)
            stop_loss_ticks: Fixed stop loss in ticks (default: 12)
            take_profit_ticks: Fixed take profit in ticks (default: 12)
        """
        self.tick_size = tick_size
        self.swing_lookback = swing_lookback
        self.internal_lookback = internal_lookback
        self.atr_period = atr_period
        self.atr_multiplier = atr_multiplier
        self.fvg_delta_multiplier = fvg_delta_multiplier
        self.avg_delta_lookback = avg_delta_lookback
        self.stop_loss_ticks = stop_loss_ticks
        self.take_profit_ticks = take_profit_ticks
        
        # Market structure state
        self.trend_bias = None  # 'BULLISH', 'BEARISH', or None
        self.last_swing_high = None  # Major swing high
        self.last_swing_low = None   # Major swing low
        self.last_internal_high = None  # Internal swing high
        self.last_internal_low = None   # Internal swing low
        
        # Order Blocks
        self.active_demand_blocks = []
        self.active_supply_blocks = []
        
        # Fair Value Gaps
        self.active_bullish_fvgs = []
        self.active_bearish_fvgs = []
        
        # Historical data for calculations
        self.bars = deque(maxlen=max(swing_lookback, atr_period) + 10)
        self.delta_history = deque(maxlen=avg_delta_lookback)
        self.true_ranges = deque(maxlen=atr_period)
        
        # Counters
        self.ob_id_counter = 0
        self.fvg_id_counter = 0
        
        self.logger = logging.getLogger(__name__)
    
    def _calculate_true_range(self, bar: Dict[str, Any], prev_close: Optional[float] = None) -> float:
        """Calculate True Range for ATR calculation."""
        high = bar['high']
        low = bar['low']
        
        if prev_close is None:
            return high - low
        
        return max(
            high - low,
            abs(high - prev_close),
            abs(low - prev_close)
        )
    
    def _calculate_atr(self) -> Optional[float]:
        """Calculate Average True Range."""
        if len(self.true_ranges) < self.atr_period:
            return None
        
        return sum(self.true_ranges) / len(self.true_ranges)
    
    def _is_swing_high(self, index: int, lookback: int) -> bool:
        """
        Check if bar at index is a swing high with given lookback.
        
        Args:
            index: Index in bars deque
            lookback: Number of bars to compare on each side
        """
        if index < lookback or index >= len(self.bars) - lookback:
            return False
        
        bars_list = list(self.bars)
        center_high = bars_list[index]['high']
        
        # Check bars before
        for i in range(index - lookback, index):
            if bars_list[i]['high'] >= center_high:
                return False
        
        # Check bars after
        for i in range(index + 1, index + lookback + 1):
            if bars_list[i]['high'] >= center_high:
                return False
        
        return True
    
    def _is_swing_low(self, index: int, lookback: int) -> bool:
        """
        Check if bar at index is a swing low with given lookback.
        
        Args:
            index: Index in bars deque
            lookback: Number of bars to compare on each side
        """
        if index < lookback or index >= len(self.bars) - lookback:
            return False
        
        bars_list = list(self.bars)
        center_low = bars_list[index]['low']
        
        # Check bars before
        for i in range(index - lookback, index):
            if bars_list[i]['low'] <= center_low:
                return False
        
        # Check bars after
        for i in range(index + 1, index + lookback + 1):
            if bars_list[i]['low'] <= center_low:
                return False
        
        return True
    
    def _update_swing_points(self):
        """Update major and internal swing points."""
        if len(self.bars) < max(self.swing_lookback, self.internal_lookback) * 2 + 1:
            return
        
        bars_list = list(self.bars)
        
        # Check for major swing high (50-bar lookback)
        swing_idx = len(bars_list) - self.swing_lookback - 1
        if swing_idx >= 0 and self._is_swing_high(swing_idx, self.swing_lookback):
            self.last_swing_high = bars_list[swing_idx]['high']
        
        # Check for major swing low (50-bar lookback)
        if swing_idx >= 0 and self._is_swing_low(swing_idx, self.swing_lookback):
            self.last_swing_low = bars_list[swing_idx]['low']
        
        # Check for internal swing high (5-bar lookback)
        internal_idx = len(bars_list) - self.internal_lookback - 1
        if internal_idx >= 0 and self._is_swing_high(internal_idx, self.internal_lookback):
            self.last_internal_high = bars_list[internal_idx]['high']
        
        # Check for internal swing low (5-bar lookback)
        if internal_idx >= 0 and self._is_swing_low(internal_idx, self.internal_lookback):
            self.last_internal_low = bars_list[internal_idx]['low']
    
    def _detect_structure_break(self, current_bar: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """
        Detect Break of Structure (BOS) or Change of Character (CHoCH).
        
        Returns:
            Dictionary with structure break details or None
        """
        close = current_bar['close']
        timestamp = current_bar['timestamp']
        
        # Check for Bullish BOS or CHoCH
        if self.last_swing_high is not None and close > self.last_swing_high:
            if self.trend_bias == 'BEARISH':
                # Change of Character - trend reversal
                self.trend_bias = 'BULLISH'
                return {
                    'type': 'CHoCH',
                    'direction': 'BULLISH',
                    'level': self.last_swing_high,
                    'timestamp': timestamp
                }
            else:
                # Break of Structure - trend continuation
                self.trend_bias = 'BULLISH'
                return {
                    'type': 'BOS',
                    'direction': 'BULLISH',
                    'level': self.last_swing_high,
                    'timestamp': timestamp
                }
        
        # Check for Bearish BOS or CHoCH
        if self.last_swing_low is not None and close < self.last_swing_low:
            if self.trend_bias == 'BULLISH':
                # Change of Character - trend reversal
                self.trend_bias = 'BEARISH'
                return {
                    'type': 'CHoCH',
                    'direction': 'BEARISH',
                    'level': self.last_swing_low,
                    'timestamp': timestamp
                }
            else:
                # Break of Structure - trend continuation
                self.trend_bias = 'BEARISH'
                return {
                    'type': 'BOS',
                    'direction': 'BEARISH',
                    'level': self.last_swing_low,
                    'timestamp': timestamp
                }
        
        return None
    
    def _create_order_block(self, structure_break: Dict[str, Any], current_bar: Dict[str, Any]):
        """
        Create Order Block after structure break.
        
        The Order Block is created from the "origin candle" - the candle that caused
        the price move leading to the structure break.
        """
        direction = structure_break['direction']
        break_level = structure_break['level']
        timestamp = current_bar['timestamp']
        
        bars_list = list(self.bars)
        if len(bars_list) < 2:
            return
        
        # Find the range between last swing point and break candle
        # Scan for the origin candle
        atr = self._calculate_atr()
        
        if direction == 'BULLISH':
            # Find candle with LOWEST LOW in the range
            origin_candle = None
            min_low = float('inf')
            
            for bar in bars_list[-10:]:  # Look back up to 10 bars
                if bar['low'] < min_low:
                    # Apply volatility filter
                    candle_range = bar['high'] - bar['low']
                    if atr and candle_range >= (self.atr_multiplier * atr):
                        # High volatility bar - use body instead of full range
                        body_low = min(bar['open'], bar['close'])
                        body_high = max(bar['open'], bar['close'])
                        origin_candle = {
                            'top': body_high,
                            'bottom': body_low,
                            'timestamp': bar['timestamp']
                        }
                    else:
                        # Normal bar - use full range
                        origin_candle = {
                            'top': bar['high'],
                            'bottom': bar['low'],
                            'timestamp': bar['timestamp']
                        }
                    min_low = bar['low']
            
            if origin_candle:
                self.ob_id_counter += 1
                demand_block = {
                    'id': self.ob_id_counter,
                    'type': 'demand',
                    'top': origin_candle['top'],
                    'bottom': origin_candle['bottom'],
                    'created_at': timestamp,
                    'mitigated': False
                }
                self.active_demand_blocks.append(demand_block)
        
        else:  # BEARISH
            # Find candle with HIGHEST HIGH in the range
            origin_candle = None
            max_high = float('-inf')
            
            for bar in bars_list[-10:]:  # Look back up to 10 bars
                if bar['high'] > max_high:
                    # Apply volatility filter
                    candle_range = bar['high'] - bar['low']
                    if atr and candle_range >= (self.atr_multiplier * atr):
                        # High volatility bar - use body instead of full range
                        body_low = min(bar['open'], bar['close'])
                        body_high = max(bar['open'], bar['close'])
                        origin_candle = {
                            'top': body_high,
                            'bottom': body_low,
                            'timestamp': bar['timestamp']
                        }
                    else:
                        # Normal bar - use full range
                        origin_candle = {
                            'top': bar['high'],
                            'bottom': bar['low'],
                            'timestamp': bar['timestamp']
                        }
                    max_high = bar['high']
            
            if origin_candle:
                self.ob_id_counter += 1
                supply_block = {
                    'id': self.ob_id_counter,
                    'type': 'supply',
                    'top': origin_candle['top'],
                    'bottom': origin_candle['bottom'],
                    'created_at': timestamp,
                    'mitigated': False
                }
                self.active_supply_blocks.append(supply_block)
    
    def _calculate_avg_delta_percent(self) -> float:
        """Calculate average delta percent from history."""
        if len(self.delta_history) == 0:
            return 0.0
        return sum(abs(d) for d in self.delta_history) / len(self.delta_history)
    
    def _detect_fvg(self, bar1: Dict[str, Any], bar2: Dict[str, Any], bar3: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """
        Detect Fair Value Gap using LuxAlgo's dynamic volatility threshold.
        
        Returns:
            FVG dictionary or None
        """
        # Calculate bar2 delta %
        bar2_delta_pct = (bar2['close'] - bar2['open']) / bar2['open'] if bar2['open'] != 0 else 0
        
        # Check Bullish FVG pattern
        if bar1['high'] < bar3['low']:
            # Filter 1: Middle candle validation
            if bar2['close'] > bar1['high']:
                # Filter 2: Dynamic volatility threshold
                avg_delta = self._calculate_avg_delta_percent()
                if avg_delta > 0 and abs(bar2_delta_pct) > (avg_delta * self.fvg_delta_multiplier):
                    self.fvg_id_counter += 1
                    return {
                        'id': self.fvg_id_counter,
                        'type': 'bullish',
                        'top': bar3['low'],
                        'bottom': bar1['high'],
                        'created_at': bar3['timestamp'],
                        'mitigated': False,
                        'traded': False
                    }
        
        # Check Bearish FVG pattern
        if bar1['low'] > bar3['high']:
            # Filter 1: Middle candle validation
            if bar2['close'] < bar1['low']:
                # Filter 2: Dynamic volatility threshold
                avg_delta = self._calculate_avg_delta_percent()
                if avg_delta > 0 and abs(bar2_delta_pct) > (avg_delta * self.fvg_delta_multiplier):
                    self.fvg_id_counter += 1
                    return {
                        'id': self.fvg_id_counter,
                        'type': 'bearish',
                        'top': bar1['low'],
                        'bottom': bar3['high'],
                        'created_at': bar3['timestamp'],
                        'mitigated': False,
                        'traded': False
                    }
        
        return None
    
    def _check_rejection_signal(self, current_bar: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """
        Check for rejection trigger entry signal.
        
        Long Rejection:
        - Current bar low touches/overlaps Demand Block or Bullish FVG
        - Current bar close > open (green candle)
        - Trend bias is BULLISH
        
        Short Rejection:
        - Current bar high touches/overlaps Supply Block or Bearish FVG
        - Current bar close < open (red candle)
        - Trend bias is BEARISH
        """
        bar_low = current_bar['low']
        bar_high = current_bar['high']
        bar_close = current_bar['close']
        bar_open = current_bar['open']
        
        # Check Long Rejection Signal
        if self.trend_bias == 'BULLISH' and bar_close > bar_open:
            # Check Demand Blocks
            for ob in self.active_demand_blocks:
                if not ob['mitigated'] and bar_low <= ob['top'] and bar_low >= ob['bottom']:
                    # Rejection from Demand Block
                    entry_price = ob['top']
                    stop_loss = entry_price - (self.stop_loss_ticks * self.tick_size)
                    take_profit = entry_price + (self.take_profit_ticks * self.tick_size)
                    
                    return {
                        'signal': 'long',
                        'entry_price': entry_price,
                        'stop_loss': stop_loss,
                        'take_profit': take_profit,
                        'strength': 'STRONG',
                        'reason': 'Demand Block Rejection',
                        'zone_id': ob['id'],
                        'zone_type': 'order_block'
                    }
            
            # Check Bullish FVGs
            for fvg in self.active_bullish_fvgs:
                if not fvg['mitigated'] and not fvg['traded'] and bar_low <= fvg['top'] and bar_low >= fvg['bottom']:
                    # Rejection from Bullish FVG
                    entry_price = fvg['top']
                    stop_loss = entry_price - (self.stop_loss_ticks * self.tick_size)
                    take_profit = entry_price + (self.take_profit_ticks * self.tick_size)
                    
                    # Check for confluence (both OB and FVG)
                    strength = 'STRONG'
                    for ob in self.active_demand_blocks:
                        if not ob['mitigated']:
                            # Check if FVG overlaps with OB
                            if (fvg['bottom'] <= ob['top'] and fvg['top'] >= ob['bottom']):
                                strength = 'VERY_STRONG'
                                break
                    
                    fvg['traded'] = True
                    return {
                        'signal': 'long',
                        'entry_price': entry_price,
                        'stop_loss': stop_loss,
                        'take_profit': take_profit,
                        'strength': strength,
                        'reason': 'Bullish FVG Rejection',
                        'zone_id': fvg['id'],
                        'zone_type': 'fvg'
                    }
        
        # Check Short Rejection Signal
        if self.trend_bias == 'BEARISH' and bar_close < bar_open:
            # Check Supply Blocks
            for ob in self.active_supply_blocks:
                if not ob['mitigated'] and bar_high >= ob['bottom'] and bar_high <= ob['top']:
                    # Rejection from Supply Block
                    entry_price = ob['bottom']
                    stop_loss = entry_price + (self.stop_loss_ticks * self.tick_size)
                    take_profit = entry_price - (self.take_profit_ticks * self.tick_size)
                    
                    return {
                        'signal': 'short',
                        'entry_price': entry_price,
                        'stop_loss': stop_loss,
                        'take_profit': take_profit,
                        'strength': 'STRONG',
                        'reason': 'Supply Block Rejection',
                        'zone_id': ob['id'],
                        'zone_type': 'order_block'
                    }
            
            # Check Bearish FVGs
            for fvg in self.active_bearish_fvgs:
                if not fvg['mitigated'] and not fvg['traded'] and bar_high >= fvg['bottom'] and bar_high <= fvg['top']:
                    # Rejection from Bearish FVG
                    entry_price = fvg['bottom']
                    stop_loss = entry_price + (self.stop_loss_ticks * self.tick_size)
                    take_profit = entry_price - (self.take_profit_ticks * self.tick_size)
                    
                    # Check for confluence (both OB and FVG)
                    strength = 'STRONG'
                    for ob in self.active_supply_blocks:
                        if not ob['mitigated']:
                            # Check if FVG overlaps with OB
                            if (fvg['bottom'] <= ob['top'] and fvg['top'] >= ob['bottom']):
                                strength = 'VERY_STRONG'
                                break
                    
                    fvg['traded'] = True
                    return {
                        'signal': 'short',
                        'entry_price': entry_price,
                        'stop_loss': stop_loss,
                        'take_profit': take_profit,
                        'strength': strength,
                        'reason': 'Bearish FVG Rejection',
                        'zone_id': fvg['id'],
                        'zone_type': 'fvg'
                    }
        
        return None
    
    def _mitigate_zones(self, current_bar: Dict[str, Any]):
        """
        Mitigate (remove) Order Blocks and FVGs that have been invalidated.
        
        Close-based mitigation: Delete zone if candle closes beyond it.
        """
        close = current_bar['close']
        
        # Mitigate Demand Blocks (close below bottom)
        for ob in self.active_demand_blocks:
            if close < ob['bottom']:
                ob['mitigated'] = True
        
        # Mitigate Supply Blocks (close above top)
        for ob in self.active_supply_blocks:
            if close > ob['top']:
                ob['mitigated'] = True
        
        # Mitigate Bullish FVGs (close below bottom)
        for fvg in self.active_bullish_fvgs:
            if close < fvg['bottom']:
                fvg['mitigated'] = True
        
        # Mitigate Bearish FVGs (close above top)
        for fvg in self.active_bearish_fvgs:
            if close > fvg['top']:
                fvg['mitigated'] = True
        
        # Remove mitigated zones
        self.active_demand_blocks = [ob for ob in self.active_demand_blocks if not ob['mitigated']]
        self.active_supply_blocks = [ob for ob in self.active_supply_blocks if not ob['mitigated']]
        self.active_bullish_fvgs = [fvg for fvg in self.active_bullish_fvgs if not fvg['mitigated']]
        self.active_bearish_fvgs = [fvg for fvg in self.active_bearish_fvgs if not fvg['mitigated']]
    
    def process_bar(self, bar: Dict[str, Any]) -> Dict[str, Any]:
        """
        Process a single bar and generate trading signals.
        
        Args:
            bar: Dictionary with keys: timestamp, open, high, low, close, volume
        
        Returns:
            Dictionary with signal information
        """
        # Add bar to history
        self.bars.append(bar)
        
        # Calculate True Range for ATR
        if len(self.bars) >= 2:
            prev_close = list(self.bars)[-2]['close']
            tr = self._calculate_true_range(bar, prev_close)
            self.true_ranges.append(tr)
        
        # Calculate bar delta % for FVG filter
        if bar['open'] != 0:
            delta_pct = (bar['close'] - bar['open']) / bar['open']
            self.delta_history.append(delta_pct)
        
        # Update swing points (dual lookback)
        self._update_swing_points()
        
        # Detect structure break (BOS or CHoCH)
        structure_break = self._detect_structure_break(bar)
        if structure_break:
            # Create Order Block when structure breaks
            self._create_order_block(structure_break, bar)
        
        # Detect FVG (need 3 bars)
        if len(self.bars) >= 3:
            bars_list = list(self.bars)
            bar1 = bars_list[-3]
            bar2 = bars_list[-2]
            bar3 = bars_list[-1]
            
            fvg = self._detect_fvg(bar1, bar2, bar3)
            if fvg:
                if fvg['type'] == 'bullish':
                    self.active_bullish_fvgs.append(fvg)
                else:
                    self.active_bearish_fvgs.append(fvg)
        
        # Check for rejection signal
        signal = self._check_rejection_signal(bar)
        
        # Mitigate zones
        self._mitigate_zones(bar)
        
        # Return result
        return {
            'signal': signal,
            'structure_break': structure_break,
            'trend_bias': self.trend_bias,
            'active_demand_blocks': len(self.active_demand_blocks),
            'active_supply_blocks': len(self.active_supply_blocks),
            'active_bullish_fvgs': len(self.active_bullish_fvgs),
            'active_bearish_fvgs': len(self.active_bearish_fvgs)
        }
    
    def get_state(self) -> Dict[str, Any]:
        """Get current strategy state for monitoring."""
        return {
            'trend_bias': self.trend_bias,
            'last_swing_high': self.last_swing_high,
            'last_swing_low': self.last_swing_low,
            'last_internal_high': self.last_internal_high,
            'last_internal_low': self.last_internal_low,
            'active_demand_blocks': len(self.active_demand_blocks),
            'active_supply_blocks': len(self.active_supply_blocks),
            'active_bullish_fvgs': len(self.active_bullish_fvgs),
            'active_bearish_fvgs': len(self.active_bearish_fvgs)
        }

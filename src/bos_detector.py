"""
BOS (Break of Structure) Detector

Detects trend changes using swing high/low breaks.
Part of the BOS + FVG Scalping Strategy.

BOS Logic:
- Bullish BOS: Price breaks above the previous swing high
- Bearish BOS: Price breaks below the previous swing low

Swing Point Detection:
- 5-bar lookback (2 bars before, 2 bars after)
- Swing high: middle bar's high > all 4 surrounding bars
- Swing low: middle bar's low < all 4 surrounding bars
"""

from typing import Dict, Any, Optional, List, Tuple
from datetime import datetime


class BOSDetector:
    """
    Detects Break of Structure (BOS) patterns for trend identification.
    
    This detector identifies when price breaks through previous swing highs or lows,
    indicating a potential trend change or continuation.
    """
    
    def __init__(self, swing_lookback: int = 5):
        """
        Initialize BOS detector.
        
        Args:
            swing_lookback: Number of bars to use for swing point detection (default: 5)
        """
        self.swing_lookback = swing_lookback
        self.last_swing_high = None
        self.last_swing_low = None
        self.current_bos_direction = None  # 'bullish', 'bearish', or None
        self.bos_level = None
        self.bos_timestamp = None
    
    def is_swing_high(self, bars: List[Dict[str, Any]], index: int) -> bool:
        """
        Check if a bar at given index is a swing high.
        
        A bar is a swing high if its high is greater than the highs of
        2 bars before it and 2 bars after it.
        
        Args:
            bars: List of OHLCV bars
            index: Index of bar to check
            
        Returns:
            True if bar is a swing high
        """
        # Need at least 5 bars and index must allow 2 bars on each side
        if len(bars) < 5 or index < 2 or index >= len(bars) - 2:
            return False
        
        high = bars[index]['high']
        
        # Check if this high is greater than all surrounding bars
        return (high > bars[index - 2]['high'] and
                high > bars[index - 1]['high'] and
                high > bars[index + 1]['high'] and
                high > bars[index + 2]['high'])
    
    def is_swing_low(self, bars: List[Dict[str, Any]], index: int) -> bool:
        """
        Check if a bar at given index is a swing low.
        
        A bar is a swing low if its low is less than the lows of
        2 bars before it and 2 bars after it.
        
        Args:
            bars: List of OHLCV bars
            index: Index of bar to check
            
        Returns:
            True if bar is a swing low
        """
        # Need at least 5 bars and index must allow 2 bars on each side
        if len(bars) < 5 or index < 2 or index >= len(bars) - 2:
            return False
        
        low = bars[index]['low']
        
        # Check if this low is less than all surrounding bars
        return (low < bars[index - 2]['low'] and
                low < bars[index - 1]['low'] and
                low < bars[index + 1]['low'] and
                low < bars[index + 2]['low'])
    
    def update_swing_points(self, bars: List[Dict[str, Any]]) -> None:
        """
        Update the last known swing high and swing low.
        
        This scans recent bars to identify and store swing points.
        
        Args:
            bars: List of OHLCV bars (must have at least 5 bars)
        """
        if len(bars) < 5:
            return
        
        # Check the bar at index -3 (we need 2 bars after it for confirmation)
        check_index = len(bars) - 3
        
        if self.is_swing_high(bars, check_index):
            self.last_swing_high = bars[check_index]['high']
        
        if self.is_swing_low(bars, check_index):
            self.last_swing_low = bars[check_index]['low']
    
    def detect_bos(self, current_bar: Dict[str, Any]) -> Tuple[Optional[str], Optional[float]]:
        """
        Detect if a Break of Structure occurred.
        
        Bullish BOS: Current close > last swing high
        Bearish BOS: Current close < last swing low
        
        Args:
            current_bar: Current bar with close price
            
        Returns:
            Tuple of (bos_direction, bos_level) where:
            - bos_direction: 'bullish', 'bearish', or None
            - bos_level: Price level where BOS occurred (swing high/low)
        """
        current_close = current_bar['close']
        
        # Check for Bullish BOS
        if self.last_swing_high is not None and current_close > self.last_swing_high:
            self.current_bos_direction = 'bullish'
            self.bos_level = self.last_swing_high
            self.bos_timestamp = current_bar.get('timestamp')
            return 'bullish', self.last_swing_high
        
        # Check for Bearish BOS
        if self.last_swing_low is not None and current_close < self.last_swing_low:
            self.current_bos_direction = 'bearish'
            self.bos_level = self.last_swing_low
            self.bos_timestamp = current_bar.get('timestamp')
            return 'bearish', self.last_swing_low
        
        return None, None
    
    def get_current_trend(self) -> Optional[str]:
        """
        Get the current trend direction based on most recent BOS.
        
        Returns:
            'bullish', 'bearish', or None
        """
        return self.current_bos_direction
    
    def process_bar(self, bars: List[Dict[str, Any]]) -> Tuple[Optional[str], Optional[float]]:
        """
        Process a new bar and check for BOS.
        
        This is the main entry point for bar-by-bar processing.
        
        Args:
            bars: Complete list of bars including the new bar
            
        Returns:
            Tuple of (bos_direction, bos_level) or (None, None)
        """
        # Update swing points first
        self.update_swing_points(bars)
        
        # Check for BOS on current bar
        if len(bars) > 0:
            return self.detect_bos(bars[-1])
        
        return None, None

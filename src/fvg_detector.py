"""
FVG (Fair Value Gap) Detector

Detects 3-candle imbalance patterns where price moves so fast it leaves gaps.
Part of the BOS + FVG Scalping Strategy.

FVG Logic:
- Bullish FVG: bar1.high < bar3.low (gap between them, price jumped up)
- Bearish FVG: bar1.low > bar3.high (gap between them, price dropped down)

Gap Size Filter:
- Minimum: 2 ticks (filters out noise)
- Maximum: 20 ticks (filters out extreme moves)

FVG Expiry:
- Each FVG expires after 60 minutes if not filled
- Prevents stale zones from cluttering the system
"""

from typing import Dict, Any, Optional, List, Tuple
from datetime import datetime, timedelta
from collections import deque


class FVGDetector:
    """
    Detects Fair Value Gap (FVG) patterns for mean reversion trading.
    
    FVGs represent price inefficiencies that tend to get filled.
    """
    
    def __init__(self, 
                 tick_size: float = 0.25,
                 min_fvg_size_ticks: int = 2,
                 max_fvg_size_ticks: int = 20,
                 fvg_expiry_minutes: int = 60,
                 max_active_fvgs: int = 10):
        """
        Initialize FVG detector.
        
        Args:
            tick_size: Instrument tick size (e.g., 0.25 for ES)
            min_fvg_size_ticks: Minimum gap size in ticks (default: 2)
            max_fvg_size_ticks: Maximum gap size in ticks (default: 20)
            fvg_expiry_minutes: Minutes before FVG expires (default: 60)
            max_active_fvgs: Maximum number of active FVGs to track (default: 10)
        """
        self.tick_size = tick_size
        self.min_fvg_size_ticks = min_fvg_size_ticks
        self.max_fvg_size_ticks = max_fvg_size_ticks
        self.fvg_expiry_minutes = fvg_expiry_minutes
        self.max_active_fvgs = max_active_fvgs
        
        # Active FVGs being tracked
        self.active_fvgs = []
        self.fvg_id_counter = 0
    
    def detect_fvg(self, bar1: Dict[str, Any], bar2: Dict[str, Any], bar3: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """
        Detect FVG pattern in 3 consecutive bars.
        
        Bullish FVG: bar1.high < bar3.low (gap up)
        Bearish FVG: bar1.low > bar3.high (gap down)
        
        Args:
            bar1: First bar (oldest)
            bar2: Middle bar (impulse candle)
            bar3: Third bar (newest)
            
        Returns:
            FVG dictionary if valid FVG found, None otherwise
        """
        # Calculate gap sizes
        bullish_gap = bar3['low'] - bar1['high']  # Gap up
        bearish_gap = bar1['low'] - bar3['high']  # Gap down
        
        # Convert to ticks
        bullish_gap_ticks = bullish_gap / self.tick_size
        bearish_gap_ticks = bearish_gap / self.tick_size
        
        # Check for Bullish FVG (gap size 2-20 ticks)
        if self.min_fvg_size_ticks <= bullish_gap_ticks <= self.max_fvg_size_ticks:
            self.fvg_id_counter += 1
            return {
                'id': self.fvg_id_counter,
                'type': 'bullish',
                'top': bar3['low'],  # Top of the gap
                'bottom': bar1['high'],  # Bottom of the gap
                'size_ticks': bullish_gap_ticks,
                'created_at': bar3.get('timestamp'),
                'expires_at': bar3.get('timestamp') + timedelta(minutes=self.fvg_expiry_minutes) if bar3.get('timestamp') else None,
                'filled': False,
                'traded': False,  # Prevents trading same FVG twice
                'bar1': bar1,
                'bar2': bar2,
                'bar3': bar3
            }
        
        # Check for Bearish FVG (gap size 2-20 ticks)
        if self.min_fvg_size_ticks <= bearish_gap_ticks <= self.max_fvg_size_ticks:
            self.fvg_id_counter += 1
            return {
                'id': self.fvg_id_counter,
                'type': 'bearish',
                'top': bar1['low'],  # Top of the gap
                'bottom': bar3['high'],  # Bottom of the gap
                'size_ticks': bearish_gap_ticks,
                'created_at': bar3.get('timestamp'),
                'expires_at': bar3.get('timestamp') + timedelta(minutes=self.fvg_expiry_minutes) if bar3.get('timestamp') else None,
                'filled': False,
                'traded': False,  # Prevents trading same FVG twice
                'bar1': bar1,
                'bar2': bar2,
                'bar3': bar3
            }
        
        return None
    
    def is_fvg_filled(self, fvg: Dict[str, Any], current_bar: Dict[str, Any]) -> bool:
        """
        Check if FVG has been filled by current bar.
        
        Bullish FVG is filled when price touches it from above:
        - current_bar.low <= fvg.top
        
        Bearish FVG is filled when price touches it from below:
        - current_bar.high >= fvg.bottom
        
        Args:
            fvg: FVG dictionary
            current_bar: Current bar to check
            
        Returns:
            True if FVG is filled
        """
        if fvg['type'] == 'bullish':
            # Price came down into the bullish FVG
            return current_bar['low'] <= fvg['top']
        
        elif fvg['type'] == 'bearish':
            # Price came up into the bearish FVG
            return current_bar['high'] >= fvg['bottom']
        
        return False
    
    def remove_expired_fvgs(self, current_time: datetime) -> None:
        """
        Remove FVGs that have expired.
        
        Args:
            current_time: Current timestamp
        """
        self.active_fvgs = [
            fvg for fvg in self.active_fvgs
            if fvg['expires_at'] is None or fvg['expires_at'] > current_time
        ]
    
    def limit_active_fvgs(self) -> None:
        """
        Limit the number of active FVGs to max_active_fvgs.
        Removes oldest FVGs first.
        """
        if len(self.active_fvgs) > self.max_active_fvgs:
            # Keep only the most recent FVGs
            self.active_fvgs = self.active_fvgs[-self.max_active_fvgs:]
    
    def get_unfilled_fvgs(self, fvg_type: Optional[str] = None) -> List[Dict[str, Any]]:
        """
        Get all unfilled FVGs, optionally filtered by type.
        
        Args:
            fvg_type: 'bullish', 'bearish', or None for all
            
        Returns:
            List of unfilled FVG dictionaries
        """
        fvgs = [fvg for fvg in self.active_fvgs if not fvg['filled'] and not fvg['traded']]
        
        if fvg_type:
            fvgs = [fvg for fvg in fvgs if fvg['type'] == fvg_type]
        
        return fvgs
    
    def process_bar(self, bars: List[Dict[str, Any]]) -> Tuple[Optional[Dict[str, Any]], List[Dict[str, Any]]]:
        """
        Process a new bar and check for new FVGs and fills.
        
        Args:
            bars: Complete list of bars including the new bar
            
        Returns:
            Tuple of:
            - new_fvg: Newly detected FVG or None
            - filled_fvgs: List of FVGs that were filled by this bar
        """
        # Need at least 3 bars for FVG detection
        if len(bars) < 3:
            return None, []
        
        # Detect new FVG from last 3 bars
        new_fvg = self.detect_fvg(bars[-3], bars[-2], bars[-1])
        if new_fvg:
            self.active_fvgs.append(new_fvg)
        
        # Check for FVG fills
        current_bar = bars[-1]
        current_time = current_bar.get('timestamp')
        filled_fvgs = []
        
        for fvg in self.active_fvgs:
            if not fvg['filled'] and not fvg['traded']:
                if self.is_fvg_filled(fvg, current_bar):
                    fvg['filled'] = True
                    filled_fvgs.append(fvg)
        
        # Clean up expired FVGs
        if current_time:
            self.remove_expired_fvgs(current_time)
        
        # Limit number of active FVGs
        self.limit_active_fvgs()
        
        return new_fvg, filled_fvgs
    
    def mark_fvg_traded(self, fvg_id: int) -> None:
        """
        Mark an FVG as traded to prevent trading it again.
        
        Args:
            fvg_id: ID of the FVG to mark as traded
        """
        for fvg in self.active_fvgs:
            if fvg['id'] == fvg_id:
                fvg['traded'] = True
                break

"""
Market Regime Detection System
================================
Detects and classifies market regimes based on volatility and price action.

CAPITULATION REVERSAL STRATEGY - SIMPLIFIED:
Regime detection is now just a GO/NO-GO FILTER, not a parameter adjuster.

TRADE these regimes:
- HIGH_VOL_TRENDING: ATR is above average AND price making directional moves
- HIGH_VOL_CHOPPY: ATR is above average BUT price chopping in range

SKIP these regimes:
- NORMAL_TRENDING: ATR is average, trending (not enough volatility for flushes)
- NORMAL: ATR is average, no trend (fake moves)
- NORMAL_CHOPPY: ATR is average, choppy (fake moves)
- LOW_VOL_RANGING: ATR is below average (dead market, no flushes)
- LOW_VOL_TRENDING: ATR is below average (dead market)

OPTIMIZED FOR FAST DETECTION:
- Minimum 34 bars required (20 baseline + 14 current) - ~34 minutes warmup
- Adaptive baseline: uses 20-50 bars depending on availability
- Progressive accuracy: more bars = more accurate, but 34 bars is sufficient
- Previous version required 114 bars (114 minutes warmup)

How to detect:
- Calculate 14-period ATR (current volatility)
- Calculate baseline ATR from 20-50 historical bars (adaptive)
- If current ATR > 1.15x baseline, it is HIGH_VOL
- If current ATR < 0.85x baseline, it is LOW_VOL
- Use price action analysis to determine trending vs choppy
"""

import logging
from typing import Dict, Optional, Tuple
from collections import deque

logger = logging.getLogger(__name__)


class RegimeParameters:
    """
    Parameters for a specific market regime.
    
    NOTE: In Capitulation Reversal Strategy, multipliers are NOT USED.
    Trade management (breakeven, trailing, stop) uses fixed rules.
    This class is kept for backwards compatibility.
    """
    
    def __init__(self, name: str, stop_mult: float = 1.0, breakeven_mult: float = 1.0, 
                 trailing_mult: float = 1.0, sideways_timeout: int = 10, underwater_timeout: int = 20):
        self.name = name
        # LEGACY: These multipliers are NOT used in Capitulation Reversal Strategy
        # Kept for backwards compatibility with older code
        self.stop_mult = stop_mult
        self.breakeven_mult = breakeven_mult
        self.trailing_mult = trailing_mult
        self.sideways_timeout = sideways_timeout
        self.underwater_timeout = underwater_timeout
    
    def __repr__(self):
        return f"RegimeParameters({self.name})"


# Tradeable regimes for Capitulation Reversal Strategy
# Only HIGH_VOL regimes have real flushes - others have fake moves, no edge
TRADEABLE_REGIMES = {"HIGH_VOL_TRENDING", "HIGH_VOL_CHOPPY"}


def is_regime_tradeable(regime: str) -> bool:
    """
    Check if the current regime allows trading.
    
    CAPITULATION REVERSAL: Only trade in HIGH_VOL regimes.
    - HIGH_VOL_TRENDING: TRADE (big moves happen, good for this strategy)
    - HIGH_VOL_CHOPPY: TRADE (still has flushes, just choppier)
    - All others: SKIP (not enough volatility for real flushes)
    
    Args:
        regime: Current market regime name
        
    Returns:
        True if regime allows trading, False otherwise
    """
    return regime in TRADEABLE_REGIMES


# Regime definitions - simplified (multipliers not used in new strategy)
# All regimes have same parameters since we use fixed rules
REGIME_DEFINITIONS = {
    "NORMAL": RegimeParameters(name="NORMAL"),
    "NORMAL_TRENDING": RegimeParameters(name="NORMAL_TRENDING"),
    "NORMAL_CHOPPY": RegimeParameters(name="NORMAL_CHOPPY"),
    "HIGH_VOL_CHOPPY": RegimeParameters(name="HIGH_VOL_CHOPPY"),
    "HIGH_VOL_TRENDING": RegimeParameters(name="HIGH_VOL_TRENDING"),
    "LOW_VOL_RANGING": RegimeParameters(name="LOW_VOL_RANGING"),
    "LOW_VOL_TRENDING": RegimeParameters(name="LOW_VOL_TRENDING"),
}


class RegimeDetector:
    """
    Detects market regimes based on ATR and price action.
    
    Uses last 20 bars to determine:
    - Volatility level (high/normal/low) based on current ATR vs 20-bar average
    - Price action (trending/choppy/ranging) based on directional move vs price range
    """
    
    def __init__(self):
        self.atr_threshold = 0.15  # 15% threshold for volatility classification
        self.trend_threshold = 0.60  # 60% directional move for trending classification
    
    def detect_regime(self, bars: deque, current_atr: float, atr_period: int = 14) -> RegimeParameters:
        """
        Detect current market regime from recent bars.
        
        OPTIMIZED FOR FAST DETECTION:
        - Minimum 34 bars required (20 baseline + 14 current)
        - Uses adaptive baseline: 20-50 bars depending on availability
        - Progressive accuracy: more bars = more accurate, but 34 bars is sufficient
        
        Args:
            bars: Recent price bars (OHLCV data)
            current_atr: Current ATR value (from last 14 bars)
            atr_period: Period for ATR calculation (default 14)
        
        Returns:
            RegimeParameters for the detected regime
        """
        # OPTIMIZED: Minimum 34 bars (20 baseline + 14 current) instead of 114
        # This allows regime detection to start in ~34 minutes instead of 114 minutes
        MINIMUM_BARS = 34  # 20 for baseline + 14 for current ATR
        
        if len(bars) < MINIMUM_BARS:
            # Not enough data yet
            logger.debug(f"Insufficient bars ({len(bars)}) for regime detection, using NORMAL")
            return REGIME_DEFINITIONS["NORMAL"]
        
        all_bars = list(bars)
        
        # ADAPTIVE BASELINE CALCULATION:
        # Use 20-50 bars for baseline depending on what's available
        # More bars = more accurate, but 20 is sufficient for good detection
        available_bars = len(all_bars)
        
        if available_bars >= 64:  # 50 baseline + 14 current
            # Optimal: Use 50 bars for baseline (excludes last 14 for current ATR)
            baseline_bars = all_bars[-64:-14]  # 50 bars
        elif available_bars >= 44:  # 30 baseline + 14 current
            # Good: Use 30 bars for baseline
            baseline_bars = all_bars[-44:-14]  # 30 bars
        else:  # 34-43 bars available
            # Minimum: Use 20 bars for baseline
            baseline_bars = all_bars[-34:-14]  # 20 bars
        
        # Use last 20 bars for price action (or fewer if not available)
        recent_bars = all_bars[-min(20, len(all_bars)):]
        
        # Calculate baseline ATR from earlier period (NOT including current 14 bars)
        avg_atr = self._calculate_average_atr(baseline_bars, atr_period)
        
        if avg_atr == 0:
            logger.debug("Average ATR is 0, using NORMAL regime")
            return REGIME_DEFINITIONS["NORMAL"]
        
        # Classify volatility: high, normal, or low
        atr_ratio = current_atr / avg_atr
        
        if atr_ratio > (1.0 + self.atr_threshold):  # > 1.15
            volatility = "HIGH"
        elif atr_ratio < (1.0 - self.atr_threshold):  # < 0.85
            volatility = "LOW"
        else:  # Within 15% of average
            volatility = "NORMAL"
        
        # Classify price action: trending, choppy, or ranging
        price_action = self._classify_price_action(recent_bars)
        
        # Map to regime
        regime = self._map_to_regime(volatility, price_action)
        
        logger.debug(f"Regime detected: {regime.name} (ATR ratio: {atr_ratio:.2f}, "
                    f"volatility: {volatility}, action: {price_action}, "
                    f"baseline_bars: {len(baseline_bars)})")
        
        return regime
    
    def _calculate_average_atr(self, bars: list, period: int = 14) -> float:
        """
        Calculate average ATR over the given bars.
        
        Note: This uses the bars passed in (typically 1-minute bars for regime detection),
        while quotrading_engine.calculate_atr() uses 15-minute bars. This is intentional
        as regime detection needs higher-resolution data for accurate volatility classification.
        
        Args:
            bars: List of bars (must have 'high', 'low', 'close')
            period: ATR period
        
        Returns:
            Average ATR value
        """
        if len(bars) < period + 1:
            return 0.0
        
        true_ranges = []
        
        for i in range(1, len(bars)):
            high = bars[i]["high"]
            low = bars[i]["low"]
            prev_close = bars[i-1]["close"]
            
            tr = max(
                high - low,
                abs(high - prev_close),
                abs(low - prev_close)
            )
            true_ranges.append(tr)
        
        if len(true_ranges) < period:
            return sum(true_ranges) / len(true_ranges) if true_ranges else 0.0
        
        # Average of last 'period' true ranges
        return sum(true_ranges[-period:]) / period
    
    def _classify_price_action(self, bars: list) -> str:
        """
        Classify price action as trending, choppy, or ranging.
        
        Uses directional move as percentage of total price range:
        - Trending: Directional move > 60% of range
        - Choppy/Ranging: Directional move < 60% of range
        
        Args:
            bars: List of bars (must have 'high', 'low', 'open', 'close')
        
        Returns:
            "TRENDING", "CHOPPY", or "RANGING"
        """
        if not bars:
            return "CHOPPY"
        
        # Calculate price range (highest high - lowest low)
        highest = max(bar["high"] for bar in bars)
        lowest = min(bar["low"] for bar in bars)
        price_range = highest - lowest
        
        if price_range == 0:
            return "RANGING"
        
        # Calculate directional move (net change from first to last)
        first_close = bars[0]["close"]
        last_close = bars[-1]["close"]
        directional_move = abs(last_close - first_close)
        
        # Calculate percentage of range that's directional
        directional_pct = directional_move / price_range
        
        if directional_pct > self.trend_threshold:
            return "TRENDING"
        else:
            # For low directional move, distinguish between choppy and ranging
            # Ranging typically has tighter price action
            return "CHOPPY"
    
    def _map_to_regime(self, volatility: str, price_action: str) -> RegimeParameters:
        """
        Map volatility and price action to a specific regime.
        
        Args:
            volatility: "HIGH", "NORMAL", or "LOW"
            price_action: "TRENDING", "CHOPPY", or "RANGING"
        
        Returns:
            RegimeParameters for the mapped regime
        """
        if volatility == "HIGH":
            if price_action == "TRENDING":
                return REGIME_DEFINITIONS["HIGH_VOL_TRENDING"]
            else:  # CHOPPY or RANGING
                return REGIME_DEFINITIONS["HIGH_VOL_CHOPPY"]
        
        elif volatility == "LOW":
            if price_action == "TRENDING":
                return REGIME_DEFINITIONS["LOW_VOL_TRENDING"]
            else:  # CHOPPY or RANGING
                return REGIME_DEFINITIONS["LOW_VOL_RANGING"]
        
        else:  # NORMAL volatility
            if price_action == "TRENDING":
                return REGIME_DEFINITIONS["NORMAL_TRENDING"]
            elif price_action == "CHOPPY":
                return REGIME_DEFINITIONS["NORMAL_CHOPPY"]
            else:  # Default to baseline NORMAL
                return REGIME_DEFINITIONS["NORMAL"]
    
    def check_regime_change(self, entry_regime: str, current_regime: RegimeParameters) -> Tuple[bool, Optional[RegimeParameters]]:
        """
        Check if regime has changed.
        
        Args:
            entry_regime: Name of regime when position was entered
            current_regime: Currently detected regime parameters
        
        Returns:
            Tuple of (has_changed, new_regime)
        """
        if entry_regime == current_regime.name:
            return False, None
        
        # Regime has changed - use pure regime multipliers (no confidence scaling)
        logger.info(f"REGIME CHANGE: {entry_regime} ΓåÆ {current_regime.name}")
        logger.info(f"  Regime multipliers: stop={current_regime.stop_mult:.2f}x, "
                   f"trailing={current_regime.trailing_mult:.2f}x")
        
        return True, current_regime


def is_regime_tradeable(regime_name: str) -> bool:
    """
    Check if a regime is tradeable for the Capitulation Reversal Strategy.
    
    The strategy only trades in HIGH_VOL regimes where real flushes happen.
    Other regimes have fake moves with no follow-through.
    
    Args:
        regime_name: Name of the regime to check
    
    Returns:
        True if the regime is tradeable
    """
    return regime_name in TRADEABLE_REGIMES


def get_tradeable_regimes() -> set:
    """
    Get the set of tradeable regimes.
    
    Returns:
        Set of regime names that are tradeable
    """
    return TRADEABLE_REGIMES.copy()


# Singleton instance
_detector = None


def get_regime_detector() -> RegimeDetector:
    """Get the global regime detector instance."""
    global _detector
    if _detector is None:
        _detector = RegimeDetector()
    return _detector

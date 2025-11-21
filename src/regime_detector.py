"""
Regime Detection Module
=======================
Real-time market regime classification for adaptive trading.

Detects current market regime and applies regime-specific rules
to adjust bot behavior automatically (non-configurable).

Regimes:
- HIGH_VOL_TRENDING: High volatility + strong trend
- HIGH_VOL_CHOPPY: High volatility + weak trend  
- LOW_VOL_TRENDING: Low volatility + strong trend
- LOW_VOL_RANGING: Low volatility + weak trend
- NORMAL: Moderate conditions
"""

import logging
from typing import Dict, List, Optional, Any, Tuple
from collections import deque
from datetime import datetime

logger = logging.getLogger(__name__)


class RegimeDetector:
    """
    Real-time market regime detector.
    Analyzes recent price action to classify current market conditions.
    """
    
    def __init__(self):
        """Initialize regime detector."""
        self.current_regime = 'NORMAL'
        self.regime_history = deque(maxlen=100)
        self.last_detection_time = None
        
        # Regime-specific trading rules (NON-CONFIGURABLE)
        self.regime_rules = {
            'HIGH_VOL_CHOPPY': {
                'position_size_multiplier': 0.7,     # Reduce size 30%
                'stop_multiplier': 1.3,              # Wider stops
                'target_multiplier': 1.2,            # Wider targets
                'min_rsi_extreme': 25,               # More extreme RSI required
                'max_rsi_extreme': 75,
                'confidence_threshold_adj': 0.10,    # Require +10% confidence
                'description': 'Choppy high volatility - reduced size, wider stops'
            },
            'HIGH_VOL_TRENDING': {
                'position_size_multiplier': 0.85,    # Reduce size 15%
                'stop_multiplier': 1.15,             # Slightly wider stops
                'target_multiplier': 1.25,           # Wider targets for trend
                'min_rsi_extreme': 30,
                'max_rsi_extreme': 70,
                'confidence_threshold_adj': 0.05,    # Require +5% confidence
                'description': 'Trending high volatility - modest size reduction'
            },
            'LOW_VOL_TRENDING': {
                'position_size_multiplier': 1.15,    # Increase size 15%
                'stop_multiplier': 0.9,              # Tighter stops
                'target_multiplier': 1.1,            # Slightly wider targets
                'min_rsi_extreme': 32,
                'max_rsi_extreme': 68,
                'confidence_threshold_adj': -0.05,   # Allow -5% confidence
                'description': 'Calm trending - increased size, tighter stops'
            },
            'LOW_VOL_RANGING': {
                'position_size_multiplier': 1.0,     # Standard size
                'stop_multiplier': 0.95,             # Slightly tighter stops
                'target_multiplier': 1.0,            # Standard targets
                'min_rsi_extreme': 30,
                'max_rsi_extreme': 70,
                'confidence_threshold_adj': 0.0,     # No adjustment
                'description': 'Calm ranging - standard parameters'
            },
            'NORMAL': {
                'position_size_multiplier': 1.0,     # Standard size
                'stop_multiplier': 1.0,              # Standard stops
                'target_multiplier': 1.0,            # Standard targets
                'min_rsi_extreme': 30,
                'max_rsi_extreme': 70,
                'confidence_threshold_adj': 0.0,     # No adjustment
                'description': 'Normal conditions - standard parameters'
            }
        }
        
        logger.info("✓ Regime Detector initialized with hardcoded rules")
    
    def detect_regime(self, bars: List[Dict[str, Any]], symbol: str = "") -> str:
        """
        Detect current market regime from recent bars.
        
        Args:
            bars: List of recent price bars (1-min)
            symbol: Symbol for logging
            
        Returns:
            Regime classification string
        """
        if not bars or len(bars) < 50:
            return 'NORMAL'
        
        # Use last 50 bars for regime detection
        recent_bars = bars[-50:]
        
        # Calculate ATR (volatility measure)
        atr_values = []
        for i in range(1, len(recent_bars)):
            high_low = recent_bars[i]['high'] - recent_bars[i]['low']
            high_close = abs(recent_bars[i]['high'] - recent_bars[i-1]['close'])
            low_close = abs(recent_bars[i]['low'] - recent_bars[i-1]['close'])
            true_range = max(high_low, high_close, low_close)
            atr_values.append(true_range)
        
        avg_atr = sum(atr_values) / len(atr_values) if atr_values else 0
        
        # Calculate directional movement for ADX
        plus_dm_values = []
        minus_dm_values = []
        
        for i in range(1, len(recent_bars)):
            high_diff = recent_bars[i]['high'] - recent_bars[i-1]['high']
            low_diff = recent_bars[i-1]['low'] - recent_bars[i]['low']
            
            plus_dm = high_diff if high_diff > low_diff and high_diff > 0 else 0
            minus_dm = low_diff if low_diff > high_diff and low_diff > 0 else 0
            
            plus_dm_values.append(plus_dm)
            minus_dm_values.append(minus_dm)
        
        avg_plus_dm = sum(plus_dm_values) / len(plus_dm_values) if plus_dm_values else 0
        avg_minus_dm = sum(minus_dm_values) / len(minus_dm_values) if minus_dm_values else 0
        
        # Calculate simplified ADX (trend strength)
        if avg_atr > 0:
            di_plus = (avg_plus_dm / avg_atr) * 100
            di_minus = (avg_minus_dm / avg_atr) * 100
            di_diff = abs(di_plus - di_minus)
            di_sum = di_plus + di_minus
            adx = (di_diff / di_sum * 100) if di_sum > 0 else 0
        else:
            adx = 0
        
        # Calculate ATR as percentage of price
        avg_price = sum(bar['close'] for bar in recent_bars) / len(recent_bars)
        atr_pct = (avg_atr / avg_price) * 100 if avg_price > 0 else 0
        
        # Regime classification thresholds
        high_vol_threshold = 0.15  # 0.15% ATR
        strong_trend_threshold = 20  # ADX > 20
        
        is_high_vol = atr_pct > high_vol_threshold
        is_trending = adx > strong_trend_threshold
        
        # Classify regime
        if is_high_vol and is_trending:
            regime = 'HIGH_VOL_TRENDING'
        elif is_high_vol and not is_trending:
            regime = 'HIGH_VOL_CHOPPY'
        elif not is_high_vol and is_trending:
            regime = 'LOW_VOL_TRENDING'
        elif not is_high_vol and not is_trending:
            regime = 'LOW_VOL_RANGING'
        else:
            regime = 'NORMAL'
        
        # Record regime change
        if regime != self.current_regime:
            logger.info(f"[{symbol}] REGIME CHANGE: {self.current_regime} → {regime}")
            logger.info(f"  ATR%: {atr_pct:.3f}, ADX: {adx:.1f}")
            logger.info(f"  Rules: {self.regime_rules[regime]['description']}")
            self.current_regime = regime
        
        # Track history
        self.regime_history.append({
            'timestamp': datetime.now(),
            'regime': regime,
            'atr_pct': atr_pct,
            'adx': adx
        })
        self.last_detection_time = datetime.now()
        
        return regime
    
    def get_regime_adjustments(self, regime: Optional[str] = None) -> Dict[str, Any]:
        """
        Get trading adjustments for current or specified regime.
        
        Args:
            regime: Regime to get rules for (uses current if None)
            
        Returns:
            Dictionary of regime-specific adjustments
        """
        if regime is None:
            regime = self.current_regime
        
        return self.regime_rules.get(regime, self.regime_rules['NORMAL'])
    
    def apply_regime_position_sizing(self, base_size: int, regime: Optional[str] = None) -> int:
        """
        Apply regime-based position size adjustment.
        
        Args:
            base_size: Base position size (contracts)
            regime: Regime to apply (uses current if None)
            
        Returns:
            Adjusted position size
        """
        if regime is None:
            regime = self.current_regime
        
        rules = self.regime_rules.get(regime, self.regime_rules['NORMAL'])
        multiplier = rules['position_size_multiplier']
        
        adjusted_size = max(1, int(base_size * multiplier))
        
        if adjusted_size != base_size:
            logger.info(f"  Regime position sizing: {base_size} → {adjusted_size} contracts ({regime})")
        
        return adjusted_size
    
    def apply_regime_stops(self, base_stop_distance: float, regime: Optional[str] = None) -> float:
        """
        Apply regime-based stop loss adjustment.
        
        Args:
            base_stop_distance: Base stop distance (price points)
            regime: Regime to apply (uses current if None)
            
        Returns:
            Adjusted stop distance
        """
        if regime is None:
            regime = self.current_regime
        
        rules = self.regime_rules.get(regime, self.regime_rules['NORMAL'])
        multiplier = rules['stop_multiplier']
        
        adjusted_stop = base_stop_distance * multiplier
        
        return adjusted_stop
    
    def apply_regime_targets(self, base_target_distance: float, regime: Optional[str] = None) -> float:
        """
        Apply regime-based profit target adjustment.
        
        Args:
            base_target_distance: Base target distance (price points)
            regime: Regime to apply (uses current if None)
            
        Returns:
            Adjusted target distance
        """
        if regime is None:
            regime = self.current_regime
        
        rules = self.regime_rules.get(regime, self.regime_rules['NORMAL'])
        multiplier = rules['target_multiplier']
        
        adjusted_target = base_target_distance * multiplier
        
        return adjusted_target
    
    def should_filter_signal(self, rsi: float, signal_type: str, regime: Optional[str] = None) -> Tuple[bool, str]:
        """
        Check if signal should be filtered based on regime rules.
        
        Args:
            rsi: Current RSI value
            signal_type: 'long' or 'short'
            regime: Regime to check (uses current if None)
            
        Returns:
            Tuple of (should_filter, reason)
        """
        if regime is None:
            regime = self.current_regime
        
        rules = self.regime_rules.get(regime, self.regime_rules['NORMAL'])
        
        # Check if RSI is extreme enough for this regime
        if signal_type == 'long':
            if rsi > rules['min_rsi_extreme']:
                return True, f"RSI {rsi:.1f} not extreme enough for {regime} (need <{rules['min_rsi_extreme']})"
        elif signal_type == 'short':
            if rsi < rules['max_rsi_extreme']:
                return True, f"RSI {rsi:.1f} not extreme enough for {regime} (need >{rules['max_rsi_extreme']})"
        
        return False, ""
    
    def adjust_confidence_threshold(self, base_threshold: float, regime: Optional[str] = None) -> float:
        """
        Adjust confidence threshold based on regime.
        
        Args:
            base_threshold: Base confidence threshold (0.0-1.0)
            regime: Regime to apply (uses current if None)
            
        Returns:
            Adjusted confidence threshold
        """
        if regime is None:
            regime = self.current_regime
        
        rules = self.regime_rules.get(regime, self.regime_rules['NORMAL'])
        adjustment = rules['confidence_threshold_adj']
        
        adjusted_threshold = max(0.0, min(1.0, base_threshold + adjustment))
        
        if adjustment != 0:
            logger.info(f"  Regime confidence adjustment: {base_threshold:.2f} → {adjusted_threshold:.2f} ({regime})")
        
        return adjusted_threshold
    
    def get_regime_summary(self) -> str:
        """
        Get summary of current regime and rules.
        
        Returns:
            Human-readable regime summary
        """
        rules = self.regime_rules.get(self.current_regime, self.regime_rules['NORMAL'])
        
        summary = f"Current Regime: {self.current_regime}\n"
        summary += f"  {rules['description']}\n"
        summary += f"  Position Size: {rules['position_size_multiplier']:.0%}\n"
        summary += f"  Stop Distance: {rules['stop_multiplier']:.0%}\n"
        summary += f"  Target Distance: {rules['target_multiplier']:.0%}\n"
        summary += f"  Confidence Adj: {rules['confidence_threshold_adj']:+.0%}\n"
        
        return summary


# Global regime detector instance (singleton)
_regime_detector = None


def get_regime_detector() -> RegimeDetector:
    """
    Get or create global regime detector instance.
    
    Returns:
        RegimeDetector instance
    """
    global _regime_detector
    if _regime_detector is None:
        _regime_detector = RegimeDetector()
    return _regime_detector

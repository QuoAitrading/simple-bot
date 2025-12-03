"""
Capitulation Reversal Detection System
========================================
Detects panic selling/buying flushes and reversal exhaustion signals.

THE EDGE:
Wait for panic selling or panic buying. When everyone is rushing for the exits
(or FOMO buying), step in the opposite direction and ride the snapback to fair value.

Strategy Flow:
1. DETECT THE FLUSH - Price dropped/pumped 20+ ticks in 5-10 minutes (2x ATR)
2. CONFIRM EXHAUSTION - Volume spike then decline, extreme RSI, momentum fading
3. ENTRY TRIGGER - Reversal candle closes, price stretched from VWAP
4. STOP LOSS - 2-4 ticks below/above flush low/high
5. PROFIT TARGET - VWAP (mean reversion destination)
6. TRADE MANAGEMENT - Breakeven at 12 ticks, trail after 15 ticks
"""

import logging
from typing import Dict, Optional, Tuple, List, Any
from collections import deque
from dataclasses import dataclass
from datetime import datetime

logger = logging.getLogger(__name__)


@dataclass
class FlushEvent:
    """Represents a detected flush (capitulation) event."""
    direction: str  # "DOWN" or "UP"
    start_time: datetime
    end_time: datetime
    start_price: float
    end_price: float
    flush_low: float  # Lowest point during flush
    flush_high: float  # Highest point during flush
    flush_size_ticks: float  # Total move in ticks
    flush_velocity: float  # Ticks per minute
    atr_multiple: float  # How many ATRs the flush was
    bar_count: int  # Number of bars in the flush
    volume_spike_ratio: float  # Peak volume vs average
    is_valid: bool = True
    

@dataclass
class ExhaustionSignal:
    """Represents exhaustion confirmation signals."""
    volume_declining: bool  # Volume declining after spike
    rsi_extreme: bool  # RSI < 20 (long) or > 80 (short)
    momentum_fading: bool  # Current bar range < previous bars
    new_extremes_stopped: bool  # No new lows/highs being made
    reversal_candle: bool  # Hammer, engulfing, doji after flush
    reversal_candle_type: Optional[str] = None
    exhaustion_score: float = 0.0  # 0-1 confidence score
    

class CapitulationDetector:
    """
    Detects capitulation (panic) flushes and reversal exhaustion signals.
    
    Capitulation Detection:
    - Price drops/pumps at least 20 ticks (5 dollars on ES) in 5-10 minutes
    - Move is FAST, not a slow grind (velocity check)
    - Move is at least 2x the average range (ATR check)
    
    Exhaustion Detection:
    - Volume spike (2-3x normal) followed by declining volume
    - RSI extreme (< 20 for longs, > 80 for shorts)
    - Current bar range smaller than previous bars (momentum fading)
    - No new lows/highs being made
    - Reversal candle forming (hammer, engulfing, doji)
    """
    
    # Configuration constants
    MIN_FLUSH_TICKS = 20  # Minimum 20 ticks (5 dollars on ES)
    MIN_ATR_MULTIPLE = 2.0  # Flush must be at least 2x ATR
    FLUSH_LOOKBACK_BARS = 10  # Look at last 10 one-minute bars
    FLUSH_MIN_BARS = 5  # Minimum 5 bars for flush
    VOLUME_SPIKE_THRESHOLD = 2.0  # 2x normal volume for spike
    RSI_OVERSOLD_EXTREME = 20  # RSI < 20 for long entry
    RSI_OVERBOUGHT_EXTREME = 80  # RSI > 80 for short entry
    
    # Stop loss configuration
    STOP_BUFFER_TICKS = 3  # 2-4 ticks buffer beyond flush extreme
    
    # Trade management
    BREAKEVEN_TRIGGER_TICKS = 12  # Move stop to entry after 12 ticks profit
    TRAILING_TRIGGER_TICKS = 15  # Start trailing after 15 ticks profit
    TRAILING_DISTANCE_TICKS = 9  # Trail 8-10 ticks behind
    MAX_HOLD_BARS = 20  # Time stop after 20 bars
    
    def __init__(self, tick_size: float = 0.25, tick_value: float = 12.50):
        """
        Initialize the capitulation detector.
        
        Args:
            tick_size: Price movement per tick (0.25 for ES)
            tick_value: Dollar value per tick ($12.50 for ES)
        """
        self.tick_size = tick_size
        self.tick_value = tick_value
        
        # State tracking
        self.last_flush: Optional[FlushEvent] = None
        self.last_exhaustion: Optional[ExhaustionSignal] = None
        self.bars_since_flush = 0
        self.flush_detected_time: Optional[datetime] = None
        
        # Volume tracking for surge detection
        self.recent_volumes: deque = deque(maxlen=20)
        
    def detect_flush(self, bars: deque, current_atr: float) -> Optional[FlushEvent]:
        """
        Detect if a capitulation flush has occurred.
        
        A flush is detected when:
        - Price moved at least 20 ticks in the last 5-10 bars
        - The move was at least 2x the ATR (fast move, not slow grind)
        
        Args:
            bars: Recent price bars (1-minute bars)
            current_atr: Current ATR value
        
        Returns:
            FlushEvent if flush detected, None otherwise
        """
        if len(bars) < self.FLUSH_LOOKBACK_BARS:
            return None
        
        if current_atr is None or current_atr <= 0:
            logger.debug("Cannot detect flush: ATR not available")
            return None
        
        # Get recent bars for analysis
        recent_bars = list(bars)[-self.FLUSH_LOOKBACK_BARS:]
        
        # Calculate price range over the lookback period
        highest_high = max(bar["high"] for bar in recent_bars)
        lowest_low = min(bar["low"] for bar in recent_bars)
        price_range = highest_high - lowest_low
        
        # Convert range to ticks
        range_ticks = price_range / self.tick_size
        
        # Check if range exceeds minimum flush size
        if range_ticks < self.MIN_FLUSH_TICKS:
            logger.debug(f"Flush check: Range {range_ticks:.1f} ticks < {self.MIN_FLUSH_TICKS} minimum")
            return None
        
        # Check ATR multiple (must be fast move, not slow grind)
        atr_multiple = price_range / current_atr if current_atr > 0 else 0
        if atr_multiple < self.MIN_ATR_MULTIPLE:
            logger.debug(f"Flush check: ATR multiple {atr_multiple:.2f}x < {self.MIN_ATR_MULTIPLE}x minimum")
            return None
        
        # Determine flush direction based on close comparison
        first_bar = recent_bars[0]
        last_bar = recent_bars[-1]
        
        # Calculate net direction
        net_change = last_bar["close"] - first_bar["open"]
        
        # Flush DOWN: Price dropped significantly (look for LONG)
        # Flush UP: Price pumped significantly (look for SHORT)
        if net_change < 0:
            direction = "DOWN"
            flush_extreme = lowest_low
        else:
            direction = "UP"
            flush_extreme = highest_high
        
        # Calculate flush velocity (ticks per bar)
        bar_count = len(recent_bars)
        velocity = range_ticks / bar_count
        
        # Calculate volume surge during flush
        bar_volumes = [bar["volume"] for bar in recent_bars]
        if bar_volumes and max(bar_volumes) > 0:
            avg_volume = sum(bar_volumes) / len(bar_volumes)
            peak_volume = max(bar_volumes)
            volume_spike_ratio = peak_volume / avg_volume if avg_volume > 0 else 1.0
        else:
            volume_spike_ratio = 1.0
        
        # Create flush event
        flush = FlushEvent(
            direction=direction,
            start_time=first_bar.get("timestamp", datetime.now()),
            end_time=last_bar.get("timestamp", datetime.now()),
            start_price=first_bar["open"],
            end_price=last_bar["close"],
            flush_low=lowest_low,
            flush_high=highest_high,
            flush_size_ticks=range_ticks,
            flush_velocity=velocity,
            atr_multiple=atr_multiple,
            bar_count=bar_count,
            volume_spike_ratio=volume_spike_ratio
        )
        
        logger.info(f"🚨 FLUSH DETECTED: {direction} | {range_ticks:.0f} ticks | "
                   f"{atr_multiple:.1f}x ATR | Velocity: {velocity:.1f} ticks/bar")
        logger.info(f"   Range: ${lowest_low:.2f} - ${highest_high:.2f} | "
                   f"Volume spike: {volume_spike_ratio:.1f}x")
        
        # Store for reference
        self.last_flush = flush
        self.bars_since_flush = 0
        self.flush_detected_time = datetime.now()
        
        return flush
    
    def confirm_exhaustion(self, bars: deque, current_bar: Dict[str, Any], 
                          rsi: Optional[float], flush: FlushEvent,
                          avg_volume: float) -> ExhaustionSignal:
        """
        Confirm exhaustion after a flush.
        
        Exhaustion signals:
        - Volume spike (2-3x normal) followed by declining volume
        - RSI extreme (< 20 for longs, > 80 for shorts)
        - Current bar range smaller than previous bars (momentum fading)
        - Price stopped making new lows/highs
        - Reversal candle forming (hammer, engulfing, doji)
        
        Args:
            bars: Recent price bars
            current_bar: Current incomplete bar
            rsi: Current RSI value
            flush: Detected flush event
            avg_volume: Average volume for comparison
        
        Returns:
            ExhaustionSignal with confirmation details
        """
        if len(bars) < 3:
            return ExhaustionSignal(
                volume_declining=False,
                rsi_extreme=False,
                momentum_fading=False,
                new_extremes_stopped=False,
                reversal_candle=False,
                exhaustion_score=0.0
            )
        
        recent_bars = list(bars)[-5:]
        prev_bar = recent_bars[-1] if recent_bars else None
        
        # 1. Check volume pattern (spike then decline)
        bar_volumes = [bar["volume"] for bar in recent_bars]
        if len(bar_volumes) >= 3:
            # Peak should be in the middle, current should be lower
            peak_idx = bar_volumes.index(max(bar_volumes))
            current_vol = current_bar.get("volume", 0)
            volume_declining = (peak_idx < len(bar_volumes) - 1 and 
                               current_vol < bar_volumes[peak_idx])
        else:
            volume_declining = False
        
        # 2. Check RSI extreme
        rsi_extreme = False
        if rsi is not None:
            if flush.direction == "DOWN" and rsi <= self.RSI_OVERSOLD_EXTREME:
                rsi_extreme = True
            elif flush.direction == "UP" and rsi >= self.RSI_OVERBOUGHT_EXTREME:
                rsi_extreme = True
        
        # 3. Check momentum fading (current bar range < previous bars)
        if prev_bar:
            prev_ranges = [bar["high"] - bar["low"] for bar in recent_bars[-3:]]
            current_range = current_bar["high"] - current_bar["low"]
            avg_prev_range = sum(prev_ranges) / len(prev_ranges) if prev_ranges else 0
            momentum_fading = current_range < avg_prev_range * 0.8  # 80% of avg
        else:
            momentum_fading = False
        
        # 4. Check if new extremes stopped
        if flush.direction == "DOWN":
            # For down flush, check if we stopped making new lows
            new_extremes_stopped = current_bar["low"] > flush.flush_low
        else:
            # For up flush, check if we stopped making new highs
            new_extremes_stopped = current_bar["high"] < flush.flush_high
        
        # 5. Check for reversal candle
        reversal_candle, candle_type = self._detect_reversal_candle(
            current_bar, flush.direction
        )
        
        # Calculate exhaustion score (0-1)
        signals = [volume_declining, rsi_extreme, momentum_fading, 
                  new_extremes_stopped, reversal_candle]
        exhaustion_score = sum(signals) / len(signals)
        
        exhaustion = ExhaustionSignal(
            volume_declining=volume_declining,
            rsi_extreme=rsi_extreme,
            momentum_fading=momentum_fading,
            new_extremes_stopped=new_extremes_stopped,
            reversal_candle=reversal_candle,
            reversal_candle_type=candle_type,
            exhaustion_score=exhaustion_score
        )
        
        self.last_exhaustion = exhaustion
        
        if exhaustion_score >= 0.6:
            logger.info(f"✅ EXHAUSTION CONFIRMED: Score {exhaustion_score:.0%}")
            logger.info(f"   Volume declining: {volume_declining} | RSI extreme: {rsi_extreme}")
            logger.info(f"   Momentum fading: {momentum_fading} | New extremes stopped: {new_extremes_stopped}")
            logger.info(f"   Reversal candle: {candle_type or 'None'}")
        
        return exhaustion
    
    def _detect_reversal_candle(self, bar: Dict[str, Any], 
                                flush_direction: str) -> Tuple[bool, Optional[str]]:
        """
        Detect reversal candle patterns.
        
        Patterns detected:
        - Hammer (long lower wick after flush down)
        - Inverted Hammer (long upper wick after flush up)
        - Engulfing (large body in opposite direction)
        - Doji (small body, indecision)
        
        Args:
            bar: Current bar data
            flush_direction: "DOWN" or "UP"
        
        Returns:
            Tuple of (is_reversal, pattern_name)
        """
        if not bar:
            return False, None
        
        open_price = bar["open"]
        close_price = bar["close"]
        high = bar["high"]
        low = bar["low"]
        
        # Calculate body and wicks
        body = abs(close_price - open_price)
        upper_wick = high - max(open_price, close_price)
        lower_wick = min(open_price, close_price) - low
        total_range = high - low
        
        if total_range <= 0:
            return False, None
        
        # Body as percentage of total range
        body_pct = body / total_range
        
        # Check for Doji (very small body)
        if body_pct < 0.15:
            return True, "doji"
        
        if flush_direction == "DOWN":
            # After flush DOWN, look for BULLISH reversal
            
            # Hammer: Long lower wick, small upper wick, body at top
            if lower_wick > body * 2 and upper_wick < body * 0.5:
                return True, "hammer"
            
            # Bullish engulfing: Large bullish candle
            if close_price > open_price and body_pct > 0.6:
                return True, "bullish_engulfing"
        
        else:  # flush_direction == "UP"
            # After flush UP, look for BEARISH reversal
            
            # Inverted hammer/shooting star: Long upper wick
            if upper_wick > body * 2 and lower_wick < body * 0.5:
                return True, "shooting_star"
            
            # Bearish engulfing: Large bearish candle
            if close_price < open_price and body_pct > 0.6:
                return True, "bearish_engulfing"
        
        return False, None
    
    def calculate_stop_price(self, flush: FlushEvent, side: str) -> float:
        """
        Calculate stop loss price based on flush extreme.
        
        Stop placement:
        - For LONG (after flush down): 2-4 ticks below flush low
        - For SHORT (after flush up): 2-4 ticks above flush high
        
        Args:
            flush: The detected flush event
            side: "long" or "short"
        
        Returns:
            Stop loss price
        """
        buffer = self.STOP_BUFFER_TICKS * self.tick_size
        
        if side == "long":
            # Stop below the flush low
            stop_price = flush.flush_low - buffer
        else:
            # Stop above the flush high
            stop_price = flush.flush_high + buffer
        
        return stop_price
    
    def get_entry_signal(self, bars: deque, current_bar: Dict[str, Any],
                        current_atr: float, rsi: Optional[float],
                        avg_volume: float, current_price: float,
                        vwap: float) -> Tuple[bool, Optional[str], Dict[str, Any]]:
        """
        Check if entry conditions are met for capitulation reversal.
        
        Entry conditions:
        1. Flush detected (price dropped/pumped 20+ ticks, 2x ATR)
        2. Exhaustion confirmed (60%+ score)
        3. Reversal candle formed (bullish for long, bearish for short)
        4. Price stretched from VWAP (rubber band ready to snap back)
        
        Args:
            bars: Recent price bars
            current_bar: Current bar data
            current_atr: Current ATR value
            rsi: Current RSI value
            avg_volume: Average volume
            current_price: Current market price
            vwap: Current VWAP value
        
        Returns:
            Tuple of (should_enter, side, entry_details)
        """
        entry_details = {
            "flush": None,
            "exhaustion": None,
            "stop_price": None,
            "target_price": None,
            "reason": ""
        }
        
        # Step 1: Detect flush
        flush = self.detect_flush(bars, current_atr)
        if flush is None:
            entry_details["reason"] = "No flush detected"
            return False, None, entry_details
        
        entry_details["flush"] = flush
        
        # Step 2: Confirm exhaustion
        exhaustion = self.confirm_exhaustion(bars, current_bar, rsi, flush, avg_volume)
        entry_details["exhaustion"] = exhaustion
        
        if exhaustion.exhaustion_score < 0.6:
            entry_details["reason"] = f"Exhaustion score too low: {exhaustion.exhaustion_score:.0%}"
            return False, None, entry_details
        
        # Step 3: Check for reversal candle
        if not exhaustion.reversal_candle:
            entry_details["reason"] = "No reversal candle pattern"
            return False, None, entry_details
        
        # Step 4: Check bar direction confirmation
        is_bullish_bar = current_bar["close"] > current_bar["open"]
        is_bearish_bar = current_bar["close"] < current_bar["open"]
        
        # Determine entry side based on flush direction
        if flush.direction == "DOWN":
            # After flush DOWN, look for LONG entry
            if not is_bullish_bar:
                entry_details["reason"] = "Waiting for bullish confirmation candle"
                return False, None, entry_details
            
            side = "long"
            stop_price = self.calculate_stop_price(flush, side)
            target_price = vwap  # Mean reversion to VWAP
            
        else:  # flush.direction == "UP"
            # After flush UP, look for SHORT entry
            if not is_bearish_bar:
                entry_details["reason"] = "Waiting for bearish confirmation candle"
                return False, None, entry_details
            
            side = "short"
            stop_price = self.calculate_stop_price(flush, side)
            target_price = vwap  # Mean reversion to VWAP
        
        # Step 5: Validate risk/reward
        # Price should be significantly stretched from VWAP
        distance_to_vwap = abs(current_price - vwap)
        distance_to_stop = abs(current_price - stop_price)
        
        if distance_to_stop == 0:
            entry_details["reason"] = "Invalid stop distance"
            return False, None, entry_details
        
        risk_reward = distance_to_vwap / distance_to_stop
        if risk_reward < 1.5:
            entry_details["reason"] = f"Poor risk/reward: {risk_reward:.2f} (need 1.5+)"
            return False, None, entry_details
        
        entry_details["stop_price"] = stop_price
        entry_details["target_price"] = target_price
        entry_details["risk_reward"] = risk_reward
        entry_details["reason"] = f"Capitulation reversal: {flush.direction} flush exhausted, {exhaustion.reversal_candle_type}"
        
        logger.info(f"🎯 ENTRY SIGNAL: {side.upper()}")
        logger.info(f"   Flush: {flush.flush_size_ticks:.0f} ticks {flush.direction}")
        logger.info(f"   Exhaustion: {exhaustion.exhaustion_score:.0%}")
        logger.info(f"   Pattern: {exhaustion.reversal_candle_type}")
        logger.info(f"   Stop: ${stop_price:.2f} | Target: ${target_price:.2f}")
        logger.info(f"   Risk/Reward: {risk_reward:.2f}")
        
        return True, side, entry_details
    
    def should_activate_breakeven(self, current_price: float, entry_price: float,
                                  side: str) -> bool:
        """
        Check if breakeven should be activated (12 ticks profit).
        
        Args:
            current_price: Current market price
            entry_price: Entry price
            side: "long" or "short"
        
        Returns:
            True if breakeven should be activated
        """
        if side == "long":
            profit_ticks = (current_price - entry_price) / self.tick_size
        else:
            profit_ticks = (entry_price - current_price) / self.tick_size
        
        return profit_ticks >= self.BREAKEVEN_TRIGGER_TICKS
    
    def should_activate_trailing(self, current_price: float, entry_price: float,
                                  side: str) -> bool:
        """
        Check if trailing stop should be activated (15+ ticks profit).
        
        Args:
            current_price: Current market price
            entry_price: Entry price
            side: "long" or "short"
        
        Returns:
            True if trailing should be activated
        """
        if side == "long":
            profit_ticks = (current_price - entry_price) / self.tick_size
        else:
            profit_ticks = (entry_price - current_price) / self.tick_size
        
        return profit_ticks >= self.TRAILING_TRIGGER_TICKS
    
    def calculate_trailing_stop(self, current_price: float, peak_price: float,
                                 side: str) -> float:
        """
        Calculate trailing stop price (8-10 ticks behind peak).
        
        Args:
            current_price: Current market price
            peak_price: Peak price reached (highest for long, lowest for short)
            side: "long" or "short"
        
        Returns:
            Trailing stop price
        """
        trail_distance = self.TRAILING_DISTANCE_TICKS * self.tick_size
        
        if side == "long":
            return peak_price - trail_distance
        else:
            return peak_price + trail_distance
    
    def check_time_stop(self, bars_held: int) -> bool:
        """
        Check if time stop should trigger (15-20 bars).
        
        Dead trades tie up capital and mental energy.
        
        Args:
            bars_held: Number of bars since entry
        
        Returns:
            True if time stop triggered
        """
        return bars_held >= self.MAX_HOLD_BARS
    
    def update_bars_since_flush(self):
        """Increment bars since flush counter."""
        self.bars_since_flush += 1
    
    def reset(self):
        """Reset detector state for new session."""
        self.last_flush = None
        self.last_exhaustion = None
        self.bars_since_flush = 0
        self.flush_detected_time = None
        self.recent_volumes.clear()


# Singleton instance
_detector: Optional[CapitulationDetector] = None


def get_capitulation_detector(tick_size: float = 0.25, 
                              tick_value: float = 12.50) -> CapitulationDetector:
    """
    Get the global capitulation detector instance.
    
    Args:
        tick_size: Price movement per tick
        tick_value: Dollar value per tick
    
    Returns:
        CapitulationDetector instance
    """
    global _detector
    if _detector is None:
        _detector = CapitulationDetector(tick_size, tick_value)
    return _detector


def reset_capitulation_detector():
    """Reset the global capitulation detector."""
    global _detector
    if _detector is not None:
        _detector.reset()

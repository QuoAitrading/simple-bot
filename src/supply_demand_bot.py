"""
Supply/Demand Rejection Strategy Bot (LuxAlgo-Style Order Blocks)

A separate trading bot that implements LuxAlgo-style supply/demand zone detection
and rejection strategy. This bot operates independently from the main capitulation bot.

LUXALGO ORDER BLOCK METHODOLOGY:
This implementation replicates the LuxAlgo supply/demand (order block) detection:
1. Identify "base" candles where institutions placed orders (pause before big move)
2. Confirm with strong impulse move (1.5x average candle range over 20 bars)
3. Wait for price to return to these institutional zones
4. Trade rejections when price respects the zone

ZONE DETECTION (LuxAlgo Algorithm):
Supply Zone (Bearish Order Block):
  - Look for uptrend (at least 1 bullish candle in prior 2)
  - Find base/pause candle (small consolidation)
  - Confirm with strong bearish impulse (1.5x avg range)
  - Zone = base candle's body top to high (institutional sell orders)
  
Demand Zone (Bullish Order Block):
  - Look for downtrend (at least 1 bearish candle in prior 2)
  - Find base/pause candle (small consolidation)
  - Confirm with strong bullish impulse (1.5x avg range)
  - Zone = base candle's body bottom to low (institutional buy orders)

ENTRY SIGNALS:
- LONG: Price rejects from demand zone (wick touches zone, green body closes above)
- SHORT: Price rejects from supply zone (wick touches zone, red body closes below)
- Rejection wick must be ≥30% of total candle (shows strong rejection)

RISK MANAGEMENT:
- Stop Loss: 2 ticks beyond zone (if zone fails, exit immediately)
- Take Profit: 1.5x risk distance (1.5:1 reward-to-risk ratio)

ZONE LIFECYCLE:
- Delete zone if price closes through it (zone is broken)
- Delete zone after 3 tests (zone losing strength)
- Delete zone after 200 candles (zone too old/stale)
"""

import logging
from datetime import datetime, timedelta
from typing import List, Dict, Optional, Tuple, Deque
from dataclasses import dataclass
from collections import deque
import pytz


@dataclass
class Zone:
    """Represents a supply or demand zone"""
    zone_type: str  # 'supply' or 'demand'
    top: float  # Top of zone
    bottom: float  # Bottom of zone
    created_at: datetime  # When zone was created
    base_candle_index: int  # Index of the base/pause candle
    impulse_size: float  # Size of impulse move away from zone (in ticks)
    test_count: int = 0  # Number of times zone has been tested
    
    def get_thickness_ticks(self, tick_size: float) -> float:
        """Get zone thickness in ticks"""
        return abs(self.top - self.bottom) / tick_size
    
    def is_valid(self, current_candle_index: int, max_age: int = 200) -> bool:
        """Check if zone is still valid"""
        age = current_candle_index - self.base_candle_index
        if age > max_age:
            return False
        if self.test_count >= 3:
            return False
        return True
    
    def is_price_in_zone(self, price: float) -> bool:
        """Check if price is within zone boundaries"""
        return self.bottom <= price <= self.top
    
    def is_broken(self, candle_close: float) -> bool:
        """Check if candle closed through the zone"""
        if self.zone_type == 'supply':
            # Supply zone broken if close is above top
            return candle_close > self.top
        else:  # demand
            # Demand zone broken if close is below bottom
            return candle_close < self.bottom


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
        """Top of candle body"""
        return max(self.open, self.close)
    
    @property
    def body_bottom(self) -> float:
        """Bottom of candle body"""
        return min(self.open, self.close)
    
    @property
    def total_range(self) -> float:
        """Total candle range (high to low)"""
        return self.high - self.low
    
    @property
    def body_size(self) -> float:
        """Size of candle body"""
        return abs(self.close - self.open)
    
    @property
    def upper_wick(self) -> float:
        """Upper wick size"""
        return self.high - self.body_top
    
    @property
    def lower_wick(self) -> float:
        """Lower wick size"""
        return self.body_bottom - self.low


class SupplyDemandStrategy:
    """
    Supply/Demand Rejection Strategy Implementation
    
    This strategy identifies institutional supply and demand zones where
    price previously paused before making a strong directional move.
    When price returns to these zones, we look for rejection patterns
    to enter trades in the direction of the original impulse.
    """
    
    def __init__(
        self,
        tick_size: float = 0.25,
        tick_value: float = 1.25,
        lookback_period: int = 20,
        impulse_multiplier: float = 1.5,
        min_zone_ticks: float = 4,
        max_zone_ticks: float = 20,
        rejection_wick_pct: float = 0.30,
        stop_loss_ticks: float = 2,
        risk_reward_ratio: float = 1.5,
        max_zone_age: int = 200,
        max_zone_tests: int = 3,
        logger: Optional[logging.Logger] = None
    ):
        """
        Initialize the Supply/Demand strategy
        
        Args:
            tick_size: Minimum price movement (e.g., 0.25 for ES)
            tick_value: Dollar value per tick (e.g., 12.50 for ES, 1.25 for MES)
            lookback_period: Bars to use for average candle range calculation
            impulse_multiplier: Impulse must be this many times avg candle range
            min_zone_ticks: Minimum zone thickness in ticks
            max_zone_ticks: Maximum zone thickness in ticks
            rejection_wick_pct: Minimum wick size as % of total candle
            stop_loss_ticks: Ticks to place stop beyond zone
            risk_reward_ratio: Target is this times the risk distance
            max_zone_age: Maximum age of zone in candles
            max_zone_tests: Maximum number of times zone can be tested
            logger: Optional logger instance
        """
        self.tick_size = tick_size
        self.tick_value = tick_value
        self.lookback_period = lookback_period
        self.impulse_multiplier = impulse_multiplier
        self.min_zone_ticks = min_zone_ticks
        self.max_zone_ticks = max_zone_ticks
        self.rejection_wick_pct = rejection_wick_pct
        self.stop_loss_ticks = stop_loss_ticks
        self.risk_reward_ratio = risk_reward_ratio
        self.max_zone_age = max_zone_age
        self.max_zone_tests = max_zone_tests
        
        self.logger = logger or logging.getLogger(__name__)
        
        # State
        self.candles: Deque[Candle] = deque(maxlen=lookback_period + 100)
        self.supply_zones: List[Zone] = []
        self.demand_zones: List[Zone] = []
        self.current_candle_index = 0
        
        # Statistics
        self.zones_created = 0
        self.zones_deleted = 0
        self.signals_generated = 0
        
    def process_candle(self, candle: Candle) -> Optional[Dict]:
        """
        Process a new candle and potentially generate trading signals
        
        Args:
            candle: New candle to process
            
        Returns:
            Dictionary with signal details if signal generated, None otherwise
            Signal format:
            {
                'signal': 'long' or 'short',
                'entry_price': float,
                'stop_price': float,
                'target_price': float,
                'zone': Zone object,
                'timestamp': datetime
            }
        """
        # Add candle to history
        self.candles.append(candle)
        self.current_candle_index += 1
        
        # Need enough candles for zone detection
        if len(self.candles) < self.lookback_period + 3:
            return None
        
        # Update zones (detect new ones, remove invalid ones)
        self._update_zones()
        
        # Check for rejection signals
        signal = self._check_for_rejection(candle)
        
        if signal:
            self.signals_generated += 1
            
        return signal
    
    def _calculate_average_candle_range(self) -> float:
        """Calculate average candle range over lookback period"""
        if len(self.candles) < self.lookback_period:
            return 0.0
        
        # Get last N candles
        recent_candles = list(self.candles)[-self.lookback_period:]
        ranges = [c.total_range for c in recent_candles]
        
        return sum(ranges) / len(ranges)
    
    def _detect_zones_in_recent_candles(self):
        """
        Detect new supply/demand zones in recent candles
        
        Zone detection logic:
        1. Look for a base candle (pause)
        2. Before base: at least 2 candles trending opposite to impulse
        3. After base: impulse candle 1.5x bigger than average
        4. Zone is the base candle's range (for body, not full candle)
        """
        if len(self.candles) < 5:  # Need at least 5 candles
            return
        
        avg_range = self._calculate_average_candle_range()
        if avg_range == 0:
            return
        
        candles_list = list(self.candles)
        
        # Check the candle that is 2 positions from the end
        # (We need to see the impulse candle after to confirm)
        check_index = len(candles_list) - 2
        if check_index < 2:
            return
        
        base_candle = candles_list[check_index]
        impulse_candle = candles_list[check_index + 1]
        
        # Check for SUPPLY zone (up trend → base → drop)
        if impulse_candle.is_bearish and impulse_candle.body_size >= avg_range * self.impulse_multiplier:
            # Check if we have upward movement before base (at least 1 bullish in last 2)
            prev_candles = candles_list[check_index - 2:check_index]
            bullish_count = sum(1 for c in prev_candles if c.is_bullish)
            if len(prev_candles) >= 2 and bullish_count >= 1:
                # Potential supply zone at base candle
                zone_top = base_candle.high
                zone_bottom = base_candle.body_top  # Where body ended (higher of open/close)
                
                zone_thickness = (zone_top - zone_bottom) / self.tick_size
                
                # Validate zone thickness
                if self.min_zone_ticks <= zone_thickness <= self.max_zone_ticks:
                    impulse_ticks = impulse_candle.body_size / self.tick_size
                    
                    # Check if we already have a zone at this location
                    if not self._zone_exists_at_price(zone_top, zone_bottom, 'supply'):
                        zone = Zone(
                            zone_type='supply',
                            top=zone_top,
                            bottom=zone_bottom,
                            created_at=base_candle.timestamp,
                            base_candle_index=self.current_candle_index - 2,
                            impulse_size=impulse_ticks
                        )
                        self.supply_zones.append(zone)
                        self.zones_created += 1
                        self.logger.info(
                            f"🔴 SUPPLY ZONE (Bearish Order Block) created at {zone_top:.2f}-{zone_bottom:.2f} "
                            f"| Thickness: {zone_thickness:.1f} ticks | Impulse: {impulse_ticks:.1f} ticks | "
                            f"Time: {base_candle.timestamp.strftime('%Y-%m-%d %H:%M')}"
                        )
        
        # Check for DEMAND zone (down trend → base → rally)
        if impulse_candle.is_bullish and impulse_candle.body_size >= avg_range * self.impulse_multiplier:
            # Check if we have downward movement before base (at least 1 bearish in last 2)
            prev_candles = candles_list[check_index - 2:check_index]
            bearish_count = sum(1 for c in prev_candles if c.is_bearish)
            if len(prev_candles) >= 2 and bearish_count >= 1:
                # Potential demand zone at base candle
                zone_bottom = base_candle.low
                zone_top = base_candle.body_bottom  # Where body ended (lower of open/close)
                
                zone_thickness = (zone_top - zone_bottom) / self.tick_size
                
                # Validate zone thickness
                if self.min_zone_ticks <= zone_thickness <= self.max_zone_ticks:
                    impulse_ticks = impulse_candle.body_size / self.tick_size
                    
                    # Check if we already have a zone at this location
                    if not self._zone_exists_at_price(zone_top, zone_bottom, 'demand'):
                        zone = Zone(
                            zone_type='demand',
                            top=zone_top,
                            bottom=zone_bottom,
                            created_at=base_candle.timestamp,
                            base_candle_index=self.current_candle_index - 2,
                            impulse_size=impulse_ticks
                        )
                        self.demand_zones.append(zone)
                        self.zones_created += 1
                        self.logger.info(
                            f"🔵 DEMAND ZONE (Bullish Order Block) created at {zone_top:.2f}-{zone_bottom:.2f} "
                            f"| Thickness: {zone_thickness:.1f} ticks | Impulse: {impulse_ticks:.1f} ticks | "
                            f"Time: {base_candle.timestamp.strftime('%Y-%m-%d %H:%M')}"
                        )
    
    def _zone_exists_at_price(self, top: float, bottom: float, zone_type: str) -> bool:
        """Check if a zone already exists at approximately the same price level"""
        zones = self.supply_zones if zone_type == 'supply' else self.demand_zones
        tolerance = self.tick_size * 2  # Allow 2 ticks difference
        
        for zone in zones:
            if (abs(zone.top - top) < tolerance and 
                abs(zone.bottom - bottom) < tolerance):
                return True
        return False
    
    def _update_zones(self):
        """Update zones: detect new ones and remove invalid/broken ones"""
        # Detect new zones
        self._detect_zones_in_recent_candles()
        
        # Get current candle for checking breakouts
        current_candle = self.candles[-1]
        
        # Remove invalid supply zones
        valid_supply = []
        for zone in self.supply_zones:
            if zone.is_broken(current_candle.close):
                self.logger.info(f"Deleted SUPPLY zone (broken by close at {current_candle.close:.2f})")
                self.zones_deleted += 1
            elif not zone.is_valid(self.current_candle_index, self.max_zone_age):
                self.logger.info(f"Deleted SUPPLY zone (too old or tested)")
                self.zones_deleted += 1
            else:
                valid_supply.append(zone)
        self.supply_zones = valid_supply
        
        # Remove invalid demand zones
        valid_demand = []
        for zone in self.demand_zones:
            if zone.is_broken(current_candle.close):
                self.logger.info(f"Deleted DEMAND zone (broken by close at {current_candle.close:.2f})")
                self.zones_deleted += 1
            elif not zone.is_valid(self.current_candle_index, self.max_zone_age):
                self.logger.info(f"Deleted DEMAND zone (too old or tested)")
                self.zones_deleted += 1
            else:
                valid_demand.append(zone)
        self.demand_zones = valid_demand
    
    def _check_for_rejection(self, candle: Candle) -> Optional[Dict]:
        """
        Check if current candle shows rejection from a zone
        
        Rejection criteria:
        - Wick touches zone
        - Body stays outside zone
        - Candle closes in rejection direction (bullish for demand, bearish for supply)
        - Wick is at least 30% of total candle size
        """
        # Check for LONG signal (demand zone rejection)
        for zone in self.demand_zones:
            # Check if lower wick touched the zone
            if candle.low <= zone.top and candle.low >= zone.bottom:
                # Check if body stayed above zone
                if candle.body_bottom > zone.top:
                    # Check if candle closed bullish
                    if candle.is_bullish:
                        # Check wick size requirement
                        wick_size = candle.lower_wick
                        if candle.total_range > 0:
                            wick_pct = wick_size / candle.total_range
                            if wick_pct >= self.rejection_wick_pct:
                                # Valid rejection - generate LONG signal
                                zone.test_count += 1
                                
                                entry_price = candle.close
                                stop_price = zone.bottom - (self.stop_loss_ticks * self.tick_size)
                                risk_ticks = (entry_price - stop_price) / self.tick_size
                                target_price = entry_price + (risk_ticks * self.risk_reward_ratio * self.tick_size)
                                
                                self.logger.info(
                                    f"🟢 LONG SIGNAL (Demand Zone Rejection) | Entry: {entry_price:.2f} | "
                                    f"Stop: {stop_price:.2f} | Target: {target_price:.2f} | "
                                    f"Risk: {risk_ticks:.1f} ticks | R:R = 1:{self.risk_reward_ratio} | "
                                    f"Wick: {wick_pct*100:.0f}% of candle"
                                )
                                
                                return {
                                    'signal': 'long',
                                    'entry_price': entry_price,
                                    'stop_price': stop_price,
                                    'target_price': target_price,
                                    'zone': zone,
                                    'timestamp': candle.timestamp,
                                    'risk_ticks': risk_ticks,
                                    'reward_ticks': risk_ticks * self.risk_reward_ratio
                                }
        
        # Check for SHORT signal (supply zone rejection)
        for zone in self.supply_zones:
            # Check if upper wick touched the zone
            if candle.high >= zone.bottom and candle.high <= zone.top:
                # Check if body stayed below zone
                if candle.body_top < zone.bottom:
                    # Check if candle closed bearish
                    if candle.is_bearish:
                        # Check wick size requirement
                        wick_size = candle.upper_wick
                        if candle.total_range > 0:
                            wick_pct = wick_size / candle.total_range
                            if wick_pct >= self.rejection_wick_pct:
                                # Valid rejection - generate SHORT signal
                                zone.test_count += 1
                                
                                entry_price = candle.close
                                stop_price = zone.top + (self.stop_loss_ticks * self.tick_size)
                                risk_ticks = (stop_price - entry_price) / self.tick_size
                                target_price = entry_price - (risk_ticks * self.risk_reward_ratio * self.tick_size)
                                
                                self.logger.info(
                                    f"🔴 SHORT SIGNAL (Supply Zone Rejection) | Entry: {entry_price:.2f} | "
                                    f"Stop: {stop_price:.2f} | Target: {target_price:.2f} | "
                                    f"Risk: {risk_ticks:.1f} ticks | R:R = 1:{self.risk_reward_ratio} | "
                                    f"Wick: {wick_pct*100:.0f}% of candle"
                                )
                                
                                return {
                                    'signal': 'short',
                                    'entry_price': entry_price,
                                    'stop_price': stop_price,
                                    'target_price': target_price,
                                    'zone': zone,
                                    'timestamp': candle.timestamp,
                                    'risk_ticks': risk_ticks,
                                    'reward_ticks': risk_ticks * self.risk_reward_ratio
                                }
        
        return None
    
    def get_statistics(self) -> Dict:
        """Get strategy statistics"""
        return {
            'zones_created': self.zones_created,
            'zones_deleted': self.zones_deleted,
            'active_supply_zones': len(self.supply_zones),
            'active_demand_zones': len(self.demand_zones),
            'signals_generated': self.signals_generated,
            'candles_processed': self.current_candle_index
        }

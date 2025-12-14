"""
Filters - Implements velocity, volume, and time-in-zone filters for trade validation
"""

import logging
from typing import Dict, Optional
from datetime import datetime
import time

logger = logging.getLogger(__name__)


class FilterManager:
    """
    Manages three filters that can veto a trade:
    1. Velocity Filter: Checks if price moved too fast (hard hit)
    2. Volume Filter: Checks if volume is abnormally high
    3. Time In Zone Filter: Checks if price stayed in zone too long
    """
    
    def __init__(self, 
                 velocity_threshold: float = 5.0,
                 reaction_window: float = 10.0,
                 volume_lookback: int = 30,
                 high_volume_threshold: float = 2.0,
                 time_in_zone_limit: float = 45.0,
                 tick_size: float = 0.25):
        """
        Initialize filter manager with thresholds.
        
        Args:
            velocity_threshold: Ticks per second threshold (default 5.0)
            reaction_window: Seconds to wait for body displacement (default 10.0)
            volume_lookback: Number of bars for volume average (default 30)
            high_volume_threshold: Volume multiplier threshold (default 2.0)
            time_in_zone_limit: Maximum seconds in zone (default 45.0)
            tick_size: Tick size for velocity calculation (default 0.25)
        """
        self.velocity_threshold = velocity_threshold
        self.reaction_window = reaction_window
        self.volume_lookback = volume_lookback
        self.high_volume_threshold = high_volume_threshold
        self.time_in_zone_limit = time_in_zone_limit
        self.tick_size = tick_size
        
        # Track pending filter states
        self.pending_velocity_check = {}  # zone_id -> start_time
        self.pending_volume_check = {}  # zone_id -> start_time
        
        logger.info(f"🔧 FilterManager initialized:")
        logger.info(f"  • Velocity threshold: {velocity_threshold} ticks/sec")
        logger.info(f"  • Reaction window: {reaction_window}s")
        logger.info(f"  • Volume lookback: {volume_lookback} bars")
        logger.info(f"  • High volume threshold: {high_volume_threshold}x")
        logger.info(f"  • Time in zone limit: {time_in_zone_limit}s")
    
    def calculate_velocity(self, current_price: float, entry_price: float, 
                          current_time: datetime, entry_time: datetime) -> float:
        """
        Calculate velocity in ticks per second.
        
        Velocity = (price_move_in_ticks) / (time_elapsed_in_seconds)
        
        Args:
            current_price: Current price
            entry_price: Price when zone was entered
            current_time: Current time
            entry_time: Time when zone was entered
            
        Returns:
            Velocity in ticks per second
        """
        # Calculate ticks moved
        price_move = abs(current_price - entry_price)
        ticks_moved = price_move / self.tick_size
        
        # Calculate time elapsed
        time_elapsed = (current_time - entry_time).total_seconds()
        
        # Avoid division by zero
        if time_elapsed < 0.1:
            time_elapsed = 0.1
        
        velocity = ticks_moved / time_elapsed
        return velocity
    
    def check_velocity_filter(self, zone: Dict, current_price: float, 
                             current_time: datetime, is_body_displaced: bool) -> tuple:
        """
        Check velocity filter.
        
        If velocity > threshold (hard hit):
            - Start pending state
            - Wait up to reaction_window seconds
            - If body displaced within window: PASS
            - If window expires without displacement: FAIL
        
        If velocity <= threshold: PASS immediately
        
        Args:
            zone: The zone being checked
            current_price: Current price
            current_time: Current time
            is_body_displaced: Whether body is currently displaced
            
        Returns:
            Tuple of (filter_status, should_wait)
            filter_status: 'pass', 'fail', or 'pending'
            should_wait: True if waiting for reaction window
        """
        if not zone.get('entry_time') or not zone.get('entry_price'):
            logger.warning("⚠️ Velocity filter: No entry time/price recorded")
            return 'pass', False
        
        # Calculate velocity
        velocity = self.calculate_velocity(
            current_price, zone['entry_price'],
            current_time, zone['entry_time']
        )
        
        zone_id = id(zone)
        
        # If velocity is low, pass immediately
        if velocity <= self.velocity_threshold:
            logger.info(f"✅ Velocity filter PASS: {velocity:.2f} ticks/sec <= {self.velocity_threshold}")
            return 'pass', False
        
        # High velocity - this is a hard hit
        logger.info(f"⚡ Hard hit detected: velocity={velocity:.2f} ticks/sec > {self.velocity_threshold}")
        
        # Check if we're already tracking this pending check
        if zone_id not in self.pending_velocity_check:
            # Start pending state
            self.pending_velocity_check[zone_id] = current_time
            logger.info(f"⏳ Velocity filter PENDING: Waiting {self.reaction_window}s for body displacement (absorption)")
            return 'pending', True
        
        # We're in pending state - check if body is displaced
        if is_body_displaced:
            # Body displaced within reaction window - this is absorption
            logger.info(f"✅ Velocity filter PASS: Body displaced within reaction window (absorption)")
            del self.pending_velocity_check[zone_id]
            return 'pass', False
        
        # Check if reaction window expired
        pending_start = self.pending_velocity_check[zone_id]
        time_waiting = (current_time - pending_start).total_seconds()
        
        if time_waiting >= self.reaction_window:
            # Window expired without displacement - this is acceptance
            logger.info(f"❌ Velocity filter FAIL: Reaction window expired without displacement (acceptance)")
            del self.pending_velocity_check[zone_id]
            return 'fail', False
        
        # Still waiting
        logger.debug(f"⏳ Velocity filter waiting: {time_waiting:.1f}s / {self.reaction_window}s")
        return 'pending', True
    
    def check_volume_filter(self, current_volume: float, average_volume: float,
                          zone: Dict, current_time: datetime, is_body_displaced: bool) -> tuple:
        """
        Check volume filter.
        
        If relative volume > threshold (high volume):
            - Start pending state
            - Wait up to reaction_window seconds
            - If body displaced within window: PASS
            - If window expires without displacement: FAIL
        
        If relative volume <= threshold: PASS immediately
        
        Args:
            current_volume: Current bar volume
            average_volume: Average volume over lookback period
            zone: The zone being checked
            current_time: Current time
            is_body_displaced: Whether body is currently displaced
            
        Returns:
            Tuple of (filter_status, should_wait)
            filter_status: 'pass', 'fail', or 'pending'
            should_wait: True if waiting for reaction window
        """
        # Calculate relative volume
        if average_volume <= 0:
            logger.warning("⚠️ Volume filter: Average volume is zero, defaulting to pass")
            return 'pass', False
        
        relative_volume = current_volume / average_volume
        
        zone_id = id(zone)
        
        # If volume is normal, pass immediately
        if relative_volume <= self.high_volume_threshold:
            logger.info(f"✅ Volume filter PASS: {relative_volume:.2f}x <= {self.high_volume_threshold}x")
            return 'pass', False
        
        # High volume detected
        logger.info(f"📊 High volume detected: {relative_volume:.2f}x > {self.high_volume_threshold}x")
        
        # Check if we're already tracking this pending check
        if zone_id not in self.pending_volume_check:
            # Start pending state
            self.pending_volume_check[zone_id] = current_time
            logger.info(f"⏳ Volume filter PENDING: Waiting {self.reaction_window}s for body displacement (absorption)")
            return 'pending', True
        
        # We're in pending state - check if body is displaced
        if is_body_displaced:
            # Body displaced within reaction window - this is absorption
            logger.info(f"✅ Volume filter PASS: Body displaced within reaction window (absorption)")
            del self.pending_volume_check[zone_id]
            return 'pass', False
        
        # Check if reaction window expired
        pending_start = self.pending_volume_check[zone_id]
        time_waiting = (current_time - pending_start).total_seconds()
        
        if time_waiting >= self.reaction_window:
            # Window expired without displacement - this is acceptance
            logger.info(f"❌ Volume filter FAIL: Reaction window expired without displacement (acceptance)")
            del self.pending_volume_check[zone_id]
            return 'fail', False
        
        # Still waiting
        logger.debug(f"⏳ Volume filter waiting: {time_waiting:.1f}s / {self.reaction_window}s")
        return 'pending', True
    
    def check_time_in_zone_filter(self, zone: Dict, current_time: datetime, 
                                  is_body_displaced: bool) -> str:
        """
        Check time in zone filter.
        
        If time in zone > limit and body NOT displaced: FAIL immediately
        If time in zone <= limit: PASS
        
        Args:
            zone: The zone being checked
            current_time: Current time
            is_body_displaced: Whether body is currently displaced
            
        Returns:
            Filter status: 'pass' or 'fail'
        """
        if not zone.get('entry_time'):
            logger.warning("⚠️ Time in zone filter: No entry time recorded")
            return 'pass'
        
        # Calculate time in zone
        time_in_zone = (current_time - zone['entry_time']).total_seconds()
        
        # If time exceeds limit and body is NOT displaced, fail
        if time_in_zone > self.time_in_zone_limit and not is_body_displaced:
            logger.info(f"❌ Time in zone filter FAIL: {time_in_zone:.1f}s > {self.time_in_zone_limit}s without displacement")
            return 'fail'
        
        logger.info(f"✅ Time in zone filter PASS: {time_in_zone:.1f}s <= {self.time_in_zone_limit}s")
        return 'pass'
    
    def check_all_filters(self, zone: Dict, current_price: float, current_time: datetime,
                         current_volume: float, average_volume: float,
                         is_body_displaced: bool) -> tuple:
        """
        Run all three filters.
        
        If any filter fails, trade is skipped.
        If all filters pass, trade is allowed.
        
        Args:
            zone: The zone being checked
            current_price: Current price
            current_time: Current time
            current_volume: Current bar volume
            average_volume: Average volume over lookback period
            is_body_displaced: Whether body is currently displaced
            
        Returns:
            Tuple of (all_passed, should_wait, pending_filters)
            all_passed: True if all filters pass, False if any failed
            should_wait: True if any filter is pending
            pending_filters: List of filter names that are pending
        """
        pending_filters = []
        
        # Check velocity filter
        velocity_status, velocity_wait = self.check_velocity_filter(
            zone, current_price, current_time, is_body_displaced
        )
        
        if velocity_status == 'fail':
            return False, False, []
        elif velocity_status == 'pending':
            pending_filters.append('velocity')
        
        # Check volume filter
        volume_status, volume_wait = self.check_volume_filter(
            current_volume, average_volume, zone, current_time, is_body_displaced
        )
        
        if volume_status == 'fail':
            return False, False, []
        elif volume_status == 'pending':
            pending_filters.append('volume')
        
        # Check time in zone filter (no waiting, immediate pass/fail)
        time_status = self.check_time_in_zone_filter(zone, current_time, is_body_displaced)
        
        if time_status == 'fail':
            return False, False, []
        
        # If any filter is pending, continue waiting
        should_wait = len(pending_filters) > 0
        
        # All filters passed (or are pending but haven't failed yet)
        if should_wait:
            logger.info(f"⏳ Filters pending: {', '.join(pending_filters)}")
            return False, True, pending_filters
        else:
            logger.info(f"✅ All filters PASSED - Trade allowed")
            return True, False, []
    
    def clear_pending_checks(self, zone: Dict) -> None:
        """
        Clear all pending filter checks for a zone.
        
        Args:
            zone: The zone to clear
        """
        zone_id = id(zone)
        if zone_id in self.pending_velocity_check:
            del self.pending_velocity_check[zone_id]
        if zone_id in self.pending_volume_check:
            del self.pending_volume_check[zone_id]

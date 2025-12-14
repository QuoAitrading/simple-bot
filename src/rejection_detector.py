"""
Rejection Detector - Detects body displacement from supply/demand zones in real time
"""

import logging
from typing import Dict, Optional

logger = logging.getLogger(__name__)


class RejectionDetector:
    """
    Detects body displacement from zones in real-time.
    
    Calculates live candle body and checks for zone entry and body displacement.
    """
    
    def __init__(self):
        """Initialize the rejection detector"""
        pass
    
    def calculate_body_high_low(self, open_price: float, current_price: float) -> tuple:
        """
        Calculate the live body high and low.
        
        Body high = max(open, current)
        Body low = min(open, current)
        
        Args:
            open_price: Candle open price
            current_price: Current price (live close)
            
        Returns:
            Tuple of (body_high, body_low)
        """
        body_high = max(open_price, current_price)
        body_low = min(open_price, current_price)
        return body_high, body_low
    
    def has_entered_zone(self, zone: Dict, candle_high: float, candle_low: float) -> bool:
        """
        Check if price has entered a zone.
        
        Supply zone: Price enters if candle high >= zone bottom
        Demand zone: Price enters if candle low <= zone top
        
        Args:
            zone: The zone to check
            candle_high: High of current candle
            candle_low: Low of current candle
            
        Returns:
            True if price has entered the zone, False otherwise
        """
        if zone['zone_type'] == 'supply':
            # Supply zone: price enters if high touched or exceeded zone bottom
            entered = candle_high >= zone['zone_bottom']
            if entered:
                logger.debug(f"Price entered SUPPLY zone: candle_high={candle_high:.2f} >= zone_bottom={zone['zone_bottom']:.2f}")
            return entered
        else:  # demand
            # Demand zone: price enters if low touched or went below zone top
            entered = candle_low <= zone['zone_top']
            if entered:
                logger.debug(f"Price entered DEMAND zone: candle_low={candle_low:.2f} <= zone_top={zone['zone_top']:.2f}")
            return entered
    
    def is_body_displaced(self, zone: Dict, body_high: float, body_low: float) -> bool:
        """
        Check if body is displaced from the zone.
        
        Supply zone: Body displaced if body_high < zone_bottom
                    (entire body is below the zone)
        Demand zone: Body displaced if body_low > zone_top
                    (entire body is above the zone)
        
        Args:
            zone: The zone to check
            body_high: High of the candle body
            body_low: Low of the candle body
            
        Returns:
            True if body is displaced, False otherwise
        """
        if zone['zone_type'] == 'supply':
            # Supply zone: body must be completely below zone bottom
            displaced = body_high < zone['zone_bottom']
            if displaced:
                logger.info(f"✅ SUPPLY zone rejection: body_high={body_high:.2f} < zone_bottom={zone['zone_bottom']:.2f}")
            return displaced
        else:  # demand
            # Demand zone: body must be completely above zone top
            displaced = body_low > zone['zone_top']
            if displaced:
                logger.info(f"✅ DEMAND zone rejection: body_low={body_low:.2f} > zone_top={zone['zone_top']:.2f}")
            return displaced
    
    def check_zone_rejection(self, zone: Dict, open_price: float, high_price: float, 
                           low_price: float, current_price: float) -> tuple:
        """
        Complete check for zone rejection (convenience method).
        
        Returns:
            Tuple of (has_entered, is_displaced, body_high, body_low)
        """
        # Calculate body
        body_high, body_low = self.calculate_body_high_low(open_price, current_price)
        
        # Check if entered
        has_entered = self.has_entered_zone(zone, high_price, low_price)
        
        # Check if displaced
        is_displaced = self.is_body_displaced(zone, body_high, body_low) if has_entered else False
        
        return has_entered, is_displaced, body_high, body_low

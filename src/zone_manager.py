"""
Zone Manager - Manages supply and demand zones for trading bot
"""

import logging
from typing import Dict, List, Optional
from datetime import datetime

logger = logging.getLogger(__name__)


class ZoneManager:
    """
    Manages the list of active supply and demand zones.
    
    Each zone contains:
    - zone_top: Top price of the zone
    - zone_bottom: Bottom price of the zone
    - zone_type: Either "supply" or "demand"
    - zone_strength: "strong", "medium", or "weak"
    - dead: Boolean flag (initially False)
    - entry_time: Timestamp when price entered the zone (for filters)
    - entry_price: Price when zone was entered (for filters)
    """
    
    def __init__(self):
        """Initialize the zone manager with an empty zone list"""
        self.zones: List[Dict] = []
        
    def update_zones_from_heartbeat(self, zone_data: List[Dict]) -> None:
        """
        Update zones from heartbeat response.
        Replaces the local zone list with zones from Azure.
        
        Args:
            zone_data: List of zones from Azure heartbeat response
                      Each zone should have: zone_top, zone_bottom, zone_type, zone_strength
        """
        if not zone_data:
            logger.info("📍 No zones received from cloud - clearing local zones")
            self.zones = []
            return
        
        # Replace the entire zone list
        self.zones = []
        for zone in zone_data:
            # Initialize zone with dead flag and entry tracking
            zone_dict = {
                'zone_top': float(zone.get('zone_top', 0)),
                'zone_bottom': float(zone.get('zone_bottom', 0)),
                'zone_type': zone.get('zone_type', 'supply'),  # 'supply' or 'demand'
                'zone_strength': zone.get('zone_strength', 'medium'),  # 'strong', 'medium', 'weak'
                'dead': False,
                'entry_time': None,
                'entry_price': None
            }
            self.zones.append(zone_dict)
        
        logger.info(f"📍 Updated zones from cloud: {len(self.zones)} zones loaded")
        for idx, zone in enumerate(self.zones):
            logger.info(f"  Zone {idx+1}: {zone['zone_type'].upper()} {zone['zone_bottom']:.2f}-{zone['zone_top']:.2f} ({zone['zone_strength']})")
    
    def add_zone(self, zone_type: str, top_price: float, bottom_price: float,
                 strength: str = "medium", source: str = "manual") -> Dict:
        """
        Add a single zone to the manager.
        
        Used for real-time zone additions from WebSocket (TradingView indicators).
        
        Args:
            zone_type: 'supply' or 'demand'
            top_price: Top of the zone
            bottom_price: Bottom of the zone
            strength: Zone strength ('strong', 'medium', 'weak')
            source: Source of zone ('tradingview', 'manual', etc.)
        
        Returns:
            The created zone dict
        """
        zone_dict = {
            'zone_top': float(top_price),
            'zone_bottom': float(bottom_price),
            'zone_type': zone_type.lower(),
            'zone_strength': strength.lower(),
            'dead': False,
            'entry_time': None,
            'entry_price': None,
            'source': source
        }
        
        # Check for duplicate zones (within 0.25 price tolerance)
        for existing in self.zones:
            if (existing['zone_type'] == zone_dict['zone_type'] and
                abs(existing['zone_top'] - zone_dict['zone_top']) < 0.5 and
                abs(existing['zone_bottom'] - zone_dict['zone_bottom']) < 0.5):
                logger.debug(f"Zone already exists, skipping: {zone_type} {bottom_price:.2f}-{top_price:.2f}")
                return existing
        
        self.zones.append(zone_dict)
        logger.info(f"📍 Added zone: {zone_type.upper()} {bottom_price:.2f}-{top_price:.2f} ({strength}) from {source}")
        
        return zone_dict
    
    def check_and_mark_dead_zones(self, current_price: float) -> None:
        """
        Check and mark zones as dead based on current price.
        
        Supply zone dies when price goes above zone top.
        Demand zone dies when price goes below zone bottom.
        
        Args:
            current_price: Current market price
        """
        zones_before = len(self.zones)
        
        for zone in self.zones:
            if zone['dead']:
                continue
                
            # Supply zone dies when price goes above zone top
            if zone['zone_type'] == 'supply' and current_price > zone['zone_top']:
                zone['dead'] = True
                logger.info(f"💀 SUPPLY zone died: {zone['zone_bottom']:.2f}-{zone['zone_top']:.2f} (price broke above at {current_price:.2f})")
            
            # Demand zone dies when price goes below zone bottom
            elif zone['zone_type'] == 'demand' and current_price < zone['zone_bottom']:
                zone['dead'] = True
                logger.info(f"💀 DEMAND zone died: {zone['zone_bottom']:.2f}-{zone['zone_top']:.2f} (price broke below at {current_price:.2f})")
        
        # Remove dead zones from the list
        self.zones = [zone for zone in self.zones if not zone['dead']]
        
        zones_removed = zones_before - len(self.zones)
        if zones_removed > 0:
            logger.info(f"🗑️  Removed {zones_removed} dead zone(s) - {len(self.zones)} active zones remaining")
    
    def get_active_zones(self) -> List[Dict]:
        """
        Get all active zones (where dead is False).
        
        Returns:
            List of active zones
        """
        return [zone for zone in self.zones if not zone['dead']]
    
    def record_zone_entry(self, zone: Dict, entry_time: datetime, entry_price: float) -> None:
        """
        Record when price enters a zone.
        
        Args:
            zone: The zone that was entered
            entry_time: Time when zone was entered
            entry_price: Price when zone was entered
        """
        zone['entry_time'] = entry_time
        zone['entry_price'] = entry_price
        logger.info(f"📍 Price entered {zone['zone_type'].upper()} zone {zone['zone_bottom']:.2f}-{zone['zone_top']:.2f} at {entry_price:.2f}")
    
    def clear_zone_entry(self, zone: Dict) -> None:
        """
        Clear zone entry state after trade or exit.
        
        Args:
            zone: The zone to clear
        """
        zone['entry_time'] = None
        zone['entry_price'] = None

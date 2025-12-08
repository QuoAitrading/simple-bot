"""
Cloud API Client for User Bots
================================
Simple client that reports trade outcomes to cloud for data collection.
Bots make decisions locally using their own RL brain.
"""

import logging
import requests
import aiohttp
import asyncio
from typing import Dict, Tuple, Optional

logger = logging.getLogger(__name__)


class CloudAPIClient:
    """
    Simple API client for user bots to report trade outcomes to cloud.
    
    User bots use this to:
    1. Report "here's what happened" after trade closes
    
    Decision-making happens locally in each bot's RL brain.
    """
    
    def __init__(self, api_url: str, license_key: str, timeout: int = 10, max_retries: int = 2):
        """
        Initialize cloud API client.
        
        Args:
            api_url: Cloud API URL (e.g., "https://quotrading-flask-api.azurewebsites.net")
            license_key: User's license key for authentication
            timeout: Request timeout in seconds (default 10s)
            max_retries: Number of retry attempts on connection failure (default 2)
        """
        self.api_url = api_url.rstrip('/')
        self.license_key = license_key
        self.timeout = timeout
        self.max_retries = max_retries
        self.license_valid = True  # Set to False only on 401 license errors
        self.session: Optional[aiohttp.ClientSession] = None
        

    async def _get_session(self) -> aiohttp.ClientSession:
        """Get or create the shared ClientSession"""
        if self.session is None or self.session.closed:
            self.session = aiohttp.ClientSession()
        return self.session

    async def close(self):
        """Close the session"""
        if self.session and not self.session.closed:
            await self.session.close()
    
    def report_trade_outcome(self, state: Dict, took_trade: bool, pnl: float, duration: float, execution_data: Optional[Dict] = None) -> bool:
        """
        Report trade outcome to cloud for data collection.
        
        Args:
            state: Market state when trade was taken (14 fields: 12 pattern matching + 2 metadata)
            took_trade: Whether trade was actually taken
            pnl: Profit/loss in dollars
            duration: Trade duration in seconds (IGNORED - not stored in cloud)
            execution_data: Optional execution quality metrics (IGNORED - not stored in cloud)
        
        Returns:
            True if successfully reported, False otherwise
            
        Example:
            client.report_trade_outcome(
                state=original_state,
                took_trade=True,
                pnl=125.50,
                duration=1800,  # ignored
                execution_data={}  # ignored
            )
        """
        # Skip reporting if license is invalid
        if not self.license_valid:
            return False
        
        try:
            # SIMPLIFIED 16-FIELD STRUCTURE
            # The 12 Pattern Matching Fields + 4 Metadata Fields
            payload = {
                "license_key": self.license_key,
                # All market state fields (14 fields from capture_market_state)
                **state,  # flush_size_ticks, flush_velocity, volume_climax_ratio, flush_direction,
                         # rsi, distance_from_flush_low, reversal_candle, no_new_extreme,
                         # vwap_distance_ticks, regime, session, hour, symbol, timestamp
                # Trade outcomes (2 fields - pnl and took_trade)
                "took_trade": took_trade,
                "pnl": pnl
            }
            
            response = requests.post(
                f"{self.api_url}/api/rl/submit-outcome",
                json=payload,
                timeout=self.timeout
            )
            
            if response.status_code == 200:
                data = response.json()
                total_exp = data.get('total_experiences', '?')
                win_rate = data.get('win_rate', 0) * 100
                return True
            else:
                logger.warning(f"⚠️ Failed to report outcome: HTTP {response.status_code}")
                return False
                
        except Exception as e:
            return False

    async def report_trade_outcome_async(self, state: Dict, took_trade: bool, pnl: float, duration: float, execution_data: Optional[Dict] = None) -> bool:
        """
        Async version of report_trade_outcome using aiohttp.
        """
        # Skip reporting if license is invalid
        if not self.license_valid:
            return False
        
        try:
            # SIMPLIFIED 16-FIELD STRUCTURE
            # The 12 Pattern Matching Fields + 4 Metadata Fields
            payload = {
                "license_key": self.license_key,
                # All market state fields (14 fields from capture_market_state)
                **state,  # flush_size_ticks, flush_velocity, volume_climax_ratio, flush_direction,
                         # rsi, distance_from_flush_low, reversal_candle, no_new_extreme,
                         # vwap_distance_ticks, regime, session, hour, symbol, timestamp
                # Trade outcomes (2 fields - pnl and took_trade)
                "took_trade": took_trade,
                "pnl": pnl
            }
            
            session = await self._get_session()
            async with session.post(
                f"{self.api_url}/api/rl/submit-outcome",
                json=payload,
                timeout=self.timeout
            ) as response:
                    
                    if response.status == 200:
                        data = await response.json()
                        total_exp = data.get('total_experiences', '?')
                        win_rate = data.get('win_rate', 0) * 100
                        return True
                    else:
                        logger.warning(f"⚠️ Failed to report outcome: HTTP {response.status}")
                        return False
                
        except Exception as e:
            return False
    
    def set_license_valid(self, valid: bool):
        """
        Set license validity status.
        Only call this if you need to re-enable after fixing license issues.
        """
        self.license_valid = valid
        status = "valid" if valid else "invalid"

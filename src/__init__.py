"""
VWAP Bounce Bot - Core Trading Module

A sophisticated VWAP-based mean reversion trading bot with adaptive exits.
"""

__version__ = "1.0.0"
__author__ = "Kevin Suero"

# Core modules
from . import config
from . import vwap_bounce_bot
from . import backtesting
from . import broker_interface

__all__ = [
    "config",
    "vwap_bounce_bot", 
    "backtesting",
    "broker_interface",
]

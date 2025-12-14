"""
QuoTrading Bot - Core Trading Module

A sophisticated algorithmic trading bot for futures markets.
For backtesting and development, see the dev/ folder.
"""

__version__ = "1.0.0"
__author__ = "Kevin Suero"

# Core production modules
# Note: avoid importing the trading engine at package import time (side effects).
from . import config
from . import broker_interface

__all__ = [
    "config",
    "broker_interface",
]

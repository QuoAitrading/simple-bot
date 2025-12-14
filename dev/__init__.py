"""
Development Environment for QuoTrading Bot

This folder contains development tools and data recording utilities.
Separated from production code in src/ for clean architecture.

Note: Backtesting framework has been removed during refactoring.
"""

__version__ = "1.0.0"

# Export data recorder components
from .data_recorder import DataRecorder

__all__ = [
    'DataRecorder'
]

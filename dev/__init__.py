"""
Development Environment for QuoTrading Bot

This folder contains the backtesting framework and development tools.
Separated from production code in src/ for clean architecture.
"""

__version__ = "1.0.0"

# Export backtesting components
from .backtesting import (
    BacktestConfig,
    BacktestEngine,
    HistoricalDataLoader,
    PerformanceMetrics,
    ReportGenerator,
    Trade
)

# Export backtest runner functions
from .run_backtest import (
    run_backtest,
    load_bot_module_for_backtest
)

# Export data recorder components
from .data_recorder import DataRecorder

__all__ = [
    'BacktestConfig',
    'BacktestEngine',
    'HistoricalDataLoader',
    'PerformanceMetrics',
    'ReportGenerator',
    'Trade',
    'run_backtest',
    'load_bot_module_for_backtest',
    'DataRecorder'
]

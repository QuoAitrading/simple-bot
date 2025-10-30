#!/usr/bin/env python3
"""
Automated parameter optimization for VWAP Bounce Bot.
Runs grid search to find the most profitable settings.
"""

import os
import sys
import logging
from datetime import datetime, timedelta
from typing import Dict, Any, List
import pytz
import json

# Set backtest mode BEFORE importing bot modules
os.environ['BOT_BACKTEST_MODE'] = 'true'

# Import bot modules
from config import load_config
from backtesting import BacktestConfig, BacktestEngine
from parameter_optimization import ParameterOptimizer, OptimizationResult

# Import bot logic for backtesting
from vwap_bounce_bot import initialize_state, on_tick, check_for_signals, check_exit_conditions, check_daily_reset, state


def setup_logger():
    """Setup logging for optimization"""
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[
            logging.FileHandler('optimization.log'),
            logging.StreamHandler()
        ]
    )
    return logging.getLogger(__name__)


def create_vwap_strategy(symbol: str, bot_config_dict: Dict[str, Any]):
    """
    Create a VWAP strategy function for backtesting.
    This integrates the actual bot logic with the backtest engine.
    """
    # Get ET timezone for daily reset checks
    et = pytz.timezone('US/Eastern')
    
    def vwap_strategy_backtest(bars_1min: List[Dict[str, Any]], bars_15min: List[Dict[str, Any]]) -> None:
        """
        Actual VWAP Bounce strategy integrated with backtest engine.
        Processes historical data through the real bot logic.
        """
        # IMPORTANT: Initialize state fresh for each backtest run
        # This clears all counters including daily_trade_count
        if symbol in state:
            state.pop(symbol)
        initialize_state(symbol)
        
        for bar in bars_1min:
            # Extract bar data
            timestamp = bar['timestamp']
            price = bar['close']
            volume = bar['volume']
            timestamp_ms = int(timestamp.timestamp() * 1000)
            
            # Check for new trading day (resets daily counters at 6 PM ET)
            timestamp_et = timestamp.astimezone(et)
            check_daily_reset(symbol, timestamp_et)
            
            # Process tick through actual bot logic
            on_tick(symbol, price, volume, timestamp_ms)
            
            # Check for entry signals after each bar
            check_for_signals(symbol)
            
            # Check for exit signals
            check_exit_conditions(symbol)
    
    return vwap_strategy_backtest


def main():
    logger = setup_logger()
    
    logger.info("="*80)
    logger.info("VWAP BOUNCE BOT - AUTOMATED PARAMETER OPTIMIZATION")
    logger.info("="*80)
    logger.info("")
    logger.info("This script will:")
    logger.info("1. Run backtests with different parameter combinations")
    logger.info("2. Find the most profitable settings")
    logger.info("3. Validate results to avoid overfitting")
    logger.info("4. Output the best parameters")
    logger.info("")
    
    # Load base configuration
    bot_config = load_config(backtest_mode=True)
    bot_config_dict = bot_config.to_dict()
    symbol = bot_config_dict['instrument']
    
    logger.info(f"Trading Symbol: {symbol}")
    logger.info(f"Initial Configuration:")
    logger.info(f"  VWAP Std Dev 2: {bot_config.vwap_std_dev_2}")
    logger.info(f"  RSI Oversold: {bot_config.rsi_oversold}")
    logger.info(f"  RSI Overbought: {bot_config.rsi_overbought}")
    logger.info(f"  Use RSI Filter: {bot_config.use_rsi_filter}")
    logger.info(f"  Use Trend Filter: {bot_config.use_trend_filter}")
    logger.info(f"  Use Volume Filter: {bot_config.use_volume_filter}")
    logger.info(f"  Risk per Trade: {bot_config.risk_per_trade * 100:.1f}%")
    logger.info(f"  Max Contracts: {bot_config.max_contracts}")
    logger.info("")
    
    # Define parameter ranges to optimize
    # Focus on the MOST impactful parameters - fewer combinations for faster testing
    param_ranges = {
        # VWAP Entry Band - Which std dev to trade from?
        'vwap_std_dev_2': [1.5, 2.0, 2.5],  # Entry zone - 3 values
        
        # RSI Extremes - Critical for mean reversion
        'rsi_oversold': [20, 25, 30],  # For long entries - 3 values
        'rsi_overbought': [70, 75, 80],  # For short entries - 3 values
        
        # Key filter toggles
        'use_rsi_filter': [True, False],  # 2 values
        'use_vwap_direction_filter': [True],  # Keep enabled (proven)
        
        # Position sizing - keep simple
        'risk_per_trade': [0.01, 0.012],  # 1%, 1.2% - 2 values
    }
    
    total_combinations = 1
    for param_values in param_ranges.values():
        total_combinations *= len(param_values)
    
    logger.info("PARAMETER RANGES TO TEST:")
    for param, values in param_ranges.items():
        logger.info(f"  {param}: {values}")
    logger.info(f"")
    logger.info(f"Total Combinations: {total_combinations}")
    logger.info("")
    
    # Setup backtest date range - use last month for speed
    tz = pytz.timezone(bot_config.timezone)
    end_date = datetime(2025, 10, 29, tzinfo=tz)  # Last day of data
    start_date = datetime(2025, 10, 1, tzinfo=tz)  # October only (1 month for speed)
    
    logger.info(f"Backtest Period:")
    logger.info(f"  Start: {start_date.strftime('%Y-%m-%d')}")
    logger.info(f"  End: {end_date.strftime('%Y-%m-%d')}")
    logger.info(f"  Duration: {(end_date - start_date).days} days")
    logger.info("")
    
    # Create backtest configuration
    backtest_config = BacktestConfig(
        start_date=start_date,
        end_date=end_date,
        initial_equity=50000.0,
        symbols=[symbol],
        data_path='./historical_data',
        use_tick_data=False,  # Use bar-by-bar for speed
        slippage_ticks=bot_config.slippage_ticks,
        commission_per_contract=bot_config.commission_per_contract
    )
    
    # Create optimizer
    optimizer = ParameterOptimizer(backtest_config, bot_config_dict, param_ranges)
    
    # Create strategy function
    strategy_func = create_vwap_strategy(symbol, bot_config_dict)
    
    # Run grid search optimization
    logger.info("="*80)
    logger.info("STARTING GRID SEARCH OPTIMIZATION")
    logger.info("="*80)
    logger.info("")
    logger.info("Optimizing for: Sharpe Ratio")
    logger.info("(Best risk-adjusted returns)")
    logger.info("")
    
    try:
        # Run optimization - use sharpe_ratio as the metric
        results = optimizer.grid_search(
            strategy_func=strategy_func,
            metric='sharpe_ratio',  # Sharpe ratio = best risk-adjusted returns
            n_jobs=1  # Sequential execution for stability
        )
        
        logger.info("")
        logger.info("="*80)
        logger.info("OPTIMIZATION COMPLETE!")
        logger.info("="*80)
        logger.info("")
        
        # Display best parameters
        logger.info("BEST PARAMETERS FOUND:")
        logger.info("="*40)
        for param, value in results.best_params.items():
            logger.info(f"  {param}: {value}")
        logger.info("")
        
        logger.info(f"Best Sharpe Ratio: {results.best_score:.4f}")
        logger.info("")
        
        # Find the best result details
        best_result = None
        for result in results.all_results:
            if result['params'] == results.best_params:
                best_result = result
                break
        
        if best_result:
            logger.info("PERFORMANCE WITH BEST PARAMETERS:")
            logger.info("="*40)
            logger.info(f"Total Trades: {best_result['total_trades']}")
            logger.info(f"Total P&L: ${best_result['total_pnl']:+,.2f}")
            logger.info(f"Total Return: {best_result['total_return']:+.2f}%")
            logger.info(f"Win Rate: {best_result['win_rate']:.2f}%")
            logger.info(f"Average Win: ${best_result['average_win']:+.2f}")
            logger.info(f"Average Loss: ${best_result['average_loss']:+.2f}")
            logger.info(f"Profit Factor: {best_result['profit_factor']:.2f}")
            logger.info(f"Sharpe Ratio: {best_result['sharpe_ratio']:.4f}")
            logger.info(f"Max Drawdown: ${best_result['max_drawdown_dollars']:,.2f} ({best_result['max_drawdown_percent']:.2f}%)")
            logger.info("")
        
        # Show top 5 parameter combinations
        logger.info("TOP 5 PARAMETER COMBINATIONS:")
        logger.info("="*80)
        sorted_results = sorted(results.all_results, key=lambda x: x['sharpe_ratio'], reverse=True)
        for i, result in enumerate(sorted_results[:5], 1):
            logger.info(f"\n#{i} - Sharpe: {result['sharpe_ratio']:.4f}, P&L: ${result['total_pnl']:+,.2f}, Trades: {result['total_trades']}")
            logger.info(f"   Parameters: {result['params']}")
        
        logger.info("")
        logger.info("="*80)
        
        # Save results to JSON file
        output_file = 'optimization_results.json'
        with open(output_file, 'w') as f:
            json.dump({
                'best_params': results.best_params,
                'best_score': results.best_score,
                'best_metrics': best_result,
                'top_5': sorted_results[:5],
                'optimization_date': datetime.now().isoformat(),
                'backtest_period': {
                    'start': start_date.isoformat(),
                    'end': end_date.isoformat()
                },
                'total_combinations_tested': results.total_combinations,
                'successful_runs': results.successful_runs
            }, f, indent=2, default=str)
        
        logger.info(f"Results saved to: {output_file}")
        logger.info("")
        
        # Generate code snippet to update config.py
        logger.info("TO UPDATE config.py WITH BEST PARAMETERS:")
        logger.info("="*80)
        logger.info("Update these values in the BotConfiguration dataclass:")
        logger.info("")
        for param, value in results.best_params.items():
            if isinstance(value, bool):
                logger.info(f"    {param}: bool = {value}")
            elif isinstance(value, int):
                logger.info(f"    {param}: int = {value}")
            elif isinstance(value, float):
                logger.info(f"    {param}: float = {value}")
        logger.info("")
        logger.info("="*80)
        
        return results
        
    except Exception as e:
        logger.error(f"Optimization failed: {e}", exc_info=True)
        raise


if __name__ == '__main__':
    try:
        results = main()
        sys.exit(0)
    except Exception as e:
        logging.error(f"Fatal error: {e}", exc_info=True)
        sys.exit(1)

"""
Parameter Optimization Framework for Backtesting
Implements grid search and walk-forward analysis to find optimal strategy parameters
"""

import logging
from typing import Dict, List, Any, Callable, Optional, Tuple
from datetime import datetime, timedelta
from dataclasses import dataclass
from itertools import product
from concurrent.futures import ProcessPoolExecutor, as_completed
import copy

from backtesting import BacktestEngine, BacktestConfig


@dataclass
class OptimizationResult:
    """Results from parameter optimization"""
    best_params: Dict[str, Any]
    best_score: float
    all_results: List[Dict[str, Any]]
    optimization_metric: str
    total_combinations: int
    successful_runs: int


class ParameterOptimizer:
    """
    Optimizes strategy parameters using grid search and walk-forward analysis.
    Helps find the best parameter combination while avoiding overfitting.
    """
    
    def __init__(self, backtest_config: BacktestConfig, bot_config: Dict[str, Any], 
                 param_ranges: Dict[str, List[Any]]):
        """
        Initialize parameter optimizer.
        
        Args:
            backtest_config: Backtest configuration
            bot_config: Bot configuration  
            param_ranges: Dictionary mapping parameter names to lists of values to test.
                         Example: {'vwap_period': [20, 30, 40], 'band_multiplier': [1.0, 1.5, 2.0]}
        """
        self.backtest_config = backtest_config
        self.bot_config = bot_config
        self.param_ranges = param_ranges
        self.logger = logging.getLogger(__name__)
        
    def grid_search(self, strategy_func: Callable, metric: str = 'sharpe_ratio',
                    n_jobs: int = 1) -> OptimizationResult:
        """
        Perform grid search over parameter space.
        
        Args:
            strategy_func: Strategy function to backtest
            metric: Metric to optimize ('sharpe_ratio', 'profit_factor', 'total_pnl', etc.)
            n_jobs: Number of parallel jobs (1 = sequential)
            
        Returns:
            OptimizationResult with best parameters and all results
        """
        self.logger.info("="*60)
        self.logger.info("Starting Parameter Optimization - Grid Search")
        self.logger.info("="*60)
        self.logger.info(f"Optimization metric: {metric}")
        self.logger.info(f"Parameter ranges:")
        for param, values in self.param_ranges.items():
            self.logger.info(f"  {param}: {values}")
        
        # Generate all parameter combinations
        param_names = list(self.param_ranges.keys())
        param_values = [self.param_ranges[name] for name in param_names]
        combinations = list(product(*param_values))
        
        total_combinations = len(combinations)
        self.logger.info(f"Total combinations to test: {total_combinations}")
        
        # Run backtests for each combination
        results = []
        
        if n_jobs == 1:
            # Sequential execution
            for i, combo in enumerate(combinations, 1):
                params = dict(zip(param_names, combo))
                self.logger.info(f"Testing combination {i}/{total_combinations}: {params}")
                
                result = self._run_backtest_with_params(strategy_func, params)
                if result is not None:
                    results.append(result)
        else:
            # Parallel execution
            with ProcessPoolExecutor(max_workers=n_jobs) as executor:
                futures = {}
                for combo in combinations:
                    params = dict(zip(param_names, combo))
                    future = executor.submit(self._run_backtest_with_params, strategy_func, params)
                    futures[future] = params
                
                for i, future in enumerate(as_completed(futures), 1):
                    params = futures[future]
                    self.logger.info(f"Completed {i}/{total_combinations}: {params}")
                    result = future.result()
                    if result is not None:
                        results.append(result)
        
        # Find best parameters
        if len(results) == 0:
            raise ValueError("No successful backtest runs")
            
        best_result = max(results, key=lambda x: x[metric])
        best_params = best_result['params']
        best_score = best_result[metric]
        
        self.logger.info("="*60)
        self.logger.info("Optimization Complete")
        self.logger.info("="*60)
        self.logger.info(f"Best parameters: {best_params}")
        self.logger.info(f"Best {metric}: {best_score:.4f}")
        
        return OptimizationResult(
            best_params=best_params,
            best_score=best_score,
            all_results=results,
            optimization_metric=metric,
            total_combinations=total_combinations,
            successful_runs=len(results)
        )
    
    def walk_forward_analysis(self, strategy_func: Callable, window_size_days: int = 30,
                            test_size_days: int = 7, metric: str = 'sharpe_ratio') -> Dict[str, Any]:
        """
        Perform walk-forward analysis to validate parameter robustness.
        
        This technique:
        1. Splits data into training and testing windows
        2. Optimizes parameters on training window
        3. Tests performance on out-of-sample test window
        4. Rolls forward and repeats
        
        Args:
            strategy_func: Strategy function to backtest
            window_size_days: Size of training window in days
            test_size_days: Size of test window in days
            metric: Metric to optimize
            
        Returns:
            Dictionary with walk-forward results and aggregate statistics
        """
        self.logger.info("="*60)
        self.logger.info("Starting Walk-Forward Analysis")
        self.logger.info("="*60)
        self.logger.info(f"Training window: {window_size_days} days")
        self.logger.info(f"Test window: {test_size_days} days")
        
        # Calculate walk-forward windows
        total_days = (self.backtest_config.end_date - self.backtest_config.start_date).days
        step_size_days = test_size_days
        
        windows = []
        current_start = self.backtest_config.start_date
        
        while (current_start + timedelta(days=window_size_days + test_size_days)) <= self.backtest_config.end_date:
            train_start = current_start
            train_end = current_start + timedelta(days=window_size_days)
            test_start = train_end
            test_end = test_start + timedelta(days=test_size_days)
            
            windows.append({
                'train_start': train_start,
                'train_end': train_end,
                'test_start': test_start,
                'test_end': test_end
            })
            
            current_start += timedelta(days=step_size_days)
        
        self.logger.info(f"Number of walk-forward windows: {len(windows)}")
        
        # Run optimization for each window
        window_results = []
        
        for i, window in enumerate(windows, 1):
            self.logger.info(f"\nWindow {i}/{len(windows)}")
            self.logger.info(f"  Train: {window['train_start'].date()} to {window['train_end'].date()}")
            self.logger.info(f"  Test:  {window['test_start'].date()} to {window['test_end'].date()}")
            
            # Optimize on training window
            train_config = copy.deepcopy(self.backtest_config)
            train_config.start_date = window['train_start']
            train_config.end_date = window['train_end']
            
            train_optimizer = ParameterOptimizer(train_config, self.bot_config, self.param_ranges)
            train_result = train_optimizer.grid_search(strategy_func, metric=metric)
            
            # Test on out-of-sample window
            test_config = copy.deepcopy(self.backtest_config)
            test_config.start_date = window['test_start']
            test_config.end_date = window['test_end']
            
            test_result = self._run_backtest_with_params(strategy_func, train_result.best_params, test_config)
            
            window_results.append({
                'window': i,
                'train_params': train_result.best_params,
                'train_score': train_result.best_score,
                'test_score': test_result[metric] if test_result else 0.0,
                'test_metrics': test_result
            })
            
            self.logger.info(f"  Train {metric}: {train_result.best_score:.4f}")
            self.logger.info(f"  Test {metric}:  {test_result[metric] if test_result else 0.0:.4f}")
        
        # Calculate aggregate statistics
        train_scores = [w['train_score'] for w in window_results]
        test_scores = [w['test_score'] for w in window_results]
        
        avg_train_score = sum(train_scores) / len(train_scores)
        avg_test_score = sum(test_scores) / len(test_scores)
        
        self.logger.info("="*60)
        self.logger.info("Walk-Forward Analysis Complete")
        self.logger.info("="*60)
        self.logger.info(f"Average train {metric}: {avg_train_score:.4f}")
        self.logger.info(f"Average test {metric}:  {avg_test_score:.4f}")
        self.logger.info(f"Train/Test ratio: {avg_test_score/avg_train_score:.2%}" if avg_train_score != 0 else "N/A")
        
        return {
            'windows': window_results,
            'avg_train_score': avg_train_score,
            'avg_test_score': avg_test_score,
            'num_windows': len(windows),
            'metric': metric
        }
    
    def _run_backtest_with_params(self, strategy_func: Callable, params: Dict[str, Any],
                                  config: Optional[BacktestConfig] = None) -> Optional[Dict[str, Any]]:
        """
        Run a backtest with specific parameter values.
        
        Args:
            strategy_func: Strategy function to backtest
            params: Parameter values to use
            config: Optional custom backtest config (uses self.backtest_config if None)
            
        Returns:
            Performance metrics dictionary with params, or None if backtest failed
        """
        try:
            # Create modified bot config with new parameters
            bot_config = copy.deepcopy(self.bot_config)
            bot_config.update(params)
            
            # Run backtest
            backtest_config = config if config is not None else self.backtest_config
            engine = BacktestEngine(backtest_config, bot_config)
            results = engine.run_with_strategy(strategy_func)
            
            # Add parameters to results
            results['params'] = params
            
            return results
            
        except Exception as e:
            self.logger.error(f"Error running backtest with params {params}: {e}")
            return None

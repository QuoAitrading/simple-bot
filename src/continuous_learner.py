"""
Continuous Learning Module
===========================
Optimizes bot parameters through iterative backtesting.

Uses evolutionary strategies to explore parameter space and find
optimal configurations that maximize profitability while maintaining
acceptable risk levels.
"""

import json
import logging
import os
import random
from typing import Dict, List, Optional, Any, Tuple, Callable
from datetime import datetime
from collections import deque

logger = logging.getLogger('continuous_learner')


class ContinuousLearner:
    """
    Continuously learns and optimizes trading parameters through backtesting.
    """
    
    def __init__(self, history_file: str = "data/learning_history.json"):
        """
        Initialize continuous learner.
        
        Args:
            history_file: Path to save learning history
        """
        self.history_file = history_file
        self.learning_history = []
        self.best_params = None
        self.best_score = float('-inf')
        self.iteration = 0
        
        # Load existing history if available
        self.load_history()
        
        logger.info(f"✓ Continuous Learner initialized")
        logger.info(f"  History file: {self.history_file}")
        logger.info(f"  Previous iterations: {self.iteration}")
    
    def generate_random_params(self) -> Dict[str, Any]:
        """
        Generate random parameter set for exploration.
        
        Returns:
            Dictionary of random parameters
        """
        params = {
            # VWAP bands
            'vwap_std_dev_1': round(random.uniform(2.0, 3.2), 1),
            'vwap_std_dev_2': round(random.uniform(1.6, 2.6), 1),
            'vwap_std_dev_3': round(random.uniform(3.2, 4.5), 1),
            
            # RSI
            'rsi_period': random.choice([8, 9, 10, 11, 12, 14]),
            'rsi_oversold': random.randint(25, 40),
            'rsi_overbought': random.randint(60, 75),
            
            # Risk management
            'stop_loss_atr_multiplier': round(random.uniform(2.5, 5.0), 1),
            'profit_target_atr_multiplier': round(random.uniform(3.5, 6.0), 1),
            
            # Breakeven
            'breakeven_profit_threshold_ticks': random.randint(6, 20),
            'breakeven_stop_offset_ticks': random.randint(1, 4),
            
            # Trailing
            'trailing_stop_distance_ticks': random.randint(8, 24),
            'trailing_stop_min_profit_ticks': random.randint(10, 30),
        }
        
        return params
    
    def mutate_params(self, params: Dict[str, Any], mutation_rate: float = 0.3) -> Dict[str, Any]:
        """
        Create mutated version of parameters for exploration.
        
        Args:
            params: Base parameters to mutate
            mutation_rate: Probability of mutating each parameter
            
        Returns:
            Mutated parameter set
        """
        mutated = params.copy()
        
        for key in mutated.keys():
            if random.random() < mutation_rate:
                if key in ['vwap_std_dev_1', 'vwap_std_dev_2', 'vwap_std_dev_3']:
                    # Mutate VWAP bands
                    mutated[key] = round(mutated[key] + random.uniform(-0.3, 0.3), 1)
                    mutated[key] = max(1.0, min(5.0, mutated[key]))
                
                elif key == 'rsi_period':
                    # Mutate RSI period
                    mutated[key] = max(5, min(20, mutated[key] + random.choice([-2, -1, 1, 2])))
                
                elif key in ['rsi_oversold', 'rsi_overbought']:
                    # Mutate RSI thresholds
                    mutated[key] = mutated[key] + random.randint(-5, 5)
                    if key == 'rsi_oversold':
                        mutated[key] = max(20, min(45, mutated[key]))
                    else:
                        mutated[key] = max(55, min(80, mutated[key]))
                
                elif 'atr_multiplier' in key:
                    # Mutate ATR multipliers
                    mutated[key] = round(mutated[key] + random.uniform(-0.5, 0.5), 1)
                    mutated[key] = max(1.5, min(7.0, mutated[key]))
                
                elif 'ticks' in key:
                    # Mutate tick-based parameters
                    mutated[key] = mutated[key] + random.randint(-3, 3)
                    mutated[key] = max(1, min(50, mutated[key]))
        
        return mutated
    
    def calculate_fitness(self, results: Dict[str, Any]) -> float:
        """
        Calculate fitness score from backtest results.
        Balances profitability with risk metrics.
        
        Args:
            results: Backtest results dictionary
            
        Returns:
            Fitness score (higher is better)
        """
        pnl = results.get('total_pnl', 0)
        win_rate = results.get('win_rate', 0)
        profit_factor = results.get('profit_factor', 0)
        sharpe = results.get('sharpe_ratio', 0)
        max_dd = abs(results.get('max_drawdown', 0))
        total_trades = results.get('total_trades', 0)
        
        # Penalize if too few trades (less reliable)
        if total_trades < 10:
            trade_penalty = 0.5
        elif total_trades < 20:
            trade_penalty = 0.8
        else:
            trade_penalty = 1.0
        
        # Weighted fitness function
        # - PnL is primary driver
        # - Win rate bonus (prefer consistency)
        # - Profit factor bonus (prefer good risk/reward)
        # - Sharpe ratio bonus (prefer smooth returns)
        # - Drawdown penalty (avoid volatile strategies)
        
        fitness = (
            pnl * 1.0 +                          # Raw profit
            (win_rate - 50) * 10 +               # Bonus for >50% win rate
            (profit_factor - 1.5) * 500 +        # Bonus for PF > 1.5
            sharpe * 200 +                       # Sharpe ratio bonus
            -max_dd * 0.5                        # Drawdown penalty
        ) * trade_penalty
        
        return fitness
    
    def record_iteration(self, params: Dict[str, Any], results: Dict[str, Any]) -> None:
        """
        Record iteration results.
        
        Args:
            params: Parameters used
            results: Backtest results
        """
        self.iteration += 1
        fitness = self.calculate_fitness(results)
        
        record = {
            'iteration': self.iteration,
            'timestamp': datetime.now().isoformat(),
            'params': params,
            'results': results,
            'fitness': fitness
        }
        
        self.learning_history.append(record)
        
        # Update best if this is better
        if fitness > self.best_score:
            self.best_score = fitness
            self.best_params = params.copy()
            logger.info(f"✓ New best parameters found! Fitness: {fitness:.2f}, P&L: ${results.get('total_pnl', 0):+,.2f}")
        
        # Keep history manageable (last 500 iterations)
        if len(self.learning_history) > 500:
            self.learning_history = self.learning_history[-500:]
    
    def save_history(self) -> None:
        """Save learning history to file."""
        try:
            # Ensure data directory exists
            os.makedirs(os.path.dirname(self.history_file), exist_ok=True)
            
            data = {
                'iteration': self.iteration,
                'best_params': self.best_params,
                'best_score': self.best_score,
                'history': self.learning_history[-100:],  # Save last 100 iterations
                'last_updated': datetime.now().isoformat()
            }
            
            with open(self.history_file, 'w') as f:
                json.dump(data, f, indent=2)
            
            logger.debug(f"Learning history saved to {self.history_file}")
        except Exception as e:
            logger.error(f"Failed to save learning history: {e}")
    
    def load_history(self) -> None:
        """Load learning history from file."""
        try:
            if os.path.exists(self.history_file):
                with open(self.history_file, 'r') as f:
                    data = json.load(f)
                
                self.iteration = data.get('iteration', 0)
                self.best_params = data.get('best_params')
                self.best_score = data.get('best_score', float('-inf'))
                self.learning_history = data.get('history', [])
                
                logger.info(f"✓ Loaded learning history: {self.iteration} iterations")
                if self.best_params:
                    logger.info(f"  Best score: {self.best_score:.2f}")
        except Exception as e:
            logger.warning(f"Could not load learning history: {e}")
    
    def get_market_insights(self) -> Dict[str, Any]:
        """
        Analyze learning history to extract market insights.
        
        Returns:
            Dictionary of insights
        """
        if not self.learning_history:
            return {}
        
        # Analyze recent performance trends
        recent = self.learning_history[-20:] if len(self.learning_history) >= 20 else self.learning_history
        
        avg_win_rate = sum(r['results'].get('win_rate', 0) for r in recent) / len(recent)
        avg_pf = sum(r['results'].get('profit_factor', 0) for r in recent) / len(recent)
        
        insights = {
            'total_iterations': self.iteration,
            'best_fitness': self.best_score,
            'recent_avg_win_rate': round(avg_win_rate, 1),
            'recent_avg_profit_factor': round(avg_pf, 2),
            'learning_status': 'improving' if len(recent) >= 10 and recent[-1]['fitness'] > recent[0]['fitness'] else 'exploring'
        }
        
        return insights


def run_continuous_learning(
    backtest_runner: Callable[[Dict[str, Any]], Dict[str, Any]],
    max_iterations: int = 50,
    mutation_rate: float = 0.3
) -> Tuple[Dict[str, Any], Dict[str, Any]]:
    """
    Run continuous learning process.
    
    Args:
        backtest_runner: Function that runs backtest with given parameters
        max_iterations: Number of learning iterations
        mutation_rate: Probability of parameter mutation
        
    Returns:
        Tuple of (best_params, insights)
    """
    learner = ContinuousLearner()
    
    # Phase 1: Random exploration (first 25% of iterations)
    exploration_iterations = max(10, max_iterations // 4)
    
    logger.info(f"\n{'='*70}")
    logger.info(f"PHASE 1: RANDOM EXPLORATION ({exploration_iterations} iterations)")
    logger.info(f"{'='*70}")
    
    for i in range(exploration_iterations):
        params = learner.generate_random_params()
        
        logger.info(f"\nIteration {i+1}/{exploration_iterations}: Testing random parameters...")
        results = backtest_runner(params)
        
        if results:
            learner.record_iteration(params, results)
            learner.save_history()
    
    # Phase 2: Exploitation with mutation (remaining iterations)
    exploitation_iterations = max_iterations - exploration_iterations
    
    logger.info(f"\n{'='*70}")
    logger.info(f"PHASE 2: EXPLOITATION & REFINEMENT ({exploitation_iterations} iterations)")
    logger.info(f"{'='*70}")
    
    for i in range(exploitation_iterations):
        # Use best params as base and mutate
        if learner.best_params:
            params = learner.mutate_params(learner.best_params, mutation_rate)
        else:
            params = learner.generate_random_params()
        
        logger.info(f"\nIteration {exploration_iterations + i + 1}/{max_iterations}: Refining best parameters...")
        results = backtest_runner(params)
        
        if results:
            learner.record_iteration(params, results)
            learner.save_history()
    
    # Get insights
    insights = learner.get_market_insights()
    
    return learner.best_params, insights

"""
Regime-Aware Learning Module
=============================
Learns different trading strategies for different market conditions.

Market Regimes:
- HIGH_VOL_TRENDING: High volatility + strong trend (ADX > 25, ATR > threshold)
- HIGH_VOL_CHOPPY: High volatility + weak trend (ATR > threshold, ADX < 25)
- LOW_VOL_TRENDING: Low volatility + strong trend (ADX > 25, ATR < threshold)
- LOW_VOL_RANGING: Low volatility + weak trend (ATR < threshold, ADX < 25)
- NORMAL: Moderate conditions that don't fit other categories

The learner optimizes parameters separately for each regime, allowing the bot
to adapt its strategy based on current market conditions.
"""

import json
import logging
import os
from typing import Dict, List, Optional, Any, Tuple
from datetime import datetime
import random
from collections import defaultdict

logger = logging.getLogger(__name__)


class RegimeAwareLearner:
    """
    Learns optimal trading parameters for different market regimes.
    """
    
    def __init__(self, base_config: Dict[str, Any], history_file: str = "data/regime_learning_history.json"):
        """
        Initialize regime-aware learner.
        
        Args:
            base_config: Base bot configuration dictionary
            history_file: Path to save learning history
        """
        self.base_config = base_config
        self.history_file = history_file
        
        # Regime categories
        self.regimes = [
            'HIGH_VOL_TRENDING',
            'HIGH_VOL_CHOPPY',
            'LOW_VOL_TRENDING',
            'LOW_VOL_RANGING',
            'NORMAL'
        ]
        
        # Learning history per regime
        self.regime_history = {regime: [] for regime in self.regimes}
        
        # Best parameters per regime
        self.best_params_per_regime = {regime: None for regime in self.regimes}
        self.best_pnl_per_regime = {regime: float('-inf') for regime in self.regimes}
        
        # Global iteration counter
        self.global_iteration = 0
        
        # Load existing history if available
        self.load_regime_history()
        
        logger.info(f"✓ Regime-Aware Learner initialized")
        logger.info(f"  Regimes: {', '.join(self.regimes)}")
        logger.info(f"  History file: {self.history_file}")
    
    def classify_regime_from_backtest(self, bars: List[Dict[str, Any]]) -> Optional[str]:
        """
        Classify market regime from backtest bars.
        
        Args:
            bars: List of price bars from backtest
            
        Returns:
            Regime classification string or None if insufficient data
        """
        if not bars or len(bars) < 50:
            logger.warning("Insufficient bars for regime classification")
            return None
        
        # Calculate ATR (Average True Range) - measure of volatility
        atr_values = []
        for i in range(1, min(len(bars), 100)):
            high_low = bars[i]['high'] - bars[i]['low']
            high_close = abs(bars[i]['high'] - bars[i-1]['close'])
            low_close = abs(bars[i]['low'] - bars[i-1]['close'])
            true_range = max(high_low, high_close, low_close)
            atr_values.append(true_range)
        
        avg_atr = sum(atr_values) / len(atr_values) if atr_values else 0
        
        # Calculate ADX (Average Directional Index) - measure of trend strength
        # Simplified ADX calculation using price movement
        plus_dm_values = []
        minus_dm_values = []
        
        for i in range(1, min(len(bars), 50)):
            high_diff = bars[i]['high'] - bars[i-1]['high']
            low_diff = bars[i-1]['low'] - bars[i]['low']
            
            plus_dm = high_diff if high_diff > low_diff and high_diff > 0 else 0
            minus_dm = low_diff if low_diff > high_diff and low_diff > 0 else 0
            
            plus_dm_values.append(plus_dm)
            minus_dm_values.append(minus_dm)
        
        avg_plus_dm = sum(plus_dm_values) / len(plus_dm_values) if plus_dm_values else 0
        avg_minus_dm = sum(minus_dm_values) / len(minus_dm_values) if minus_dm_values else 0
        
        # Simplified ADX (directional movement index)
        if avg_atr > 0:
            di_plus = (avg_plus_dm / avg_atr) * 100
            di_minus = (avg_minus_dm / avg_atr) * 100
            di_diff = abs(di_plus - di_minus)
            di_sum = di_plus + di_minus
            adx = (di_diff / di_sum * 100) if di_sum > 0 else 0
        else:
            adx = 0
        
        # Determine volatility threshold (relative to price)
        avg_price = sum(bar['close'] for bar in bars[:50]) / min(len(bars), 50)
        atr_pct = (avg_atr / avg_price) * 100 if avg_price > 0 else 0
        
        high_vol_threshold = 0.15  # 0.15% ATR relative to price
        strong_trend_threshold = 20  # ADX above 20 indicates trend
        
        # Classify regime
        is_high_vol = atr_pct > high_vol_threshold
        is_trending = adx > strong_trend_threshold
        
        if is_high_vol and is_trending:
            regime = 'HIGH_VOL_TRENDING'
        elif is_high_vol and not is_trending:
            regime = 'HIGH_VOL_CHOPPY'
        elif not is_high_vol and is_trending:
            regime = 'LOW_VOL_TRENDING'
        elif not is_high_vol and not is_trending:
            regime = 'LOW_VOL_RANGING'
        else:
            regime = 'NORMAL'
        
        logger.info(f"Regime classified: {regime} (ATR%: {atr_pct:.3f}, ADX: {adx:.1f})")
        return regime
    
    def generate_parameter_set(self, regime: str) -> Dict[str, Any]:
        """
        Generate parameters optimized for specific regime.
        Uses randomization with regime-specific bounds.
        
        Args:
            regime: Market regime classification
            
        Returns:
            Dictionary of parameters to test
        """
        # Base parameter ranges (will be adjusted per regime)
        params = {}
        
        # VWAP bands - adjust based on regime
        if regime == 'HIGH_VOL_CHOPPY':
            # Wider bands for choppy high vol
            params['vwap_std_dev_1'] = round(random.uniform(2.8, 3.5), 1)
            params['vwap_std_dev_2'] = round(random.uniform(2.3, 2.8), 1)
            params['vwap_std_dev_3'] = round(random.uniform(4.0, 5.0), 1)
        elif regime == 'HIGH_VOL_TRENDING':
            # Moderate bands for trending high vol
            params['vwap_std_dev_1'] = round(random.uniform(2.3, 3.0), 1)
            params['vwap_std_dev_2'] = round(random.uniform(1.9, 2.5), 1)
            params['vwap_std_dev_3'] = round(random.uniform(3.5, 4.5), 1)
        elif regime == 'LOW_VOL_RANGING':
            # Tighter bands for low vol ranging
            params['vwap_std_dev_1'] = round(random.uniform(1.8, 2.5), 1)
            params['vwap_std_dev_2'] = round(random.uniform(1.5, 2.1), 1)
            params['vwap_std_dev_3'] = round(random.uniform(3.0, 3.8), 1)
        elif regime == 'LOW_VOL_TRENDING':
            # Moderate-tight bands for low vol trending
            params['vwap_std_dev_1'] = round(random.uniform(2.0, 2.7), 1)
            params['vwap_std_dev_2'] = round(random.uniform(1.7, 2.3), 1)
            params['vwap_std_dev_3'] = round(random.uniform(3.2, 4.0), 1)
        else:  # NORMAL
            # Standard ranges
            params['vwap_std_dev_1'] = round(random.uniform(2.2, 2.8), 1)
            params['vwap_std_dev_2'] = round(random.uniform(1.8, 2.4), 1)
            params['vwap_std_dev_3'] = round(random.uniform(3.5, 4.2), 1)
        
        # RSI parameters
        params['rsi_period'] = random.choice([8, 9, 10, 11, 12, 14])
        
        if regime in ['HIGH_VOL_CHOPPY', 'LOW_VOL_RANGING']:
            # More extreme RSI for ranging/choppy markets
            params['rsi_oversold'] = random.randint(25, 35)
            params['rsi_overbought'] = random.randint(65, 75)
        else:
            # Moderate RSI for trending markets
            params['rsi_oversold'] = random.randint(30, 40)
            params['rsi_overbought'] = random.randint(60, 70)
        
        # Risk management - adjust based on regime
        if regime in ['HIGH_VOL_CHOPPY']:
            # Wider stops for choppy markets
            params['stop_loss_atr_multiplier'] = round(random.uniform(3.8, 5.0), 1)
            params['profit_target_atr_multiplier'] = round(random.uniform(4.5, 6.0), 1)
        elif regime in ['HIGH_VOL_TRENDING']:
            # Moderate stops for volatile trends
            params['stop_loss_atr_multiplier'] = round(random.uniform(3.2, 4.2), 1)
            params['profit_target_atr_multiplier'] = round(random.uniform(4.2, 5.5), 1)
        elif regime in ['LOW_VOL_RANGING', 'LOW_VOL_TRENDING']:
            # Tighter stops for low vol
            params['stop_loss_atr_multiplier'] = round(random.uniform(2.8, 3.8), 1)
            params['profit_target_atr_multiplier'] = round(random.uniform(3.8, 5.0), 1)
        else:  # NORMAL
            params['stop_loss_atr_multiplier'] = round(random.uniform(3.0, 4.0), 1)
            params['profit_target_atr_multiplier'] = round(random.uniform(4.0, 5.2), 1)
        
        # Breakeven parameters
        params['breakeven_profit_threshold_ticks'] = random.randint(8, 16)
        params['breakeven_stop_offset_ticks'] = random.randint(1, 3)
        
        # Trailing stop parameters
        params['trailing_stop_distance_ticks'] = random.randint(10, 20)
        params['trailing_stop_min_profit_ticks'] = random.randint(12, 24)
        
        return params
    
    def record_backtest(self, params: Dict[str, Any], results: Dict[str, Any], bars: List[Dict[str, Any]]) -> None:
        """
        Record backtest results for a specific regime.
        
        Args:
            params: Parameters used in backtest
            results: Backtest results dictionary
            bars: Price bars for regime classification
        """
        regime = self.classify_regime_from_backtest(bars)
        if not regime:
            return
        
        self.global_iteration += 1
        
        # Record result
        record = {
            'iteration': self.global_iteration,
            'timestamp': datetime.now().isoformat(),
            'params': params,
            'results': results,
            'pnl': results.get('total_pnl', 0),
            'win_rate': results.get('win_rate', 0),
            'profit_factor': results.get('profit_factor', 0),
            'sharpe_ratio': results.get('sharpe_ratio', 0),
            'total_trades': results.get('total_trades', 0)
        }
        
        self.regime_history[regime].append(record)
        
        # Update best params if this is better
        if record['pnl'] > self.best_pnl_per_regime[regime]:
            self.best_pnl_per_regime[regime] = record['pnl']
            self.best_params_per_regime[regime] = params.copy()
            logger.info(f"✓ New best for {regime}: ${record['pnl']:+,.2f}")
    
    def save_regime_history(self) -> None:
        """Save regime learning history to file."""
        try:
            # Ensure data directory exists
            os.makedirs(os.path.dirname(self.history_file), exist_ok=True)
            
            data = {
                'global_iteration': self.global_iteration,
                'regimes': self.regimes,
                'history': self.regime_history,
                'best_params': self.best_params_per_regime,
                'best_pnl': self.best_pnl_per_regime,
                'last_updated': datetime.now().isoformat()
            }
            
            with open(self.history_file, 'w') as f:
                json.dump(data, f, indent=2)
            
            logger.debug(f"Regime history saved to {self.history_file}")
        except Exception as e:
            logger.error(f"Failed to save regime history: {e}")
    
    def load_regime_history(self) -> None:
        """Load regime learning history from file."""
        try:
            if os.path.exists(self.history_file):
                with open(self.history_file, 'r') as f:
                    data = json.load(f)
                
                self.global_iteration = data.get('global_iteration', 0)
                self.regime_history = data.get('history', {regime: [] for regime in self.regimes})
                self.best_params_per_regime = data.get('best_params', {regime: None for regime in self.regimes})
                self.best_pnl_per_regime = data.get('best_pnl', {regime: float('-inf') for regime in self.regimes})
                
                logger.info(f"✓ Loaded regime history: {self.global_iteration} iterations")
        except Exception as e:
            logger.warning(f"Could not load regime history: {e}")
    
    def print_regime_summary(self) -> None:
        """Print summary of learning progress for each regime."""
        print("\n" + "="*70)
        print("REGIME LEARNING SUMMARY")
        print("="*70)
        
        for regime in self.regimes:
            print(f"\n{regime}:")
            print(f"  Iterations: {len(self.regime_history.get(regime, []))}")
            
            if self.best_params_per_regime.get(regime):
                print(f"  Best P&L: ${self.best_pnl_per_regime[regime]:+,.2f}")
                print(f"  Best Params:")
                for key, value in self.best_params_per_regime[regime].items():
                    print(f"    {key}: {value}")
            else:
                print(f"  No data yet")
        
        print("="*70)
    
    def get_regime_params(self, regime: str) -> Optional[Dict[str, Any]]:
        """
        Get best learned parameters for a specific regime.
        
        Args:
            regime: Market regime classification
            
        Returns:
            Best parameters for regime or None if no data
        """
        return self.best_params_per_regime.get(regime)

"""
Focused ML Optimizer - Learns Only Real Parameters
Optimizes what actually exists and works: RSI, VWAP, filters, risk management
No gates, no restrictions - just better trading
"""

import subprocess
import re
import json
import os
import numpy as np
from pathlib import Path
from datetime import datetime
from dataclasses import dataclass, asdict
from typing import List, Dict, Tuple
import time

try:
    from skopt import gp_minimize
    from skopt.space import Real, Integer, Categorical
    from skopt.utils import use_named_args
    HAS_SKOPT = True
except ImportError:
    HAS_SKOPT = False


@dataclass
class TradeResult:
    # Entry Parameters
    rsi_period: int
    rsi_oversold: int
    rsi_overbought: int
    vwap_entry: float
    vwap_exit: float
    use_vwap_direction: bool
    max_trades_per_day: int
    use_atr_stops: bool
    stop_atr_mult: float
    target_atr_mult: float
    use_trend_filter: bool
    ema_period: int
    
    # Advanced Exit Management Parameters
    breakeven_enabled: bool
    breakeven_profit_threshold_ticks: int
    breakeven_stop_offset_ticks: int
    trailing_stop_enabled: bool
    trailing_stop_distance_ticks: int
    trailing_stop_min_profit_ticks: int
    time_decay_enabled: bool
    time_decay_50_tightening: float
    time_decay_75_tightening: float
    time_decay_90_tightening: float
    partial_exits_enabled: bool
    partial_exit_1_percentage: float
    partial_exit_1_r_multiple: float
    partial_exit_2_percentage: float
    partial_exit_2_r_multiple: float
    
    # Performance
    trades: int
    win_rate: float
    profit: float
    profit_factor: float
    sharpe: float
    max_drawdown: float
    avg_win: float
    avg_loss: float
    
    fitness: float
    timestamp: str
    iteration: int


class FocusedMLOptimizer:
    def __init__(self):
        self.config_path = Path("config.py")
        self.results_file = Path("ml_learning_history.json")
        self.baseline_backup = Path("config_baseline_backup.py")
        self.results_history: List[TradeResult] = []
        self.best_result = None
        self.baseline_fitness = None  # Track baseline performance
        self.iteration = 0
        
        self.baseline = self.read_baseline()
        self.save_baseline_backup()  # Always save current as backup
        self.load_history()
    
    def read_baseline(self) -> Dict:
        """Read current baseline config"""
        try:
            content = self.config_path.read_text(encoding='utf-8')
            
            baseline = {
                # Entry parameters
                'rsi_period': int(re.search(r'rsi_period:\s*int\s*=\s*(\d+)', content).group(1)),
                'rsi_oversold': int(re.search(r'rsi_oversold:\s*int\s*=\s*(\d+)', content).group(1)),
                'rsi_overbought': int(re.search(r'rsi_overbought:\s*int\s*=\s*(\d+)', content).group(1)),
                'vwap_entry': float(re.search(r'vwap_std_dev_2:\s*float\s*=\s*([\d.]+)', content).group(1)),
                'vwap_exit': float(re.search(r'vwap_std_dev_3:\s*float\s*=\s*([\d.]+)', content).group(1)),
                'max_trades_per_day': int(re.search(r'max_trades_per_day:\s*int\s*=\s*(\d+)', content).group(1)),
                'use_trend': r'use_trend_filter:\s*bool\s*=\s*True' in content,
                'ema_period': int(re.search(r'trend_ema_period:\s*int\s*=\s*(\d+)', content).group(1)),
                'stop_atr_mult': float(re.search(r'stop_loss_atr_multiplier:\s*float\s*=\s*([\d.]+)', content).group(1)),
                'target_atr_mult': float(re.search(r'profit_target_atr_multiplier:\s*float\s*=\s*([\d.]+)', content).group(1)),
                
                # Advanced exit management
                'breakeven_enabled': r'breakeven_enabled:\s*bool\s*=\s*True' in content,
                'breakeven_profit_threshold': int(re.search(r'breakeven_profit_threshold_ticks:\s*int\s*=\s*(\d+)', content).group(1)),
                'breakeven_stop_offset': int(re.search(r'breakeven_stop_offset_ticks:\s*int\s*=\s*(\d+)', content).group(1)),
                'trailing_enabled': r'trailing_stop_enabled:\s*bool\s*=\s*True' in content,
                'trailing_distance': int(re.search(r'trailing_stop_distance_ticks:\s*int\s*=\s*(\d+)', content).group(1)),
                'trailing_min_profit': int(re.search(r'trailing_stop_min_profit_ticks:\s*int\s*=\s*(\d+)', content).group(1)),
                'time_decay_enabled': r'time_decay_enabled:\s*bool\s*=\s*True' in content,
                'time_decay_50': float(re.search(r'time_decay_50_percent_tightening:\s*float\s*=\s*([\d.]+)', content).group(1)),
                'time_decay_75': float(re.search(r'time_decay_75_percent_tightening:\s*float\s*=\s*([\d.]+)', content).group(1)),
                'time_decay_90': float(re.search(r'time_decay_90_percent_tightening:\s*float\s*=\s*([\d.]+)', content).group(1)),
                'partial_enabled': r'partial_exits_enabled:\s*bool\s*=\s*True' in content,
                'partial_1_pct': float(re.search(r'partial_exit_1_percentage:\s*float\s*=\s*([\d.]+)', content).group(1)),
                'partial_1_r': float(re.search(r'partial_exit_1_r_multiple:\s*float\s*=\s*([\d.]+)', content).group(1)),
                'partial_2_pct': float(re.search(r'partial_exit_2_percentage:\s*float\s*=\s*([\d.]+)', content).group(1)),
                'partial_2_r': float(re.search(r'partial_exit_2_r_multiple:\s*float\s*=\s*([\d.]+)', content).group(1)),
            }
            
            print("="*80)
            print("ML OPTIMIZER - ADVANCED EXIT LEARNING")
            print("="*80)
            print("Learning entry AND exit management:")
            print(f"   RSI: {baseline['rsi_period']}/{baseline['rsi_oversold']}/{baseline['rsi_overbought']}")
            print(f"   VWAP: {baseline['vwap_entry']:.2f} / {baseline['vwap_exit']:.2f}")
            print(f"   Breakeven: {baseline['breakeven_enabled']} ({baseline['breakeven_profit_threshold']} ticks)")
            print(f"   Trailing: {baseline['trailing_enabled']} ({baseline['trailing_distance']} ticks)")
            print(f"   Time Decay: {baseline['time_decay_enabled']}")
            print(f"   Partial Exits: {baseline['partial_enabled']}")
            print()
            print("Learning EVERYTHING for maximum profit!")
            print("="*80)
            print()
            
            return baseline
        except Exception as e:
            print(f"Error reading config: {e}")
            return {
                # Entry parameters defaults
                'rsi_period': 14, 'rsi_oversold': 25, 'rsi_overbought': 75,
                'vwap_entry': 2.0, 'vwap_exit': 3.5, 'max_trades_per_day': 3,
                'use_trend': False, 'ema_period': 20,
                'stop_atr_mult': 2.0, 'target_atr_mult': 3.5,
                # Exit management defaults
                'breakeven_enabled': True, 'breakeven_profit_threshold': 8, 'breakeven_stop_offset': 1,
                'trailing_enabled': True, 'trailing_distance': 8, 'trailing_min_profit': 12,
                'time_decay_enabled': True, 'time_decay_50': 0.10, 'time_decay_75': 0.20, 'time_decay_90': 0.30,
                'partial_enabled': True, 'partial_1_pct': 0.50, 'partial_1_r': 2.0, 'partial_2_pct': 0.30, 'partial_2_r': 3.0
            }
    
    def save_baseline_backup(self):
        """Save current config as baseline backup"""
        try:
            content = self.config_path.read_text(encoding='utf-8')
            self.baseline_backup.write_text(content, encoding='utf-8')
            print(" Baseline backup saved")
        except Exception as e:
            print(f"Warning: Could not backup baseline: {e}")
    
    def restore_baseline(self):
        """Restore baseline if learning makes things worse"""
        try:
            if self.baseline_backup.exists():
                content = self.baseline_backup.read_text(encoding='utf-8')
                self.config_path.write_text(content, encoding='utf-8')
                print("  REVERTED to baseline (new config was worse)")
                return True
        except Exception as e:
            print(f"Error restoring baseline: {e}")
        return False
    
    def test_baseline_performance(self, days: int = 30) -> float:
        """Test baseline and return its fitness - USES 30 DAYS TO MATCH MANUAL BACKTEST"""
        print("\n Testing baseline performance (30 days)...")
        success, metrics = self.run_backtest(days)
        if success:
            fitness = self.calculate_fitness(metrics)
            print(f"   Baseline: {metrics['trades']} trades, {metrics['win_rate']:.1f}% WR, ${metrics['profit']:,.2f}")
            print(f"   Baseline fitness: {fitness:.0f}\n")
            return fitness
        return -10000
    
    def load_history(self):
        """Load learning history"""
        if self.results_file.exists():
            try:
                with open(self.results_file, 'r') as f:
                    data = json.load(f)
                    self.results_history = [TradeResult(**r) for r in data.get('results', [])]
                    if data.get('best'):
                        self.best_result = TradeResult(**data['best'])
                    self.iteration = data.get('iteration', 0)
                    
                if self.results_history:
                    print(f" Loaded {len(self.results_history)} previous learning sessions")
                if self.best_result:
                    print(f" Best so far: ${self.best_result.profit:,.2f}, {self.best_result.win_rate:.1f}% WR, {self.best_result.trades} trades")
                    print()
            except Exception as e:
                print(f"Starting fresh: {e}\n")
    
    def save_history(self):
        """Save learning progress"""
        def convert_to_serializable(obj):
            """Convert numpy/pandas types to native Python types"""
            import numpy as np
            if isinstance(obj, (np.integer, np.int64)):
                return int(obj)
            elif isinstance(obj, (np.floating, np.float64)):
                return float(obj)
            elif isinstance(obj, (np.bool_, bool)):
                return bool(obj)
            elif isinstance(obj, dict):
                return {k: convert_to_serializable(v) for k, v in obj.items()}
            elif isinstance(obj, list):
                return [convert_to_serializable(item) for item in obj]
            return obj
        
        data = {
            'iteration': int(self.iteration),
            'results': [convert_to_serializable(asdict(r)) for r in self.results_history[-50:]],
            'best': convert_to_serializable(asdict(self.best_result)) if self.best_result else None,
            'last_updated': datetime.now().isoformat()
        }
        with open(self.results_file, 'w') as f:
            json.dump(data, f, indent=2)
    
    def update_config(self, params: Dict) -> bool:
        """Update config with new parameters"""
        try:
            content = self.config_path.read_text(encoding='utf-8')
            
            # Update entry parameters
            content = re.sub(r'(rsi_period:\s*int\s*=\s*)\d+', f'\\g<1>{params["rsi_period"]}', content)
            content = re.sub(r'(rsi_oversold:\s*int\s*=\s*)\d+', f'\\g<1>{params["rsi_oversold"]}', content)
            content = re.sub(r'(rsi_overbought:\s*int\s*=\s*)\d+', f'\\g<1>{params["rsi_overbought"]}', content)
            content = re.sub(r'(vwap_std_dev_2:\s*float\s*=\s*)[\d.]+', f'\\g<1>{params["vwap_entry"]}', content)
            content = re.sub(r'(vwap_std_dev_3:\s*float\s*=\s*)[\d.]+', f'\\g<1>{params["vwap_exit"]}', content)
            content = re.sub(r'(use_vwap_direction_filter:\s*bool\s*=\s*)(True|False)', f'\\g<1>{params["use_vwap_dir"]}', content)
            content = re.sub(r'(use_atr_stops:\s*bool\s*=\s*)(True|False)', f'\\g<1>{params["use_atr"]}', content)
            content = re.sub(r'(stop_loss_atr_multiplier:\s*float\s*=\s*)[\d.]+', f'\\g<1>{params["stop_atr"]}', content)
            content = re.sub(r'(profit_target_atr_multiplier:\s*float\s*=\s*)[\d.]+', f'\\g<1>{params["target_atr"]}', content)
            content = re.sub(r'(use_trend_filter:\s*bool\s*=\s*)(True|False)', f'\\g<1>{params["use_trend"]}', content)
            content = re.sub(r'(trend_ema_period:\s*int\s*=\s*)\d+', f'\\g<1>{params["ema_period"]}', content)
            
            # Update advanced exit management parameters
            content = re.sub(r'(breakeven_enabled:\s*bool\s*=\s*)(True|False)', f'\\g<1>{params["breakeven_enabled"]}', content)
            content = re.sub(r'(breakeven_profit_threshold_ticks:\s*int\s*=\s*)\d+', f'\\g<1>{params["breakeven_threshold"]}', content)
            content = re.sub(r'(breakeven_stop_offset_ticks:\s*int\s*=\s*)\d+', f'\\g<1>{params["breakeven_offset"]}', content)
            content = re.sub(r'(trailing_stop_enabled:\s*bool\s*=\s*)(True|False)', f'\\g<1>{params["trailing_enabled"]}', content)
            content = re.sub(r'(trailing_stop_distance_ticks:\s*int\s*=\s*)\d+', f'\\g<1>{params["trailing_distance"]}', content)
            content = re.sub(r'(trailing_stop_min_profit_ticks:\s*int\s*=\s*)\d+', f'\\g<1>{params["trailing_min_profit"]}', content)
            content = re.sub(r'(time_decay_enabled:\s*bool\s*=\s*)(True|False)', f'\\g<1>{params["time_decay_enabled"]}', content)
            content = re.sub(r'(time_decay_50_percent_tightening:\s*float\s*=\s*)[\d.]+', f'\\g<1>{params["time_decay_50"]}', content)
            content = re.sub(r'(time_decay_75_percent_tightening:\s*float\s*=\s*)[\d.]+', f'\\g<1>{params["time_decay_75"]}', content)
            content = re.sub(r'(time_decay_90_percent_tightening:\s*float\s*=\s*)[\d.]+', f'\\g<1>{params["time_decay_90"]}', content)
            content = re.sub(r'(partial_exits_enabled:\s*bool\s*=\s*)(True|False)', f'\\g<1>{params["partial_enabled"]}', content)
            content = re.sub(r'(partial_exit_1_percentage:\s*float\s*=\s*)[\d.]+', f'\\g<1>{params["partial_1_pct"]}', content)
            content = re.sub(r'(partial_exit_1_r_multiple:\s*float\s*=\s*)[\d.]+', f'\\g<1>{params["partial_1_r"]}', content)
            content = re.sub(r'(partial_exit_2_percentage:\s*float\s*=\s*)[\d.]+', f'\\g<1>{params["partial_2_pct"]}', content)
            content = re.sub(r'(partial_exit_2_r_multiple:\s*float\s*=\s*)[\d.]+', f'\\g<1>{params["partial_2_r"]}', content)
            
            if len(content) < 100:
                raise ValueError("Config corrupted")
            
            self.config_path.write_text(content, encoding='utf-8')
            return True
        except Exception as e:
            print(f"Config update failed: {e}")
            return False
    
    def run_backtest(self, days: int = 90) -> Tuple[bool, Dict]:
        """Run backtest and get results using current config"""
        try:
            cmd = f"python -B main.py --mode backtest --symbol ES --days {days}"
            print(f"DEBUG: Running command: {cmd}")
            
            # Use -B flag to avoid writing .pyc files and ensure fresh imports
            result = subprocess.run(
                cmd,
                shell=True,
                capture_output=True,
                text=True,
                encoding='utf-8',
                errors='replace',
                timeout=600,
                env={**os.environ, 'PYTHONDONTWRITEBYTECODE': '1'}  # Force fresh imports
            )
            
            output = result.stdout + result.stderr
            
            # CRITICAL FIX: Use findall and take LAST match (backtest prints daily stats)
            # re.search() was taking FIRST match which was from daily stats, not final total
            metrics = {}
            
            if matches := re.findall(r'Total Trades:\s*(\d+)', output):
                metrics['trades'] = int(matches[-1])  # Take LAST match (final total)
            if matches := re.findall(r'Total P&L:\s*\$([+-]?[\d,]+\.?\d*)', output):
                metrics['profit'] = float(matches[-1].replace(',', ''))
            if matches := re.findall(r'Win Rate:\s*([\d.]+)%', output):
                metrics['win_rate'] = float(matches[-1])
            if matches := re.findall(r'Profit Factor:\s*([\d.]+)', output):
                metrics['profit_factor'] = float(matches[-1])
            if matches := re.findall(r'Sharpe Ratio:\s*([\d.]+)', output):
                metrics['sharpe'] = float(matches[-1])
            if matches := re.findall(r'Max Drawdown:\s*\$([\d,]+\.?\d*)', output):
                metrics['max_drawdown'] = float(matches[-1].replace(',', ''))
            if matches := re.findall(r'Average Win:\s*\$\+?([\d,]+\.?\d*)', output):
                metrics['avg_win'] = float(matches[-1].replace(',', ''))
            else:
                metrics['avg_win'] = 0.0
            if matches := re.findall(r'Average Loss:\s*\$-?([\d,]+\.?\d*)', output):
                metrics['avg_loss'] = float(matches[-1].replace(',', ''))
            else:
                metrics['avg_loss'] = 0.0
            
            return bool(metrics.get('trades')), metrics
            
        except Exception as e:
            print(f"Backtest error: {e}")
            return False, {}
    
    def run_backtest_with_params(self, params: Dict, days: int = 30) -> Tuple[bool, Dict]:
        """Run backtest with temporary parameters WITHOUT modifying config file"""
        # Save current config
        original_config = self.config_path.read_text(encoding='utf-8')
        
        try:
            # Temporarily update config
            if not self.update_config(params):
                return False, {}
            
            # Run backtest with temporary config
            success, metrics = self.run_backtest(days)
            
            return success, metrics
            
        finally:
            # ALWAYS restore original config, even if backtest fails
            self.config_path.write_text(original_config, encoding='utf-8')
    
    def calculate_fitness(self, metrics: Dict) -> float:
        """Calculate fitness score focused on what matters"""
        trades = metrics.get('trades', 0)
        profit = metrics.get('profit', 0)
        win_rate = metrics.get('win_rate', 0)
        pf = metrics.get('profit_factor', 0)
        sharpe = metrics.get('sharpe', 0)
        dd = metrics.get('max_drawdown', 0)
        avg_win = metrics.get('avg_win', 0)
        avg_loss = metrics.get('avg_loss', 0)
        
        # CRITICAL: ONLY PROFITABLE STRATEGIES ARE ACCEPTABLE
        if profit <= 0:
            return -10000  # Reject ALL losing strategies
        
        # Minimum requirements (relaxed for mean reversion)
        if trades < 10:
            return -10000
        if win_rate < 30:  # At least 30% win rate (mean reversion baseline is ~43%)
            return -10000
        
        # Scoring focused on profit and quality
        profit_score = profit * 2.0  # PROFIT IS KING
        frequency_score = min(trades, 50) * 40  # Good frequency (baseline ~42 trades)
        quality_score = win_rate * 25  # Win rate matters
        risk_reward = (avg_win / max(avg_loss, 1)) * 150  # Win big, lose small
        consistency = pf * 250  # Profit factor
        risk_adjusted = sharpe * 300  # Sharpe ratio
        drawdown_penalty = -dd * 1.5  # Punish big drawdowns
        
        # Bonuses for excellence
        bonus = 0
        if profit > 3000:
            bonus += 500  # Great profit
        if win_rate > 60 and trades >= 12:
            bonus += 400  # Consistent winner
        if pf > 2.0:
            bonus += 300  # Strong profit factor
        if sharpe > 2.5:
            bonus += 300  # Excellent risk-adjusted returns
        
        fitness = (
            profit_score * 0.35 +
            frequency_score * 0.15 +
            quality_score * 0.15 +
            risk_reward * 0.15 +
            consistency * 0.10 +
            risk_adjusted * 0.05 +
            drawdown_penalty * 0.05 +
            bonus
        )
        
        return fitness
    
    def learn(self, n_iterations: int = 25, days: int = 30):
        """Start learning optimal parameters"""
        
        if not HAS_SKOPT:
            print("ERROR: Need scikit-optimize")
            print("Run: pip install scikit-optimize")
            return
        
        print("="*80)
        print("STARTING LEARNING SESSION")
        print("="*80)
        print(f"Iterations: {n_iterations}")
        print(f"Backtest period: {days} days")
        print()
        
        b = self.baseline
        
        # COMPREHENSIVE search space - entry signals AND exit management
        space = [
            # Entry signal parameters
            Integer(max(10, b['rsi_period']-3), min(20, b['rsi_period']+3), name='rsi_period'),
            Integer(max(20, b['rsi_oversold']-5), min(40, b['rsi_oversold']+5), name='rsi_oversold'),
            Integer(max(55, b['rsi_overbought']-10), min(85, b['rsi_overbought']+10), name='rsi_overbought'),
            Real(max(0.8, b['vwap_entry']-0.4), min(2.2, b['vwap_entry']+0.4), name='vwap_entry'),
            Real(max(2.5, b['vwap_exit']-1.0), min(5.5, b['vwap_exit']+1.0), name='vwap_exit'),
            Categorical([True, False], name='use_vwap_dir'),
            Categorical([True, False], name='use_atr'),
            Real(1.0, 3.5, name='stop_atr'),
            Real(2.0, 6.0, name='target_atr'),
            Categorical([True, False], name='use_trend'),
            Integer(10, 50, name='ema_period'),
            
            # Advanced exit management parameters
            Categorical([True, False], name='breakeven_enabled'),
            Integer(4, 12, name='breakeven_threshold'),  # 4-12 ticks to activate breakeven
            Integer(0, 3, name='breakeven_offset'),  # 0-3 ticks offset
            Categorical([True, False], name='trailing_enabled'),
            Integer(4, 16, name='trailing_distance'),  # 4-16 ticks trailing distance
            Integer(8, 20, name='trailing_min_profit'),  # 8-20 ticks min profit before trailing
            Categorical([True, False], name='time_decay_enabled'),
            Real(0.05, 0.25, name='time_decay_50'),  # 5-25% tightening at 50% time
            Real(0.10, 0.40, name='time_decay_75'),  # 10-40% at 75%
            Real(0.15, 0.50, name='time_decay_90'),  # 15-50% at 90%
            Categorical([True, False], name='partial_enabled'),
            Real(0.30, 0.70, name='partial_1_pct'),  # First exit: 30-70% of position
            Real(1.5, 3.0, name='partial_1_r'),  # First exit: 1.5-3.0R
            Real(0.20, 0.50, name='partial_2_pct'),  # Second exit: 20-50%
            Real(2.5, 4.5, name='partial_2_r'),  # Second exit: 2.5-4.5R
        ]
        
        # Start from baseline - all current settings
        x0 = [
            # Entry signals
            b['rsi_period'], b['rsi_oversold'], b['rsi_overbought'],
            b['vwap_entry'], b['vwap_exit'], True,
            False, b['stop_atr_mult'], b['target_atr_mult'],
            False, 20,
            # Exit management
            b['breakeven_enabled'], b['breakeven_profit_threshold'], b['breakeven_stop_offset'],
            b['trailing_enabled'], b['trailing_distance'], b['trailing_min_profit'],
            b['time_decay_enabled'], b['time_decay_50'], b['time_decay_75'], b['time_decay_90'],
            b['partial_enabled'], b['partial_1_pct'], b['partial_1_r'], b['partial_2_pct'], b['partial_2_r']
        ]
        
        @use_named_args(space)
        def objective(**p):
            self.iteration += 1
            
            # Validate
            if p['rsi_overbought'] <= p['rsi_oversold'] + 20:
                return 1e6
            if p['time_decay_75'] <= p['time_decay_50']:
                return 1e6  # Time decay must increase
            if p['time_decay_90'] <= p['time_decay_75']:
                return 1e6
            if p['partial_2_r'] <= p['partial_1_r']:
                return 1e6  # Second exit must be further than first
            
            print(f"\n{'='*80}")
            print(f"ITERATION {self.iteration}/{n_iterations}")
            print(f"{'='*80}")
            print(f"ENTRY SIGNALS:")
            print(f"   RSI: {p['rsi_period']}/{p['rsi_oversold']}/{p['rsi_overbought']}")
            print(f"   VWAP: {p['vwap_entry']:.2f}σ / {p['vwap_exit']:.2f}σ, Direction: {p['use_vwap_dir']}")
            print(f"   Trend: EMA {p['ema_period']}, Filter: {p['use_trend']}")
            print(f"   ATR: {p['use_atr']}, Stop: {p['stop_atr']:.1f}x, Target: {p['target_atr']:.1f}x")
            print(f"EXIT MANAGEMENT:")
            print(f"   Breakeven: {p['breakeven_enabled']} ({p['breakeven_threshold']}t ±{p['breakeven_offset']}t)")
            print(f"   Trailing: {p['trailing_enabled']} ({p['trailing_distance']}t dist, {p['trailing_min_profit']}t min)")
            print(f"   Time Decay: {p['time_decay_enabled']} ({p['time_decay_50']:.0%}/{p['time_decay_75']:.0%}/{p['time_decay_90']:.0%})")
            print(f"   Partial Exits: {p['partial_enabled']} ({p['partial_1_pct']:.0%}@{p['partial_1_r']:.1f}R, {p['partial_2_pct']:.0%}@{p['partial_2_r']:.1f}R)")
            print()
            
            # Backtest with these parameters
            success, metrics = self.run_backtest_with_params(p, days)
            if not success:
                print(" Failed\n")
                return 1e6
            
            # Calculate fitness
            fitness = self.calculate_fitness(metrics)
            
            # Display results
            print(f"RESULTS:")
            print(f"  Trades: {metrics.get('trades', 0)}, Win Rate: {metrics.get('win_rate', 0):.1f}%")
            print(f"  Profit: ${metrics.get('profit', 0):,.2f}, PF: {metrics.get('profit_factor', 0):.2f}, Sharpe: {metrics.get('sharpe', 0):.2f}")
            print(f"  Avg Win: ${metrics.get('avg_win', 0):,.2f}, Avg Loss: ${metrics.get('avg_loss', 0):,.2f}")
            print(f"  Max DD: ${metrics.get('max_drawdown', 0):,.2f}")
            print(f"   FITNESS: {fitness:.0f}")
            
            # Save result with ALL parameters
            result = TradeResult(
                # Entry signals
                rsi_period=p['rsi_period'], rsi_oversold=p['rsi_oversold'], rsi_overbought=p['rsi_overbought'],
                vwap_entry=p['vwap_entry'], vwap_exit=p['vwap_exit'],
                use_vwap_direction=p['use_vwap_dir'], max_trades_per_day=999,
                use_atr_stops=p['use_atr'], stop_atr_mult=p['stop_atr'], target_atr_mult=p['target_atr'],
                use_trend_filter=p['use_trend'], ema_period=p['ema_period'],
                # Exit management
                breakeven_enabled=p['breakeven_enabled'],
                breakeven_profit_threshold_ticks=p['breakeven_threshold'],
                breakeven_stop_offset_ticks=p['breakeven_offset'],
                trailing_stop_enabled=p['trailing_enabled'],
                trailing_stop_distance_ticks=p['trailing_distance'],
                trailing_stop_min_profit_ticks=p['trailing_min_profit'],
                time_decay_enabled=p['time_decay_enabled'],
                time_decay_50_tightening=p['time_decay_50'],
                time_decay_75_tightening=p['time_decay_75'],
                time_decay_90_tightening=p['time_decay_90'],
                partial_exits_enabled=p['partial_enabled'],
                partial_exit_1_percentage=p['partial_1_pct'],
                partial_exit_1_r_multiple=p['partial_1_r'],
                partial_exit_2_percentage=p['partial_2_pct'],
                partial_exit_2_r_multiple=p['partial_2_r'],
                # Performance metrics
                trades=metrics.get('trades', 0), win_rate=metrics.get('win_rate', 0), profit=metrics.get('profit', 0),
                profit_factor=metrics.get('profit_factor', 0), sharpe=metrics.get('sharpe', 0),
                max_drawdown=metrics.get('max_drawdown', 0), avg_win=metrics.get('avg_win', 0), avg_loss=metrics.get('avg_loss', 0),
                fitness=fitness, timestamp=datetime.now().isoformat(), iteration=self.iteration
            )
            
            self.results_history.append(result)
            
            # Check for improvement
            if self.best_result is None or fitness > self.best_result.fitness:
                self.best_result = result
                print(f"\n NEW BEST! Fitness: {fitness:.0f}")
                print(f"   ${metrics['profit']:,.2f} profit | {metrics['win_rate']:.1f}% WR | {metrics['trades']} trades\n")
            
            # Save progress
            if self.iteration % 3 == 0:
                self.save_history()
            
            return -fitness
        
        # RUN LEARNING
        print(f" Starting from baseline, will explore {n_iterations} variations...\n")
        
        # Test baseline performance first if not already done
        if self.baseline_fitness is None:
            self.baseline_fitness = self.test_baseline_performance(days)
        
        result = gp_minimize(
            objective, space, n_calls=n_iterations, x0=x0,
            random_state=42, verbose=False
        )
        
        # Final save
        self.save_history()
        
        # Apply best ONLY if better than baseline
        if self.best_result:
            print("\n" + "="*80)
            print("LEARNING COMPLETE - CHECKING RESULTS")
            print("="*80)
            
            best = self.best_result
            
            # Compare to baseline
            if self.baseline_fitness is None:
                # First run - establish baseline
                self.baseline_fitness = best.fitness
                improvement = 0
            else:
                improvement = best.fitness - self.baseline_fitness
            
            print(f"\nBest fitness this session: {best.fitness:.0f}")
            print(f"Baseline fitness: {self.baseline_fitness:.0f}")
            print(f"Improvement: {improvement:+.0f}")
            
            if best.fitness >= self.baseline_fitness:
                # IMPROVEMENT! Apply it
                print("\n IMPROVEMENT FOUND - APPLYING NEW CONFIGURATION")
                
                best_params = {
                    # Entry signals
                    'rsi_period': best.rsi_period, 'rsi_oversold': best.rsi_oversold,
                    'rsi_overbought': best.rsi_overbought, 'vwap_entry': best.vwap_entry,
                    'vwap_exit': best.vwap_exit, 'use_vwap_dir': best.use_vwap_direction,
                    'use_trend': best.use_trend_filter, 'ema_period': best.ema_period,
                    'use_atr': best.use_atr_stops,
                    'stop_atr': best.stop_atr_mult, 'target_atr': best.target_atr_mult,
                    # Exit management
                    'breakeven_enabled': best.breakeven_enabled,
                    'breakeven_threshold': best.breakeven_profit_threshold_ticks,
                    'breakeven_offset': best.breakeven_stop_offset_ticks,
                    'trailing_enabled': best.trailing_stop_enabled,
                    'trailing_distance': best.trailing_stop_distance_ticks,
                    'trailing_min_profit': best.trailing_stop_min_profit_ticks,
                    'time_decay_enabled': best.time_decay_enabled,
                    'time_decay_50': best.time_decay_50_tightening,
                    'time_decay_75': best.time_decay_75_tightening,
                    'time_decay_90': best.time_decay_90_tightening,
                    'partial_enabled': best.partial_exits_enabled,
                    'partial_1_pct': best.partial_exit_1_percentage,
                    'partial_1_r': best.partial_exit_1_r_multiple,
                    'partial_2_pct': best.partial_exit_2_percentage,
                    'partial_2_r': best.partial_exit_2_r_multiple
                }
                self.update_config(best_params)
                
                # Update baseline
                self.baseline_fitness = best.fitness
                self.save_baseline_backup()
                
                print(f"\nENTRY SIGNALS:")
                print(f"   RSI: {best.rsi_period}/{best.rsi_oversold}/{best.rsi_overbought}")
                print(f"   VWAP: {best.vwap_entry:.2f}σ / {best.vwap_exit:.2f}σ, Direction: {best.use_vwap_direction}")
                print(f"   Trend: EMA {best.ema_period}, Filter: {best.use_trend_filter}")
                print(f"   ATR stops: {best.use_atr_stops}, {best.stop_atr_mult:.1f}x/{best.target_atr_mult:.1f}x")
                print(f"EXIT MANAGEMENT:")
                print(f"   Breakeven: {best.breakeven_enabled} ({best.breakeven_profit_threshold_ticks}t ±{best.breakeven_stop_offset_ticks}t)")
                print(f"   Trailing: {best.trailing_stop_enabled} ({best.trailing_stop_distance_ticks}t dist, {best.trailing_stop_min_profit_ticks}t min)")
                print(f"   Time Decay: {best.time_decay_enabled} ({best.time_decay_50_tightening:.0%}/{best.time_decay_75_tightening:.0%}/{best.time_decay_90_tightening:.0%})")
                print(f"   Partial Exits: {best.partial_exits_enabled} ({best.partial_exit_1_percentage:.0%}@{best.partial_exit_1_r_multiple:.1f}R, {best.partial_exit_2_percentage:.0%}@{best.partial_exit_2_r_multiple:.1f}R)")
                print(f"\nPERFORMANCE:")
                print(f"   Profit: ${best.profit:,.2f}")
                print(f"   Trades: {best.trades}, Win Rate: {best.win_rate:.1f}%")
                print(f"   Profit Factor: {best.profit_factor:.2f}, Sharpe: {best.sharpe:.2f}")
                print(f"   NEW BASELINE FITNESS: {best.fitness:.0f}")
            else:
                # WORSE - revert to baseline
                print("\n  NO IMPROVEMENT - REVERTING TO BASELINE")
                self.restore_baseline()
            
            print("="*80)
    
    def continuous_learning(self, iterations_per_cycle: int = 15):
        """Continuous learning - keeps getting better"""
        cycle = 0
        
        print("\n" + "="*80)
        print("CONTINUOUS LEARNING MODE - RUNS FOREVER")
        print("="*80)
        print(f"{iterations_per_cycle} iterations per cycle")
        print("Press Ctrl+C to stop\n")
        
        try:
            while True:
                cycle += 1
                print(f"\n{'#'*80}")
                print(f"LEARNING CYCLE {cycle}")
                print(f"{'#'*80}\n")
                
                self.learn(n_iterations=iterations_per_cycle, days=30)
                
                print(f"\n Cycle {cycle} done. Starting next cycle...\n")
                
        except KeyboardInterrupt:
            print("\n\n  Stopped by user")
            self.save_history()
            print(" Progress saved")


def main():
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument('--mode', choices=['single', 'continuous'], default='single')
    parser.add_argument('--iterations', type=int, default=25)
    parser.add_argument('--days', type=int, default=90)
    args = parser.parse_args()
    
    optimizer = FocusedMLOptimizer()
    
    if args.mode == 'single':
        optimizer.learn(n_iterations=args.iterations, days=args.days)
    else:
        optimizer.continuous_learning(iterations_per_cycle=args.iterations)


if __name__ == '__main__':
    main()

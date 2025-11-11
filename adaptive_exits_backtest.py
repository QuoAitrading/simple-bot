"""
Adaptive Exit Management for Backtest - FULL PORT FROM LIVE BOT
================================================================
This is a COMPLETE port of the adaptive exit system from the live bot.
Uses the same RL learning, regime detection, and dynamic parameters.
"""

import statistics
from typing import Dict, List, Any, Optional
from datetime import datetime
import logging

logger = logging.getLogger(__name__)


def detect_market_regime(bars: List[Dict], current_atr: float) -> str:
    """
    Detect current market regime (volatility + trend).
    Returns: HIGH_VOL_TRENDING, HIGH_VOL_CHOPPY, NORMAL_TRENDING, etc.
    """
    if len(bars) < 20:
        return "NORMAL"
    
    # Calculate average ATR
    recent_atrs = []
    for bar in bars[-20:]:
        if "atr" in bar and bar["atr"] > 0:
            recent_atrs.append(bar["atr"])
    
    if not recent_atrs:
        avg_atr = current_atr
    else:
        avg_atr = statistics.mean(recent_atrs)
    
    # Detect volatility regime
    if current_atr > avg_atr * 1.2:
        vol_regime = "HIGH_VOL"
    elif current_atr < avg_atr * 0.8:
        vol_regime = "LOW_VOL"
    else:
        vol_regime = "NORMAL"
    
    # Detect trending vs choppy
    recent_prices = [bar["close"] for bar in bars[-20:]]
    price_range = max(recent_prices) - min(recent_prices)
    avg_bar_range = statistics.mean([bar["high"] - bar["low"] for bar in bars[-20:]])
    
    # Trending if total range is much larger than individual bar ranges
    is_trending = price_range > (avg_bar_range * 10)
    
    # Combine volatility + trend
    if vol_regime == "HIGH_VOL":
        return "HIGH_VOL_TRENDING" if is_trending else "HIGH_VOL_CHOPPY"
    elif vol_regime == "LOW_VOL":
        return "LOW_VOL_TRENDING" if is_trending else "LOW_VOL_RANGING"
    else:
        return "NORMAL_TRENDING" if is_trending else "NORMAL"


def get_recommended_scaling_strategy(market_state: Dict, regime: str, adaptive_manager = None) -> Dict:
    """
    Recommend scaling strategy by RETRIEVING similar past experiences (backtest version).
    Same logic as live bot - learns from exit experiences.
    """
    # Import the learning functions from main adaptive_exits module
    from adaptive_exits import _find_similar_exit_experiences, _extract_scaling_strategy_from_experiences
    
    rsi = market_state.get('rsi', 50)
    volume_ratio = market_state.get('volume_ratio', 1.0)
    hour = market_state.get('hour', 12)
    streak = market_state.get('streak', 0)
    
    # STEP 1: Try to learn from similar past experiences
    if adaptive_manager and hasattr(adaptive_manager, 'exit_experiences') and len(adaptive_manager.exit_experiences) >= 20:
        similar_exits = _find_similar_exit_experiences(
            market_state=market_state,
            regime=regime,
            all_experiences=adaptive_manager.exit_experiences,
            min_similarity=0.60
        )
        
        if len(similar_exits) >= 5:
            strategy = _extract_scaling_strategy_from_experiences(similar_exits, market_state, regime)
            strategy['similar_count'] = len(similar_exits)
            strategy['learning_mode'] = 'EXPERIENCE_BASED'
            return strategy
    
    # STEP 2: Fallback to rule-based (cold start)
    # AGGRESSIVE SCALING: Get out quick (choppy/overbought/afternoon)
    if (rsi > 65 and "CHOPPY" in regime) or (13 <= hour <= 15 and "CHOPPY" in regime):
        return {
            'partial_1_r': 2.0,
            'partial_1_pct': 0.70,  # 70% @ 2R (secure most profit)
            'partial_2_r': 3.0,
            'partial_2_pct': 0.25,  # 25% @ 3R
            'partial_3_r': 5.0,
            'partial_3_pct': 0.05,  # 5% runner
            'single_contract_target': 2.5,  # Quick exit for 1-contract in choppy
            'strategy': f'AGGRESSIVE_SCALE (RSI:{rsi:.0f}, {regime}, Hour:{hour})',
            'similar_count': 0,
            'learning_mode': 'RULE_BASED'
        }
    
    # HOLD FULL POSITION: Let it run (trending + momentum)
    elif ("TRENDING" in regime and volume_ratio > 1.3) or (streak >= 3 and "TRENDING" in regime):
        return {
            'partial_1_r': 3.0,
            'partial_1_pct': 0.0,   # Hold all @ 2R
            'partial_2_r': 4.0,
            'partial_2_pct': 0.30,  # Take some @ 4R
            'partial_3_r': 6.0,
            'partial_3_pct': 0.70,  # Most @ 6R (ride the trend!)
            'single_contract_target': 5.0,  # Patient exit for 1-contract in trending
            'strategy': f'HOLD_FULL (TRENDING, Vol:{volume_ratio:.1f}x, Streak:{streak:+d})',
            'similar_count': 0,
            'learning_mode': 'RULE_BASED'
        }
    
    # BALANCED SCALING: Standard approach (normal conditions)
    else:
        return {
            'partial_1_r': 2.0,
            'partial_1_pct': 0.50,  # 50% @ 2R
            'partial_2_r': 3.0,
            'partial_2_pct': 0.30,  # 30% @ 3R
            'partial_3_r': 5.0,
            'partial_3_pct': 0.20,  # 20% @ 5R
            'single_contract_target': 3.5,  # Balanced exit for 1-contract
            'strategy': f'BALANCED ({regime}, RSI:{rsi:.0f})',
            'similar_count': 0,
            'learning_mode': 'RULE_BASED'
        }


def get_adaptive_exit_params(bars: List[Dict], position: Dict, current_price: float,
                             config: Dict, entry_time: datetime, adaptive_manager=None) -> Dict:
    """
    Calculate adaptive exit parameters based on market conditions.
    
    THIS IS THE KEY FUNCTION - calculates exit params dynamically like live bot.
    
    Args:
        bars: Recent price bars
        position: Position info
        current_price: Current market price
        config: Bot configuration
        entry_time: Trade entry time
        adaptive_manager: Optional AdaptiveExitManager for learned parameters
    
    Returns dict with:
      - breakeven_threshold_ticks: When to move to BE
      - trailing_distance_ticks: How far to trail
      - trailing_min_profit_ticks: Min profit before trail activates
      - market_regime: Detected regime
      - situation_factors: What's happening now
      - decision_reasons: Why these params chosen
    """
    # Base parameters from config (Iteration 3 values)
    base_breakeven_threshold = config.get("breakeven_threshold_ticks", 9)
    base_breakeven_offset = config.get("breakeven_offset_ticks", 1)
    base_trailing_distance = config.get("trailing_distance_ticks", 10)
    base_trailing_min_profit = config.get("trailing_min_profit_ticks", 16)
    
    # Calculate current ATR
    if len(bars) > 0 and "atr" in bars[-1]:
        current_atr = bars[-1]["atr"]
    elif len(bars) >= 14:
        recent_ranges = [(b["high"] - b["low"]) for b in bars[-14:]]
        current_atr = statistics.mean(recent_ranges) if recent_ranges else 2.0
        # Ensure minimum ATR
        if current_atr < 1.0:
            current_atr = 2.0  # Sensible minimum
    else:
        current_atr = 2.0
    
    # Detect market regime
    market_regime = detect_market_regime(bars, current_atr)
    
    # ========================================================================
    # CLOUD EXIT RL - Query cloud for REAL-TIME exit recommendations
    # ========================================================================
    # Try to get cloud-recommended exit params based on current market conditions
    cloud_params = None
    if adaptive_manager and hasattr(adaptive_manager, 'get_cloud_exit_params'):
        # Build market state dict for cloud query
        market_state_for_cloud = {}
        if len(bars) > 0:
            latest_bar = bars[-1]
            market_state_for_cloud = {
                'rsi': latest_bar.get('rsi', 50.0),
                'atr': current_atr,
                'vwap_distance': abs(current_price - latest_bar.get('vwap', current_price)) if 'vwap' in latest_bar else 0.0,
                'volume_ratio': latest_bar.get('volume', 1.0) / latest_bar.get('avg_volume', 1.0) if 'avg_volume' in latest_bar else 1.0,
                'hour': entry_time.hour if entry_time else 12,
                'day_of_week': entry_time.weekday() if entry_time else 0,
                'streak': position.get('streak', 0) if 'streak' in position else 0,
                'recent_pnl': position.get('recent_pnl', 0.0) if 'recent_pnl' in position else 0.0,
                'vix': latest_bar.get('vix', 15.0) if 'vix' in latest_bar else 15.0
            }
        
        # Calculate duration for position state
        if len(bars) > 0 and "timestamp" in bars[-1]:
            current_time = bars[-1]["timestamp"]
            if isinstance(current_time, str):
                current_time = datetime.fromisoformat(current_time.replace('Z', '+00:00'))
            duration_minutes = (current_time.timestamp() - entry_time.timestamp()) / 60 if entry_time else 0
        else:
            duration_minutes = 0
        
        # Build position state for cloud query
        position_for_cloud = {
            'side': position.get('side', 'long'),
            'duration_minutes': duration_minutes,
            'unrealized_pnl': position.get('unrealized_pnl', 0.0) if 'unrealized_pnl' in position else 0.0,
            'entry_price': position.get('entry_price', current_price),
            'r_multiple': position.get('r_multiple', 0.0) if 'r_multiple' in position else 0.0
        }
        
        # Query cloud for real-time exit params
        cloud_params = adaptive_manager.get_cloud_exit_params(
            regime=market_regime,
            market_state=market_state_for_cloud,
            position=position_for_cloud,
            entry_confidence=0.75  # Default confidence for backtest
        )
        
        # If cloud returns params, use them directly (they're already optimized)
        if cloud_params:
            cloud_meta = cloud_params.get('_cloud_metadata', {})
            logger.info(f"🎯 [CLOUD EXIT RL] {cloud_meta.get('recommendation', 'N/A')} (analyzed {cloud_meta.get('similar_exits', 0)} similar exits)")
            return {
                'breakeven_threshold_ticks': cloud_params.get('breakeven_threshold_ticks', base_breakeven_threshold),
                'breakeven_offset_ticks': cloud_params.get('breakeven_offset_ticks', base_breakeven_offset),
                'trailing_distance_ticks': cloud_params.get('trailing_distance_ticks', base_trailing_distance),
                'trailing_min_profit_ticks': int(cloud_params.get('partial_1_r', 2.0) * base_trailing_distance),
                'market_regime': market_regime,
                'current_volatility_atr': current_atr,
                'is_aggressive_mode': "TIGHTEN" in cloud_meta.get('recommendation', ''),
                'situation_factors': {},
                'decision_reasons': ['CLOUD_RL'],
                'duration_minutes': duration_minutes,
                'learned_multiplier': 1.0,
                'cloud_recommendation': cloud_meta
            }
        else:
            logger.debug("[CLOUD EXIT RL] Cloud unavailable, using local learned params")
    
    # If cloud query failed or not available, continue with local learned parameters below
    # ========================================================================
    
    # Calculate trade duration
    if len(bars) > 0 and "timestamp" in bars[-1]:
        current_time = bars[-1]["timestamp"]
        if isinstance(current_time, str):
            current_time = datetime.fromisoformat(current_time.replace('Z', '+00:00'))
        duration_minutes = (current_time.timestamp() - entry_time.timestamp()) / 60
        current_hour = current_time.hour
    else:
        duration_minutes = 0
        current_hour = 12
    
    # ========================================================================
    # SITUATION AWARENESS - What's happening RIGHT NOW?
    # ========================================================================
    situation_factors = {
        'is_choppy': "CHOPPY" in market_regime,
        'is_high_vol': "HIGH_VOL" in market_regime,
        'is_trending': "TRENDING" in market_regime,
        'is_morning': 9 <= current_hour < 11,  # 9-11 AM volatile
        'is_lunch': 11 <= current_hour < 14,   # 11 AM - 2 PM slow
        'is_close': current_hour >= 15,        # After 3 PM rushes/reversals
        'is_old_trade': duration_minutes > 30,  # Been in too long
        'is_quick_trade': duration_minutes < 5,  # Very new trade
    }
    
    # ========================================================================
    # ADAPTIVE DECISION LOGIC - What should we do?
    # ========================================================================
    decision_reasons = []
    is_aggressive_mode = False
    
    # Get LEARNED parameters from adaptive manager if available
    # The learned params ARE the optimal values - use them as-is!
    if adaptive_manager and hasattr(adaptive_manager, 'learned_params'):
        regime_params = adaptive_manager.learned_params.get(market_regime, {'breakeven_mult': 1.0, 'trailing_mult': 1.0})
        breakeven_mult = regime_params['breakeven_mult']
        trailing_mult = regime_params['trailing_mult']
        decision_reasons.append(f"RL_LEARNED_{market_regime}")
    else:
        # Fallback: Use regime defaults only when NO learning available
        learned_params = {
            'HIGH_VOL_CHOPPY': {'breakeven_mult': 0.75, 'trailing_mult': 0.7},
            'HIGH_VOL_TRENDING': {'breakeven_mult': 0.85, 'trailing_mult': 1.1},
            'LOW_VOL_RANGING': {'breakeven_mult': 1.0, 'trailing_mult': 1.0},
            'LOW_VOL_TRENDING': {'breakeven_mult': 1.0, 'trailing_mult': 1.15},
            'NORMAL': {'breakeven_mult': 1.0, 'trailing_mult': 1.0},
            'NORMAL_TRENDING': {'breakeven_mult': 1.0, 'trailing_mult': 1.1},
            'NORMAL_CHOPPY': {'breakeven_mult': 0.95, 'trailing_mult': 0.95}
        }
        regime_params = learned_params.get(market_regime, {'breakeven_mult': 1.0, 'trailing_mult': 1.0})
        breakeven_mult = regime_params['breakeven_mult']
        trailing_mult = regime_params['trailing_mult']
        decision_reasons.append(f"FALLBACK_{market_regime}")
    
    # Apply multipliers to base parameters
    breakeven_threshold = int(base_breakeven_threshold * breakeven_mult)
    trailing_distance = int(base_trailing_distance * trailing_mult)
    trailing_min_profit = int(base_trailing_min_profit * trailing_mult)
    
    # Ensure minimums
    breakeven_threshold = max(5, breakeven_threshold)
    trailing_distance = max(6, trailing_distance)
    trailing_min_profit = max(8, trailing_min_profit)
    
    return {
        'breakeven_threshold_ticks': breakeven_threshold,
        'breakeven_offset_ticks': base_breakeven_offset,
        'trailing_distance_ticks': trailing_distance,
        'trailing_min_profit_ticks': trailing_min_profit,
        'market_regime': market_regime,
        'current_volatility_atr': current_atr,
        'is_aggressive_mode': is_aggressive_mode,
        'situation_factors': situation_factors,
        'decision_reasons': decision_reasons,
        'duration_minutes': duration_minutes,
        'learned_multiplier': trailing_mult
    }

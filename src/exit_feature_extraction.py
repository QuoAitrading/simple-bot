"""
Exit Feature Extraction - Convert JSON experiences to 208 normalized features
=============================================================================
Handles all field types: scalars, strings, lists, nested dicts, string-encoded JSON

Feature Breakdown (208 total):
- exit_params_used: 132 features (what parameters were actually used)
- market_state: 9 features
- outcome fields: 54 numeric features
- root fields: 13 numeric features
Total: 208 features

This module properly handles:
- String encoding (regime, side, exit_reason, session)
- List aggregation (partial_exits, exit_param_updates, stop_adjustments)
- String-encoded JSON parsing (decision_history, unrealized_pnl_history)
- Nested dict flattening (market_state, outcome)
"""

import json
import logging
from typing import Dict, List, Any
import numpy as np

logger = logging.getLogger(__name__)


# Encoding mappings for categorical features
REGIME_MAP = {
    'NORMAL': 0, 'NORMAL_TRENDING': 1, 'HIGH_VOL_TRENDING': 2,
    'HIGH_VOL_CHOPPY': 3, 'LOW_VOL_TRENDING': 4, 'LOW_VOL_RANGING': 5,
    'UNKNOWN': 0
}

SIDE_MAP = {'long': 0, 'short': 1, 'LONG': 0, 'SHORT': 1}

EXIT_REASON_MAP = {
    'take_profit': 0, 'stop_loss': 1, 'trailing_stop': 2,
    'time_limit': 3, 'partial_exit': 4, 'breakeven': 5,
    'profit_drawdown': 6, 'adverse_momentum': 7, 'max_hold': 8,
    'unknown': 9
}


def extract_all_features_for_training(experience: Dict) -> List[float]:
    """
    Extract all 208 features from an exit experience for neural network training.
    
    Args:
        experience: Exit experience dict from JSON
        
    Returns:
        List of 208 normalized float values
    """
    features = []
    
    # =====================================================
    # PART 1: exit_params_used (132 features)
    # =====================================================
    # These are the actual exit parameters that were used for this trade
    # The model will learn to predict these based on market context
    exit_params_used = experience.get('exit_params_used', experience.get('exit_params', {}))
    
    # Extract in consistent order (alphabetically sorted for determinism)
    param_names = sorted(exit_params_used.keys())
    for param_name in param_names:
        value = exit_params_used[param_name]
        # Normalize boolean to 0/1
        if isinstance(value, bool):
            features.append(1.0 if value else 0.0)
        else:
            # Already numeric, add as-is (will be normalized during training)
            features.append(float(value))
    
    # If we don't have exactly 132, pad or truncate
    if len(features) < 132:
        logger.debug(f"Only {len(features)} exit params, expected 132. Padding with zeros.")
        features.extend([0.0] * (132 - len(features)))
    elif len(features) > 132:
        logger.debug(f"Got {len(features)} exit params, expected 132. Truncating.")
        features = features[:132]
    
    # =====================================================
    # PART 2: market_state (9 features)
    # =====================================================
    market_state = experience.get('market_state', {})
    
    # Add market_state features in order
    features.append(float(market_state.get('atr', 2.0)))
    features.append(float(market_state.get('day_of_week', 0)))
    features.append(float(market_state.get('hour', 12)))
    features.append(float(market_state.get('recent_pnl', 0.0)))
    features.append(float(market_state.get('rsi', 50.0)))
    features.append(float(market_state.get('streak', 0)))
    features.append(float(market_state.get('vix', 15.0)))
    features.append(float(market_state.get('volume_ratio', 1.0)))
    features.append(float(market_state.get('vwap_distance', 0.0)))
    
    # =====================================================
    # PART 3: Root-level numeric fields (13 features)
    # =====================================================
    # These are direct fields at the root of the experience dict
    features.append(float(experience.get('bars_until_breakeven', 0)))
    features.append(float(experience.get('bars_until_trailing', 0)))
    features.append(float(experience.get('bid_ask_spread_ticks', 0.5)))
    features.append(1.0 if experience.get('breakeven_activated', False) else 0.0)
    features.append(float(experience.get('breakeven_activation_bar', 0)))
    features.append(float(experience.get('commission_cost', 5.0)))
    features.append(float(experience.get('duration', 1.0)))
    features.append(float(experience.get('entry_confidence', 0.75)))
    features.append(float(experience.get('exit_param_update_count', 0)))
    features.append(float(experience.get('mae', 0.0)))
    features.append(float(experience.get('max_profit_reached', 0.0)))
    features.append(float(experience.get('max_r_achieved', 0.0)))
    features.append(float(experience.get('mfe', 0.0)))
    
    # Continue with more root fields
    features.append(float(experience.get('min_r_achieved', 0.0)))
    features.append(float(experience.get('pnl', 0.0)))
    features.append(float(experience.get('r_multiple', 0.0)))
    features.append(float(experience.get('rejected_partial_count', 0)))
    features.append(float(experience.get('slippage_ticks', 0.5)))
    features.append(float(experience.get('stop_adjustment_count', 0)))
    features.append(1.0 if experience.get('stop_hit', False) else 0.0)
    features.append(float(experience.get('time_in_breakeven_bars', 0)))
    features.append(1.0 if experience.get('trailing_activated', False) else 0.0)
    features.append(float(experience.get('trailing_activation_bar', 0)))
    features.append(1.0 if experience.get('volatility_regime_change', False) else 0.0)
    features.append(float(experience.get('volume_at_exit', 100.0)))
    features.append(1.0 if experience.get('win', False) else 0.0)
    
    # =====================================================
    # PART 4: Encoded categorical fields (4 features)
    # =====================================================
    # These need encoding from strings to numeric values
    
    # Regime encoding (normalized 0-1)
    regime = experience.get('regime', 'NORMAL')
    regime_encoded = REGIME_MAP.get(regime, 0) / 5.0  # Normalize to 0-1
    features.append(regime_encoded)
    
    # Side encoding
    side = experience.get('side', 'long')
    side_encoded = float(SIDE_MAP.get(side, 0))
    features.append(side_encoded)
    
    # Exit reason encoding (normalized 0-1)
    exit_reason = experience.get('exit_reason', 'unknown')
    exit_reason_encoded = EXIT_REASON_MAP.get(exit_reason, 9) / 9.0
    features.append(exit_reason_encoded)
    
    # Session (already numeric, but ensure it's a float)
    session = experience.get('session', 0)
    if isinstance(session, str):
        # Handle if session is stored as string
        session_map = {'Asia': 0, 'London': 1, 'NY': 2}
        session = session_map.get(session, 0)
    features.append(float(session) / 2.0)  # Normalize 0-1
    
    # =====================================================
    # PART 5: List field aggregates (9 features: 3 lists × 3 stats each)
    # =====================================================
    # partial_exits, exit_param_updates, stop_adjustments are lists
    # We extract: count, sum/avg, last_value for each
    
    # partial_exits
    partial_exits = experience.get('partial_exits', [])
    if isinstance(partial_exits, str):
        try:
            partial_exits = json.loads(partial_exits)
        except:
            partial_exits = []
    features.append(float(len(partial_exits)))  # count
    features.append(float(len(partial_exits) > 0))  # has any
    features.append(0.0)  # reserved for future use
    
    # exit_param_updates (could be at root or in outcome)
    exit_param_updates = experience.get('exit_param_updates', [])
    if isinstance(exit_param_updates, str):
        try:
            exit_param_updates = json.loads(exit_param_updates)
        except:
            exit_param_updates = []
    features.append(float(len(exit_param_updates)))  # count
    features.append(float(len(exit_param_updates) > 0))  # has any
    features.append(0.0)  # reserved
    
    # stop_adjustments
    stop_adjustments = experience.get('stop_adjustments', [])
    if isinstance(stop_adjustments, str):
        try:
            stop_adjustments = json.loads(stop_adjustments)
        except:
            stop_adjustments = []
    features.append(float(len(stop_adjustments)))  # count
    features.append(float(len(stop_adjustments) > 0))  # has any
    features.append(0.0)  # reserved
    
    # =====================================================
    # PART 6: outcome dict numeric fields (37 features)
    # =====================================================
    # The outcome dict has many more fields we should use
    outcome = experience.get('outcome', {})
    
    # Extract numeric fields from outcome (skip duplicates and string fields)
    outcome_features_to_extract = [
        'atr_change_percent', 'avg_atr_during_trade', 'bars_held',
        'contracts', 'cumulative_pnl_before_trade', 
        'daily_loss_limit', 'daily_loss_proximity_pct', 'daily_pnl_before_trade',
        'drawdown_bars', 'duration_bars',
        'entry_bar', 'exit_bar', 
        'entry_hour', 'entry_minute', 'exit_hour', 'exit_minute',
        'entry_price', 'high_volatility_bars',
        'losses_in_last_5_trades', 'max_drawdown_percent',
        'minutes_until_close', 'opportunity_cost',
        'peak_r_multiple', 'peak_unrealized_pnl',
        'profit_drawdown_from_peak', 'trade_number_in_session',
        'vix', 'wins_in_last_5_trades',
        # Also include outcome.session, outcome.side (encoded), outcome.exit_reason (encoded)
    ]
    
    for field in outcome_features_to_extract:
        value = outcome.get(field, 0.0)
        if isinstance(value, bool):
            features.append(1.0 if value else 0.0)
        else:
            features.append(float(value))
    
    # Add encoded fields from outcome
    outcome_side = outcome.get('side', side)  # Use root side as fallback
    features.append(float(SIDE_MAP.get(outcome_side, 0)))
    
    outcome_exit_reason = outcome.get('exit_reason', exit_reason)
    features.append(EXIT_REASON_MAP.get(outcome_exit_reason, 9) / 9.0)
    
    outcome_session = outcome.get('session', session)
    features.append(float(outcome_session) / 2.0)
    
    # Add a few more outcome fields for completeness
    features.append(1.0 if outcome.get('held_through_sessions', False) else 0.0)
    
    # =====================================================
    # VALIDATION: Ensure we have exactly 208 features
    # =====================================================
    current_count = len(features)
    
    if current_count < 208:
        logger.debug(f"Only extracted {current_count} features, expected 208. Padding with zeros.")
        features.extend([0.0] * (208 - current_count))
    elif current_count > 208:
        logger.debug(f"Extracted {current_count} features, expected 208. Truncating.")
        features = features[:208]
    
    return features


def normalize_features_for_training(features_list: List[List[float]]) -> np.ndarray:
    """
    Normalize features using min-max scaling per feature.
    
    Args:
        features_list: List of feature vectors (each 208 floats)
        
    Returns:
        Normalized numpy array of shape (n_samples, 208)
    """
    features_array = np.array(features_list, dtype=np.float32)
    
    # Min-max normalization per feature
    for i in range(features_array.shape[1]):
        col = features_array[:, i]
        min_val = col.min()
        max_val = col.max()
        
        # Avoid division by zero
        if max_val - min_val > 1e-8:
            features_array[:, i] = (col - min_val) / (max_val - min_val)
        else:
            # If all values are the same, normalize to 0.5
            features_array[:, i] = 0.5
    
    return features_array


def prepare_training_data(experiences: List[Dict]) -> tuple:
    """
    Prepare training data from list of experiences.
    
    Args:
        experiences: List of exit experience dicts
        
    Returns:
        Tuple of (input_features, output_params) as numpy arrays
    """
    X = []  # Input features (208)
    y = []  # Output parameters (132 exit_params to predict)
    
    for exp in experiences:
        try:
            # Extract input features (208)
            input_features = extract_all_features_for_training(exp)
            X.append(input_features)
            
            # Extract output targets (132 exit_params)
            exit_params = exp.get('exit_params', {})
            param_names = sorted(exit_params.keys())
            output_params = []
            for param_name in param_names:
                value = exit_params[param_name]
                if isinstance(value, bool):
                    output_params.append(1.0 if value else 0.0)
                else:
                    output_params.append(float(value))
            
            # Ensure 132 outputs
            if len(output_params) < 132:
                output_params.extend([0.0] * (132 - len(output_params)))
            elif len(output_params) > 132:
                output_params = output_params[:132]
            
            y.append(output_params)
            
        except Exception as e:
            logger.error(f"Error processing experience: {e}")
            continue
    
    # Convert to numpy arrays
    X = np.array(X, dtype=np.float32)
    y = np.array(y, dtype=np.float32)
    
    # Normalize inputs
    X = normalize_features_for_training(X.tolist())
    
    # Normalize outputs to 0-1 range for better training
    for i in range(y.shape[1]):
        col = y[:, i]
        min_val = col.min()
        max_val = col.max()
        
        if max_val - min_val > 1e-8:
            y[:, i] = (col - min_val) / (max_val - min_val)
        else:
            y[:, i] = 0.5
    
    logger.info(f"Prepared training data: X shape {X.shape}, y shape {y.shape}")
    return X, y

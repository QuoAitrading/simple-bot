"""
Live-Only Exit Parameters
These 5 parameters require real-time broker/market data and CANNOT be learned from backtest.
Used ONLY in live trading, not in backtesting or neural network training.
"""

# ============================================================================
# LIVE-ONLY EXIT PARAMETERS (5 total)
# ============================================================================

LIVE_ONLY_EXIT_PARAMS = {
    # EXECUTION QUALITY (5 params - most critical for live trading)
    # -------------------------------------------------------------------------
    'partial_fill_min_acceptable_pct': {
        'min': 0.50, 'max': 0.80, 'default': 0.70,
        'description': 'Minimum fill percentage to keep position',
        'category': 'live_execution',
        'requires': 'Actual fill confirmations'
    },
    'order_rejection_retry_max': {
        'min': 2, 'max': 5, 'default': 3,
        'description': 'Exit attempts before giving up',
        'category': 'live_execution',
        'requires': 'Broker order status'
    },
    'margin_buffer_exit_threshold_pct': {
        'min': 0.10, 'max': 0.30, 'default': 0.20,
        'description': 'Close if margin dropping too low',
        'category': 'live_execution',
        'requires': 'Live account margin data'
    },
    'position_sizing_error_exit_pct': {
        'min': 0.10, 'max': 0.25, 'default': 0.15,
        'description': 'Exit if actual size differs from intended by X%',
        'category': 'live_execution',
        'requires': 'Actual filled contracts vs intended'
    },
    'stop_order_rejection_exit': {
        'min': 0, 'max': 1, 'default': 1,
        'description': 'Emergency exit if protective stop rejected (boolean)',
        'category': 'live_execution',
        'requires': 'Broker order rejection notifications'
    },
}


# ============================================================================
# HELPER FUNCTIONS
# ============================================================================

def get_live_only_defaults():
    """Get dict of all live-only parameters with default values"""
    return {name: config['default'] for name, config in LIVE_ONLY_EXIT_PARAMS.items()}


def get_all_live_params():
    """
    Get complete parameter set for live trading: backtest params + live-only params
    
    Returns dict with 59 backtest params + 5 live-only params = 64 total
    """
    from exit_params_config import get_default_exit_params
    
    all_params = get_default_exit_params()  # 59 backtest-learnable params
    all_params.update(get_live_only_defaults())  # + 5 live-only params
    
    return all_params  # 64 total


# Validation
assert len(LIVE_ONLY_EXIT_PARAMS) == 5, f"Expected 5 live-only params, got {len(LIVE_ONLY_EXIT_PARAMS)}"
print(f"✓ Live-only exit parameters loaded: {len(LIVE_ONLY_EXIT_PARAMS)} parameters")

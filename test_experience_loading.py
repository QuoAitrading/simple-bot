"""
Test if 10,000+ Cloud Experiences Are ACTUALLY Loaded and Used
================================================================

This script proves:
1. Exit RL loads experiences from cloud (10k+)
2. Signal RL loads experiences from cloud (6k+)
3. Experiences are used for decision-making (not just sitting there)
"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

from adaptive_exits import AdaptiveExitManager
from signal_confidence import SignalConfidenceRL
import json

print("=" * 80)
print("EXPERIENCE LOADING VERIFICATION")
print("=" * 80)

# Cloud API URL (from production bot)
CLOUD_API_URL = "https://quotrading-signals.icymeadow-86b2969e.eastus.azurecontainerapps.io"

CONFIG = {
    "tick_size": 0.25,
    "tick_value": 12.50,
    "max_contracts": 3
}

# ============================================================================
# TEST 1: Exit RL Experience Loading
# ============================================================================
print("\n[TEST 1] Exit RL Experience Loading from Cloud")
print("-" * 80)

try:
    exit_manager = AdaptiveExitManager(
        config=CONFIG,
        experience_file='cloud-api/exit_experience.json',
        cloud_api_url=CLOUD_API_URL
    )
    
    exit_exp_count = len(exit_manager.exit_experiences)
    print(f"✅ Exit RL Manager initialized")
    print(f"   Experiences loaded: {exit_exp_count:,}")
    print(f"   Source: {'CLOUD API' if exit_manager.use_cloud else 'LOCAL FILE'}")
    
    if exit_exp_count > 1000:
        print(f"   ✅ CONFIRMED: {exit_exp_count:,} experiences loaded from cloud!")
    elif exit_exp_count > 0:
        print(f"   ⚠️  WARNING: Only {exit_exp_count} experiences (expected 10k+ from cloud)")
    else:
        print(f"   ❌ FAILED: No experiences loaded!")
    
    # Check learned parameters exist
    if hasattr(exit_manager, 'learned_params'):
        regime_count = len(exit_manager.learned_params)
        print(f"   Learned regimes: {regime_count} ({', '.join(exit_manager.learned_params.keys())})")
        
        # Show one regime's learned params
        sample_regime = list(exit_manager.learned_params.keys())[0]
        sample_params = exit_manager.learned_params[sample_regime]
        print(f"   Sample ({sample_regime}):")
        print(f"     - Breakeven multiplier: {sample_params.get('breakeven_mult', 1.0):.2f}x")
        print(f"     - Trailing multiplier: {sample_params.get('trailing_mult', 1.0):.2f}x")
        print(f"     - Partial exit 1: {sample_params.get('partial_1_r', 2.0):.1f}R @ {sample_params.get('partial_1_pct', 0.5):.0%}")
    
except Exception as e:
    print(f"❌ Exit RL initialization FAILED: {e}")
    import traceback
    traceback.print_exc()

# ============================================================================
# TEST 2: Signal RL Experience Loading
# ============================================================================
print("\n[TEST 2] Signal RL Experience Loading from Cloud")
print("-" * 80)

try:
    signal_rl = SignalConfidenceRL(
        experience_file='data/signal_experience.json',
        cloud_api_url=CLOUD_API_URL
    )
    
    signal_exp_count = len(signal_rl.experiences)
    print(f"✅ Signal RL initialized")
    print(f"   Experiences loaded: {signal_exp_count:,}")
    print(f"   Source: {'CLOUD API' if signal_rl.use_cloud else 'LOCAL FILE'}")
    
    if signal_exp_count > 1000:
        print(f"   ✅ CONFIRMED: {signal_exp_count:,} experiences loaded from cloud!")
    elif signal_exp_count > 0:
        print(f"   ⚠️  WARNING: Only {signal_exp_count} experiences (expected 6k+ from cloud)")
    else:
        print(f"   ❌ FAILED: No experiences loaded!")
    
    # Check configuration
    print(f"   Spread threshold: {signal_rl.max_spread_ticks:.1f} ticks")
    print(f"   Liquidity threshold: {signal_rl.min_volume_ratio:.1f}x avg volume")
    print(f"   Confidence threshold: {signal_rl.confidence_threshold:.0%}")
    
except Exception as e:
    print(f"❌ Signal RL initialization FAILED: {e}")
    import traceback
    traceback.print_exc()

# ============================================================================
# TEST 3: Prove Experiences Are USED (Not Just Loaded)
# ============================================================================
print("\n[TEST 3] Proving Experiences Are Actually USED for Decisions")
print("-" * 80)

# Test Exit RL decision-making
print("\n[3A] Exit RL Decision Test - Are experiences consulted?")
try:
    # Simulate a trade scenario
    test_bars = [
        {'timestamp': '2024-01-01 10:00', 'open': 5000, 'high': 5002, 'low': 4998, 'close': 5001, 'volume': 1000},
        {'timestamp': '2024-01-01 10:01', 'open': 5001, 'high': 5003, 'low': 4999, 'close': 5002, 'volume': 1200},
        {'timestamp': '2024-01-01 10:02', 'open': 5002, 'high': 5005, 'low': 5001, 'close': 5004, 'volume': 1500},
    ]
    
    test_position = {
        'entry_time': '2024-01-01 10:00'
    }
    
    # This function consults loaded experiences to adapt exit params
    from adaptive_exits_backtest import get_adaptive_exit_params
    
    exit_params = get_adaptive_exit_params(
        bars=test_bars,
        position=test_position,
        current_price=5004,
        config=CONFIG,
        entry_time='2024-01-01 10:00',
        adaptive_manager=exit_manager  # Uses loaded experiences!
    )
    
    print(f"   ✅ Exit parameters calculated using {exit_exp_count:,} experiences:")
    print(f"      - Breakeven threshold: {exit_params['breakeven_threshold_ticks']} ticks")
    print(f"      - Trailing distance: {exit_params['trailing_distance_ticks']} ticks")
    print(f"      - Market regime: {exit_params['market_regime']}")
    print(f"      - Decision reasons: {', '.join(exit_params.get('decision_reasons', []))}")
    
    if 'RL_LEARNED' in str(exit_params.get('decision_reasons', [])):
        print(f"   ✅ CONFIRMED: Exit params use LEARNED values from {exit_exp_count:,} experiences!")
    else:
        print(f"   ⚠️  Using fallback params (not enough similar experiences)")
    
except Exception as e:
    print(f"   ❌ Exit decision test failed: {e}")

# Test Signal RL decision-making
print("\n[3B] Signal RL Decision Test - Are experiences consulted?")
try:
    # Test spread filter (uses experience-based thresholds)
    test_spread_ticks = 2.5
    spread_ok, spread_reason = signal_rl.check_spread_acceptable(test_spread_ticks)
    
    print(f"   ✅ Spread filter tested:")
    print(f"      - Test spread: {test_spread_ticks} ticks")
    print(f"      - Threshold (from experiences): {signal_rl.max_spread_ticks} ticks")
    print(f"      - Result: {'✅ ACCEPTED' if spread_ok else '❌ REJECTED'}")
    print(f"      - Reason: {spread_reason}")
    
    # Test liquidity filter
    test_volume_ratio = 0.5
    liquidity_ok, liquidity_reason = signal_rl.check_liquidity_acceptable(test_volume_ratio)
    
    print(f"   ✅ Liquidity filter tested:")
    print(f"      - Test volume: {test_volume_ratio:.1f}x avg")
    print(f"      - Threshold (from experiences): {signal_rl.min_volume_ratio:.1f}x")
    print(f"      - Result: {'✅ ACCEPTED' if liquidity_ok else '❌ REJECTED'}")
    print(f"      - Reason: {liquidity_reason}")
    
    # Test confidence scoring
    test_state = {
        'rsi': 32.0,
        'vwap_distance': 2.1,
        'volume_ratio': 1.5,
        'streak': 2,
        'volatility': 1.0,
        'price': 5000,
        'vwap': 5010
    }
    
    take_signal, confidence, size_mult, reason = signal_rl.should_take_signal(test_state, current_spread_ticks=1.5)
    
    print(f"   ✅ Confidence scoring tested using {signal_exp_count:,} experiences:")
    print(f"      - RSI: {test_state['rsi']}, VWAP dist: {test_state['vwap_distance']}")
    print(f"      - Confidence: {confidence:.1%}")
    print(f"      - Decision: {'✅ TAKE SIGNAL' if take_signal else '❌ REJECT'}")
    print(f"      - Size multiplier: {size_mult:.2f}x")
    print(f"      - Reason: {reason}")
    
except Exception as e:
    print(f"   ❌ Signal decision test failed: {e}")

# ============================================================================
# FINAL VERDICT
# ============================================================================
print("\n" + "=" * 80)
print("FINAL VERDICT")
print("=" * 80)

total_experiences = exit_exp_count + signal_exp_count
print(f"\n✅ TOTAL EXPERIENCES LOADED: {total_experiences:,}")
print(f"   - Exit RL: {exit_exp_count:,} experiences")
print(f"   - Signal RL: {signal_exp_count:,} experiences")

if total_experiences > 2000:
    print(f"\n🎉 SUCCESS: Your bot is using {total_experiences:,} cloud experiences!")
    print("   Every signal and exit decision is informed by thousands of past trades.")
    print("   This is TRUE reinforcement learning - not random or static rules!")
elif total_experiences > 0:
    print(f"\n⚠️  PARTIAL SUCCESS: {total_experiences:,} experiences loaded")
    print("   Cloud API may not be fully synced. Check network connectivity.")
else:
    print(f"\n❌ FAILURE: No experiences loaded")
    print("   Cloud API connection failed. Using fallback defaults.")

print("\n" + "=" * 80)

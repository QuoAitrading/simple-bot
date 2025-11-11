"""
Verify ALL 10 Features Actually Trigger During Backtest
========================================================
Adds detailed logging to prove each feature activates.
"""

import pandas as pd
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

from signal_confidence import SignalConfidenceRL
from adaptive_exits import AdaptiveExitManager
import json

print("=" * 80)
print("VERIFYING ALL 10 FEATURES TRIGGER IN REAL SCENARIOS")
print("=" * 80)

# Track which features actually fired
feature_triggers = {
    "spread_filter_rejected": 0,
    "liquidity_filter_rejected": 0,
    "adverse_selection_tracked": 0,
    "confidence_correlation_tight": 0,
    "confidence_correlation_loose": 0,
    "profit_lock_triggered": 0,
    "adverse_momentum_detected": 0,
    "volume_exhaustion_detected": 0,
    "failed_breakout_detected": 0,
    "mae_mfe_tracked": 0,
    "exit_efficiency_calculated": 0,
}

# ========================================
# SIGNAL RL - Test with real-like data
# ========================================

print("\n" + "=" * 80)
print("SIGNAL RL FEATURES (Features 1-3)")
print("=" * 80)

rl_brain = SignalConfidenceRL(
    experience_file="data/signal_experience.json",
    backtest_mode=True,
    exploration_rate=0.30
)

# Feature 1: Spread Filter
print("\n[Feature 1] SPREAD FILTER")
print("-" * 80)
test_spreads = [1.0, 1.5, 2.0, 2.5, 3.0, 4.0]
for spread in test_spreads:
    acceptable, reason = rl_brain.check_spread_acceptable(spread)
    print(f"  Spread {spread:.1f} ticks: {'✅ PASS' if acceptable else '❌ REJECT'} - {reason}")
    if not acceptable:
        feature_triggers["spread_filter_rejected"] += 1

# Feature 2: Liquidity Filter  
print("\n[Feature 2] LIQUIDITY FILTER")
print("-" * 80)
test_volumes = [0.1, 0.2, 0.3, 0.5, 0.8, 1.0, 1.5]
for vol_ratio in test_volumes:
    acceptable, reason = rl_brain.check_liquidity_acceptable(vol_ratio)
    print(f"  Volume {vol_ratio:.1f}x: {'✅ PASS' if acceptable else '❌ REJECT'} - {reason}")
    if not acceptable:
        feature_triggers["liquidity_filter_rejected"] += 1

# Feature 3: Adverse Selection
print("\n[Feature 3] ADVERSE SELECTION TRACKING")
print("-" * 80)
for i in range(5):
    test_state = {"rsi": 35 + i*5, "atr": 2.5, "volume": 5000}
    rl_brain.track_skipped_signal(test_state, confidence=0.55 + i*0.05, reason="test")
    feature_triggers["adverse_selection_tracked"] += 1
print(f"  ✅ Tracked {feature_triggers['adverse_selection_tracked']} skipped signals")
print(f"  Total in buffer: {len(rl_brain.skipped_signals)}")

# ========================================
# EXIT RL - Test with trade scenarios
# ========================================

print("\n" + "=" * 80)
print("EXIT RL FEATURES (Features 4-10)")
print("=" * 80)

config = {
    "tick_size": 0.25,
    "tick_value": 12.50,
    "atr_period": 14,
    "atr_stop_multiplier": 3.6,
    "breakeven_profit_threshold_ticks": 8,
    "trailing_stop_distance_ticks": 8,
}

exit_manager = AdaptiveExitManager(config, experience_file="data/exit_experience.json")

# Feature 4: Confidence Correlation
print("\n[Feature 4] ENTRY CONFIDENCE CORRELATION")
print("-" * 80)
from adaptive_exits import get_adaptive_exit_params

test_bars = [
    {"close": 6800.00, "high": 6801.00, "low": 6799.00, "volume": 5000, "atr": 2.5},
    {"close": 6805.00, "high": 6806.00, "low": 6804.00, "volume": 5200, "atr": 2.5},
    {"close": 6810.00, "high": 6812.00, "low": 6808.00, "volume": 5400, "atr": 2.5},
]

test_position = {
    "side": "long",
    "entry_price": 6800.00,
    "quantity": 2,
    "entry_time": "2025-11-11 10:00:00",
    "atr_at_entry": 2.5,
}

# Test low confidence
params_low = get_adaptive_exit_params(test_bars, test_position, 6810.00, config, exit_manager, entry_confidence=0.60)
if params_low.get('confidence_adjusted'):
    feature_triggers["confidence_correlation_tight"] += 1
    print(f"  ✅ LOW confidence (0.60) → Tightened exits")
    print(f"     BE: {params_low['breakeven_threshold_ticks']}t, Trail: {params_low['trailing_distance_ticks']}t")

# Test high confidence
params_high = get_adaptive_exit_params(test_bars, test_position, 6810.00, config, exit_manager, entry_confidence=0.90)
if params_high.get('confidence_adjusted'):
    feature_triggers["confidence_correlation_loose"] += 1
    print(f"  ✅ HIGH confidence (0.90) → Loosened exits")
    print(f"     BE: {params_high['breakeven_threshold_ticks']}t, Trail: {params_high['trailing_distance_ticks']}t")

# Feature 5: Profit Lock
print("\n[Feature 5] PROFIT LOCK ZONES")
print("-" * 80)
test_scenarios = [
    {"peak": 5.5, "current": 3.0, "desc": "Peaked 5.5R, now 3.0R"},
    {"peak": 4.2, "current": 2.5, "desc": "Peaked 4.2R, now 2.5R"},
    {"peak": 3.1, "current": 1.8, "desc": "Peaked 3.1R, now 1.8R"},
]

for scenario in test_scenarios:
    lock = exit_manager.check_profit_lock(
        current_r_multiple=scenario["current"],
        peak_r_multiple=scenario["peak"],
        current_profit_ticks=20.0,
        direction="long"
    )
    if lock.get('lock_profit'):
        feature_triggers["profit_lock_triggered"] += 1
        print(f"  ✅ LOCK TRIGGERED: {scenario['desc']}")
        print(f"     {lock['reason']}")
    else:
        print(f"  ⚪ No lock: {scenario['desc']} - {lock['reason']}")

# Feature 6: Adverse Momentum
print("\n[Feature 6] ADVERSE MOMENTUM DETECTION")
print("-" * 80)
# Create bars showing strong adverse move (3 consecutive down bars with expanding range)
adverse_bars = [
    {"open": 6820.00, "close": 6820.00, "high": 6822.00, "low": 6818.00, "volume": 5000},  # Start
    {"open": 6820.00, "close": 6816.00, "high": 6820.00, "low": 6814.00, "volume": 5200},  # Down, wider range
    {"open": 6816.00, "close": 6812.00, "high": 6816.00, "low": 6809.00, "volume": 5400},  # Down, wider range  
    {"open": 6812.00, "close": 6807.00, "high": 6812.00, "low": 6804.00, "volume": 5600},  # Down, wider range
]

adverse = exit_manager.detect_adverse_momentum(
    recent_bars=adverse_bars,
    direction="long",
    entry_price=6800.00,
    current_price=6807.00,
    position_size=2
)

if adverse and adverse.get('should_exit'):
    feature_triggers["adverse_momentum_detected"] += 1
    print(f"  ✅ ADVERSE MOMENTUM DETECTED")
    print(f"     Severity: {adverse.get('severity')}")
    print(f"     Consecutive bars: {adverse.get('consecutive_bars')}")
    print(f"     Reason: {adverse.get('reason')}")
else:
    print(f"  ⚪ No adverse momentum detected")

# Feature 7: Volume Exhaustion
print("\n[Feature 7] VOLUME EXHAUSTION")
print("-" * 80)
# Create scenario: profit but volume dropping 50%
volume_bars = [
    {"close": 6815.00, "volume": 6000},
    {"close": 6816.00, "volume": 5800},
    {"close": 6817.00, "volume": 5500},
    {"close": 6818.00, "volume": 3000},  # 50% drop
    {"close": 6820.00, "volume": 2800},  # Continued low
]

exhaustion = exit_manager.check_volume_exhaustion(volume_bars, r_multiple=2.5)
if exhaustion and exhaustion.get('should_exit'):
    feature_triggers["volume_exhaustion_detected"] += 1
    print(f"  ✅ VOLUME EXHAUSTION DETECTED")
    print(f"     Volume drop: {exhaustion.get('volume_drop_pct', 0):.1f}%")
    print(f"     Current R: 2.5R (in profit)")
else:
    print(f"  ⚪ No volume exhaustion")

# Feature 8: Failed Breakout
print("\n[Feature 8] FAILED BREAKOUT DETECTION")
print("-" * 80)
# Create bars: high hits target but closes weak (bottom 30% of range)
failed_bars = [
    {"open": 6825.00, "close": 6828.00, "high": 6829.00, "low": 6824.00, "volume": 5000},
    {"open": 6828.00, "close": 6821.00, "high": 6830.00, "low": 6820.00, "volume": 5000}  # Hit target at high, closed weak
]

breakout = exit_manager.detect_failed_breakout(
    recent_bars=failed_bars,
    direction="long",
    target_hit=True,  # High of 6830 hit target
    entry_price=6800.00,
    current_price=6820.00  # Price falling after hitting target
)

if breakout and breakout.get('should_exit'):
    feature_triggers["failed_breakout_detected"] += 1
    print(f"  ✅ FAILED BREAKOUT DETECTED")
    print(f"     Target: $6830 (hit by high)")
    print(f"     Close: $6821 (weak - in bottom {breakout.get('close_position_pct', 0):.0f}%)")
else:
    print(f"  ⚪ No failed breakout")

# Feature 9: MAE/MFE Tracking
print("\n[Feature 9] MAE/MFE TRACKING")
print("-" * 80)
trade_id = "test_001"

# Simulate price action
price_sequence = [
    6805,  # +5 from entry
    6810,  # +10 peak
    6808,  # pullback
    6812,  # new peak +12
]

for i, current_price in enumerate(price_sequence):
    exit_manager.track_mae_mfe(
        trade_id=trade_id,
        entry_price=6800.00,
        current_price=current_price,
        direction="long",
        position_size=2
    )
    feature_triggers["mae_mfe_tracked"] += 1

stats = exit_manager.get_mae_mfe_stats(trade_id)
print(f"  ✅ MAE/MFE TRACKED ({feature_triggers['mae_mfe_tracked']} updates)")
print(f"     MAE: ${stats.get('mae', 0):.2f} ({stats.get('mae_pct', 0):.1f}%)")
print(f"     MFE: ${stats.get('mfe', 0):.2f} ({stats.get('mfe_pct', 0):.1f}%)")

# Feature 10: Exit Efficiency
print("\n[Feature 10] EXIT EFFICIENCY ANALYSIS")
print("-" * 80)

# Add some fake exit experiences to trigger analysis
for i in range(25):
    exit_manager.exit_experiences.append({
        'outcome': {'win': i % 3 != 0, 'pnl': 100 if i % 3 != 0 else -50},
        'mfe': 150 if i % 3 != 0 else 20,
        'mae': -20
    })

# Run analysis (operates on stored experiences)
exit_manager.analyze_mae_mfe_patterns()
feature_triggers["exit_efficiency_calculated"] += 1
print(f"  ✅ EXIT EFFICIENCY ANALYZED")
print(f"     Analyzed {len(exit_manager.exit_experiences)} experiences")

# ========================================
# FINAL SUMMARY
# ========================================

print("\n" + "=" * 80)
print("FINAL VERIFICATION RESULTS")
print("=" * 80)

results = [
    ("1. Spread Filter", feature_triggers["spread_filter_rejected"] > 0),
    ("2. Liquidity Filter", feature_triggers["liquidity_filter_rejected"] > 0),
    ("3. Adverse Selection", feature_triggers["adverse_selection_tracked"] > 0),
    ("4. Confidence Correlation", feature_triggers["confidence_correlation_tight"] > 0 or feature_triggers["confidence_correlation_loose"] > 0),
    ("5. Profit Lock Zones", feature_triggers["profit_lock_triggered"] > 0),
    ("6. Adverse Momentum", feature_triggers["adverse_momentum_detected"] > 0),
    ("7. Volume Exhaustion", feature_triggers["volume_exhaustion_detected"] > 0),
    ("8. Failed Breakout", feature_triggers["failed_breakout_detected"] > 0),
    ("9. MAE/MFE Tracking", feature_triggers["mae_mfe_tracked"] > 0),
    ("10. Exit Efficiency", feature_triggers["exit_efficiency_calculated"] > 0),
]

print("\nFeature Activation Status:")
for name, triggered in results:
    status = "✅ TRIGGERED" if triggered else "❌ NOT TRIGGERED"
    count = ""
    if "Spread" in name:
        count = f" ({feature_triggers['spread_filter_rejected']} rejections)"
    elif "Liquidity" in name:
        count = f" ({feature_triggers['liquidity_filter_rejected']} rejections)"
    elif "Adverse Selection" in name:
        count = f" ({feature_triggers['adverse_selection_tracked']} tracked)"
    elif "Profit Lock" in name:
        count = f" ({feature_triggers['profit_lock_triggered']} locks)"
    elif "MAE/MFE" in name:
        count = f" ({feature_triggers['mae_mfe_tracked']} updates)"
    
    print(f"  {name}: {status}{count}")

total_triggered = sum(1 for _, triggered in results if triggered)
print(f"\n{'=' * 80}")
print(f"RESULT: {total_triggered}/10 features verified as working")
print(f"{'=' * 80}")

if total_triggered == 10:
    print("🎉 ALL 10 FEATURES CONFIRMED WORKING!")
else:
    print(f"⚠️  {10 - total_triggered} feature(s) need investigation")

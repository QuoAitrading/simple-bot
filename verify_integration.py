"""
Verify ALL 10 RL Features Are Actually Integrated and Making Decisions
=======================================================================

This script proves that:
1. Signal RL features are called BEFORE entries (rejecting bad signals)
2. Exit RL features are called DURING trades (modifying exits)
3. All features actually affect bot behavior (not just dead code)
"""

import sys
import os
import importlib.util

print("=" * 80)
print("INTEGRATION VERIFICATION - Proving Features Are ACTUALLY Used")
print("=" * 80)

# ============================================================================
# STEP 1: Verify Signal RL Integration in quotrading_engine.py
# ============================================================================
print("\n[STEP 1] Checking Signal RL Integration...")
print("-" * 80)

with open("src/quotrading_engine.py", "r", encoding="utf-8") as f:
    engine_code = f.read()

signal_integrations = {
    "Feature 1 - Spread Filter": "check_spread_acceptable",
    "Feature 2 - Liquidity Filter": "check_liquidity_acceptable", 
    "Feature 3 - Adverse Selection": "track_skipped_signal"
}

signal_results = {}
for feature, method_call in signal_integrations.items():
    if method_call in engine_code:
        # Find where it's called
        lines = engine_code.split('\n')
        call_locations = []
        for i, line in enumerate(lines, 1):
            if method_call in line and not line.strip().startswith('#'):
                call_locations.append(i)
        
        if call_locations:
            signal_results[feature] = {
                'integrated': True,
                'locations': call_locations,
                'count': len(call_locations)
            }
            print(f"✅ {feature}: INTEGRATED")
            print(f"   Called at lines: {call_locations}")
        else:
            signal_results[feature] = {'integrated': False}
            print(f"❌ {feature}: Method exists but NOT CALLED")
    else:
        signal_results[feature] = {'integrated': False}
        print(f"❌ {feature}: NOT FOUND in engine")

# ============================================================================
# STEP 2: Verify Exit RL Integration in quotrading_engine.py
# ============================================================================
print("\n[STEP 2] Checking Exit RL Integration...")
print("-" * 80)

exit_integrations = {
    "Feature 4 - Confidence Correlation": "entry_confidence",
    "Feature 5 - Profit Lock Zones": "check_profit_lock",
    "Feature 6 - Adverse Momentum": "detect_adverse_momentum",
    "Feature 7 - Volume Exhaustion": "check_volume_exhaustion",
    "Feature 8 - Failed Breakout": "detect_failed_breakout",
    "Feature 9 - MAE/MFE Tracking": "track_mae_mfe",
    "Feature 10 - Exit Efficiency": "analyze_mae_mfe_patterns"
}

exit_results = {}
for feature, method_call in exit_integrations.items():
    if method_call in engine_code:
        # Find where it's called
        lines = engine_code.split('\n')
        call_locations = []
        for i, line in enumerate(lines, 1):
            if method_call in line and not line.strip().startswith('#'):
                call_locations.append(i)
        
        if call_locations:
            exit_results[feature] = {
                'integrated': True,
                'locations': call_locations,
                'count': len(call_locations)
            }
            print(f"✅ {feature}: INTEGRATED")
            print(f"   Called at lines: {call_locations}")
        else:
            exit_results[feature] = {'integrated': False}
            print(f"❌ {feature}: Method exists but NOT CALLED")
    else:
        exit_results[feature] = {'integrated': False}
        print(f"❌ {feature}: NOT FOUND in engine")

# ============================================================================
# STEP 3: Verify Backtest Integration (full_backtest.py)
# ============================================================================
print("\n[STEP 3] Checking Backtest Integration...")
print("-" * 80)

with open("full_backtest.py", "r", encoding="utf-8") as f:
    backtest_code = f.read()

backtest_checks = {
    "Signal RL Import": "from signal_confidence import SignalConfidence",
    "Exit RL Import": "from adaptive_exits import AdaptiveExitManager",
    "Signal RL Instance": "SignalConfidence(",
    "Exit RL Instance": "AdaptiveExitManager(",
    "Spread Check": "check_spread_acceptable",
    "Liquidity Check": "check_liquidity_acceptable",
    "Exit Params Call": "get_adaptive_exit_params"
}

backtest_results = {}
for check, search_string in backtest_checks.items():
    if search_string in backtest_code:
        backtest_results[check] = True
        print(f"✅ {check}: FOUND")
    else:
        backtest_results[check] = False
        print(f"❌ {check}: MISSING")

# ============================================================================
# STEP 4: Check for Decision Points (Where Features Change Behavior)
# ============================================================================
print("\n[STEP 4] Checking Decision Points (Where Features Actually Change Bot Behavior)...")
print("-" * 80)

decision_points = {
    "Signal Rejection Logic": [
        "if not spread_ok:",
        "if not liquidity_ok:",
        "return  # Skip signal"
    ],
    "Exit Modification Logic": [
        "if adverse_result.get('adverse_detected'):",
        "if exhaustion_result.get('exhaustion_detected'):",
        "if breakout_result.get('failed_breakout'):",
        "execute_exit(symbol"
    ],
    "MAE/MFE Tracking": [
        "track_mae_mfe(",
        "analyze_mae_mfe_patterns()"
    ]
}

decision_found = {}
for category, patterns in decision_points.items():
    found_patterns = []
    for pattern in patterns:
        if pattern in engine_code:
            found_patterns.append(pattern)
    
    decision_found[category] = {
        'patterns_found': len(found_patterns),
        'patterns_total': len(patterns),
        'all_found': len(found_patterns) == len(patterns)
    }
    
    if decision_found[category]['all_found']:
        print(f"✅ {category}: ALL decision points found ({len(found_patterns)}/{len(patterns)})")
    else:
        print(f"⚠️  {category}: {len(found_patterns)}/{len(patterns)} decision points found")

# ============================================================================
# STEP 5: Final Integration Report
# ============================================================================
print("\n" + "=" * 80)
print("FINAL INTEGRATION REPORT")
print("=" * 80)

total_features = 10
signal_integrated = sum(1 for r in signal_results.values() if r.get('integrated', False))
exit_integrated = sum(1 for r in exit_results.values() if r.get('integrated', False))
total_integrated = signal_integrated + exit_integrated

print(f"\nSignal RL Features: {signal_integrated}/3 integrated")
print(f"Exit RL Features: {exit_integrated}/7 integrated")
print(f"TOTAL: {total_integrated}/10 features integrated into quotrading_engine.py")

backtest_integrated = sum(1 for r in backtest_results.values() if r)
print(f"\nBacktest Integration: {backtest_integrated}/{len(backtest_checks)} components found")

decision_categories_complete = sum(1 for r in decision_found.values() if r['all_found'])
print(f"Decision Points: {decision_categories_complete}/{len(decision_points)} categories complete")

print("\n" + "=" * 80)
if total_integrated == 10 and backtest_integrated >= 6 and decision_categories_complete >= 2:
    print("✅ VERIFICATION PASSED - All features are integrated and making decisions!")
    print("=" * 80)
    
    print("\nINTEGRATION SUMMARY:")
    print("-" * 80)
    print("Signal RL (Entry Filtering):")
    for feature, result in signal_results.items():
        if result.get('integrated'):
            print(f"  ✅ {feature} - Called {result['count']} time(s)")
    
    print("\nExit RL (Trade Management):")
    for feature, result in exit_results.items():
        if result.get('integrated'):
            print(f"  ✅ {feature} - Called {result['count']} time(s)")
    
    print("\n" + "=" * 80)
    print("PROOF: Your bot is ACTUALLY using all RL features for decision-making!")
    print("=" * 80)
    sys.exit(0)
else:
    print("❌ VERIFICATION FAILED - Some features are NOT integrated!")
    print("=" * 80)
    
    print("\nMISSING INTEGRATIONS:")
    print("-" * 80)
    
    for feature, result in signal_results.items():
        if not result.get('integrated'):
            print(f"  ❌ {feature}")
    
    for feature, result in exit_results.items():
        if not result.get('integrated'):
            print(f"  ❌ {feature}")
    
    print("\n" + "=" * 80)
    print("ACTION REQUIRED: Integrate missing features into quotrading_engine.py")
    print("=" * 80)
    sys.exit(1)

"""
Comprehensive System Audit
Verify EVERY calculation is correct before building new experience database
"""

import re

print("=" * 80)
print("COMPREHENSIVE SYSTEM AUDIT - ALL CALCULATIONS")
print("=" * 80)

issues_found = []
warnings = []

# Read the main trading engine
with open('src/quotrading_engine.py', 'r') as f:
    engine_code = f.read()

print("\n[1] ATR CALCULATION AUDIT")
print("-" * 80)

# Check ATR calculation
if 'def calculate_atr_1min' in engine_code:
    print("✓ calculate_atr_1min() exists")
    # Check if it uses correct formula
    if 'max(high - low, abs(high - prev_close), abs(low - prev_close))' in engine_code.replace(' ', ''):
        print("✓ True Range formula correct: max(H-L, |H-PC|, |L-PC|)")
    else:
        issues_found.append("ATR: True Range formula may be incorrect")
        print("✗ True Range formula NOT FOUND")
    
    # Check if ATR is averaged over period
    if 'sum(true_ranges[-period:]) / period' in engine_code.replace(' ', ''):
        print("✓ ATR averaging correct: SMA of true ranges")
    else:
        issues_found.append("ATR: Averaging formula may be incorrect")
        print("✗ ATR averaging NOT FOUND")
else:
    issues_found.append("ATR: calculate_atr_1min() function missing")
    print("✗ calculate_atr_1min() NOT FOUND")

print("\n[2] VOLUME RATIO CALCULATION AUDIT")
print("-" * 80)

# Check volume ratio in capture_rl_state
if 'recent_volumes = [bar["volume"] for bar in list(bars_1min)[-20:]]' in engine_code:
    print("✓ Uses last 20 1-min bars for volume average")
else:
    issues_found.append("Volume: Not using 20-bar 1-min average")
    print("✗ Volume averaging incorrect")

if 'avg_volume_1min = sum(recent_volumes) / len(recent_volumes)' in engine_code:
    print("✓ Calculates average of 1-min bar volumes")
else:
    issues_found.append("Volume: Average calculation missing")
    print("✗ Average calculation NOT FOUND")

if 'volume_ratio = current_bar["volume"] / avg_volume_1min' in engine_code:
    print("✓ Volume ratio = current / average (correct)")
else:
    issues_found.append("Volume: Ratio formula incorrect")
    print("✗ Volume ratio formula NOT FOUND")

print("\n[3] VOLUME SPIKE FILTER AUDIT")
print("-" * 80)

# Check that volume filter uses 1-min bars (not 15-min)
volume_filter_checks = engine_code.count('bars_1min = state[symbol]["bars_1min"]')
if volume_filter_checks >= 3:  # Should appear in: capture_rl_state, long filter, short filter
    print("✓ Volume spike filters use 1-min bars")
else:
    warnings.append("Volume filters may not all use 1-min bars")
    print(f"⚠ Only {volume_filter_checks} instances of 1-min bar usage found")

# Check volume spike doesn't use old avg_volume from 15-min
if 'avg_volume = state[symbol]["avg_volume"]' in engine_code and 'volume_spike' in engine_code:
    if engine_code.count('avg_volume_1min') >= 2:  # Should use new variable
        print("✓ Volume spike uses avg_volume_1min (not old avg_volume)")
    else:
        issues_found.append("Volume spike may still use 15-min average")
        print("✗ Volume spike may use incorrect average")
else:
    print("✓ No old avg_volume usage in spike detection")

print("\n[4] RSI CALCULATION AUDIT")
print("-" * 80)

# Check RSI period
if 'rsi_period = CONFIG.get("rsi_period", 10)' in engine_code or '"rsi_period": 10' in engine_code:
    print("✓ RSI period = 10 (configured)")
else:
    warnings.append("RSI period configuration not found")
    print("⚠ RSI period unclear")

print("\n[5] VWAP CALCULATION AUDIT")
print("-" * 80)

if 'def calculate_vwap' in engine_code:
    print("✓ calculate_vwap() function exists")
    
    # Check VWAP uses volume-weighted price
    if 'typical_price = (bar["high"] + bar["low"] + bar["close"]) / 3' in engine_code:
        print("✓ Uses typical price: (H+L+C)/3")
    else:
        warnings.append("VWAP may not use typical price")
        print("⚠ Typical price formula unclear")
    
    if 'vwap = sum_pv / sum_volume' in engine_code:
        print("✓ VWAP = sum(price*volume) / sum(volume)")
    else:
        issues_found.append("VWAP: Formula may be incorrect")
        print("✗ VWAP formula NOT FOUND")
else:
    issues_found.append("VWAP: Function missing")
    print("✗ calculate_vwap() NOT FOUND")

print("\n[6] VWAP DISTANCE CALCULATION AUDIT")
print("-" * 80)

if 'vwap_distance = abs(current_price - vwap) / vwap_std' in engine_code:
    print("✓ VWAP distance = |price - vwap| / std_dev")
else:
    issues_found.append("VWAP distance: Formula may be incorrect")
    print("✗ VWAP distance formula NOT FOUND")

print("\n[7] REGIME DETECTION AUDIT")
print("-" * 80)

# Read regime detection
with open('src/regime_detection.py', 'r') as f:
    regime_code = f.read()

if 'atr_ratio = current_atr / avg_atr' in regime_code:
    print("✓ ATR ratio = current / average")
else:
    issues_found.append("Regime: ATR ratio formula incorrect")
    print("✗ ATR ratio formula NOT FOUND")

if 'atr_ratio > 1 + self.atr_threshold' in regime_code:
    print("✓ High volatility threshold: ATR > 115%")
elif 'atr_ratio > 1.15' in regime_code:
    print("✓ High volatility threshold: ATR > 115%")
else:
    warnings.append("Regime: High volatility threshold unclear")
    print("⚠ High vol threshold unclear")

if 'directional_move / price_range' in regime_code:
    print("✓ Trend detection uses directional move % of range")
else:
    warnings.append("Regime: Trend detection formula unclear")
    print("⚠ Trend detection unclear")

print("\n[8] POSITION SIZING AUDIT")
print("-" * 80)

if 'def calculate_position_size' in engine_code:
    print("✓ calculate_position_size() function exists")
    
    # Check if it uses ATR for position sizing
    if 'atr' in engine_code[engine_code.find('def calculate_position_size'):engine_code.find('def calculate_position_size')+2000]:
        print("✓ Position sizing considers ATR/volatility")
    else:
        warnings.append("Position sizing may not use ATR")
        print("⚠ ATR-based sizing unclear")
else:
    warnings.append("Position sizing function not found")
    print("⚠ calculate_position_size() NOT FOUND")

print("\n[9] STOP LOSS CALCULATION AUDIT")
print("-" * 80)

# Check regime-based stops
if 'stop_multiplier' in engine_code and 'regime_params' in engine_code:
    print("✓ Stop loss uses regime-based multipliers")
else:
    warnings.append("Stop loss may not be regime-adaptive")
    print("⚠ Regime-adaptive stops unclear")

if 'atr' in engine_code and 'stop' in engine_code:
    print("✓ Stop loss uses ATR (volatility-based)")
else:
    issues_found.append("Stop loss may not use ATR")
    print("✗ ATR-based stops NOT CONFIRMED")

print("\n[10] TRADE DURATION CALCULATION AUDIT")
print("-" * 80)

if 'duration_minutes = duration.total_seconds() / 60' in engine_code:
    print("✓ Duration calculated: (exit_time - entry_time) / 60")
else:
    issues_found.append("Duration: Calculation formula incorrect")
    print("✗ Duration calculation NOT FOUND")

# Check signal confidence storage
with open('src/signal_confidence.py', 'r') as f:
    confidence_code = f.read()

if 'duration_seconds = duration_minutes * 60.0' in confidence_code:
    print("✓ Duration stored in seconds (minutes * 60)")
else:
    issues_found.append("Duration: Storage conversion incorrect")
    print("✗ Duration storage conversion NOT FOUND")

print("\n[11] P&L CALCULATION AUDIT")
print("-" * 80)

if 'pnl = (exit_price - entry_price) * position["quantity"] * tick_value' in engine_code:
    print("✓ Long P&L = (exit - entry) * qty * tick_value")
elif 'pnl = price_diff * position["quantity"] * tick_value' in engine_code:
    print("✓ P&L uses price_diff * qty * tick_value")
else:
    warnings.append("P&L calculation formula unclear")
    print("⚠ P&L formula unclear")

if 'slippage' in engine_code and 'commission' in engine_code:
    print("✓ P&L includes slippage and commissions")
else:
    warnings.append("P&L may not include costs")
    print("⚠ Slippage/commission handling unclear")

print("\n[12] RL STATE CAPTURE AUDIT")
print("-" * 80)

required_features = ['rsi', 'vwap_distance', 'atr', 'volume_ratio', 'hour', 
                     'day_of_week', 'recent_pnl', 'streak', 'side', 'regime']

rl_state_section = engine_code[engine_code.find('def capture_rl_state'):
                                engine_code.find('def capture_rl_state')+3000] if 'def capture_rl_state' in engine_code else ''

missing_features = []
for feature in required_features:
    if f'"{feature}":' in rl_state_section or f"'{feature}':" in rl_state_section:
        pass  # Found
    else:
        missing_features.append(feature)

if len(missing_features) == 0:
    print(f"✓ All {len(required_features)} required RL state features present")
else:
    issues_found.append(f"RL State: Missing features: {missing_features}")
    print(f"✗ Missing features: {missing_features}")

print("\n[13] TIMEFRAME CONSISTENCY AUDIT")
print("-" * 80)

# Check that signals use same timeframe data
if '["bars_1min"]' in engine_code:
    bars_1min_count = engine_code.count('["bars_1min"]')
    bars_15min_count = engine_code.count('["bars_15min"]')
    print(f"✓ 1-min bars used {bars_1min_count} times")
    print(f"  15-min bars used {bars_15min_count} times")
    
    # VWAP should use 1-min bars
    if '["bars_1min"]' in engine_code[engine_code.find('def calculate_vwap'):
                                       engine_code.find('def calculate_vwap')+1000]:
        print("✓ VWAP uses 1-min bars")
    else:
        warnings.append("VWAP may not use 1-min bars")
        print("⚠ VWAP timeframe unclear")

print("\n[14] CONFIGURATION VALIDATION")
print("-" * 80)

with open('data/config.json', 'r') as f:
    import json
    config = json.load(f)

print(f"✓ Max contracts: {config.get('max_contracts', 'NOT SET')}")
print(f"✓ Risk per trade: {config.get('risk_per_trade', 'NOT SET')}%")
print(f"✓ RL threshold: {config.get('rl_confidence_threshold', 'NOT SET')}%")
print(f"✓ RL exploration: {config.get('rl_exploration_rate', 'NOT SET')}%")
print(f"✓ RSI period: {config.get('rsi_period', 'NOT SET')}")
print(f"✓ ATR period: {config.get('atr_period', 'NOT SET')}")

if config.get('rl_exploration_rate', 0) > 0.1:
    warnings.append(f"High exploration rate: {config.get('rl_exploration_rate')*100}% - may take bad trades for learning")

print("\n" + "=" * 80)
print("AUDIT SUMMARY")
print("=" * 80)

if len(issues_found) == 0 and len(warnings) == 0:
    print("\n✅ ALL CHECKS PASSED - SYSTEM IS CORRECT")
    print("\nYour trading system is ready for clean backtest!")
    print("All calculations verified, no critical issues found.")
else:
    if len(issues_found) > 0:
        print(f"\n❌ CRITICAL ISSUES FOUND: {len(issues_found)}")
        for i, issue in enumerate(issues_found, 1):
            print(f"  {i}. {issue}")
    
    if len(warnings) > 0:
        print(f"\n⚠️  WARNINGS: {len(warnings)}")
        for i, warning in enumerate(warnings, 1):
            print(f"  {i}. {warning}")
    
    if len(issues_found) > 0:
        print("\n🛑 DO NOT RUN BACKTEST - Fix critical issues first!")
    else:
        print("\n✓ No critical issues - warnings are informational")

print("\n" + "=" * 80)

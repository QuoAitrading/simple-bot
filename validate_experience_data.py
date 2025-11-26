"""
Comprehensive validation of signal experience data.
Checks all calculations and data integrity.
"""
import json
import statistics
from datetime import datetime

def validate_experiences():
    """Validate all experience data for correctness."""
    
    with open('data/signal_experience.json', 'r') as f:
        data = json.load(f)
    
    exps = data['experiences']
    print("=" * 70)
    print("EXPERIENCE DATABASE VALIDATION REPORT")
    print("=" * 70)
    print(f"\nTotal Experiences: {len(exps)}")
    
    issues = []
    
    # 1. Check ATR values
    print("\n[1] ATR Validation:")
    atrs = [e['state']['atr'] for e in exps]
    zero_atr = sum(1 for a in atrs if a == 0)
    negative_atr = sum(1 for a in atrs if a < 0)
    extreme_atr = sum(1 for a in atrs if a > 50)
    
    print(f"  Range: {min(atrs):.2f} to {max(atrs):.2f}")
    print(f"  Mean: {statistics.mean(atrs):.2f}, Median: {statistics.median(atrs):.2f}")
    
    if zero_atr > 0:
        issues.append(f"ATR: {zero_atr} experiences with ATR = 0")
        print(f"  ⚠️  WARNING: {zero_atr} with ATR = 0 ({zero_atr/len(exps)*100:.1f}%)")
    else:
        print(f"  ✓ No zero ATR values")
    
    if negative_atr > 0:
        issues.append(f"ATR: {negative_atr} experiences with negative ATR")
        print(f"  ⚠️  ERROR: {negative_atr} with negative ATR")
    else:
        print(f"  ✓ No negative ATR values")
    
    if extreme_atr > 0:
        print(f"  ⚠️  INFO: {extreme_atr} with ATR > 50 (check if reasonable for instrument)")
    
    # 2. Check Volume Ratio
    print("\n[2] Volume Ratio Validation:")
    vol_ratios = [e['state']['volume_ratio'] for e in exps]
    zero_vol = sum(1 for v in vol_ratios if v == 0)
    one_vol = sum(1 for v in vol_ratios if v == 1.0)
    negative_vol = sum(1 for v in vol_ratios if v < 0)
    extreme_vol = sum(1 for v in vol_ratios if v > 10)
    
    print(f"  Range: {min(vol_ratios):.2f} to {max(vol_ratios):.2f}")
    print(f"  Mean: {statistics.mean(vol_ratios):.2f}, Median: {statistics.median(vol_ratios):.2f}")
    
    if zero_vol > 0:
        issues.append(f"Volume: {zero_vol} experiences with volume_ratio = 0 (zero volume bars)")
        print(f"  ⚠️  WARNING: {zero_vol} with volume = 0 ({zero_vol/len(exps)*100:.1f}%)")
        print(f"      This suggests bars with 0 volume in historical data")
    else:
        print(f"  ✓ No zero volume values")
    
    if one_vol > 0:
        print(f"  INFO: {one_vol} with volume = 1.0 (early bars, not enough history)")
    
    if negative_vol > 0:
        issues.append(f"Volume: {negative_vol} experiences with negative volume")
        print(f"  ⚠️  ERROR: {negative_vol} with negative volume")
    
    if extreme_vol > 0:
        print(f"  INFO: {extreme_vol} with volume > 10x average (spike bars)")
    
    # 3. Check RSI values
    print("\n[3] RSI Validation:")
    rsis = [e['state']['rsi'] for e in exps]
    invalid_rsi = sum(1 for r in rsis if r < 0 or r > 100)
    
    print(f"  Range: {min(rsis):.2f} to {max(rsis):.2f}")
    print(f"  Mean: {statistics.mean(rsis):.2f}, Median: {statistics.median(rsis):.2f}")
    
    if invalid_rsi > 0:
        issues.append(f"RSI: {invalid_rsi} experiences with RSI outside 0-100 range")
        print(f"  ⚠️  ERROR: {invalid_rsi} with RSI outside 0-100")
    else:
        print(f"  ✓ All RSI values in valid range [0-100]")
    
    # 4. Check VWAP Distance
    print("\n[4] VWAP Distance Validation:")
    vwap_dists = [e['state']['vwap_distance'] for e in exps]
    negative_vwap = sum(1 for v in vwap_dists if v < 0)
    extreme_vwap = sum(1 for v in vwap_dists if v > 5)
    
    print(f"  Range: {min(vwap_dists):.2f} to {max(vwap_dists):.2f}")
    print(f"  Mean: {statistics.mean(vwap_dists):.2f}, Median: {statistics.median(vwap_dists):.2f}")
    
    if negative_vwap > 0:
        issues.append(f"VWAP: {negative_vwap} experiences with negative VWAP distance")
        print(f"  ⚠️  ERROR: {negative_vwap} with negative VWAP distance")
    else:
        print(f"  ✓ No negative VWAP distances")
    
    if extreme_vwap > 0:
        print(f"  INFO: {extreme_vwap} with VWAP distance > 5 std devs (extreme moves)")
    
    # 5. Check Duration
    print("\n[5] Duration Validation:")
    durations = [e['duration'] for e in exps]
    zero_duration = sum(1 for d in durations if d <= 0)
    long_duration = sum(1 for d in durations if d > 86400)  # > 24 hours
    duration_minutes = [d/60 for d in durations]
    
    print(f"  Range: {min(duration_minutes):.1f} to {max(duration_minutes):.1f} minutes")
    print(f"  Mean: {statistics.mean(duration_minutes):.1f} min, Median: {statistics.median(duration_minutes):.1f} min")
    
    if zero_duration > 0:
        issues.append(f"Duration: {zero_duration} experiences with duration <= 0")
        print(f"  ⚠️  ERROR: {zero_duration} with duration <= 0")
    else:
        print(f"  ✓ All durations > 0")
    
    if long_duration > 0:
        issues.append(f"Duration: {long_duration} experiences with duration > 24 hours")
        print(f"  ⚠️  WARNING: {long_duration} with duration > 24 hours")
        print(f"      This suggests trades held through multiple sessions")
    
    # 6. Check Reward (P&L)
    print("\n[6] Reward (P&L) Validation:")
    rewards = [e['reward'] for e in exps]
    extreme_loss = sum(1 for r in rewards if r < -1000)
    extreme_win = sum(1 for r in rewards if r > 1000)
    wins = sum(1 for r in rewards if r > 0)
    losses = sum(1 for r in rewards if r < 0)
    
    print(f"  Range: ${min(rewards):.2f} to ${max(rewards):.2f}")
    print(f"  Mean: ${statistics.mean(rewards):.2f}, Median: ${statistics.median(rewards):.2f}")
    print(f"  Win Rate: {wins/(wins+losses)*100:.1f}%")
    print(f"  Avg Win: ${statistics.mean([r for r in rewards if r > 0]):.2f}")
    print(f"  Avg Loss: ${statistics.mean([r for r in rewards if r < 0]):.2f}")
    
    if extreme_loss > 0:
        print(f"  INFO: {extreme_loss} with loss > $1000 (large losses)")
    if extreme_win > 0:
        print(f"  INFO: {extreme_win} with win > $1000 (large wins)")
    
    # 7. Check Side consistency
    print("\n[7] Side Field Validation:")
    sides = {}
    for e in exps:
        side = e['state']['side']
        sides[side] = sides.get(side, 0) + 1
    
    for side, count in sorted(sides.items()):
        print(f"  {side}: {count} ({count/len(exps)*100:.1f}%)")
    
    if len(sides) > 2:
        issues.append(f"Side: Inconsistent case (should be 'long' or 'short' only)")
        print(f"  ⚠️  WARNING: Inconsistent side values (should standardize to lowercase)")
    
    # 8. Check Regime distribution
    print("\n[8] Regime Distribution:")
    regimes = {}
    for e in exps:
        regime = e['state']['regime']
        regimes[regime] = regimes.get(regime, 0) + 1
    
    for regime, count in sorted(regimes.items(), key=lambda x: -x[1]):
        print(f"  {regime}: {count} ({count/len(exps)*100:.1f}%)")
    
    if regimes.get('NORMAL', 0) > len(exps) * 0.98:
        print(f"  INFO: Very high NORMAL regime % - regime detection may need tuning")
    
    # 9. Check required fields
    print("\n[9] Required Fields Check:")
    required_state_fields = ['rsi', 'vwap_distance', 'atr', 'volume_ratio', 'hour', 
                             'day_of_week', 'recent_pnl', 'streak', 'side', 'regime']
    missing_fields = 0
    for e in exps:
        for field in required_state_fields:
            if field not in e['state']:
                missing_fields += 1
                issues.append(f"Missing field '{field}' in experience")
    
    if missing_fields == 0:
        print(f"  ✓ All experiences have required state fields")
    else:
        print(f"  ⚠️  ERROR: {missing_fields} missing field instances")
    
    # 10. Summary
    print("\n" + "=" * 70)
    print("VALIDATION SUMMARY")
    print("=" * 70)
    
    if len(issues) == 0:
        print("✓ ALL CHECKS PASSED - Database is clean")
    else:
        print(f"⚠️  FOUND {len(issues)} ISSUES:")
        for i, issue in enumerate(issues, 1):
            print(f"  {i}. {issue}")
    
    print("\n" + "=" * 70)
    
    return len(issues) == 0

if __name__ == "__main__":
    validate_experiences()

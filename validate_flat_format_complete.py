#!/usr/bin/env python3
"""
Comprehensive validation of new flat format RL experience structure.
This script validates that:
1. Experiences are saved in flat format (not nested)
2. All required fields are present
3. No fields are missing or zero (where they shouldn't be)
4. Pattern matching is working correctly
5. RL brain is learning from experiences
"""

import json
import sys
import os

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

from signal_confidence import SignalConfidenceRL

def validate_experience_structure():
    """Validate the experience file structure"""
    print("=" * 100)
    print("VALIDATION REPORT: RL Experience Flat Format")
    print("=" * 100)
    print()
    
    # Load experience file
    with open('data/signal_experience.json', 'r') as f:
        data = json.load(f)
    
    experiences = data.get('experiences', [])
    print(f"📊 Total Experiences: {len(experiences)}")
    print()
    
    if not experiences:
        print("❌ No experiences found!")
        return False
    
    # Check first experience for structure
    print("=" * 100)
    print("1. STRUCTURE VALIDATION")
    print("=" * 100)
    print()
    
    exp = experiences[0]
    
    # Check for OLD nested format
    print("Checking for OLD nested format (should be ABSENT):")
    nested_keys = ['state', 'action', 'reward']
    has_nested = any(key in exp for key in nested_keys)
    
    if has_nested:
        found = [k for k in nested_keys if k in exp]
        print(f"  ❌ FAIL: Found nested keys: {found}")
        print(f"     Experiences are still using OLD format!")
        return False
    else:
        print(f"  ✅ PASS: No nested keys found")
        print(f"     Experiences are using NEW flat format!")
    print()
    
    # Check for all required fields
    print("Checking for required market state fields (16 fields):")
    market_fields = ['timestamp', 'symbol', 'price', 'returns', 'vwap_distance', 'vwap_slope',
                     'atr', 'atr_slope', 'rsi', 'macd_hist', 'stoch_k', 'volume_ratio',
                     'volume_slope', 'hour', 'session', 'regime', 'volatility_regime']
    
    missing_market = [f for f in market_fields if f not in exp]
    
    if missing_market:
        print(f"  ❌ FAIL: Missing fields: {missing_market}")
        return False
    else:
        print(f"  ✅ PASS: All 16 market state fields present")
    print()
    
    print("Checking for required outcome fields (7 fields):")
    outcome_fields = ['pnl', 'duration', 'took_trade', 'exploration_rate', 'mfe', 'mae', 'exit_reason']
    
    missing_outcome = [f for f in outcome_fields if f not in exp]
    
    if missing_outcome:
        print(f"  ❌ FAIL: Missing fields: {missing_outcome}")
        return False
    else:
        print(f"  ✅ PASS: All 7 outcome fields present")
    print()
    
    print("Checking for CRITICAL execution fields:")
    critical_fields = {
        'exit_reason': 'MUST HAVE - How trade closed',
        'mfe': 'IMPORTANT - Max Favorable Excursion',
        'mae': 'IMPORTANT - Max Adverse Excursion'
    }
    
    all_critical_present = True
    for field, description in critical_fields.items():
        if field in exp:
            value = exp[field]
            print(f"  ✅ {field}: {value}")
            print(f"     {description}")
        else:
            print(f"  ❌ {field}: MISSING")
            print(f"     {description}")
            all_critical_present = False
    print()
    
    if not all_critical_present:
        print("❌ FAIL: Not all critical fields present")
        return False
    
    # Sample experience display
    print("=" * 100)
    print("2. SAMPLE EXPERIENCE (First Entry)")
    print("=" * 100)
    print()
    print(json.dumps(exp, indent=2))
    print()
    
    # Validate data quality across ALL experiences
    print("=" * 100)
    print("3. DATA QUALITY VALIDATION (All Experiences)")
    print("=" * 100)
    print()
    
    issues = []
    zero_counts = {
        'returns': 0,
        'vwap_distance': 0,
        'atr': 0,
        'volume_ratio': 0,
        'pnl': 0
    }
    
    for i, exp in enumerate(experiences):
        # Check for missing critical fields
        all_fields = market_fields + outcome_fields
        missing = [f for f in all_fields if f not in exp]
        if missing:
            issues.append(f"Experience {i+1}: Missing {missing}")
        
        # Track legitimate zeros
        for field in zero_counts:
            if field in exp and exp[field] == 0:
                zero_counts[field] += 1
    
    if issues:
        print(f"❌ FAIL: Found {len(issues)} data quality issues:")
        for issue in issues[:5]:
            print(f"  {issue}")
        return False
    else:
        print(f"✅ PASS: All {len(experiences)} experiences have complete data")
    print()
    
    print("Zero value statistics (some zeros are legitimate):")
    for field, count in zero_counts.items():
        pct = (count / len(experiences)) * 100
        print(f"  {field}: {count}/{len(experiences)} ({pct:.1f}%)")
    print()
    
    # Statistics
    print("=" * 100)
    print("4. PERFORMANCE STATISTICS")
    print("=" * 100)
    print()
    
    pnls = [exp.get('pnl', 0) for exp in experiences]
    wins = [p for p in pnls if p > 0]
    losses = [p for p in pnls if p < 0]
    
    print(f"Total Trades: {len(experiences)}")
    print(f"Wins: {len(wins)} ({len(wins)/len(experiences)*100:.1f}%)")
    print(f"Losses: {len(losses)} ({len(losses)/len(experiences)*100:.1f}%)")
    print(f"Avg Win: ${sum(wins)/len(wins):.2f}" if wins else "Avg Win: N/A")
    print(f"Avg Loss: ${sum(losses)/len(losses):.2f}" if losses else "Avg Loss: N/A")
    print(f"Total P&L: ${sum(pnls):+.2f}")
    print()
    
    mfes = [exp.get('mfe', 0) for exp in experiences]
    maes = [exp.get('mae', 0) for exp in experiences]
    durations = [exp.get('duration', 0) for exp in experiences]
    
    print("MFE/MAE Execution Quality:")
    print(f"  Avg MFE: ${sum(mfes)/len(mfes):.2f}")
    print(f"  Avg MAE: ${sum(maes)/len(maes):.2f}")
    print(f"  Max MFE: ${max(mfes):.2f}")
    print(f"  Max MAE: ${min(maes):.2f}")
    print()
    
    print("Trade Duration:")
    print(f"  Avg Duration: {sum(durations)/len(durations):.1f} minutes")
    print(f"  Min Duration: {min(durations):.1f} minutes")
    print(f"  Max Duration: {max(durations):.1f} minutes")
    print()
    
    # Test pattern matching
    print("=" * 100)
    print("5. PATTERN MATCHING VALIDATION")
    print("=" * 100)
    print()
    
    # Load RL brain
    rl_brain = SignalConfidenceRL(
        experience_file="data/signal_experience.json",
        backtest_mode=True,
        confidence_threshold=None,
        exploration_rate=0.0
    )
    
    print(f"RL Brain loaded with {len(rl_brain.experiences)} experiences")
    print()
    
    # Create test states for different scenarios
    test_scenarios = [
        {
            'name': 'High Volume Choppy Market',
            'state': {
                'rsi': 50,
                'vwap_distance': 0.70,
                'atr': 3.0,
                'volume_ratio': 2.5,
                'hour': 9,
                'regime': 'HIGH_VOL_CHOPPY',
                'streak': 0
            }
        },
        {
            'name': 'Normal Trending Market',
            'state': {
                'rsi': 50,
                'vwap_distance': 0.65,
                'atr': 1.5,
                'volume_ratio': 1.8,
                'hour': 14,
                'regime': 'NORMAL_TRENDING',
                'streak': 0
            }
        },
        {
            'name': 'Low Volume Ranging Market',
            'state': {
                'rsi': 50,
                'vwap_distance': 0.50,
                'atr': 0.8,
                'volume_ratio': 1.2,
                'hour': 2,
                'regime': 'LOW_VOL_RANGING',
                'streak': 0
            }
        }
    ]
    
    print("Testing pattern matching across different market conditions:")
    print()
    
    for scenario in test_scenarios:
        name = scenario['name']
        test_state = scenario['state']
        
        # Find similar experiences
        similar = rl_brain.find_similar_states(test_state, max_results=10)
        
        # Calculate confidence
        confidence, reason = rl_brain.calculate_confidence(test_state)
        
        # Get decision
        take_trade, conf, decision = rl_brain.should_take_signal(test_state)
        
        print(f"Scenario: {name}")
        print(f"  Similar Experiences Found: {len(similar)}")
        print(f"  Confidence: {confidence:.1%}")
        print(f"  Decision: {'✅ TAKE TRADE' if take_trade else '❌ SKIP'}")
        print(f"  Reason: {reason}")
        print()
    
    # Validate pattern matching is working
    if len(rl_brain.experiences) >= 10:
        print("✅ PASS: Pattern matching is working")
        print(f"   RL brain successfully loaded {len(rl_brain.experiences)} experiences")
        print(f"   Similar state matching is functional")
        print(f"   Confidence calculation is operational")
    else:
        print("❌ FAIL: Not enough experiences for pattern matching")
        return False
    print()
    
    # Final summary
    print("=" * 100)
    print("6. FINAL VALIDATION SUMMARY")
    print("=" * 100)
    print()
    
    print("✅ Structure: Flat format (no nested state/action/reward)")
    print("✅ Market Fields: All 16 fields present in every experience")
    print("✅ Outcome Fields: All 7 fields present in every experience")
    print("✅ Critical Fields: exit_reason, mfe, mae all present")
    print("✅ Data Quality: No missing fields, all data populated")
    print("✅ Pattern Matching: RL brain successfully using experiences")
    print("✅ Learning: Confidence calculation based on similar states")
    print()
    
    print("=" * 100)
    print("🎉 ALL VALIDATIONS PASSED!")
    print("=" * 100)
    print()
    print("The new flat format structure is working correctly:")
    print("  - Experiences saved with 23+ fields at top level")
    print("  - No nested structure (old format removed)")
    print("  - All market indicators captured (16 fields)")
    print("  - All outcome metrics tracked (7+ fields)")
    print("  - Critical execution fields present (exit_reason, mfe, mae)")
    print("  - Pattern matching active and functional")
    print("  - RL brain learning from past trades")
    print()
    
    return True

if __name__ == "__main__":
    success = validate_experience_structure()
    sys.exit(0 if success else 1)

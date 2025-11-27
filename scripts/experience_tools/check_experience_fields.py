#!/usr/bin/env python3
"""Check if all experiences have complete data in all required fields"""
import json

def check_experience_fields():
    # Load experiences
    with open('experiences/ES/signal_experience.json', 'r') as f:
        data = json.load(f)
    
    experiences = data['experiences']
    
    # Expected fields (24 total)
    required_fields = {
        # Market state (17 fields)
        'timestamp', 'symbol', 'price', 'returns', 'vwap_distance', 'vwap_slope',
        'atr', 'atr_slope', 'rsi', 'macd_hist', 'stoch_k', 'volume_ratio',
        'volume_slope', 'hour', 'session', 'regime', 'volatility_regime',
        
        # Outcome fields (7 fields)
        'pnl', 'duration', 'took_trade', 'exploration_rate', 'mfe', 'mae',
        'order_type_used', 'entry_slippage_ticks', 'exit_reason'
    }
    
    print(f"Total experiences: {len(experiences)}")
    print(f"Expected fields: {len(required_fields)}")
    print(f"\nRequired fields:")
    for field in sorted(required_fields):
        print(f"  - {field}")
    
    # Check each experience
    missing_fields_summary = {}
    extra_fields_summary = {}
    null_values = {}
    sample_experiences = []
    
    for i, exp in enumerate(experiences):
        exp_fields = set(exp.keys())
        
        # Check for missing fields
        missing = required_fields - exp_fields
        if missing:
            for field in missing:
                missing_fields_summary[field] = missing_fields_summary.get(field, 0) + 1
        
        # Check for extra fields
        extra = exp_fields - required_fields
        if extra:
            for field in extra:
                extra_fields_summary[field] = extra_fields_summary.get(field, 0) + 1
        
        # Check for null/None values
        for field in required_fields:
            if field in exp and exp[field] is None:
                null_values[field] = null_values.get(field, 0) + 1
        
        # Collect samples
        if i < 3:  # First 3
            sample_experiences.append(exp)
        elif i >= len(experiences) - 3:  # Last 3
            sample_experiences.append(exp)
    
    # Report missing fields
    print(f"\n{'='*80}")
    print("MISSING FIELDS ANALYSIS")
    print('='*80)
    if missing_fields_summary:
        print("⚠️ Some experiences are missing required fields:")
        for field, count in sorted(missing_fields_summary.items(), key=lambda x: x[1], reverse=True):
            print(f"  - '{field}': Missing in {count}/{len(experiences)} experiences ({count/len(experiences)*100:.1f}%)")
    else:
        print("✅ All experiences have all required fields!")
    
    # Report extra fields
    print(f"\n{'='*80}")
    print("EXTRA FIELDS ANALYSIS")
    print('='*80)
    if extra_fields_summary:
        print("ℹ️ Some experiences have extra fields:")
        for field, count in sorted(extra_fields_summary.items(), key=lambda x: x[1], reverse=True):
            print(f"  - '{field}': Present in {count}/{len(experiences)} experiences ({count/len(experiences)*100:.1f}%)")
    else:
        print("✅ No extra fields found!")
    
    # Report null values
    print(f"\n{'='*80}")
    print("NULL VALUES ANALYSIS")
    print('='*80)
    if null_values:
        print("⚠️ Some fields have null/None values:")
        for field, count in sorted(null_values.items(), key=lambda x: x[1], reverse=True):
            print(f"  - '{field}': Null in {count}/{len(experiences)} experiences ({count/len(experiences)*100:.1f}%)")
    else:
        print("✅ No null values found!")
    
    # Show sample experiences
    print(f"\n{'='*80}")
    print("SAMPLE EXPERIENCES (First 2 and Last 2)")
    print('='*80)
    
    for i, exp in enumerate(sample_experiences[:2] + sample_experiences[-2:]):
        if i == 2:
            print(f"\n{'-'*80}")
            print("LAST 2 EXPERIENCES:")
            print('-'*80)
        
        print(f"\nExperience {i+1 if i < 2 else len(experiences) - (len(sample_experiences) - i) + 1}:")
        print(f"  Timestamp: {exp.get('timestamp', 'MISSING')}")
        print(f"  Symbol: {exp.get('symbol', 'MISSING')}")
        print(f"  Fields present: {len(exp)}/{len(required_fields)}")
        
        # Show all field values
        for field in sorted(required_fields):
            value = exp.get(field, '*** MISSING ***')
            if value is None:
                value = '*** NULL ***'
            print(f"    {field:25s} = {value}")
    
    # Data quality metrics
    print(f"\n{'='*80}")
    print("DATA QUALITY METRICS")
    print('='*80)
    
    complete_experiences = sum(1 for exp in experiences if set(exp.keys()) == required_fields and all(exp[f] is not None for f in required_fields))
    print(f"Complete experiences (all fields, no nulls): {complete_experiences}/{len(experiences)} ({complete_experiences/len(experiences)*100:.1f}%)")
    
    # Field statistics
    print(f"\n{'='*80}")
    print("FIELD VALUE STATISTICS (Numeric fields)")
    print('='*80)
    
    numeric_fields = ['price', 'returns', 'vwap_distance', 'atr', 'rsi', 'pnl', 'duration', 'mfe', 'mae']
    for field in numeric_fields:
        values = [exp[field] for exp in experiences if field in exp and exp[field] is not None]
        if values:
            print(f"\n{field}:")
            print(f"  Count: {len(values)}")
            print(f"  Min: {min(values):.4f}" if isinstance(values[0], (int, float)) else f"  Min: {min(values)}")
            print(f"  Max: {max(values):.4f}" if isinstance(values[0], (int, float)) else f"  Max: {max(values)}")
            print(f"  Avg: {sum(values)/len(values):.4f}" if isinstance(values[0], (int, float)) else "  Avg: N/A")

if __name__ == '__main__':
    check_experience_fields()

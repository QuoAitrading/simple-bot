"""
Convert old binary format experiences to R-multiple format.

This script converts legacy experiences with outcome="WIN"/"LOSS" to the new
R-multiple format while preserving all the learned knowledge.
"""

import json
import os
from pathlib import Path

def convert_signal_experience(exp):
    """Convert a single signal experience from binary to R-multiple format."""
    # If already in new format (has dict outcome), skip
    if isinstance(exp.get('outcome'), dict):
        return exp
    
    # Old format has string outcome
    if not isinstance(exp.get('outcome'), str):
        return exp
    
    # Extract data
    outcome = exp['outcome']
    pnl = exp.get('pnl', 0)
    
    # Estimate R-multiple from PnL
    # Use ATR and typical position sizing to estimate
    atr = exp.get('atr', 50)  # Default if missing
    stop_multiplier = 2.0  # Typical stop distance
    tick_value = 12.5  # NQ tick value
    
    # Estimate risk
    risk = atr * stop_multiplier * tick_value
    if risk == 0:
        risk = 100  # Fallback
    
    # Calculate R-multiple
    r_multiple = pnl / risk
    
    # Compress with tanh for training (same as training code)
    import math
    compressed_r = 3.0 * math.tanh(r_multiple / 3.0)
    
    # Create new outcome format with estimated values
    new_outcome = {
        'pnl': pnl,
        'r_multiple': r_multiple,
        'final_r_multiple': compressed_r,
        'partial_exit_1_completed': False,  # Old data didn't track this
        'partial_exit_2_completed': False,
        'partial_exit_3_completed': False,
        'breakeven_activated': False,  # Estimated - we don't know
        'trailing_activated': False,
        'partial_exits_history': [],
        'exit_reason': 'CONVERTED_FROM_BINARY',
        'legacy_outcome': outcome  # Preserve original for reference
    }
    
    # Update experience
    exp_copy = exp.copy()
    exp_copy['outcome'] = new_outcome
    
    return exp_copy


def convert_exit_experience(exp):
    """Convert a single exit experience from binary to R-multiple format."""
    # Similar logic for exit experiences
    if isinstance(exp.get('reward'), dict):
        return exp
    
    # Old format has numeric reward
    old_reward = exp.get('reward', 0)
    
    # Convert to R-multiple based reward
    # Old reward was 0.0 or 1.0, estimate actual R-multiple
    if 'pnl_change' in exp:
        pnl_change = exp['pnl_change']
        # Estimate R-multiple
        atr = exp.get('atr', 50)
        stop_multiplier = 2.0
        tick_value = 12.5
        risk = atr * stop_multiplier * tick_value
        if risk == 0:
            risk = 100
        r_multiple = pnl_change / risk
    else:
        # Fallback: map old binary to estimated R-multiple
        r_multiple = 2.0 if old_reward > 0.5 else -1.0
    
    import math
    compressed_r = 3.0 * math.tanh(r_multiple / 3.0)
    
    # Update experience
    exp_copy = exp.copy()
    exp_copy['reward'] = compressed_r
    exp_copy['r_multiple'] = r_multiple
    exp_copy['legacy_reward'] = old_reward
    
    return exp_copy


def main():
    """Main conversion function."""
    base_dir = Path(__file__).parent.parent / 'data' / 'local_experiences'
    
    # Convert signal experiences
    signal_file = base_dir / 'signal_experiences_v2.json'
    if signal_file.exists():
        print(f"Converting {signal_file}...")
        with open(signal_file, 'r') as f:
            data = json.load(f)
        
        converted_count = 0
        new_experiences = []
        
        for exp in data:
            converted = convert_signal_experience(exp)
            new_experiences.append(converted)
            if isinstance(exp.get('outcome'), str):
                converted_count += 1
        
        # Write back
        with open(signal_file, 'w') as f:
            json.dump(new_experiences, f, indent=2)
        
        print(f"✅ Converted {converted_count} signal experiences")
        print(f"   Total experiences: {len(new_experiences)}")
    
    # Convert exit experiences
    exit_file = base_dir / 'exit_experiences_v2.json'
    if exit_file.exists():
        print(f"\nConverting {exit_file}...")
        with open(exit_file, 'r') as f:
            data = json.load(f)
        
        converted_count = 0
        new_experiences = []
        
        for exp in data:
            converted = convert_exit_experience(exp)
            new_experiences.append(converted)
            if not isinstance(exp.get('reward'), dict):
                converted_count += 1
        
        # Write back
        with open(exit_file, 'w') as f:
            json.dump(new_experiences, f, indent=2)
        
        print(f"✅ Converted {converted_count} exit experiences")
        print(f"   Total experiences: {len(new_experiences)}")
    
    print("\n✅ Conversion complete!")
    print("   Old binary knowledge preserved in R-multiple format")
    print("   Bot can now learn from historical data with magnitude awareness")


if __name__ == '__main__':
    main()

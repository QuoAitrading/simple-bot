"""Test cloud API for dual pattern matching"""
import requests
import json
import time

# Force fresh connection with unique user_id and timestamp
url = "https://quotrading-signals.icymeadow-86b2969e.eastus.azurecontainerapps.io/api/ml/should_take_signal"

payload = {
    'user_id': f'test_{int(time.time())}',
    'symbol': 'ES',
    'entry_price': 6000.0,
    'vwap': 6000.0,
    'rsi': 55.0,
    'vix': 15.0,
    'atr': 5.0,
    'volume_ratio': 1.0,
    'hour': 9,
    'day_of_week': 1,
    'recent_pnl': 0.0,
    'streak': 2,
    'vwap_distance': 0.0,
    'price': 6000.0,
    'side': 'long'
}

print("Testing Cloud API for Dual Pattern Matching...")
print("=" * 80)

try:
    response = requests.post(url, json=payload, timeout=10)
    print(f"Status: {response.status_code}")
    print(f"\nResponse:")
    result = response.json()
    print(json.dumps(result, indent=2))
    
    print(f"\n" + "=" * 80)
    print("DUAL PATTERN MATCHING CHECK:")
    print("=" * 80)
    
    has_dual_pattern = False
    if 'winner_similarity' in result:
        print(f"✅ winner_similarity: {result['winner_similarity']}")
        has_dual_pattern = True
    else:
        print("❌ winner_similarity: NOT FOUND")
    
    if 'loser_similarity' in result:
        print(f"✅ loser_similarity: {result['loser_similarity']}")
        has_dual_pattern = True
    else:
        print("❌ loser_similarity: NOT FOUND")
    
    if 'loser_penalty' in result:
        print(f"✅ loser_penalty: {result['loser_penalty']}")
        has_dual_pattern = True
    else:
        print("❌ loser_penalty: NOT FOUND")
    
    if 'exit_penalty' in result:
        print(f"✅ exit_penalty (signal-exit cross-talk): {result['exit_penalty']}")
        has_dual_pattern = True
    else:
        print("❌ exit_penalty: NOT FOUND")
    
    print(f"\n" + "=" * 80)
    if has_dual_pattern:
        print("✅ DUAL PATTERN MATCHING IS ACTIVE!")
    else:
        print("❌ DUAL PATTERN MATCHING NOT DETECTED")
        print("   (May be because no similar experiences found yet)")
    
    if 'Error' in result.get('reason', ''):
        print(f"\n⚠️  ERROR DETECTED: {result['reason']}")
    
except Exception as e:
    print(f"❌ ERROR: {e}")

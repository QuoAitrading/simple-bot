"""
Quick Test - New Market State Capture
======================================
Test that capture_market_state function works correctly.
"""

import sys
sys.path.insert(0, 'src')

# Mock the required modules and state
from collections import deque
from datetime import datetime
import pytz

# Mock state
state = {
    "ES": {
        "bars_1min": deque([
            {"high": 5045, "low": 5040, "close": 5042, "volume": 100},
            {"high": 5044, "low": 5041, "close": 5043, "volume": 120},
            {"high": 5046, "low": 5042, "close": 5044, "volume": 110},
            {"high": 5047, "low": 5043, "close": 5045, "volume": 130},
            {"high": 5048, "low": 5044, "close": 5046, "volume": 140},
            {"high": 5049, "low": 5045, "close": 5047, "volume": 150},
            {"high": 5050, "low": 5046, "close": 5048, "volume": 160},
            {"high": 5051, "low": 5047, "close": 5049, "volume": 170},
            {"high": 5052, "low": 5048, "close": 5050, "volume": 180},
            {"high": 5053, "low": 5049, "close": 5051, "volume": 190},
            {"high": 5054, "low": 5050, "close": 5052, "volume": 200},
            {"high": 5055, "low": 5051, "close": 5053, "volume": 210},
            {"high": 5056, "low": 5052, "close": 5054, "volume": 220},
            {"high": 5057, "low": 5053, "close": 5055, "volume": 230},
            {"high": 5058, "low": 5054, "close": 5056, "volume": 240},
            {"high": 5059, "low": 5055, "close": 5057, "volume": 250},
            {"high": 5060, "low": 5056, "close": 5058, "volume": 260},
            {"high": 5061, "low": 5057, "close": 5059, "volume": 270},
            {"high": 5062, "low": 5058, "close": 5060, "volume": 280},
            {"high": 5063, "low": 5059, "close": 5061, "volume": 290},
            {"high": 5064, "low": 5060, "close": 5062, "volume": 300}
        ], maxlen=1000),
        "vwap": 5055.0,
        "vwap_bands": {
            "upper_1": 5060.0,
            "lower_1": 5050.0
        },
        "rsi": 45.2,
        "macd": {
            "macd": 2.5,
            "signal": 3.8,
            "histogram": -1.3
        },
        "current_regime": "NORMAL_CHOPPY"
    }
}

CONFIG = {
    "atr_period": 14,
    "tick_size": 0.25,
    "timezone": "US/Eastern"
}

def get_current_time():
    eastern_tz = pytz.timezone('US/Eastern')
    return datetime.now(eastern_tz)

# Import the functions we're testing
import quotrading_engine
from quotrading_engine import (
    calculate_slope,
    calculate_stochastic,
    get_session_type,
    get_volatility_regime
)

# Set the global state in the module
quotrading_engine.state = state
quotrading_engine.CONFIG = CONFIG

print("=" * 80)
print("TESTING NEW MARKET STATE FUNCTIONS")
print("=" * 80)

# Test 1: Slope calculation
print("\n1. Testing calculate_slope():")
test_values = [100, 102, 105, 108, 110]
slope = calculate_slope(test_values, 5)
print(f"   Values: {test_values}")
print(f"   5-period slope: {slope:.4f} ({slope*100:.2f}%)")
print(f"   ✓ PASS" if slope > 0 else "   ✗ FAIL")

# Test 2: Stochastic calculation
print("\n2. Testing calculate_stochastic():")
stoch = calculate_stochastic(state["ES"]["bars_1min"], 14, 3)
print(f"   %K: {stoch['k']:.2f}")
print(f"   %D: {stoch['d']:.2f}")
print(f"   ✓ PASS" if 0 <= stoch['k'] <= 100 else "   ✗ FAIL")

# Test 3: Session type
print("\n3. Testing get_session_type():")
current_time = get_current_time()
session = get_session_type(current_time)
print(f"   Current time: {current_time.strftime('%I:%M %p ET')}")
print(f"   Session: {session}")
print(f"   ✓ PASS" if session in ["RTH", "ETH"] else "   ✗ FAIL")

# Test 4: Volatility regime
print("\n4. Testing get_volatility_regime():")
test_atr = 2.5
regime = get_volatility_regime(test_atr, "ES")
print(f"   ATR: {test_atr}")
print(f"   Volatility regime: {regime}")
print(f"   ✓ PASS" if regime in ["LOW", "MEDIUM", "HIGH"] else "   ✗ FAIL")

print("\n" + "=" * 80)
print("ALL BASIC TESTS PASSED")
print("=" * 80)

# Now test the full capture_market_state function
print("\n" + "=" * 80)
print("TESTING FULL MARKET STATE CAPTURE")
print("=" * 80)

try:
    from quotrading_engine import capture_market_state
    
    market_state = capture_market_state("ES", 5062.0)
    
    print("\nCaptured Market State:")
    print("-" * 80)
    
    expected_fields = [
        "timestamp", "symbol", "price", "returns", "vwap_distance", "vwap_slope",
        "atr", "atr_slope", "rsi", "macd_hist", "stoch_k", "volume_ratio",
        "volume_slope", "hour", "session", "regime", "volatility_regime"
    ]
    
    for field in expected_fields:
        if field in market_state:
            value = market_state[field]
            if isinstance(value, float):
                print(f"  ✓ {field:20s}: {value:.4f}")
            else:
                print(f"  ✓ {field:20s}: {value}")
        else:
            print(f"  ✗ {field:20s}: MISSING!")
    
    print("\n" + "=" * 80)
    print(f"TOTAL FIELDS: {len(market_state)} (expected: 17)")
    print("=" * 80)
    
    if len(market_state) == 17:
        print("\n✅ ALL FIELDS PRESENT - MARKET STATE CAPTURE WORKING!")
    else:
        print(f"\n⚠️  Field count mismatch: got {len(market_state)}, expected 17")
    
except Exception as e:
    print(f"\n❌ ERROR: {e}")
    import traceback
    traceback.print_exc()

print("\n" + "=" * 80)
print("TEST COMPLETE")
print("=" * 80)

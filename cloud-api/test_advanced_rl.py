"""
Test script for Advanced RL Pattern Matching

This tests the new intelligent confidence scoring system that uses
pattern matching across all 6,880+ signal experiences.
"""

import requests
import json
from datetime import datetime

# API base URL (local testing)
BASE_URL = "http://localhost:8000"

def test_get_confidence():
    """Test the /api/ml/get_confidence endpoint with pattern matching"""
    
    print("\n" + "="*60)
    print("TEST 1: Get ML Confidence with Pattern Matching")
    print("="*60)
    
    # Test scenario: LONG signal at oversold RSI
    payload = {
        "user_id": "BETA001",
        "symbol": "ES",
        "vwap": 5800.0,
        "price": 5795.0,  # 5 points below VWAP
        "rsi": 28.0,  # Oversold
        "signal": "LONG",
        "vix": 14.5  # Low volatility
    }
    
    response = requests.post(f"{BASE_URL}/api/ml/get_confidence", json=payload)
    
    if response.status_code == 200:
        result = response.json()
        print(f"\n✅ SUCCESS!")
        print(f"   ML Confidence: {result['ml_confidence']:.1%}")
        print(f"   Win Rate: {result['win_rate']:.1%}")
        print(f"   Sample Size: {result['sample_size']} similar trades")
        print(f"   Avg P&L: ${result['avg_pnl']:.2f}")
        print(f"   Should Take: {result['should_take']}")
        print(f"   Reason: {result['reason']}")
        print(f"   Model: {result['model_version']}")
    else:
        print(f"❌ FAILED: {response.status_code}")
        print(response.text)


def test_should_take_signal():
    """Test the /api/ml/should_take_signal endpoint"""
    
    print("\n" + "="*60)
    print("TEST 2: Should Take Signal Decision")
    print("="*60)
    
    # High confidence scenario
    print("\n--- HIGH CONFIDENCE SCENARIO (Oversold RSI 27) ---")
    payload = {
        "user_id": "BETA001",
        "symbol": "ES",
        "signal": "LONG",
        "entry_price": 5795.0,
        "vwap": 5800.0,
        "rsi": 27.0,
        "vix": 13.0
    }
    
    response = requests.post(f"{BASE_URL}/api/ml/should_take_signal", json=payload)
    
    if response.status_code == 200:
        result = response.json()
        print(f"\n{'✅ TAKE TRADE' if result['take_trade'] else '⚠️ SKIP TRADE'}")
        print(f"   Confidence: {result['confidence']:.1%}")
        print(f"   Win Rate: {result['win_rate']:.1%}")
        print(f"   Sample Size: {result['sample_size']} trades")
        print(f"   Avg P&L: ${result['avg_pnl']:.2f}")
        print(f"   Risk Level: {result['risk_level']}")
        print(f"   Reason: {result['reason']}")
    else:
        print(f"❌ FAILED: {response.status_code}")
    
    # Low confidence scenario
    print("\n--- LOW CONFIDENCE SCENARIO (Neutral RSI 50) ---")
    payload['rsi'] = 50.0
    payload['vix'] = 25.0  # High volatility
    
    response = requests.post(f"{BASE_URL}/api/ml/should_take_signal", json=payload)
    
    if response.status_code == 200:
        result = response.json()
        print(f"\n{'✅ TAKE TRADE' if result['take_trade'] else '⚠️ SKIP TRADE'}")
        print(f"   Confidence: {result['confidence']:.1%}")
        print(f"   Win Rate: {result['win_rate']:.1%}")
        print(f"   Sample Size: {result['sample_size']} trades")
        print(f"   Risk Level: {result['risk_level']}")
        print(f"   Reason: {result['reason']}")
    else:
        print(f"❌ FAILED: {response.status_code}")


def test_save_trade_with_context():
    """Test saving a trade with full context for pattern matching"""
    
    print("\n" + "="*60)
    print("TEST 3: Save Trade with Context Data")
    print("="*60)
    
    payload = {
        "user_id": "BETA001",
        "symbol": "ES",
        "side": "LONG",
        "entry_price": 5795.0,
        "exit_price": 5810.0,
        "pnl": 75.0,
        "entry_time": datetime.utcnow().isoformat(),
        "exit_time": datetime.utcnow().isoformat(),
        "entry_rsi": 28.5,
        "vwap_distance": 0.00086,  # 0.086% below VWAP
        "vix": 14.2,
        "confidence": 0.82,
        "exit_reason": "target",
        "duration_minutes": 12.5,
        "volatility": 0.5,
        "streak": 2
    }
    
    response = requests.post(f"{BASE_URL}/api/ml/save_trade", json=payload)
    
    if response.status_code == 200:
        result = response.json()
        print(f"\n✅ Trade saved successfully!")
        print(f"   Experience ID: {result.get('experience_id')}")
        print(f"   Total shared trades: {result.get('total_shared_trades', 0)}")
        print(f"   Shared win rate: {result.get('shared_win_rate', 0):.1%}")
    else:
        print(f"❌ FAILED: {response.status_code}")
        print(response.text)


if __name__ == "__main__":
    print("\n🧠 ADVANCED RL PATTERN MATCHING TEST SUITE")
    print("="*60)
    print("Testing the new intelligent confidence scoring system")
    print("that learns from 6,880+ signal experiences!")
    
    try:
        # Run tests
        test_get_confidence()
        test_should_take_signal()
        test_save_trade_with_context()
        
        print("\n" + "="*60)
        print("✅ ALL TESTS COMPLETED!")
        print("="*60)
        
    except Exception as e:
        print(f"\n❌ TEST SUITE FAILED: {e}")
        import traceback
        traceback.print_exc()

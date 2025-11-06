#!/usr/bin/env python3
"""
Test GUI to Bot Settings Integration
=====================================
Verifies that all GUI settings are properly loaded and used by the bot.
"""

import os
import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent / "src"))

def test_env_variables_loaded():
    """Test that config.py properly loads environment variables."""
    print("\n" + "="*60)
    print("TEST 1: Environment Variable Loading")
    print("="*60)
    
    # Set test environment variables
    test_vars = {
        "BOT_CONFIDENCE_THRESHOLD": "75.0",
        "BOT_DYNAMIC_CONFIDENCE": "true",
        "BOT_DYNAMIC_CONTRACTS": "true",
        "BOT_TRAILING_DRAWDOWN": "true",
        "BOT_RECOVERY_MODE": "false",
        "BOT_MAX_DRAWDOWN_PERCENT": "8.0",
        "BOT_MAX_CONTRACTS": "3",
        "BOT_DAILY_LOSS_LIMIT": "2000.0",
    }
    
    for key, value in test_vars.items():
        os.environ[key] = value
    
    # Load config
    from config import load_from_env
    config = load_from_env()
    
    # Test conversions
    print(f"\n✓ Testing confidence threshold conversion...")
    assert config.rl_confidence_threshold == 0.75, f"Expected 0.75, got {config.rl_confidence_threshold}"
    print(f"  BOT_CONFIDENCE_THRESHOLD=75.0 → rl_confidence_threshold={config.rl_confidence_threshold} ✓")
    
    print(f"\n✓ Testing boolean conversions...")
    assert config.dynamic_confidence == True, f"Expected True, got {config.dynamic_confidence}"
    print(f"  BOT_DYNAMIC_CONFIDENCE=true → dynamic_confidence={config.dynamic_confidence} ✓")
    
    assert config.dynamic_contracts == True, f"Expected True, got {config.dynamic_contracts}"
    print(f"  BOT_DYNAMIC_CONTRACTS=true → dynamic_contracts={config.dynamic_contracts} ✓")
    
    assert config.trailing_drawdown == True, f"Expected True, got {config.trailing_drawdown}"
    print(f"  BOT_TRAILING_DRAWDOWN=true → trailing_drawdown={config.trailing_drawdown} ✓")
    
    assert config.recovery_mode == False, f"Expected False, got {config.recovery_mode}"
    print(f"  BOT_RECOVERY_MODE=false → recovery_mode={config.recovery_mode} ✓")
    
    print(f"\n✓ Testing numeric conversions...")
    assert config.max_drawdown_percent == 8.0, f"Expected 8.0, got {config.max_drawdown_percent}"
    print(f"  BOT_MAX_DRAWDOWN_PERCENT=8.0 → max_drawdown_percent={config.max_drawdown_percent} ✓")
    
    assert config.max_contracts == 3, f"Expected 3, got {config.max_contracts}"
    print(f"  BOT_MAX_CONTRACTS=3 → max_contracts={config.max_contracts} ✓")
    
    assert config.daily_loss_limit == 2000.0, f"Expected 2000.0, got {config.daily_loss_limit}"
    print(f"  BOT_DAILY_LOSS_LIMIT=2000.0 → daily_loss_limit={config.daily_loss_limit} ✓")
    
    print(f"\n✅ ALL ENVIRONMENT VARIABLE TESTS PASSED")
    return True

def test_config_to_dict():
    """Test that config.to_dict() includes all new fields."""
    print("\n" + "="*60)
    print("TEST 2: Config Dictionary Conversion")
    print("="*60)
    
    from config import BotConfiguration
    config = BotConfiguration()
    config.dynamic_confidence = True
    config.dynamic_contracts = True
    config.trailing_drawdown = True
    config.recovery_mode = False
    config.rl_confidence_threshold = 0.75
    
    config_dict = config.to_dict()
    
    print(f"\n✓ Checking dictionary keys...")
    required_keys = [
        "dynamic_confidence",
        "dynamic_contracts", 
        "trailing_drawdown",
        "recovery_mode",
        "rl_confidence_threshold"
    ]
    
    for key in required_keys:
        assert key in config_dict, f"Missing key: {key}"
        print(f"  '{key}': {config_dict[key]} ✓")
    
    print(f"\n✅ ALL DICTIONARY CONVERSION TESTS PASSED")
    return True

def test_bot_uses_config():
    """Test that bot logic checks CONFIG for dynamic features."""
    print("\n" + "="*60)
    print("TEST 3: Bot Logic Integration")
    print("="*60)
    
    # We can't run the full bot, but we can check the code
    bot_file = Path(__file__).parent / "src" / "vwap_bounce_bot.py"
    with open(bot_file, 'r') as f:
        bot_code = f.read()
    
    print(f"\n✓ Checking for dynamic_contracts usage...")
    assert 'CONFIG.get("dynamic_contracts"' in bot_code, "Bot doesn't check dynamic_contracts"
    print(f"  Bot checks CONFIG.get('dynamic_contracts') ✓")
    
    print(f"\n✓ Checking for dynamic_confidence usage...")
    assert 'CONFIG.get("dynamic_confidence"' in bot_code, "Bot doesn't check dynamic_confidence"
    print(f"  Bot checks CONFIG.get('dynamic_confidence') ✓")
    
    print(f"\n✓ Checking for recovery_mode usage...")
    assert 'CONFIG.get("recovery_mode"' in bot_code, "Bot doesn't check recovery_mode"
    print(f"  Bot checks CONFIG.get('recovery_mode') ✓")
    
    print(f"\n✅ ALL BOT LOGIC INTEGRATION TESTS PASSED")
    return True

def test_percentage_conversion():
    """Test percentage to decimal conversion for confidence threshold."""
    print("\n" + "="*60)
    print("TEST 4: Percentage Conversion Logic")
    print("="*60)
    
    # Test that values > 1 are treated as percentages
    test_cases = [
        ("50.0", 0.50, "50% → 0.50"),
        ("75.0", 0.75, "75% → 0.75"),
        ("100.0", 1.0, "100% → 1.0"),
        ("0.5", 0.5, "0.5 (already decimal) → 0.5"),
        ("0.75", 0.75, "0.75 (already decimal) → 0.75"),
    ]
    
    from config import load_from_env
    
    for env_val, expected, description in test_cases:
        os.environ["BOT_CONFIDENCE_THRESHOLD"] = env_val
        config = load_from_env()
        assert abs(config.rl_confidence_threshold - expected) < 0.001, \
            f"Failed: {description}, got {config.rl_confidence_threshold}"
        print(f"  ✓ {description}")
    
    print(f"\n✅ ALL PERCENTAGE CONVERSION TESTS PASSED")
    return True

def main():
    """Run all tests."""
    print("\n" + "="*60)
    print("GUI TO BOT SETTINGS INTEGRATION TEST SUITE")
    print("="*60)
    
    try:
        # Run all tests
        test_env_variables_loaded()
        test_config_to_dict()
        test_bot_uses_config()
        test_percentage_conversion()
        
        # Summary
        print("\n" + "="*60)
        print("TEST SUMMARY")
        print("="*60)
        print("✅ ALL TESTS PASSED!")
        print("\nGUI settings are properly:")
        print("  • Loaded from environment variables")
        print("  • Converted to correct data types")
        print("  • Included in config dictionary")
        print("  • Used by bot logic")
        print("\nIntegration is working correctly! 🎉")
        print("="*60)
        
        return 0
    
    except AssertionError as e:
        print(f"\n❌ TEST FAILED: {e}")
        return 1
    except Exception as e:
        print(f"\n❌ ERROR: {e}")
        import traceback
        traceback.print_exc()
        return 1

if __name__ == "__main__":
    sys.exit(main())

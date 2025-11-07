#!/usr/bin/env python3
"""
Test Recovery Mode Behavior
============================
Verifies that recovery mode correctly controls trading behavior based on daily loss limit.
"""

import sys
from pathlib import Path

# Add src directory to path
sys.path.insert(0, str(Path(__file__).parent / "src"))

def test_recovery_mode_enabled():
    """Test that bot continues trading when recovery mode is enabled."""
    print("=" * 80)
    print("TEST: Recovery Mode ENABLED - Bot Should Continue Trading")
    print("=" * 80)
    
    from session_state import SessionStateManager
    
    session = SessionStateManager()
    
    # Simulate approaching daily loss limit (85%)
    session.update_trading_state(
        starting_equity=50000.0,
        current_equity=48300.0,  # Lost $1,700
        daily_pnl=-1700.0,       # 85% of $2000 limit
        daily_trades=5,
        broker="TopStep",
        account_type="prop_firm"
    )
    
    warnings, recommendations, smart_settings = session.check_warnings_and_recommendations(
        account_size=50000.0,
        daily_loss_limit=2000.0,
        current_confidence=65.0,
        max_contracts=3,
        recovery_mode_enabled=True  # ENABLED
    )
    
    print("\n✅ RECOVERY MODE = ENABLED (recovery_mode_enabled=True)")
    print("-" * 80)
    print("Expected Behavior: Bot CONTINUES trading with higher confidence")
    print(f"Actual State: in_recovery_mode = {session.state.get('in_recovery_mode')}")
    print(f"Approaching Failure: {session.state.get('approaching_failure')}")
    
    if warnings:
        print("\nWarnings (bot is aware but still trading):")
        for warning in warnings:
            print(f"  [{warning['level'].upper()}] {warning['message']}")
    
    if recommendations:
        print("\nRecommendations (suggests enabling recovery features):")
        for rec in recommendations[:3]:  # Show first 3
            print(f"  [{rec['priority'].upper()}] {rec['message']}")
    
    # Verify recovery mode is active
    assert session.state.get('in_recovery_mode') == True, "Recovery mode should be active"
    assert session.state.get('approaching_failure') == True, "Should be approaching failure"
    
    print("\n✅ PASS: Recovery mode enabled correctly - bot continues trading")
    return True

def test_recovery_mode_disabled():
    """Test that bot stops trading when recovery mode is disabled."""
    print("\n" + "=" * 80)
    print("TEST: Recovery Mode DISABLED - Bot Should Stop Trading")
    print("=" * 80)
    
    from session_state import SessionStateManager
    
    session = SessionStateManager()
    
    # Simulate approaching daily loss limit (85%)
    session.update_trading_state(
        starting_equity=50000.0,
        current_equity=48300.0,  # Lost $1,700
        daily_pnl=-1700.0,       # 85% of $2000 limit
        daily_trades=5,
        broker="TopStep",
        account_type="prop_firm"
    )
    
    warnings, recommendations, smart_settings = session.check_warnings_and_recommendations(
        account_size=50000.0,
        daily_loss_limit=2000.0,
        current_confidence=65.0,
        max_contracts=3,
        recovery_mode_enabled=False  # DISABLED
    )
    
    print("\n✅ RECOVERY MODE = DISABLED (recovery_mode_enabled=False)")
    print("-" * 80)
    print("Expected Behavior: Bot STOPS trading when approaching limit")
    print(f"Actual State: in_recovery_mode = {session.state.get('in_recovery_mode')}")
    print(f"Approaching Failure: {session.state.get('approaching_failure')}")
    
    if warnings:
        print("\nWarnings (bot warns user to enable recovery mode):")
        for warning in warnings:
            print(f"  [{warning['level'].upper()}] {warning['message']}")
    
    if recommendations:
        print("\nRecommendations (suggests enabling recovery mode):")
        for rec in recommendations[:3]:  # Show first 3
            print(f"  [{rec['priority'].upper()}] {rec['message']}")
    
    # Verify recovery mode is NOT active
    assert session.state.get('in_recovery_mode') == False, "Recovery mode should NOT be active"
    assert session.state.get('approaching_failure') == True, "Should be approaching failure"
    
    # Check for recommendation to enable recovery mode
    has_recovery_recommendation = any(
        'Recovery Mode' in rec.get('message', '') 
        for rec in recommendations
    )
    assert has_recovery_recommendation, "Should recommend enabling recovery mode"
    
    print("\n✅ PASS: Recovery mode disabled correctly - bot stops trading")
    return True

def test_safe_zone():
    """Test that bot trades normally when not approaching limits."""
    print("\n" + "=" * 80)
    print("TEST: Safe Zone - Bot Should Trade Normally")
    print("=" * 80)
    
    from session_state import SessionStateManager
    
    session = SessionStateManager()
    
    # Simulate safe zone (only 30% of daily loss limit)
    session.update_trading_state(
        starting_equity=50000.0,
        current_equity=49400.0,  # Lost $600
        daily_pnl=-600.0,        # 30% of $2000 limit
        daily_trades=2,
        broker="TopStep",
        account_type="prop_firm"
    )
    
    warnings, recommendations, smart_settings = session.check_warnings_and_recommendations(
        account_size=50000.0,
        daily_loss_limit=2000.0,
        current_confidence=65.0,
        max_contracts=3,
        recovery_mode_enabled=False  # Doesn't matter in safe zone
    )
    
    print("\n✅ SAFE ZONE (only 30% of daily loss limit)")
    print("-" * 80)
    print("Expected Behavior: Bot trades normally, no restrictions")
    print(f"Actual State: in_recovery_mode = {session.state.get('in_recovery_mode')}")
    print(f"Approaching Failure: {session.state.get('approaching_failure')}")
    
    # Verify not approaching failure
    assert session.state.get('approaching_failure') == False, "Should NOT be approaching failure"
    
    # Should have minimal warnings (just info about current loss)
    critical_warnings = [w for w in warnings if w.get('level') == 'critical']
    assert len(critical_warnings) == 0, "Should have no critical warnings in safe zone"
    
    print("\n✅ PASS: Safe zone behavior correct - bot trades normally")
    return True

def main():
    """Run all recovery mode tests."""
    print("\n" + "=" * 80)
    print("RECOVERY MODE BEHAVIOR TEST SUITE")
    print("=" * 80)
    print("\nVerifying recovery mode correctly controls trading behavior:\n")
    print("1. Recovery Mode ON  → Bot continues trading")
    print("2. Recovery Mode OFF → Bot stops trading after limit")
    print("3. Safe Zone        → Bot trades normally")
    
    results = []
    
    try:
        results.append(("Recovery Mode Enabled", test_recovery_mode_enabled()))
    except Exception as e:
        print(f"\n❌ FAIL: {e}")
        results.append(("Recovery Mode Enabled", False))
    
    try:
        results.append(("Recovery Mode Disabled", test_recovery_mode_disabled()))
    except Exception as e:
        print(f"\n❌ FAIL: {e}")
        results.append(("Recovery Mode Disabled", False))
    
    try:
        results.append(("Safe Zone", test_safe_zone()))
    except Exception as e:
        print(f"\n❌ FAIL: {e}")
        results.append(("Safe Zone", False))
    
    # Print summary
    print("\n" + "=" * 80)
    print("TEST SUMMARY")
    print("=" * 80)
    
    passed = sum(1 for _, result in results if result)
    total = len(results)
    
    for test_name, result in results:
        status = "✅ PASS" if result else "❌ FAIL"
        print(f"{status:10s} {test_name}")
    
    print()
    print(f"Results: {passed}/{total} tests passed")
    
    if passed == total:
        print("\n🎉 ALL TESTS PASSED! Recovery mode behavior is correct.")
        print("\nSummary:")
        print("  ✅ Recovery mode ON  → Bot continues trading with high confidence")
        print("  ✅ Recovery mode OFF → Bot stops trading when approaching limit")
        print("  ✅ Safe zone        → Bot trades normally")
        return 0
    else:
        print(f"\n⚠️  {total - passed} test(s) failed.")
        return 1

if __name__ == "__main__":
    sys.exit(main())

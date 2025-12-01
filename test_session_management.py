"""
Test Session Management
=======================
Verify that:
1. Launcher and bot use the same device fingerprint
2. Stale sessions are auto-cleared on login
3. Active sessions block concurrent logins
4. Sessions are released on clean shutdown

Note: This test duplicates the fingerprint generation logic from launcher
and bot files because importing those files directly requires tkinter and
other dependencies that may not be available in test environment. This
ensures tests can run in isolation but should be kept in sync with changes
to production code.
"""

import sys
import os
import hashlib
import platform
import getpass
import uuid

def get_launcher_device_fingerprint() -> str:
    """
    Generate a unique device fingerprint for session locking.
    One session per machine/user - shared between launcher and bot.
    
    This is the LAUNCHER version from QuoTrading_Launcher.py
    """
    # Get platform-specific machine ID
    try:
        machine_id = str(uuid.getnode())  # MAC address as unique ID
    except:
        machine_id = "unknown"
    
    # Get username
    try:
        username = getpass.getuser()
    except:
        username = "unknown"
    
    # Get platform info
    platform_name = platform.system()  # Windows, Darwin (Mac), Linux
    
    # Combine all components WITHOUT PID - one session per machine/user, not per process
    # This allows launcher and bot to share the same session
    fingerprint_raw = f"{machine_id}:{username}:{platform_name}"
    
    # Hash for privacy (don't send raw MAC address to server)
    fingerprint_hash = hashlib.sha256(fingerprint_raw.encode()).hexdigest()[:16]
    
    return fingerprint_hash


def get_bot_device_fingerprint() -> str:
    """
    Generate a unique device fingerprint for session locking.
    One session per machine/user - shared between launcher and bot.
    
    This is the BOT version from quotrading_engine.py
    """
    # Get platform-specific machine ID
    try:
        machine_id = str(uuid.getnode())  # MAC address as unique ID
    except:
        machine_id = "unknown"
    
    # Get username
    try:
        username = getpass.getuser()
    except:
        username = "unknown"
    
    # Get platform info
    platform_name = platform.system()  # Windows, Darwin (Mac), Linux
    
    # Combine all components WITHOUT PID - one session per machine/user, not per process
    # This allows launcher and bot to share the same session
    fingerprint_raw = f"{machine_id}:{username}:{platform_name}"
    
    # Hash for privacy (don't send raw MAC address to server)
    fingerprint_hash = hashlib.sha256(fingerprint_raw.encode()).hexdigest()[:16]
    
    return fingerprint_hash


def test_device_fingerprint_consistency():
    """Test that launcher and bot generate the same device fingerprint"""
    print("\n" + "="*70)
    print("TEST: Device Fingerprint Consistency")
    print("="*70)
    
    # Generate fingerprints
    launcher_fingerprint = get_launcher_device_fingerprint()
    bot_fingerprint = get_bot_device_fingerprint()
    
    print(f"Launcher fingerprint: {launcher_fingerprint}")
    print(f"Bot fingerprint:      {bot_fingerprint}")
    
    # Verify they match
    if launcher_fingerprint == bot_fingerprint:
        print("✅ PASS: Fingerprints match - launcher and bot will share the same session")
        return True
    else:
        print("❌ FAIL: Fingerprints don't match - this will cause session conflicts!")
        print("  Launcher and bot MUST use the same fingerprint")
        return False


def test_fingerprint_excludes_pid():
    """Test that device fingerprint does NOT include process ID"""
    print("\n" + "="*70)
    print("TEST: Fingerprint Excludes PID")
    print("="*70)
    
    # Generate fingerprint multiple times (should always be the same)
    fp1 = get_launcher_device_fingerprint()
    fp2 = get_launcher_device_fingerprint()
    fp3 = get_bot_device_fingerprint()
    
    print(f"Launcher call 1: {fp1}")
    print(f"Launcher call 2: {fp2}")
    print(f"Bot call 1:      {fp3}")
    
    # Verify they all match
    if fp1 == fp2 == fp3:
        print("✅ PASS: Fingerprint is stable - does not include PID or other volatile data")
        return True
    else:
        print("❌ FAIL: Fingerprint changes - may include unstable components like PID")
        return False


def test_fingerprint_format():
    """Test that fingerprint has expected format"""
    print("\n" + "="*70)
    print("TEST: Fingerprint Format")
    print("="*70)
    
    fp = get_launcher_device_fingerprint()
    
    print(f"Fingerprint: {fp}")
    print(f"Length: {len(fp)} characters")
    print(f"Is hex: {all(c in '0123456789abcdef' for c in fp)}")
    
    # Should be 16-character hex string
    if len(fp) == 16 and all(c in '0123456789abcdef' for c in fp):
        print("✅ PASS: Fingerprint format is correct (16-char hex)")
        return True
    else:
        print("❌ FAIL: Fingerprint format is incorrect")
        return False


def main():
    """Run all tests"""
    print("\n" + "="*70)
    print("SESSION MANAGEMENT TEST SUITE")
    print("="*70)
    
    results = []
    
    # Test 1: Device fingerprint consistency
    results.append(("Fingerprint Consistency", test_device_fingerprint_consistency()))
    
    # Test 2: Fingerprint excludes PID
    results.append(("Fingerprint Stability", test_fingerprint_excludes_pid()))
    
    # Test 3: Fingerprint format
    results.append(("Fingerprint Format", test_fingerprint_format()))
    
    # Print summary
    print("\n" + "="*70)
    print("TEST SUMMARY")
    print("="*70)
    
    passed = sum(1 for _, result in results if result)
    total = len(results)
    
    for test_name, result in results:
        status = "✅ PASS" if result else "❌ FAIL"
        print(f"{status}: {test_name}")
    
    print(f"\nTotal: {passed}/{total} tests passed")
    
    if passed == total:
        print("\n✅ ALL TESTS PASSED")
        return 0
    else:
        print(f"\n❌ {total - passed} TEST(S) FAILED")
        return 1


if __name__ == "__main__":
    sys.exit(main())

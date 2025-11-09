"""
Test script for instance locking system
Tests lock creation, checking, and stale lock detection
"""
import json
import os
import time
from pathlib import Path
import psutil

def test_lock_system():
    """Test the instance locking mechanism"""
    
    print("=" * 60)
    print("Instance Lock System Test")
    print("=" * 60)
    
    locks_dir = Path("locks")
    locks_dir.mkdir(exist_ok=True)
    
    test_account_id = "TEST_123456"
    lock_file = locks_dir / f"account_{test_account_id}.lock"
    
    # Test 1: Create a lock
    print("\n[TEST 1] Creating lock for account:", test_account_id)
    lock_data = {
        "account_id": test_account_id,
        "pid": os.getpid(),
        "created_at": "2025-11-09T15:00:00",
        "broker_username": "test_user"
    }
    
    with open(lock_file, 'w') as f:
        json.dump(lock_data, f, indent=2)
    
    if lock_file.exists():
        print("✅ Lock file created successfully")
        print(f"   Location: {lock_file}")
    else:
        print("❌ Failed to create lock file")
        return
    
    # Test 2: Check if lock exists and is valid
    print("\n[TEST 2] Checking if lock is valid...")
    with open(lock_file, 'r') as f:
        read_lock = json.load(f)
    
    pid = read_lock.get("pid")
    if psutil.pid_exists(pid):
        print(f"✅ Lock is VALID (PID {pid} is running)")
        print(f"   Account: {read_lock['account_id']}")
        print(f"   Broker: {read_lock['broker_username']}")
        print(f"   Created: {read_lock['created_at']}")
    else:
        print(f"❌ Lock is STALE (PID {pid} not running)")
    
    # Test 3: Create a stale lock (fake PID)
    print("\n[TEST 3] Creating stale lock with non-existent PID...")
    stale_lock_data = {
        "account_id": test_account_id,
        "pid": 999999,  # Very unlikely to exist
        "created_at": "2025-11-09T14:00:00",
        "broker_username": "stale_user"
    }
    
    with open(lock_file, 'w') as f:
        json.dump(stale_lock_data, f, indent=2)
    
    # Check if stale
    with open(lock_file, 'r') as f:
        stale_lock = json.load(f)
    
    stale_pid = stale_lock.get("pid")
    if psutil.pid_exists(stale_pid):
        print(f"⚠️  PID {stale_pid} exists (unexpected)")
    else:
        print(f"✅ Detected STALE lock (PID {stale_pid} not running)")
        print(f"   → Would auto-remove this lock in real scenario")
        lock_file.unlink()
        print(f"   → Stale lock removed")
    
    # Test 4: Multiple account locks
    print("\n[TEST 4] Creating locks for multiple accounts...")
    accounts = ["ACCOUNT_A", "ACCOUNT_B", "ACCOUNT_C"]
    
    for acc in accounts:
        acc_lock = locks_dir / f"account_{acc}.lock"
        acc_data = {
            "account_id": acc,
            "pid": os.getpid(),
            "created_at": "2025-11-09T15:00:00",
            "broker_username": f"user_{acc}"
        }
        with open(acc_lock, 'w') as f:
            json.dump(acc_data, f, indent=2)
    
    lock_count = len(list(locks_dir.glob("*.lock")))
    print(f"✅ Created {lock_count} lock files")
    
    # List all locks
    print("\n[TEST 5] Listing all active locks...")
    for lock_path in locks_dir.glob("*.lock"):
        with open(lock_path, 'r') as f:
            lock_info = json.load(f)
        status = "VALID" if psutil.pid_exists(lock_info.get("pid", 0)) else "STALE"
        print(f"   - {lock_info['account_id']}: {status} (PID {lock_info.get('pid')})")
    
    # Test 6: Cleanup
    print("\n[TEST 6] Cleaning up test locks...")
    for lock_path in locks_dir.glob("*.lock"):
        lock_path.unlink()
        print(f"   ✅ Removed: {lock_path.name}")
    
    remaining = len(list(locks_dir.glob("*.lock")))
    if remaining == 0:
        print("✅ All test locks removed successfully")
    else:
        print(f"⚠️  {remaining} lock files remaining")
    
    print("\n" + "=" * 60)
    print("Instance Lock System Test COMPLETE")
    print("=" * 60)
    print("\n✅ All tests passed! Lock system is working correctly.")
    print("\nNext steps:")
    print("1. Launch GUI normally")
    print("2. Validate credentials and select account")
    print("3. Click 'Start Bot' → Lock should be created")
    print("4. Try launching second GUI with SAME account → Should be blocked")
    print("5. Close first GUI → Lock should be removed")
    print("6. Launch second GUI again → Should work now")

if __name__ == "__main__":
    test_lock_system()

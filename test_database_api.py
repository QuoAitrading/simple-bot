"""
Test Database and Admin API Endpoints for QuoTrading
Tests user management, license validation, and admin operations
"""

import requests
import json
from datetime import datetime

# Azure API URL
BASE_URL = "https://quotrading-signals.icymeadow-86b2969e.eastus.azurecontainerapps.io"

# Store admin license key (will be set after first run)
ADMIN_LICENSE_KEY = "QT-0149-EA27-38BB-C7A0"  # Replace with your actual admin key

def test_health():
    """Test 1: Health check"""
    print("\n" + "="*60)
    print("TEST 1: Health Check")
    print("="*60)
    
    try:
        response = requests.get(f"{BASE_URL}/health")
        print(f"Status: {response.status_code}")
        print(f"Response: {json.dumps(response.json(), indent=2)}")
        assert response.status_code == 200
        print("✅ Health check PASSED")
        return True
    except Exception as e:
        print(f"❌ Health check FAILED: {e}")
        return False


def test_license_validation_invalid():
    """Test 2: License validation with invalid key"""
    print("\n" + "="*60)
    print("TEST 2: License Validation (Invalid Key)")
    print("="*60)
    
    try:
        response = requests.post(
            f"{BASE_URL}/api/license/validate",
            json={"license_key": "INVALID-KEY-12345"}
        )
        print(f"Status: {response.status_code}")
        print(f"Response: {json.dumps(response.json(), indent=2)}")
        assert response.status_code == 403
        print("✅ Invalid license correctly rejected")
        return True
    except Exception as e:
        print(f"❌ Test FAILED: {e}")
        return False


def test_admin_stats():
    """Test 3: Get admin stats"""
    print("\n" + "="*60)
    print("TEST 3: Admin Stats")
    print("="*60)
    
    try:
        response = requests.get(
            f"{BASE_URL}/api/admin/stats",
            params={"license_key": ADMIN_LICENSE_KEY}
        )
        print(f"Status: {response.status_code}")
        data = response.json()
        print(f"Response: {json.dumps(data, indent=2)}")
        
        if response.status_code == 200:
            print(f"\n📊 System Stats:")
            print(f"   Total Users: {data['users']['total']}")
            print(f"   Active Users: {data['users']['active']}")
            print(f"   API Calls (24h): {data['api_calls_24h']}")
            print(f"   Total Trades: {data['trades']['total']}")
            print("✅ Admin stats retrieved successfully")
            return True
        else:
            print(f"❌ Failed to get admin stats (check ADMIN_LICENSE_KEY)")
            return False
    except Exception as e:
        print(f"❌ Test FAILED: {e}")
        return False


def test_get_all_users():
    """Test 4: Get all users"""
    print("\n" + "="*60)
    print("TEST 4: Get All Users")
    print("="*60)
    
    try:
        response = requests.get(
            f"{BASE_URL}/api/admin/users",
            params={"license_key": ADMIN_LICENSE_KEY}
        )
        print(f"Status: {response.status_code}")
        data = response.json()
        
        if response.status_code == 200:
            print(f"\n👥 Total Users: {data['total_users']}")
            for user in data['users']:
                print(f"\n   Account: {user['account_id']}")
                print(f"   Email: {user['email']}")
                print(f"   License: {user['license_type']} - {user['license_status']}")
                print(f"   Key: {user['license_key']}")
                if user['license_expiration']:
                    print(f"   Expires: {user['license_expiration']}")
            print("\n✅ Users retrieved successfully")
            return True
        else:
            print(f"❌ Failed to get users (check ADMIN_LICENSE_KEY)")
            print(f"Response: {json.dumps(data, indent=2)}")
            return False
    except Exception as e:
        print(f"❌ Test FAILED: {e}")
        return False


def test_add_user():
    """Test 5: Add a new user"""
    print("\n" + "="*60)
    print("TEST 5: Add New User")
    print("="*60)
    
    new_user_id = f"TEST-{datetime.now().strftime('%Y%m%d-%H%M%S')}"
    
    try:
        response = requests.post(
            f"{BASE_URL}/api/admin/add-user",
            params={
                "license_key": ADMIN_LICENSE_KEY,
                "account_id": new_user_id,
                "email": f"{new_user_id.lower()}@test.com",
                "license_type": "BETA",
                "license_duration_days": 90,
                "notes": "Automated test user"
            }
        )
        print(f"Status: {response.status_code}")
        data = response.json()
        print(f"Response: {json.dumps(data, indent=2)}")
        
        if response.status_code == 200:
            print(f"\n✅ User created successfully!")
            print(f"   Account ID: {data['user']['account_id']}")
            print(f"   License Key: {data['user']['license_key']}")
            print(f"   Expires: {data['user']['license_expiration']}")
            return data['user']['license_key']  # Return for next tests
        else:
            print(f"❌ Failed to create user")
            return None
    except Exception as e:
        print(f"❌ Test FAILED: {e}")
        return None


def test_validate_new_user_license(user_license_key):
    """Test 6: Validate newly created user's license"""
    print("\n" + "="*60)
    print("TEST 6: Validate New User License")
    print("="*60)
    
    if not user_license_key:
        print("⚠️  Skipping - no user license key from previous test")
        return False
    
    try:
        response = requests.post(
            f"{BASE_URL}/api/license/validate",
            json={"license_key": user_license_key}
        )
        print(f"Status: {response.status_code}")
        data = response.json()
        print(f"Response: {json.dumps(data, indent=2)}")
        
        if response.status_code == 200 and data.get('valid'):
            print("✅ New user license is valid!")
            return True
        else:
            print("❌ License validation failed")
            return False
    except Exception as e:
        print(f"❌ Test FAILED: {e}")
        return False


def test_rate_limiting():
    """Test 7: Rate limiting still works"""
    print("\n" + "="*60)
    print("TEST 7: Rate Limiting")
    print("="*60)
    
    try:
        response = requests.get(f"{BASE_URL}/api/rate-limit/status")
        print(f"Status: {response.status_code}")
        data = response.json()
        print(f"Response: {json.dumps(data, indent=2)}")
        
        if response.status_code == 200:
            print(f"\n⏱️  Rate Limit Status:")
            print(f"   Requests Used: {data.get('requests_made', data.get('requests_used', 0))}")
            print(f"   Requests Remaining: {data.get('requests_remaining', 0)}")
            print(f"   Blocked: {data.get('blocked', False)}")
            print("✅ Rate limiting operational")
            return True
        else:
            print("❌ Rate limit check failed")
            return False
    except Exception as e:
        print(f"❌ Test FAILED: {e}")
        return False


def test_calendar_endpoints():
    """Test 8: Calendar endpoints still work"""
    print("\n" + "="*60)
    print("TEST 8: Economic Calendar")
    print("="*60)
    
    try:
        response = requests.get(f"{BASE_URL}/api/calendar/today")
        print(f"Status: {response.status_code}")
        data = response.json()
        
        if response.status_code == 200:
            print(f"Date: {data.get('date', 'N/A')}")
            print(f"Events Count: {data.get('count', 0)}")
            print(f"Trading Recommended: {data.get('trading_recommended', True)}")
            print("✅ Calendar endpoint working")
            return True
        else:
            print("❌ Calendar check failed")
            return False
    except Exception as e:
        print(f"❌ Test FAILED: {e}")
        return False


def main():
    """Run all tests"""
    print("\n" + "="*70)
    print("  QuoTrading Database & Admin API Test Suite")
    print("="*70)
    print(f"Testing: {BASE_URL}")
    print(f"Admin Key: {ADMIN_LICENSE_KEY}")
    print("="*70)
    
    results = []
    
    # Run tests
    results.append(("Health Check", test_health()))
    results.append(("Invalid License", test_license_validation_invalid()))
    results.append(("Admin Stats", test_admin_stats()))
    results.append(("Get All Users", test_get_all_users()))
    
    # Create and validate new user
    new_user_key = test_add_user()
    results.append(("Add New User", new_user_key is not None))
    results.append(("Validate New User", test_validate_new_user_license(new_user_key)))
    
    # Test other features still work
    results.append(("Rate Limiting", test_rate_limiting()))
    results.append(("Calendar API", test_calendar_endpoints()))
    
    # Print summary
    print("\n" + "="*70)
    print("  TEST SUMMARY")
    print("="*70)
    
    passed = sum(1 for _, result in results if result)
    total = len(results)
    
    for test_name, result in results:
        status = "✅ PASS" if result else "❌ FAIL"
        print(f"{test_name:.<50} {status}")
    
    print("="*70)
    print(f"Results: {passed}/{total} tests passed ({passed/total*100:.0f}%)")
    print("="*70)
    
    if passed == total:
        print("\n🎉 All tests passed! Database & Admin API fully operational!")
    else:
        print(f"\n⚠️  {total - passed} test(s) failed. Check output above for details.")
    
    print("\n📝 Note: If admin tests failed, update ADMIN_LICENSE_KEY in this script")
    print("   Get your admin key from the database initialization output.")


if __name__ == "__main__":
    main()

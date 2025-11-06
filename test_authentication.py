#!/usr/bin/env python3
"""
Test script for QuoTrading Cloud Authentication System
Validates that all components are working correctly
"""

import requests
import json
import sys

def test_server_health():
    """Test if server is running."""
    print("Testing server health...")
    try:
        response = requests.get("http://localhost:5000/api/health", timeout=5)
        if response.status_code == 200:
            print("✅ Server is healthy")
            return True
        else:
            print(f"❌ Server returned status code: {response.status_code}")
            return False
    except requests.exceptions.ConnectionError:
        print("❌ Cannot connect to server. Is it running?")
        print("   Run: python validation_server.py")
        return False
    except Exception as e:
        print(f"❌ Error: {e}")
        return False

def test_valid_credentials():
    """Test login with valid credentials."""
    print("\nTesting valid credentials (demo_user)...")
    try:
        response = requests.post(
            "http://localhost:5000/api/validate",
            json={
                "username": "demo_user",
                "password": "demo_password",
                "api_key": "DEMO_API_KEY_12345"
            },
            timeout=5
        )
        
        data = response.json()
        if data.get("valid"):
            print("✅ Valid credentials accepted")
            print(f"   User data: {data.get('user_data')}")
            return True
        else:
            print(f"❌ Credentials rejected: {data.get('message')}")
            return False
    except Exception as e:
        print(f"❌ Error: {e}")
        return False

def test_invalid_password():
    """Test login with invalid password."""
    print("\nTesting invalid password...")
    try:
        response = requests.post(
            "http://localhost:5000/api/validate",
            json={
                "username": "demo_user",
                "password": "wrong_password",
                "api_key": "DEMO_API_KEY_12345"
            },
            timeout=5
        )
        
        data = response.json()
        if not data.get("valid"):
            print("✅ Invalid password correctly rejected")
            print(f"   Message: {data.get('message')}")
            return True
        else:
            print("❌ Invalid password was accepted!")
            return False
    except Exception as e:
        print(f"❌ Error: {e}")
        return False

def test_invalid_api_key():
    """Test login with invalid API key."""
    print("\nTesting invalid API key...")
    try:
        response = requests.post(
            "http://localhost:5000/api/validate",
            json={
                "username": "demo_user",
                "password": "demo_password",
                "api_key": "WRONG_KEY"
            },
            timeout=5
        )
        
        data = response.json()
        if not data.get("valid"):
            print("✅ Invalid API key correctly rejected")
            print(f"   Message: {data.get('message')}")
            return True
        else:
            print("❌ Invalid API key was accepted!")
            return False
    except Exception as e:
        print(f"❌ Error: {e}")
        return False

def test_missing_fields():
    """Test login with missing fields."""
    print("\nTesting missing fields...")
    try:
        response = requests.post(
            "http://localhost:5000/api/validate",
            json={
                "username": "demo_user",
                "password": "demo_password"
                # API key missing
            },
            timeout=5
        )
        
        data = response.json()
        if not data.get("valid"):
            print("✅ Missing fields correctly rejected")
            print(f"   Message: {data.get('message')}")
            return True
        else:
            print("❌ Missing fields were accepted!")
            return False
    except Exception as e:
        print(f"❌ Error: {e}")
        return False

def main():
    """Run all tests."""
    print("="*60)
    print("QuoTrading Cloud Authentication - Test Suite")
    print("="*60)
    
    results = []
    
    # Test 1: Server health
    results.append(("Server Health", test_server_health()))
    
    if not results[0][1]:
        print("\n" + "="*60)
        print("Server is not running. Please start it first:")
        print("  python validation_server.py")
        print("="*60)
        sys.exit(1)
    
    # Test 2: Valid credentials
    results.append(("Valid Credentials", test_valid_credentials()))
    
    # Test 3: Invalid password
    results.append(("Invalid Password", test_invalid_password()))
    
    # Test 4: Invalid API key
    results.append(("Invalid API Key", test_invalid_api_key()))
    
    # Test 5: Missing fields
    results.append(("Missing Fields", test_missing_fields()))
    
    # Summary
    print("\n" + "="*60)
    print("Test Summary")
    print("="*60)
    
    passed = sum(1 for _, result in results if result)
    total = len(results)
    
    for test_name, result in results:
        status = "✅ PASS" if result else "❌ FAIL"
        print(f"{status} - {test_name}")
    
    print("="*60)
    print(f"Results: {passed}/{total} tests passed")
    print("="*60)
    
    if passed == total:
        print("\n🎉 All tests passed! System is ready to use.")
        print("\nNext steps:")
        print("1. Run the GUI: python customer/QuoTrading_Launcher.py")
        print("2. Login with demo_user / demo_password / DEMO_API_KEY_12345")
        return 0
    else:
        print("\n⚠️  Some tests failed. Please check the errors above.")
        return 1

if __name__ == "__main__":
    sys.exit(main())

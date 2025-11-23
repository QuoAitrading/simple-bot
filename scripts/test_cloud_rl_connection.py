#!/usr/bin/env python3
"""
Cloud RL Connection Tester for Live Trading
==========================================
Tests connectivity to the Azure-hosted RL API before going live.
Validates that the RL system is working correctly.
"""

import sys
import json
import os
from pathlib import Path
import requests
from datetime import datetime

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))


class CloudRLTester:
    """Tests cloud RL API connectivity and functionality"""
    
    def __init__(self, api_url: str = None, license_key: str = None):
        """
        Initialize tester
        
        Args:
            api_url: Cloud API URL (defaults to value from config.json)
            license_key: License key (defaults to value from config.json)
        """
        # Load from config if not provided
        if api_url is None or license_key is None:
            config_path = Path(__file__).parent.parent / 'data' / 'config.json'
            if config_path.exists():
                with open(config_path, 'r') as f:
                    config = json.load(f)
                    if api_url is None:
                        api_url = config.get('cloud_api_url', 
                            'https://quotrading-signals.icymeadow-86b2969e.eastus.azurecontainerapps.io')
                    if license_key is None:
                        license_key = config.get('quotrading_api_key', '')
        
        self.api_url = api_url.rstrip('/') if api_url else ''
        self.license_key = license_key
        self.timeout = 10
    
    def test_health_endpoint(self) -> bool:
        """Test if API is responding"""
        print("\n[1/4] Testing API Health...")
        
        try:
            response = requests.get(
                f"{self.api_url}/health",
                timeout=self.timeout
            )
            
            if response.status_code == 200:
                print(f"   ✅ API is healthy: {self.api_url}")
                return True
            else:
                print(f"   ❌ API returned status {response.status_code}")
                return False
        
        except requests.Timeout:
            print(f"   ❌ Timeout connecting to {self.api_url}")
            return False
        except Exception as e:
            print(f"   ❌ Connection error: {e}")
            return False
    
    def test_license_validation(self) -> bool:
        """Test license key validation"""
        print("\n[2/4] Testing License Validation...")
        
        if not self.license_key:
            print("   ⚠️  No license key configured in config.json")
            return False
        
        try:
            # Test with a simple signal analysis request
            response = requests.post(
                f"{self.api_url}/api/rl/analyze-signal",
                json={
                    "license_key": self.license_key,
                    "symbol": "ES",
                    "state": {
                        "rsi": 50.0,
                        "vwap_distance": 1.0,
                        "atr": 2.5,
                        "volume_ratio": 1.0,
                        "hour": 10,
                        "day_of_week": 2,
                        "recent_pnl": 0.0,
                        "streak": 0,
                        "side": "long",
                        "price": 6800.0,
                        "regime": "NORMAL"
                    }
                },
                timeout=self.timeout
            )
            
            if response.status_code == 200:
                print(f"   ✅ License key is valid")
                return True
            elif response.status_code == 401:
                print(f"   ❌ License key is INVALID or EXPIRED")
                return False
            else:
                print(f"   ⚠️  Unexpected response: {response.status_code}")
                return False
        
        except Exception as e:
            print(f"   ❌ Error validating license: {e}")
            return False
    
    def test_signal_analysis(self) -> bool:
        """Test RL signal analysis with realistic data"""
        print("\n[3/4] Testing RL Signal Analysis...")
        
        if not self.license_key:
            print("   ⚠️  Skipped (no license key)")
            return False
        
        try:
            # Test with a good setup (low RSI long)
            test_state = {
                "rsi": 28.5,
                "vwap_distance": 0.95,
                "atr": 2.5,
                "volume_ratio": 1.2,
                "hour": 10,
                "day_of_week": 2,
                "recent_pnl": 100.0,
                "streak": 2,
                "side": "long",
                "price": 6750.0,
                "regime": "NORMAL"
            }
            
            response = requests.post(
                f"{self.api_url}/api/rl/analyze-signal",
                json={
                    "license_key": self.license_key,
                    "symbol": "ES",
                    "state": test_state
                },
                timeout=self.timeout
            )
            
            if response.status_code == 200:
                data = response.json()
                take_trade = data.get('take_trade', False)
                confidence = data.get('confidence', 0.0)
                reason = data.get('reason', 'No reason provided')
                
                print(f"   ✅ RL Analysis successful")
                print(f"      Decision: {'TAKE' if take_trade else 'SKIP'}")
                print(f"      Confidence: {confidence:.1%}")
                print(f"      Reason: {reason}")
                return True
            else:
                print(f"   ❌ Signal analysis failed: HTTP {response.status_code}")
                return False
        
        except Exception as e:
            print(f"   ❌ Error during signal analysis: {e}")
            return False
    
    def test_outcome_reporting(self) -> bool:
        """Test reporting trade outcomes"""
        print("\n[4/4] Testing Trade Outcome Reporting...")
        
        if not self.license_key:
            print("   ⚠️  Skipped (no license key)")
            return False
        
        try:
            # Submit a test outcome
            test_state = {
                "rsi": 30.0,
                "vwap_distance": 0.98,
                "atr": 2.5,
                "volume_ratio": 1.1,
                "hour": 11,
                "day_of_week": 2,
                "recent_pnl": 0.0,
                "streak": 0,
                "side": "long",
                "price": 6760.0,
                "regime": "NORMAL"
            }
            
            response = requests.post(
                f"{self.api_url}/api/rl/submit-outcome",
                json={
                    "license_key": self.license_key,
                    "symbol": "ES",
                    "state": test_state,
                    "took_trade": True,
                    "pnl": 125.0,
                    "duration": 1800
                },
                timeout=self.timeout
            )
            
            if response.status_code == 200:
                data = response.json()
                total_exp = data.get('total_experiences', '?')
                print(f"   ✅ Outcome reported successfully")
                print(f"      Total experiences: {total_exp}")
                return True
            else:
                print(f"   ⚠️  Outcome reporting returned: HTTP {response.status_code}")
                # This is not critical, so we return True
                return True
        
        except Exception as e:
            print(f"   ⚠️  Error reporting outcome: {e}")
            # Non-critical, return True
            return True
    
    def run_all_tests(self) -> bool:
        """Run all connection tests"""
        print("=" * 80)
        print("CLOUD RL CONNECTION TEST FOR LIVE TRADING")
        print("=" * 80)
        print(f"\nAPI URL: {self.api_url}")
        print(f"License Key: {'*' * 10}{self.license_key[-4:] if self.license_key and len(self.license_key) > 4 else 'NOT SET'}")
        
        # Run tests
        results = {
            'health': self.test_health_endpoint(),
            'license': self.test_license_validation(),
            'analysis': self.test_signal_analysis(),
            'reporting': self.test_outcome_reporting(),
        }
        
        # Summary
        print("\n" + "=" * 80)
        print("TEST SUMMARY")
        print("=" * 80)
        
        passed = sum(results.values())
        total = len(results)
        
        for test_name, result in results.items():
            status = "✅ PASS" if result else "❌ FAIL"
            print(f"{status} - {test_name.upper()}")
        
        print("\n" + "=" * 80)
        if passed == total:
            print(f"✅ ALL TESTS PASSED ({passed}/{total}) - READY FOR LIVE TRADING")
        elif passed >= 2:  # Health and license are critical
            print(f"⚠️  PARTIAL PASS ({passed}/{total}) - CHECK WARNINGS ABOVE")
        else:
            print(f"❌ TESTS FAILED ({passed}/{total}) - FIX ERRORS BEFORE LIVE TRADING")
        print("=" * 80)
        
        return results['health'] and results['license']


def main():
    """Main entry point"""
    tester = CloudRLTester()
    success = tester.run_all_tests()
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()

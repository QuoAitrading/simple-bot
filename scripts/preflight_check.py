#!/usr/bin/env python3
"""
Pre-Flight Check for Live Trading
=================================
Comprehensive check before starting live trading bot.
Validates:
1. JSON configuration files
2. Cloud RL API connectivity
3. Environment variables
4. Risk management settings
"""

import sys
import os
import json
from pathlib import Path
import subprocess
from typing import Dict, List, Tuple

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))


class PreFlightChecker:
    """Pre-flight checker for live trading"""
    
    def __init__(self, project_root: str = None):
        if project_root is None:
            self.project_root = Path(__file__).parent.parent
        else:
            self.project_root = Path(project_root)
        
        self.config = {}
        self.errors = []
        self.warnings = []
        self.results = {}
    
    def load_config(self) -> bool:
        """Load configuration file"""
        config_path = self.project_root / 'data' / 'config.json'
        
        try:
            with open(config_path, 'r') as f:
                self.config = json.load(f)
            return True
        except Exception as e:
            self.errors.append(f"Failed to load config.json: {e}")
            return False
    
    def check_json_files(self) -> bool:
        """Check all JSON files"""
        print("\n[1/6] Validating JSON Files...")
        
        # Run the JSON validator script
        try:
            result = subprocess.run(
                [sys.executable, str(self.project_root / 'scripts' / 'validate_json_files.py')],
                capture_output=True,
                text=True,
                cwd=str(self.project_root)
            )
            
            if result.returncode == 0:
                print("   ✅ All JSON files are valid")
                return True
            else:
                print("   ❌ JSON validation failed:")
                print(result.stdout)
                self.errors.append("JSON validation failed")
                return False
        except Exception as e:
            print(f"   ❌ Error running JSON validator: {e}")
            self.errors.append(f"JSON validator error: {e}")
            return False
    
    def check_cloud_rl_connection(self) -> bool:
        """Check cloud RL API connection"""
        print("\n[2/6] Testing Cloud RL Connection...")
        
        # Run the cloud RL connection test
        try:
            result = subprocess.run(
                [sys.executable, str(self.project_root / 'scripts' / 'test_cloud_rl_connection.py')],
                capture_output=True,
                text=True,
                cwd=str(self.project_root)
            )
            
            if result.returncode == 0:
                print("   ✅ Cloud RL connection successful")
                return True
            else:
                print("   ❌ Cloud RL connection failed:")
                print(result.stdout)
                self.errors.append("Cloud RL connection failed")
                return False
        except Exception as e:
            print(f"   ⚠️  Could not test cloud RL: {e}")
            self.warnings.append(f"Cloud RL test error: {e}")
            return True  # Non-critical
    
    def check_environment_variables(self) -> bool:
        """Check required environment variables"""
        print("\n[3/6] Checking Environment Variables...")
        
        # Required env vars for production
        required_env_vars = {
            'BOT_ENVIRONMENT': 'production',
            'CONFIRM_LIVE_TRADING': '1',
        }
        
        # Optional but recommended
        recommended_env_vars = [
            'TOPSTEP_API_TOKEN',
            'TOPSTEP_USERNAME',
            'BOT_MAX_CONTRACTS',
        ]
        
        all_ok = True
        
        # Check required
        for var, expected_value in required_env_vars.items():
            actual_value = os.getenv(var, '')
            if actual_value == expected_value:
                print(f"   ✅ {var} = {expected_value}")
            else:
                print(f"   ❌ {var} should be '{expected_value}', got '{actual_value}'")
                self.errors.append(f"{var} not set correctly for live trading")
                all_ok = False
        
        # Check recommended
        for var in recommended_env_vars:
            if os.getenv(var):
                print(f"   ✅ {var} is set")
            else:
                print(f"   ⚠️  {var} is not set (optional)")
                self.warnings.append(f"{var} not configured")
        
        return all_ok
    
    def check_risk_settings(self) -> bool:
        """Validate risk management settings"""
        print("\n[4/6] Validating Risk Settings...")
        
        all_ok = True
        
        # Check max contracts
        max_contracts = self.config.get('max_contracts', 0)
        if max_contracts < 1:
            print(f"   ❌ max_contracts must be >= 1, got {max_contracts}")
            self.errors.append("Invalid max_contracts")
            all_ok = False
        elif max_contracts > 25:
            print(f"   ❌ max_contracts exceeds safety limit (max 25), got {max_contracts}")
            self.errors.append("max_contracts too high")
            all_ok = False
        elif max_contracts > 15:
            print(f"   ⚠️  max_contracts is high ({max_contracts}), ensure adequate account size")
            self.warnings.append("High max_contracts setting")
        else:
            print(f"   ✅ max_contracts: {max_contracts}")
        
        # Check daily loss limit
        daily_loss = self.config.get('daily_loss_limit', 0)
        account_size = self.config.get('account_size', 0)
        
        if daily_loss <= 0:
            print(f"   ❌ daily_loss_limit must be > 0, got {daily_loss}")
            self.errors.append("Invalid daily_loss_limit")
            all_ok = False
        elif account_size > 0:
            loss_pct = (daily_loss / account_size) * 100
            print(f"   ✅ daily_loss_limit: ${daily_loss:.2f} ({loss_pct:.1f}% of account)")
            
            if loss_pct > 5:
                print(f"   ⚠️  Daily loss limit is high ({loss_pct:.1f}% of account)")
                self.warnings.append("High daily loss percentage")
        else:
            print(f"   ✅ daily_loss_limit: ${daily_loss:.2f}")
        
        # Check RL settings
        rl_threshold = self.config.get('rl_confidence_threshold', 0.5)
        if 0.0 <= rl_threshold <= 1.0:
            print(f"   ✅ RL confidence threshold: {rl_threshold:.1%}")
        else:
            print(f"   ❌ RL confidence threshold invalid: {rl_threshold}")
            self.errors.append("Invalid RL confidence threshold")
            all_ok = False
        
        rl_exploration = self.config.get('rl_exploration_rate', 0.0)
        if rl_exploration > 0:
            print(f"   ⚠️  RL exploration rate is {rl_exploration:.1%} - should be 0.0 for live trading")
            self.warnings.append("RL exploration enabled in live mode")
        else:
            print(f"   ✅ RL exploration rate: {rl_exploration:.1%} (disabled for live)")
        
        return all_ok
    
    def check_trading_hours(self) -> bool:
        """Validate trading hours configuration"""
        print("\n[5/6] Checking Trading Hours Configuration...")
        
        # This is informational, not critical
        symbols = self.config.get('symbols', [])
        print(f"   ✅ Trading symbols: {', '.join(symbols)}")
        
        shadow_mode = self.config.get('shadow_mode', False)
        if shadow_mode:
            print(f"   ⚠️  Shadow mode is ENABLED (paper trading)")
            self.warnings.append("Shadow mode enabled")
        else:
            print(f"   ✅ Shadow mode is DISABLED (live trading)")
        
        return True
    
    def check_broker_config(self) -> bool:
        """Check broker configuration"""
        print("\n[6/6] Checking Broker Configuration...")
        
        broker_type = self.config.get('broker_type', '')
        if not broker_type:
            print(f"   ⚠️  Broker type not configured")
            self.warnings.append("No broker configured")
        else:
            print(f"   ✅ Broker type: {broker_type}")
        
        broker_validated = self.config.get('broker_validated', False)
        if broker_validated:
            print(f"   ✅ Broker credentials validated")
        else:
            print(f"   ⚠️  Broker credentials not validated")
            self.warnings.append("Broker not validated")
        
        return True
    
    def run_all_checks(self) -> bool:
        """Run all pre-flight checks"""
        print("=" * 80)
        print("PRE-FLIGHT CHECK FOR LIVE TRADING")
        print("=" * 80)
        
        # Load config first
        if not self.load_config():
            print("\n❌ CRITICAL: Cannot load config.json")
            return False
        
        # Run all checks
        checks = [
            ('json_files', self.check_json_files),
            ('cloud_rl', self.check_cloud_rl_connection),
            ('environment', self.check_environment_variables),
            ('risk_settings', self.check_risk_settings),
            ('trading_hours', self.check_trading_hours),
            ('broker', self.check_broker_config),
        ]
        
        for check_name, check_func in checks:
            try:
                self.results[check_name] = check_func()
            except Exception as e:
                print(f"\n   ❌ Error during {check_name}: {e}")
                self.results[check_name] = False
                self.errors.append(f"{check_name} check failed: {e}")
        
        # Print summary
        print("\n" + "=" * 80)
        print("PRE-FLIGHT CHECK SUMMARY")
        print("=" * 80)
        
        passed = sum(self.results.values())
        total = len(self.results)
        
        print(f"\nChecks Passed: {passed}/{total}")
        
        if self.errors:
            print(f"\n❌ ERRORS ({len(self.errors)}):")
            for error in self.errors:
                print(f"   - {error}")
        
        if self.warnings:
            print(f"\n⚠️  WARNINGS ({len(self.warnings)}):")
            for warning in self.warnings:
                print(f"   - {warning}")
        
        print("\n" + "=" * 80)
        
        # Final verdict
        if len(self.errors) == 0:
            if len(self.warnings) == 0:
                print("✅ ALL CHECKS PASSED - READY FOR LIVE TRADING")
                print("=" * 80)
                return True
            else:
                print("⚠️  ALL CHECKS PASSED WITH WARNINGS - Review warnings before trading")
                print("=" * 80)
                return True
        else:
            print("❌ PRE-FLIGHT CHECK FAILED - Fix errors before live trading")
            print("=" * 80)
            return False


def main():
    """Main entry point"""
    checker = PreFlightChecker()
    success = checker.run_all_checks()
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()

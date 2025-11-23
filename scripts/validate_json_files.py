#!/usr/bin/env python3
"""
JSON File Validation Script for Live Trading
============================================
Validates all JSON configuration files before live trading starts.
Ensures data integrity and proper schema compliance.
"""

import json
import sys
import os
from pathlib import Path
from typing import Dict, Any, List, Tuple

# Add parent directory to path to import from src
sys.path.insert(0, str(Path(__file__).parent.parent))


class JSONValidator:
    """Validates JSON files for trading bot"""
    
    def __init__(self, project_root: str = None):
        if project_root is None:
            self.project_root = Path(__file__).parent.parent
        else:
            self.project_root = Path(project_root)
    
    def validate_config_json(self, filepath: str) -> Tuple[bool, List[str]]:
        """Validate data/config.json structure"""
        errors = []
        
        try:
            with open(filepath, 'r') as f:
                config = json.load(f)
            
            # Required fields for live trading
            required_fields = {
                'market_type': str,
                'symbols': list,
                'account_size': (int, float),
                'max_contracts': int,
                'max_trades_per_day': int,
                'risk_per_trade': float,
                'daily_loss_limit': float,
                'rl_confidence_threshold': float,
                'rl_exploration_rate': float,
                'cloud_api_url': str,
            }
            
            for field, expected_type in required_fields.items():
                if field not in config:
                    errors.append(f"Missing required field: {field}")
                elif not isinstance(config[field], expected_type):
                    errors.append(f"Field '{field}' has wrong type. Expected {expected_type}, got {type(config[field])}")
            
            # Validate specific field values
            if 'max_contracts' in config:
                if config['max_contracts'] < 1 or config['max_contracts'] > 25:
                    errors.append(f"max_contracts must be between 1 and 25, got {config['max_contracts']}")
            
            if 'rl_confidence_threshold' in config:
                if not (0.0 <= config['rl_confidence_threshold'] <= 1.0):
                    errors.append(f"rl_confidence_threshold must be between 0.0 and 1.0, got {config['rl_confidence_threshold']}")
            
            if 'rl_exploration_rate' in config:
                if not (0.0 <= config['rl_exploration_rate'] <= 1.0):
                    errors.append(f"rl_exploration_rate must be between 0.0 and 1.0, got {config['rl_exploration_rate']}")
            
            if 'symbols' in config:
                if not config['symbols']:
                    errors.append("symbols list cannot be empty")
            
            if 'cloud_api_url' in config:
                if not config['cloud_api_url'].startswith(('http://', 'https://')):
                    errors.append(f"cloud_api_url must be a valid URL, got {config['cloud_api_url']}")
            
        except json.JSONDecodeError as e:
            errors.append(f"JSON syntax error: {e}")
        except Exception as e:
            errors.append(f"Unexpected error: {e}")
        
        return len(errors) == 0, errors
    
    def validate_signal_experience_json(self, filepath: str) -> Tuple[bool, List[str]]:
        """Validate data/signal_experience.json structure"""
        errors = []
        
        try:
            with open(filepath, 'r') as f:
                data = json.load(f)
            
            # Should have experiences and stats
            if 'experiences' not in data:
                errors.append("Missing 'experiences' field")
            elif not isinstance(data['experiences'], list):
                errors.append("'experiences' must be a list")
            
            if 'stats' not in data:
                errors.append("Missing 'stats' field")
            elif not isinstance(data['stats'], dict):
                errors.append("'stats' must be a dictionary")
            
            # Validate a sample experience if any exist
            if 'experiences' in data and len(data['experiences']) > 0:
                exp = data['experiences'][0]
                required_exp_fields = ['timestamp', 'state', 'action', 'reward', 'duration']
                for field in required_exp_fields:
                    if field not in exp:
                        errors.append(f"Experience missing required field: {field}")
                        break
                
                # Validate state structure
                if 'state' in exp:
                    state = exp['state']
                    state_fields = ['rsi', 'vwap_distance', 'atr', 'volume_ratio', 'hour', 'day_of_week']
                    for field in state_fields:
                        if field not in state:
                            errors.append(f"Experience state missing field: {field}")
        
        except json.JSONDecodeError as e:
            errors.append(f"JSON syntax error: {e}")
        except Exception as e:
            errors.append(f"Unexpected error: {e}")
        
        return len(errors) == 0, errors
    
    def validate_trade_summary_json(self, filepath: str) -> Tuple[bool, List[str]]:
        """Validate data/trade_summary.json structure"""
        errors = []
        
        try:
            with open(filepath, 'r') as f:
                trade = json.load(f)
            
            # Required fields for a trade summary
            required_fields = {
                'symbol': str,
                'direction': str,
                'entry_price': (int, float),
                'exit_price': (int, float),
                'contracts': int,
                'pnl': (int, float),
                'timestamp': str,
            }
            
            for field, expected_type in required_fields.items():
                if field not in trade:
                    errors.append(f"Missing required field: {field}")
                elif not isinstance(trade[field], expected_type):
                    errors.append(f"Field '{field}' has wrong type. Expected {expected_type}, got {type(trade[field])}")
            
            # Validate direction
            if 'direction' in trade:
                if trade['direction'] not in ['LONG', 'SHORT']:
                    errors.append(f"direction must be 'LONG' or 'SHORT', got {trade['direction']}")
        
        except json.JSONDecodeError as e:
            errors.append(f"JSON syntax error: {e}")
        except Exception as e:
            errors.append(f"Unexpected error: {e}")
        
        return len(errors) == 0, errors
    
    def validate_daily_summary_json(self, filepath: str) -> Tuple[bool, List[str]]:
        """Validate daily_summary.json structure"""
        errors = []
        
        try:
            with open(filepath, 'r') as f:
                summary = json.load(f)
            
            # Required fields for daily summary
            required_fields = {
                'total_pnl': (int, float),
                'wins': int,
                'losses': int,
                'account_balance': (int, float),
                'timestamp': str,
            }
            
            for field, expected_type in required_fields.items():
                if field not in summary:
                    errors.append(f"Missing required field: {field}")
                elif not isinstance(summary[field], expected_type):
                    errors.append(f"Field '{field}' has wrong type. Expected {expected_type}, got {type(summary[field])}")
        
        except json.JSONDecodeError as e:
            errors.append(f"JSON syntax error: {e}")
        except Exception as e:
            errors.append(f"Unexpected error: {e}")
        
        return len(errors) == 0, errors
    
    def validate_all(self) -> bool:
        """Validate all JSON files"""
        all_valid = True
        
        print("=" * 80)
        print("JSON FILE VALIDATION FOR LIVE TRADING")
        print("=" * 80)
        print()
        
        # Define files to validate
        files_to_validate = [
            ('data/config.json', self.validate_config_json),
            ('data/signal_experience.json', self.validate_signal_experience_json),
            ('data/trade_summary.json', self.validate_trade_summary_json),
            ('daily_summary.json', self.validate_daily_summary_json),
        ]
        
        for filename, validator_func in files_to_validate:
            filepath = self.project_root / filename
            
            if not filepath.exists():
                print(f"⚠️  {filename}: FILE NOT FOUND")
                all_valid = False
                continue
            
            valid, errors = validator_func(str(filepath))
            
            if valid:
                print(f"✅ {filename}: VALID")
            else:
                print(f"❌ {filename}: INVALID")
                for error in errors:
                    print(f"   - {error}")
                all_valid = False
        
        print()
        print("=" * 80)
        if all_valid:
            print("✅ ALL JSON FILES ARE VALID - READY FOR LIVE TRADING")
        else:
            print("❌ VALIDATION FAILED - FIX ERRORS BEFORE LIVE TRADING")
        print("=" * 80)
        
        return all_valid


def main():
    """Main entry point"""
    validator = JSONValidator()
    success = validator.validate_all()
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""
JSON File Auto-Fixer for Live Trading
=====================================
Automatically fixes common JSON issues and ensures files are production-ready.
Creates backups before making changes.
"""

import json
import sys
import os
import shutil
from pathlib import Path
from datetime import datetime
from typing import Dict, Any, List

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

# Default cloud API URL (can be overridden via environment variable)
DEFAULT_CLOUD_API_URL = os.getenv(
    'QUOTRADING_CLOUD_API_URL',
    'https://quotrading-signals.icymeadow-86b2969e.eastus.azurecontainerapps.io'
)


class JSONAutoFixer:
    """Automatically fixes common JSON configuration issues"""
    
    def __init__(self, project_root: str = None):
        if project_root is None:
            self.project_root = Path(__file__).parent.parent
        else:
            self.project_root = Path(project_root)
        
        self.backup_dir = self.project_root / 'backups' / f'json_backup_{datetime.now().strftime("%Y%m%d_%H%M%S")}'
        self.fixes_applied = []
    
    def create_backup(self, filepath: Path):
        """Create backup of a file before modifying"""
        self.backup_dir.mkdir(parents=True, exist_ok=True)
        backup_path = self.backup_dir / filepath.name
        shutil.copy2(filepath, backup_path)
        print(f"   📁 Backup created: {backup_path}")
    
    def fix_config_json(self, filepath: Path) -> bool:
        """Fix data/config.json with defaults and corrections"""
        try:
            with open(filepath, 'r') as f:
                config = json.load(f)
            
            modified = False
            
            # Ensure RL exploration is 0 for production
            if config.get('rl_exploration_rate', 0.0) > 0:
                self.create_backup(filepath)
                config['rl_exploration_rate'] = 0.0
                config['rl_min_exploration_rate'] = 0.0
                modified = True
                self.fixes_applied.append("Set RL exploration rate to 0.0 for live trading")
            
            # Ensure RL confidence threshold is valid
            if not (0.0 <= config.get('rl_confidence_threshold', 0.7) <= 1.0):
                self.create_backup(filepath)
                config['rl_confidence_threshold'] = 0.7
                modified = True
                self.fixes_applied.append("Reset RL confidence threshold to 0.7")
            
            # Ensure max_contracts is within safe range
            if config.get('max_contracts', 2) > 25:
                self.create_backup(filepath)
                config['max_contracts'] = 25
                modified = True
                self.fixes_applied.append("Capped max_contracts at safety limit of 25")
            
            # Ensure cloud API URL is set
            if not config.get('cloud_api_url') or config.get('cloud_api_url') == '':
                self.create_backup(filepath)
                config['cloud_api_url'] = DEFAULT_CLOUD_API_URL
                modified = True
                self.fixes_applied.append("Set default cloud API URL")
            
            # Ensure symbols is a list
            if not isinstance(config.get('symbols', []), list):
                self.create_backup(filepath)
                config['symbols'] = ["ES"]
                modified = True
                self.fixes_applied.append("Reset symbols to default ['ES']")
            
            # Set auto_calculate_limits if missing
            if 'auto_calculate_limits' not in config:
                self.create_backup(filepath)
                config['auto_calculate_limits'] = True
                modified = True
                self.fixes_applied.append("Enabled auto_calculate_limits")
            
            if modified:
                with open(filepath, 'w') as f:
                    json.dump(config, f, indent=2)
                print(f"   ✅ Fixed {filepath}")
                return True
            else:
                print(f"   ✅ No fixes needed for {filepath}")
                return False
        
        except Exception as e:
            print(f"   ❌ Error fixing {filepath}: {e}")
            return False
    
    def fix_signal_experience_json(self, filepath: Path) -> bool:
        """Ensure signal_experience.json has proper structure"""
        try:
            with open(filepath, 'r') as f:
                data = json.load(f)
            
            modified = False
            
            # Ensure 'experiences' key exists
            if 'experiences' not in data:
                self.create_backup(filepath)
                data['experiences'] = []
                modified = True
                self.fixes_applied.append("Added missing 'experiences' key")
            
            # Ensure 'stats' key exists
            if 'stats' not in data:
                self.create_backup(filepath)
                data['stats'] = {
                    'total_signals': 0,
                    'taken': 0,
                    'skipped': 0,
                    'take_rate': 0,
                    'recent_pnl': 0,
                    'recent_win_rate': 0,
                    'exploration_rate': 0.0
                }
                modified = True
                self.fixes_applied.append("Added missing 'stats' key with defaults")
            
            if modified:
                with open(filepath, 'w') as f:
                    json.dump(data, f, indent=2)
                print(f"   ✅ Fixed {filepath}")
                return True
            else:
                print(f"   ✅ No fixes needed for {filepath}")
                return False
        
        except Exception as e:
            print(f"   ❌ Error fixing {filepath}: {e}")
            return False
    
    def validate_and_fix_all(self) -> bool:
        """Validate and auto-fix all JSON files"""
        print("=" * 80)
        print("JSON AUTO-FIXER FOR LIVE TRADING")
        print("=" * 80)
        print()
        
        files_to_fix = [
            ('data/config.json', self.fix_config_json),
            ('data/signal_experience.json', self.fix_signal_experience_json),
        ]
        
        all_ok = True
        
        for filename, fixer_func in files_to_fix:
            filepath = self.project_root / filename
            
            if not filepath.exists():
                print(f"⚠️  {filename}: FILE NOT FOUND - Skipping")
                continue
            
            print(f"\n📝 Processing {filename}...")
            try:
                fixer_func(filepath)
            except Exception as e:
                print(f"   ❌ Error: {e}")
                all_ok = False
        
        # Print summary
        print("\n" + "=" * 80)
        print("AUTO-FIX SUMMARY")
        print("=" * 80)
        
        if self.fixes_applied:
            print(f"\n✅ Applied {len(self.fixes_applied)} fixes:")
            for fix in self.fixes_applied:
                print(f"   - {fix}")
            print(f"\n📁 Backups saved to: {self.backup_dir}")
        else:
            print("\n✅ All files are already correct - No fixes needed")
        
        print("\n" + "=" * 80)
        
        return all_ok


def main():
    """Main entry point"""
    fixer = JSONAutoFixer()
    success = fixer.validate_and_fix_all()
    
    print("\n💡 Next steps:")
    print("   1. Review the changes made above")
    print("   2. Run: python scripts/validate_json_files.py")
    print("   3. Run: python scripts/preflight_check.py")
    print()
    
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()

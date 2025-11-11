"""
Migrate 3,214 exit experiences from rl_experiences table to exit_experiences table.

This ensures all exit data is in ONE table for learning.
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from database import DatabaseManager, RLExperience, ExitExperience
from datetime import datetime
import json

def migrate_exit_experiences():
    """Migrate all EXIT experiences from rl_experiences to exit_experiences table."""
    
    db_manager = DatabaseManager()
    session = db_manager.get_session()
    
    try:
        # Get all EXIT experiences from rl_experiences table
        old_exits = session.query(RLExperience).filter(
            RLExperience.experience_type == 'EXIT'
        ).all()
        
        print(f"\n[MIGRATION] Found {len(old_exits):,} exit experiences in rl_experiences table")
        
        # Check how many already exist in exit_experiences
        existing_count = session.query(ExitExperience).count()
        print(f"[MIGRATION] Currently {existing_count:,} experiences in exit_experiences table")
        
        migrated = 0
        skipped = 0
        
        for i, old_exp in enumerate(old_exits):
            # Build exit experience structure from rl_experiences columns
            exit_params = {
                'stop_loss_ticks': 12,  # Default values (we don't have originals)
                'breakeven_threshold_ticks': 9,
                'trailing_distance_ticks': 12,
                'partial_profit_levels': [],
                'current_atr': old_exp.atr or 0,
                'market_regime': 'NORMAL'  # Default
            }
            
            outcome = {
                'pnl': old_exp.pnl,
                'duration': old_exp.duration_minutes or 0,
                'exit_reason': old_exp.exit_reason or 'unknown',
                'side': old_exp.side,
                'contracts': 1,  # Default
                'win': old_exp.pnl > 0,
                'quality_score': 1.0
            }
            
            situation = {
                'time_of_day': old_exp.timestamp.strftime('%H:%M') if old_exp.timestamp else '12:00',
                'volatility_atr': old_exp.atr or 0,
                'trend_strength': 0
            }
            
            market_state = {
                'rsi': old_exp.rsi or 50.0,
                'volume_ratio': old_exp.volume_ratio or 1.0,
                'hour': old_exp.hour_of_day or 12,
                'day_of_week': old_exp.day_of_week or 0,
                'streak': old_exp.streak or 0,
                'recent_pnl': old_exp.recent_pnl or 0.0,
                'vix': old_exp.vix or 15.0,
                'vwap_distance': old_exp.vwap_distance or 0.0,
                'atr': old_exp.atr or 0.0
            }
            
            # Create new ExitExperience
            new_exit = ExitExperience(
                timestamp=old_exp.timestamp or datetime.now(),
                user_id=old_exp.user_id,
                symbol=old_exp.symbol,
                regime='NORMAL',  # Default
                exit_params_json=json.dumps(exit_params),
                outcome_json=json.dumps(outcome),
                situation_json=json.dumps(situation),
                market_state_json=json.dumps(market_state),
                partial_exits_json=json.dumps([])  # No partial data in old records
            )
            
            session.add(new_exit)
            migrated += 1
            
            if (i + 1) % 500 == 0:
                session.commit()
                print(f"  Progress: {i+1}/{len(old_exits)} migrated...")
        
        # Final commit
        session.commit()
        
        # Verify
        final_count = session.query(ExitExperience).count()
        
        print(f"\n[MIGRATION] ✓ Complete!")
        print(f"  Migrated: {migrated:,}")
        print(f"  Skipped: {skipped:,}")
        print(f"  Final count in exit_experiences: {final_count:,}")
        
    except Exception as e:
        print(f"\n[ERROR] Migration failed: {e}")
        session.rollback()
        import traceback
        traceback.print_exc()
        
    finally:
        session.close()


if __name__ == "__main__":
    print("="*80)
    print("EXIT EXPERIENCE MIGRATION")
    print("="*80)
    print("This will migrate 3,214 exit experiences from rl_experiences → exit_experiences")
    print()
    
    migrate_exit_experiences()

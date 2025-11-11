"""Check actual data in rl_experiences table to verify all features are populated"""
import os
from sqlalchemy import create_engine, text

database_url = os.getenv('DATABASE_URL', 'postgresql://quotadmin:QuoTrading2025!Secure@quotrading-db.postgres.database.azure.com/quotrading?sslmode=require')

engine = create_engine(database_url)

with engine.connect() as conn:
    # Get total count
    result = conn.execute(text("SELECT COUNT(*) FROM rl_experiences"))
    total = result.fetchone()[0]
    print(f"Total RL experiences in database: {total:,}")
    
    # Get count by type
    result = conn.execute(text("""
        SELECT experience_type, COUNT(*) 
        FROM rl_experiences 
        GROUP BY experience_type
    """))
    print("\nBy type:")
    for row in result:
        print(f"  {row[0]:10s}: {row[1]:,}")
    
    # Sample recent records to check if ALL features are populated
    result = conn.execute(text("""
        SELECT 
            experience_type,
            signal_type,
            outcome,
            pnl,
            rsi,
            vwap_distance,
            vix,
            day_of_week,
            hour_of_day,
            atr,
            volume_ratio,
            recent_pnl,
            streak,
            timestamp
        FROM rl_experiences 
        ORDER BY timestamp DESC 
        LIMIT 5
    """))
    
    print("\nMost recent 5 experiences (checking ALL features):")
    for row in result:
        exp_type, signal_type, outcome, pnl, rsi, vwap_dist, vix, day, hour, atr, vol_ratio, recent_pnl, streak, ts = row
        
        # Handle NULL values
        pnl_val = pnl if pnl is not None else 0
        rsi_val = rsi if rsi is not None else 0
        vwap_val = vwap_dist if vwap_dist is not None else 0
        vix_val = vix if vix is not None else 0
        atr_val = atr if atr is not None else 0
        vol_val = vol_ratio if vol_ratio is not None else 0
        rpnl_val = recent_pnl if recent_pnl is not None else 0
        streak_val = streak if streak is not None else 0
        
        print(f"\n  {exp_type} - {signal_type} - {outcome} | P&L: ${pnl_val:.0f}")
        print(f"    RSI: {rsi_val:.1f} | VWAP Dist: {vwap_val:.4f} | VIX: {vix_val:.1f}")
        print(f"    Day: {day if day is not None else 'NULL'} | Hour: {hour if hour is not None else 'NULL'} | ATR: {atr_val:.2f}")
        print(f"    Vol Ratio: {vol_val:.2f} | Recent P&L: ${rpnl_val:.0f} | Streak: {streak_val:+d}")
        print(f"    Timestamp: {ts}")
    
    # Check for NULL values in critical features
    print("\n\nNULL value check (should be 0 for critical features):")
    for col in ['rsi', 'vwap_distance', 'vix', 'day_of_week', 'hour_of_day', 
                'atr', 'volume_ratio', 'recent_pnl', 'streak']:
        result = conn.execute(text(f"SELECT COUNT(*) FROM rl_experiences WHERE {col} IS NULL"))
        null_count = result.fetchone()[0]
        status = "✅" if null_count == 0 else "❌"
        print(f"  {status} {col:20s}: {null_count:,} NULL values")

# Automatic Backup Feature

**Date:** November 17, 2025  
**Feature:** Automatic backup of experience files before overwriting  
**Purpose:** Prevent data loss from file corruption or accidental overwrites

---

## Overview

All experience files are now automatically backed up before being overwritten. This provides a safety net to recover data if something goes wrong during saving.

---

## How It Works

### 1. Automatic Backup Creation

Before saving any experience file, the system:
1. Checks if the file already exists
2. Creates a timestamped backup in a `backups/` subdirectory
3. Saves the new data to the original file

**Backup Format:**
```
data/local_experiences/backups/signal_experiences_v2.json.20251117_200438.backup
```

**Timestamp Format:** `YYYYMMDD_HHMMSS`

### 2. Automatic Cleanup

To prevent unlimited backup accumulation:
- Only the **10 most recent** backups are kept per file
- Older backups are automatically deleted
- Deletion is logged for transparency

### 3. Backup Locations

**Signal Experiences:**
- Main file: `data/local_experiences/signal_experiences_v2.json`
- Backups: `data/local_experiences/backups/signal_experiences_v2.json.*.backup`

**Exit Experiences:**
- Main file: `data/local_experiences/exit_experiences_v2.json`
- Backups: `data/local_experiences/backups/exit_experiences_v2.json.*.backup`

**Live Trading (additional):**
- Main file: `data/rl_signal_experiences.json`
- Backups: `data/backups/rl_signal_experiences.json.*.backup`

---

## Files Modified

### 1. `dev-tools/local_experience_manager.py`
Added backup methods:
- `_create_backup()` - Creates timestamped backup
- `_cleanup_old_backups()` - Keeps only 10 most recent
- Updated `save_new_experiences_to_file()` to call backup

### 2. `src/signal_confidence.py`
Added backup methods:
- `_create_backup()` - Creates timestamped backup
- `_cleanup_old_backups()` - Keeps only 10 most recent
- Updated `save_experience()` to call backup

### 3. `src/adaptive_exits.py`
Added backup methods:
- `_create_backup()` - Creates timestamped backup
- `_cleanup_old_backups()` - Keeps only 10 most recent
- Updated `save_experiences()` to call backup

### 4. `dev-tools/local_exit_manager.py`
Added backup methods:
- `_create_backup()` - Creates timestamped backup
- `_cleanup_old_backups()` - Keeps only 10 most recent
- Updated `save_new_experiences_to_file()` to call backup

---

## Output Examples

### During Backtest:
```
⚡ LOCAL MODE: Saving 97 signal experiences to local files...
   📦 Backup created: data/local_experiences/backups/signal_experiences_v2.json.20251117_200438.backup
✅ Saved 97 new signal experiences to local file
   Total experiences now: 12,538
```

### During Live Trading:
```
INFO: Backup created: data/backups/rl_signal_experiences.json.20251117_200438.backup
INFO: Saved 15 experiences to data/rl_signal_experiences.json and data/local_experiences/signal_experiences_v2.json
```

### When Cleanup Occurs:
```
   📦 Backup created: data/local_experiences/backups/signal_experiences_v2.json.20251117_200438.backup
   🗑️  Removed old backup: signal_experiences_v2.json.20251117_120530.backup
```

---

## Recovery Process

If you need to restore from a backup:

### 1. List Available Backups
```bash
ls -lh data/local_experiences/backups/
```

### 2. Check Backup Contents
```bash
head -20 data/local_experiences/backups/signal_experiences_v2.json.20251117_200438.backup
```

### 3. Restore Backup
```bash
# Make a copy of current file (just in case)
cp data/local_experiences/signal_experiences_v2.json data/local_experiences/signal_experiences_v2.json.current

# Restore from backup
cp data/local_experiences/backups/signal_experiences_v2.json.20251117_200438.backup data/local_experiences/signal_experiences_v2.json
```

### 4. Verify Restoration
```bash
# Check experience count
python -c "import json; data = json.load(open('data/local_experiences/signal_experiences_v2.json')); print(f'Experiences: {len(data[\"experiences\"])}')"
```

---

## Benefits

### 1. Data Protection
- Protects against file corruption
- Protects against accidental overwrites
- Provides recovery point for last 10 saves

### 2. Minimal Storage Impact
- Automatic cleanup keeps storage usage low
- Only 10 backups per file = ~150MB total (10 × ~15MB)
- Old backups automatically deleted

### 3. Zero Configuration
- Automatically enabled for all experience saves
- No user action required
- Transparent operation

### 4. Debugging Aid
- Can review historical states
- Can identify when corruption occurred
- Can track experience growth over time

---

## Technical Details

### Backup Method Implementation

```python
def _create_backup(self, filepath: str):
    """Create automatic backup of experience file before overwriting"""
    if os.path.exists(filepath):
        import shutil
        from datetime import datetime
        # Create backup with timestamp
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_dir = os.path.join(os.path.dirname(filepath), "backups")
        os.makedirs(backup_dir, exist_ok=True)
        
        filename = os.path.basename(filepath)
        backup_path = os.path.join(backup_dir, f"{filename}.{timestamp}.backup")
        
        try:
            shutil.copy2(filepath, backup_path)
            print(f"   📦 Backup created: {backup_path}")
            
            # Keep only last 10 backups to save space
            self._cleanup_old_backups(backup_dir, filename)
        except Exception as e:
            print(f"   ⚠️  Backup failed (continuing anyway): {e}")
```

### Cleanup Method Implementation

```python
def _cleanup_old_backups(self, backup_dir: str, filename: str):
    """Keep only the 10 most recent backups"""
    import glob
    pattern = os.path.join(backup_dir, f"{filename}.*.backup")
    backups = sorted(glob.glob(pattern), reverse=True)
    
    # Remove backups beyond the 10 most recent
    for old_backup in backups[10:]:
        try:
            os.remove(old_backup)
            print(f"   🗑️  Removed old backup: {os.path.basename(old_backup)}")
        except Exception as e:
            print(f"   ⚠️  Failed to remove old backup: {e}")
```

---

## Error Handling

### Backup Failure
If backup creation fails:
- Error is logged with warning
- Original save operation continues
- Data is still saved (without backup)

**Why:** Better to save data without backup than lose new experiences

### Cleanup Failure
If old backup deletion fails:
- Error is logged with warning
- New backup is still created
- More than 10 backups may accumulate temporarily

**Why:** Better to have extra backups than fail the save operation

---

## Storage Estimates

### Current Usage
- Signal experiences: ~14 MB per file
- Exit experiences: ~32 MB per file

### Backup Storage
- Signal backups: 10 × 14 MB = ~140 MB
- Exit backups: 10 × 32 MB = ~320 MB
- **Total backup storage: ~460 MB**

### Growth Rate
- New backtest: +1 backup (signal + exit)
- Live trading: +1 backup per save (varies by frequency)
- Old backups deleted automatically

---

## Summary

✅ **Automatic backups now enabled for all experience files**

**Features:**
- Timestamped backups before each save
- 10 most recent backups kept per file
- Automatic cleanup of old backups
- Zero configuration required
- Transparent operation

**Protection:**
- File corruption recovery
- Accidental overwrite recovery
- Historical state tracking
- Debugging capability

**Storage:**
- ~460 MB for all backups
- Automatic cleanup prevents unlimited growth
- Minimal impact on disk space

The automatic backup feature provides a safety net for your valuable experience data without requiring any user action or configuration.

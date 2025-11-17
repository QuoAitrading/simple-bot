#!/usr/bin/env python3
"""
Comprehensive Bug Audit - Check for Issues That Could Destroy Learning
Searches for patterns similar to the exploration rate bug
"""
import os
import re

print("=" * 80)
print("COMPREHENSIVE BUG AUDIT")
print("=" * 80)
print()

issues_found = []

# Pattern 1: Double filtering (like exploration bug)
print("1. CHECKING FOR DOUBLE FILTERING BUGS...")
print("-" * 80)

files_to_check = [
    'dev-tools/full_backtest.py',
    'dev-tools/local_experience_manager.py',
    'src/signal_confidence.py',
    'src/adaptive_exits.py'
]

for filepath in files_to_check:
    if not os.path.exists(filepath):
        continue
    
    with open(filepath, 'r') as f:
        lines = f.readlines()
    
    # Look for take_signal decisions followed by additional filters
    for i, line in enumerate(lines):
        if 'take_signal' in line and '=' in line and 'True' in line:
            # Check next 10 lines for additional filtering
            for j in range(i+1, min(i+15, len(lines))):
                if 'if' in lines[j] and ('contracts' in lines[j] or 'threshold' in lines[j]):
                    if 'contracts == 0' in lines[j] or 'contracts < ' in lines[j]:
                        # Potential double filter
                        context = f"{filepath}:{i+1}-{j+1}"
                        issue = f"Potential double filtering: take_signal=True followed by contracts check"
                        print(f"  ⚠️  {context}")
                        print(f"      Line {i+1}: {line.strip()}")
                        print(f"      Line {j+1}: {lines[j].strip()}")
                        issues_found.append((context, issue))
                        break

print()

# Pattern 2: Data loss in experience saving
print("2. CHECKING FOR DATA LOSS IN EXPERIENCE SAVING...")
print("-" * 80)

for filepath in files_to_check:
    if not os.path.exists(filepath):
        continue
    
    with open(filepath, 'r') as f:
        content = f.read()
    
    # Check for conditional experience saving
    if 'add_signal_experience' in content or 'add_exit_experience' in content:
        # Look for if statements around experience saving
        pattern = r'if\s+.*:\s*\n\s*.*add_.*_experience'
        matches = re.finditer(pattern, content, re.MULTILINE)
        for match in matches:
            line_num = content[:match.start()].count('\n') + 1
            context = f"{filepath}:{line_num}"
            issue = "Experience saving inside conditional - might lose data"
            print(f"  ⚠️  {context}")
            print(f"      {match.group(0)[:100]}")
            issues_found.append((context, issue))

print()

# Pattern 3: NaN/None values corrupting data
print("3. CHECKING FOR NaN/None HANDLING ISSUES...")
print("-" * 80)

training_files = [
    'dev-tools/train_model.py',
    'dev-tools/train_exit_model.py'
]

for filepath in training_files:
    if not os.path.exists(filepath):
        continue
    
    with open(filepath, 'r') as f:
        lines = f.readlines()
    
    # Look for skipping experiences due to missing data
    for i, line in enumerate(lines):
        if 'skip' in line.lower() and 'experience' in line.lower():
            context = f"{filepath}:{i+1}"
            issue = "Skipping experience - might lose training data"
            print(f"  ⚠️  {context}: {line.strip()}")
            issues_found.append((context, issue))

print()

# Pattern 4: Threshold checks that might be too restrictive
print("4. CHECKING FOR OVERLY RESTRICTIVE THRESHOLDS...")
print("-" * 80)

for filepath in files_to_check:
    if not os.path.exists(filepath):
        continue
    
    with open(filepath, 'r') as f:
        lines = f.readlines()
    
    # Look for hardcoded minimum data requirements
    for i, line in enumerate(lines):
        if 'if len(' in line and '<' in line:
            # Extract the number
            match = re.search(r'<\s*(\d+)', line)
            if match:
                threshold = int(match.group(1))
                if threshold > 50:  # High thresholds might prevent learning
                    context = f"{filepath}:{i+1}"
                    issue = f"High minimum data requirement: {threshold}"
                    print(f"  ⚠️  {context}: {line.strip()}")
                    issues_found.append((context, issue))

print()

# Pattern 5: Exploration/randomness being ignored
print("5. CHECKING FOR IGNORED EXPLORATION/RANDOMNESS...")
print("-" * 80)

for filepath in files_to_check:
    if not os.path.exists(filepath):
        continue
    
    with open(filepath, 'r') as f:
        content = f.read()
    
    # Check if exploration_rate is passed but not used
    if 'exploration_rate' in content:
        # Count usages
        usages = content.count('exploration_rate')
        # Check if it's actually used in logic
        if 'random.random() < exploration_rate' not in content and usages > 1:
            context = filepath
            issue = "exploration_rate defined but might not be used in decision logic"
            print(f"  ⚠️  {context}")
            issues_found.append((context, issue))

print()

# Pattern 6: Confidence threshold applied multiple times
print("6. CHECKING FOR REDUNDANT THRESHOLD CHECKS...")
print("-" * 80)

for filepath in files_to_check:
    if not os.path.exists(filepath):
        continue
    
    with open(filepath, 'r') as f:
        lines = f.readlines()
    
    threshold_checks = []
    for i, line in enumerate(lines):
        if 'confidence' in line and 'threshold' in line and '<' in line:
            threshold_checks.append((i+1, line.strip()))
    
    if len(threshold_checks) > 2:  # Multiple threshold checks might indicate redundancy
        context = filepath
        issue = f"Multiple confidence threshold checks ({len(threshold_checks)})"
        print(f"  ⚠️  {context}: {len(threshold_checks)} threshold checks found")
        for line_num, line_text in threshold_checks[:3]:
            print(f"      Line {line_num}: {line_text[:80]}")

print()

# Summary
print("=" * 80)
print("AUDIT SUMMARY")
print("=" * 80)
print()

if issues_found:
    print(f"⚠️  Found {len(issues_found)} potential issues")
    print()
    print("RECOMMENDATIONS:")
    print("1. Review double filtering patterns (like exploration bug)")
    print("2. Ensure ALL experiences are saved (no conditional skipping)")
    print("3. Handle NaN/None values properly (don't skip experiences)")
    print("4. Check if thresholds are too restrictive")
    print("5. Verify exploration/randomness is actually used")
    print("6. Remove redundant threshold checks")
else:
    print("✅ No major issues detected")

print()
print("=" * 80)

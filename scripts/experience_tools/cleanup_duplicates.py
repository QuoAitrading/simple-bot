#!/usr/bin/env python3
"""Remove all duplicates and save only unique experiences"""
import json

# Load the file
with open('experiences/ES/signal_experience.json', 'r') as f:
    data = json.load(f)

experiences = data['experiences']
print(f"Before cleanup: {len(experiences)} experiences")

# Remove duplicates - keep first occurrence
seen = set()
unique_experiences = []

for exp in experiences:
    exp_key = (exp['timestamp'], exp['symbol'], exp['pnl'], exp['exit_reason'])
    if exp_key not in seen:
        seen.add(exp_key)
        unique_experiences.append(exp)

print(f"After cleanup: {len(unique_experiences)} unique experiences")
print(f"Removed: {len(experiences) - len(unique_experiences)} duplicates")

# Update the data
data['experiences'] = unique_experiences
data['stats']['total_signals'] = len(unique_experiences)
data['stats']['taken'] = len(unique_experiences)

# Create backup first
with open('experiences/ES/signal_experience.json.before_cleanup', 'w') as f:
    json.dump({"experiences": experiences}, f, indent=2)
print(f"\nBackup saved: signal_experience.json.before_cleanup")

# Save cleaned data
with open('experiences/ES/signal_experience.json', 'w') as f:
    json.dump(data, f, indent=2)

print(f"✅ Cleaned file saved with {len(unique_experiences)} unique experiences!")

# Verify
wins = sum(1 for e in unique_experiences if e['pnl'] > 0)
losses = sum(1 for e in unique_experiences if e['pnl'] <= 0)
total_pnl = sum(e['pnl'] for e in unique_experiences)

print(f"\nStats:")
print(f"  Wins: {wins} ({wins/len(unique_experiences)*100:.1f}%)")
print(f"  Losses: {losses} ({losses/len(unique_experiences)*100:.1f}%)")
print(f"  Total PnL: ${total_pnl:.2f}")
print(f"  Avg PnL: ${total_pnl/len(unique_experiences):.2f}")

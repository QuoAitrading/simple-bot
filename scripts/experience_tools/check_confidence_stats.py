#!/usr/bin/env python3
"""Analyze confidence levels from experiences"""
import json
import statistics

# Load experiences
with open('experiences/ES/signal_experience.json', 'r') as f:
    data = json.load(f)

experiences = data['experiences']
print(f"Analyzing {len(experiences)} experiences\n")

# Get all confidence scores
confidences = [exp.get('exploration_rate', 1.0) for exp in experiences]

# Calculate stats
avg_conf = statistics.mean(confidences)
median_conf = statistics.median(confidences)
min_conf = min(confidences)
max_conf = max(confidences)

print(f"📊 Confidence Statistics:")
print(f"  Average: {avg_conf:.3f}")
print(f"  Median:  {median_conf:.3f}")
print(f"  Min:     {min_conf:.3f}")
print(f"  Max:     {max_conf:.3f}")

# Distribution
high_conf = sum(1 for c in confidences if c >= 0.8)
med_conf = sum(1 for c in confidences if 0.5 <= c < 0.8)
low_conf = sum(1 for c in confidences if c < 0.5)

print(f"\n📈 Confidence Distribution:")
print(f"  High (≥0.8):    {high_conf} ({high_conf/len(confidences)*100:.1f}%)")
print(f"  Medium (0.5-0.8): {med_conf} ({med_conf/len(confidences)*100:.1f}%)")
print(f"  Low (<0.5):     {low_conf} ({low_conf/len(confidences)*100:.1f}%)")

# Confidence by outcome
wins = [exp for exp in experiences if exp['pnl'] > 0]
losses = [exp for exp in experiences if exp['pnl'] <= 0]

if wins:
    win_conf = statistics.mean([exp.get('exploration_rate', 1.0) for exp in wins])
    print(f"\n💰 Winning Trades:")
    print(f"  Count: {len(wins)}")
    print(f"  Avg Confidence: {win_conf:.3f}")

if losses:
    loss_conf = statistics.mean([exp.get('exploration_rate', 1.0) for exp in losses])
    print(f"\n❌ Losing Trades:")
    print(f"  Count: {len(losses)}")
    print(f"  Avg Confidence: {loss_conf:.3f}")

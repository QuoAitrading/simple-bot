import json
from datetime import datetime

# Load experiences
with open('data/signal_experience.json', 'r') as f:
    data = json.load(f)

exps = data['experiences']

# Find experiences with volume_ratio = 0
zero_vol_exps = [e for e in exps if e['state']['volume_ratio'] == 0]

print(f'Analyzing {len(zero_vol_exps)} experiences with volume_ratio = 0\n')

# Group by hour
hours = {}
for e in zero_vol_exps:
    ts = datetime.fromisoformat(e['timestamp'])
    hour = ts.hour
    hours[hour] = hours.get(hour, 0) + 1

print('Distribution by hour (ET):')
for hour in sorted(hours.keys()):
    print(f'  {hour:02d}:00 - {hours[hour]} occurrences')

# Check if these were actually low-volume periods
# (Late night / early morning = low volume for ES)
overnight_hours = [22, 23, 0, 1, 2, 3, 4, 5]
overnight_count = sum(hours.get(h, 0) for h in overnight_hours)

print(f'\nOvernight hours (22:00-05:00): {overnight_count}/{len(zero_vol_exps)} ({overnight_count/len(zero_vol_exps)*100:.1f}%)')
print(f'Market hours (09:30-16:00): {len(zero_vol_exps) - overnight_count}/{len(zero_vol_exps)} ({(len(zero_vol_exps) - overnight_count)/len(zero_vol_exps)*100:.1f}%)')

# Sample a few
print('\nSample zero-volume experiences:')
for i, e in enumerate(zero_vol_exps[:5]):
    ts = datetime.fromisoformat(e['timestamp'])
    print(f'\n--- Sample {i+1} ---')
    print(f'Time: {ts.strftime("%Y-%m-%d %H:%M:%S")} (Hour: {ts.hour})')
    print(f'Side: {e["state"]["side"]}, Regime: {e["state"]["regime"]}')
    print(f'ATR: {e["state"]["atr"]:.2f}, RSI: {e["state"]["rsi"]:.1f}')
    print(f'Reward: ${e["reward"]:.2f}, Duration: {e["duration"]/60:.1f} min')

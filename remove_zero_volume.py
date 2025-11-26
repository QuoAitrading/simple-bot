import json

# Load experiences
with open('data/signal_experience.json', 'r') as f:
    data = json.load(f)

original_count = len(data['experiences'])

# Remove zero-volume experiences (they're corrupted)
data['experiences'] = [e for e in data['experiences'] if e['state']['volume_ratio'] != 0]

# Save
with open('data/signal_experience.json', 'w') as f:
    json.dump(data, f, indent=2)

removed = original_count - len(data['experiences'])
print(f'Removed {removed} corrupted zero-volume experiences')
print(f'Remaining: {len(data["experiences"])} valid experiences')

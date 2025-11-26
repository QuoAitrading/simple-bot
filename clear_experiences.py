import json

# Clear old experience database
data = {"experiences": []}
with open("data/signal_experience.json", "w") as f:
    json.dump(data, f, indent=2)

print("Cleared experience database - ready for new market state format")

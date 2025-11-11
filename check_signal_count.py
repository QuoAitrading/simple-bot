import requests
import json

CLOUD_URL = "https://quotrading-signals.icymeadow-86b2969e.eastus.azurecontainerapps.io"

print("Checking Signal Experience Count...")
print("=" * 60)

# Try to get stats from API
try:
    r = requests.get(f"{CLOUD_URL}/api/ml/stats", timeout=10)
    if r.status_code == 200:
        data = r.json()
        total = data.get("total_experiences", 0)
        print(f"✅ Signal Experiences (from cloud API): {total:,}")
    else:
        print(f"❌ API returned status {r.status_code}")
        print("Trying alternate method...")
        
        # Check local file
        try:
            with open("cloud-api/signal_experience.json", "r") as f:
                experiences = json.load(f)
                if isinstance(experiences, list):
                    print(f"✅ Signal Experiences (from local file): {len(experiences):,}")
                elif isinstance(experiences, dict):
                    total = sum(len(v) for v in experiences.values() if isinstance(v, list))
                    print(f"✅ Signal Experiences (from local file): {total:,}")
        except FileNotFoundError:
            print("❌ Local file not found")
except Exception as e:
    print(f"❌ Error: {e}")
    
    # Fallback to local file
    try:
        with open("cloud-api/signal_experience.json", "r") as f:
            experiences = json.load(f)
            if isinstance(experiences, list):
                count = len(experiences)
            elif isinstance(experiences, dict):
                count = sum(len(v) for v in experiences.values() if isinstance(v, list))
            else:
                count = 0
            print(f"\n✅ Signal Experiences (from local backup): {count:,}")
    except Exception as e2:
        print(f"❌ Could not read local file: {e2}")

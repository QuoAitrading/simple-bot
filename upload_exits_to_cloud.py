"""
Upload 3,214 exit experiences from local JSON file to cloud PostgreSQL.

This migrates all exit data from cloud-api/exit_experience.json → PostgreSQL exit_experiences table.
"""

import requests
import json

CLOUD_API_URL = "https://quotrading-signals.icymeadow-86b2969e.eastus.azurecontainerapps.io"

print("="*80)
print("UPLOADING EXIT EXPERIENCES TO CLOUD")
print("="*80)

# Load local exit experiences
print("\n[1] Loading exit experiences from cloud-api/exit_experience.json...")
with open('cloud-api/exit_experience.json', 'r') as f:
    data = json.load(f)
    exit_experiences = data.get('exit_experiences', [])

print(f"    Found {len(exit_experiences):,} exit experiences in local file")

# Check what's currently in cloud
print("\n[2] Checking current cloud database...")
try:
    response = requests.get(f"{CLOUD_API_URL}/api/ml/get_exit_experiences", timeout=10)
    if response.status_code == 200:
        current_count = response.json().get('total_count', 0)
        print(f"    Currently {current_count:,} experiences in cloud database")
    else:
        print(f"    Error checking cloud: {response.status_code}")
        current_count = 0
except Exception as e:
    print(f"    Error: {e}")
    current_count = 0

# Upload all experiences
print(f"\n[3] Uploading {len(exit_experiences):,} experiences to cloud...")
uploaded = 0
failed = 0

for i, exp in enumerate(exit_experiences):
    try:
        # Convert boolean to int for JSON
        cloud_exp = {
            **exp,
            'outcome': {
                **exp['outcome'],
                'win': int(exp['outcome']['win']) if isinstance(exp['outcome'].get('win'), bool) else exp['outcome'].get('win', 0)
            }
        }
        
        response = requests.post(
            f"{CLOUD_API_URL}/api/ml/save_exit_experience",
            json=cloud_exp,
            timeout=5
        )
        
        if response.status_code == 200 and response.json().get('saved'):
            uploaded += 1
            if (i + 1) % 500 == 0:
                total_in_db = response.json().get('total_exit_experiences', 0)
                print(f"    Progress: {i+1}/{len(exit_experiences)} uploaded... (DB now has {total_in_db:,})")
        else:
            failed += 1
            if failed <= 3:  # Show first 3 errors
                print(f"    Error on experience {i+1}: {response.json().get('error', 'Unknown')}")
                
    except Exception as e:
        failed += 1
        if failed <= 3:
            print(f"    Exception on experience {i+1}: {e}")

# Final check
print(f"\n[4] Verifying upload...")
try:
    response = requests.get(f"{CLOUD_API_URL}/api/ml/get_exit_experiences", timeout=10)
    if response.status_code == 200:
        final_count = response.json().get('total_count', 0)
        print(f"    Final count in cloud: {final_count:,}")
    else:
        final_count = 0
except:
    final_count = 0

print("\n" + "="*80)
print("UPLOAD COMPLETE")
print("="*80)
print(f"Uploaded: {uploaded:,}")
print(f"Failed: {failed:,}")
print(f"Cloud database now has: {final_count:,} exit experiences")
print("="*80)

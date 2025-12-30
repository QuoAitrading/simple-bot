import requests

webhook_url = "https://discord.com/api/webhooks/1455297557793341462/24Jk2H-Udqaers72aBtjb84JybUSNiLnGUTeBvmy1InaGZ_3meH5_gC03zmgj4UhOLRu"

data = {
    "content": "✅ Webhook test successful! Earnings Whispers will post here.",
    "username": "Earnings Whispers"
}

r = requests.post(webhook_url, json=data)
print(f"Status: {r.status_code}")
print(f"Response: {r.text}")

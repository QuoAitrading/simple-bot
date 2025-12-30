"""Test fetching Earnings Whispers"""
import asyncio
import aiohttp

async def test():
    # Try Reddit search
    url = "https://www.reddit.com/r/wallstreetbets/search.json?q=most+anticipated+earnings&restrict_sr=1&sort=new&limit=10"
    headers = {'User-Agent': 'QuoTradingBot/1.0'}
    
    async with aiohttp.ClientSession() as session:
        print("Testing Reddit search...")
        async with session.get(url, headers=headers) as resp:
            print(f"Status: {resp.status}")
            if resp.status == 200:
                data = await resp.json()
                posts = data.get('data', {}).get('children', [])
                print(f"Found {len(posts)} posts")
                for post in posts[:5]:
                    pd = post.get('data', {})
                    print(f"\nTitle: {pd.get('title', 'N/A')[:80]}")
                    print(f"URL: {pd.get('url', 'N/A')[:80]}")
                    print(f"Is image: {pd.get('url', '').endswith(('.jpg', '.png', '.gif', '.webp'))}")

asyncio.run(test())

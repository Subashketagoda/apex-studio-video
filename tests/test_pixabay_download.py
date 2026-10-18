import os
import requests
from dotenv import load_dotenv

load_dotenv()
api_key = os.getenv("PIXABAY_API_KEY")
res = requests.get("https://pixabay.com/api/videos/", params={"key": api_key, "q": "galaxy stars"}).json()
hit = res["hits"][0]
v = hit["videos"]
print("Available sizes:", list(v.keys()))
for sz in ["tiny", "small", "medium", "large"]:
    if sz in v:
        u = v[sz]["url"]
        print(f"{sz}: size={v[sz].get('size')} url={u}")
        try:
            r = requests.get(u, headers={"User-Agent": "Mozilla/5.0"}, stream=True, timeout=10)
            print(f"{sz} status: {r.status_code}, content-type: {r.headers.get('content-type')}")
            chunk = next(r.iter_content(chunk_size=1024))
            print(f"{sz} first chunk bytes: {len(chunk)}")
        except Exception as e:
            print(f"{sz} error: {e}")

import requests
import re
import json

headers = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8"
}

url = "https://www.pexels.com/search/videos/space/?orientation=portrait"
r = requests.get(url, headers=headers, timeout=10)
print("Status code:", r.status_code)

# Search for mp4 URLs
mp4_urls = set(re.findall(r'https://[^\s"\'<>]+\.mp4[^\s"\'<>]*', r.text))
print("Found MP4 URLs:", len(mp4_urls))
for u in list(mp4_urls)[:5]:
    print(" -", u)

import os
from dotenv import load_dotenv
load_dotenv()
from google import genai

client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))

for m in ["gemini-3.8-flash", "gemini-3.8-flash-lite", "gemini-3.5-flash", "gemini-flash-latest"]:
    try:
        resp = client.models.generate_content(
            model=m,
            contents="Say 'OK'"
        )
        print(f"SUCCESS with {m}: {resp.text.strip()}")
        break
    except Exception as e:
        print(f"FAILED {m}: {e}")

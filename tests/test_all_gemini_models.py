import os
import sys
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
from dotenv import load_dotenv
load_dotenv()
from google import genai

client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))

models_to_test = [
    "gemini-flash-latest",
    "gemini-flash-lite-latest",
    "gemini-3.5-flash",
    "gemini-3.5-flash-lite",
    "gemini-3.8-flash-lite",
    "gemini-3.1-flash-lite",
    "gemini-pro-latest",
    "gemini-3.1-pro-preview"
]

working = []
for m in models_to_test:
    try:
        resp = client.models.generate_content(
            model=m,
            contents="Say 'OK'"
        )
        print(f"✅ WORKING: {m} -> {resp.text.strip()}")
        working.append(m)
    except Exception as e:
        print(f"❌ FAILED: {m} -> {str(e)[:100]}")

print("\nWORKING MODELS LIST:", working)

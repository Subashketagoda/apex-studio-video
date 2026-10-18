import sys
import time
from pathlib import Path
from dotenv import load_dotenv

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

load_dotenv()
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from core.pipeline import ShortsPipeline

print("=== Running Full Shorts Pipeline Test ===", flush=True)
t0 = time.time()
pipeline = ShortsPipeline()
res = pipeline.run("The Deep Sea Mystery", auto_approve_scenes=True)
print(f"\n🎉 SUCCESS in {time.time()-t0:.2f}s!", flush=True)
print(f"Video file: {res.final_video_path}", flush=True)
print(f"File exists: {Path(res.final_video_path).exists()}", flush=True)
print(f"File size: {Path(res.final_video_path).stat().st_size / (1024*1024):.2f} MB", flush=True)

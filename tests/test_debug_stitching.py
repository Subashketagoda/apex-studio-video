import os
import sys
import time
from pathlib import Path
from dotenv import load_dotenv

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

load_dotenv()
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from core.tts_engine import TTSEngine
from core.media_fetcher import MediaFetcher
from core.schemas import VisualSegment
from core.video_editor import VideoEditor

print(">>> [1] Testing Voiceover with Edge-TTS...", flush=True)
t0 = time.time()
tts = TTSEngine(provider="edge-tts")
audio_res = tts.generate_voiceover(
    text="Scientists exploring deep ocean trenches made a discovery that defies explanation.",
    filename="test_voiceover.mp3"
)
print(f">>> [1 Done] in {time.time()-t0:.2f}s | Audio Duration: {audio_res.duration_seconds}s | Words: {len(audio_res.words_timing)}", flush=True)

print(">>> [2] Testing Media Fetcher...", flush=True)
t1 = time.time()
fetcher = MediaFetcher()
segs = [
    VisualSegment(order=1, search_query="galaxy stars", scene_description="Space", approx_duration_sec=5.0),
    VisualSegment(order=2, search_query="ocean waves underwater", scene_description="Ocean", approx_duration_sec=5.0)
]
clips = fetcher.fetch_all_segments(segs)
clip_paths = [c.file_path for c in clips]
print(f">>> [2 Done] in {time.time()-t1:.2f}s | Clips: {clip_paths}", flush=True)

print(">>> [3] Testing Video Editor...", flush=True)
t2 = time.time()
editor = VideoEditor()
out = editor.build_short_video(
    audio_result=audio_res,
    clip_paths=clip_paths,
    output_filename="test_stitched_debug.mp4"
)
print(f">>> [3 Done] in {time.time()-t2:.2f}s | Output: {out}", flush=True)

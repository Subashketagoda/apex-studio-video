import sys
import time
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from core.tts_engine import AudioResult, WordTiming
from core.video_editor import VideoEditor

clips = [str(p.resolve()) for p in Path("temp/clips").glob("*.mp4") if p.stat().st_size > 1000000][:3]
print(f"Testing with {len(clips)} existing clips: {[Path(c).name for c in clips]}", flush=True)

# Mock audio result
mock_words = [
    WordTiming(word="THIS", start=0.0, end=0.4),
    WordTiming(word="MYSTERY", start=0.4, end=0.9),
    WordTiming(word="SHOCKED", start=0.9, end=1.4),
    WordTiming(word="SCIENTISTS", start=1.4, end=2.0),
    WordTiming(word="WORLDWIDE", start=2.0, end=2.8),
]
audio_res = AudioResult(
    audio_path=str(Path("temp/voiceover_1.mp3").resolve() if Path("temp/voiceover_1.mp3").exists() else Path("temp/test_voiceover.mp3").resolve()),
    duration_seconds=15.0,
    words_timing=mock_words
)
print(f"Audio file: {audio_res.audio_path} exists? {Path(audio_res.audio_path).exists()}", flush=True)

editor = VideoEditor()
t0 = time.time()
print("Starting build_short_video...", flush=True)
out = editor.build_short_video(
    audio_result=audio_res,
    clip_paths=clips,
    output_filename="test_speed_result.mp4"
)
print(f"DONE in {time.time()-t0:.2f}s! Output: {out}", flush=True)

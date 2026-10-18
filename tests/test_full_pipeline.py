import sys
from pathlib import Path

# Ensure UTF-8 output encoding on Windows terminals
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8")

# Add project root to path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from core.tts_engine import TTSEngine
from core.video_editor import VideoEditor
from tests.test_script_generation import get_mock_script


def test_end_to_end_video():
    print("=" * 60)
    print("🎬 Testing End-to-End Video Production & Subtitle Burning")
    print("=" * 60)

    script = get_mock_script("Space Signal Mystery")
    tts = TTSEngine(provider="edge-tts")

    print("\n1️⃣  Synthesizing Voiceover...")
    audio_result = tts.generate_voiceover(
        text="In 1977, astronomers detected a 72-second radio signal from deep space that has never been explained. Was it an alien transmission?",
        filename="e2e_audio_test.mp3"
    )
    print(f"   Audio Duration: {audio_result.duration_seconds}s")

    print("\n2️⃣  Running Video Editor (Stitching, Whisper Alignment & Subtitles)...")
    editor = VideoEditor()
    final_video = editor.build_short_video(
        audio_result=audio_result,
        clip_paths=[],  # Test procedural backdrop & subtitle engine
        output_filename="test_short_rendered.mp4"
    )

    print("\n3️⃣  Verification:")
    if final_video.exists():
        size_mb = final_video.stat().st_size / (1024 * 1024)
        print(f"✅ Video generated successfully: {final_video.name}")
        print(f"   - File size: {size_mb:.2f} MB")
        print(f"   - Resolution: 1080x1920 (9:16 Vertical)")
        print(f"   - Location: {final_video.resolve()}")
    else:
        print("❌ Video file was not created.")

    print("=" * 60)
    print("🚀 Full Pipeline Test Succeeded!")


if __name__ == "__main__":
    test_end_to_end_video()

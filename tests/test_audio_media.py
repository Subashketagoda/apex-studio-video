import sys
import argparse
from pathlib import Path

# Ensure UTF-8 output encoding on Windows terminals
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8")

# Add project root to path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from core.config import AppConfig
from core.tts_engine import TTSEngine
from core.media_fetcher import MediaFetcher
from tests.test_script_generation import get_mock_script


def run_audio_media_test(topic: str = "Space Mysteries"):
    print("=" * 60)
    print("🎧 Testing Step 2: Audio & Media Generation")
    print("=" * 60)

    # 1. Get script text
    script = get_mock_script(topic)
    print(f"📖 Voiceover Text ({len(script.voiceover_text.split())} words):")
    print(f'"{script.voiceover_text[:120]}..."')

    # 2. Test TTS (Edge-TTS is free, realistic and requires no API key)
    print(f"\n🎙️ Generating voiceover using Edge-TTS ({AppConfig.EDGE_TTS_VOICE})...")
    tts = TTSEngine(provider="edge-tts")
    try:
        audio_result = tts.generate_voiceover(
            text=script.voiceover_text,
            filename="test_voiceover.mp3"
        )
        print(f"✅ Voiceover generated successfully!")
        print(f"   - File: {audio_result.audio_path}")
        print(f"   - Exact Duration: {audio_result.duration_seconds}s")
        print(f"   - Word Timings Extracted: {len(audio_result.words_timing)} words")
        if audio_result.words_timing:
            first_few = [f"{w.word} ({w.start}s-{w.end}s)" for w in audio_result.words_timing[:5]]
            print(f"   - Sample Timings: {', '.join(first_few)}")
    except Exception as e:
        print(f"❌ Voiceover generation failed: {e}")
        return

    # 3. Test Pexels Media Fetcher
    print("\n🎬 Testing Pexels Stock Video Search...")
    fetcher = MediaFetcher()
    if not AppConfig.PEXELS_API_KEY:
        print("⚠️  PEXELS_API_KEY not configured in .env.")
        print("   Get a free API key at: https://www.pexels.com/api/")
        print("   When configured, it automatically downloads 9:16 vertical 1080x1920 HD video clips.")
    else:
        sample_query = script.visual_segments[0].search_query
        print(f"🔎 Querying Pexels portrait clip for: '{sample_query}'...")
        clip = fetcher.fetch_clip_for_query(query=sample_query, order=1)
        if clip:
            print(f"✅ Downloaded Clip: {clip.file_path}")
            print(f"   - Dimensions: {clip.width}x{clip.height}")
            print(f"   - Duration: {clip.duration}s")
        else:
            print("⚠️ Could not download clip (check API key or query).")

    print("\n" + "=" * 60)
    print("🚀 Step 2 Audio Verification Complete! Audio is ready for MoviePy synchronization.")
    print("=" * 60)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Test Step 2: Audio & Media Generation")
    parser.add_argument("--topic", type=str, default="Space Mysteries", help="Topic for test script")
    args = parser.parse_args()

    run_audio_media_test(topic=args.topic)

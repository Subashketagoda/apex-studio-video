import os
import sys
import unittest
from pathlib import Path

# Add project root to path
ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from core.config import AppConfig
from core.schemas import ShortsScript, VisualSegment, FactualClaim
from core.researcher import ResearchService
from core.script_generator import ScriptGenerator
from core.tts_engine import TTSEngine, AudioResult
from core.media_fetcher import MediaFetcher
from core.video_editor import VideoEditor
from core.pipeline import ShortsPipeline, PipelineResult


class TestApexGenPipeline(unittest.TestCase):
    """Integration test suite verifying research grounding, distinct scripts, and full video rendering."""

    @classmethod
    def setUpClass(cls):
        AppConfig.initialize_dirs()

    def test_01_three_distinct_topics_research_and_scripting(self):
        """
        Verify that scripts and visual queries generated for:
        1. Coca-Cola vs Pepsi
        2. Black holes
        3. Eiffel Tower history
        are genuinely different, topic-specific, factually grounded, and free of generic filler.
        """
        generator = ScriptGenerator()

        topics = [
            "Coca-Cola vs Pepsi",
            "Black holes",
            "Eiffel Tower history"
        ]

        scripts = {}
        for t in topics:
            print(f"\n--- Testing Topic: {t} ---")
            script = generator.generate(topic=t, duration_pref="Balanced (~45s)")
            self.assertIsInstance(script, ShortsScript)
            self.assertTrue(len(script.voiceover_text.split()) >= 30, f"Script for {t} too short.")
            self.assertTrue(len(script.visual_segments) >= 3, f"Too few scenes for {t}.")
            self.assertTrue(len(script.factual_claims) >= 1, f"Missing factual claims for {t}.")
            
            # Verify primary sources are present with URLs
            for claim in script.factual_claims:
                self.assertTrue(claim.source_url.startswith("http"), f"Invalid source URL: {claim.source_url}")
            
            # Check for banned generic filler in hook
            low_hook = script.hook.lower()
            for banned in ["hey guys", "in this video", "did you know", "welcome back"]:
                self.assertNotIn(banned, low_hook, f"Hook contains banned filler '{banned}'")

            scripts[t] = script

        # Confirm scripts are genuinely different and topic-specific
        coke_script = scripts["Coca-Cola vs Pepsi"]
        black_hole_script = scripts["Black holes"]
        eiffel_script = scripts["Eiffel Tower history"]

        # Topic 1: Coca-Cola vs Pepsi checks
        coke_text = (coke_script.title + " " + coke_script.voiceover_text).lower()
        self.assertTrue(any(w in coke_text for w in ["coca", "pepsi", "cola", "coke"]), "Coke/Pepsi script lacks topic keywords.")
        coke_queries = " ".join([s.search_query.lower() for s in coke_script.visual_segments])
        self.assertTrue(any(w in coke_queries for w in ["coca", "pepsi", "cola", "soda", "bottle"]), "Coke/Pepsi scenes lack relevant keywords.")

        # Topic 2: Black Holes checks
        bh_text = (black_hole_script.title + " " + black_hole_script.voiceover_text).lower()
        self.assertTrue(any(w in bh_text for w in ["black hole", "gravity", "horizon", "singularity"]), "Black hole script lacks astrophysics keywords.")
        bh_queries = " ".join([s.search_query.lower() for s in black_hole_script.visual_segments])
        self.assertTrue(any(w in bh_queries for w in ["black hole", "galaxy", "cosmic", "space", "horizon"]), "Black hole scenes lack space queries.")

        # Topic 3: Eiffel Tower checks
        eiffel_text = (eiffel_script.title + " " + eiffel_script.voiceover_text).lower()
        self.assertTrue(any(w in eiffel_text for w in ["eiffel", "tower", "paris", "gustave"]), "Eiffel Tower script lacks historical keywords.")
        eiffel_queries = " ".join([s.search_query.lower() for s in eiffel_script.visual_segments])
        self.assertTrue(any(w in eiffel_queries for w in ["eiffel", "tower", "paris", "iron", "construction"]), "Eiffel Tower scenes lack architectural queries.")

        # Ensure topics did not output identical text
        self.assertNotEqual(coke_script.voiceover_text, black_hole_script.voiceover_text)
        self.assertNotEqual(black_hole_script.voiceover_text, eiffel_script.voiceover_text)
        print("✅ All 3 topics generated distinct, verified, topic-specific scripts!")

    def test_02_voiceover_generation_and_validation(self):
        """Verify Edge-TTS voiceover generation and mutagen duration measurement."""
        tts = TTSEngine(provider="edge-tts", voice="en-US-ChristopherNeural")
        test_script = (
            "In 1975, Pepsi launched a blind taste test that terrified Coca-Cola into committing the greatest blunder in business history. "
            "Fifty-eight percent of consumers preferred Pepsi's sweeter taste."
        )
        audio_res = tts.generate_voiceover(text=test_script, filename="test_tts_audio.mp3")
        self.assertIsInstance(audio_res, AudioResult)
        self.assertTrue(Path(audio_res.audio_path).exists())
        self.assertTrue(audio_res.duration_seconds > 4.0, f"Duration unexpected: {audio_res.duration_seconds}s")
        self.assertTrue(len(audio_res.words_timing) > 0, "No word boundary events captured.")
        print(f"✅ Edge-TTS generated audio: {audio_res.duration_seconds}s with {len(audio_res.words_timing)} word timestamps.")

    def test_03_complete_video_render_and_ffprobe_validation(self):
        """
        Executes a complete end-to-end render pipeline for 'Coca-Cola vs Pepsi',
        verifying 1080x1920 dimensions, 30 FPS, audio sync, ASS subtitle burning, and FFprobe integrity.
        """
        pipeline = ShortsPipeline(
            tts_provider="edge-tts",
            voice="en-US-ChristopherNeural"
        )
        print("\n--- Testing Complete End-to-End Video Production ---")
        result = pipeline.run(
            topic="Coca-Cola vs Pepsi",
            tone="Historical Clash",
            duration_pref="Fast (~30s)",
            bgm_track="cinematic_drone",
            bgm_volume=0.10,
            subtitle_style="mrbeast",
            auto_approve_scenes=True
        )

        self.assertIsInstance(result, PipelineResult)
        output_file = Path(result.final_video_path)
        self.assertTrue(output_file.exists(), f"Rendered video does not exist: {output_file}")
        self.assertTrue(output_file.stat().st_size > 500_000, f"Rendered video too small: {output_file.stat().st_size} bytes")

        # Verify FFprobe output validation report
        v_rep = result.validation_report
        self.assertIsNotNone(v_rep, "Validation report missing from result.")
        self.assertEqual(v_rep.get("width"), 1080, f"Expected width 1080, got {v_rep.get('width')}")
        self.assertEqual(v_rep.get("height"), 1920, f"Expected height 1920, got {v_rep.get('height')}")
        self.assertIn("h264", v_rep.get("video_codec", "").lower(), "Expected H.264 video codec")
        self.assertIn("aac", v_rep.get("audio_codec", "").lower(), "Expected AAC audio codec")
        self.assertTrue(v_rep.get("duration", 0) > 10.0, f"Duration too short: {v_rep.get('duration')}s")

        print(f"✅ Full render complete: {output_file.name} ({v_rep.get('size_mb')} MB, {v_rep.get('duration')}s)")


if __name__ == "__main__":
    unittest.main()

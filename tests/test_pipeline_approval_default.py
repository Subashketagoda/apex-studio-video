"""Regression tests for the mandatory scene-review gate."""
import pytest

from core.config import AppConfig
from core.job_manager import JobManager
from core.pipeline import ShortsPipeline
from core.schemas import ScenePlanItem, ShortsScript, TimestampedScenePlan, VisualSegment
from core.tts_engine import AudioResult


def test_pipeline_pauses_for_scene_approval_by_default(tmp_path, monkeypatch):
    """A normal pipeline run must save review data and stop before final rendering."""
    monkeypatch.setattr(JobManager, "JOBS_FILE", tmp_path / "jobs.json")
    monkeypatch.setattr(AppConfig, "TEMP_DIR", tmp_path / "temp")
    (tmp_path / "temp").mkdir(parents=True, exist_ok=True)

    pipeline = ShortsPipeline()
    voiceover = (
        "Today we examine a small test subject in its environment, observe its movement, "
        "and explain why this simple example matters for our visual approval workflow."
    )
    script = ShortsScript(
        topic="Test topic",
        title="A Test Topic 🎬",
        hook="Here is the hook.",
        voiceover_text=voiceover,
        description="Test description.",
        visual_segments=[
            VisualSegment(
                order=1,
                search_query="test subject overview",
                scene_description="Introduce the test subject in its environment.",
            ),
            VisualSegment(
                order=2,
                search_query="test subject movement",
                scene_description="Show the test subject moving through the environment.",
            ),
            VisualSegment(
                order=3,
                search_query="test subject closeup",
                scene_description="End with a clear close-up of the test subject.",
            ),
        ],
    )
    monkeypatch.setattr(pipeline.script_generator, "generate", lambda **kwargs: script)

    audio_path = tmp_path / "voiceover.mp3"
    audio_path.write_bytes(b"fake audio for the mocked TTS result")
    monkeypatch.setattr(
        pipeline.tts_engine,
        "generate_voiceover",
        lambda **kwargs: AudioResult(
            audio_path=str(audio_path),
            duration_seconds=9.0,
            words_timing=[],
        ),
    )

    plan = TimestampedScenePlan(
        topic="Test topic",
        total_scenes=3,
        total_duration=9.0,
        scenes=[
            ScenePlanItem(
                scene_order=1,
                narration_segment="Introduce the test subject in its environment.",
                start_time=0.0,
                end_time=3.0,
                duration=3.0,
                main_subject="Test subject",
                action="Introduce the subject",
            ),
            ScenePlanItem(
                scene_order=2,
                narration_segment="Observe its movement through the environment.",
                start_time=3.0,
                end_time=6.0,
                duration=3.0,
                main_subject="Test subject",
                action="Show the subject moving",
            ),
            ScenePlanItem(
                scene_order=3,
                narration_segment="Explain why the example matters for visual approval.",
                start_time=6.0,
                end_time=9.0,
                duration=3.0,
                main_subject="Test subject",
                action="End on a clear close-up",
            ),
        ],
    )
    monkeypatch.setattr(
        "core.pipeline.ScenePlanner.create_scene_plan",
        staticmethod(lambda **kwargs: plan),
    )
    monkeypatch.setattr(
        pipeline.media_fetcher,
        "fetch_all_scenes",
        lambda **kwargs: ([], []),
    )
    monkeypatch.setattr(
        pipeline.video_editor,
        "build_short_video",
        lambda **kwargs: pytest.fail("Final render must not run before scene approval"),
    )

    result = pipeline.run(topic="Test topic")

    assert result.final_video_path == ""
    assert result.qc_report is None
    job = JobManager.get_job(result.job_id)
    assert job is not None
    assert job.status == "AWAITING_APPROVAL"
    assert job.scene_plan_data["scenes"][0]["approval_status"] == "PENDING"
    assert job.audio_path == str(audio_path)


def test_ai_visual_cache_key_changes_when_scene_direction_changes():
    """Edited prompts/actions must not silently reuse a previously generated clip."""
    from core.media_fetcher import MediaFetcher

    scene = ScenePlanItem(
        scene_order=1,
        narration_segment="A test scene.",
        start_time=0.0,
        end_time=3.0,
        duration=3.0,
        main_subject="Test subject",
        action="Show the subject from the front",
        visual_description="A clear cinematic portrait of the subject",
        required_objects=["test object"],
    )
    original_key = MediaFetcher._scene_visual_cache_key("Test topic", scene)
    scene.action = "Show the subject from a high angle"
    changed_key = MediaFetcher._scene_visual_cache_key("Test topic", scene)
    assert original_key != changed_key

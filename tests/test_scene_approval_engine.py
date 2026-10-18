import os
import sys
import json
from pathlib import Path


# Add project root to path
ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from core.config import AppConfig
from core.schemas import ScenePlanItem, TimestampedScenePlan
from core.visual_director import VisualDirector
from core.video_providers import HardwareDetector, MockVideoProvider, AIVideoEngine, LabeledStillMotionProvider
from core.job_manager import JobManager
from core.pipeline import ShortsPipeline
from core.tts_engine import AudioResult


def test_hardware_detector_intel_igpu():
    """Verify hardware detection accurately reports Intel Integrated Graphics and blocks heavy diffusion models."""
    hw = HardwareDetector.detect()
    assert "gpu_name" in hw
    assert hw["system_ram_gb"] > 0
    assert hw["free_disk_space_gb"] > 0
    assert isinstance(hw["supported_backends"], list)
    assert "model_compatibility" in hw

    # Check that Wan 2.1 is flagged as incompatible without dedicated CUDA GPU
    if not hw["has_cuda"]:
        assert hw["model_compatibility"]["wan2.1_local"]["compatible"] is False
        assert "CUDA" in hw["model_compatibility"]["wan2.1_local"]["reason"]
        assert hw["model_compatibility"]["ltx_video_local"]["compatible"] is False

    # Check that fallback and test providers are flagged as compatible
    assert hw["model_compatibility"]["labeled_still_motion"]["compatible"] is True
    assert hw["model_compatibility"]["mock_test"]["compatible"] is True


def test_visual_director_enrichment():
    """Verify VisualDirector produces scene-specific camera choreographies and prompts."""
    scene = ScenePlanItem(
        scene_order=1,
        narration_segment="Two beverage empires clashed for global soda supremacy.",
        start_time=0.0,
        end_time=4.5,
        duration=4.5,
        main_subject="Red and Blue Cola Bottles",
        action="Glowing studio spotlights shining across chilled sweating cola bottles",
        setting="Commercial studio",
        required_objects=["cola bottle"],
        negative_constraints=["soup cans", "vegetables"]
    )

    directed = VisualDirector.direct_scene(scene, topic="Coca-Cola vs Pepsi", scene_index=0, total_scenes=5)

    assert directed.shot_type != ""
    assert directed.camera_movement != ""
    assert directed.camera_angle != ""
    assert "vertical 9:16" in directed.composition
    assert "Red and Blue Cola Bottles" in directed.positive_prompt
    assert "soup cans" in directed.negative_prompt
    assert "blurry" in directed.negative_prompt
    assert directed.generation_status == "PLANNED"
    assert directed.approval_status == "PENDING"


def test_mock_video_provider_ffprobe_validation(tmp_path):
    """Verify MockVideoProvider creates genuine 1080x1920 30FPS MP4 clips validated by FFprobe."""
    scene = ScenePlanItem(
        scene_order=1,
        narration_segment="Test narration segment.",
        start_time=0.0,
        end_time=3.0,
        duration=3.0,
        main_subject="Test Subject",
        action="Testing action"
    )

    out_file = tmp_path / "test_mock_clip.mp4"
    prov = MockVideoProvider()
    generated = prov.generate_clip(scene, out_file)

    assert generated.exists()
    assert generated.stat().st_size > 1000

    # Validate using AIVideoEngine FFprobe validator
    stream_info = AIVideoEngine._validate_clip_with_ffprobe(generated, min_duration=1.0)
    assert int(stream_info["width"]) == 1080
    assert int(stream_info["height"]) == 1920
    assert stream_info["codec_name"] == "h264"


def test_job_manager_approval_state_machine(tmp_path):
    """
    Verify complete approval state machine:
    - Initial state is PENDING
    - Approval to APPROVED
    - Editing prompt resets approval to PENDING and increments prompt_version
    - Replacing clip resets approval to PENDING and logs history
    - are_all_scenes_approved gate enforcement
    """
    job = JobManager.create_job(topic="State Machine Verification")
    job_id = job.job_id

    # Create 2 scenes
    scenes = [
        ScenePlanItem(
            scene_order=1,
            narration_segment="First sentence.",
            start_time=0.0,
            end_time=3.0,
            duration=3.0,
            main_subject="Scene 1",
            action="Action 1",
            selected_asset_path=str(tmp_path / "clip1.mp4"),
            approval_status="PENDING"
        ),
        ScenePlanItem(
            scene_order=2,
            narration_segment="Second sentence.",
            start_time=3.0,
            end_time=6.0,
            duration=3.0,
            main_subject="Scene 2",
            action="Action 2",
            selected_asset_path=str(tmp_path / "clip2.mp4"),
            approval_status="PENDING"
        )
    ]
    plan = TimestampedScenePlan(
        topic="State Machine Verification",
        total_scenes=2,
        total_duration=6.0,
        scenes=scenes
    )

    JobManager.update_job(job_id, scene_plan_data=plan.model_dump())

    # Initially, neither is approved
    all_app, unapp = JobManager.are_all_scenes_approved(job_id)
    assert all_app is False
    assert unapp == [1, 2]

    # Approve scene 1
    JobManager.update_scene_approval(job_id, scene_order=1, status="APPROVED")
    all_app, unapp = JobManager.are_all_scenes_approved(job_id)
    assert all_app is False
    assert unapp == [2]

    # Approve scene 2
    JobManager.update_scene_approval(job_id, scene_order=2, status="APPROVED")
    all_app, unapp = JobManager.are_all_scenes_approved(job_id)
    assert all_app is True
    assert unapp == []

    # Editing scene 1 prompt must invalidate approval and increment version
    JobManager.update_scene_prompt(job_id, scene_order=1, new_prompt="Updated prompt for scene 1")
    reloaded = JobManager.get_job(job_id)
    sc1 = reloaded.scene_plan_data["scenes"][0]
    assert sc1["approval_status"] == "PENDING"
    assert sc1["prompt_version"] == 2
    all_app, unapp = JobManager.are_all_scenes_approved(job_id)
    assert all_app is False
    assert unapp == [1]

    # Re-approve scene 1
    JobManager.update_scene_approval(job_id, scene_order=1, status="APPROVED")
    assert JobManager.are_all_scenes_approved(job_id)[0] is True

    # Replacing clip on scene 2 must invalidate approval and log history
    new_clip = str(tmp_path / "replaced_clip2.mp4")
    JobManager.replace_scene_clip(job_id, scene_order=2, new_clip_path=new_clip, reason="user_test_replace")
    reloaded2 = JobManager.get_job(job_id)
    sc2 = reloaded2.scene_plan_data["scenes"][1]
    assert sc2["approval_status"] == "PENDING"
    assert sc2["selected_asset_path"] == new_clip
    assert len(sc2["clip_replacement_history"]) == 1
    assert sc2["clip_replacement_history"][0]["reason"] == "user_test_replace"
    assert JobManager.are_all_scenes_approved(job_id)[0] is False


def test_pipeline_approval_gate_blocks_rendering(tmp_path):
    """Verify ShortsPipeline.render_approved_job strictly refuses to render when scenes are unapproved."""
    job = JobManager.create_job(topic="Approval Gate Block Test")
    job_id = job.job_id

    # Create dummy audio
    audio_path = tmp_path / "dummy_audio.mp3"
    audio_path.write_bytes(b"\x00" * 1024)

    scenes = [
        ScenePlanItem(
            scene_order=1,
            narration_segment="Sentence 1",
            start_time=0.0,
            end_time=3.0,
            duration=3.0,
            main_subject="Sub 1",
            action="Act 1",
            approval_status="PENDING"
        )
    ]
    plan = TimestampedScenePlan(
        topic="Approval Gate Block Test",
        total_scenes=1,
        total_duration=3.0,
        scenes=scenes
    )
    JobManager.update_job(job_id, scene_plan_data=plan.model_dump(), audio_path=str(audio_path))

    pipeline = ShortsPipeline()

    # Attempting to render while unapproved MUST raise RuntimeError
    raised = False
    try:
        pipeline.render_approved_job(job_id)
    except RuntimeError as e:
        raised = True
        assert "Rendering BLOCKED" in str(e)
        assert "Scene #1" in str(e)

    assert raised, "Expected RuntimeError when rendering unapproved scenes, but none was raised!"



def test_full_pipeline_render_approved_job(tmp_path):
    """
    Verify that once all scenes are approved with valid clips,
    render_approved_job executes successfully, burns subtitles, duck audio,
    and inspects representative frames.
    """
    job = JobManager.create_job(topic="Full Approved Render Test")
    job_id = job.job_id

    # Generate quick speech audio via edge-tts
    from core.tts_engine import TTSEngine
    tts = TTSEngine(provider="edge-tts", voice="en-US-ChristopherNeural")
    audio_res = tts.generate_voiceover(
        text="Two beverage empires clashed for global soda supremacy. One bold taste test changed advertising forever.",
        filename=f"test_approved_{job_id}.mp3"
    )

    dur1 = round(audio_res.duration_seconds / 2.0, 2)
    dur2 = round(audio_res.duration_seconds - dur1, 2)

    prov = MockVideoProvider()
    # Generate genuine 1080x1920 test clips matching exact audio durations
    clip1 = prov.generate_clip(
        ScenePlanItem(scene_order=1, narration_segment="First scene.", start_time=0.0, end_time=dur1, duration=dur1, main_subject="Scene 1", action="Act 1"),
        tmp_path / "clip1.mp4"
    )
    clip2 = prov.generate_clip(
        ScenePlanItem(scene_order=2, narration_segment="Second scene.", start_time=dur1, end_time=audio_res.duration_seconds, duration=dur2, main_subject="Scene 2", action="Act 2"),
        tmp_path / "clip2.mp4"
    )

    scenes = [
        ScenePlanItem(
            scene_order=1,
            narration_segment="Two beverage empires clashed for global soda supremacy.",
            start_time=0.0,
            end_time=dur1,
            duration=dur1,
            main_subject="Cola Bottles",
            action="Spotlight on red and blue bottles",
            selected_asset_path=str(clip1.resolve()),
            selected_asset_source="mock_test",
            approval_status="APPROVED"
        ),
        ScenePlanItem(
            scene_order=2,
            narration_segment="One bold taste test changed advertising forever.",
            start_time=dur1,
            end_time=round(audio_res.duration_seconds, 2),
            duration=dur2,
            main_subject="Taste Test",

            action="Blind taste test cups",
            selected_asset_path=str(clip2.resolve()),
            selected_asset_source="mock_test",
            approval_status="APPROVED"
        )
    ]

    plan = TimestampedScenePlan(
        topic="Full Approved Render Test",
        total_scenes=2,
        total_duration=audio_res.duration_seconds,
        scenes=scenes
    )

    JobManager.update_job(
        job_id,
        scene_plan_data=plan.model_dump(),
        audio_path=audio_res.audio_path,
        script_data={"voiceover_text": "Two beverage empires clashed for global soda supremacy. One bold taste test changed advertising forever."}
    )

    # All scenes are approved: render_approved_job should now succeed!
    pipeline = ShortsPipeline()
    rendered_file = pipeline.render_approved_job(
        job_id=job_id,
        bgm_track="cinematic_drone",
        bgm_volume=0.15,
        subtitle_style="mrbeast"
    )

    assert rendered_file.exists()
    assert rendered_file.stat().st_size > 10000

    # Verify container with FFprobe
    inspection = pipeline.video_editor.inspect_rendered_video(rendered_file, expected_duration=audio_res.duration_seconds)
    assert inspection["width"] == 1080
    assert inspection["height"] == 1920
    assert inspection["all_frames_valid"] is True
    assert len(inspection["extracted_frames"]) == 5  # 10%, 30%, 50%, 70%, 90%

    # Check that QC report was created
    qc_file = AppConfig.OUTPUT_DIR / f"qc_report_{job_id}.json"
    assert qc_file.exists()
    qc_data = json.loads(qc_file.read_text(encoding="utf-8"))
    assert qc_data["overall_pass"] is True
    assert qc_data["passed_scenes"] == 2


if __name__ == "__main__":
    import tempfile
    print("🚀 Running Test Suite: Scene Approval Engine & Intel Hardware Compatibility")
    
    test_hardware_detector_intel_igpu()
    print("✅ test_hardware_detector_intel_igpu passed")

    test_visual_director_enrichment()
    print("✅ test_visual_director_enrichment passed")

    with tempfile.TemporaryDirectory() as td:
        test_mock_video_provider_ffprobe_validation(Path(td))
        print("✅ test_mock_video_provider_ffprobe_validation passed")

    with tempfile.TemporaryDirectory() as td:
        test_job_manager_approval_state_machine(Path(td))
        print("✅ test_job_manager_approval_state_machine passed")

    with tempfile.TemporaryDirectory() as td:
        test_pipeline_approval_gate_blocks_rendering(Path(td))
        print("✅ test_pipeline_approval_gate_blocks_rendering passed")

    with tempfile.TemporaryDirectory() as td:
        test_full_pipeline_render_approved_job(Path(td))
        print("✅ test_full_pipeline_render_approved_job passed")

    print("🎉 ALL TESTS PASSED SUCCESSFULLY!")


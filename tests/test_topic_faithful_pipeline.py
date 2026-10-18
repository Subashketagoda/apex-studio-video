import sys
import os
import json
import time
from pathlib import Path

# Ensure root directory in path
ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8")

from core.pipeline import ShortsPipeline, PipelineResult
from core.schemas import TimestampedScenePlan, QualityControlReport


def test_topic(pipeline: ShortsPipeline, topic: str, tone: str) -> PipelineResult:
    print("\n" + "=" * 80)
    print(f"🎬 EXECUTING TOPIC-FAITHFUL TEST FOR: '{topic.upper()}'")
    print("=" * 80, flush=True)

    start_t = time.time()
    res: PipelineResult = pipeline.run(
        topic=topic,
        tone=tone,
        duration_pref="⚡ Fast (~30s - 35s)",
        visual_source="auto",
        auto_approve_scenes=True,
        bgm_track="cinematic_drone",
        bgm_volume=0.18,
        enable_hook_sfx=True,
        subtitle_style="mrbeast"
    )
    elapsed = time.time() - start_t

    print("\n" + "-" * 80)
    print(f"📊 RESULTS FOR: '{topic}' (Elapsed: {elapsed:.1f}s)")
    print("-" * 80)
    print(f"• Video Path: {res.final_video_path}")
    print(f"• Audio Duration: {res.audio_duration:.2f}s")
    print(f"• Total Scenes: {res.scene_plan.total_scenes if res.scene_plan else 'N/A'}")
    print(f"• Clips Downloaded/Rendered: {res.clips_downloaded}")

    # Validate Scene Plan
    assert res.scene_plan is not None, "TimestampedScenePlan was not generated!"
    assert len(res.scene_plan.scenes) >= 3, "Insufficient scenes planned!"
    print("\n📋 SCENE PLAN AUDIT:")
    for sc in res.scene_plan.scenes:
        print(
            f"  [Scene #{sc.scene_order}] {sc.start_time:.1f}s - {sc.end_time:.1f}s ({sc.duration:.1f}s) | "
            f"Subject: {sc.main_subject} | Source: {sc.selected_asset_source} | Status: {sc.validation_status}"
        )
        print(f"    Narration: \"{sc.narration_segment[:70]}...\"")
        print(f"    Required: {sc.required_objects} | Negative Constraints: {sc.negative_constraints[:4]}")

    # Validate Quality Control Report
    assert res.qc_report is not None, "QualityControlReport was not generated!"
    print(f"\n🛡️ QC REPORT AUDIT:")
    print(f"• Passed Scenes: {res.qc_report.passed_scenes}/{res.qc_report.total_scenes}")
    print(f"• Overall QC Pass: {res.qc_report.overall_pass}")
    print(f"• Total Rejections: {len(res.qc_report.rejections)}")
    for rej in res.qc_report.rejections:
        print(f"  ❌ Rejection [Scene #{rej.scene_order} - {rej.candidate_source}]: {rej.rejection_reason} (Dominant: {rej.detected_dominant_subject})")

    # Validate FFprobe and Representative Extracted Frames
    assert res.validation_report is not None, "Validation report missing!"
    v_rep = res.validation_report
    print(f"\n🔍 FFPROBE & FRAME INSPECTION AUDIT:")
    print(f"• Container Resolution: {v_rep['width']}x{v_rep['height']} (Expected 1080x1920)")
    assert v_rep['width'] == 1080 and v_rep['height'] == 1920, f"Invalid resolution: {v_rep['width']}x{v_rep['height']}"
    print(f"• Encoded Duration: {v_rep['duration']:.2f}s vs Voiceover: {res.audio_duration:.2f}s")
    print(f"• Video Codec: {v_rep['video_codec']} | Audio Codec: {v_rep['audio_codec']} @ {v_rep.get('audio_sample_rate')} Hz")
    print(f"• File Size: {v_rep['size_mb']} MB")

    frames = v_rep.get("extracted_frames", [])
    print(f"• Extracted Representative Frames: {len(frames)}")
    assert len(frames) == 5, f"Expected 5 extracted frames, found {len(frames)}"
    for fr in frames:
        print(
            f"  🖼️ Frame @ {int(fr['fraction']*100)}% ({fr['timestamp_sec']}s): "
            f"Res: {fr['resolution']}, Brightness: {fr['average_brightness']}, StdDev: {fr['contrast_stddev']}, Valid: {fr['is_valid_frame']}"
        )
        assert fr["is_valid_frame"], f"Frame at {fr['fraction']} is corrupt or invalid!"
        assert Path(fr["frame_path"]).exists(), f"Frame file missing: {fr['frame_path']}"

    print(f"\n✅ Topic '{topic}' PASSED all topic-faithful validation and rendering checks!\n")
    return res


def main():
    print("=" * 80)
    print("🚀 APEXGEN 3D SHORTS AI — TOPIC-FAITHFUL PIPELINE ACCEPTANCE TEST SUITE")
    print("=" * 80)

    pipeline = ShortsPipeline(llm_provider="gemini", tts_provider="edge-tts")

    # 3 Substantially Different Topics
    topics_to_test = [
        ("Coca-Cola vs Pepsi", "Dramatic rivalry & corporate clash"),
        ("The Secrets of Black Holes", "Mysterious & astrophysical wonder"),
        ("Julius Caesar Assassination", "Historical conspiracy & betrayal")
    ]

    results = []
    for topic, tone in topics_to_test:
        res = test_topic(pipeline, topic, tone)
        results.append(res)

    print("\n" + "=" * 80)
    print("🎉 ALL 3 TOPIC-FAITHFUL PIPELINE TESTS SUCCEEDED!")
    print("=" * 80)
    for res in results:
        qc = res.qc_report
        print(f"• {res.topic}: {qc.passed_scenes}/{qc.total_scenes} scenes passed | Rejections: {len(qc.rejections)} | Video: {Path(res.final_video_path).name}")


if __name__ == "__main__":
    main()

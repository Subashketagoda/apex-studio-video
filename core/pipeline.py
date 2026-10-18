import time
import json
from pathlib import Path
from typing import Optional, List, Dict, Any, Callable
from pydantic import BaseModel, Field

from core.config import AppConfig
from core.schemas import ShortsScript, TimestampedScenePlan, QualityControlReport, AssetRejectionRecord
from core.script_generator import ScriptGenerator
from core.tts_engine import TTSEngine, AudioResult
from core.scene_planner import ScenePlanner
from core.media_fetcher import MediaFetcher, DownloadedClip
from core.video_editor import VideoEditor
from core.youtube_publisher import YouTubePublisher
from core.job_manager import JobManager, JobRecord


class PipelineResult(BaseModel):
    """Complete results from an automated Shorts pipeline run."""
    job_id: str
    topic: str
    script: ShortsScript
    scene_plan: Optional[TimestampedScenePlan] = None
    audio_path: str
    audio_duration: float
    clips_downloaded: int
    final_video_path: str
    validation_report: Optional[Dict[str, Any]] = None
    qc_report: Optional[QualityControlReport] = None


class ShortsPipeline:
    """
    End-to-End Autonomous Viral Shorts Pipeline:
    1. Researches and scripts topic with verified primary sources.
    2. Synthesizes voiceover audio with sub-second timestamps.
    3. Plans timestamp-synchronized scenes with strict visual requirements.
    4. Sourcing & relevance validation of footage across a 4-tier pipeline.
    5. Mixes audio with ducked background music & burns active ASS subtitles.
    6. Validates container integrity via FFprobe & inspects representative frames.
    """

    def __init__(
        self,
        llm_provider: Optional[str] = None,
        tts_provider: Optional[str] = None,
        voice: Optional[str] = None,
    ):
        self.script_generator = ScriptGenerator(provider=llm_provider)
        self.tts_engine = TTSEngine(provider=tts_provider, voice=voice)
        self.media_fetcher = MediaFetcher()
        self.video_editor = VideoEditor()
        self.youtube_publisher = YouTubePublisher()

    def run(
        self,
        topic: str,
        tone: str = "suspenseful & fascinating",
        progress_callback: Optional[Callable[[str, float], None]] = None,
        override_script: Optional[ShortsScript] = None,
        duration_pref: Optional[str] = None,
        job_id: Optional[str] = None,
        **kwargs: Any,
    ) -> PipelineResult:
        """
        Executes end-to-end pipeline with stage logging and job persistence.
        """
        # Create or resume job record
        if not job_id:
            job = JobManager.create_job(topic=topic)
            job_id = job.job_id
        else:
            JobManager.update_job(job_id, status="RUNNING", stage="Starting pipeline")

        def update_progress(message: str, step_fraction: float, stage_name: str):
            JobManager.update_job(
                job_id,
                progress=step_fraction,
                stage=stage_name,
                log_msg=message
            )
            if progress_callback:
                progress_callback(message, step_fraction)
            print(f"[{int(step_fraction * 100)}%] [{stage_name}] {message}", flush=True)

        try:
            # Stage 1: Research & Scripting
            update_progress("Researching verified historical/scientific facts...", 0.10, "RESEARCHING")
            if override_script:
                script = override_script
                update_progress("Using reviewed script configuration.", 0.25, "SCRIPTING")
            else:
                update_progress("Synthesizing script grounded in primary sources...", 0.20, "SCRIPTING")
                script = self.script_generator.generate(
                    topic=topic,
                    tone=tone,
                    duration_pref=duration_pref
                )

            JobManager.update_job(job_id, script_data=script.model_dump())

            # Stage 2: Voiceover Audio
            voice_rate = kwargs.get("tts_rate", "+0%")
            voice_volume = kwargs.get("tts_volume", "+0%")
            update_progress("Generating neural voiceover audio with sub-second timing...", 0.35, "VOICEOVER")
            audio_result = self.tts_engine.generate_voiceover(
                text=script.voiceover_text,
                filename=f"voiceover_{job_id}.mp3",
                rate=voice_rate,
                volume=voice_volume
            )
            JobManager.update_job(job_id, audio_path=audio_result.audio_path)

            # Stage 2.5: Scene Planning (Strict Timestamp Synchronization)
            update_progress("Generating structured timestamped scene plan...", 0.40, "SCENE_PLANNING")
            scene_plan = ScenePlanner.create_scene_plan(
                script=script,
                audio_result=audio_result,
                topic=topic
            )
            print(f"[ShortsPipeline] 📋 Scene plan created: {len(scene_plan.scenes)} scenes covering {scene_plan.total_duration}s", flush=True)
            for sc in scene_plan.scenes:
                print(f"  • Scene #{sc.scene_order} ({sc.start_time:.1f}s - {sc.end_time:.1f}s): {sc.main_subject}", flush=True)

            JobManager.update_job(job_id, scene_plan_data=scene_plan.model_dump())

            # Stage 3: Visual Footage Acquisition via 4-Tier Priority Pipeline
            custom_clip_paths = kwargs.get("custom_clip_paths")
            visual_source = kwargs.get("visual_source", "auto")

            if custom_clip_paths and any(Path(p).exists() for p in custom_clip_paths):
                update_progress(f"Using {len(custom_clip_paths)} uploaded user media clips...", 0.60, "SOURCING_MEDIA")
                clip_paths = [str(Path(p).resolve()) for p in custom_clip_paths if Path(p).exists()]
                downloaded_clips = []
                rejections: List[AssetRejectionRecord] = []
            else:
                update_progress("Acquiring and validating topic-faithful visual assets...", 0.45, "SOURCING_MEDIA")
                downloaded_clips, rejections = self.media_fetcher.fetch_all_scenes(
                    topic=topic,
                    scene_plan=scene_plan,
                    visual_mode=visual_source,
                    progress_callback=lambda msg, frac: update_progress(msg, frac, "SOURCING_MEDIA")
                )
                clip_paths = [c.file_path for c in downloaded_clips]

            # Sync downloaded clips into scene plan items
            for i, clip in enumerate(downloaded_clips):
                if i < len(scene_plan.scenes):
                    scene_plan.scenes[i].selected_asset_path = clip.file_path
                    scene_plan.scenes[i].selected_asset_source = clip.source_tier
                    scene_plan.scenes[i].generation_status = "GENERATED"

            # Human review is the safe default. Auto-approval must be explicitly
            # enabled by trusted callers (for example, isolated integration tests).
            auto_approve = kwargs.get("auto_approve_scenes", False) is True
            if auto_approve:
                for sc in scene_plan.scenes:
                    sc.approval_status = "APPROVED"
                scene_plan.all_approved = True
                JobManager.update_job(job_id, scene_plan_data=scene_plan.model_dump())
            else:
                # Persist all review inputs before returning control to the UI.
                # Do not raise here: the generic exception handler would mark this
                # expected approval pause as FAILED and hide the reviewable job.
                pending_orders = [
                    sc.scene_order for sc in scene_plan.scenes
                    if sc.approval_status != "APPROVED"
                ]
                pending_text = ", ".join(f"Scene #{order}" for order in pending_orders) or "none"
                message = (
                    "Scene assets are ready for human review. Final rendering is "
                    f"paused until every scene is approved. Pending: {pending_text}."
                )
                JobManager.update_job(
                    job_id,
                    status="AWAITING_APPROVAL",
                    progress=0.65,
                    stage="Awaiting Human Scene Approval",
                    scene_plan_data=scene_plan.model_dump(),
                    log_msg=message,
                )
                return PipelineResult(
                    job_id=job_id,
                    topic=topic,
                    script=script,
                    scene_plan=scene_plan,
                    audio_path=audio_result.audio_path,
                    audio_duration=audio_result.duration_seconds,
                    clips_downloaded=len(downloaded_clips),
                    final_video_path="",
                    validation_report=None,
                    qc_report=None,
                )

            scene_durations = [sc.duration for sc in scene_plan.scenes]

            # Stage 4: Video Editing, Subtitle Burning & Boundary Synchronization
            update_progress("Synchronizing scene cuts, ducking BGM & burning active subtitles...", 0.80, "RENDERING")
            final_video_path = self.video_editor.build_short_video(
                audio_result=audio_result,
                clip_paths=clip_paths,
                output_filename=f"short_{job_id}.mp4",
                fallback_text=script.voiceover_text,
                progress_callback=lambda msg, frac: update_progress(msg, frac, "RENDERING"),
                bgm_track=kwargs.get("bgm_track", "cinematic_drone"),
                bgm_volume=float(kwargs.get("bgm_volume", 0.18)),
                enable_hook_sfx=bool(kwargs.get("enable_hook_sfx", True)),
                subtitle_style=kwargs.get("subtitle_style", "mrbeast"),
                subtitle_size=kwargs.get("subtitle_size", "medium"),
                watermark_text=kwargs.get("watermark_text", None),
                scene_durations=scene_durations
            )

            # Stage 5: Quality Inspection & Representative Frame Analysis
            update_progress("Inspecting rendered video and representative frames...", 0.95, "VALIDATION")
            inspection_report = self.video_editor.inspect_rendered_video(
                final_video_path,
                expected_duration=audio_result.duration_seconds
            )

            # Build Quality Control Report
            qc_report = QualityControlReport(
                job_id=job_id,
                topic=topic,
                total_scenes=len(scene_plan.scenes),
                passed_scenes=len(downloaded_clips),
                rejections=rejections,
                scene_asset_sources={c.order: c.source_tier for c in downloaded_clips},
                frame_inspection=inspection_report,
                overall_pass=inspection_report.get("all_frames_valid", True)
            )

            # Save QC Report to disk
            qc_report_path = AppConfig.OUTPUT_DIR / f"qc_report_{job_id}.json"
            qc_report_path.write_text(json.dumps(qc_report.model_dump(), indent=2), encoding="utf-8")
            print(f"[ShortsPipeline] 📄 Quality Control Report saved: {qc_report_path.name}", flush=True)

            update_progress("Short rendered and inspected successfully! 🎉", 1.0, "COMPLETED")
            JobManager.update_job(
                job_id,
                status="COMPLETED",
                progress=1.0,
                stage="Completed",
                video_path=str(final_video_path.resolve()),
                validation_report=inspection_report,
                log_msg=f"Validated {inspection_report['width']}x{inspection_report['height']} @ {inspection_report['duration']}s | Rejected: {len(rejections)}"
            )

            return PipelineResult(
                job_id=job_id,
                topic=topic,
                script=script,
                scene_plan=scene_plan,
                audio_path=audio_result.audio_path,
                audio_duration=audio_result.duration_seconds,
                clips_downloaded=len(downloaded_clips),
                final_video_path=str(final_video_path.resolve()),
                validation_report=inspection_report,
                qc_report=qc_report
            )

        except Exception as e:
            err_msg = str(e)
            print(f"[ShortsPipeline] ❌ Error: {err_msg}", flush=True)
            update_progress(f"Pipeline error: {err_msg}", 1.0, "FAILED")
            JobManager.update_job(
                job_id,
                status="FAILED",
                stage="Error",
                error_message=err_msg,
                log_msg=f"Failure: {err_msg}"
            )
            raise e

    def render_approved_job(
        self,
        job_id: str,
        progress_callback: Optional[Callable[[str, float], None]] = None,
        **kwargs: Any
    ) -> Path:
        """
        Renders a fully-approved job.
        Strictly blocks rendering if ANY scene remains unapproved.
        """
        job = JobManager.get_job(job_id)
        if not job:
            raise ValueError(f"Job {job_id} not found.")

        # 1. Enforce strict approval gate
        all_approved, unapproved = JobManager.are_all_scenes_approved(job_id)
        if not all_approved:
            unapproved_str = ", ".join(f"Scene #{o}" for o in unapproved)
            raise RuntimeError(f"Rendering BLOCKED: The following scenes have not been approved by the user: {unapproved_str}.")

        if not job.audio_path or not Path(job.audio_path).exists():
            raise FileNotFoundError(f"Voiceover audio file missing for job {job_id}: {job.audio_path}")

        scene_data = job.scene_plan_data or {}
        scenes = scene_data.get("scenes", [])
        if not scenes:
            raise ValueError("No scenes found in job scene plan.")

        clip_paths = []
        scene_durations = []
        for s in scenes:
            path = s.get("selected_asset_path")
            if not path or not Path(path).exists():
                raise FileNotFoundError(f"Missing asset for Scene #{s.get('scene_order')}: {path}")
            clip_paths.append(path)
            scene_durations.append(float(s.get("duration", 3.0)))

        def update_progress(message: str, step_fraction: float, stage_name: str):
            JobManager.update_job(
                job_id,
                progress=step_fraction,
                stage=stage_name,
                log_msg=message
            )
            if progress_callback:
                progress_callback(message, step_fraction)

        update_progress("Rendering approved scenes with audio ducking and subtitles...", 0.30, "RENDERING")

        # Mock AudioResult for editor
        from core.tts_engine import AudioResult
        audio_res = AudioResult(
            audio_path=job.audio_path,
            duration_seconds=sum(scene_durations),
            words_timing=[]
        )

        final_video_path = self.video_editor.build_short_video(
            audio_result=audio_res,
            clip_paths=clip_paths,
            output_filename=f"short_{job_id}.mp4",
            fallback_text=job.script_data.get("voiceover_text", "") if job.script_data else "",
            progress_callback=lambda msg, frac: update_progress(msg, 0.30 + frac * 0.50, "RENDERING"),
            bgm_track=kwargs.get("bgm_track", "cinematic_drone"),
            bgm_volume=float(kwargs.get("bgm_volume", 0.18)),
            enable_hook_sfx=bool(kwargs.get("enable_hook_sfx", True)),
            subtitle_style=kwargs.get("subtitle_style", "mrbeast"),
            subtitle_size=kwargs.get("subtitle_size", "medium"),
            watermark_text=kwargs.get("watermark_text", None),
            scene_durations=scene_durations
        )

        update_progress("Inspecting final rendered video...", 0.85, "VALIDATION")
        inspection_report = self.video_editor.inspect_rendered_video(
            final_video_path,
            expected_duration=audio_res.duration_seconds
        )

        qc_report = QualityControlReport(
            job_id=job_id,
            topic=job.topic,
            total_scenes=len(scenes),
            passed_scenes=len(scenes),
            rejections=[],
            scene_asset_sources={s.get("scene_order", i + 1): s.get("selected_asset_source", "approved") for i, s in enumerate(scenes)},
            frame_inspection=inspection_report,
            overall_pass=inspection_report.get("all_frames_valid", True)
        )
        qc_report_path = AppConfig.OUTPUT_DIR / f"qc_report_{job_id}.json"
        qc_report_path.write_text(json.dumps(qc_report.model_dump(), indent=2), encoding="utf-8")

        update_progress("Approved short rendered successfully! 🎉", 1.0, "COMPLETED")
        JobManager.update_job(
            job_id,
            status="COMPLETED",
            progress=1.0,
            stage="Completed",
            video_path=str(final_video_path.resolve()),
            validation_report=inspection_report,
            log_msg=f"Approved video rendered: {final_video_path.name}"
        )
        return final_video_path


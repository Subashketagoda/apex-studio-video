import os
import json
import time
import uuid
from pathlib import Path
from typing import List, Dict, Any, Optional, Tuple
from pydantic import BaseModel, Field

from core.config import AppConfig


class JobRecord(BaseModel):
    """Persistent job record for tracking render progress, scene plans, and human approval states."""
    job_id: str
    topic: str
    status: str = "QUEUED"  # QUEUED, RESEARCHING, SCRIPTING, VOICEOVER, SCENE_PLANNING, SOURCING_MEDIA, RENDERING, COMPLETED, FAILED
    progress: float = 0.0
    current_stage: str = "Initialized"
    created_at: float = Field(default_factory=time.time)
    completed_at: Optional[float] = None
    script_data: Optional[Dict[str, Any]] = None
    scene_plan_data: Optional[Dict[str, Any]] = None
    all_scenes_approved: bool = False
    unapproved_scenes: List[int] = Field(default_factory=list)
    audio_path: Optional[str] = None
    video_path: Optional[str] = None
    error_message: Optional[str] = None
    logs: List[str] = Field(default_factory=list)
    validation_report: Optional[Dict[str, Any]] = None


class JobManager:
    """Manages job persistence, scene-level state transitions, approval validation, and history logging."""

    JOBS_FILE = AppConfig.OUTPUT_DIR / "jobs.json"

    @classmethod
    def _load_jobs(cls) -> Dict[str, Dict[str, Any]]:
        cls.JOBS_FILE.parent.mkdir(parents=True, exist_ok=True)
        if cls.JOBS_FILE.exists():
            try:
                data = json.loads(cls.JOBS_FILE.read_text(encoding="utf-8"))
                return data if isinstance(data, dict) else {}
            except Exception:
                return {}
        return {}

    @classmethod
    def _save_jobs(cls, jobs: Dict[str, Dict[str, Any]]) -> None:
        cls.JOBS_FILE.parent.mkdir(parents=True, exist_ok=True)
        cls.JOBS_FILE.write_text(json.dumps(jobs, indent=2, ensure_ascii=False), encoding="utf-8")

    @classmethod
    def create_job(cls, topic: str) -> JobRecord:
        job_id = f"job_{int(time.time())}_{uuid.uuid4().hex[:6]}"
        record = JobRecord(job_id=job_id, topic=topic)
        jobs = cls._load_jobs()
        jobs[job_id] = record.model_dump()
        cls._save_jobs(jobs)
        return record

    @classmethod
    def update_job(
        cls,
        job_id: str,
        status: Optional[str] = None,
        progress: Optional[float] = None,
        stage: Optional[str] = None,
        log_msg: Optional[str] = None,
        script_data: Optional[Dict[str, Any]] = None,
        scene_plan_data: Optional[Dict[str, Any]] = None,
        audio_path: Optional[str] = None,
        video_path: Optional[str] = None,
        error_message: Optional[str] = None,
        validation_report: Optional[Dict[str, Any]] = None
    ) -> Optional[JobRecord]:
        jobs = cls._load_jobs()
        if job_id not in jobs:
            return None

        job = jobs[job_id]
        if status:
            job["status"] = status
            if status in {"COMPLETED", "FAILED"}:
                job["completed_at"] = time.time()
        if progress is not None:
            job["progress"] = round(min(max(progress, 0.0), 1.0), 2)
        if stage:
            job["current_stage"] = stage
        if log_msg:
            timestamp_str = time.strftime("%H:%M:%S")
            job.setdefault("logs", []).append(f"[{timestamp_str}] {log_msg}")
        if script_data is not None:
            job["script_data"] = script_data
        if scene_plan_data is not None:
            job["scene_plan_data"] = scene_plan_data
            scenes = scene_plan_data.get("scenes", [])
            unapproved = [s.get("scene_order", i + 1) for i, s in enumerate(scenes) if s.get("approval_status") != "APPROVED"]
            job["unapproved_scenes"] = unapproved
            job["all_scenes_approved"] = len(unapproved) == 0 and len(scenes) > 0
        if audio_path is not None:
            job["audio_path"] = audio_path
        if video_path is not None:
            job["video_path"] = video_path
        if error_message is not None:
            job["error_message"] = error_message
        if validation_report is not None:
            job["validation_report"] = validation_report

        jobs[job_id] = job
        cls._save_jobs(jobs)
        return JobRecord.model_validate(job)

    @classmethod
    def get_job(cls, job_id: str) -> Optional[JobRecord]:
        jobs = cls._load_jobs()
        if job_id in jobs:
            return JobRecord.model_validate(jobs[job_id])
        return None

    @classmethod
    def list_jobs(cls, limit: int = 50) -> List[JobRecord]:
        jobs = cls._load_jobs()
        records = [JobRecord.model_validate(d) for d in jobs.values()]
        records.sort(key=lambda r: r.created_at, reverse=True)
        return records[:limit]

    # --- Scene Approval & Modification State Machine ---

    @classmethod
    def update_scene_approval(
        cls,
        job_id: str,
        scene_order: int,
        status: str,  # APPROVED or REJECTED or PENDING
        notes: Optional[str] = None
    ) -> Optional[JobRecord]:
        """Updates human approval status for a specific scene and recalculates project-level gate."""
        jobs = cls._load_jobs()
        if job_id not in jobs or "scene_plan_data" not in jobs[job_id] or not jobs[job_id]["scene_plan_data"]:
            return None

        job = jobs[job_id]
        scenes = job["scene_plan_data"].get("scenes", [])
        found = False
        for s in scenes:
            if s.get("scene_order") == scene_order or s.get("sequence_number") == scene_order:
                s["approval_status"] = status.upper()
                if notes is not None:
                    s["approval_notes"] = notes
                found = True
                break

        if not found:
            return None

        unapproved = [s.get("scene_order", i + 1) for i, s in enumerate(scenes) if s.get("approval_status") != "APPROVED"]
        job["unapproved_scenes"] = unapproved
        job["all_scenes_approved"] = len(unapproved) == 0 and len(scenes) > 0
        job["scene_plan_data"]["all_approved"] = job["all_scenes_approved"]

        timestamp_str = time.strftime("%H:%M:%S")
        job.setdefault("logs", []).append(
            f"[{timestamp_str}] Scene #{scene_order} marked as {status.upper()}" + (f": {notes}" if notes else "")
        )

        jobs[job_id] = job
        cls._save_jobs(jobs)
        return JobRecord.model_validate(job)

    @classmethod
    def update_scene_prompt(
        cls,
        job_id: str,
        scene_order: int,
        new_prompt: str,
        new_negative: Optional[str] = None
    ) -> Optional[JobRecord]:
        """
        Updates prompt for a scene. Resets approval to PENDING and increments prompt_version.
        """
        jobs = cls._load_jobs()
        if job_id not in jobs or "scene_plan_data" not in jobs[job_id] or not jobs[job_id]["scene_plan_data"]:
            return None

        job = jobs[job_id]
        scenes = job["scene_plan_data"].get("scenes", [])
        for s in scenes:
            if s.get("scene_order") == scene_order or s.get("sequence_number") == scene_order:
                s["positive_prompt"] = new_prompt
                s["visual_description"] = new_prompt
                if new_negative is not None:
                    s["negative_prompt"] = new_negative
                    s["negative_constraints"] = [c.strip() for c in new_negative.split(",") if c.strip()]
                s["prompt_version"] = s.get("prompt_version", 1) + 1
                # CRITICAL: Changing prompt resets approval
                s["approval_status"] = "PENDING"
                s["approval_notes"] = "Prompt edited; requires fresh review."
                break

        unapproved = [s.get("scene_order", i + 1) for i, s in enumerate(scenes) if s.get("approval_status") != "APPROVED"]
        job["unapproved_scenes"] = unapproved
        job["all_scenes_approved"] = False
        job["scene_plan_data"]["all_approved"] = False

        jobs[job_id] = job
        cls._save_jobs(jobs)
        return JobRecord.model_validate(job)

    @classmethod
    def replace_scene_clip(
        cls,
        job_id: str,
        scene_order: int,
        new_clip_path: str,
        reason: str = "manual_replacement"
    ) -> Optional[JobRecord]:
        """
        Replaces visual clip for a scene, logs history, and resets approval to PENDING.
        """
        jobs = cls._load_jobs()
        if job_id not in jobs or "scene_plan_data" not in jobs[job_id] or not jobs[job_id]["scene_plan_data"]:
            return None

        job = jobs[job_id]
        scenes = job["scene_plan_data"].get("scenes", [])
        for s in scenes:
            if s.get("scene_order") == scene_order or s.get("sequence_number") == scene_order:
                old_path = s.get("selected_asset_path")
                s.setdefault("clip_replacement_history", []).append({
                    "timestamp": time.time(),
                    "old_path": old_path,
                    "new_path": new_clip_path,
                    "reason": reason
                })
                s["selected_asset_path"] = new_clip_path
                s["selected_asset_source"] = "user_replacement"
                s["generation_status"] = "GENERATED"
                # CRITICAL: Replacing clip resets approval
                s["approval_status"] = "PENDING"
                s["approval_notes"] = "Clip replaced; requires fresh review."
                break

        unapproved = [s.get("scene_order", i + 1) for i, s in enumerate(scenes) if s.get("approval_status") != "APPROVED"]
        job["unapproved_scenes"] = unapproved
        job["all_scenes_approved"] = False
        job["scene_plan_data"]["all_approved"] = False

        jobs[job_id] = job
        cls._save_jobs(jobs)
        return JobRecord.model_validate(job)

    @classmethod
    def are_all_scenes_approved(cls, job_id: str) -> tuple[bool, List[int]]:
        """
        Validates if every required scene in the project is approved.
        Returns (all_approved: bool, unapproved_orders: List[int]).
        """
        job = cls.get_job(job_id)
        if not job or not job.scene_plan_data:
            return False, []
        scenes = job.scene_plan_data.get("scenes", [])
        if not scenes:
            return False, []
        unapproved = [s.get("scene_order", i + 1) for i, s in enumerate(scenes) if s.get("approval_status") != "APPROVED"]
        return len(unapproved) == 0, unapproved


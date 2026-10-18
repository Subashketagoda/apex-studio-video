import os
import sys
import re
import time
import requests
import subprocess
from pathlib import Path
from typing import Optional, List, Dict, Any, Set, Tuple, Callable
from pydantic import BaseModel, Field

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8")

from core.config import AppConfig
from core.schemas import ScenePlanItem, TimestampedScenePlan, AssetRejectionRecord, ValidationResult
from core.motion_graphics import TopicMotionGraphicGenerator
from core.ai_visual_generator import AIVisualGenerator
from core.visual_validator import VisualRelevanceValidator


class DownloadedClip(BaseModel):
    """Metadata and attribution for an acquired video clip."""
    order: int
    keyword: str
    file_path: str
    duration: float
    width: int
    height: int
    asset_url: Optional[str] = None
    attribution: Optional[str] = "Pexels Free License"
    is_procedural_graphic: bool = False
    source_tier: str = "stock"
    validation_confidence: float = 1.0


class MediaFetcher:
    """
    Topic-Faithful 4-Tier Visual Acquisition Pipeline:
    Tier 1: Relevant licensed stock footage (Pexels / Pixabay) -> strictly validated.
    Tier 2: Relevant historical photographs / archival advertising (Wikimedia) -> strictly validated.
    Tier 3: Topic-specific AI-generated imagery (FLUX.1-schnell / Pollinations) -> strictly validated.
    Tier 4: Carefully designed topic motion graphics (Pillow + typography + dynamic layout fallback).

    Every candidate asset is validated by VisualRelevanceValidator before being approved.
    Unrelated footage (icebergs, soup cans, arbitrary glitches) is rejected with logged justification.
    """

    PEXELS_API_URL = "https://api.pexels.com/videos/search"
    PIXABAY_API_URL = "https://pixabay.com/api/videos/"

    def __init__(self, api_key: Optional[str] = None, output_dir: Optional[Path] = None):
        self.api_key = api_key or AppConfig.PEXELS_API_KEY
        self.output_dir = output_dir or (AppConfig.TEMP_DIR / "clips")
        self.output_dir.mkdir(parents=True, exist_ok=True)
        # Avoid repeating the same clip ID across scenes
        self.used_asset_ids: Set[str] = set()

    def fetch_all_scenes(
        self,
        topic: str,
        scene_plan: TimestampedScenePlan,
        visual_mode: str = "auto",
        progress_callback: Optional[Callable[[str, float], None]] = None
    ) -> Tuple[List[DownloadedClip], List[AssetRejectionRecord]]:
        """
        Processes all scenes in the TimestampedScenePlan through the 4-tier visual pipeline.
        Returns list of approved clips and list of all rejected candidate records for QC.
        """
        approved_clips: List[DownloadedClip] = []
        all_rejections: List[AssetRejectionRecord] = []
        total_scenes = len(scene_plan.scenes)

        print(f"\n[MediaFetcher] 🎬 Sourcing assets for {total_scenes} scenes in '{topic}'...", flush=True)

        for idx, scene in enumerate(scene_plan.scenes):
            step_frac = 0.40 + (idx / total_scenes) * 0.35
            if progress_callback:
                progress_callback(f"🖼️ Sourcing Scene #{scene.scene_order}: {scene.main_subject}...", step_frac)

            clip, rejections = self.fetch_scene_asset(
                scene=scene,
                topic=topic,
                total_scenes=total_scenes,
                visual_mode=visual_mode
            )
            approved_clips.append(clip)
            all_rejections.extend(rejections)

            # Update scene plan item with validation metadata
            scene.selected_asset_path = clip.file_path
            scene.selected_asset_source = clip.source_tier
            scene.validation_status = "passed" if not clip.is_procedural_graphic else "fallback"
            scene.validation_confidence = clip.validation_confidence

        return approved_clips, all_rejections

    def fetch_scene_asset(
        self,
        scene: ScenePlanItem,
        topic: str,
        total_scenes: int,
        visual_mode: str = "auto"
    ) -> Tuple[DownloadedClip, List[AssetRejectionRecord]]:
        """
        Executes the 4-tier visual acquisition priority for a single scene plan item.
        """
        rejections: List[AssetRejectionRecord] = []
        order = scene.scene_order
        duration = max(scene.duration, 2.5)

        # -------------------------------------------------------------
        # Tier 1: Stock Footage (Pexels / Pixabay)
        # Only accepted if it passes strict visual relevance validation!
        # -------------------------------------------------------------
        if visual_mode in ("auto", "stock", "hybrid") and self.api_key:
            for kw in scene.search_keywords:
                stock_clip, rej = self._try_fetch_pexels_validated(kw, scene, duration)
                if rej:
                    rejections.extend(rej)
                if stock_clip:
                    return stock_clip, rejections

        # -------------------------------------------------------------
        # Tier 2: Historical / Archival Imagery (Wikimedia / Public Domain)
        # -------------------------------------------------------------
        if visual_mode in ("auto", "archival", "hybrid", "ai_cinematic"):
            archival_clip, rej = self._try_fetch_archival_validated(topic, scene, duration)
            if rej:
                rejections.extend(rej)
            if archival_clip:
                return archival_clip, rejections

        # -------------------------------------------------------------
        # Tier 3: Topic-Specific AI-Generated Imagery (FLUX.1-schnell / Pollinations)
        # -------------------------------------------------------------
        if visual_mode in ("auto", "ai_cinematic", "hybrid"):
            ai_clip, rej = self._try_generate_ai_validated(topic, scene, duration)
            if rej:
                rejections.extend(rej)
            if ai_clip:
                return ai_clip, rejections

        # -------------------------------------------------------------
        # Tier 4: Carefully Designed Motion Graphics Fallback
        # Never generic; designed specifically for this scene and topic
        # -------------------------------------------------------------
        print(f"[MediaFetcher] 🎨 Tier 4: Rendering topic motion graphic for Scene #{order}...", flush=True)
        mg_clip = self._generate_topic_motion_graphic(topic, scene, total_scenes, duration)
        return mg_clip, rejections

    def _try_fetch_pexels_validated(
        self,
        query: str,
        scene: ScenePlanItem,
        duration: float
    ) -> Tuple[Optional[DownloadedClip], List[AssetRejectionRecord]]:
        """Attempts to find, download, and visually validate Pexels stock video."""
        rejections: List[AssetRejectionRecord] = []
        headers = {"Authorization": self.api_key}
        params = {"query": query, "orientation": "portrait", "per_page": 6}

        try:
            r = requests.get(self.PEXELS_API_URL, headers=headers, params=params, timeout=10)
            if r.status_code != 200:
                return None, rejections

            videos = r.json().get("videos", [])
            for v in videos:
                vid_id = str(v.get("id"))
                if vid_id in self.used_asset_ids:
                    continue

                v_files = v.get("video_files", [])
                best_file = None
                for vf in v_files:
                    w, h = vf.get("width") or 0, vf.get("height") or 0
                    if h >= w:
                        if not best_file or h > (best_file.get("height") or 0):
                            best_file = vf

                if not best_file and v_files:
                    best_file = v_files[0]

                if best_file and "link" in best_file:
                    cand_path = self.output_dir / f"cand_pexels_{scene.scene_order}_{vid_id}.mp4"
                    # Download candidate
                    dl_ok = self._download_file(best_file["link"], cand_path)
                    if not dl_ok:
                        continue

                    # Validate with VisualRelevanceValidator
                    val_res = VisualRelevanceValidator.validate_asset(
                        candidate_path=cand_path,
                        scene=scene,
                        metadata={
                            "title": v.get("url", ""),
                            "tags": v.get("tags", []),
                            "url": best_file["link"]
                        }
                    )

                    if val_res.is_relevant:
                        self.used_asset_ids.add(vid_id)
                        photographer = v.get("user", {}).get("name", "Pexels Creator")
                        return DownloadedClip(
                            order=scene.scene_order,
                            keyword=query,
                            file_path=str(cand_path.resolve()),
                            duration=duration,
                            width=best_file.get("width", 1080),
                            height=best_file.get("height", 1920),
                            asset_url=v.get("url", best_file["link"]),
                            attribution=f"Video by {photographer} on Pexels",
                            is_procedural_graphic=False,
                            source_tier="stock",
                            validation_confidence=val_res.confidence
                        ), rejections
                    else:
                        # Log rejection
                        rejections.append(
                            AssetRejectionRecord(
                                scene_order=scene.scene_order,
                                candidate_source="Pexels Stock",
                                candidate_identifier=f"pexels_{vid_id}",
                                rejection_reason=val_res.rejection_reason,
                                confidence_score=val_res.confidence,
                                detected_dominant_subject=val_res.dominant_subject
                            )
                        )
                        # Remove rejected candidate file
                        try:
                            cand_path.unlink(missing_ok=True)
                        except Exception:
                            pass
        except Exception as e:
            print(f"[MediaFetcher] Pexels check exception for '{query}': {e}", flush=True)

        return None, rejections

    def _try_fetch_archival_validated(
        self,
        topic: str,
        scene: ScenePlanItem,
        duration: float
    ) -> Tuple[Optional[DownloadedClip], List[AssetRejectionRecord]]:
        """Searches archival/historical sources (Wikimedia) and validates."""
        rejections: List[AssetRejectionRecord] = []
        safe_q = re.sub(r"[^a-zA-Z0-9]+", "_", f"{scene.scene_order}_{scene.main_subject}")[:30].strip("_")
        img_path = self.output_dir / f"cand_wiki_{safe_q}.jpg"
        vid_path = self.output_dir / f"archival_{safe_q}.mp4"

        search_query = f"{scene.main_subject} {scene.historical_period or ''}".strip()
        has_img = AIVisualGenerator._fetch_wikimedia_image(search_query, topic, img_path)
        if not has_img:
            return None, rejections

        # Validate candidate image
        val_res = VisualRelevanceValidator.validate_asset(
            candidate_path=img_path,
            scene=scene,
            metadata={"title": search_query}
        )

        if val_res.is_relevant:
            clip_path = AIVisualGenerator._render_ken_burns_video(
                image_path=img_path,
                output_mp4_path=vid_path,
                duration_sec=duration,
                camera_motion=scene.camera_movement
            )
            if clip_path and clip_path.exists():
                return DownloadedClip(
                    order=scene.scene_order,
                    keyword=search_query,
                    file_path=str(clip_path.resolve()),
                    duration=duration,
                    width=1080,
                    height=1920,
                    asset_url=None,
                    attribution="Wikimedia Public Domain Archive",
                    is_procedural_graphic=False,
                    source_tier="archival",
                    validation_confidence=val_res.confidence
                ), rejections
        else:
            rejections.append(
                AssetRejectionRecord(
                    scene_order=scene.scene_order,
                    candidate_source="Wikimedia Archival",
                    candidate_identifier=f"wiki_{safe_q}",
                    rejection_reason=val_res.rejection_reason,
                    confidence_score=val_res.confidence,
                    detected_dominant_subject=val_res.dominant_subject
                )
            )
            try:
                img_path.unlink(missing_ok=True)
            except Exception:
                pass

        return None, rejections

    def _try_generate_ai_validated(
        self,
        topic: str,
        scene: ScenePlanItem,
        duration: float
    ) -> Tuple[Optional[DownloadedClip], List[AssetRejectionRecord]]:
        """Generates authentic AI image matching scene prompt and validates."""
        rejections: List[AssetRejectionRecord] = []
        safe_q = re.sub(r"[^a-zA-Z0-9]+", "_", f"{scene.scene_order}_{scene.main_subject}")[:30].strip("_")
        img_path = self.output_dir / f"ai_img_{safe_q}.jpg"
        vid_path = self.output_dir / f"ai_clip_{safe_q}.mp4"

        # Check if already rendered and valid
        if vid_path.exists() and vid_path.stat().st_size > 50_000:
            return DownloadedClip(
                order=scene.scene_order,
                keyword=scene.main_subject,
                file_path=str(vid_path.resolve()),
                duration=duration,
                width=1080,
                height=1920,
                asset_url=None,
                attribution="AI Cinematic Visual (FLUX.1-schnell + Ken-Burns)",
                is_procedural_graphic=False,
                source_tier="ai_generated",
                validation_confidence=0.95
            ), rejections

        # Craft prompt
        prompt = (
            f"photorealistic 8k vertical portrait of {scene.visual_description}, "
            f"period: {scene.historical_period or 'cinematic history'}, "
            f"dramatic studio lighting, 35mm lens, depth of field, 9:16 aspect ratio"
        )[:260]

        # 1. Try FLUX.1-schnell
        has_img = AIVisualGenerator._fetch_flux_image(prompt, img_path, seed=scene.scene_order * 113 + 42)
        # 2. Try Pollinations fallback
        if not has_img:
            has_img = AIVisualGenerator._fetch_pollinations_image(prompt, img_path, seed=scene.scene_order * 113 + 42)

        if not has_img or not img_path.exists() or img_path.stat().st_size < 10_000:
            return None, rejections

        # Validate generated visual
        val_res = VisualRelevanceValidator.validate_asset(
            candidate_path=img_path,
            scene=scene,
            metadata={"prompt": prompt}
        )

        if val_res.is_relevant:
            clip_path = AIVisualGenerator._render_ken_burns_video(
                image_path=img_path,
                output_mp4_path=vid_path,
                duration_sec=duration,
                camera_motion=scene.camera_movement
            )
            if clip_path and clip_path.exists():
                return DownloadedClip(
                    order=scene.scene_order,
                    keyword=scene.main_subject,
                    file_path=str(clip_path.resolve()),
                    duration=duration,
                    width=1080,
                    height=1920,
                    asset_url=None,
                    attribution="AI Cinematic Visual (FLUX.1-schnell + Ken-Burns)",
                    is_procedural_graphic=False,
                    source_tier="ai_generated",
                    validation_confidence=val_res.confidence
                ), rejections
        else:
            rejections.append(
                AssetRejectionRecord(
                    scene_order=scene.scene_order,
                    candidate_source="FLUX AI Generation",
                    candidate_identifier=f"flux_{safe_q}",
                    rejection_reason=val_res.rejection_reason,
                    confidence_score=val_res.confidence,
                    detected_dominant_subject=val_res.dominant_subject
                )
            )
            try:
                img_path.unlink(missing_ok=True)
            except Exception:
                pass

        return None, rejections

    def _generate_topic_motion_graphic(
        self,
        topic: str,
        scene: ScenePlanItem,
        total_scenes: int,
        duration: float
    ) -> DownloadedClip:
        """Generates an intentional, topic-faithful infographic motion graphic."""
        safe_q = re.sub(r"[^a-zA-Z0-9]+", "_", f"{scene.scene_order}_{scene.main_subject}")[:30].strip("_")
        img_path = self.output_dir / f"mg_{safe_q}.jpg"
        vid_path = self.output_dir / f"mg_{safe_q}.mp4"

        TopicMotionGraphicGenerator.create_scene_graphic(
            topic=topic,
            scene_order=scene.scene_order,
            total_scenes=total_scenes,
            scene_title=scene.main_subject,
            key_metric_or_text=scene.on_screen_text or scene.main_subject.upper(),
            factual_takeaway=scene.narration_segment,
            source_name=f"APEXGEN ARCHIVE // {scene.historical_period or 'VERIFIED HISTORY'}",
            output_image_path=img_path
        )

        TopicMotionGraphicGenerator.render_graphic_to_video(
            image_path=img_path,
            duration_sec=duration,
            output_mp4_path=vid_path
        )

        return DownloadedClip(
            order=scene.scene_order,
            keyword=scene.main_subject,
            file_path=str(vid_path.resolve()),
            duration=duration,
            width=1080,
            height=1920,
            asset_url=None,
            attribution="ApexGen Factual Motion Graphic",
            is_procedural_graphic=True,
            source_tier="motion_graphic",
            validation_confidence=1.0
        )

    def _download_file(self, url: str, target_path: Path) -> bool:
        """Downloads a remote asset to local disk."""
        try:
            r = requests.get(url, stream=True, timeout=20)
            if r.status_code == 200:
                with open(target_path, "wb") as f:
                    for chunk in r.iter_content(chunk_size=65536):
                        if chunk:
                            f.write(chunk)
                return target_path.exists() and target_path.stat().st_size > 1000
        except Exception as e:
            print(f"[MediaFetcher] Download failed for {url}: {e}", flush=True)
        return False

    # Backwards compatibility helper for older callers
    def fetch_all_segments(
        self,
        topic: str,
        visual_segments: List[Any],
        visual_mode: str = "ai_cinematic",
        progress_callback: Optional[Callable[[str, float], None]] = None
    ) -> List[DownloadedClip]:
        """Backwards compatibility adapter."""
        # Convert segments to dummy ScenePlanItems
        from core.schemas import ScenePlanItem
        scenes = []
        for i, s in enumerate(visual_segments):
            dur = getattr(s, "approx_duration_sec", 6.0)
            scenes.append(
                ScenePlanItem(
                    scene_order=i + 1,
                    narration_segment=getattr(s, "scene_description", topic),
                    start_time=i * dur,
                    end_time=(i + 1) * dur,
                    duration=dur,
                    main_subject=getattr(s, "search_query", topic),
                    action=getattr(s, "scene_description", topic),
                    visual_description=getattr(s, "scene_description", topic),
                    required_objects=[topic.split()[0]],
                    search_keywords=[getattr(s, "search_query", topic)],
                    negative_constraints=["soup can", "iceberg", "glitch"],
                    camera_movement=getattr(s, "camera_movement", "cinematic push-in")
                )
            )
        plan = TimestampedScenePlan(topic=topic, total_scenes=len(scenes), total_duration=len(scenes)*6.0, scenes=scenes)
        clips, _ = self.fetch_all_scenes(topic, plan, visual_mode=visual_mode, progress_callback=progress_callback)
        return clips

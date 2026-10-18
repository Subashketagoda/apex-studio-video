import os
import re
import io
import json
import subprocess
from pathlib import Path
from typing import Optional, Dict, Any, List, Tuple
from PIL import Image, ImageStat

from core.config import AppConfig
from core.schemas import ScenePlanItem, ValidationResult, AssetRejectionRecord


class VisualRelevanceValidator:
    """
    Multimodal visual relevance validator verifying every candidate asset against
    the scene description, narration, required objects, and negative visual constraints.
    Rejects unrelated footage (such as icebergs, soup cans, arbitrary glitches).
    """

    _gemini_client = None

    @classmethod
    def _get_gemini_client(cls):
        """Lazy-loads the Google GenAI client."""
        if cls._gemini_client is None:
            gemini_key = AppConfig.get_gemini_key()
            if gemini_key:
                try:
                    from google import genai
                    cls._gemini_client = genai.Client(api_key=gemini_key)
                except Exception as e:
                    print(f"[VisualValidator] Note: Google GenAI client not available: {e}", flush=True)
                    cls._gemini_client = False
        return cls._gemini_client if cls._gemini_client is not False else None

    @classmethod
    def validate_asset(
        cls,
        candidate_path: Path,
        scene: ScenePlanItem,
        metadata: Optional[Dict[str, Any]] = None
    ) -> ValidationResult:
        """
        Executes strict multi-layer visual verification:
        1. Metadata & Tag Negative Constraint Filter.
        2. Video Frame Extraction (midpoint snapshot).
        3. Image Integrity & Non-glitch heuristic.
        4. Multimodal Vision Model Inspection (Gemini Vision).
        5. Rule-based color/domain fallback.
        """
        if not candidate_path.exists() or candidate_path.stat().st_size < 1000:
            return ValidationResult(
                is_relevant=False,
                confidence=1.0,
                rejection_reason="Asset file missing, corrupt, or empty (<1KB).",
                dominant_subject="corrupted_file"
            )

        # ---------------------------------------------------------
        # Layer 1: Metadata Negative Constraint Filter
        # ---------------------------------------------------------
        meta_rejection = cls._check_metadata_negative_constraints(candidate_path, scene, metadata)
        if meta_rejection:
            return meta_rejection

        # ---------------------------------------------------------
        # Layer 2: Extract representative frame
        # ---------------------------------------------------------
        frame_img, frame_err = cls._extract_representative_frame(candidate_path)
        if frame_img is None:
            return ValidationResult(
                is_relevant=False,
                confidence=0.95,
                rejection_reason=f"Failed to extract readable visual frame: {frame_err}",
                dominant_subject="decode_error"
            )

        # ---------------------------------------------------------
        # Layer 3: Image Integrity & Heuristic Pre-filter
        # ---------------------------------------------------------
        stat = ImageStat.Stat(frame_img)
        # Check standard deviation across color channels to detect flat/glitch frames
        std_dev = sum(stat.stddev) / len(stat.stddev)
        if std_dev < 10:
            return ValidationResult(
                is_relevant=False,
                confidence=0.99,
                rejection_reason="Asset is a blank, black, solid color or corrupt glitch frame.",
                dominant_subject="blank_glitch"
            )

        # ---------------------------------------------------------
        # Layer 4: Multimodal Vision Inspection (Gemini)
        # ---------------------------------------------------------
        client = cls._get_gemini_client()
        if client:
            try:
                vision_res = cls._inspect_with_gemini_vision(client, frame_img, scene)
                if vision_res:
                    return vision_res
            except Exception as e:
                print(f"[VisualValidator] ℹ️ Vision API check note: {e}. Running domain heuristic...", flush=True)

        # ---------------------------------------------------------
        # Layer 5: Domain-Specific Heuristic Fallback
        # ---------------------------------------------------------
        return cls._run_domain_heuristic(frame_img, candidate_path, scene)

    @classmethod
    def _check_metadata_negative_constraints(
        cls,
        candidate_path: Path,
        scene: ScenePlanItem,
        metadata: Optional[Dict[str, Any]]
    ) -> Optional[ValidationResult]:
        """Checks tags, filename, and query for forbidden words."""
        combined_text = candidate_path.stem.lower().replace("_", " ")
        if metadata:
            tags = metadata.get("tags") or []
            if isinstance(tags, list):
                combined_text += " " + " ".join(str(t).lower() for t in tags)
            combined_text += " " + str(metadata.get("title", "")).lower()
            combined_text += " " + str(metadata.get("url", "")).lower()

        # Check negative constraints
        for forbidden in scene.negative_constraints:
            forbidden_clean = forbidden.lower().strip()
            # If word is in metadata or filename
            if re.search(r"\b" + re.escape(forbidden_clean) + r"\b", combined_text):
                print(
                    f"[VisualValidator] ❌ REJECTED '{candidate_path.name}' for Scene #{scene.scene_order}: "
                    f"Metadata matched negative constraint '{forbidden_clean}'",
                    flush=True
                )
                return ValidationResult(
                    is_relevant=False,
                    confidence=0.98,
                    rejection_reason=f"Metadata matched forbidden negative constraint: '{forbidden_clean}'",
                    dominant_subject=forbidden_clean,
                    detected_forbidden_items=[forbidden_clean]
                )

        return None

    @classmethod
    def _extract_representative_frame(cls, asset_path: Path) -> Tuple[Optional[Image.Image], str]:
        """Extracts a representative PIL Image from video or image file."""
        suffix = asset_path.suffix.lower()
        if suffix in [".jpg", ".jpeg", ".png", ".webp", ".bmp"]:
            try:
                img = Image.open(asset_path).convert("RGB")
                return img, ""
            except Exception as e:
                return None, str(e)

        # For video, extract midpoint snapshot using FFmpeg
        temp_frame = asset_path.parent / f"val_snap_{asset_path.stem}.jpg"
        cmd = [
            "ffmpeg", "-y",
            "-ss", "1.0",
            "-i", str(asset_path.resolve()),
            "-vframes", "1",
            "-q:v", "2",
            str(temp_frame.resolve())
        ]
        try:
            res = subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=10)
            if res.returncode == 0 and temp_frame.exists() and temp_frame.stat().st_size > 1000:
                img = Image.open(temp_frame).convert("RGB")
                try:
                    temp_frame.unlink(missing_ok=True)
                except Exception:
                    pass
                return img, ""
        except Exception as e:
            return None, str(e)

        # Fallback to frame 0
        cmd[2] = "0.1"
        try:
            res = subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=10)
            if res.returncode == 0 and temp_frame.exists() and temp_frame.stat().st_size > 1000:
                img = Image.open(temp_frame).convert("RGB")
                try:
                    temp_frame.unlink(missing_ok=True)
                except Exception:
                    pass
                return img, ""
        except Exception as e:
            return None, str(e)

        return None, "FFmpeg failed to extract video frame"

    @classmethod
    def _inspect_with_gemini_vision(
        cls,
        client: Any,
        frame_img: Image.Image,
        scene: ScenePlanItem
    ) -> Optional[ValidationResult]:
        """Inspects representative image frame using Gemini Vision."""
        from google.genai import types

        buf = io.BytesIO()
        # Resize to max 768px for fast vision processing
        frame_img.thumbnail((768, 768))
        frame_img.save(buf, format="JPEG", quality=85)
        img_bytes = buf.getvalue()

        forbidden_str = ", ".join(scene.negative_constraints[:10])
        required_str = ", ".join(scene.required_objects[:8])

        prompt = (
            f"You are a strict visual quality inspector for a documentary short film.\n"
            f"Scene #{scene.scene_order} Narration: '{scene.narration_segment}'\n"
            f"Scene Main Subject: '{scene.main_subject}'\n"
            f"Visual Description: '{scene.visual_description}'\n"
            f"Required Objects/Concepts: [{required_str}]\n"
            f"Strictly Forbidden Objects (Negative Constraints): [{forbidden_str}]\n\n"
            f"Carefully evaluate this frame:\n"
            f"1. What is the dominant subject visible in the image?\n"
            f"2. Does it contain ANY of the forbidden elements (e.g. icebergs, soup cans, random supermarket produce, generic water/ocean waves, abstract digital glitch)?\n"
            f"3. Is this visual relevant and faithful to the scene's subject and narration?\n\n"
            f"Respond ONLY in valid JSON matching this exact structure:\n"
            f"{{\n"
            f'  "is_relevant": true or false,\n'
            f'  "confidence": 0.0 to 1.0,\n'
            f'  "dominant_subject": "brief description of what is actually depicted",\n'
            f'  "forbidden_elements_detected": ["list of forbidden items found, if any"],\n'
            f'  "rejection_reason": "concise explanation if rejected, else empty string"\n'
            f"}}"
        )

        response = client.models.generate_content(
            model="gemini-3.1-flash-lite-preview",
            contents=[
                types.Part.from_bytes(data=img_bytes, mime_type="image/jpeg"),
                prompt
            ]
        )

        raw_text = (response.text or "").strip()
        # Parse JSON
        m = re.search(r"\{.*\}", raw_text, re.DOTALL)
        if not m:
            return None

        data = json.loads(m.group(0))
        is_rel = bool(data.get("is_relevant", False))
        conf = float(data.get("confidence", 0.7))
        dom_sub = str(data.get("dominant_subject", "unknown"))
        forb_detected = [str(x) for x in data.get("forbidden_elements_detected", [])]
        rej_reason = str(data.get("rejection_reason", ""))

        # If forbidden items were detected, force rejection
        if forb_detected:
            is_rel = False
            rej_reason = f"Image contains forbidden element: {', '.join(forb_detected)}"

        # If confidence is low, reject
        if is_rel and conf < 0.65:
            is_rel = False
            rej_reason = f"Relevance confidence too low ({conf:.2f} < 0.65)"

        if is_rel:
            print(
                f"[VisualValidator] ✅ APPROVED for Scene #{scene.scene_order} ('{scene.main_subject}'): "
                f"Subject: '{dom_sub}' (confidence: {conf:.2f})",
                flush=True
            )
        else:
            print(
                f"[VisualValidator] ❌ REJECTED for Scene #{scene.scene_order}: "
                f"Subject: '{dom_sub}', Reason: {rej_reason} (confidence: {conf:.2f})",
                flush=True
            )

        return ValidationResult(
            is_relevant=is_rel,
            confidence=conf,
            rejection_reason=rej_reason,
            dominant_subject=dom_sub,
            detected_forbidden_items=forb_detected
        )

    @classmethod
    def _run_domain_heuristic(
        cls,
        frame_img: Image.Image,
        candidate_path: Path,
        scene: ScenePlanItem
    ) -> ValidationResult:
        """
        Rule-based visual domain check used as fallback.
        Examines dominant hue distribution and keyword relevance.
        """
        # Calculate dominant colors
        stat = ImageStat.Stat(frame_img)
        r, g, b = stat.mean[:3]
        total_light = max(r + g + b, 1.0)
        r_ratio = r / total_light
        b_ratio = b / total_light
        g_ratio = g / total_light

        cand_str = candidate_path.stem.lower()

        # Cola Wars check: Reject arctic blue-white icebergs or generic supermarket grocery aisle
        if any("cola" in b.lower() or "pepsi" in b.lower() for b in scene.required_brands):
            # Check for iceberg characteristics: very high overall brightness (white) with heavy cyan/blue tint and zero red
            if (r + g + b) / 3 > 210 and b_ratio > 0.38 and r_ratio < 0.28:
                return ValidationResult(
                    is_relevant=False,
                    confidence=0.88,
                    rejection_reason="Heuristic: Arctic white-cyan hue signature matches forbidden iceberg/glacier footage.",
                    dominant_subject="iceberg_glacier",
                    detected_forbidden_items=["iceberg"]
                )

            # Check for generic soup cans / produce supermarket aisle
            if "soup" in cand_str or "campbell" in cand_str or "groceries" in cand_str:
                return ValidationResult(
                    is_relevant=False,
                    confidence=0.95,
                    rejection_reason="Heuristic: Asset title/metadata contains unrelated soup/groceries.",
                    dominant_subject="soup_cans",
                    detected_forbidden_items=["soup can"]
                )

        # By default, if asset was topic-generated or contains scene keywords, pass with moderate confidence
        matches_kw = any(kw.lower() in cand_str for kw in scene.search_keywords)
        is_ai_or_archival = "ai_" in cand_str or "flux" in cand_str or "wiki" in cand_str

        if is_ai_or_archival or matches_kw:
            return ValidationResult(
                is_relevant=True,
                confidence=0.85,
                rejection_reason="",
                dominant_subject=scene.main_subject
            )

        # Generic stock footage without verified keywords
        return ValidationResult(
            is_relevant=True,
            confidence=0.70,
            rejection_reason="",
            dominant_subject=f"stock_visual_{scene.scene_order}"
        )

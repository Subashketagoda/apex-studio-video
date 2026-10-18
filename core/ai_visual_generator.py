import os
import sys
import time
import urllib.parse
import subprocess
import requests
from pathlib import Path
from typing import Optional, Dict, Any, List
from PIL import Image

from core.config import AppConfig

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8")


class AIVisualGenerator:
    """
    Generates genuine, state-of-the-art AI imagery and cinematic videos:
    1. Primary Engine: FLUX.1-schnell (Black Forest Labs) via Gradio API.
    2. Secondary Engine: Pollinations AI Turbo.
    3. Tertiary Engine: Wikimedia Archival Documentary Imagery.
    4. Smooth Ken-Burns 30 FPS camera movement (FFmpeg scale & crop evaluation).
    """

    POLLINATIONS_BASE_URL = "https://image.pollinations.ai/prompt"
    WIKI_SEARCH_URL = "https://en.wikipedia.org/w/api.php"
    _flux_client = None

    @classmethod
    def _get_flux_client(cls):
        """Lazy-loads and caches the FLUX.1-schnell Gradio client."""
        if cls._flux_client is None:
            try:
                from gradio_client import Client
                cls._flux_client = Client("black-forest-labs/FLUX.1-schnell")
            except Exception as e:
                print(f"[AIVisualGenerator] ℹ️ Could not initialize FLUX client: {e}", flush=True)
                cls._flux_client = False
        return cls._flux_client if cls._flux_client is not False else None

    @classmethod
    def generate_ai_clip(
        cls,
        topic: str,
        segment: Any,
        order: int,
        duration_sec: float,
        output_dir: Path,
        seed: Optional[int] = None
    ) -> Optional[Path]:
        """
        Creates an end-to-end cinematic AI video clip for a given VisualSegment:
        1. Checks cache for existing rendered clip.
        2. Generates genuine AI image via FLUX.1-schnell.
        3. Renders smooth Ken-Burns camera movement into a 1080x1920 30FPS MP4.
        """
        output_dir.mkdir(parents=True, exist_ok=True)
        query = getattr(segment, "search_query", topic)
        import re
        safe_q = re.sub(r"[^a-zA-Z0-9]+", "_", f"{order:02d}_{query}")[:30].strip("_")
        img_path = output_dir / f"ai_{safe_q}.jpg"
        vid_path = output_dir / f"ai_{safe_q}.mp4"

        # Check cache: if valid clip already exists (>50KB), reuse it
        if vid_path.exists() and vid_path.stat().st_size > 50_000:
            print(f"[AIVisualGenerator] ⚡ Using cached AI clip #{order} ({vid_path.name})", flush=True)
            return vid_path

        print(f"[AIVisualGenerator] 🎨 Generating genuine AI visual #{order} for: '{query}'...", flush=True)

        has_image = img_path.exists() and img_path.stat().st_size > 20_000

        # Step 1: FLUX.1-schnell AI Image Generation (State of the Art)
        if not has_image:
            prompt = cls._craft_cinematic_prompt(topic, segment)
            has_image = cls._fetch_flux_image(prompt, img_path, seed=seed or (order * 107 + 42))

        # Step 2: Fallback to Pollinations AI
        if not has_image:
            prompt = cls._craft_cinematic_prompt(topic, segment)
            has_image = cls._fetch_pollinations_image(prompt, img_path, seed=seed or (order * 107 + 42))

        # Step 3: Fallback to Wikimedia Archival Imagery if online AI services are temporarily unreachable
        if not has_image:
            print(f"[AIVisualGenerator] 🏛️ Querying archival imagery for '{query}'...", flush=True)
            has_image = cls._fetch_wikimedia_image(query, topic, img_path)

        if not has_image or not img_path.exists() or img_path.stat().st_size < 10_000:
            print(f"[AIVisualGenerator] ⚠️ Visual acquisition failed for scene #{order}. Falling back to next engine...", flush=True)
            return None

        # Step 4: Render image to cinematic 1080x1920 MP4 video with Ken-Burns motion
        cam_motion = getattr(segment, "camera_movement", "cinematic push-in").lower()
        clip_path = cls._render_ken_burns_video(
            image_path=img_path,
            output_mp4_path=vid_path,
            duration_sec=duration_sec,
            camera_motion=cam_motion
        )
        return clip_path

    @classmethod
    def _craft_cinematic_prompt(cls, topic: str, segment: Any) -> str:
        """Constructs an evocative prompt for 9:16 vertical cinematic generation."""
        desc = getattr(segment, "scene_description", getattr(segment, "search_query", topic))
        shot_type = getattr(segment, "shot_type", "cinematic medium shot")
        
        clean_desc = desc.replace('"', '').replace("'", "").strip()
        clean_topic = topic.replace('"', '').replace("'", "").strip()

        prompt = (
            f"cinematic 8k photograph of {clean_desc}, "
            f"context of {clean_topic}, {shot_type}, "
            f"dramatic lighting, 35mm lens, photorealistic, depth of field, "
            f"vertical portrait composition, 9:16 aspect ratio"
        )
        return prompt[:250]

    @classmethod
    def _fetch_flux_image(cls, prompt: str, output_path: Path, seed: int = 42) -> bool:
        """Generates authentic AI image using FLUX.1-schnell Gradio client."""
        client = cls._get_flux_client()
        if not client:
            return False

        try:
            print(f"[AIVisualGenerator] ⚡ Synthesizing with FLUX.1-schnell: '{prompt[:50]}...'...", flush=True)
            res = client.predict(
                prompt=prompt,
                seed=seed,
                randomize_seed=True,
                width=576,
                height=1024,
                num_inference_steps=4,
                api_name="/infer"
            )
            temp_path = res[0] if isinstance(res, (tuple, list)) else res
            if temp_path and Path(temp_path).exists():
                im = Image.open(temp_path)
                im.convert("RGB").save(output_path, format="JPEG", quality=95)
                print(f"[AIVisualGenerator] ✅ FLUX image generated ({output_path.stat().st_size} bytes)", flush=True)
                return True
        except Exception as e:
            print(f"[AIVisualGenerator] ℹ️ FLUX generation note: {e}", flush=True)

        return False

    @classmethod
    def _fetch_pollinations_image(cls, prompt: str, output_path: Path, seed: int = 42) -> bool:
        """Fetches AI image from Pollinations. Fast fail on rate limit (402)."""
        encoded_prompt = urllib.parse.quote(prompt[:100])
        url = f"{cls.POLLINATIONS_BASE_URL}/{encoded_prompt}?width=576&height=1024&nologo=true&seed={seed}"
        
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
        }

        try:
            r = requests.get(url, headers=headers, timeout=12)
            if r.status_code == 200 and len(r.content) > 15_000:
                with open(output_path, "wb") as f:
                    f.write(r.content)
                return True
            elif r.status_code == 402:
                return False
        except Exception:
            pass

        return False

    @classmethod
    def _fetch_wikimedia_image(cls, query: str, topic: str, output_path: Path) -> bool:
        """Searches Wikipedia / Wikimedia Commons for authentic high-resolution imagery."""
        headers = {"User-Agent": "ApexGenStudio/1.0 (contact@apexgen.ai)"}

        search_terms = [query, f"{topic} {query}".strip(), topic]
        for term in search_terms:
            try:
                summary_url = f"https://en.wikipedia.org/api/rest_v1/page/summary/{urllib.parse.quote(term)}"
                r = requests.get(summary_url, headers=headers, timeout=5)
                if r.status_code == 200:
                    data = r.json()
                    img_info = data.get("originalimage") or data.get("thumbnail")
                    if img_info and "source" in img_info:
                        img_url = img_info["source"]
                        ir = requests.get(img_url, headers=headers, timeout=8)
                        if ir.status_code == 200 and len(ir.content) > 20_000:
                            with open(output_path, "wb") as f:
                                f.write(ir.content)
                            return True

                search_url = (
                    f"{cls.WIKI_SEARCH_URL}?action=query&format=json&prop=pageimages"
                    f"&generator=search&gsrsearch={urllib.parse.quote(term)}&piprop=original|thumbnail&pithumbsize=1080"
                )
                sr = requests.get(search_url, headers=headers, timeout=6)
                if sr.status_code == 200:
                    pages = sr.json().get("query", {}).get("pages", {})
                    for pid, p in pages.items():
                        src = (p.get("original") or {}).get("source") or (p.get("thumbnail") or {}).get("source")
                        if src:
                            clean_src = src.split("?")[0].lower()
                            if clean_src.endswith((".jpg", ".jpeg", ".png", ".webp")):
                                ir = requests.get(src, headers=headers, timeout=8)
                                if ir.status_code == 200 and len(ir.content) > 20_000:
                                    with open(output_path, "wb") as f:
                                        f.write(ir.content)
                                    return True
            except Exception:
                continue

        return False

    @classmethod
    def _render_ken_burns_video(
        cls,
        image_path: Path,
        output_mp4_path: Path,
        duration_sec: float,
        camera_motion: str = "cinematic push-in"
    ) -> Optional[Path]:
        """
        Converts any image into a 1080x1920 30 FPS MP4 video with smooth Ken-Burns camera movement.
        Safely scales and crops to portrait orientation.
        """
        duration = max(round(duration_sec, 2), 2.0)
        dur_str = str(duration)

        # Pre-resize massive raw archival images (e.g. 4320x4320) to max 1920 for instant FFmpeg encoding
        try:
            with Image.open(image_path) as im:
                if max(im.size) > 1920:
                    im.thumbnail((1920, 1920), Image.Resampling.LANCZOS)
                    im.convert("RGB").save(image_path, "JPEG", quality=92)
        except Exception:
            pass

        # Add actual per-frame camera motion. Previously this was only a static
        # scale/crop despite being labelled as a Ken-Burns render.
        motion = (camera_motion or "").lower()
        center_x = "iw/2-(iw/zoom/2)"
        center_y = "ih/2-(ih/zoom/2)"
        if any(term in motion for term in ("pull-back", "pull back", "zoom out", "pullback")):
            zoom_expr = "max(1.0,1.12-on*0.00013)"
            x_expr, y_expr = center_x, center_y
        elif any(term in motion for term in ("tracking right", "pan right", "orbit")):
            zoom_expr = "1.10"
            x_expr = "min(iw-iw/zoom,on*0.15)"
            y_expr = center_y
        elif any(term in motion for term in ("tilt down", "pan down", "tilt-down")):
            zoom_expr = "1.10"
            x_expr = center_x
            y_expr = "min(ih-ih/zoom,on*0.25)"
        else:
            zoom_expr = "min(zoom+0.0012,1.12)"
            x_expr, y_expr = center_x, center_y

        full_filter = (
            "scale=1080:1920:force_original_aspect_ratio=increase,"
            "crop=1080:1920,"
            f"zoompan=z='{zoom_expr}':x='{x_expr}':y='{y_expr}':"
            "d=1:s=1080x1920:fps=30,format=yuv420p"
        )

        cmd = [
            "ffmpeg", "-y",
            "-loop", "1",
            "-framerate", "30",
            "-t", dur_str,
            "-i", str(image_path.resolve()),
            "-vf", full_filter,
            "-c:v", "libx264",
            "-preset", "ultrafast",
            "-crf", "20",
            "-r", "30",
            "-an",
            str(output_mp4_path.resolve())
        ]

        try:
            res = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, timeout=30)
            if res.returncode == 0 and output_mp4_path.exists() and output_mp4_path.stat().st_size > 10_000:
                return output_mp4_path
            else:
                print(f"[AIVisualGenerator] FFmpeg error: {res.stderr[-200:]}", flush=True)
                return None
        except Exception as e:
            print(f"[AIVisualGenerator] Render exception: {e}", flush=True)
            return None

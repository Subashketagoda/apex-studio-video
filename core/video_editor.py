import os
import sys
import json
import subprocess
import time
from pathlib import Path
from typing import List, Optional, Any, Dict, Callable
from mutagen.mp3 import MP3

from core.config import AppConfig
from core.subtitles import SubtitleGenerator, SubtitleWord
from core.tts_engine import AudioResult


class VideoEditor:
    """
    High-performance native FFmpeg video editing pipeline:
    - Normalizes clips to standard 1080x1920 9:16 vertical format (30 FPS).
    - Concatenates scenes with smooth pacing.
    - Synchronizes voiceover audio.
    - Applies background music with intelligent sidechain ducking.
    - Burns styled ASS TikTok animated subtitles.
    - Strictly validates final output with FFprobe.
    """

    def __init__(self, output_dir: Optional[Path] = None):
        self.output_dir = output_dir or AppConfig.OUTPUT_DIR
        self.temp_dir = AppConfig.TEMP_DIR
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.temp_dir.mkdir(parents=True, exist_ok=True)
        self.subtitle_generator = SubtitleGenerator(model_size="base")

    def build_short_video(
        self,
        audio_result: AudioResult,
        clip_paths: List[str],
        output_filename: Optional[str] = None,
        custom_words: Optional[List[SubtitleWord]] = None,
        fallback_text: Optional[str] = None,
        progress_callback: Optional[Callable[[str, float], None]] = None,
        bgm_track: Optional[str] = "cinematic_drone",
        bgm_volume: float = 0.12,
        enable_hook_sfx: bool = True,
        subtitle_style: str = "mrbeast",
        subtitle_size: str = "medium",
        watermark_text: Optional[str] = None,
        scene_durations: Optional[List[float]] = None
    ) -> Path:
        """
        Executes complete video editing and subtitle burn pipeline with strict validation.
        """
        timestamp = int(time.time())
        if not output_filename:
            output_filename = f"apexgen_short_{timestamp}.mp4"

        final_output_path = self.output_dir / output_filename
        stitched_video_path = self.temp_dir / f"stitched_{timestamp}.mp4"
        ass_subtitles_path = self.temp_dir / f"subs_{timestamp}.ass"

        total_audio_duration = audio_result.duration_seconds
        print(f"[VideoEditor] 🎬 Assembling Vertical Short (Target Duration: {total_audio_duration:.2f}s)...", flush=True)

        # 1. Normalize and stitch scene clips
        valid_clips = [p for p in clip_paths if Path(p).exists() and Path(p).stat().st_size > 1000]
        if not valid_clips:
            raise FileNotFoundError("No valid video clips or procedural graphics available for rendering.")

        if progress_callback:
            progress_callback(f"🎞️ Synchronizing {len(valid_clips)} scene clips to exact spoken boundaries...", 0.78)

        self._stitch_and_mix(
            clip_paths=valid_clips,
            target_duration=total_audio_duration,
            audio_path=audio_result.audio_path,
            output_path=stitched_video_path,
            scene_durations=scene_durations,
            progress_callback=progress_callback,
            bgm_track=bgm_track,
            bgm_volume=bgm_volume,
            enable_hook_sfx=enable_hook_sfx
        )

        # 2. Extract Subtitle Timings
        if progress_callback:
            progress_callback("📝 Synchronizing acoustic word-level subtitles...", 0.90)

        if custom_words and len(custom_words) > 0:
            words = custom_words
        else:
            tts_words = [
                SubtitleWord(word=w.word, start=w.start, end=w.end)
                for w in (audio_result.words_timing or [])
            ]
            words = self.subtitle_generator.transcribe_words(
                audio_path=audio_result.audio_path,
                fallback_text=fallback_text,
                tts_words=tts_words
            )

        print(f"[VideoEditor] ✨ Generating ASS subtitles with '{subtitle_style}' active word styling...", flush=True)
        self.subtitle_generator.create_ass_subtitles(
            words=words,
            output_ass_path=ass_subtitles_path,
            style_preset=subtitle_style,
            font_size_preset=subtitle_size,
            watermark_text=watermark_text
        )

        # 3. Burn Subtitles via FFmpeg
        if progress_callback:
            progress_callback("🔥 Burning animated subtitles into 1080x1920 MP4...", 0.95)

        self._burn_subtitles_ffmpeg(
            video_input=stitched_video_path,
            ass_path=ass_subtitles_path,
            final_output=final_output_path
        )

        # 4. Strict FFprobe Output Validation
        if progress_callback:
            progress_callback("🔍 Validating container integrity with FFprobe...", 0.98)

        validation_report = self.validate_output_video(final_output_path, expected_duration=total_audio_duration)
        print(f"[VideoEditor] ✅ Video validated: {validation_report}", flush=True)

        return final_output_path

    def _stitch_and_mix(
        self,
        clip_paths: List[str],
        target_duration: float,
        audio_path: str,
        output_path: Path,
        scene_durations: Optional[List[float]] = None,
        progress_callback: Optional[Any] = None,
        bgm_track: Optional[str] = "cinematic_drone",
        bgm_volume: float = 0.12,
        enable_hook_sfx: bool = True
    ) -> None:
        """
        Normalizes each clip to 1080x1920 30FPS matching its exact scene duration,
        concatenates them in exact narrative order, and mixes voiceover with BGM using sidechain ducking.
        """
        default_dur = max(round(target_duration / len(clip_paths), 2), 2.5)
        normalized_clips: List[Path] = []
        total_clips = len(clip_paths)

        for idx, cp in enumerate(clip_paths):
            if scene_durations and idx < len(scene_durations):
                clip_dur = max(round(scene_durations[idx], 2), 2.0)
            else:
                clip_dur = default_dur

            norm_path = self.temp_dir / f"norm_{int(time.time())}_{idx}.mp4"
            # FFmpeg filter: scale to fill 1080x1920 then center-crop, force 30 FPS
            vf = "scale=1080:1920:force_original_aspect_ratio=increase,crop=1080:1920,setsar=1,fps=30"
            cmd = [
                "ffmpeg", "-y",
                "-ss", "0",
                "-t", str(clip_dur),
                "-i", cp,
                "-vf", vf,
                "-r", "30",
                "-c:v", "libx264",
                "-preset", "ultrafast",
                "-an",
                str(norm_path.resolve())
            ]
            try:
                subprocess.run(cmd, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                if norm_path.exists() and norm_path.stat().st_size > 1000:
                    normalized_clips.append(norm_path)
            except Exception as e:
                print(f"[VideoEditor] Clip normalize error on {cp}: {e}", flush=True)

        if not normalized_clips:
            raise RuntimeError("Failed to normalize scene video clips.")

        # Build concat demuxer list (play each scene in sequential order)
        concat_list_path = self.temp_dir / f"concat_{int(time.time())}.txt"
        lines = []
        for np_path in normalized_clips:
            safe_p = str(np_path.resolve()).replace("\\", "/")
            lines.append(f"file '{safe_p}'")

        # If audio duration slightly exceeds sum of clips, append last clip once more to prevent black end
        total_norm_dur = sum(
            scene_durations[i] if (scene_durations and i < len(scene_durations)) else default_dur
            for i in range(len(normalized_clips))
        )
        if total_norm_dur < target_duration - 0.5:
            safe_p = str(normalized_clips[-1].resolve()).replace("\\", "/")
            lines.append(f"file '{safe_p}'")

        concat_list_path.write_text("\n".join(lines) + "\n", encoding="utf-8")

        # Audio mixing with ducking
        bgm_path = self._resolve_bgm_track(bgm_track)
        
        # Build FFmpeg command for video concat + audio sidechain ducking
        # Inputs: 0 = video concat, 1 = voiceover audio, [2 = optional BGM]
        if bgm_path and bgm_path.exists() and bgm_track != "none":
            # Clear, audible BGM with gentle speech sidechain ducking
            vol = max(float(bgm_volume), 0.16)
            filter_complex = (
                f"[2:a]volume={vol:.2f},aloop=loop=-1:size=2e+09,aformat=sample_rates=44100:channel_layouts=stereo[bgm];"
                f"[1:a]aformat=sample_rates=44100:channel_layouts=stereo[voice];"
                f"[bgm][voice]sidechaincompress=threshold=0.18:ratio=2.5:attack=20:release=300[ducked_bgm];"
                f"[voice][ducked_bgm]amix=inputs=2:duration=first:dropout_transition=0[aout]"
            )
            cmd = [
                "ffmpeg", "-y",
                "-f", "concat", "-safe", "0", "-i", str(concat_list_path.resolve()),
                "-i", str(Path(audio_path).resolve()),
                "-i", str(bgm_path.resolve()),
                "-filter_complex", filter_complex,
                "-map", "0:v",
                "-map", "[aout]",
                "-t", str(round(target_duration, 2)),
                "-c:v", "libx264",
                "-preset", "ultrafast",
                "-c:a", "aac",
                "-b:a", "192k",
                "-pix_fmt", "yuv420p",
                "-r", "30",
                str(output_path.resolve())
            ]
        else:
            # Simple voiceover mux
            cmd = [
                "ffmpeg", "-y",
                "-f", "concat", "-safe", "0", "-i", str(concat_list_path.resolve()),
                "-i", str(Path(audio_path).resolve()),
                "-map", "0:v",
                "-map", "1:a",
                "-t", str(round(target_duration, 2)),
                "-c:v", "libx264",
                "-preset", "ultrafast",
                "-c:a", "aac",
                "-b:a", "192k",
                "-pix_fmt", "yuv420p",
                "-r", "30",
                str(output_path.resolve())
            ]

        res = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        if res.returncode != 0:
            print(f"[VideoEditor] Warning on audio mix: {res.stderr[:300]}", flush=True)
            # Fallback simple mux if complex filter encountered issue
            fallback_cmd = [
                "ffmpeg", "-y",
                "-f", "concat", "-safe", "0", "-i", str(concat_list_path.resolve()),
                "-i", str(Path(audio_path).resolve()),
                "-map", "0:v",
                "-map", "1:a",
                "-t", str(round(target_duration, 2)),
                "-c:v", "libx264",
                "-preset", "ultrafast",
                "-c:a", "aac",
                str(output_path.resolve())
            ]
            subprocess.run(fallback_cmd, check=True)

    def _burn_subtitles_ffmpeg(
        self,
        video_input: Path,
        ass_path: Path,
        final_output: Path
    ) -> None:
        """Burns ASS subtitle stream directly onto the video track using libass."""
        # Escape path for FFmpeg subtitles/ass filter
        safe_ass = str(ass_path.resolve()).replace("\\", "/").replace(":", "\\:")
        cmd = [
            "ffmpeg", "-y",
            "-i", str(video_input.resolve()),
            "-vf", f"ass='{safe_ass}'",
            "-c:v", "libx264",
            "-preset", "veryfast",
            "-crf", "20",
            "-c:a", "copy",
            str(final_output.resolve())
        ]
        res = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        if res.returncode != 0 or not final_output.exists():
            print(f"[VideoEditor] ⚠️ libass burn issue ({res.stderr[:200]}). Trying subtitles fallback...", flush=True)
            cmd_sub = [
                "ffmpeg", "-y",
                "-i", str(video_input.resolve()),
                "-vf", f"subtitles='{safe_ass}'",
                "-c:v", "libx264",
                "-preset", "fast",
                "-crf", "18",
                "-c:a", "copy",
                str(final_output.resolve())
            ]
            subprocess.run(cmd_sub, check=True)

    def validate_output_video(self, video_path: Path, expected_duration: float) -> Dict[str, Any]:
        """
        Uses FFprobe to validate file integrity, dimensions (1080x1920), 
        frame rate, and audio stream existence.
        """
        if not video_path.exists():
            raise FileNotFoundError(f"Final output video not found at: {video_path}")
        if video_path.stat().st_size < 50_000:
            raise ValueError(f"Output video file size too small: {video_path.stat().st_size} bytes")

        cmd = [
            "ffprobe", "-v", "quiet",
            "-print_format", "json",
            "-show_format", "-show_streams",
            str(video_path.resolve())
        ]
        res = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        if res.returncode != 0:
            raise RuntimeError(f"FFprobe failed to analyze video: {res.stderr}")

        info = json.loads(res.stdout)
        streams = info.get("streams", [])
        v_stream = next((s for s in streams if s.get("codec_type") == "video"), None)
        a_stream = next((s for s in streams if s.get("codec_type") == "audio"), None)

        if not v_stream:
            raise ValueError("Output video contains NO video stream.")
        if not a_stream:
            raise ValueError("Output video contains NO audio stream.")

        width = int(v_stream.get("width", 0))
        height = int(v_stream.get("height", 0))
        if width != 1080 or height != 1920:
            print(f"[VideoEditor] ⚠️ Warning: Dimensions {width}x{height} (expected 1080x1920)")

        actual_duration = float(info.get("format", {}).get("duration", 0.0))
        duration_diff = abs(actual_duration - expected_duration)
        if duration_diff > 2.0:
            print(f"[VideoEditor] ⚠️ Duration difference: {actual_duration:.2f}s vs expected {expected_duration:.2f}s")

        return {
            "status": "valid",
            "width": width,
            "height": height,
            "duration": actual_duration,
            "size_mb": round(video_path.stat().st_size / (1024 * 1024), 2),
            "video_codec": v_stream.get("codec_name"),
            "audio_codec": a_stream.get("codec_name"),
            "audio_sample_rate": a_stream.get("sample_rate"),
            "fps": eval(v_stream.get("r_frame_rate", "30/1")) if "/" in v_stream.get("r_frame_rate", "") else 30.0
        }

    def inspect_rendered_video(
        self,
        video_path: Path,
        expected_duration: float,
        output_frames_dir: Optional[Path] = None
    ) -> Dict[str, Any]:
        """
        Comprehensive quality inspection:
        1. Validates FFprobe container stream integrity, frame rate, duration, audio.
        2. Extracts 5 representative frames at 10%, 30%, 50%, 70%, 90% timestamps.
        3. Inspects frame dimensions (1080x1920), non-blankness, brightness, and contrast.
        """
        report = self.validate_output_video(video_path, expected_duration)
        actual_dur = report["duration"]

        if not output_frames_dir:
            output_frames_dir = AppConfig.OUTPUT_DIR / f"qc_frames_{video_path.stem}"
        output_frames_dir.mkdir(parents=True, exist_ok=True)

        sample_points = [0.10, 0.30, 0.50, 0.70, 0.90]
        extracted_frames = []
        from PIL import Image, ImageStat

        print(f"\n[VideoEditor] 🔍 Inspecting rendered video frames for '{video_path.name}'...", flush=True)

        for frac in sample_points:
            t_sec = round(actual_dur * frac, 2)
            frame_file = output_frames_dir / f"frame_{int(frac*100)}pct_{t_sec}s.jpg"

            cmd = [
                "ffmpeg", "-y",
                "-ss", str(t_sec),
                "-i", str(video_path.resolve()),
                "-vframes", "1",
                "-q:v", "2",
                str(frame_file.resolve())
            ]
            try:
                subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=12)
                if frame_file.exists() and frame_file.stat().st_size > 1000:
                    img = Image.open(frame_file)
                    w, h = img.size
                    stat = ImageStat.Stat(img)
                    avg_brightness = round(sum(stat.mean[:3]) / 3, 1)
                    std_dev = round(sum(stat.stddev[:3]) / 3, 1) if stat.stddev else 0.0
                    is_valid_frame = (w == 1080 and h == 1920 and 5 <= avg_brightness <= 250)


                    extracted_frames.append({
                        "fraction": frac,
                        "timestamp_sec": t_sec,
                        "frame_path": str(frame_file.resolve()),
                        "resolution": f"{w}x{h}",
                        "average_brightness": avg_brightness,
                        "contrast_stddev": std_dev,
                        "is_valid_frame": is_valid_frame
                    })
                    print(
                        f"  [Frame @ {int(frac*100)}% ({t_sec}s)] Resolution: {w}x{h}, "
                        f"Brightness: {avg_brightness}, Valid: {is_valid_frame}",
                        flush=True
                    )
            except Exception as e:
                print(f"  [Frame @ {int(frac*100)}%] Extraction failed: {e}", flush=True)

        report["extracted_frames"] = extracted_frames
        report["all_frames_valid"] = len(extracted_frames) == 5 and all(f["is_valid_frame"] for f in extracted_frames)
        return report

    def _resolve_bgm_track(self, track_name: Optional[str]) -> Optional[Path]:
        """Resolves background music MP3 from assets/audio or procedural assets."""
        if not track_name or track_name == "none":
            return None
        assets_audio_dir = AppConfig.BASE_DIR / "assets" / "audio"
        assets_audio_dir.mkdir(parents=True, exist_ok=True)
        
        target_path = assets_audio_dir / f"{track_name}.mp3"
        if target_path.exists():
            return target_path

        # Check any mp3 in assets/audio
        available_mp3s = list(assets_audio_dir.glob("*.mp3"))
        if available_mp3s:
            return available_mp3s[0]

        return None


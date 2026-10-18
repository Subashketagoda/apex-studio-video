import os
import re
from pathlib import Path
from typing import List, Dict, Any, Optional
from pydantic import BaseModel

class SubtitleWord(BaseModel):
    """Timestamped individual spoken word."""
    word: str
    start: float  # seconds
    end: float    # seconds


class SubtitleGenerator:
    """
    Extracts word-level timestamps using faster-whisper and generates
    high-retention, animated TikTok/Shorts-style Advanced SubStation Alpha (.ass) subtitles.
    """

    def __init__(self, model_size: str = "base"):
        self.model_size = model_size
        self._model = None

    def transcribe_words(
        self,
        audio_path: str,
        fallback_text: Optional[str] = None,
        tts_words: Optional[List[SubtitleWord]] = None
    ) -> List[SubtitleWord]:
        """
        Transcribes voiceover audio to extract exact word-level timing.
        Hierarchy:
        1. Faster-Whisper audio transcription (acoustic ground truth)
        2. Edge-TTS WordBoundary events (synthesizer metadata)
        3. Documented duration-proportional interpolation fallback
        """
        # Tier 1: Faster-Whisper Acoustic Word Alignment
        try:
            from faster_whisper import WhisperModel
            if self._model is None:
                self._model = WhisperModel(self.model_size, device="cpu", compute_type="int8")

            segments, info = self._model.transcribe(audio_path, word_timestamps=True, language="en")
            all_words: List[SubtitleWord] = []
            for seg in segments:
                if seg.words:
                    for w in seg.words:
                        clean = w.word.strip()
                        if clean:
                            all_words.append(
                                SubtitleWord(
                                    word=clean,
                                    start=round(w.start, 2),
                                    end=round(w.end, 2)
                                )
                            )

            if len(all_words) >= 5:
                print(f"[SubtitleGenerator] 🎯 Faster-Whisper aligned {len(all_words)} words acoustically.", flush=True)
                return all_words
        except Exception as e:
            print(f"[SubtitleGenerator] ℹ️ Faster-Whisper alignment bypassed ({e}). Evaluating TTS boundaries...", flush=True)

        # Tier 2: Edge-TTS Word Boundary Events
        if tts_words and len(tts_words) >= 5:
            print(f"[SubtitleGenerator] 🎙️ Using {len(tts_words)} Edge-TTS synthesized word boundaries.", flush=True)
            return tts_words

        # Tier 3: Documented Proportional Alignment Fallback
        if fallback_text:
            print("[SubtitleGenerator] ⚠️ Acoustic transcription uncertain. Using documented duration interpolation fallback.", flush=True)
            from mutagen.mp3 import MP3
            audio = MP3(audio_path)
            total_dur = float(audio.info.length)
            raw_words = fallback_text.strip().split()
            if raw_words:
                time_per_word = total_dur / len(raw_words)
                return [
                    SubtitleWord(
                        word=w,
                        start=round(i * time_per_word, 2),
                        end=round((i + 1) * time_per_word, 2)
                    )
                    for i, w in enumerate(raw_words)
                ]

        return []

    def create_ass_subtitles(
        self,
        words: List[SubtitleWord],
        output_ass_path: Path,
        max_words_per_group: int = 4,
        style_preset: str = "mrbeast",
        font_size_preset: str = "medium",
        watermark_text: Optional[str] = None
    ) -> Path:
        """
        Compiles an ASS subtitle file with active spoken word highlighted in bold neon yellow/gold,
        white base text, thick black outline, and safe vertical margins for YouTube Shorts (1080x1920).
        """
        # Style color definitions in ASS format: &HAABBGGRR
        styles = {
            "mrbeast": {
                "active": r"&H0000D7FF&",   # Rich Gold / Amber Yellow
                "base": r"&H00FFFFFF&",     # Pure White
                "outline": r"&H00000000&",  # Solid Black
                "outline_w": 6,
                "shadow_w": 2
            },
            "hormozi": {
                "active": r"&H0000FF00&",   # Electric Neon Green
                "base": r"&H00FFFFFF&",     # Crisp White
                "outline": r"&H00000000&",
                "outline_w": 7,
                "shadow_w": 2
            },
            "red_alert": {
                "active": r"&H000022FF&",   # Crimson Red
                "base": r"&H00FFFFFF&",
                "outline": r"&H00000000&",
                "outline_w": 6,
                "shadow_w": 2
            },
            "cyber_cyan": {
                "active": r"&H00FFFF00&",   # Cyan
                "base": r"&H00FFFFFF&",
                "outline": r"&H00000000&",
                "outline_w": 6,
                "shadow_w": 2
            }
        }

        cfg = styles.get(style_preset, styles["mrbeast"])
        
        # Font size calculation for 1080x1920 vertical format
        font_sizes = {"compact": 58, "medium": 68, "large": 82}
        font_size = font_sizes.get(font_size_preset, 68)

        # Vertical safe margin: Place subtitles at lower-third (~1420px from top, MarginV=360 from bottom)
        # This completely avoids YouTube Shorts top header and bottom title/music badges!
        margin_v = 360

        ass_header = f"""[Script Info]
Title: ApexGen Animated Vertical Subtitles
ScriptType: v4.00+
WrapStyle: 0
ScaledBorderAndShadow: yes
YCbCr Matrix: TV.601
PlayResX: 1080
PlayResY: 1920

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: TikTokActive,Arial,{font_size},{cfg['base']},&H000000FF,{cfg['outline']},&H80000000,-1,0,0,0,100,100,1,0,1,{cfg['outline_w']},{cfg['shadow_w']},2,60,60,{margin_v},1
Style: Watermark,Arial,34,&H80FFFFFF,&H000000FF,&H80000000,&H00000000,-1,0,0,0,100,100,0,0,1,3,1,8,40,40,200,1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""

        events = []

        # Optional watermark banner
        if watermark_text and watermark_text.strip():
            end_time_str = "01:00:00.00"
            if words:
                end_time_str = self._format_ass_time(words[-1].end + 2.0)
            events.append(f"Dialogue: 0,00:00:00.00,{end_time_str},Watermark,,0,0,0,,{watermark_text.strip()}")

        # Group words into short phrases (3 to 4 words)
        grouped_words: List[List[SubtitleWord]] = []
        current_group: List[SubtitleWord] = []
        for w in words:
            current_group.append(w)
            # Break group on punctuation or max length
            if len(current_group) >= max_words_per_group or any(p in w.word for p in [".", "!", "?", ","]):
                grouped_words.append(current_group)
                current_group = []
        if current_group:
            grouped_words.append(current_group)

        # Generate active word highlight events for each slice
        for grp in grouped_words:
            if not grp:
                continue
            for active_idx, target_word in enumerate(grp):
                start_str = self._format_ass_time(target_word.start)
                end_str = self._format_ass_time(target_word.end)

                # Format text with the active word in gold/yellow and inactive words in white
                rendered_tokens = []
                for idx, w in enumerate(grp):
                    clean_text = self._escape_ass(w.word)
                    if idx == active_idx:
                        # Highlight active word with gold/yellow color and slight scaling
                        rendered_tokens.append(f"{{\\c{cfg['active']}\\b1}}{clean_text}{{\\c{cfg['base']}\\b0}}")
                    else:
                        rendered_tokens.append(clean_text)

                line_text = " ".join(rendered_tokens)
                events.append(f"Dialogue: 1,{start_str},{end_str},TikTokActive,,0,0,0,,{line_text}")

        output_ass_path.parent.mkdir(parents=True, exist_ok=True)
        output_ass_path.write_text(ass_header + "\n".join(events) + "\n", encoding="utf-8")
        return output_ass_path

    @staticmethod
    def _format_ass_time(seconds: float) -> str:
        """Formats seconds into ASS timestamp: H:MM:SS.cs"""
        hrs = int(seconds // 3600)
        mins = int((seconds % 3600) // 60)
        secs = int(seconds % 60)
        centis = int(round((seconds - int(seconds)) * 100))
        if centis >= 100:
            centis = 99
        return f"{hrs:d}:{mins:02d}:{secs:02d}.{centis:02d}"

    @staticmethod
    def _escape_ass(text: str) -> str:
        """Escapes ASS special formatting characters."""
        return text.replace("\\", "").replace("{", "").replace("}", "")

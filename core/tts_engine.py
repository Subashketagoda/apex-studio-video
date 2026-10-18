import abc
import os
import sys
import asyncio
import subprocess
import time
from pathlib import Path
from typing import Optional, List, Dict, Any
from pydantic import BaseModel
from mutagen.mp3 import MP3

from core.config import AppConfig


class WordTiming(BaseModel):
    """Word-level timing information for subtitle synchronization."""
    word: str
    start: float  # seconds
    end: float    # seconds


class AudioResult(BaseModel):
    """Result of validated voiceover generation."""
    audio_path: str
    duration_seconds: float
    words_timing: List[WordTiming] = []
    provider: str = "edge-tts"
    voice: str = "en-US-ChristopherNeural"



class TTSProvider(abc.ABC):
    """Abstract interface for voice synthesis providers."""

    @abc.abstractmethod
    def generate(
        self,
        text: str,
        output_path: Path,
        voice: str,
        rate: str = "+0%",
        volume: str = "+0%",
        pitch: str = "+0Hz"
    ) -> AudioResult:
        """Synthesizes text into speech and returns AudioResult."""
        pass


class EdgeTTSProvider(TTSProvider):
    """
    Free Microsoft Edge Neural TTS provider.
    High-definition natural speech with sub-second word boundary timing extraction.
    """

    def generate(
        self,
        text: str,
        output_path: Path,
        voice: str,
        rate: str = "+0%",
        volume: str = "+0%",
        pitch: str = "+0Hz"
    ) -> AudioResult:
        max_retries = 3
        last_error = None

        for attempt in range(1, max_retries + 1):
            try:
                return asyncio.run(
                    self._generate_async(text, output_path, voice, rate, volume, pitch)
                )
            except Exception as e:
                last_error = e
                print(f"[EdgeTTSProvider] ⚠️ Attempt {attempt}/{max_retries} failed ({e}). Retrying...", flush=True)
                time.sleep(1.0 * attempt)

        raise RuntimeError(f"Edge-TTS voiceover generation failed after {max_retries} attempts: {last_error}")

    async def _generate_async(
        self,
        text: str,
        output_path: Path,
        voice: str,
        rate: str,
        volume: str,
        pitch: str
    ) -> AudioResult:
        import edge_tts

        communicate = edge_tts.Communicate(
            text=text,
            voice=voice,
            rate=rate,
            volume=volume,
            pitch=pitch
        )

        words_timing: List[WordTiming] = []
        with open(output_path, "wb") as f:
            async for chunk in communicate.stream():
                if chunk["type"] == "audio":
                    f.write(chunk["data"])
                elif chunk["type"] == "WordBoundary":
                    offset_sec = chunk["offset"] / 10_000_000.0
                    duration_sec = chunk["duration"] / 10_000_000.0
                    clean_w = chunk["text"].strip()
                    if clean_w:
                        words_timing.append(
                            WordTiming(
                                word=clean_w,
                                start=round(offset_sec, 2),
                                end=round(offset_sec + duration_sec, 2)
                            )
                        )
                elif chunk["type"] == "SentenceBoundary":
                    sent_offset = chunk["offset"] / 10_000_000.0
                    sent_dur = chunk["duration"] / 10_000_000.0
                    sent_text = chunk["text"].strip()
                    s_words = sent_text.split()
                    if s_words and sent_dur > 0:
                        w_step = sent_dur / len(s_words)
                        for idx, sw in enumerate(s_words):
                            words_timing.append(
                                WordTiming(
                                    word=sw,
                                    start=round(sent_offset + (idx * w_step), 2),
                                    end=round(sent_offset + ((idx + 1) * w_step), 2)
                                )
                            )

        audio = MP3(str(output_path.resolve()))
        duration = float(audio.info.length)

        # Ensure words_timing is populated if boundary events were sparse
        if not words_timing:
            raw_w = text.strip().split()
            if raw_w and duration > 0:
                step = duration / len(raw_w)
                words_timing = [
                    WordTiming(
                        word=w,
                        start=round(i * step, 2),
                        end=round((i + 1) * step, 2)
                    )
                    for i, w in enumerate(raw_w)
                ]
        duration = float(audio.info.length)

        return AudioResult(
            audio_path=str(output_path.resolve()),
            duration_seconds=round(duration, 2),
            words_timing=words_timing,
            provider="edge-tts",
            voice=voice
        )


class ElevenLabsProvider(TTSProvider):
    """ElevenLabs voice synthesis provider behind the abstract interface."""

    def generate(
        self,
        text: str,
        output_path: Path,
        voice: str,
        rate: str = "+0%",
        volume: str = "+0%",
        pitch: str = "+0Hz"
    ) -> AudioResult:
        api_key = AppConfig.ELEVENLABS_API_KEY
        if not api_key:
            raise ValueError("ELEVENLABS_API_KEY is not configured in .env. Switch to Edge-TTS for free voiceover.")

        try:
            from elevenlabs.client import ElevenLabs
        except ImportError:
            raise ImportError("elevenlabs package is not installed. Run `pip install elevenlabs`.")

        client = ElevenLabs(api_key=api_key)
        voice_id = voice or AppConfig.ELEVENLABS_VOICE_ID or "21m00Tcm4TlvDq8ikWAM"

        max_retries = 3
        for attempt in range(1, max_retries + 1):
            try:
                audio_stream = client.text_to_speech.convert(
                    voice_id=voice_id,
                    text=text,
                    model_id="eleven_multilingual_v2",
                )
                with open(output_path, "wb") as f:
                    for chunk in audio_stream:
                        f.write(chunk)

                audio = MP3(str(output_path.resolve()))
                duration = float(audio.info.length)

                return AudioResult(
                    audio_path=str(output_path.resolve()),
                    duration_seconds=round(duration, 2),
                    words_timing=[],
                    provider="elevenlabs",
                    voice=voice_id
                )
            except Exception as e:
                if attempt == max_retries:
                    raise RuntimeError(f"ElevenLabs generation failed: {e}")
                time.sleep(1.5 * attempt)

        raise RuntimeError("ElevenLabs generation failed.")


class TTSEngine:
    """Facade for audio generation with provider selection, validation, and duration measurement."""

    PROVIDERS: Dict[str, TTSProvider] = {
        "edge-tts": EdgeTTSProvider(),
        "elevenlabs": ElevenLabsProvider(),
    }

    def __init__(
        self,
        provider: Optional[str] = None,
        voice: Optional[str] = None,
        output_dir: Optional[Path] = None,
    ):
        self.provider_name = (provider or AppConfig.TTS_PROVIDER).lower()
        self.voice = voice or AppConfig.EDGE_TTS_VOICE
        self.output_dir = output_dir or AppConfig.TEMP_DIR
        self.output_dir.mkdir(parents=True, exist_ok=True)

        if self.provider_name not in self.PROVIDERS:
            raise ValueError(f"Unknown TTS provider: {self.provider_name}. Supported: {list(self.PROVIDERS.keys())}")
        self.provider = self.PROVIDERS[self.provider_name]

    def generate_voiceover(
        self,
        text: str,
        filename: str = "voiceover.mp3",
        rate: str = "+0%",
        volume: str = "+0%",
        pitch: str = "+0Hz"
    ) -> AudioResult:
        if not text or not text.strip():
            raise ValueError("Voiceover narration text cannot be empty.")

        output_path = self.output_dir / filename
        if output_path.exists():
            try:
                output_path.unlink()
            except Exception:
                pass

        result = self.provider.generate(
            text=text,
            output_path=output_path,
            voice=self.voice,
            rate=rate,
            volume=volume,
            pitch=pitch
        )

        # Strict audio validation
        self._validate_audio(output_path, result.duration_seconds)
        return result

    @staticmethod
    def _validate_audio(path: Path, duration: float) -> None:
        """Verifies file existence, minimum size, valid MP3 header, and non-zero duration."""
        if not path.exists():
            raise FileNotFoundError(f"Generated audio file missing at {path}")
        if path.stat().st_size < 1000:
            raise ValueError(f"Generated audio file is too small ({path.stat().st_size} bytes)")
        if duration <= 0.5:
            raise ValueError(f"Generated audio duration is invalid ({duration:.2f}s)")

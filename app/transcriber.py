"""
Whisper ASR wrapper.

Transcribes audio files and returns full text plus per-segment timestamps.
Models are loaded once and cached in-process.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

_MODEL_CACHE: dict[str, Any] = {}


@dataclass
class Transcription:
    text: str
    segments: list[dict[str, Any]]  # raw Whisper segment dicts (start, end, text, …)
    language: str
    audio_path: str


def transcribe(
    audio_path: str | Path,
    model_name: str = "base",
    language: str | None = None,
) -> Transcription:
    """
    Transcribe an audio file with Whisper.

    Args:
        audio_path: path to .wav / .mp3 / .m4a or any ffmpeg-supported format
        model_name: "tiny" | "base" | "small" | "medium" | "large"
        language:   ISO-639-1 code ("pt", "en", …); None = auto-detect
    """
    model = _load(model_name)
    options: dict[str, Any] = {"verbose": False}
    if language:
        options["language"] = language

    result = model.transcribe(str(audio_path), **options)
    return Transcription(
        text=result["text"].strip(),
        segments=result["segments"],
        language=result.get("language", ""),
        audio_path=str(audio_path),
    )


def _load(name: str) -> Any:
    if name not in _MODEL_CACHE:
        import whisper  # openai-whisper; imported lazily so the module loads without GPU
        _MODEL_CACHE[name] = whisper.load_model(name)
    return _MODEL_CACHE[name]

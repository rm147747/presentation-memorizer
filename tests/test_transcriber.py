"""Tests for transcriber.py — Whisper is mocked throughout."""
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from app.transcriber import Transcription, transcribe, _MODEL_CACHE


def _make_mock_model(text="hello world", segments=None, language="en"):
    model = MagicMock()
    model.transcribe.return_value = {
        "text": f"  {text}  ",
        "segments": segments or [{"start": 0.0, "end": 1.0, "text": text}],
        "language": language,
    }
    return model


# ── transcribe ────────────────────────────────────────────────────────────────

def test_transcribe_returns_transcription(tmp_path):
    audio = tmp_path / "test.wav"
    audio.write_bytes(b"fake")
    mock_model = _make_mock_model()
    with patch("app.transcriber._load", return_value=mock_model):
        result = transcribe(audio)
    assert isinstance(result, Transcription)


def test_transcribe_strips_whitespace(tmp_path):
    audio = tmp_path / "test.wav"
    audio.write_bytes(b"fake")
    mock_model = _make_mock_model(text="  trimmed text  ")
    with patch("app.transcriber._load", return_value=mock_model):
        result = transcribe(audio)
    assert result.text == "trimmed text"


def test_transcribe_passes_language(tmp_path):
    audio = tmp_path / "test.wav"
    audio.write_bytes(b"fake")
    mock_model = _make_mock_model(language="pt")
    with patch("app.transcriber._load", return_value=mock_model):
        result = transcribe(audio, language="pt")
    _, kwargs = mock_model.transcribe.call_args
    assert kwargs.get("language") == "pt"


def test_transcribe_no_language_option_when_none(tmp_path):
    audio = tmp_path / "test.wav"
    audio.write_bytes(b"fake")
    mock_model = _make_mock_model()
    with patch("app.transcriber._load", return_value=mock_model):
        transcribe(audio, language=None)
    _, kwargs = mock_model.transcribe.call_args
    assert "language" not in kwargs


def test_transcribe_audio_path_stored(tmp_path):
    audio = tmp_path / "speech.mp3"
    audio.write_bytes(b"fake")
    mock_model = _make_mock_model()
    with patch("app.transcriber._load", return_value=mock_model):
        result = transcribe(audio)
    assert result.audio_path == str(audio)


def test_transcribe_segments_forwarded(tmp_path):
    audio = tmp_path / "test.wav"
    audio.write_bytes(b"fake")
    segs = [{"start": 0.0, "end": 2.0, "text": "hi"}]
    mock_model = _make_mock_model(segments=segs)
    with patch("app.transcriber._load", return_value=mock_model):
        result = transcribe(audio)
    assert result.segments == segs


# ── _load / caching ───────────────────────────────────────────────────────────

def test_load_caches_model(tmp_path):
    _MODEL_CACHE.clear()
    mock_whisper = MagicMock()
    mock_model = _make_mock_model()
    mock_whisper.load_model.return_value = mock_model
    with patch.dict("sys.modules", {"whisper": mock_whisper}):
        from app.transcriber import _load
        m1 = _load("base")
        m2 = _load("base")
    assert m1 is m2
    assert mock_whisper.load_model.call_count == 1
    _MODEL_CACHE.clear()


def test_load_different_models_not_shared(tmp_path):
    _MODEL_CACHE.clear()
    mock_whisper = MagicMock()
    mock_whisper.load_model.side_effect = lambda name: MagicMock(name=name)
    with patch.dict("sys.modules", {"whisper": mock_whisper}):
        from app.transcriber import _load
        m_base = _load("base")
        m_small = _load("small")
    assert m_base is not m_small
    _MODEL_CACHE.clear()

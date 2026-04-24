"""Shared pytest fixtures — includes a Whisper mock so tests run without GPU."""
from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest


@pytest.fixture
def whisper_mock():
    """
    Replace app.transcriber.transcribe with a deterministic mock.
    Inject into tests that call the transcriber indirectly (API, etc.).
    """
    fake = MagicMock()
    fake.text = "hello world this is a test"
    fake.language = "pt"
    fake.audio_path = "/tmp/test.wav"
    fake.segments = [
        {"start": 0.0, "end": 1.5, "text": "hello world"},
        {"start": 1.5, "end": 3.0, "text": "this is a test"},
    ]
    with patch("app.transcriber.transcribe", return_value=fake) as mock:
        yield mock


@pytest.fixture
def sample_segments():
    return [
        {"start": 0.0, "end": 1.0, "text": "hello world"},
        {"start": 1.0, "end": 2.0, "text": "this is fine"},
        {"start": 5.0, "end": 6.0, "text": "here after pause"},  # 3 s gap → hesitation
    ]


@pytest.fixture
def sample_report_data():
    from app.reporter import ReportData, SessionSummary
    return ReportData(
        presentation_title="Fixture Presentation",
        sessions=[
            SessionSummary("1", "2024-03-01T09:00:00", 720.0, 0.25),
        ],
        segments=[
            {"text": "Easy part.", "difficulty_score": 0.1, "attempts": 6},
            {"text": "Hard part.", "difficulty_score": 0.9, "attempts": 2},
        ],
        word_pairs=[("rápido", "lento")],
    )

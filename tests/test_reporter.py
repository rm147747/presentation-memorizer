"""Tests for reporter.py"""
import json
import tempfile
from pathlib import Path

import pytest

from app.reporter import (
    DOMINATED_THRESHOLD,
    UNSTABLE_THRESHOLD,
    ReportData,
    SessionSummary,
    _score_colour,
    export_json,
    export_pdf,
)


def _make_data(**overrides) -> ReportData:
    defaults = dict(
        presentation_title="Test Presentation",
        sessions=[
            SessionSummary("1", "2024-01-01T10:00:00", 600.0, 0.3),
            SessionSummary("2", "2024-01-02T10:00:00", 900.0, 0.15),
        ],
        segments=[
            {"text": "Introduction paragraph.", "difficulty_score": 0.1, "attempts": 5},
            {"text": "Difficult section here.", "difficulty_score": 0.8, "attempts": 3},
            {"text": "Moderate difficulty.", "difficulty_score": 0.4, "attempts": 4},
        ],
        word_pairs=[("quick", "slow"), ("beautiful", "nice")],
    )
    defaults.update(overrides)
    return ReportData(**defaults)


# ── JSON export ───────────────────────────────────────────────────────────────

def test_json_creates_file():
    with tempfile.TemporaryDirectory() as tmp:
        path = export_json(_make_data(), Path(tmp) / "report.json")
        assert path.exists()


def test_json_valid_structure():
    with tempfile.TemporaryDirectory() as tmp:
        path = export_json(_make_data(), Path(tmp) / "report.json")
        data = json.loads(path.read_text(encoding="utf-8"))
        assert data["presentation_title"] == "Test Presentation"
        assert len(data["sessions"]) == 2
        assert len(data["segments"]) == 3


def test_json_word_pairs_preserved():
    with tempfile.TemporaryDirectory() as tmp:
        path = export_json(_make_data(), Path(tmp) / "report.json")
        data = json.loads(path.read_text(encoding="utf-8"))
        assert ["quick", "slow"] in data["word_pairs"]


def test_json_generated_at_set():
    with tempfile.TemporaryDirectory() as tmp:
        path = export_json(_make_data(), Path(tmp) / "r.json")
        data = json.loads(path.read_text(encoding="utf-8"))
        assert data["generated_at"]  # non-empty


def test_json_empty_sessions():
    with tempfile.TemporaryDirectory() as tmp:
        data = _make_data(sessions=[], word_pairs=[])
        path = export_json(data, Path(tmp) / "empty.json")
        loaded = json.loads(path.read_text(encoding="utf-8"))
        assert loaded["sessions"] == []


# ── PDF export ────────────────────────────────────────────────────────────────

def test_pdf_creates_file():
    with tempfile.TemporaryDirectory() as tmp:
        path = export_pdf(_make_data(), Path(tmp) / "report.pdf")
        assert path.exists()


def test_pdf_header():
    with tempfile.TemporaryDirectory() as tmp:
        path = export_pdf(_make_data(), Path(tmp) / "report.pdf")
        content = path.read_bytes()
        assert content[:4] == b"%PDF"


def test_pdf_non_empty():
    with tempfile.TemporaryDirectory() as tmp:
        path = export_pdf(_make_data(), Path(tmp) / "report.pdf")
        assert path.stat().st_size > 1_000  # at least 1 KB


def test_pdf_with_empty_word_pairs():
    with tempfile.TemporaryDirectory() as tmp:
        data = _make_data(word_pairs=[])
        path = export_pdf(data, Path(tmp) / "report.pdf")
        assert path.exists()


# ── Score colour helper ───────────────────────────────────────────────────────

def test_colour_dominated():
    assert _score_colour(0.0) == "#27ae60"
    assert _score_colour(DOMINATED_THRESHOLD) == "#27ae60"


def test_colour_unstable():
    assert _score_colour(DOMINATED_THRESHOLD + 0.01) == "#e67e22"
    assert _score_colour(UNSTABLE_THRESHOLD) == "#e67e22"


def test_colour_critical():
    assert _score_colour(UNSTABLE_THRESHOLD + 0.01) == "#e74c3c"
    assert _score_colour(1.0) == "#e74c3c"


# ── ReportData auto-timestamp ─────────────────────────────────────────────────

def test_generated_at_auto():
    data = _make_data()
    # accepts either "Z" or "+00:00" UTC suffix
    assert data.generated_at.endswith("Z") or data.generated_at.endswith("+00:00")


def test_generated_at_custom():
    data = _make_data(generated_at="2024-06-01T00:00:00Z")
    assert data.generated_at == "2024-06-01T00:00:00Z"

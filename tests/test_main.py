"""Integration tests for FastAPI endpoints in main.py."""
from __future__ import annotations

import io
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.database import Base
from app.transcriber import Transcription


# ── Fixtures ──────────────────────────────────────────────────────────────────

@pytest.fixture
def session_factory():
    # StaticPool keeps a single shared connection so the in-memory DB persists
    # across all Sessions created by the factory.
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine, expire_on_commit=False)


@pytest.fixture
def client(session_factory):
    with patch("app.main._SessionFactory", session_factory):
        from app.main import app
        with TestClient(app) as c:
            yield c


def _fake_transcription(text="hello world"):
    return Transcription(
        text=text,
        segments=[{"start": 0.0, "end": 1.0, "text": text}],
        language="en",
        audio_path="/tmp/fake.wav",
    )


def _audio_file():
    return ("audio.wav", io.BytesIO(b"RIFF\x00\x00\x00\x00WAVEfmt "), "audio/wav")


# ── /presentations/ ───────────────────────────────────────────────────────────

def test_create_presentation_status(client):
    r = client.post("/presentations/", json={"title": "My Talk", "text": "Hello world.\nLine two."})
    assert r.status_code == 201


def test_create_presentation_body(client):
    r = client.post("/presentations/", json={"title": "Demo", "text": "Para one.\nPara two.\nPara three."})
    body = r.json()
    assert body["title"] == "Demo"
    assert body["segment_count"] == 3
    assert "id" in body


def test_create_presentation_single_paragraph(client):
    r = client.post("/presentations/", json={"title": "T", "text": "Only one paragraph."})
    assert r.json()["segment_count"] == 1


# ── /degrade ──────────────────────────────────────────────────────────────────

def test_degrade_level1(client):
    r = client.post("/degrade", json={"text": "Hello world", "level": 1})
    assert r.status_code == 200
    assert r.json()["text"] == "Hello world"


def test_degrade_level4(client):
    r = client.post("/degrade", json={"text": "Hello world", "level": 4})
    assert r.json()["text"] == ""


def test_degrade_invalid_level(client):
    r = client.post("/degrade", json={"text": "x", "level": 5})
    assert r.status_code == 400


def test_degrade_level2_has_blanks(client):
    r = client.post("/degrade", json={"text": "The quick brown fox", "level": 2, "seed": 0})
    assert r.status_code == 200
    body = r.json()
    assert "text" in body and "blanked_indices" in body


# ── /sessions/ ────────────────────────────────────────────────────────────────

def test_start_session_not_found(client):
    r = client.post("/sessions/", params={"presentation_id": 999, "level": 1})
    assert r.status_code == 404


def test_start_session_success(client):
    pres = client.post("/presentations/", json={"title": "T", "text": "a"}).json()
    r = client.post("/sessions/", params={"presentation_id": pres["id"], "level": 2})
    assert r.status_code == 201
    assert "session_id" in r.json()


# ── /presentations/{id}/schedule ──────────────────────────────────────────────

def test_get_schedule_not_found(client):
    r = client.get("/presentations/999/schedule")
    assert r.status_code == 404


def test_get_schedule_success(client):
    pres = client.post("/presentations/", json={"title": "T", "text": "a\nb"}).json()
    r = client.get(f"/presentations/{pres['id']}/schedule")
    assert r.status_code == 200
    body = r.json()
    assert "summary" in body
    assert "repeat_segments" in body


def test_get_schedule_unseen_all_repeat(client):
    pres = client.post("/presentations/", json={"title": "T", "text": "a\nb\nc"}).json()
    r = client.get(f"/presentations/{pres['id']}/schedule")
    body = r.json()
    # Unseen segments have score=1.0 > 0.5 threshold → all should repeat
    assert len(body["repeat_segments"]) == 3


# ── /presentations/{id}/report ────────────────────────────────────────────────

def test_report_not_found(client):
    r = client.get("/presentations/999/report")
    assert r.status_code == 404


def test_report_json(client, tmp_path):
    pres = client.post("/presentations/", json={"title": "Talk", "text": "a\nb"}).json()
    with patch("app.main.REPORT_DIR", tmp_path):
        r = client.get(f"/presentations/{pres['id']}/report", params={"fmt": "json"})
    assert r.status_code == 200
    assert r.headers["content-type"] == "application/json"


def test_report_invalid_format(client):
    pres = client.post("/presentations/", json={"title": "T", "text": "a"}).json()
    r = client.get(f"/presentations/{pres['id']}/report", params={"fmt": "xml"})
    assert r.status_code == 422  # validation error from Query pattern


def test_report_pdf(client, tmp_path):
    pres = client.post("/presentations/", json={"title": "T", "text": "a"}).json()
    with patch("app.main.REPORT_DIR", tmp_path):
        r = client.get(f"/presentations/{pres['id']}/report", params={"fmt": "pdf"})
    assert r.status_code == 200
    assert "pdf" in r.headers["content-type"]


def test_report_json_with_attempts_and_substitutions(client, tmp_path):
    # Covers lines 220-226: attempt re-diff loop with substitutions.
    pres = client.post("/presentations/", json={"title": "T", "text": "cats are great"}).json()
    sess = client.post("/sessions/", params={"presentation_id": pres["id"], "level": 1}).json()
    tx = _fake_transcription("dogs are great")
    with patch("app.main.transcribe", return_value=tx):
        client.post(
            f"/sessions/{sess['session_id']}/attempt",
            params={"segment_index": 0},
            files={"audio": _audio_file()},
        )
    with patch("app.main.REPORT_DIR", tmp_path):
        r = client.get(f"/presentations/{pres['id']}/report", params={"fmt": "json"})
    assert r.status_code == 200


# ── /presentations/{id}/reference-audio ──────────────────────────────────────

def test_reference_audio_not_found(client):
    f = _audio_file()
    r = client.post("/presentations/999/reference-audio", files={"audio": f})
    assert r.status_code == 404


def test_reference_audio_success(client, tmp_path):
    pres = client.post("/presentations/", json={"title": "T", "text": "hello world"}).json()
    tx = _fake_transcription("hello world")
    with patch("app.main.transcribe", return_value=tx), \
         patch("app.main.AUDIO_DIR", tmp_path):
        r = client.post(
            f"/presentations/{pres['id']}/reference-audio",
            files={"audio": _audio_file()},
        )
    assert r.status_code == 200
    body = r.json()
    assert "transcript" in body
    assert "coverage_pct" in body


# ── /sessions/{id}/attempt ────────────────────────────────────────────────────

def test_record_attempt_session_not_found(client):
    f = _audio_file()
    r = client.post(
        "/sessions/999/attempt",
        params={"segment_index": 0},
        files={"audio": f},
    )
    assert r.status_code == 404


def test_record_attempt_segment_not_found(client):
    pres = client.post("/presentations/", json={"title": "T", "text": "a"}).json()
    sess = client.post("/sessions/", params={"presentation_id": pres["id"], "level": 1}).json()
    f = _audio_file()
    with patch("app.transcriber.transcribe", return_value=_fake_transcription()):
        r = client.post(
            f"/sessions/{sess['session_id']}/attempt",
            params={"segment_index": 99},
            files={"audio": f},
        )
    assert r.status_code == 404


def test_record_attempt_success(client):
    pres = client.post("/presentations/", json={"title": "T", "text": "hello world"}).json()
    sess = client.post("/sessions/", params={"presentation_id": pres["id"], "level": 1}).json()
    f = _audio_file()
    with patch("app.main.transcribe", return_value=_fake_transcription("hello world")):
        r = client.post(
            f"/sessions/{sess['session_id']}/attempt",
            params={"segment_index": 0},
            files={"audio": f},
        )
    assert r.status_code == 200
    body = r.json()
    assert "transcript" in body
    assert "error_count" in body
    assert body["error_count"] == 0

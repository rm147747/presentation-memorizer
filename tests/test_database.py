"""Tests for database.py — uses an in-memory SQLite database."""
import pytest

from app.database import (
    Attempt,
    Presentation,
    Segment,
    TrainingSession,
    make_session_factory,
)


@pytest.fixture
def db():
    factory = make_session_factory(":memory:")
    with factory() as session:
        yield session


# ── make_session_factory ──────────────────────────────────────────────────────

def test_session_factory_returns_session(db):
    assert db is not None


# ── Presentation ──────────────────────────────────────────────────────────────

def test_create_presentation(db):
    pres = Presentation(title="My Talk", text="Hello world.")
    db.add(pres)
    db.commit()
    assert pres.id is not None


def test_presentation_has_no_reference_audio_by_default(db):
    pres = Presentation(title="T", text="x")
    db.add(pres)
    db.commit()
    assert pres.reference_audio is None


# ── Segment ───────────────────────────────────────────────────────────────────

def test_segment_difficulty_unseen(db):
    pres = Presentation(title="T", text="a\nb")
    db.add(pres)
    db.flush()
    seg = Segment(presentation_id=pres.id, segment_index=0, text="a")
    db.add(seg)
    db.commit()
    assert seg.difficulty_score == pytest.approx(1.0)


def test_segment_difficulty_with_attempts(db):
    pres = Presentation(title="T", text="a")
    db.add(pres)
    db.flush()
    seg = Segment(
        presentation_id=pres.id,
        segment_index=0,
        text="a",
        attempts=4,
        total_errors=2,
        total_hesitations=2,
    )
    db.add(seg)
    db.commit()
    assert seg.difficulty_score == pytest.approx(1.0)  # (2+2)/4


def test_segment_difficulty_perfect(db):
    pres = Presentation(title="T", text="a")
    db.add(pres)
    db.flush()
    seg = Segment(
        presentation_id=pres.id, segment_index=0, text="a", attempts=5,
        total_errors=0, total_hesitations=0
    )
    db.add(seg)
    db.commit()
    assert seg.difficulty_score == pytest.approx(0.0)


# ── TrainingSession ───────────────────────────────────────────────────────────

def test_create_training_session(db):
    pres = Presentation(title="T", text="a")
    db.add(pres)
    db.flush()
    sess = TrainingSession(presentation_id=pres.id, level=2)
    db.add(sess)
    db.commit()
    assert sess.id is not None
    assert sess.completed_at is None
    assert sess.mean_score is None


# ── Attempt ───────────────────────────────────────────────────────────────────

def test_create_attempt(db):
    pres = Presentation(title="T", text="a")
    db.add(pres)
    db.flush()
    sess = TrainingSession(presentation_id=pres.id, level=1)
    db.add(sess)
    db.flush()
    att = Attempt(
        session_id=sess.id,
        segment_index=0,
        attempt_text="a",
        error_count=1,
        hesitation_count=0,
    )
    db.add(att)
    db.commit()
    assert att.id is not None


# ── Cascade ───────────────────────────────────────────────────────────────────

def test_cascade_delete_segments(db):
    pres = Presentation(title="T", text="a\nb")
    db.add(pres)
    db.flush()
    db.add(Segment(presentation_id=pres.id, segment_index=0, text="a"))
    db.commit()
    pres_id = pres.id
    db.delete(pres)
    db.commit()
    remaining = db.query(Segment).filter_by(presentation_id=pres_id).all()
    assert remaining == []

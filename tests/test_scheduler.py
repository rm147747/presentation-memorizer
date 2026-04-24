"""Tests for scheduler.py"""
import pytest

from app.scheduler import REPEAT_THRESHOLD, Schedule, SegmentStats


def _schedule(*scores) -> Schedule:
    """Build a Schedule pre-loaded with fixed difficulty scores."""
    segs = []
    for i, score in enumerate(scores):
        s = SegmentStats(segment_index=i, text=f"Segment {i}")
        if score is not None:
            s.attempts = 10
            s.total_errors = int(score * 10)
            s.total_hesitations = 0
        segs.append(s)
    return Schedule(segments=segs)


# ── SegmentStats ──────────────────────────────────────────────────────────────

def test_unseen_score_is_one():
    seg = SegmentStats(segment_index=0, text="hello")
    assert seg.difficulty_score == pytest.approx(1.0)


def test_score_formula():
    seg = SegmentStats(segment_index=0, text="x", attempts=4, total_errors=2, total_hesitations=2)
    assert seg.difficulty_score == pytest.approx(1.0)  # (2+2)/4


def test_score_zero_on_perfect():
    seg = SegmentStats(segment_index=0, text="x", attempts=5, total_errors=0, total_hesitations=0)
    assert seg.difficulty_score == pytest.approx(0.0)


def test_needs_repeat_above_threshold():
    seg = SegmentStats(segment_index=0, text="x", attempts=2, total_errors=2, total_hesitations=0)
    assert seg.difficulty_score > REPEAT_THRESHOLD
    assert seg.needs_repeat


def test_no_repeat_below_threshold():
    seg = SegmentStats(segment_index=0, text="x", attempts=10, total_errors=1, total_hesitations=0)
    assert not seg.needs_repeat


# ── Schedule.from_paragraphs ──────────────────────────────────────────────────

def test_from_paragraphs_count():
    sched = Schedule.from_paragraphs(["a", "b", "c"])
    assert len(sched.segments) == 3


def test_from_paragraphs_indices():
    sched = Schedule.from_paragraphs(["alpha", "beta"])
    assert sched.segments[0].segment_index == 0
    assert sched.segments[1].segment_index == 1


def test_from_paragraphs_unseen_score():
    sched = Schedule.from_paragraphs(["x"])
    assert sched.segments[0].difficulty_score == pytest.approx(1.0)


# ── Schedule.record_attempt ───────────────────────────────────────────────────

def test_record_attempt_increments():
    sched = Schedule.from_paragraphs(["a", "b"])
    sched.record_attempt(0, errors=3, hesitations=1)
    seg = sched.segments[0]
    assert seg.attempts == 1
    assert seg.total_errors == 3
    assert seg.total_hesitations == 1


def test_record_attempt_multiple():
    sched = Schedule.from_paragraphs(["x"])
    sched.record_attempt(0, 2, 0)
    sched.record_attempt(0, 0, 1)
    seg = sched.segments[0]
    assert seg.attempts == 2
    assert seg.total_errors == 2
    assert seg.total_hesitations == 1


def test_record_attempt_unknown_index():
    sched = Schedule.from_paragraphs(["x"])
    with pytest.raises(KeyError):
        sched.record_attempt(99, 1, 0)


# ── Schedule.next_cycle ───────────────────────────────────────────────────────

def test_next_cycle_returns_hard_segments():
    sched = _schedule(0.8, 0.1, 0.9)
    repeat = sched.next_cycle()
    indices = [s.segment_index for s in repeat]
    assert 0 in indices
    assert 2 in indices
    assert 1 not in indices


def test_next_cycle_sorted_by_difficulty_desc():
    sched = _schedule(0.6, 0.9, 0.7)
    repeat = sched.next_cycle()
    scores = [s.difficulty_score for s in repeat]
    assert scores == sorted(scores, reverse=True)


def test_next_cycle_empty_when_all_dominated():
    sched = _schedule(0.05, 0.1, 0.15)
    assert sched.next_cycle() == []


def test_next_cycle_unseen_included():
    sched = Schedule.from_paragraphs(["a"])
    assert sched.next_cycle()  # unseen → score 1.0 → repeat


# ── Schedule.dominated ────────────────────────────────────────────────────────

def test_dominated_default_threshold():
    sched = _schedule(0.1, 0.5, 0.9)
    dom = sched.dominated()
    assert len(dom) == 1
    assert dom[0].segment_index == 0


def test_dominated_custom_threshold():
    sched = _schedule(0.1, 0.4, 0.9)
    dom = sched.dominated(threshold=0.5)
    assert len(dom) == 2


def test_unseen_not_dominated():
    sched = Schedule.from_paragraphs(["x"])
    assert sched.dominated() == []


# ── Schedule.summary ─────────────────────────────────────────────────────────

def test_summary_keys():
    sched = _schedule(0.1, 0.8)
    s = sched.summary()
    assert "total_segments" in s
    assert "dominated" in s
    assert "pct_dominated" in s
    assert "mean_score" in s


def test_summary_pct():
    sched = _schedule(0.1, 0.1, 0.9)  # 2 dominated out of 3
    s = sched.summary()
    assert s["dominated"] == 2
    assert s["pct_dominated"] == pytest.approx(66.7, abs=0.1)


def test_summary_empty():
    sched = Schedule(segments=[])
    s = sched.summary()
    assert s["total_segments"] == 0
    assert s["pct_dominated"] == 0.0

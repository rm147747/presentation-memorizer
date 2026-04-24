"""Tests for differ.py"""
import pytest

from app.differ import HESITATION_THRESHOLD, DiffResult, compare


# ── Perfect match ─────────────────────────────────────────────────────────────

def test_identical_texts_no_errors():
    result = compare("hello world", "hello world")
    assert result.error_count == 0
    assert result.omitted == []
    assert result.substituted == []


def test_identical_all_ok_status():
    result = compare("one two three", "one two three")
    assert all(d.status == "ok" for d in result.word_diffs)


# ── Omissions ─────────────────────────────────────────────────────────────────

def test_single_omission():
    result = compare("hello beautiful world", "hello world")
    assert "beautiful" in result.omitted


def test_multiple_omissions():
    result = compare("one two three four five", "one five")
    assert len(result.omitted) >= 2
    assert "two" in result.omitted or "three" in result.omitted


def test_all_words_omitted():
    result = compare("alpha beta gamma", "")
    assert result.error_count == 3


# ── Substitutions ─────────────────────────────────────────────────────────────

def test_single_substitution():
    result = compare("the quick fox", "the slow fox")
    originals = [o for o, _ in result.substituted]
    assert "quick" in originals


def test_substitution_pairs_correct():
    result = compare("cats are great", "dogs are great")
    subs = dict(result.substituted)
    assert subs.get("cats") == "dogs"


# ── Error ratio ───────────────────────────────────────────────────────────────

def test_error_ratio_zero_on_perfect():
    result = compare("one two three", "one two three")
    assert result.error_ratio == pytest.approx(0.0)


def test_error_ratio_bounded():
    result = compare("one two three four", "completely different text here")
    assert 0.0 <= result.error_ratio <= 1.0


def test_error_ratio_empty_original():
    result = compare("", "")
    assert result.error_ratio == 0.0


# ── Hesitation detection ──────────────────────────────────────────────────────

def test_hesitation_detected_over_threshold():
    segments = [
        {"start": 0.0, "end": 1.0, "text": "hello"},
        {"start": 4.0, "end": 5.0, "text": "world"},  # 3 s gap → hesitation
    ]
    result = compare("hello world", "hello world", segments)
    assert len(result.hesitation_points) == 1
    assert result.hesitation_points[0] == pytest.approx(1.0)


def test_no_hesitation_below_threshold():
    segments = [
        {"start": 0.0, "end": 1.0, "text": "hello"},
        {"start": 2.5, "end": 3.0, "text": "world"},  # 1.5 s gap → ok
    ]
    result = compare("hello world", "hello world", segments)
    assert result.hesitation_points == []


def test_hesitation_exactly_at_threshold_not_counted():
    segments = [
        {"start": 0.0, "end": 1.0, "text": "a"},
        {"start": 3.0, "end": 4.0, "text": "b"},  # gap == HESITATION_THRESHOLD → not counted
    ]
    result = compare("a b", "a b", segments)
    assert result.hesitation_points == []


def test_multiple_hesitations():
    segments = [
        {"start": 0.0, "end": 1.0, "text": "a"},
        {"start": 5.0, "end": 6.0, "text": "b"},   # gap 4 s
        {"start": 6.5, "end": 7.0, "text": "c"},   # gap 0.5 s — ok
        {"start": 10.0, "end": 11.0, "text": "d"},  # gap 3 s
    ]
    result = compare("a b c d", "a b c d", segments)
    assert len(result.hesitation_points) == 2


def test_no_segments_no_hesitations():
    result = compare("hello world", "hello world", [])
    assert result.hesitation_points == []


def test_no_segments_param_omitted():
    result = compare("hello world", "hello world")
    assert result.hesitation_count == 0


def test_replace_with_leftover_originals_omitted():
    # replace opcode where original has more words than attempt →
    # covers the leftover-originals loop at differ.py line 106.
    # "world foo" → "replaced": zip covers ("world","replaced"), "foo" is leftover.
    result = compare("hello world foo bar", "hello replaced bar")
    omitted = result.omitted
    assert "foo" in omitted

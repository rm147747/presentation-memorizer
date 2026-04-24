"""Tests for aligner.py"""
import pytest

from app.aligner import AlignedWord, align, annotate_difficulty, _expand_segments


# ── Fixtures ──────────────────────────────────────────────────────────────────

def _seg(start, end, text, words=None):
    s = {"start": start, "end": end, "text": text}
    if words is not None:
        s["words"] = words
    return s


SIMPLE_SEGS = [
    _seg(0.0, 2.0, "hello world"),
    _seg(2.5, 5.0, "this is a test"),
]

ORIGINAL = "Hello world this is a test"


# ── align — perfect match ──────────────────────────────────────────────────────

def test_align_all_matched():
    result = align(ORIGINAL, SIMPLE_SEGS)
    assert all(aw.matched for aw in result)


def test_align_word_count():
    result = align(ORIGINAL, SIMPLE_SEGS)
    assert len(result) == 6


def test_align_timestamps_assigned():
    result = align(ORIGINAL, SIMPLE_SEGS)
    for aw in result:
        assert aw.start is not None
        assert aw.end is not None


def test_align_word_values():
    result = align(ORIGINAL, SIMPLE_SEGS)
    words = [aw.word for aw in result]
    assert words == ["hello", "world", "this", "is", "a", "test"]


# ── align — empty / no segments ───────────────────────────────────────────────

def test_align_no_segments():
    result = align(ORIGINAL, [])
    assert len(result) == 6
    assert all(not aw.matched for aw in result)
    assert all(aw.start is None for aw in result)


def test_align_empty_text():
    result = align("", SIMPLE_SEGS)
    assert result == []


# ── align — partial mismatch ──────────────────────────────────────────────────

def test_align_extra_word_in_transcript():
    # "hello beautiful world" in transcript but original only has "hello world"
    segs = [_seg(0.0, 3.0, "hello beautiful world")]
    result = align("hello world", segs)
    matched_words = {aw.word for aw in result if aw.matched}
    assert "hello" in matched_words
    assert "world" in matched_words


def test_align_missing_word_in_transcript():
    segs = [_seg(0.0, 1.0, "hello")]      # "world" missing
    result = align("hello world", segs)
    hello = next(aw for aw in result if aw.word == "hello")
    world = next(aw for aw in result if aw.word == "world")
    assert hello.matched
    assert not world.matched


# ── _expand_segments — proportional distribution ──────────────────────────────

def test_expand_single_segment_two_words():
    segs = [_seg(0.0, 4.0, "hello world")]
    words = _expand_segments(segs)
    assert len(words) == 2
    assert words[0]["word"] == "hello"
    assert words[0]["start"] == pytest.approx(0.0)
    assert words[0]["end"] == pytest.approx(2.0)
    assert words[1]["word"] == "world"
    assert words[1]["start"] == pytest.approx(2.0)
    assert words[1]["end"] == pytest.approx(4.0)


def test_expand_segment_with_word_level_data():
    segs = [_seg(0.0, 2.0, "hi there", words=[
        {"word": "Hi", "start": 0.0, "end": 0.8},
        {"word": "there", "start": 0.9, "end": 2.0},
    ])]
    words = _expand_segments(segs)
    assert len(words) == 2
    assert words[0]["start"] == pytest.approx(0.0)
    assert words[1]["end"] == pytest.approx(2.0)


def test_expand_empty_segment_text():
    segs = [_seg(0.0, 1.0, ""), _seg(1.0, 2.0, "ok")]
    words = _expand_segments(segs)
    assert len(words) == 1
    assert words[0]["word"] == "ok"


# ── annotate_difficulty ───────────────────────────────────────────────────────

def test_annotate_difficulty_keys():
    result = align(ORIGINAL, SIMPLE_SEGS)
    paragraphs = [ORIGINAL]
    scores = {0: 0.75}
    annotated = annotate_difficulty(result, scores, paragraphs)
    assert len(annotated) == 6
    assert annotated[0]["difficulty"] == pytest.approx(0.75)


def test_annotate_difficulty_missing_score_defaults_zero():
    result = align(ORIGINAL, SIMPLE_SEGS)
    annotated = annotate_difficulty(result, {}, [ORIGINAL])
    assert all(a["difficulty"] == 0.0 for a in annotated)


def test_annotate_difficulty_multiple_paragraphs():
    paras = ["Hello world", "this is a test"]
    segs = SIMPLE_SEGS
    result = align(ORIGINAL, segs)
    scores = {0: 0.1, 1: 0.9}
    annotated = annotate_difficulty(result, scores, paras)
    # "hello" and "world" → para 0 (score 0.1)
    # "this", "is", "a", "test" → para 1 (score 0.9)
    assert annotated[0]["difficulty"] == pytest.approx(0.1)
    assert annotated[2]["difficulty"] == pytest.approx(0.9)


def test_align_one_to_one_replace_maps_timestamps():
    # equal-length replace opcode → lines 57-58 in aligner.py
    # original "hello foo" → transcript "hello bar": "foo"→"bar" is replace(1,1)
    segs = [_seg(0.0, 2.0, "hello bar")]
    result = align("hello foo", segs)
    foo = next(aw for aw in result if aw.word == "foo")
    # The aligner maps the position even on a replace, so timestamps are present
    assert foo.start is not None
    assert foo.end is not None

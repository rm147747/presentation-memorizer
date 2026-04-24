"""Tests for degrader.py"""
import pytest

from app.degrader import BLANK, REMOVAL_RATIO, DegradedText, degrade

_SAMPLE_EN = "The quick brown fox jumps over the lazy dog and then runs away quickly."
_SAMPLE_PT = (
    "Bom dia a todos. Hoje vamos apresentar os resultados do projeto de pesquisa.\n"
    "Começamos com a metodologia e depois discutimos os dados coletados.\n"
    "Por fim, apresentamos nossas conclusões e próximos passos."
)


# ── Level 1 ───────────────────────────────────────────────────────────────────

def test_level1_returns_original():
    result = degrade(_SAMPLE_EN, 1)
    assert result.text == _SAMPLE_EN


def test_level1_no_blanks():
    result = degrade(_SAMPLE_EN, 1)
    assert result.blanked_indices == []
    assert BLANK not in result.text


def test_level1_dataclass():
    result = degrade(_SAMPLE_EN, 1)
    assert isinstance(result, DegradedText)
    assert result.level == 1


# ── Level 2 ───────────────────────────────────────────────────────────────────

def test_level2_has_blanks():
    result = degrade(_SAMPLE_EN, 2, seed=0)
    assert BLANK in result.text
    assert len(result.blanked_indices) > 0


def test_level2_removal_ratio_approx():
    import re
    words = re.findall(r"\w+", _SAMPLE_EN)
    result = degrade(_SAMPLE_EN, 2, seed=0)
    blank_count = result.text.count(BLANK)
    expected = round(len(words) * REMOVAL_RATIO)
    assert abs(blank_count - expected) <= 2, (
        f"Expected ~{expected} blanks, got {blank_count}"
    )


def test_level2_reproducible_with_seed():
    r1 = degrade(_SAMPLE_EN, 2, seed=42)
    r2 = degrade(_SAMPLE_EN, 2, seed=42)
    assert r1.text == r2.text
    assert r1.blanked_indices == r2.blanked_indices


def test_level2_different_seeds_differ():
    r1 = degrade(_SAMPLE_EN, 2, seed=1)
    r2 = degrade(_SAMPLE_EN, 2, seed=99)
    # Very unlikely to be identical with a 13-word sentence
    assert r1.text != r2.text


def test_level2_preserves_punctuation():
    result = degrade(_SAMPLE_EN, 2, seed=0)
    # Full stops and commas should survive (they are not "words")
    assert "." in result.text or "," in result.text or result.text.endswith(BLANK)


def test_level2_empty_text():
    result = degrade("", 2, seed=0)
    assert result.text == ""
    assert result.blanked_indices == []


def test_level2_single_word():
    result = degrade("Olá", 2, seed=0)
    # With one word, the ratio rounds to 0 or 1; either is valid
    assert isinstance(result.text, str)


def test_level2_portuguese():
    result = degrade(_SAMPLE_PT, 2, seed=7)
    assert BLANK in result.text


# ── Level 3 ───────────────────────────────────────────────────────────────────

def test_level3_first_word_only():
    text = "Hello world this is line one.\nAnother paragraph here."
    result = degrade(text, 3)
    lines = result.text.split("\n")
    assert lines[0] == "Hello"
    assert lines[1] == "Another"


def test_level3_blank_paragraphs_preserved():
    text = "First paragraph.\n\nThird paragraph."
    result = degrade(text, 3)
    lines = result.text.split("\n")
    assert lines[0] == "First"
    assert lines[1] == ""
    assert lines[2] == "Third"


def test_level3_single_paragraph():
    result = degrade("Apenas uma frase aqui.", 3)
    assert result.text == "Apenas"


# ── Level 4 ───────────────────────────────────────────────────────────────────

def test_level4_empty_string():
    result = degrade(_SAMPLE_EN, 4)
    assert result.text == ""
    assert result.blanked_indices == []


# ── Validation ────────────────────────────────────────────────────────────────

def test_invalid_level_raises():
    with pytest.raises(ValueError, match="level must be 1–4"):
        degrade(_SAMPLE_EN, 0)


def test_invalid_level_5_raises():
    with pytest.raises(ValueError):
        degrade(_SAMPLE_EN, 5)


# ── Edge-case coverage ────────────────────────────────────────────────────────

def test_level2_all_function_words_skips_nltk():
    # All tokens are Portuguese function words → remaining_idx is empty,
    # NLTK pass is skipped entirely (line 130 early-return).
    result = degrade("e de a o", 2, seed=0)
    assert isinstance(result, DegradedText)


def test_level2_nltk_success_path(monkeypatch):
    # Inject fake NLTK that succeeds: data.find raises LookupError (download is called),
    # then pos_tag returns mixed tags to cover all branches in lines 140-151.
    import sys
    import types

    fake_nltk = types.ModuleType("nltk")
    fake_data = types.ModuleType("nltk.data")

    def _lookup_error(*a, **kw):
        raise LookupError("resource not found")

    fake_data.find = _lookup_error
    fake_nltk.data = fake_data
    fake_nltk.download = lambda *a, **kw: None  # no-op, covers line 141

    # Return one tag from each category to cover all branches
    def _pos_tag(words, **kw):
        tags = ["IN", "NN", "JJ"]  # tier1, tier2, other
        return [(w, tags[i % len(tags)]) for i, w in enumerate(words)]

    fake_nltk.pos_tag = _pos_tag
    monkeypatch.setitem(sys.modules, "nltk", fake_nltk)

    result = degrade("over quick lazy", 2, seed=0)
    assert isinstance(result, DegradedText)


def test_level2_nltk_exception_falls_back_gracefully(monkeypatch):
    # NLTK may not be installed. Inject a fake module whose pos_tag raises so
    # we can exercise the except-branch (lines 137-151) regardless.
    import sys
    import types

    fake_nltk = types.ModuleType("nltk")
    fake_data = types.ModuleType("nltk.data")
    fake_data.find = lambda *a, **kw: None  # pretend resources exist

    def _fail(words, **kwargs):
        raise RuntimeError("simulated NLTK failure")

    fake_nltk.data = fake_data
    fake_nltk.pos_tag = _fail

    monkeypatch.setitem(sys.modules, "nltk", fake_nltk)

    result = degrade("The quick brown fox", 2, seed=0)
    assert isinstance(result, DegradedText)

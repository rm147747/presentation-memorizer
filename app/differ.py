"""
Textual comparison between original text and a user's attempt.

Detects:
  - omitted words
  - substituted words
  - order changes (via SequenceMatcher)
  - hesitation points: gaps > HESITATION_THRESHOLD seconds between Whisper segments
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from difflib import SequenceMatcher
from typing import Any

HESITATION_THRESHOLD = 2.0  # seconds


@dataclass
class WordDiff:
    original_word: str
    attempt_word: str | None  # None means omitted
    status: str               # "ok" | "omitted" | "substituted"
    original_index: int


@dataclass
class DiffResult:
    word_diffs: list[WordDiff]
    omitted: list[str]
    substituted: list[tuple[str, str]]  # (original, attempt)
    hesitation_points: list[float]      # timestamps (s) of pauses > threshold
    error_count: int
    hesitation_count: int

    @property
    def total_words(self) -> int:
        return len(self.word_diffs)

    @property
    def error_ratio(self) -> float:
        return self.error_count / self.total_words if self.total_words else 0.0


def compare(
    original: str,
    attempt: str,
    whisper_segments: list[dict[str, Any]] | None = None,
) -> DiffResult:
    """
    Compare original text with the user's transcribed attempt.

    Args:
        original:         reference presentation text
        attempt:          user's transcribed attempt
        whisper_segments: Whisper segment list; each dict must have 'start' and 'end'
    """
    orig_words = _normalise(original)
    attempt_words = _normalise(attempt)

    diffs = _align(orig_words, attempt_words)
    omitted = [d.original_word for d in diffs if d.status == "omitted"]
    substituted = [
        (d.original_word, d.attempt_word)
        for d in diffs
        if d.status == "substituted"
    ]
    hesitations = _detect_hesitations(whisper_segments or [])

    return DiffResult(
        word_diffs=diffs,
        omitted=omitted,
        substituted=substituted,
        hesitation_points=hesitations,
        error_count=len(omitted) + len(substituted),
        hesitation_count=len(hesitations),
    )


# ── internals ─────────────────────────────────────────────────────────────────

def _normalise(text: str) -> list[str]:
    return re.findall(r"\b\w+\b", text.lower())


def _align(original: list[str], attempt: list[str]) -> list[WordDiff]:
    matcher = SequenceMatcher(None, original, attempt, autojunk=False)
    diffs: list[WordDiff] = []

    for tag, i1, i2, j1, j2 in matcher.get_opcodes():
        if tag == "equal":
            for k, word in enumerate(original[i1:i2]):
                diffs.append(WordDiff(word, word, "ok", i1 + k))

        elif tag == "delete":
            for k, word in enumerate(original[i1:i2]):
                diffs.append(WordDiff(word, None, "omitted", i1 + k))

        elif tag == "replace":
            pairs = list(zip(original[i1:i2], attempt[j1:j2]))
            for k, (orig, att) in enumerate(pairs):
                diffs.append(WordDiff(orig, att, "ok" if orig == att else "substituted", i1 + k))
            # any leftover originals not covered by the zip are omitted
            for k, word in enumerate(original[i1 + len(pairs) : i2]):
                diffs.append(WordDiff(word, None, "omitted", i1 + len(pairs) + k))

        # "insert": extra words in attempt — not penalised as original errors

    return diffs


def _detect_hesitations(segments: list[dict[str, Any]]) -> list[float]:
    """Return the end-timestamp of any segment followed by a gap > threshold."""
    hesitations: list[float] = []
    for prev, curr in zip(segments, segments[1:]):
        if curr["start"] - prev["end"] > HESITATION_THRESHOLD:
            hesitations.append(prev["end"])
    return hesitations

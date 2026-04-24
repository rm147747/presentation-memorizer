"""
Word-level alignment between the original presentation text and a Whisper transcription.

Whisper returns segment timestamps (start/end per segment, or per word with the
large-v2/v3 models). This module distributes timestamps within each segment
proportionally across words, then aligns them against the original text using
SequenceMatcher so every original word gets a timestamp (or None if unmatched).

This powers:
  - Time-indexed heat maps (which part of the recording is error-prone)
  - Hesitation detection at word level
  - Per-word difficulty overlay in the UI
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from difflib import SequenceMatcher
from typing import Any


@dataclass
class AlignedWord:
    word: str
    original_index: int
    start: float | None   # seconds into the recording; None = not found in transcript
    end: float | None
    matched: bool


def align(
    original_text: str,
    whisper_segments: list[dict[str, Any]],
) -> list[AlignedWord]:
    """
    Align original text words with Whisper segment timestamps.

    Returns one AlignedWord per original word; unmatched words get
    start=end=None, matched=False.
    """
    orig_words = _normalise(original_text)
    tx_words = _expand_segments(whisper_segments)

    if not tx_words:
        return [AlignedWord(w, i, None, None, False) for i, w in enumerate(orig_words)]

    tx_tokens = [t["word"] for t in tx_words]
    matcher = SequenceMatcher(None, orig_words, tx_tokens, autojunk=False)

    # orig_idx → tx_idx for equal and 1-to-1 replace blocks
    index_map: dict[int, int] = {}
    for tag, i1, i2, j1, j2 in matcher.get_opcodes():
        if tag == "equal":
            for k in range(i2 - i1):
                index_map[i1 + k] = j1 + k
        elif tag == "replace" and (i2 - i1) == (j2 - j1):
            for k in range(i2 - i1):
                index_map[i1 + k] = j1 + k

    result: list[AlignedWord] = []
    for i, word in enumerate(orig_words):
        tx_i = index_map.get(i)
        if tx_i is not None:
            tw = tx_words[tx_i]
            result.append(AlignedWord(word, i, tw["start"], tw["end"], True))
        else:
            result.append(AlignedWord(word, i, None, None, False))
    return result


def annotate_difficulty(
    aligned: list[AlignedWord],
    paragraph_scores: dict[int, float],
    paragraphs: list[str],
) -> list[dict[str, Any]]:
    """
    Attach a difficulty score to every aligned word based on which paragraph it
    belongs to. Used to build a time-indexed heat-map overlay.
    """
    word_to_para = _build_word_para_map(paragraphs)
    return [
        {
            "word": aw.word,
            "original_index": aw.original_index,
            "start": aw.start,
            "end": aw.end,
            "matched": aw.matched,
            "difficulty": paragraph_scores.get(word_to_para.get(aw.original_index, -1), 0.0),
        }
        for aw in aligned
    ]


# ── helpers ───────────────────────────────────────────────────────────────────

def _normalise(text: str) -> list[str]:
    return re.findall(r"\b\w+\b", text.lower())


def _expand_segments(segments: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """
    Produce a flat list of {word, start, end} from Whisper segments.

    If the segment already carries word-level data (large-v2/v3 model), use it.
    Otherwise distribute the segment duration proportionally across its words.
    """
    out: list[dict] = []
    for seg in segments:
        if "words" in seg and seg["words"]:
            for w in seg["words"]:
                out.append({
                    "word": w["word"].strip().lower(),
                    "start": w["start"],
                    "end": w["end"],
                })
        else:
            words = _normalise(seg.get("text", ""))
            if not words:
                continue
            step = (seg["end"] - seg["start"]) / len(words)
            for k, word in enumerate(words):
                out.append({
                    "word": word,
                    "start": seg["start"] + k * step,
                    "end": seg["start"] + (k + 1) * step,
                })
    return out


def _build_word_para_map(paragraphs: list[str]) -> dict[int, int]:
    """Map global word index → paragraph index."""
    result: dict[int, int] = {}
    idx = 0
    for para_i, para in enumerate(paragraphs):
        for _ in _normalise(para):
            result[idx] = para_i
            idx += 1
    return result

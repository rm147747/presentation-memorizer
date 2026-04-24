"""
Progressive text degradation for active-recall memorization training.

Level 1: full text visible — no changes
Level 2: ~30 % of words replaced with blanks; function words first
         (connectives, adverbs, determiners), then content words (nouns, verbs)
Level 3: only the first word of each paragraph
Level 4: blank screen — empty string

Supports both Portuguese and English via a two-pass strategy:
  Pass 1 — match against a hardcoded Portuguese function-word list (fast, no model needed)
  Pass 2 — NLTK POS tagger for remaining words (works well for English; used as
            a best-effort fallback for Portuguese)
"""
from __future__ import annotations

import random
import re
from dataclasses import dataclass, field
from typing import Literal

# ── Portuguese function words (conectivos, preposições, advérbios, determinantes) ──
_PT_FUNCTION_WORDS: frozenset[str] = frozenset(
    """
    e ou mas porém contudo todavia entretanto portanto logo então assim
    porque pois quando se que como também ainda já só apenas muito mais
    bem nunca sempre antes depois agora aqui ali lá onde quanto assim
    de do da dos das em no na nos nas por pelo pela pelos pelas para
    com sem sobre entre até após ante perante sob trás a o os as um
    uma uns umas ao à aos às este esta estes estas esse essa esses essas
    aquele aquela aqueles aquelas este isso aquilo meu minha meus minhas
    teu tua teus tuas seu sua seus suas nosso nossa nossos nossas
    vosso vossa vossos vossas me te se lhe nos vos lhes
    """.split()
)

# NLTK POS tags that represent function words (tier 1) and content words (tier 2)
_TIER1_POS = {"CC", "IN", "RB", "RBR", "RBS", "DT", "RP", "WRB", "TO", "UH"}
_TIER2_POS = {"NN", "NNS", "NNP", "NNPS", "VB", "VBD", "VBG", "VBN", "VBP", "VBZ"}

BLANK = "_____"
REMOVAL_RATIO = 0.30


@dataclass
class DegradedText:
    text: str
    level: int
    blanked_indices: list[int] = field(default_factory=list)


def degrade(
    text: str,
    level: Literal[1, 2, 3, 4],
    seed: int | None = None,
) -> DegradedText:
    """
    Return text degraded to the requested memorization level.

    Args:
        text:  original presentation text
        level: 1 (full) → 2 (gaps) → 3 (first-word prompts) → 4 (blank)
        seed:  optional RNG seed for reproducible blanking at level 2
    """
    if level not in (1, 2, 3, 4):
        raise ValueError(f"level must be 1–4, got {level!r}")
    if level == 1:
        return DegradedText(text=text, level=1)
    if level == 2:
        return _apply_level2(text, seed)
    if level == 3:
        return _apply_level3(text)
    return DegradedText(text="", level=4)


# ── internal ──────────────────────────────────────────────────────────────────

def _apply_level2(text: str, seed: int | None) -> DegradedText:
    """Replace REMOVAL_RATIO of words with BLANK; function words removed first."""
    rng = random.Random(seed)
    tokens = _tokenize(text)
    word_positions = [i for i, t in enumerate(tokens) if t["is_word"]]

    if not word_positions:
        return DegradedText(text=text, level=2)

    words = [tokens[i]["raw"].lower() for i in word_positions]
    target = max(1, round(len(word_positions) * REMOVAL_RATIO))

    tier1, tier2, other = _classify_words(words, word_positions)

    chosen: list[int] = []
    for pool in (tier1, tier2, other):
        if len(chosen) >= target:
            break
        need = target - len(chosen)
        chosen.extend(rng.sample(pool, min(need, len(pool))))

    blanked = set(chosen)
    rebuilt = [BLANK if i in blanked else tokens[i]["raw"] for i in range(len(tokens))]
    return DegradedText(
        text="".join(rebuilt),
        level=2,
        blanked_indices=sorted(blanked),
    )


def _classify_words(
    words: list[str],
    positions: list[int],
) -> tuple[list[int], list[int], list[int]]:
    """
    Split word positions into three priority tiers for blanking.

    Tier 1 — function words (Portuguese list + NLTK CC/IN/RB/DT…)
    Tier 2 — content words (NLTK NN/VB…)
    Tier 3 — everything else (JJ, PRP, …)
    """
    tier1: list[int] = []
    tier2: list[int] = []
    other: list[int] = []

    # Portuguese pass — no model needed
    pt_tier1 = [positions[k] for k, w in enumerate(words) if w in _PT_FUNCTION_WORDS]
    remaining_idx = [k for k, w in enumerate(words) if w not in _PT_FUNCTION_WORDS]

    tier1.extend(pt_tier1)

    if not remaining_idx:
        return tier1, tier2, other

    # NLTK pass for words not caught by the Portuguese list
    remaining_words = [words[k] for k in remaining_idx]
    try:
        import nltk

        for resource in ("averaged_perceptron_tagger_eng", "punkt_tab"):
            try:
                nltk.data.find(f"taggers/{resource}")
            except LookupError:
                nltk.download(resource, quiet=True)

        tagged = nltk.pos_tag(remaining_words)
        for local_k, (_, tag) in enumerate(tagged):
            global_pos = positions[remaining_idx[local_k]]
            if tag in _TIER1_POS:
                tier1.append(global_pos)
            elif tag in _TIER2_POS:
                tier2.append(global_pos)
            else:
                other.append(global_pos)
    except Exception:
        # If NLTK unavailable, put everything in tier2
        for k in remaining_idx:
            tier2.append(positions[k])

    return tier1, tier2, other


def _apply_level3(text: str) -> DegradedText:
    """Reduce each paragraph to its first word."""
    prompts: list[str] = []
    for para in text.split("\n"):
        stripped = para.strip()
        if not stripped:
            prompts.append("")
            continue
        m = re.search(r"\S+", stripped)
        prompts.append(m.group() if m else "")
    return DegradedText(text="\n".join(prompts), level=3)


def _tokenize(text: str) -> list[dict]:
    """
    Split text into alternating word / non-word tokens.
    Joining all raw values with '' reproduces the original string exactly.
    """
    return [
        {"raw": m.group(), "is_word": bool(re.fullmatch(r"\w+", m.group()))}
        for m in re.finditer(r"(\w+|\W+)", text)
    ]

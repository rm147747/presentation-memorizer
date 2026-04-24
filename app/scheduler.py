"""
Spaced-repetition scheduler for presentation segments.

difficulty_score = (errors + hesitations) / attempts
Segments with score > REPEAT_THRESHOLD are flagged for the next training cycle.
Unseen segments (attempts == 0) receive score 1.0 — maximum priority.
"""
from __future__ import annotations

from dataclasses import dataclass, field

REPEAT_THRESHOLD = 0.5


@dataclass
class SegmentStats:
    segment_index: int
    text: str
    attempts: int = 0
    total_errors: int = 0
    total_hesitations: int = 0

    @property
    def difficulty_score(self) -> float:
        if self.attempts == 0:
            return 1.0
        return (self.total_errors + self.total_hesitations) / self.attempts

    @property
    def needs_repeat(self) -> bool:
        return self.difficulty_score > REPEAT_THRESHOLD


@dataclass
class Schedule:
    segments: list[SegmentStats] = field(default_factory=list)

    @classmethod
    def from_paragraphs(cls, paragraphs: list[str]) -> "Schedule":
        return cls(
            segments=[
                SegmentStats(segment_index=i, text=p)
                for i, p in enumerate(paragraphs)
            ]
        )

    def record_attempt(self, segment_index: int, errors: int, hesitations: int) -> None:
        seg = self._get(segment_index)
        seg.attempts += 1
        seg.total_errors += errors
        seg.total_hesitations += hesitations

    def next_cycle(self) -> list[SegmentStats]:
        """Segments that should repeat in the next training cycle, sorted by difficulty."""
        return sorted(
            (s for s in self.segments if s.needs_repeat),
            key=lambda s: s.difficulty_score,
            reverse=True,
        )

    def dominated(self, threshold: float = 0.2) -> list[SegmentStats]:
        """Segments considered mastered (score ≤ threshold)."""
        return [s for s in self.segments if s.attempts > 0 and s.difficulty_score <= threshold]

    def summary(self) -> dict:
        total = len(self.segments)
        dom = len(self.dominated())
        return {
            "total_segments": total,
            "dominated": dom,
            "pct_dominated": round(dom / total * 100, 1) if total else 0.0,
            "mean_score": (
                round(sum(s.difficulty_score for s in self.segments) / total, 3)
                if total else 0.0
            ),
        }

    def _get(self, index: int) -> SegmentStats:
        for s in self.segments:
            if s.segment_index == index:
                return s
        raise KeyError(f"segment_index {index} not found")

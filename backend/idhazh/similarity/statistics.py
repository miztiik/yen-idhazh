"""What do completed pairs say about valid agreement, refusal and uncertainty?"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from typing import Protocol

from idhazh.contracts.content_similarity_judge_metrics import ContentSimilarityJudgeMetrics
from idhazh.contracts.story_similarity_pair_verdict import SameStoryVerdict


class PairReadings(Protocol):
    """The evidence shared by an in-memory pair and its retained row."""

    @property
    def verdict(self) -> SameStoryVerdict | None: ...

    @property
    def verdict_swapped(self) -> SameStoryVerdict | None: ...

    @property
    def grammar_applied(self) -> bool | None: ...


@dataclass(frozen=True, slots=True)
class PairStatistics:
    """Counts first; rates are derived only after completed pairs are combined."""

    attempted: int
    valid: int
    agreed: int
    unclear: int

    @property
    def refused(self) -> int:
        return self.attempted - self.valid

    @property
    def disagreement_rate(self) -> float | None:
        return (self.valid - self.agreed) / self.valid if self.valid else None

    @property
    def unclear_rate(self) -> float | None:
        return self.unclear / self.agreed if self.agreed else None


def reading_statistics(pairs: Iterable[PairReadings]) -> PairStatistics:
    """Count both orders symmetrically after the caller selects its instrument."""
    attempted = valid = agreed = unclear = 0
    for pair in pairs:
        attempted += 1
        if (
            pair.grammar_applied is False
            or pair.verdict is None
            or pair.verdict_swapped is None
        ):
            continue
        valid += 1
        if pair.verdict == pair.verdict_swapped:
            agreed += 1
            unclear += pair.verdict is SameStoryVerdict.UNCLEAR
    return PairStatistics(attempted, valid, agreed, unclear)


def combined_statistics(parts: Iterable[PairStatistics]) -> PairStatistics:
    """The statistics of every part's pairs counted as one lot, rates derived afterwards.

    A runner that read ten pairs weighs ten in the night's rate and a runner that read two
    hundred weighs two hundred, which is what averaging the runners' own rates would not do.
    """
    attempted = valid = agreed = unclear = 0
    for part in parts:
        attempted += part.attempted
        valid += part.valid
        agreed += part.agreed
        unclear += part.unclear
    return PairStatistics(attempted, valid, agreed, unclear)


def shipped_statistics(reading: ContentSimilarityJudgeMetrics) -> PairStatistics:
    """What one runner's shipped reading counted, with its UNCLEAR count recovered.

    The reading holds `unclear_rate` and not the count behind it. The runner made the rate
    from two whole numbers, so the rate times the agreed pairs, rounded, is the count back
    exactly. The completed pairs are the valid ones and the refused ones: a pair the window
    no longer reached, or one the runner never got to, is not a completed pair.
    """
    unclear = round((reading.unclear_rate or 0.0) * reading.pairs_agreed)
    return PairStatistics(
        attempted=reading.pairs_read + reading.pairs_refused,
        valid=reading.pairs_read,
        agreed=reading.pairs_agreed,
        unclear=unclear,
    )

"""What do completed pairs say about valid agreement, refusal and uncertainty?"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from typing import Protocol

from idhazh.contracts.story_similarity_pair import SameStoryVerdict


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

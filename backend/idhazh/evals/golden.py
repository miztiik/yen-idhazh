"""Score the golden set with whichever model is currently served.

This is the measurement Row #7's decision rule judges. It runs the real path -
fetch, extract, summarize, score - because the question is not "how good is this
model" but "how good is this model through our prompt, our extraction and our
corpus". Three variables sit between a leaderboard number and that one.
"""

from __future__ import annotations

import json
import statistics
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True, slots=True)
class GoldenResult:
    """One model's run over the set. Written per model, read by the decider."""

    model_id: str
    leaderboard_hhem: float
    scores: list[float]
    attempted: int

    @property
    def measured_hhem(self) -> float:
        return statistics.fmean(self.scores) if self.scores else 0.0

    @property
    def articles(self) -> int:
        """Scored, not attempted. An article that would not fetch measured nothing."""
        return len(self.scores)

    def to_json(self) -> str:
        return (
            json.dumps(
                {
                    "model_id": self.model_id,
                    "leaderboard_hhem": self.leaderboard_hhem,
                    "scores": self.scores,
                    "attempted": self.attempted,
                    "measured_hhem": self.measured_hhem,
                    "articles": self.articles,
                },
                indent=2,
                sort_keys=True,
            )
            + "\n"
        )

    @classmethod
    def from_json(cls, text: str) -> GoldenResult:
        payload = json.loads(text)
        return cls(
            model_id=payload["model_id"],
            leaderboard_hhem=payload["leaderboard_hhem"],
            scores=payload["scores"],
            attempted=payload["attempted"],
        )


def results_in(directory: Path) -> list[GoldenResult]:
    """Every per-model result written so far, in a stable order."""
    return [
        GoldenResult.from_json(path.read_text(encoding="utf-8"))
        for path in sorted(directory.glob("*.json"))
    ]


def ledger_relpath(date: str) -> str:
    """`state/validation-<date>.csv` - POSIX and dated, per the row's own spec."""
    return f"state/validation-{date}.csv"

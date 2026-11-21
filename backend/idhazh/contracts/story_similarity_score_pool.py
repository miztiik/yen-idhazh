"""What score histogram can preparation hand to settlement for one exact attempt?"""

from typing import ClassVar

from pydantic import Field

from idhazh.contracts.base import ChangelogEntry, Contract, RunId
from idhazh.contracts.story_similarity_diagnostics import DiagnosticDate, ScorePoolHistogram


class ContentSimilarityScorePool(Contract):
    """One histogram and its invocation, carried in the existing preparation receipt."""

    __schema_stem__: ClassVar[str] = "story-similarity-score-pool"
    __changelog__: ClassVar[tuple[ChangelogEntry, ...]] = (
        ChangelogEntry(
            version="2026-11-21",
            change="Declare the score pool histogram and the invocation it belongs to.",
            why="Settlement can read the pool without rescoring or confusing attempts.",
        ),
    )

    date: DiagnosticDate = Field(description="The UTC digest date of the scored pairs.")
    run_id: RunId
    attempt: int = Field(strict=True, ge=1)
    histogram: ScorePoolHistogram

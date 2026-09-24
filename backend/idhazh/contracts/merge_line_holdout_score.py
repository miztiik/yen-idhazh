"""How does the merge line the pipeline applies stand against a marked holdout?

One row per scoring run: the line that was in force, the four cells of the
comparison, and what the line was made of when the cells were counted.

**It scores the LINE, not the judge.** The holdout rows carry no verdict, the
shipped implementation calls no model, and the labels were written outside this
pipeline. So this row inherits no call stamp: eight call columns here would be
five empty cells and one asserting an instrument that never ran.

**Counts only, and no precision, recall or accuracy column.** A stored rate is a
rate somebody reads without its denominator, and this denominator is small
enough that one flip moves the answer by tens of points. `labelled_two_story_pairs`
is on the row so that every rate a reader derives is derived with the population
it came from in view (Guardrail #10).

**The two directions of a mistake are not the same mistake.** A line that leaves
one story in two pieces shows the reader the same story twice, and a reader can
dismiss the second. A line that joins two stories hides one of them, and the
reader never learns it existed. Both get their own cell, because a single error
count would add them together.

**The read behind this row is bounded by the holdout and not by the archive**
(Guardrail #12). Each holdout row names its own two days, so the hand-marked
file is the bound on what has to be opened.

The store is
`state/content-similarity-judge/merge-line-holdout-scores/<YYYY>/<MM>/<DD>.csv`.
The directory name is spelled in `idhazh.ledger`, which is where a path belongs
and which this module may not import (CLAUDE.md section 4).
"""

from __future__ import annotations

from typing import Annotated, Any, ClassVar, Final, Self

from pydantic import Field, StringConstraints, model_validator

from idhazh.contracts.base import (
    PRINTABLE_LINE_PATTERN,
    ChangelogEntry,
    Contract,
    DateStamp,
    RunId,
    without_retired_keys,
)
from idhazh.contracts.story_similarity_pair import ScorerModelId

#: Who marked the holdout, as one printable line. Free text rather than a model
#: id on purpose: the committed labels name a model from outside this
#: repository's registry, and a column that could hold only pipeline models would
#: have to refuse the truth. A line, because a newline splits the row for any
#: reader that takes a day file a line at a time.
Labeller = Annotated[str, StringConstraints(pattern=PRINTABLE_LINE_PATTERN, max_length=64)]

#: Headings a committed day file still carries that this row no longer names and
#: that nothing replaced. `key_point_weight` went with the key points
#: themselves: the term shipped at a weight of 0.0, so it never moved a line.
#: `from_csv_row` hands this model every cell the file carries, so without this
#: set `extra="forbid"` would refuse the whole committed day.
DROPPED_CELLS: Final[frozenset[str]] = frozenset({"key_point_weight"})


class MergeLineHoldoutScore(Contract):
    """One run's reading of the applied merge line against the hand-marked holdout."""

    __schema_stem__: ClassVar[str] = "content-similarity-judge-merge-line-holdout-score"
    __changelog__: ClassVar[tuple[ChangelogEntry, ...]] = (
        ChangelogEntry(
            version="2026-09-24",
            change="key_point_weight is gone. Its heading is carried and dropped on read.",
            why="The term shipped at a weight of zero and never moved a score.",
        ),
        ChangelogEntry(
            version="2026-09-21",
            change="Initial shape: the line in force, its four cells, and what it was made of.",
            why="Nothing recorded how the line the pipeline applies stands against the labels.",
        ),
    )

    date: DateStamp = Field(description="The day the line was scored.")
    run_id: RunId = Field(description="The run that scored it.")
    applied_line: float = Field(
        ge=0,
        le=1,
        description=(
            "The merge line in force when these cells were counted. On the row because "
            "two rows counted under two lines answer two different questions."
        ),
    )
    labeller: Labeller = Field(
        description=(
            "Who marked the holdout. Free text rather than a model this repository "
            "ships, because the committed labels name a model from outside the registry "
            "and a narrower column would have to refuse the truth."
        )
    )
    merged_and_one_story: int = Field(
        ge=0, description="The line joined the pair and the label agrees it is one story."
    )
    merged_and_two_stories: int = Field(
        ge=0,
        description=(
            "The line joined two stories that the label says are not one. The invisible "
            "direction: the reader never learns the second story existed."
        ),
    )
    apart_and_one_story: int = Field(
        ge=0,
        description=(
            "The line left one story in two pieces. The reader sees it twice and can "
            "dismiss the second, which is why this is the cheaper of the two mistakes."
        ),
    )
    apart_and_two_stories: int = Field(
        ge=0, description="The line left the pair apart and the label agrees they are two."
    )
    pairs_unresolved: int = Field(
        ge=0,
        description=(
            "Labelled pairs neither cell could be counted for, because retention has "
            "deleted one of the two days they name. Reported rather than dropped, so a "
            "shrinking comparison is visible instead of silent."
        ),
    )
    labelled_two_story_pairs: int = Field(
        ge=0,
        description=(
            "How many labelled pairs are marked two stories - the population the "
            "false-merge cell is drawn from. On the row so that no rate is ever read "
            "without the denominator it came from."
        ),
    )
    scorer_model: ScorerModelId = Field(
        description="Which encoder produced the cosines these cells were counted under."
    )
    cosine_weight: float = Field(
        ge=0,
        le=1,
        description=(
            "What the cosine was worth in the score the line was applied to. On the row "
            "because a later reader comparing two runs has to know both were asked the "
            "same question."
        ),
    )

    @model_validator(mode="before")
    @classmethod
    def _without_the_columns_this_row_stopped_naming(cls, data: Any) -> Any:
        """The read-side migration `CLAUDE.md` section 11 owes a removed column.

        `from_csv_row` hands this model every cell the file carries, so a heading
        the row stopped naming would be refused by `extra="forbid"` and take the
        whole committed day with it.
        """
        return without_retired_keys(data, *DROPPED_CELLS)

    @model_validator(mode="after")
    def _the_negative_cells_fit_their_population(self) -> Self:
        """Two cells are drawn from the labelled negatives, and cannot outnumber them.

        A pair the label calls two stories is counted in exactly one of them, or
        in neither when its days have aged out - so the two added together are at
        or below the population, and a row where they are not is a row whose
        false-merge rate would read above one.
        """
        scored = self.merged_and_two_stories + self.apart_and_two_stories
        if scored > self.labelled_two_story_pairs:
            raise ValueError(
                f"{scored} pairs are counted against {self.labelled_two_story_pairs} labelled "
                "two-story pairs. The merged and apart cells are both drawn from that "
                "population, so together they cannot exceed it."
            )
        return self

    @classmethod
    def csv_columns(cls) -> tuple[str, ...]:
        """One definition, so a writer and a reader cannot disagree about the shape."""
        return tuple(cls.model_fields)

    def csv_row(self) -> dict[str, str]:
        """Every cell a string. Nothing here is optional, so nothing here is empty."""
        payload = self.model_dump(mode="json")
        return {name: str(payload[name]) for name in payload}

    @classmethod
    def from_csv_row(cls, row: dict[str, str]) -> Self:
        """The inverse. Every column is required, so a missing cell fails by name."""
        payload: dict[str, Any] = dict(row)
        return cls.model_validate(payload)

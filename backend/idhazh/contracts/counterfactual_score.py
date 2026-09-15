"""What a run's ranker would have done if one lens had been weighted differently.

`state/counterfactual-scores/YYYY/MM/DD.csv`. One row per candidate a run
scored, written by the plan stage after the day's items are settled. The row
records two numbers for one story: the score it got at the lens weights in
`config/taxonomy.json`, and the score it would have got at a candidate weight.
It changes nothing. The run takes what the committed weights told it to take,
and this file is the note it leaves behind about the question it did not act on.

**The refused candidates are the reason the file exists.** A story a run
published leaves a payload, a summary and a published row, so its score can be
looked up afterwards for as long as the day is kept. A story the run scored and
did not take leaves nothing at all - the candidate list is rebuilt from the
feeds on every run, and yesterday's feeds no longer carry yesterday's stories.
So the question "would a heavier lens weight have bought a different day" can
only ever be answered from data written at the time the day was planned. After
the fact there is nothing left to compute it from, and a counterfactual built
from the published half alone can only ever delete an item from a day, never
displace one into it - which is the half of a weight change that matters.

**Both scores come from one call each over the same candidates.** `rank.score`
is called twice with two lens weights rather than once with arithmetic applied
after, so there is one scoring path and the two answers cannot drift apart. The
lens term is added flatly today and a subtraction would agree with the second
call exactly - but that is a fact about this month's arithmetic, not a promise,
and a subtraction would keep returning a number after it stopped being true.

**The pool is bounded, and the bound is in config rather than here.** Every
candidate a run scores would be several thousand rows a day, and this collection
is appended to forever, so it is capped at the items the run took plus the
highest-scoring refused candidates on each desk
(`collect.lens_weights.counterfactual_refused_per_desk`). A refused candidate
far down its desk would not have crossed the cut under any weight this probe
asks about, so its row is bytes with no question in them. What is kept is
bounded per run rather than per day or per archive, so the cost of a run does
not rise as the archive grows (CLAUDE.md Guardrail #12), and a trailing window
is all any reader opens.
"""

from __future__ import annotations

from typing import Any, ClassVar, Self

from pydantic import Field, model_validator

from idhazh.contracts.base import (
    ChangelogEntry,
    Contract,
    DateStamp,
    RunId,
)

#: What two scores rounded to six decimal places may disagree by before the
#: disagreement is arithmetic rather than rounding. `rank.score` rounds its
#: total, so each of the two scores carries up to 5e-7 of rounding and the
#: difference of the lens terms carries another - 1.5e-6 in the worst case, and
#: this is that with room to spare. Any wider and the check stops catching a row
#: whose multiplier and whose scores came from different runs.
SCORE_TOLERANCE = 2e-6


class CounterfactualScoreRow(Contract):
    """One candidate, scored twice."""

    __schema_stem__: ClassVar[str] = "counterfactual-score-row"
    __changelog__: ClassVar[tuple[ChangelogEntry, ...]] = (
        ChangelogEntry(
            version="2026-09-14T11:00",
            change="Initial shape: the desk, the address, whether the run took it, the lens.",
            why="A lens weight was a number somebody picked and no committed file priced it.",
        ),
    )

    date: DateStamp = Field(description="The digest date the run was planning.")
    run_id: RunId = Field(description="The run that scored it.")
    vertical: str = Field(
        min_length=1,
        description=(
            "The desk the candidate was scored on. Desks are planned separately, so a "
            "score is only ever comparable with another score from the same desk."
        ),
    )
    url_key: str = Field(
        min_length=1,
        description=(
            "The candidate's address key, which is what makes two rows about one story "
            "recognisable across runs. Not an item id: a refused candidate never gets "
            "one."
        ),
    )
    taken: bool = Field(
        description=(
            "Whether this candidate was in the run's plan after every later pass - the "
            "day-wide duplicate fold and the run's own safety ceiling included. False "
            "is the interesting value and the one nothing else records."
        )
    )
    lens_id: str = Field(
        default="",
        description=(
            "The lens whose weight this row's counterfactual moves, empty when the "
            "headline matched none. One story takes the largest weight it earned and "
            "never the sum, so this names one lens and never a list."
        ),
    )
    lens_bonus: float = Field(
        ge=0.0,
        description=(
            "What `lens_id` was worth in the run, read from the committed taxonomy. "
            "0.0 when no lens matched, and then both scores are the same number."
        ),
    )
    lens_multiplier: float = Field(
        gt=0.0,
        description=(
            "What the counterfactual multiplied the committed lens weight by. On the "
            "row rather than in a config file a reader would have to go and find, so a "
            "window of rows spanning a config change is still readable."
        ),
    )
    score_committed: float = Field(
        description=(
            "What `rank.score` returned at the committed weights. This is the score "
            "that decided the day."
        )
    )
    score_counterfactual: float = Field(
        description=(
            "What `rank.score` returned at the candidate weight, over the same "
            "candidates in the same call shape. It decided nothing."
        )
    )

    @model_validator(mode="after")
    def _the_two_scores_differ_by_the_lens_and_nothing_else(self) -> Self:
        """Two rules, and both catch a row that would poison a window.

        A bonus with no lens named is a bonus nobody can attribute, so a later
        reader counting per-lens effects would silently drop it into whichever
        bucket it happened to sort into.

        The second rule is the load-bearing one. Every term of the score except
        the lens is identical between the two calls, so their difference is the
        lens term's difference exactly. A row where it is not is a row whose
        multiplier and whose scores came from different places - a config read
        after the scoring rather than before it, or two collections joined by
        address after the fact. Both produce a number that looks like an answer.
        """
        if self.lens_bonus and not self.lens_id:
            raise ValueError("a lens bonus with no lens named cannot be attributed to anything")
        if self.lens_id and not self.lens_bonus:
            raise ValueError("a lens worth nothing is not a lens this row can have matched")
        expected = self.lens_bonus * self.lens_multiplier - self.lens_bonus
        if abs(self.score_counterfactual - self.score_committed - expected) > SCORE_TOLERANCE:
            raise ValueError(
                "the two scores must differ by the lens term and by nothing else: "
                f"{self.score_counterfactual} - {self.score_committed} is not {expected}"
            )
        return self

    @classmethod
    def csv_columns(cls) -> tuple[str, ...]:
        """One definition, so a writer and a reader cannot disagree about the shape."""
        return tuple(cls.model_fields)

    def csv_row(self) -> dict[str, str]:
        """Every cell a string. An absent optional is an empty cell."""
        payload = self.model_dump(mode="json")
        return {name: "" if payload[name] is None else str(payload[name]) for name in payload}

    @classmethod
    def from_csv_row(cls, row: dict[str, str]) -> Self:
        """The inverse. `taken` is read back from the text `bool` writes."""
        payload: dict[str, Any] = {name: row.get(name, "") for name in cls.model_fields}
        payload["taken"] = payload["taken"] == "True"
        return cls.model_validate(payload)

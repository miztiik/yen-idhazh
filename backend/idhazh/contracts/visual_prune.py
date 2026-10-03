"""What one cleanup pass over the rendered visuals found, took, and left behind.

`state/raw/visual-prunes/YYYY/MM/DD/<file_id>.parquet`. One row per pass of
the gardener's `visual-prune` task, written through the ledger door, dry run or
not. Read whole - "is the backlog shrinking" has no time bound - so the
day layout buys the read nothing, and it is there for what it buys a writer
instead: every writer holds a file of its own, so two runs never write one
path. `idhazh.ledger` owns that trade and states it
(`docs/architecture/contracts/schemas.md`). The CSV methods below read the day
files this ledger was committed as before it moved there.

**`skipped_by_fuse` is the field this row exists for.** `deleted` is capped by
the visual-prune declaration's `max_deletes_per_run`, so it reads the same on a
run that cleared its
backlog and on one that could not get near it: 200 either way. Only the pair
says which. A run that deleted 200 and skipped none is finished; a run that
deleted 200 and skipped 4,000 has twenty more runs to go, and nothing else on
this row would tell them apart.

**`skipped_by_fuse` means the same thing on a dry run as on a live one**: the
candidates the fuse would not have let this run reach. It is deliberately not
"everything that was still there afterwards". A dry run deletes nothing, so
folding the two facts together would make `skipped_by_fuse` equal
`candidates_found` on every run that ships today, and the field would say
nothing at all - which is the failure the field exists to fix, arrived at from
the other side. `dry_run` is the cell that says nothing was deleted, and the
arithmetic reads it: on a live run `deleted + skipped_by_fuse` is
`candidates_found` exactly, and on a dry run it falls short by what a live run
would have taken.

**The two byte figures are the tree the cleanup walks, not the published site.**
Those are two different trees - eighteen times apart when `idhazh.retention` last
measured them - and pairing a number from one with a name from the other is the
defect that module already paid for once. The site is measured by `idhazh
site-weight` against the built bundle, and never here.
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

#: The cells that are a date or nothing. An empty cell is an absent value on
#: both of them, and neither ever carries a stand-in date.
_OPTIONAL_DATES = ("cutoff_date", "oldest_kept")


class VisualPruneRow(Contract):
    """One cleanup pass, one row."""

    __schema_stem__: ClassVar[str] = "visual-prune-row"
    __changelog__: ClassVar[tuple[ChangelogEntry, ...]] = (
        ChangelogEntry(
            version="2026-10-03T16:19",
            change="Byte totals cover the named candidate window.",
            why="A whole-tree total reads more files as the archive grows.",
        ),
        ChangelogEntry(
            version="2026-10-03T15:00",
            change="Candidates and oldest kept are limited to the named period window.",
            why="A scheduled cleanup reads a fixed period window and names it in the report.",
        ),
        ChangelogEntry(
            version="2026-09-06T13:00",
            change="Initial shape: the policy in force, the cutoff it computed, what it found.",
            why="The cleanup counted what it deleted into a job log that GitHub keeps.",
        ),
    )

    date: DateStamp = Field(description="The digest date the cleaning run was for.")
    run_id: RunId = Field(description="The run that did the cleaning.")
    policy_months: int = Field(
        ge=-1,
        description=(
            "`retention.image_months` in force. -1 means no age window at all, so the "
            "row reports and nothing is ever a candidate; it is the model default and "
            "was what shipped until 2026-09-13, when config/idhazh.json took 13."
        ),
    )
    max_deletes_per_run: int = Field(
        ge=0,
        description="The visual-prune declaration's `max_deletes_per_run` in force - the fuse.",
    )
    dry_run: bool = Field(
        description=(
            "True when this run was only reporting. Set by config or by the step's own "
            "flag, and either one is enough."
        )
    )
    cutoff_date: DateStamp | None = Field(
        default=None,
        description=(
            "The day the policy drew its line at. Empty when the policy is off, because "
            "a disabled policy has no line and a stand-in date would read like one."
        ),
    )
    window_start: DateStamp | None = Field(
        default=None,
        description="First expired UTC day included in this pass's fixed candidate window.",
    )
    window_end: DateStamp | None = Field(
        default=None,
        description="Last expired UTC day included in this pass's fixed candidate window.",
    )
    candidates_found: int = Field(
        ge=0, description="Rendered visuals in the named candidate window."
    )
    deleted: int = Field(ge=0, description="How many this run removed. Always 0 on a dry run.")
    skipped_by_fuse: int = Field(
        ge=0,
        description=(
            "Candidates the fuse would not let this run reach. The same fact on a dry "
            "run as on a live one, which is what stops it collapsing into `deleted`."
        ),
    )
    fuse_tripped: bool = Field(description="Whether the backlog was larger than the fuse.")
    bytes_reclaimed: int = Field(
        ge=0, description="What the deletions freed, measured. 0 on a dry run."
    )
    oldest_kept: DateStamp | None = Field(
        default=None,
        description=(
            "Whether the first kept day carries a rendered visual after this run. Empty "
            "when that named day carries none; this does not claim to describe older history."
        ),
    )
    payload_bytes_before: int = Field(
        ge=0,
        description=(
            "The bytes under this pass's named candidate days, before cleanup. This "
            "is not the whole committed tree or the built site."
        ),
    )
    payload_bytes_after: int = Field(
        ge=0, description="The same named candidate days, after cleanup."
    )

    @model_validator(mode="after")
    def _the_arithmetic_holds(self) -> Self:
        """Five cross-field rules, each one a way a hand-written row could lie.

        `fuse_tripped` and `bytes_reclaimed` are both derivable, and both are on
        the row because the plan asked a reader for them. Pinning them to what
        they are derived from is what keeps a stored value from drifting away
        from the thing it describes.
        """
        if self.fuse_tripped != (self.skipped_by_fuse > 0):
            raise ValueError("fuse_tripped and skipped_by_fuse must say the same thing")
        if (self.policy_months < 0) != (self.cutoff_date is None):
            raise ValueError("a switched-off policy has no cutoff, and a live one has one")
        if (self.window_start is None) != (self.window_end is None):
            raise ValueError("the candidate window has both endpoints or neither")
        if (
            self.window_start is not None
            and self.window_end is not None
            and self.window_start > self.window_end
        ):
            raise ValueError("the candidate window starts after it ends")
        if self.payload_bytes_after > self.payload_bytes_before:
            raise ValueError("a cleanup cannot grow the tree it walks")
        if self.payload_bytes_before - self.payload_bytes_after != self.bytes_reclaimed:
            raise ValueError("bytes_reclaimed must be the difference the two measurements show")
        if self.dry_run:
            if self.deleted or self.bytes_reclaimed:
                raise ValueError("a dry run deletes nothing and reclaims nothing")
        elif self.deleted + self.skipped_by_fuse != self.candidates_found:
            raise ValueError(
                "a live run either deleted a candidate or the fuse held it back, so the "
                "two have to add up to what it found"
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
        """The inverse. An empty cell is an absent value, never the empty string."""
        payload: dict[str, Any] = {name: row.get(name, "") for name in cls.model_fields}
        for name in _OPTIONAL_DATES:
            if payload[name] == "":
                payload[name] = None
        return cls.model_validate(payload)

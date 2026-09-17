"""A line one host prints on page after page, so a template is caught the third time.

One row per host and line, in `state/chrome.csv`. Nothing here is text a
publisher wrote: a line becomes a sha256 before it is counted, so the store can
never carry an instruction a fetched page tried to give us (Guardrail #11).

**The grain is the host, never the feed.** Chrome belongs to the server
template. Four of our feeds are one broadcaster and two are one paper, so keying
on the feed would split one template's evidence across several rows and count
each page once - which is the mistake the outlet rule already repaired for
grouping.

**One file, and its read carries no clock.** Chrome learned in August is chrome
in September, so a day or month layout would open every partition anyway and buy
a directory walk for nothing. What bounds the file is the source registry:
`extract.chrome_lines_per_host_max` lines a host, and `extract.chrome_forget_days`
since a line was last seen. It grows with how many hosts we read and then stops.

`docs/architecture/extraction/chrome.md` owns the rule this store serves.
"""

from __future__ import annotations

from typing import Any, ClassVar, Self

from pydantic import Field

from idhazh.contracts.base import (
    ChangelogEntry,
    Contract,
    DateStamp,
    Sha256,
)

#: How a line is reduced before it is hashed, as a name a row carries.
#:
#: **A column and never a comment.** The reduction decides what two lines have
#: to have in common to be the same line, so changing it makes every stored hash
#: mean something else. A read filters to the rule it computes with, which turns
#: a changed normaliser into rows that age out rather than into rows that
#: silently never match - and a silent never-match is a signal that reads as
#: "this host prints nothing twice".
CHROME_LINE_RULE: str = "nfkc-casefold-collapse-v1"


class ChromeLineRow(Contract):
    """One line, one host, and how many of that host's pages carried it."""

    __schema_stem__: ClassVar[str] = "chrome-line-row"
    __changelog__: ClassVar[tuple[ChangelogEntry, ...]] = (
        ChangelogEntry(
            version="2026-09-17",
            change="Initial shape: the host, the reduction, the line's hash and its page count.",
            why="A host serving one template was caught on the 166th page, or never.",
        ),
    )

    host: str = Field(
        min_length=1,
        max_length=253,
        description=(
            "The registrable host of the page's canonical address, lowercased. The "
            "server that served the template, never the feed that named it."
        ),
    )
    line_rule: str = Field(
        default=CHROME_LINE_RULE,
        min_length=1,
        description=(
            "Which reduction produced `line_hash`. A read filters to the rule it "
            "computes with, so a changed reduction retires its rows by ageing them "
            "out rather than by matching nothing and saying the host is clean."
        ),
    )
    line_hash: Sha256 = Field(
        description=(
            "The reduced line, hashed. The line itself is fetched text and is never "
            "stored: a sha256 of it cannot carry an instruction (Guardrail #11)."
        )
    )
    pages_seen: int = Field(
        ge=1,
        description=(
            "How many DISTINCT pages of this host have carried the line. Distinct "
            "pages rather than rows, because a line on one page repeated is one page "
            "saying one thing and says nothing about a template."
        ),
    )
    first_seen: DateStamp = Field(description="The published day this line was first counted on.")
    last_seen: DateStamp = Field(
        description=(
            "The published day it was last counted on. What the forget window and the "
            "eviction order both read."
        )
    )

    @classmethod
    def csv_columns(cls) -> tuple[str, ...]:
        """One definition, so a writer and a reader cannot disagree about the shape."""
        return tuple(cls.model_fields)

    def csv_row(self) -> dict[str, str]:
        """Every cell a string. No field here is optional, so no cell is ever empty."""
        payload = self.model_dump(mode="json")
        return {name: str(payload[name]) for name in payload}

    @classmethod
    def from_csv_row(cls, row: dict[str, str]) -> Self:
        """The inverse. Every cell is required, so a missing one refuses the row."""
        payload: dict[str, Any] = {name: row[name] for name in cls.model_fields}
        return cls.model_validate(payload)

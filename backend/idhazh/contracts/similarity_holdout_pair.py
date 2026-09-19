"""Two articles a judge read, and whether it called them one story.

The fixed floor every fitted line has to stay above. One row a pair, and the
false rows are the load-bearing ones: a line that drops below a pair marked as
two different stories would publish a merge nobody chose.

It carries addresses rather than digests because the rows are written to be read
back by a person. The two address keys and the pair key are recomputed on read
from the URLs on the row, so there is no cell that can go stale.

**A judge labels this file, and `note` says which one** (owner, 2026-09-19).
It was specified as a person's hand-typed file and shipped empty, so the floor it
exists to set was never on any screen. A model strong enough to be trusted with
the call fills it instead, and some autotune paths will route a person into the
same loop later. The mark is only worth what its labeller is worth, which is why
the labeller's name is on every row rather than in a header somewhere.
"""

from __future__ import annotations

from typing import Any, ClassVar, Self

from pydantic import Field, model_validator

from idhazh.contracts.base import (
    ChangelogEntry,
    Contract,
    DateStamp,
    Url,
    derive_text_digest,
    derive_url_key,
)
from idhazh.contracts.item_health import OneLine


class SimilarityHoldoutPair(Contract):
    """One pair, two headlines, a person's mark and the reason for it."""

    __schema_stem__: ClassVar[str] = "similarity-holdout-pair"
    __changelog__: ClassVar[tuple[ChangelogEntry, ...]] = (
        ChangelogEntry(
            version="2026-09-19",
            change="A judge labels this file, not only a person. No field moved.",
            why="Specified as hand-typed, it shipped empty, so the floor was on no screen.",
        ),
        ChangelogEntry(
            version="2026-09-18",
            change="Initial shape: two addresses, two headlines, a mark and its reason.",
            why="The hand labels that set today's floor lived in one person's reading.",
        ),
    )

    left_url: Url = Field(
        description=(
            "One of the two articles, as a canonical URL. A person types this file, so it "
            "carries addresses rather than digests; the keys are recomputed on read."
        )
    )
    right_url: Url = Field(description="The other article.")
    left_date: DateStamp = Field(
        description=(
            "The digest date the left article was published on. On the row so a reader of "
            "the holdout report opens two named day files rather than searching the "
            "published tree for an address."
        )
    )
    right_date: DateStamp = Field(
        description=(
            "The digest date the right article was published on. The same day as the left "
            "one where the pair could ever have merged, and a different one where the pair "
            "straddled midnight."
        )
    )
    left_title: OneLine = Field(
        description=(
            "The headline, so a reader of the holdout panel can tell which pair a mark "
            "belongs to."
        )
    )
    right_title: OneLine = Field(description="The other headline.")
    same_story: bool = Field(
        description=(
            "True where the labeller judged the two to be one event. The false rows are "
            "the load-bearing ones: the line has to stay above every one of them."
        )
    )
    marked_on: DateStamp = Field(
        description=(
            "When it was marked. A mark taken under an older reading of what counts as "
            "one story is still on record and still says when it was taken."
        )
    )
    note: OneLine = Field(
        description=(
            "Who marked it and why, in one line. A mark is worth what its labeller is "
            "worth, and one with no reason cannot be argued with later."
        )
    )

    @property
    def left_url_key(self) -> str:
        """The left address key, recomputed. Never a column a typist could get wrong."""
        return derive_url_key(self.left_url)

    @property
    def right_url_key(self) -> str:
        """The right address key, recomputed for the same reason."""
        return derive_url_key(self.right_url)

    @property
    def pair_key(self) -> str:
        """The same identity a scored pair carries, so the two files can be joined."""
        keys = sorted((self.left_url_key, self.right_url_key))
        return derive_text_digest(keys[0] + keys[1])

    @model_validator(mode="after")
    def _the_two_addresses_differ(self) -> Self:
        """One article against itself is not a mark, and it scores 1.0 whatever the line is.

        A row like that would sit in the holdout set as a same-story pair no line
        can ever fail, which reads as evidence and is not.
        """
        if self.left_url == self.right_url:
            raise ValueError(f"a holdout pair is two articles, and both cells are {self.left_url}")
        return self

    @classmethod
    def csv_columns(cls) -> tuple[str, ...]:
        return tuple(cls.model_fields)

    def csv_row(self) -> dict[str, str]:
        payload = self.model_dump(mode="json")
        return {name: "" if payload[name] is None else str(payload[name]) for name in payload}

    @classmethod
    def from_csv_row(cls, row: dict[str, str]) -> Self:
        payload: dict[str, Any] = {name: row.get(name, "") for name in cls.model_fields}
        payload["same_story"] = row.get("same_story", "") == "True"
        return cls.model_validate(payload)

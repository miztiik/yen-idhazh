"""Which known-answer pairs does the content-similarity judge check itself against?

One config file, `config/judges/content-similarity-canaries.json`, holds a short list of
pairs of summaries whose right answer was decided before the judge saw them. Each council
run puts them to the judge through the same request builder as the night's own pairs, and
the answers go on the night's threshold row. A wrong answer is a reading, logged and stored,
and nothing reacts to it.

A **canary pair** here is a known-answer pair. The word also names a planted prompt-injection
example elsewhere in this repository; the two share nothing but the word.

**The summary text lives in this file and is never refreshed from the published days.** A
published day retires, and a pair that pointed at one would be orphaned. Refreshing it
automatically would put fetched text into the reference set unreviewed, so a pair changes by
a reviewed edit that bumps `version` (Guardrail #11).

**Only the checks that need no clock live here.** That `version` names a real day that has
already arrived is checked where the file is read (`content_similarity_judge.settings`), so
this contract stays the same on every day it is validated.
"""

from __future__ import annotations

from collections import Counter
from datetime import date as date_type
from enum import StrEnum
from types import MappingProxyType
from typing import Annotated, Final, Literal, Self

from pydantic import AfterValidator, Field, StringConstraints, field_validator, model_validator

from idhazh.contracts.base import (
    PRINTABLE_LINE_PATTERN,
    DateStamp,
    ItemId,
    Model,
    Slug,
    normalize_prose,
)
from idhazh.contracts.story_similarity_pair_verdict import SameStoryVerdict

#: The most pairs the file may hold. Each pair is two calls on one runner at about the cost of a
#: drawn pair (110.98 s measured), so twelve pairs on four runners is three pairs and about five
#: and a half minutes a runner before the night's own pairs. A bigger set takes a reviewed edit
#: of this contract, because every pair added is time taken from the pairs that move the
#: thresholds.
MAX_CANARY_PAIRS: Final = 12

#: The id prefix for a pair explicitly marked as hand-written.
SYNTHETIC_PREFIX: Final = "synthetic-"


def _a_day_that_exists(day: str) -> str:
    try:
        date_type.fromisoformat(day)
    except ValueError as error:
        raise ValueError(f"{day} is not a calendar day") from error
    return day


CanaryDate = Annotated[
    DateStamp, AfterValidator(_a_day_that_exists), Field(json_schema_extra={"format": "date"})
]
ReviewNote = Annotated[str, StringConstraints(pattern=PRINTABLE_LINE_PATTERN)]


class CanaryKind(StrEnum):
    """What the pair is, in the terms of the judge's own three answers."""

    SAME = "same"
    DIFFERENT = "different"
    UNCLEAR = "unclear"


#: The answer each kind has, by the judge prompt's own definitions: one event, two events, and
#: a summary too vague to name what happened.
ANSWER_OF_KIND: Final = MappingProxyType(
    {
        CanaryKind.SAME: SameStoryVerdict.YES,
        CanaryKind.DIFFERENT: SameStoryVerdict.NO,
        CanaryKind.UNCLEAR: SameStoryVerdict.UNCLEAR,
    }
)


class CanarySide(Model):
    """One of a pair's two summaries, with a source pointer only when recorded."""

    summary: str = Field(
        min_length=1,
        description=(
            "The summary exactly as the judge is given it. ASCII, because the file is, and "
            "shaped as every published summary is: no control characters and no stray "
            "spaces or blank lines. An accent is folded to its plain letter when the "
            "summary is copied in."
        ),
    )
    date: CanaryDate | None = Field(
        default=None,
        description="The UTC digest day the summary was copied from, if recorded.",
    )
    item_id: ItemId | None = Field(
        default=None,
        description="The item's id in that UTC digest day, if recorded.",
    )

    @field_validator("summary")
    @classmethod
    def _ascii_and_shaped_like_a_published_summary(cls, text: str) -> str:
        """The shape a live summary has, so the request is built from the same kind of text."""
        if not text.isascii():
            raise ValueError("a known-answer summary is ASCII, because the config file is")
        if normalize_prose(text) != text:
            raise ValueError(
                "a known-answer summary is not shaped like a published one: it holds a "
                "control character, a run of spaces or a stray blank line"
            )
        return text

    @model_validator(mode="after")
    def _the_day_and_the_item_come_together(self) -> Self:
        if (self.date is None) != (self.item_id is None):
            raise ValueError(
                "a summary names both the day and the item it was copied from, or neither"
            )
        return self


class CanaryPair(Model):
    """Two summaries, the expected answer, and any recorded review notes."""

    id: Slug = Field(
        description=(
            "Stable name of the pair, and the key its answer is filed under on the night's "
            "threshold row. Across config revisions, the same id identifies the same case "
            "only if both summaries and the expected answer are unchanged. "
            "The summaries are addressed as <pair-id>.left.summary and <pair-id>.right.summary."
        ),
    )
    kind: CanaryKind = Field(
        description=(
            "same: one event, the same actors, action and occasion. different: no actor, "
            "place or topic in common. unclear: at least one summary too vague to name what "
            "happened."
        ),
    )
    expected: SameStoryVerdict = Field(
        description=(
            "The answer the judge ought to give in both orders. It follows from the kind, and "
            "is written out so a mislabelled pair is a disagreement the file refuses."
        ),
    )
    date: CanaryDate | None = Field(
        default=None,
        description="UTC date recorded for the pair, not a source pointer for either summary.",
    )
    origin: Literal["published", "synthetic"] | None = Field(
        default=None,
        description=(
            "Recorded provenance: published requires both summaries to name their source "
            "items; synthetic requires no source items and an id starting with `synthetic-`."
        ),
    )
    labelled_by: Literal["agent", "person"] | None = Field(
        default=None,
        description="Who decided the expected answer from the summaries alone, if recorded.",
    )
    failure_mode: ReviewNote | None = Field(
        default=None,
        description="One line of ASCII naming the mistake this pair checks for, if recorded.",
    )
    basis: ReviewNote | None = Field(
        default=None,
        description="One line of ASCII explaining the expected answer, if recorded.",
    )
    left: CanarySide = Field(description="The first summary, in file order.")
    right: CanarySide = Field(description="The second summary, in file order.")

    @model_validator(mode="after")
    def _the_labels_and_the_provenance_agree(self) -> Self:
        if self.expected is not ANSWER_OF_KIND[self.kind]:
            raise ValueError(
                f"{self.id} is of kind {self.kind.value}, which is answered "
                f"{ANSWER_OF_KIND[self.kind].value}, and it expects {self.expected.value}"
            )
        if self.origin is None:
            return self
        if self.id.startswith(SYNTHETIC_PREFIX) != (self.origin == "synthetic"):
            raise ValueError(
                f"{self.id} has origin {self.origin}, and a hand-written pair is the one whose "
                f"id starts with {SYNTHETIC_PREFIX}"
            )
        named = [side.item_id is not None for side in (self.left, self.right)]
        if self.origin == "published" and not all(named):
            raise ValueError(f"{self.id} is published, so each summary names the item it came from")
        if self.origin == "synthetic" and any(named):
            raise ValueError(f"{self.id} is hand-written, so no summary names an item")
        return self


class ContentSimilarityCanaryConfig(Model):
    """The known-answer pairs, and the date their text last changed."""

    version: DateStamp = Field(
        description=(
            "UTC date (YYYY-MM-DD) of the last edit to this file that changed a value, bumped "
            "in the same commit as that edit. A night records the date of each judge-owned "
            "config file it read. It is a revision date and never a schema version, so it needs "
            "no migration. The loader refuses a date that does not exist or has not arrived yet."
        ),
    )
    pairs: list[CanaryPair] = Field(
        min_length=1,
        max_length=MAX_CANARY_PAIRS,
        description=(
            "The pairs, in the order that deals them: the pair at position i goes to runner "
            "(i + the date's ordinal) mod the runners, so the order is part of the contract and "
            "a new pair goes at the end."
        ),
    )

    @model_validator(mode="after")
    def _ids_are_unique_and_every_kind_is_present(self) -> Self:
        counted = Counter(pair.id for pair in self.pairs)
        twice = sorted(name for name, count in counted.items() if count > 1)
        if twice:
            raise ValueError(f"known-answer pair ids repeat: {twice}")
        present = {pair.kind for pair in self.pairs}
        missing = sorted(kind.value for kind in CanaryKind if kind not in present)
        if missing:
            raise ValueError(
                f"the pairs hold no pair of kind {missing}, and a judge checked on two of its "
                "three answers is not checked on the third"
            )
        return self

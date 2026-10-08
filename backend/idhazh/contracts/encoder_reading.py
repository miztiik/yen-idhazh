"""One encoder's reading, written as it is taken.

A reading is written to disk before the encoding starts and rewritten at every
checkpoint, so a shard that hits the job deadline leaves a part-finished reading
behind rather than nothing at all. A six-hour job that dies at five fifty-nine
with an empty directory has taught nobody anything, and the encoder most likely
to hit that deadline is the large one whose cost is the open question.

The shape is declared here because a later run reads it: the collect step merges
one file a shard into the table a person reads (CLAUDE.md Guardrail #3).
"""

from __future__ import annotations

from enum import StrEnum
from typing import Annotated, ClassVar, Self

from pydantic import Field, model_validator

from idhazh.contracts.base import (
    ChangelogEntry,
    Contract,
    Model,
    Slug,
    Timestamp,
)


class ReadingState(StrEnum):
    """How far one encoder's reading got."""

    #: The weights are downloading or loading. Nothing is encoded yet.
    LOADING = "loading"

    #: Encoding is under way. `articles_done` says how far.
    ENCODING = "encoding"

    #: Every article encoded and every pair scored.
    MEASURED = "measured"

    #: The model did not load. `reason` says what the runtime reported.
    UNAVAILABLE = "unavailable"

    #: The shard was stopped before it finished. The counts are what it reached.
    STOPPED = "stopped"


class PairCounts(Model):
    """How many pairs of each kind this reading scored."""

    #: Titles sharing most of their subject words. Treated as one event.
    same: Annotated[int, Field(ge=0)]

    #: Titles sharing almost nothing. Treated as different events.
    different: Annotated[int, Field(ge=0)]

    #: Titles sharing something but not much. Never scored right or wrong.
    ambiguous: Annotated[int, Field(ge=0)]

    #: One outlet, one day, one subject: a correction or a follow-up, and a
    #: word-overlap rule cannot say which. Never scored right or wrong.
    related: Annotated[int, Field(ge=0)] = 0


class EncoderReading(Contract):
    """What one encoder scored, how fast it ran, and how far it got."""

    __schema_stem__: ClassVar[str] = "encoder-reading"
    __changelog__: ClassVar[tuple[ChangelogEntry, ...]] = (
        ChangelogEntry(
            version="2026-10-08",
            change="Initial shape: the encoder, its progress, its readings and its cost.",
            why=(
                "A shard that hits the job deadline left nothing behind, and the "
                "encoder most likely to hit it is the one whose cost is the question."
            ),
        ),
    )

    version: str = "2026-10-08"

    #: The short name this comparison files the encoder under.
    slug: Slug

    #: The published name of the weights, as a model hub answers it.
    model_id: str

    #: Declared parameter count, in millions. It sets the expectation for cost.
    parameters_millions: Annotated[int, Field(ge=0)]

    #: The text this encoder wants in front of its input. Empty for most.
    prefix: str = ""

    #: Why this encoder is in the comparison at all.
    why: str

    #: How far the reading got.
    state: ReadingState

    #: What the runtime reported, when the state is `unavailable` or `stopped`.
    reason: str | None = None

    #: When this file was last written. Every checkpoint moves it.
    written_at: Timestamp

    #: Articles this reading has to encode.
    articles_to_encode: Annotated[int, Field(ge=0)]

    #: Articles encoded so far. Equal to `articles_to_encode` when measured.
    articles_done: Annotated[int, Field(ge=0)] = 0

    #: Seconds spent downloading and loading the weights.
    load_seconds: Annotated[float, Field(ge=0)] | None = None

    #: Seconds spent encoding, so far.
    encode_seconds: Annotated[float, Field(ge=0)] | None = None

    #: Numbers an article. Known once the first batch returns.
    numbers_an_article: Annotated[int, Field(ge=1)] | None = None

    #: Pairs of each kind, once the scoring runs.
    pairs: PairCounts | None = None

    #: The chance this encoder scores a matching pair above a mismatching one.
    #: One is perfect, a half is a coin toss. No similarity scale distorts it.
    separation: Annotated[float, Field(ge=0, le=1)] | None = None

    #: Mean score of the matching pairs.
    same_mean: float | None = None

    #: Mean score of the mismatching pairs.
    different_mean: float | None = None

    #: Mean score of the uncertain middle. Not right or wrong, only a lean.
    ambiguous_mean: float | None = None

    #: Share of uncertain pairs scored above halfway between the two means.
    #: High means this encoder joins too much; low means it fragments.
    ambiguous_lean: Annotated[float, Field(ge=0, le=1)] | None = None

    #: Mean score of one outlet's second piece on one subject in one day.
    related_mean: float | None = None

    #: Share of those scored above halfway. Near one means this encoder cannot
    #: tell a follow-up from a new story; lower means it keeps some signal.
    related_lean: Annotated[float, Field(ge=0, le=1)] | None = None

    #: How far apart the two means sit. A wide spread leaves room for a cut-off.
    spread: float | None = None

    #: Articles encoded a second, on the runner's four threads.
    articles_a_second: Annotated[float, Field(ge=0)] | None = None

    #: Minutes to encode every published article once, at that rate.
    minutes_for_whole_archive: Annotated[float, Field(ge=0)] | None = None

    #: Minutes to encode one normal day, at that rate.
    minutes_for_one_day: Annotated[float, Field(ge=0)] | None = None

    #: Peak memory of the whole process, in gigabytes, against the runner's 16.
    peak_memory_gb: Annotated[float, Field(ge=0)] | None = None

    @model_validator(mode="after")
    def check_progress_fits_the_state(self) -> Self:
        """A measured reading encoded everything and scored something."""
        if self.articles_done > self.articles_to_encode:
            raise ValueError(
                f"{self.slug}: encoded {self.articles_done} of "
                f"{self.articles_to_encode}, which is more than it was given"
            )
        if self.state is ReadingState.MEASURED:
            if self.articles_done != self.articles_to_encode:
                raise ValueError(
                    f"{self.slug}: measured, but encoded {self.articles_done} "
                    f"of {self.articles_to_encode}"
                )
            if self.separation is None:
                raise ValueError(f"{self.slug}: measured, but no separation")
        if self.state in (ReadingState.UNAVAILABLE, ReadingState.STOPPED):
            if not self.reason:
                raise ValueError(f"{self.slug}: {self.state} needs a reason")
        return self

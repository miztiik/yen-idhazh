"""One item's summary: our own text, of a pinned shape.

The article body is never committed and never served; this payload and the
source link are the entire published output. The shape is enforced by the
decoder rather than requested in the prompt, so an injected instruction cannot
change it even if it changes the words (Guardrail #11).
"""

from __future__ import annotations

from enum import StrEnum
from typing import ClassVar, Self

from pydantic import Field, model_validator

from idhazh.contracts.article import UntrustedLine
from idhazh.contracts.base import (
    ChangelogEntry,
    Contract,
    ItemId,
    Sha256,
    Slug,
    Timestamp,
    UrlKey,
    derive_output_digest,
)
from idhazh.contracts.call_cost import COST_FIELDS, CallCost
from idhazh.contracts.item_health import FAILURE_CODE_STAGES, FailureCode, ItemStage


class SummaryStatus(StrEnum):
    OK = "ok"
    FAILED = "failed"
    SKIPPED = "skipped"


class LengthAction(StrEnum):
    """What the length verdict did with this reply.

    Recorded because a trimmed summary and a compliant one are indistinguishable
    afterwards - the ledger stores the length after the trim - so without this
    field the pipeline cannot say how often the tolerance is doing work.
    """

    PUBLISH = "publish"
    PUBLISH_OVER = "publish_over"
    TRIM = "trim"
    FAIL = "fail"


class Summary(Contract):
    """The Summarize stage's output payload, one per item."""

    __schema_stem__: ClassVar[str] = "summary"
    __changelog__: ClassVar[tuple[ChangelogEntry, ...]] = (
        ChangelogEntry(
            version="2026-09-12T18:40",
            change=(
                "item_id accepts a second shape: sixteen Crockford base32 symbols "
                "beside the decimal digits it already took."
            ),
            why=(
                "Ten decimal digits is 33 bits of the address, which collides often "
                "enough that the collision had to be resolved - and the only way to "
                "resolve one is to step the loser past whatever else the run planned, "
                "so a collided id depended on the day's pool rather than on the "
                "address alone. Two runs of one day draw different pools, so the same "
                "article came back under a second id and published twice. Eighty bits "
                "do not collide. This widens and never contracts: every day published "
                "before today carries the decimal shape and a published day is frozen, "
                "so nothing was rewritten and no read-side migration is owed."
            ),
        ),
        ChangelogEntry(
            version="2026-09-12T16:20",
            change=(
                "Added optional call_1 and call_2, each a CallCost; the five flat cost "
                "fields are now the item's total across the calls recorded there."
            ),
            why=(
                "An item is read by more than one model call and this payload kept one "
                "call's five numbers without saying which. Folded, they stop being "
                "readable: measured on the one two-call run, cached_tokens of 0 and "
                "1,493 fold to 1,493 against 3,886 prompt tokens - 38 percent, which is "
                "neither call's 0 nor its 62. Both slots default to null, so a payload "
                "an earlier run wrote still validates and its flat five stand alone. "
                "Where a slot is filled the flat five must equal the sum over the "
                "filled slots, which is what keeps every aggregate that reads them - "
                "publish_day_metrics, publish_console_band, reconcile_prefill - correct "
                "the day a second call starts being recorded, with no edit of their "
                "own. No read-side migration is owed: this payload is written under "
                "backend/var/, which is gitignored and read only inside the run that "
                "wrote it."
            ),
        ),
        ChangelogEntry(
            version="2026-09-10T00:30",
            change="length_action added, optional and defaulting to null.",
            why=(
                "A reply outside its band's ask no longer deletes the item; it publishes, "
                "publishes over-length, or is trimmed at the last complete sentence that "
                "fits. A trimmed summary and a compliant one read identically afterwards, "
                "because summary_word_count is measured after the trim, so without this "
                "field there is no way to count how often the tolerance fires. Additive "
                "with a default, so a payload written by an earlier run still validates "
                "and reads as null - which is the truth about it, since no verdict was "
                "recorded when it was written."
            ),
        ),
        ChangelogEntry(
            version="2026-08-30T20:00",
            change="attempt says in its description that it is a constant, not a measurement.",
            why=(
                "The description read 'A low-band summary is retried on the smaller "
                "model', which describes a retry the pipeline does not do. summarize "
                "takes attempt as a keyword defaulting to 1 and no caller passes "
                "anything else, so the column is 1 everywhere: measured 2026-08-30, "
                "3,113 of 3,113 rows of state/scores.csv carry 1. A reader who "
                "believed the old sentence would have read a column of 1s as evidence "
                "that a retry almost never fires, which is a measurement the data "
                "cannot support. No field was added, removed or retyped and no payload "
                "was rewritten; the generated schema moves because a description is "
                "part of it."
            ),
        ),
        ChangelogEntry(
            version="2026-08-27",
            change="failure_code may now carry copied_source or leaked_address.",
            why=(
                "Summarize refuses two more replies: one that copies the source instead "
                "of summarizing it, and one that carries an address into our own words. "
                "No field on this payload changed, but the failure vocabulary is inlined "
                "into this schema, so the generated file's bytes move and the change is "
                "stamped here rather than left to the drift gate to announce. Additive - "
                "a payload written before today names none of the new values and still "
                "validates."
            ),
        ),
        ChangelogEntry(
            version="2026-08-24T18:30",
            change="Added prefill_ms, decode_ms and cached_tokens.",
            why=(
                "summarize_ms is one number covering two costs with different rates: "
                "reading the article runs about twice as fast per token as writing the "
                "summary, so a blended figure cannot say whether a slow run was a long "
                "article or a long reply. The runtime already reports both separately, "
                "and cached_tokens is what makes a prefill figure comparable between "
                "items. All three default to zero, so an older payload still validates."
            ),
        ),
        ChangelogEntry(
            version="2026-08-23T17:36",
            change="Added optional failure_code for typed summarize failures.",
            why=(
                "A dead local model server is infrastructure failure, not a malformed "
                "model reply. The failure payload now carries model_unreachable as a "
                "typed value so the item-health classifier can read it without "
                "pattern-matching failure_detail."
            ),
        ),
        ChangelogEntry(
            version="2026-08-23",
            change="Added optional title, and folded it into output_digest when present.",
            why=(
                "The digest published the source's own headline, which is written to win "
                "a click. The summarizer now writes a title from the article's own facts "
                "and it is published words like the rest, so it belongs in the digest "
                "that detects drift. Additive both ways: the field is optional, and a "
                "null title is left out of the digested payload rather than digested as "
                "null, so every payload written before today still recomputes to the "
                "same value."
            ),
        ),
        ChangelogEntry(
            version="2026-08-22",
            change="Split duration_ms into fetch_ms, extract_ms and summarize_ms.",
            why=(
                "One number covering fetch, extract and summarize could not answer the "
                "question it was there for: a slow item might be a slow host or a slow "
                "model, and only one of those is ours to fix. Additive - the blended "
                "field stays, and a payload written before this still validates."
            ),
        ),
        ChangelogEntry(
            version="2026-08-21T02:00",
            change="Added required pipeline_fingerprint and output_digest.",
            why=(
                "Skip-if-exists becomes skip-if-fingerprint-matches, and a match with unequal "
                "output has to be detectable. No payload predates this - the pipeline has "
                "never run - so the read-side migration is the fixtures, restamped here."
            ),
        ),
        ChangelogEntry(
            version="2026-08-21",
            change="Initial shape: summary text, key points, the model, and the cost.",
            why="Contracts before logic - Summarize is written against a fixed payload.",
        ),
    )

    item_id: ItemId
    url_key: UrlKey
    title: UntrustedLine | None = Field(
        default=None,
        description=(
            "Our own headline, written from the article's facts. Optional because a "
            "title outside the asked range degrades to the source's rather than "
            "costing the item (section 1a)."
        ),
    )
    summary: str | None = None
    key_points: list[str] = Field(default_factory=list)

    pipeline_fingerprint: Sha256 = Field(
        description="The stamp of every input that could have moved this text."
    )
    output_digest: Sha256 = Field(
        description="Digest of the words only. Recomputed on read, never trusted."
    )

    model_id: Slug = Field(
        description="The ModelRef id from config. The full ref lives in the manifest."
    )
    attempt: int = Field(
        default=1,
        ge=1,
        description=(
            "Which summarize attempt wrote this payload. A count, not a duration - 1 "
            "is the first try. It is 1 on every payload and every ledger row ever "
            "written: 3,113 of 3,113 rows of state/scores.csv on 2026-08-30. "
            "summarize() takes it as a keyword defaulting to 1 and no caller passes "
            "anything else, because no retry budget exists yet. Nothing reads it "
            "today. It is kept for the retry budget it is named for, so read it as a "
            "constant that is reserved and never as a measurement of how often a "
            "summary is redone."
        ),
    )
    source_truncated: bool = False
    length_action: LengthAction | None = Field(
        default=None,
        description=(
            "What the length verdict did with this reply, or null on a payload written "
            "before the verdict existed and on any item that never reached it. "
            "`publish` is inside the band's ask or inside the tolerance around it; "
            "`publish_over` ran long on a band that would rather be long than cut a "
            "qualification off the end; `trim` was cut at the last complete sentence "
            "that fits; `fail` did not reach the absolute floor and is a failed "
            "extraction rather than a summary."
        ),
    )
    input_tokens: int = Field(
        default=0, ge=0, description="Prompt tokens, added over every call recorded below."
    )
    output_tokens: int = Field(
        default=0, ge=0, description="Tokens written, added over every call recorded below."
    )
    duration_ms: int = Field(
        default=0, ge=0, description="Fetch plus extract plus summarize. The three below sum to it."
    )
    fetch_ms: int = Field(default=0, ge=0, description="Network. Says more about the host than us.")
    extract_ms: int = Field(default=0, ge=0, description="Boilerplate removal and sanitising.")
    summarize_ms: int = Field(
        default=0,
        ge=0,
        description=(
            "The model, on the stage clock. The only one of the three that a model swap "
            "moves, and the one cost below that stays a stage figure: it is the wall "
            "clock around every call the stage made, including the HTTP overhead no "
            "call reports."
        ),
    )
    prefill_ms: int = Field(
        default=0,
        ge=0,
        description=(
            "Reading the prompt, added over every call recorded below. Scales with "
            "article length, minus what the cache kept."
        ),
    )
    decode_ms: int = Field(
        default=0,
        ge=0,
        description=(
            "Writing the reply, added over every call recorded below. One token at a "
            "time, so about half the prefill rate."
        ),
    )
    cached_tokens: int = Field(
        default=0,
        ge=0,
        description=(
            "Prompt tokens the runtime reused instead of reading, added over every call "
            "recorded below. input_tokens minus this is what prefill_ms actually paid "
            "for. Read it per call rather than here when the question is whether the "
            "cache answered: a second call that reuses the first call's prompt makes "
            "this figure non-zero on every item."
        ),
    )
    call_1: CallCost | None = Field(
        default=None,
        description=(
            "What the stage's first model call cost, and which call it was. Null on a "
            "payload written before 2026-09-12, which recorded a total and no split."
        ),
    )
    call_2: CallCost | None = Field(
        default=None,
        description="The same for the second call, or null where the stage made only one.",
    )

    generated_at: Timestamp
    status: SummaryStatus
    failure_code: FailureCode | None = Field(
        default=None,
        description=(
            "Typed summarize-stage failure, when the cause is already known. "
            "Older payloads omit it and still validate."
        ),
    )
    failure_detail: UntrustedLine | None = None

    @model_validator(mode="after")
    def _output_digest_is_rebuilt_not_trusted(self) -> Self:
        expected = derive_output_digest(self.summary, self.key_points, title=self.title)
        if self.output_digest != expected:
            raise ValueError("output_digest must be the digest of the published words")
        return self

    @model_validator(mode="after")
    def _cache_fits_inside_the_prompt(self) -> Self:
        # Read straight off the runtime, and the console divides by the remainder.
        if self.cached_tokens > self.input_tokens:
            raise ValueError("cached_tokens cannot exceed input_tokens")
        return self

    @model_validator(mode="after")
    def _the_flat_cost_is_the_sum_of_the_calls(self) -> Self:
        """Enforced rather than described, because every aggregate depends on it.

        A writer that records one call and forgets the other leaves a total that
        reads as the item's and is one call's, which is the defect the split
        exists to prevent. It fires here, at the moment the payload is built.
        """
        calls = [call for call in (self.call_1, self.call_2) if call is not None]
        if not calls:
            return self
        for field in COST_FIELDS:
            total = sum(getattr(call, field) for call in calls)
            if getattr(self, field) != total:
                raise ValueError(f"{field} must equal the sum over the recorded calls")
        return self

    @model_validator(mode="after")
    def _state_is_complete(self) -> Self:
        if self.status is SummaryStatus.OK:
            if not self.summary or not self.key_points:
                raise ValueError("an ok summary carries summary text and at least one key point")
            if self.failure_detail is not None:
                raise ValueError("an ok summary carries no failure_detail")
            if self.failure_code is not None:
                raise ValueError("an ok summary carries no failure_code")
        else:
            if self.failure_detail is None:
                raise ValueError("a summary that did not land must record why")
            if self.title is not None:
                raise ValueError("a summary that did not land publishes no title")
            if (
                self.failure_code is not None
                and ItemStage.SUMMARIZE not in FAILURE_CODE_STAGES[self.failure_code]
            ):
                raise ValueError("summary failure_code must belong to summarize")
        return self

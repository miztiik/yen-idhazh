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
            version="2026-09-15",
            change="failure_code may now carry no_title.",
            why="Extract gained a refusal for an item whose feed carried no headline.",
        ),
        ChangelogEntry(
            version="2026-09-13T22:00",
            change="Removed pipeline_fingerprint.",
            why="It gated a skip nothing was ever wired to, and no writer has filled it since.",
        ),
        ChangelogEntry(
            version="2026-09-13T14:20",
            change="A summary that failed on its reply records call_1 and the five cost cells.",
            why="Every gate below 'the model never answered' refuses text already paid for.",
        ),
        ChangelogEntry(
            version="2026-09-12T21:00",
            change="pipeline_fingerprint is optional and nothing sets it.",
            why="Skip-if-fingerprint-matches was never wired to a caller, so the stamp cost bytes.",
        ),
        ChangelogEntry(
            version="2026-08-21",
            change="Earlier changes are in this file's git history.",
            why="A changelog says what moved lately; git is the archive.",
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

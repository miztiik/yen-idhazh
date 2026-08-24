"""What happened to one planned item on one run.

One row per planned item per run, appended to
`state/item-health/<YYYY-MM>.csv`. The row is a census: successes and failures
share one file, because a rate needs its denominator beside its numerator.
"""

from __future__ import annotations

from collections.abc import Mapping
from enum import StrEnum
from types import MappingProxyType
from typing import Annotated, Any, ClassVar, Final, Self

from pydantic import Field, StringConstraints, model_validator

from idhazh.contracts.base import (
    ChangelogEntry,
    Contract,
    DateStamp,
    ItemId,
    RunId,
    Slug,
    Url,
    UrlKey,
)

ItemHealthDetail = Annotated[str, StringConstraints(min_length=1, max_length=200)]


class ItemStage(StrEnum):
    """The terminal stage for an item."""

    PLAN = "plan"
    FETCH = "fetch"
    EXTRACT = "extract"
    SUMMARIZE = "summarize"
    PUBLISH = "publish"


class ItemOutcome(StrEnum):
    """Whether the item reached the digest."""

    OK = "ok"
    FAILED = "failed"


class FailureCode(StrEnum):
    """Stable failure vocabulary for item-health rows."""

    NOT_ATTEMPTED = "not_attempted"
    ROBOTS_DENIED = "robots_denied"
    ROBOTS_UNREACHABLE = "robots_unreachable"
    BLOCKED_ADDRESS = "blocked_address"
    HTTP_CLIENT_ERROR = "http_client_error"
    HTTP_RATE_LIMITED = "http_rate_limited"
    HTTP_SERVER_ERROR = "http_server_error"
    NETWORK_ERROR = "network_error"
    NO_TEXT = "no_text"
    TOO_SHORT = "too_short"
    NOT_PROSE = "not_prose"
    BOILERPLATE = "boilerplate"
    PAYWALLED = "paywalled"
    UNSUPPORTED_FORM = "unsupported_form"
    MODEL_UNREACHABLE = "model_unreachable"
    OUTPUT_TRUNCATED = "output_truncated"
    BAD_SHAPE = "bad_shape"
    LENGTH_OUT_OF_RANGE = "length_out_of_range"
    UNKNOWN = "unknown"


FAILURE_CODE_STAGES: Final[Mapping[FailureCode, frozenset[ItemStage]]] = MappingProxyType(
    {
        FailureCode.NOT_ATTEMPTED: frozenset({ItemStage.PLAN}),
        FailureCode.ROBOTS_DENIED: frozenset({ItemStage.FETCH}),
        FailureCode.ROBOTS_UNREACHABLE: frozenset({ItemStage.FETCH}),
        FailureCode.BLOCKED_ADDRESS: frozenset({ItemStage.FETCH}),
        FailureCode.HTTP_CLIENT_ERROR: frozenset({ItemStage.FETCH}),
        FailureCode.HTTP_RATE_LIMITED: frozenset({ItemStage.FETCH}),
        FailureCode.HTTP_SERVER_ERROR: frozenset({ItemStage.FETCH}),
        FailureCode.NETWORK_ERROR: frozenset({ItemStage.FETCH}),
        FailureCode.NO_TEXT: frozenset({ItemStage.EXTRACT}),
        FailureCode.TOO_SHORT: frozenset({ItemStage.EXTRACT, ItemStage.PUBLISH}),
        FailureCode.NOT_PROSE: frozenset({ItemStage.EXTRACT, ItemStage.PUBLISH}),
        FailureCode.BOILERPLATE: frozenset({ItemStage.EXTRACT, ItemStage.PUBLISH}),
        FailureCode.PAYWALLED: frozenset({ItemStage.EXTRACT}),
        FailureCode.UNSUPPORTED_FORM: frozenset({ItemStage.EXTRACT}),
        FailureCode.MODEL_UNREACHABLE: frozenset({ItemStage.SUMMARIZE}),
        FailureCode.OUTPUT_TRUNCATED: frozenset({ItemStage.SUMMARIZE}),
        FailureCode.BAD_SHAPE: frozenset({ItemStage.SUMMARIZE}),
        FailureCode.LENGTH_OUT_OF_RANGE: frozenset({ItemStage.SUMMARIZE}),
        FailureCode.UNKNOWN: frozenset(ItemStage),
    }
)

SOURCE_NEUTRAL_FAILURE_CODES: Final[frozenset[FailureCode]] = frozenset(
    {
        FailureCode.NOT_ATTEMPTED,
        FailureCode.ROBOTS_DENIED,
        FailureCode.ROBOTS_UNREACHABLE,
        FailureCode.BLOCKED_ADDRESS,
        FailureCode.HTTP_RATE_LIMITED,
        FailureCode.TOO_SHORT,
        FailureCode.MODEL_UNREACHABLE,
        FailureCode.NOT_PROSE,
        FailureCode.BOILERPLATE,
        FailureCode.OUTPUT_TRUNCATED,
        FailureCode.BAD_SHAPE,
        FailureCode.LENGTH_OUT_OF_RANGE,
    }
)


class ItemHealthRow(Contract):
    """One item, one run, one terminal outcome."""

    __schema_stem__: ClassVar[str] = "item-health-row"
    __changelog__: ClassVar[tuple[ChangelogEntry, ...]] = (
        ChangelogEntry(
            version="2026-08-24T18:30",
            change=(
                "Added nullable prefill_ms, decode_ms, input_tokens, output_tokens and "
                "cached_tokens at the end of the row."
            ),
            why=(
                "This is the only ledger that carries every planned item, so it is the "
                "only place a day's model throughput can be read without keeping a "
                "runtime log. Reading the prompt and writing the summary run at "
                "different rates, and summarize_ms blends them. A rate needs its token "
                "count beside its milliseconds, so both land here. Appended at the end "
                "and nullable, so a row an earlier run wrote still reads."
            ),
        ),
        ChangelogEntry(
            version="2026-08-23T18:40",
            change="Added nullable fetch_ms, extract_ms and summarize_ms at the end of the row.",
            why=(
                "The console was charting stage timings from the scored subset, which never "
                "carried those columns. The per-item census is the row that exists for every "
                "planned item, so stage timings belong there."
            ),
        ),
        ChangelogEntry(
            version="2026-08-23T18:15",
            change=(
                "Added not_prose, boilerplate, paywalled and unsupported_form codes; "
                "allowed too_short, not_prose and boilerplate as ok-row extract signals."
            ),
            why=(
                "Extract now records shape signals separately from paywall and unsupported "
                "form drops, so the item-health ledger can group each cause without free text."
            ),
        ),
        ChangelogEntry(
            version="2026-08-23",
            change="Initial shape: one census row per planned item per run.",
            why=(
                "A run that publishes eight of seventeen items needs a durable row for "
                "all seventeen, or the next run and the console cannot explain the rate."
            ),
        ),
    )

    date: DateStamp
    run_id: RunId
    item_id: ItemId
    url_key: UrlKey
    canonical_url: Url
    vertical: Slug
    source_id: Slug
    stage: ItemStage
    outcome: ItemOutcome
    code: FailureCode | None = None
    http_status: int | None = Field(default=None, ge=100, le=599)
    source_chars: int | None = Field(default=None, ge=0)
    source_words: int | None = Field(default=None, ge=0)
    summary_words: int | None = Field(default=None, ge=0)
    detail: ItemHealthDetail | None = Field(
        default=None,
        description="Our own one-line reason, only for unknown. Never source text.",
    )
    fetch_ms: int | None = Field(default=None, ge=0)
    extract_ms: int | None = Field(default=None, ge=0)
    summarize_ms: int | None = Field(default=None, ge=0)
    prefill_ms: int | None = Field(default=None, ge=0)
    decode_ms: int | None = Field(default=None, ge=0)
    input_tokens: int | None = Field(default=None, ge=0)
    output_tokens: int | None = Field(default=None, ge=0)
    cached_tokens: int | None = Field(default=None, ge=0)

    @property
    def counts_against_source(self) -> bool:
        """Does this failure count against the source in later source-health reads?"""
        return self.code is not None and self.code not in SOURCE_NEUTRAL_FAILURE_CODES

    @model_validator(mode="after")
    def _state_is_complete(self) -> Self:
        if self.outcome is ItemOutcome.OK:
            if self.code not in {
                None,
                FailureCode.TOO_SHORT,
                FailureCode.NOT_PROSE,
                FailureCode.BOILERPLATE,
            }:
                raise ValueError("an ok item-health row carries only a recorded extract signal")
            if self.detail is not None:
                raise ValueError("an ok item-health row carries no detail")
        elif self.code is None:
            raise ValueError("a failed item-health row must carry a failure code")

        if self.code is not None and self.stage not in FAILURE_CODE_STAGES[self.code]:
            raise ValueError("failure code does not belong to item stage")
        if self.http_status is not None and self.stage is not ItemStage.FETCH:
            raise ValueError("http_status belongs only on fetch item-health rows")
        if self.code is FailureCode.UNKNOWN:
            if self.detail is None:
                raise ValueError("unknown item-health failure must carry detail")
        elif self.detail is not None:
            raise ValueError("detail belongs only to unknown item-health failures")
        return self

    @classmethod
    def csv_columns(cls) -> tuple[str, ...]:
        """One definition, so a writer and a reader cannot disagree about the row."""
        return tuple(cls.model_fields)

    def csv_row(self) -> dict[str, str]:
        """Every cell a string. An absent optional is an empty cell."""
        payload = self.model_dump(mode="json")
        return {name: "" if payload[name] is None else str(payload[name]) for name in payload}

    @classmethod
    def from_csv_row(cls, row: dict[str, str]) -> Self:
        """The inverse. An empty cell is an absent value, never the empty string."""
        payload: dict[str, Any] = {name: row.get(name, "") for name in cls.model_fields}
        optional_fields = (
            "code",
            "http_status",
            "source_chars",
            "source_words",
            "summary_words",
            "detail",
            "fetch_ms",
            "extract_ms",
            "summarize_ms",
            "prefill_ms",
            "decode_ms",
            "input_tokens",
            "output_tokens",
            "cached_tokens",
        )
        for name in optional_fields:
            if payload[name] == "":
                payload[name] = None
        return cls.model_validate(payload)

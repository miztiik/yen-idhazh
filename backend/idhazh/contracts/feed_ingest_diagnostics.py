"""Which fetch or extraction operation failed, and what was actually measured?"""

from typing import Annotated, Literal, Self

from pydantic import Field, model_validator

from idhazh.contracts.base import Model
from idhazh.contracts.feed_ingest_candidate import Count

FetchFailure = Literal[
    "http",
    "timeout",
    "unsafe-target",
    "dns",
    "network",
    "robots-denied",
    "robots-unknown",
    "body-too-large",
    "redirect-loop",
]
ExtractionFailure = Literal[
    "missing-document-root",
    "dom-depth-exceeded",
    "empty-content",
    "missing-title",
]
ExtractionSignal = Literal["contaminated", "boilerplate", "not_prose", "too_short"]


class ExtractionQuality(Model):
    """Article length and shape measured before any worker model-input cap."""

    source_word_count: Count
    word_count: Count
    corroborated_word_count: Count | None
    token_count: Count | None
    truncated: bool | None
    truncated_at_tokens: Annotated[int, Field(strict=True, ge=1)] | None
    truncation_cap_tokens: Annotated[int, Field(strict=True, ge=256)]
    too_short: bool
    not_prose: bool
    boilerplate: bool | None
    contaminated: bool | None
    failure_code: ExtractionSignal | None
    rejected: bool
    extractor_version: Annotated[str, Field(min_length=1)]
    sanitizer_version: Annotated[str, Field(min_length=1)]

    @model_validator(mode="after")
    def validate_measurements(self) -> Self:
        if self.source_word_count < self.word_count:
            raise ValueError("source_word_count counts the body before a cap")
        if (self.corroborated_word_count is None) != (self.contaminated is None):
            raise ValueError("contamination requires an independent length reading")
        if self.corroborated_word_count == 0:
            raise ValueError("an independent length reading must contain words")
        if (self.truncated is True) != (self.truncated_at_tokens is not None):
            raise ValueError("a truncation point requires an applied cut")
        expected = (
            "contaminated" if self.contaminated else
            "boilerplate" if self.boilerplate else
            "not_prose" if self.not_prose else
            "too_short" if self.too_short else None
        )
        if self.failure_code != expected:
            raise ValueError("failure_code must follow native signal precedence")
        if self.rejected and self.failure_code is None:
            raise ValueError("a quality rejection requires a measured signal")
        return self


class HarvestDiagnostics(Model):
    """Bounded machine evidence, never exception prose or fetched page content."""

    http_status: int | None = Field(default=None, strict=True, ge=100, le=599)
    robots: Literal["allowed", "denied", "unknown"] | None = None
    fetch_failure: FetchFailure | None = None
    robots_failure: FetchFailure | None = None
    robots_http_status: int | None = Field(default=None, strict=True, ge=100, le=599)
    error_code: Annotated[str, Field(max_length=64, pattern=r"^[A-Z][A-Z0-9_]*$")] | None = None
    extraction_failure: ExtractionFailure | None = None
    failure_code: (
        Literal[
            "robots_denied",
            "robots_unreachable",
            "blocked_address",
            "http_client_error",
            "http_rate_limited",
            "http_server_error",
            "network_error",
            "no_text",
            "no_title",
            "unknown",
            "contaminated",
            "boilerplate",
            "not_prose",
            "too_short",
        ]
        | None
    ) = None
    stopped_stage: Literal["fetch", "extract", "parse"] | None = None
    detail: (
        Literal[
            "http",
            "timeout",
            "unsafe-target",
            "dns",
            "network",
            "robots-denied",
            "robots-unknown",
            "body-too-large",
            "redirect-loop",
            "missing-document-root",
            "dom-depth-exceeded",
            "empty-content",
            "missing-title",
            "malformed-feed",
            "empty-feed",
            "contaminated",
            "boilerplate",
            "not_prose",
            "too_short",
        ]
        | None
    ) = None
    fetch_ms: Count | None = None
    extract_ms: Count | None = None
    warnings: list[Literal["malformed-json-ld", "semantic-dom-fallback"]] = Field(
        default=[], max_length=2,
    )
    quality: ExtractionQuality | None = None

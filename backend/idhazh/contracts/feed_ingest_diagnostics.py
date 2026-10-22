"""Which fetch or extraction operation failed, and what was actually measured?"""

from typing import Annotated, Literal

from pydantic import Field

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
        ]
        | None
    ) = None
    fetch_ms: Count | None = None
    extract_ms: Count | None = None
    warnings: list[Literal["malformed-json-ld"]] = Field(default=[], max_length=1)

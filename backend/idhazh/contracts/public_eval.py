"""The browser-safe projection of the score ledger.

`state/scores/<YYYY-MM>.csv` is the ledger - one row per scored item per attempt
- and it carries three cells a reader must never receive. This is the narrow
shape that does cross, written to `frontend/public/scores/<YYYY-MM>.csv` and
fetched a month at a time as the console pans its viewport.

It is the same trade `public_telemetry.py` makes, for the same reason, against a
different ledger: the console draws faithfulness, coverage, compression and the
confidence bands off these rows, and every one of those is a measurement of our
own work. The article's address and the article's headline are not, so they stop
here (Guardrail #11).

**`version` is a field and never a cell.** The published header is read by
position, the way `parseTelemetryCsv` reads the telemetry header, so one more
name at position zero would shift every column the console draws. The shape's
own stamp lives in `schemas/public-eval.schema.json`. A new cell is appended at
the end, never inserted.
"""

from __future__ import annotations

from typing import Any, ClassVar, Final, Self

from pydantic import Field

from idhazh.contracts.base import (
    ChangelogEntry,
    Contract,
    DateStamp,
    RunId,
    Sha256,
    Slug,
    Timestamp,
)
from idhazh.contracts.eval_row import ConfidenceBand, Score
from idhazh.contracts.public_telemetry import PublicItemKey

#: The three ledger cells that may never reach a browser.
#:
#: `source_url` is the article's address and `url_key` is that address hashed, so
#: both identify the page rather than the measurement. `title` is `UntrustedLine`
#: on `EvalRow` - fetched text, which never reaches a reader unlabelled
#: (Guardrail #11) - and the published day payload already carries our own title for
#: every item a reader can see. None of the three is needed to draw a score, a
#: band or a rate, which is the whole of what the console does with this ledger.
FORBIDDEN_COLUMNS: Final[frozenset[str]] = frozenset({"url_key", "source_url", "title"})


class PublicEvalRow(Contract):
    """One scored attempt, as the console is allowed to read it."""

    __schema_stem__: ClassVar[str] = "public-eval"
    __changelog__: ClassVar[tuple[ChangelogEntry, ...]] = (
        ChangelogEntry(
            version="2026-09-09",
            change=(
                "Initial shape: the score ledger's own measurements, typed, with "
                "url_key, source_url and title refused at import."
            ),
            why=(
                "The console reads state/scores/ at build time and serialises the "
                "result into its document, so the ledger's shape crossed to a reader "
                "as inlined JSON with no contract, no version stamp and no changelog "
                "while the telemetry projection beside it has all three (Guardrail #3). "
                "Naming the shape before a producer exists is what stops the producer, "
                "the consumer and the gates each inventing their own list. item_id is "
                "carried as an opaque key on the same terms PublicTelemetryRow carries "
                "it: identity is minted by the ledger writer, and a published shard has "
                "no writer left to re-mint it if that grammar moves."
            ),
        ),
    )

    date: DateStamp
    run_id: RunId
    item_id: PublicItemKey
    vertical: Slug
    model_id: Slug
    attempt: int = Field(ge=1)

    hhem: Score = Field(ge=0.0, le=1.0)
    hhem_full: Score = Field(ge=0.0, le=1.0)
    hhem_delta: Score
    truncation_flagged: bool
    coverage: Score = Field(ge=0.0, le=1.0)
    compression: Score = Field(ge=0.0)
    extractiveness: Score = Field(ge=0.0, le=1.0)
    verbatim_run: Score = Field(default=0.0, ge=0.0, le=1.0)
    unsupported_numbers: int = Field(default=0, ge=0)
    hedge_dropped: bool = False
    extraction_suspect: bool = False
    band: ConfidenceBand

    source_word_count: int | None = Field(default=None, ge=0)
    source_seen_word_count: int = Field(default=0, ge=0)
    summary_word_count: int = Field(ge=0)
    pipeline_fingerprint: Sha256
    output_digest: Sha256
    determinism_violation: bool = False
    scorer_version: str = Field(min_length=1)
    scored_at: Timestamp
    score_ms: int = Field(default=0, ge=0)

    evidential_density: Score | None = Field(default=None, ge=0.0)
    speculative_density: Score | None = Field(default=None, ge=0.0)
    self_repetition: Score | None = Field(default=None, ge=0.0, le=1.0)
    source_digest: Sha256 | None = None
    new_fact_rate: Score | None = Field(default=None, ge=0.0, le=1.0)

    @classmethod
    def csv_columns(cls) -> tuple[str, ...]:
        """The published header. `version` is a field of the shape, not a cell."""
        return tuple(name for name in cls.model_fields if name != "version")

    def csv_row(self) -> dict[str, str]:
        """Every cell a string. An absent optional is an empty cell."""
        payload = self.model_dump(mode="json")
        return {
            name: "" if payload[name] is None else str(payload[name])
            for name in self.csv_columns()
        }

    @classmethod
    def from_csv_row(cls, row: dict[str, str]) -> Self:
        """The inverse. An empty cell is an absent value, never the empty string."""
        payload: dict[str, Any] = {name: row.get(name, "") for name in cls.csv_columns()}
        for name, field in cls.model_fields.items():
            if name in payload and field.default is None and payload[name] == "":
                payload[name] = None
        return cls.model_validate(payload)


if FORBIDDEN_COLUMNS & set(PublicEvalRow.model_fields):
    raise AssertionError(
        "a score-ledger field a reader may never receive is on the published "
        f"projection: {sorted(FORBIDDEN_COLUMNS & set(PublicEvalRow.model_fields))}"
    )

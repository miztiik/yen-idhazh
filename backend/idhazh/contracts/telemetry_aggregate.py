"""One day of one pipeline stage, after the full-grain rows are gone.

`state/item-health/<YYYY-MM>.csv` is the census: one row per planned item per
run, and the denominator under every rate this project publishes. It is also the
fastest-growing thing under `state/` - measured 2026-08-30, 1,270,452 bytes for
six published days, which is 211,742 bytes a day and about 77 MB a year.

`observability.keep_months` decides how long that stays readable item by item.
Past it, a month is folded into this shape and the full-grain shard is deleted.
One row per `(date, stage)` is five rows a day, so a year of history costs
kilobytes rather than megabytes and a year-over-year comparison stays possible -
which deleting the shard outright would make unanswerable, and Rule #10 would
then forbid citing last year's number at all.

**The fold changes the grain and never the answer.** Counts are of rows as the
shard held them, with no deduplication: the committed ledger really does carry
repeated `(date, run_id, item_id)` keys where a run executed twice, so a fold
that quietly collapsed them would make the aggregate disagree with the file it
replaced - and nobody could ever tell which of the two was right. Deduplication
is a judgement, and a judgement taken at fold time can never be undone.
"""

from __future__ import annotations

import math
from typing import Any, ClassVar, Self

from pydantic import Field, model_validator

from idhazh.contracts.base import ChangelogEntry, Contract, DateStamp
from idhazh.contracts.item_health import ItemStage


def percentile(sorted_values: list[int], quantile: float) -> int:
    """Nearest-rank percentile over an already-sorted, non-empty list.

    Nearest rank rather than interpolation, because the result has to be an
    integer a reader can compare against a full-grain row that really occurred.
    An interpolated p90 is a millisecond count no item ever took, and a fold that
    invents a value cannot be checked against the shard it replaced.
    """
    if not sorted_values:
        raise ValueError("a percentile needs at least one value")
    rank = max(1, math.ceil(quantile * len(sorted_values)))
    return sorted_values[rank - 1]


class TelemetryAggregateRow(Contract):
    """One `(date, stage)` pair, summarised from the item-health shard."""

    __schema_stem__: ClassVar[str] = "telemetry-aggregate-row"
    __changelog__: ClassVar[tuple[ChangelogEntry, ...]] = (
        ChangelogEntry(
            version="2026-08-30T20:00",
            change="Initial shape: one row per (date, stage) folded from an item-health shard.",
            why=(
                "The item-health census grows at about 212,000 bytes a published day and "
                "nothing bounded it. Deleting an old shard outright would answer that and "
                "cost every year-over-year comparison, so a month past "
                "observability.keep_months is folded to this shape first. Five rows a day "
                "keeps the counts and the timing distribution and drops only the per-item "
                "detail, which is what the console's failure list offers and no rate needs."
            ),
        ),
    )

    date: DateStamp
    stage: ItemStage
    items: int = Field(
        ge=1,
        description=(
            "Rows the shard held for this date and stage, counted as they were "
            "written. A run that executed twice under one run id really does leave two "
            "rows for one item, and the fold reproduces that rather than deciding for "
            "a later reader which of them to believe."
        ),
    )
    failed: int = Field(
        ge=0,
        description="Of those rows, the ones whose outcome was not ok. The numerator.",
    )
    timed: int = Field(
        ge=0,
        description=(
            "Of those rows, the ones that recorded any milliseconds at all. The "
            "denominator the four figures below are taken over, which is never the row "
            "count: a plan-stage row times nothing, and a row written before the timing "
            "columns existed times nothing either."
        ),
    )
    p50_ms: int | None = Field(
        default=None,
        ge=0,
        description=(
            "Nearest-rank median of fetch, extract and summarize milliseconds added up "
            "per row. Empty when no row at this stage recorded any - empty is not zero."
        ),
    )
    p90_ms: int | None = Field(default=None, ge=0, description="Nearest-rank 90th percentile.")
    max_ms: int | None = Field(default=None, ge=0, description="The slowest row of the group.")
    sum_ms: int | None = Field(
        default=None,
        ge=0,
        description=(
            "Every timed row added together, so a day's total stage time survives the "
            "fold. A percentile cannot be re-added into a total; this can."
        ),
    )

    @model_validator(mode="after")
    def _the_parts_fit_the_whole(self) -> Self:
        if self.failed > self.items:
            raise ValueError("more failures than rows")
        if self.timed > self.items:
            raise ValueError("more timed rows than rows")
        timing = (self.p50_ms, self.p90_ms, self.max_ms, self.sum_ms)
        if self.timed == 0 and any(value is not None for value in timing):
            raise ValueError("a group that timed nothing carries no timing figures")
        if self.timed > 0 and any(value is None for value in timing):
            raise ValueError("a group that timed something carries all four timing figures")
        if self.timed > 0:
            assert self.p50_ms is not None and self.p90_ms is not None
            assert self.max_ms is not None and self.sum_ms is not None
            if not self.p50_ms <= self.p90_ms <= self.max_ms:
                raise ValueError("the percentiles must not run past the maximum")
            if self.sum_ms < self.max_ms:
                raise ValueError("the total must not be smaller than its largest part")
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
        for name, field in cls.model_fields.items():
            if field.default is None and payload[name] == "":
                payload[name] = None
        return cls.model_validate(payload)

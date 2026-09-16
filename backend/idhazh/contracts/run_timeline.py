"""One item's place on the run's clock (`frontend/public/run-timeline/`).

The console can say what a run cost and what each stage cost. It cannot say
**where the time went, item by item, across one run** - which item started late,
which one ran long, and how much of a run's wall clock is not inside any step
anybody named. This row is that question written as a shape, and it lands before
any producer fills a column so the writers produce what the chart reads rather
than a shape the chart has to migrate (Guardrail #3).

## A row is one item

Not one stage and not one span. The chart's y axis is items, so the row's key is
the item and every column on it is about that one item. A row per stage cannot
place an item, and a row per span cannot either - `SpanRollupRow` is folded per
shard and per span name, so it knows how long fetching took and not which
article was being fetched.

## The clock is an offset, never a timestamp

`start_offset_ms` is milliseconds from the run's own start, so an item that
waited forty seconds for a worker sits forty seconds to the right and the wait is
the thing a reader sees first. A wall-clock timestamp would need the reader to
subtract, and a category axis - one column an item, evenly spaced - would hide
the queue entirely, which is the one thing this chart exists to show.

## Eight named steps, in the order they happen

`plan`, `fetch`, `extract`, the label call, the summary call, the visual plan,
`score`, `publish`. Each carries its own duration and each is optional: an item
that died at fetch carries `fetch_ms` and seven nulls, and it still draws.

**Six of the eight keep the name a ledger already gave them** - `fetch_ms`,
`extract_ms`, `label_ms`, `summary_ms` and `visual_plan_ms` are what
`ItemHealthRow` spells, `score_ms` is what `EvalRow` spells. `plan_ms` and
`publish_ms` are new because no ledger times either step yet. One vocabulary
across the instrument is worth more than a shorter name here, because a reader
comparing a bar against the census is comparing two spellings of one number the
moment the names come apart.

## Two numbers no ledger holds, and six that are re-filed on purpose

`start_offset_ms` and `residual_ms` are new. The eight durations are the same
numbers the census keeps, re-filed against a clock, and that is deliberate rather
than an oversight: a chart cannot join five ledgers at fetch time, and a
projection that cuts named cells out of a wider row is what every other console
payload already is. Nothing here is a fourth account of a measurement - it is one
account, filed twice, with the census as the source.

## The residual is its own column and is never folded into a neighbour

`residual_ms` is the item's total minus the eight named steps. It gets a column
of its own because a step that absorbed the leftover reads as slower than it was,
and a reader cannot tell the overhead from the work. `SpanRollupRow` made this
ruling once already for the shard; this is the same ruling for the item.

**It is signed, for the reason `ItemHealthRow.stage_gap_ms` is signed.** Two of
the eight steps genuinely overlap: the visual plan is decoded inside the
summarize-and-plan call, so `visual_plan_ms` is apportioned out of `summary_ms`
rather than timed beside it, and adding the two counts part of the call twice. A
negative residual says exactly that - two steps overlapped, or two clocks
disagreed - and clamping it to zero would hide the only signal that says so.

**The subtraction happens here and nowhere else.** A row that omits
`residual_ms` gets it filled from its own columns, and a row that supplies one
the arithmetic does not agree with is refused. Two subtractions in two modules
is how a chart and a ledger start reporting different overheads for one item.

## One shape, whichever tree it lands in

Nothing on this row identifies a page. No address, no `url_key`, no title, no
fetched text - only an item id the pipeline minted, a clock and a set of
durations of our own work. So there is nothing to redact and no second
`public-run-timeline` shape to declare, the way `span-rollup-row`, `day-metrics`
and `runtime-counters-row` are published whole
(`docs/architecture/publishing/console-payloads.md`). Where the rows land - a
published mirror alone, or a committed ledger projected into one - is decided by
the row that writes them, and it is the same columns either way.

## What this shape cannot settle

**Whether the chart is readable.** How the eight steps are coloured, whether the
residual drawn hollow is legible beside them, how many items fit on one screen
and what happens to a negative residual are all questions about a drawing, and a
drawing is not a contract. They are settled where the chart is built.
"""

from __future__ import annotations

from typing import Any, ClassVar, Final, Self

from pydantic import Field, model_validator

from idhazh.contracts.base import ChangelogEntry, Contract, DateStamp, ItemId, RunId

#: The eight steps a bar is drawn from, in the order the pipeline runs them. The
#: order is the declaration order of the columns below and the two are held equal
#: by a test, so a step added to one and not the other cannot ship.
STEP_COLUMNS: Final[tuple[str, ...]] = (
    "plan_ms",
    "fetch_ms",
    "extract_ms",
    "label_ms",
    "summary_ms",
    "visual_plan_ms",
    "score_ms",
    "publish_ms",
)


def _whole_ms(value: Any) -> int | None:
    """A whole millisecond count, or None where the cell holds no number.

    A CSV cell arrives as a string and an absent one as the empty string, so the
    residual's arithmetic has to read both forms. Anything that is not a whole
    number reads as absent here and is left for the field's own validator to
    refuse, which keeps the error the reader sees pointing at the cell that is
    wrong rather than at a subtraction that could not be done.
    """
    if value is None or isinstance(value, bool) or value == "":
        return None
    if isinstance(value, int):
        return value
    if isinstance(value, str):
        try:
            return int(value)
        except ValueError:
            return None
    return None


class RunTimelineRow(Contract):
    """One item's bar: where it starts on the run's clock, and what it spent."""

    __schema_stem__: ClassVar[str] = "run-timeline-row"
    __changelog__: ClassVar[tuple[ChangelogEntry, ...]] = (
        ChangelogEntry(
            version="2026-09-16",
            change="Steps 4 and 5 are a stopwatch around each request, not the server's sum.",
            why="It follows item-health-row, where both columns are written.",
        ),
        ChangelogEntry(
            version="2026-09-15",
            change="Initial shape: one row an item, an offset, eight steps and the residual.",
            why="Contracts before logic - the writers and the chart need one fixed shape first.",
        ),
    )

    date: DateStamp
    run_id: RunId
    shard: int = Field(
        ge=0,
        description=(
            "Which work shard read and summarised this item. Two bars overlapping on "
            "the clock is correct exactly when they sit on different shards, and "
            "without this column a reader cannot tell an overlap from a contradiction. "
            "The plan and publish steps are not sharded; this names the shard that did "
            "the middle."
        ),
    )
    item_id: ItemId = Field(
        description=(
            "The item this bar is about. An item no shard was given produces no row "
            "rather than an empty one, so an absent row reads as never worked."
        )
    )
    start_offset_ms: int = Field(
        ge=0,
        description=(
            "Milliseconds from the run's start to the moment this item's own work "
            "began. An offset and not a timestamp: the reader is asking where on the "
            "run's clock the bar sits, and an item that queued forty seconds has to "
            "sit forty seconds to the right for the queue to be visible at all."
        ),
    )
    item_total_ms: int = Field(
        ge=0,
        description=(
            "How long the bar is - what the item cost once its wait is taken out, "
            "which is the same number `ItemHealthRow.item_total_ms` holds and spelled "
            "the same way. The wait is `start_offset_ms` and is drawn as position "
            "rather than length, so counting it here would draw it twice."
        ),
    )
    plan_ms: int | None = Field(
        default=None,
        ge=0,
        description="Step 1. What choosing this item cost. Null where nothing timed it.",
    )
    fetch_ms: int | None = Field(
        default=None,
        ge=0,
        description="Step 2. Reading the page, as `ItemHealthRow.fetch_ms` spells it.",
    )
    extract_ms: int | None = Field(
        default=None,
        ge=0,
        description="Step 3. Taking the article out of the page, as the census spells it.",
    )
    label_ms: int | None = Field(
        default=None,
        ge=0,
        description="Step 4. The label call, on the stopwatch the census spells `label_ms`.",
    )
    summary_ms: int | None = Field(
        default=None,
        ge=0,
        description=(
            "Step 5. The summarize-and-plan call, on the stopwatch the census spells "
            "`summary_ms`."
        ),
    )
    visual_plan_ms: int | None = Field(
        default=None,
        ge=0,
        description=(
            "Step 6. What the visual plan cost. The plan is decoded inside the call "
            "above, so this is apportioned out of `summary_ms` rather than timed "
            "beside it - which is why the residual is signed."
        ),
    )
    score_ms: int | None = Field(
        default=None,
        ge=0,
        description="Step 7. The model-free scorers, as `EvalRow.score_ms` spells it.",
    )
    publish_ms: int | None = Field(
        default=None,
        ge=0,
        description="Step 8. What placing this item in the day cost. Null where nothing timed it.",
    )
    residual_ms: int = Field(
        description=(
            "`item_total_ms` minus the eight named steps: the part of the bar no step "
            "accounts for. Its own column because a step that absorbed the leftover "
            "reads as slower than it was. Signed on purpose - a negative value means "
            "two of the eight overlapped or two clocks disagreed, and the apportioned "
            "visual plan is a known overlap, so clamping it to zero would hide the one "
            "signal that says so. Derived here rather than supplied: a row that omits "
            "it gets it filled, and a row that disagrees with the arithmetic is "
            "refused."
        )
    )

    @model_validator(mode="before")
    @classmethod
    def _fill_a_residual_nobody_wrote(cls, data: Any) -> Any:
        """Do the subtraction for a writer that did not, and only for that writer.

        A supplied value is left exactly as it arrived, so the validator below is
        what refuses a wrong one. Filling and then checking in one place would
        mean the check could never fail.
        """
        if not isinstance(data, dict):
            return data
        supplied = data.get("residual_ms")
        if supplied is not None and supplied != "":
            return data
        total = _whole_ms(data.get("item_total_ms"))
        if total is None:
            return data
        steps = [_whole_ms(data.get(name)) for name in STEP_COLUMNS]
        return {**data, "residual_ms": total - sum(step for step in steps if step is not None)}

    @model_validator(mode="after")
    def _the_residual_is_this_rows_own_subtraction(self) -> Self:
        """One subtraction, in one place, so a chart and a ledger cannot disagree."""
        expected = self.item_total_ms - self.named_total_ms()
        if self.residual_ms != expected:
            raise ValueError(
                f"residual_ms is item_total_ms minus the eight named steps, which is "
                f"{expected} for this row; got {self.residual_ms}"
            )
        return self

    def steps(self) -> dict[str, int | None]:
        """What each of the eight named steps cost, in the order they happen."""
        return {name: getattr(self, name) for name in STEP_COLUMNS}

    def named_total_ms(self) -> int:
        """The eight steps added together, an absent step counted as nothing.

        Absent means nothing timed the step, never that the step took no time, and
        the two are the same number here for one reason: an untimed step cannot be
        subtracted, so whatever it cost lands in the residual where a reader can
        see there is time nobody accounted for.
        """
        return sum(value for value in self.steps().values() if value is not None)

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

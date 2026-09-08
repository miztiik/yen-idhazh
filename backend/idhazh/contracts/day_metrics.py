"""What a run wrote once about one published day, for the console to read back.

One file per published day, at `state/day-metrics/<YYYY>/<MM>/<DD>.json`,
rewritten when that day is corrected. The path nests by year and month to mirror
the published digest-day layout (`frontend/public/digest/<YYYY>/<MM>/<DD>/`), so
one month's folder holds about 31 files rather than one directory that grows
with every published day. It is never a running total: a total needs a
decrement path for every correction, and a missed decrement is silent and
permanent (owner, 2026-09-06). So this record is always the whole truth about
the day as of the run that wrote it, and a later correction rewrites it whole.

The console today rebuilds these figures by walking every committed score row,
item-health row, feed-health row and published day (research findings 61, 62,
63, 67, 68, 70, 73, 74, 75). That walk gets slower every published day for an
answer that never changes once the day is frozen (CLAUDE.md Rule #12). This
record is the answer, written once by the producer that already holds the data.

**Additive against non-additive is the spine of this shape (Andre).** A figure a
reader may add across days is stored as the number itself - a count, a sum. A
figure a reader may NOT add across days - a median, a distinct count, a ranked
list - is stored as the day's own value plus whatever lets the reader combine
days in a defined way, and its field doc says which. A percentile cannot be
re-added into a window's percentile; a per-day count and sum beside it can be
summed and divided into the window's mean. A distinct count double-counts across
days; the per-source rows beside it can be merged without double-counting.

**No producer and no reader ship with this contract (Fowler).** The model, its
generated schema and its round-trip test land first; the run that writes the
file and the reducers that read it come later, against the shape the owner signs
off here.

Every path this record could name is relative and POSIX (CLAUDE.md section 2),
and it carries facts about a day and never a line of article text (section 0a).
"""

from __future__ import annotations

from typing import Annotated, ClassVar, Self

from pydantic import Field, StringConstraints, model_validator

from idhazh.contracts.base import (
    ChangelogEntry,
    Contract,
    DateStamp,
    Model,
    Sha256,
    Slug,
)
from idhazh.contracts.item_health import ItemStage

# An eval-row column name is snake_case (`hhem_full`, `score_ms`), so it is not a
# kebab-case Slug. This is the identifier the reducer joins an instrument on.
EvalColumn = Annotated[str, StringConstraints(pattern=r"^[a-z0-9]+(?:_[a-z0-9]+)*$")]

# The measured eval-row columns this record aggregates one at a time in
# `instruments`, matching the frontend's `DRAWN_BY` map. Recorded here so the
# model documents which columns row 23 pairs against; the set is not validated,
# so a column added to EvalRow later gains an instrument without a schema break.
INSTRUMENT_COLUMNS: frozenset[str] = frozenset(
    {
        "hhem",
        "hhem_full",
        "hhem_delta",
        "coverage",
        "compression",
        "extractiveness",
        "verbatim_run",
        "self_repetition",
        "evidential_density",
        "speculative_density",
        "new_fact_rate",
        "source_word_count",
        "source_seen_word_count",
        "summary_word_count",
        "score_ms",
    }
)


class DayBands(Model):
    """How the day's published items split across the confidence bands.

    Additive. Every published item carries exactly one band, so the three counts
    partition the published set and a window's band counts are the daily counts
    added up.
    """

    high: int = Field(ge=0, description="Items the checker did not doubt.")
    medium: int = Field(ge=0)
    low: int = Field(ge=0)


class DayReasons(Model):
    """Why each doubted item did not reach the top band.

    Additive. A `high` item has no reason; every `medium` or `low` item falls
    into exactly one bucket here, so the six counts partition the doubted set.
    `unattributed` is a doubted item the checker recorded no reason for - a real
    category the Model page counts separately, not the same fact as `not_scored`
    (which is a recorded reason meaning no faithfulness score exists).
    """

    unsupported_number: int = Field(ge=0)
    not_scored: int = Field(ge=0)
    lead_missing: int = Field(ge=0)
    hedge_dropped: int = Field(ge=0)
    faithfulness: int = Field(ge=0)
    unattributed: int = Field(
        ge=0,
        description="Doubted, with no band_reason on the published item. Never source text.",
    )

    def total(self) -> int:
        return (
            self.unsupported_number
            + self.not_scored
            + self.lead_missing
            + self.hedge_dropped
            + self.faithfulness
            + self.unattributed
        )


class DayThroughput(Model):
    """The model's token clock for the day, so a rate survives without a runtime log.

    Every field is additive: sum the milliseconds and the token counts over a
    window and divide once for the window's prefill and decode rates. Reading the
    prompt and writing the summary run at different rates, so their milliseconds
    are kept apart. Null on the day facts when no item timed a token.
    """

    items: int = Field(ge=0, description="Items that recorded any token count. The denominator.")
    prefill_ms: int = Field(ge=0, description="Milliseconds reading prompts, added over the day.")
    decode_ms: int = Field(ge=0, description="Milliseconds writing summaries, added over the day.")
    input_tokens: int = Field(ge=0)
    output_tokens: int = Field(ge=0)
    cached_tokens: int = Field(ge=0)


class DayStageTiming(Model):
    """One pipeline stage's wall-clock over the day's items.

    `timed` and `sum_ms` are additive - a window's total stage time is the daily
    totals added up, and a mean is `sum_ms` over `timed`. The three percentiles
    are the day's own and are NOT additive: a median of daily medians is not the
    window's median (the Model page's own caveat). A reader shows a daily
    percentile or recomputes an exact one from a value population this record
    does not carry. Empty percentiles are not zero: a stage that timed nothing
    carries none of the four figures.
    """

    stage: ItemStage
    timed: int = Field(
        ge=0, description="Items that recorded milliseconds at this stage. Additive."
    )
    sum_ms: int | None = Field(
        default=None, ge=0, description="Every timed item added up. Additive."
    )
    p50_ms: int | None = Field(default=None, ge=0, description="The day's median. Not additive.")
    p90_ms: int | None = Field(
        default=None, ge=0, description="The day's 90th percentile. Not additive."
    )
    max_ms: int | None = Field(
        default=None, ge=0, description="The day's slowest item. Not additive."
    )

    @model_validator(mode="after")
    def _timing_is_all_or_nothing(self) -> Self:
        figures = (self.sum_ms, self.p50_ms, self.p90_ms, self.max_ms)
        if self.timed == 0 and any(value is not None for value in figures):
            raise ValueError("a stage that timed nothing carries no timing figures")
        if self.timed > 0 and any(value is None for value in figures):
            raise ValueError("a stage that timed something carries all four timing figures")
        if self.timed > 0:
            assert self.sum_ms is not None and self.p50_ms is not None
            assert self.p90_ms is not None and self.max_ms is not None
            if not self.p50_ms <= self.p90_ms <= self.max_ms:
                raise ValueError("the percentiles must not run past the maximum")
            if self.sum_ms < self.max_ms:
                raise ValueError("the total must not be smaller than its largest part")
        return self


class DayDistribution(Model):
    """One numeric instrument aggregated over the day, split by how it combines.

    `count` and `total` are additive: sum both over a window and divide once for
    the window's mean, which is a mean over items and never a mean of daily
    means. The quartiles and the range are the day's own and are NOT additive - a
    reader shows a daily quartile or recomputes an exact one from a value
    population this record does not carry. A day that measured nothing carries the
    count 0, the total 0.0 and no order statistic; empty is not zero.
    """

    count: int = Field(ge=0, description="Items that carried a value. Additive.")
    total: float = Field(description="The values added up. Additive.")
    p25: float | None = Field(default=None, description="The day's lower quartile. Not additive.")
    p50: float | None = Field(default=None, description="The day's median. Not additive.")
    p75: float | None = Field(default=None, description="The day's upper quartile. Not additive.")
    minimum: float | None = Field(
        default=None, description="The day's smallest value. Not additive."
    )
    maximum: float | None = Field(
        default=None, description="The day's largest value. Not additive."
    )

    @model_validator(mode="after")
    def _statistics_are_all_or_nothing(self) -> Self:
        order = (self.p25, self.p50, self.p75, self.minimum, self.maximum)
        if self.count == 0:
            if self.total != 0.0 or any(value is not None for value in order):
                raise ValueError("a distribution over nothing carries no total and no statistics")
            return self
        if any(value is None for value in order):
            raise ValueError("a distribution over something carries every order statistic")
        assert self.minimum is not None and self.p25 is not None and self.p50 is not None
        assert self.p75 is not None and self.maximum is not None
        if not self.minimum <= self.p25 <= self.p50 <= self.p75 <= self.maximum:
            raise ValueError("the quartiles must not run outside the range")
        return self


class DayInstrument(Model):
    """One measured eval-row column, aggregated over the day.

    `column` names the eval-row column (an entry from `INSTRUMENT_COLUMNS`); the
    reducer joins on it. `stat` carries the aggregate, additive and non-additive
    parts kept apart by `DayDistribution`.
    """

    column: EvalColumn
    stat: DayDistribution


class DaySource(Model):
    """One source's day, counted so the reader can rank and combine without a re-walk.

    Every count is additive within a source: sum a source's `published` over a
    window for its window total. The reader combines days by keying on
    `source_id`, then re-ranks - the ranking itself is non-additive, which is why
    the whole per-source list is stored rather than a daily top list.
    """

    source_id: Slug
    published: int = Field(ge=0, description="Items this source contributed to the day.")
    doubted: int = Field(ge=0, description="Of those, the ones not in the top band.")
    truncated: int = Field(ge=0, description="Of those, the ones extract cut at the cap.")

    @model_validator(mode="after")
    def _the_parts_fit_the_source(self) -> Self:
        if self.doubted > self.published:
            raise ValueError("a source cannot doubt more items than it published")
        if self.truncated > self.published:
            raise ValueError("a source cannot cut more items than it published")
        return self


class DayExtraction(Model):
    """What the candidate pass found on the day, and what the page drew from it.

    Every count is additive across days, so a window is a sum and never a re-walk.
    The two rates a reader wants are not stored, because a rate is not additive:
    `idhazh.evals.metrics` derives both from these counts, and the console does
    the same arithmetic on the same cells.

    **Three classes and not five.** `comparative` and `processual` are claims
    about how an article is written rather than about its numbers, so they have
    no query yet and land with the diagram plan. `unclassified` is that gap
    stated plainly rather than folded into `narrative`, which would report an
    article carrying two figures as one carrying none.
    """

    items: int = Field(
        ge=0,
        description=(
            "Planned items whose article carried text, so the pass ran on them. The "
            "denominator of the integrity rate, and never the published set."
        ),
    )
    span_integrity_pass: int = Field(
        ge=0,
        description="Of those, the ones where every element span cut its own characters.",
    )
    elements_found: int = Field(
        ge=0,
        description=(
            "Tier 1 elements the pass kept, added over the day. The extractor's own "
            "signal: it falls when the patterns stop matching, whatever the planner does."
        ),
    )
    chartable: int = Field(ge=0, description="Items whose numbers could have made a chart.")
    narrative: int = Field(ge=0, description="Items stating no quantity at all.")
    unclassified: int = Field(
        ge=0, description="Items with quantities but no unit shared widely enough."
    )
    chartable_published: int = Field(
        ge=0,
        description=(
            "Chartable items that reached the day's published set. The denominator of "
            "the unused rate: an item that never published cannot carry a chart, and "
            "counting it would blame the planner for a fetch that failed."
        ),
    )
    chartable_charted: int = Field(
        ge=0, description="Of those, the ones a reader can see a rendered chart on."
    )

    @model_validator(mode="after")
    def _the_parts_fit_the_day(self) -> Self:
        if self.span_integrity_pass > self.items:
            raise ValueError("more spans held than there were items to hold them")
        if self.chartable + self.narrative + self.unclassified > self.span_integrity_pass:
            raise ValueError("an item was classified without its spans being re-sliced first")
        if self.chartable_published > self.chartable:
            raise ValueError("more chartable items published than were chartable")
        if self.chartable_charted > self.chartable_published:
            raise ValueError("a chart was drawn for a chartable item the day did not publish")
        return self


class DayMetrics(Contract):
    """Everything a run settled about one published day, for a later reducer to read."""

    __schema_stem__: ClassVar[str] = "day-metrics"
    __changelog__: ClassVar[tuple[ChangelogEntry, ...]] = (
        ChangelogEntry(
            version="2026-09-08T21:00",
            change="Added the nullable extraction block.",
            why=(
                "Nothing said whether an article the planner drew nothing for had "
                "anything to draw, so a fall in published charts read the same whether "
                "the planner stopped choosing them or the extractor stopped finding "
                "numbers. The block is the day's join of the item-health census, which "
                "carries the class, against the published day, which carries the chart - "
                "both bounded by the day and neither by the archive (Rule #12). Nullable, "
                "because a record an earlier run wrote carries no such block and the "
                "console reads it leniently rather than dropping the whole day."
            ),
        ),
        ChangelogEntry(
            version="2026-09-07",
            change="Initial shape: one record per published day, additive against non-additive.",
            why=(
                "The console rebuilt every per-day figure by walking the whole committed "
                "history on every build (research findings 61-75), a cost that rose with "
                "each published day for an answer that never changed once the day was "
                "frozen (Rule #12). This record carries those figures, written once by the "
                "producer that already holds the data. It stores a total only where a "
                "reader may add it across days and never as a running counter, because a "
                "correction to a counter needs a decrement path and a missed decrement is "
                "silent (owner, 2026-09-06); a correction rewrites this whole record "
                "instead. A non-additive figure carries the day's own value plus what a "
                "reader needs to combine days in a defined way (Andre)."
            ),
        ),
    )

    date: DateStamp

    revision: int = Field(
        ge=1,
        description=(
            "The ordinal of the newest run that published this day - DigestDay.runs[-1].n, "
            "the same number introduced_by_run counts up. A record whose revision is behind "
            "the day's own newest run is stale and must be rewritten (Fowler)."
        ),
    )
    runs: int = Field(ge=1, description="Runs that published this day. Additive.")

    model_id: Slug = Field(
        description=(
            "The model that wrote the day's summaries. Not additive - a per-day attribute a "
            "reader compares against the next day to find a model change (finding 70)."
        )
    )
    pipeline_fingerprint: Sha256 = Field(
        description=(
            "The digest of the declared settings the day ran under, as EvalRow carries it. "
            "Not additive - the boundary a model-change reading is drawn on (finding 70)."
        )
    )

    items_published: int = Field(ge=0, description="Items in the day's published set. Additive.")
    items_planned: int = Field(ge=0, description="Items the day's runs planned. Additive.")
    items_failed: int = Field(
        ge=0, description="Planned items that never reached the digest. Additive."
    )
    visuals_rendered: int = Field(ge=0, description="Visuals that rendered on the day. Additive.")
    items_truncated: int = Field(
        ge=0,
        description="Published items extract cut at the truncation cap (finding 68). Additive.",
    )
    summaries_scored: int = Field(
        ge=0,
        description="Published items the checker gave a faithfulness score. Additive.",
    )
    determinism_violations: int = Field(
        ge=0,
        description="Scored items whose identical inputs produced different words. Additive.",
    )
    extraction_suspect: int = Field(
        ge=0,
        description="Scored items whose source read like page furniture. Additive.",
    )

    sources_present: int = Field(
        ge=0,
        description=(
            "Distinct sources that contributed a published item. Not additive - two days "
            "may share a source, so a reader combines the `sources` list rather than adding "
            "this across days. Equal to the length of `sources`."
        ),
    )
    addresses_considered: int | None = Field(
        default=None,
        ge=0,
        description=(
            "Distinct addresses the feeds offered the day, before what it had published or "
            "failed on (finding 62). Not additive - two days may repeat an address, so a "
            "reader treats a sum as an upper bound. Null on a day that recorded none."
        ),
    )

    bands: DayBands
    reasons: DayReasons
    throughput: DayThroughput | None = Field(
        default=None,
        description="The day's token clock, or null when no item timed a token. Additive parts.",
    )
    stage_timing: list[DayStageTiming] = Field(
        default_factory=list,
        description="One entry per pipeline stage the day timed (findings 75, note 33).",
    )
    instruments: list[DayInstrument] = Field(
        default_factory=list,
        description="One entry per measured eval-row column (finding 74, note 38).",
    )
    sources: list[DaySource] = Field(
        default_factory=list,
        description="One entry per source that published (findings 67, 68, 73).",
    )
    extraction: DayExtraction | None = Field(
        default=None,
        description=(
            "What the candidate pass found and what the page drew from it, or null on a "
            "record written before 2026-09-08. Additive parts."
        ),
    )

    @model_validator(mode="after")
    def _the_parts_fit_the_day(self) -> Self:
        if self.bands.high + self.bands.medium + self.bands.low != self.items_published:
            raise ValueError("every published item carries exactly one band")
        if self.reasons.total() != self.bands.medium + self.bands.low:
            raise ValueError("every doubted item carries exactly one reason bucket")
        if self.summaries_scored > self.items_published:
            raise ValueError("more scored summaries than published items")
        if self.items_truncated > self.items_published:
            raise ValueError("more cut items than published items")
        if self.determinism_violations > self.summaries_scored:
            raise ValueError("more determinism violations than scored summaries")
        if self.extraction_suspect > self.summaries_scored:
            raise ValueError("more extraction-suspect items than scored summaries")

        stages = [entry.stage for entry in self.stage_timing]
        if len(stages) != len(set(stages)):
            raise ValueError("a stage is timed at most once a day")

        columns = [entry.column for entry in self.instruments]
        if len(columns) != len(set(columns)):
            raise ValueError("an instrument is aggregated at most once a day")

        source_ids = [entry.source_id for entry in self.sources]
        if len(source_ids) != len(set(source_ids)):
            raise ValueError("a source appears at most once a day")
        if self.sources_present != len(self.sources):
            raise ValueError("sources_present must count the sources listed")
        if sum(entry.published for entry in self.sources) != self.items_published:
            raise ValueError("the per-source published counts must total the published items")
        return self

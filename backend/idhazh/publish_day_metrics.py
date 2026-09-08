"""Write one day-metrics record per published day, at publication.

The console rebuilds every per-day figure by walking the whole committed
history - every score row, item-health row and published day - on each build
(research findings 61-75). That walk gets slower with every published day for an
answer that never changes once the day is frozen (CLAUDE.md Rule #12). This
producer writes the answer once, from the data the publication step already
holds, so a reader loads one small file instead.

One writer, at the existing publication step (`cli.stage_assemble`), never a
second stage (Fowler). A republished day rewrites its record whole rather than
adding to a running total: a total needs a decrement path for every correction,
and a missed decrement is silent and permanent (owner, 2026-09-06).

The record carries counts and facts about a day and never a line of article text
(CLAUDE.md section 0a). Every path it could name is relative and POSIX
(section 2).

The day's slice is read from that one day's month shard alone - not the whole
ledger - so the cost does not rise as the ledger keeps more months (Rule #12).
The figures match the frontend console reducers exactly, so the reader that
replaces the walk reads the same numbers it computes today: an eval-row
percentile is nearest-rank as `eval-instruments.ts` takes it, a stage or
throughput figure is interpolated as `series.ts` takes it.
"""

from __future__ import annotations

import csv
import logging
import math
from collections import Counter
from collections.abc import Iterable, Sequence
from pathlib import Path
from typing import Final

from idhazh import ledger
from idhazh.assemble import write_atomic
from idhazh.contracts.day_metrics import (
    INSTRUMENT_COLUMNS,
    DayBands,
    DayDistribution,
    DayExtraction,
    DayInstrument,
    DayMetrics,
    DayReasons,
    DaySource,
    DayStageTiming,
    DayThroughput,
)
from idhazh.contracts.digest_day import DigestDay
from idhazh.contracts.eval_row import BandReason, ConfidenceBand
from idhazh.contracts.item_health import ElementClass, ItemStage
from idhazh.contracts.run_manifest import ModelRole, RunManifest
from idhazh.contracts.visual_decision import VisualKind, VisualState
from idhazh.evals import writer as eval_writer
from idhazh.evals.metrics import extractable_but_unused_rate, span_integrity_rate

LOG: Final = logging.getLogger("idhazh")

DIRNAME: Final = "day-metrics"

#: The item-health timing column each stage records. Only these three stages
#: carry a wall-clock; plan and publish record none, so they never draw a bar.
_STAGE_TIMING_COLUMNS: Final[tuple[tuple[ItemStage, str], ...]] = (
    (ItemStage.FETCH, "fetch_ms"),
    (ItemStage.EXTRACT, "extract_ms"),
    (ItemStage.SUMMARIZE, "summarize_ms"),
)

#: Which `DayReasons` field a published item's `band_reason` counts into.
_BAND_REASON_FIELD: Final[dict[BandReason, str]] = {
    BandReason.UNSUPPORTED_NUMBER: "unsupported_number",
    BandReason.NOT_SCORED: "not_scored",
    BandReason.LEAD_MISSING: "lead_missing",
    BandReason.HEDGE_DROPPED: "hedge_dropped",
    BandReason.FAITHFULNESS: "faithfulness",
}

#: The two bands a doubted item falls in. A `high` item is never doubted.
_DOUBTED: Final[frozenset[ConfidenceBand]] = frozenset(
    {ConfidenceBand.MEDIUM, ConfidenceBand.LOW}
)


# --- paths -------------------------------------------------------------------


def day_metrics_relpath(date: str) -> str:
    """`state/day-metrics/<YYYY>/<MM>/<DD>.json` - the POSIX form, for a log line."""
    year, month, day = date[:4], date[5:7], date[8:10]
    return f"{ledger.STATE_DIRNAME}/{DIRNAME}/{year}/{month}/{day}.json"


def day_metrics_path(state_root: Path, date: str) -> Path:
    """The nested file one date's record lives in.

    Nested by year and month to mirror `frontend/public/digest/<YYYY>/<MM>/<DD>/`,
    so one month's folder holds about 31 files rather than a single directory
    that grows with every published day.
    """
    return state_root / DIRNAME / date[:4] / date[5:7] / f"{date[8:10]}.json"


# --- reading one day's committed slice ---------------------------------------


def read_score_rows(state_root: Path, date: str) -> list[dict[str, str]]:
    """The committed score rows for one day, from that day's month shard alone.

    One shard, never the whole ledger: the record is about one day, and a walk
    over every month would cost more with each month the ledger keeps
    (CLAUDE.md Rule #12).
    """
    return _rows_for_date(eval_writer.ledger_path(state_root, date), date)


def read_health_rows(state_root: Path, date: str) -> list[dict[str, str]]:
    """The committed item-health rows for one day, from that day's month shard alone."""
    return _rows_for_date(ledger.item_health_path(state_root, date), date)


def _rows_for_date(shard: Path, date: str) -> list[dict[str, str]]:
    if not shard.is_file():
        return []
    with shard.open("r", encoding="utf-8", newline="") as handle:
        return [row for row in csv.DictReader(handle) if row.get("date") == date]


# --- reducer arithmetic, matched to the frontend console ---------------------


def _measured(cell: str | None) -> float | None:
    """A cell that reads as a finite number, or None. An empty cell is None, never 0."""
    if cell is None:
        return None
    text = cell.strip()
    if text == "":
        return None
    try:
        value = float(text)
    except ValueError:
        return None
    return value if math.isfinite(value) else None


def _flag(cell: str | None) -> bool:
    """The ledger's own spelling of true. Anything else, a blank included, is false."""
    return (cell or "").strip().lower() == "true"


def _interpolated(values: Sequence[float], fraction: float) -> float:
    """The value a fraction of the way through a sorted list, interpolated.

    `series.ts quantile`: the convention the stage-timing and throughput panels
    read by. `values` is sorted and non-empty.
    """
    if len(values) == 1:
        return values[0]
    position = (len(values) - 1) * fraction
    low = math.floor(position)
    high = math.ceil(position)
    return values[low] + (values[high] - values[low]) * (position - low)


def _nearest_rank(values: Sequence[float], fraction: float) -> float:
    """The value at a position in a sorted list, never averaged.

    `eval-instruments.ts at`: the convention the eval-instrument panels read by.
    An interpolated quartile is a number no summary actually scored. `values` is
    sorted and non-empty.
    """
    index = min(len(values) - 1, math.floor(fraction * len(values)))
    return values[index]


# --- the record --------------------------------------------------------------


def build(
    *,
    date: str,
    day: DigestDay,
    manifest: RunManifest,
    score_rows: Sequence[dict[str, str]],
    health_rows: Sequence[dict[str, str]],
) -> DayMetrics:
    """The whole truth about one published day, as of the run that wrote it.

    `day` and `manifest` are this run's in-memory payloads; `score_rows` and
    `health_rows` are that day's committed ledger slices, so a correction reads
    the day as it now stands across every run rather than only what this run
    touched.
    """
    model_id, pipeline_fingerprint = _model_and_fingerprint(manifest, score_rows)
    scored, drifted, suspect = _scored_items(day, score_rows)
    return DayMetrics(
        version=DayMetrics.schema_version(),
        date=date,
        revision=manifest.runs[-1].n,
        runs=len(manifest.runs),
        model_id=model_id,
        pipeline_fingerprint=pipeline_fingerprint,
        items_published=len(day.items),
        items_planned=sum(run.items_planned for run in manifest.runs),
        items_failed=sum(run.items_failed for run in manifest.runs),
        visuals_rendered=sum(
            1
            for item in day.items
            if item.visual is not None and item.visual.state is VisualState.RENDERED
        ),
        items_truncated=sum(1 for item in day.items if item.truncated),
        summaries_scored=scored,
        determinism_violations=drifted,
        extraction_suspect=suspect,
        sources_present=len({item.source_id for item in day.items}),
        addresses_considered=_addresses_considered(day),
        bands=_bands(day),
        reasons=_reasons(day),
        throughput=_throughput(health_rows),
        stage_timing=_stage_timing(health_rows),
        instruments=_instruments(score_rows),
        sources=_sources(day),
        extraction=_extraction(day, health_rows),
    )


def _extraction(
    day: DigestDay, health_rows: Sequence[dict[str, str]]
) -> DayExtraction | None:
    """The day's join of what the extractor found against what the page drew.

    The class comes from the census, which carries every planned item across
    every run of the day; whether a chart reached a reader comes from the day
    payload, which is the whole published day. Joining them on `item_id` is what
    separates a planner that stopped choosing charts from an extractor that
    stopped finding numbers - without the denominator, one fall looks like the
    other and only one of them is the planner's fault.

    Both inputs are one day's worth, so the cost does not rise as the archive
    does (Rule #12). Null when no row on the day recorded the pass at all, which
    is what a day written before 2026-09-08 looks like: a block of zeros there
    would report an extractor that found nothing rather than a day that measured
    nothing.
    """
    charted = {
        item.item_id
        for item in day.items
        if item.visual is not None
        and item.visual.kind is VisualKind.CHART
        and item.visual.state is VisualState.RENDERED
    }
    published = {item.item_id for item in day.items}

    ran = 0
    held = 0
    found = 0
    classes: Counter[str] = Counter()
    chartable_published = 0
    chartable_charted = 0
    for row in health_rows:
        integrity = (row.get("span_integrity") or "").strip()
        if integrity == "":
            continue
        ran += 1
        if not _flag(integrity):
            continue
        held += 1
        found += int(_measured(row.get("elements_found")) or 0)
        label = (row.get("element_class") or "").strip()
        classes[label] += 1
        if label != ElementClass.CHARTABLE.value:
            continue
        item_id = row.get("item_id") or ""
        if item_id not in published:
            continue
        chartable_published += 1
        if item_id in charted:
            chartable_charted += 1

    if ran == 0:
        return None
    return DayExtraction(
        items=ran,
        span_integrity_pass=held,
        elements_found=found,
        chartable=classes[ElementClass.CHARTABLE.value],
        narrative=classes[ElementClass.NARRATIVE.value],
        unclassified=classes[ElementClass.UNCLASSIFIED.value],
        chartable_published=chartable_published,
        chartable_charted=chartable_charted,
    )


def _scored_items(
    day: DigestDay, score_rows: Sequence[dict[str, str]]
) -> tuple[int, int, int]:
    """Distinct published items the checker scored, drifted on, and doubted the text of.

    Counted over published items, not ledger rows, because these three are capped
    at the published set and the ledger is not one row per published item: it
    dedupes by measurement, so one item re-scored under a new stamp keeps both
    rows, and a run may score an item it then drops. Measured 2026-09-07 over the
    committed ledger, four of eighteen days carry more rows than the day
    published. A day's instrument distributions still read every row, as the
    console does; only these per-item counts join to the published set.
    """
    published = {item.item_id for item in day.items}
    scored: set[str] = set()
    drifted: set[str] = set()
    suspect: set[str] = set()
    for row in score_rows:
        item_id = row.get("item_id", "")
        if item_id not in published:
            continue
        scored.add(item_id)
        if _flag(row.get("determinism_violation")):
            drifted.add(item_id)
        if _flag(row.get("extraction_suspect")):
            suspect.add(item_id)
    return len(scored), len(drifted), len(suspect)



def _bands(day: DigestDay) -> DayBands:
    counts = {ConfidenceBand.HIGH: 0, ConfidenceBand.MEDIUM: 0, ConfidenceBand.LOW: 0}
    for item in day.items:
        counts[item.band] += 1
    return DayBands(
        high=counts[ConfidenceBand.HIGH],
        medium=counts[ConfidenceBand.MEDIUM],
        low=counts[ConfidenceBand.LOW],
    )


def _reasons(day: DigestDay) -> DayReasons:
    """Count each doubted item into exactly one bucket.

    A published `band_reason` names its bucket; a doubted item with no reason is
    `unattributed` - a real category the Model page counts apart, and never the
    same fact as `not_scored`. This mirrors `doubt-reasons.ts reasonDays`.
    """
    buckets = dict.fromkeys(_BAND_REASON_FIELD.values(), 0)
    unattributed = 0
    for item in day.items:
        if item.band_reason is not None:
            buckets[_BAND_REASON_FIELD[item.band_reason]] += 1
        elif item.band in _DOUBTED:
            unattributed += 1
    return DayReasons(
        unsupported_number=buckets["unsupported_number"],
        not_scored=buckets["not_scored"],
        lead_missing=buckets["lead_missing"],
        hedge_dropped=buckets["hedge_dropped"],
        faithfulness=buckets["faithfulness"],
        unattributed=unattributed,
    )


def _addresses_considered(day: DigestDay) -> int | None:
    """Distinct addresses the feeds offered the day, summed over its desks.

    Null on a day published before the desks carried the count: the three
    shortfall fields arrive together, so a single absent `considered` makes the
    day's total unknown rather than zero.
    """
    if not day.verticals or any(desk.considered is None for desk in day.verticals):
        return None
    return sum(desk.considered or 0 for desk in day.verticals)


def _sources(day: DigestDay) -> list[DaySource]:
    """One entry per source that published, counted off the day payload.

    `published`, `doubted` and `truncated` all read the published item, so the
    per-source counts and the day's bands and truncation cannot disagree.
    """
    published: dict[str, int] = {}
    doubted: dict[str, int] = {}
    truncated: dict[str, int] = {}
    for item in day.items:
        source_id = item.source_id
        published[source_id] = published.get(source_id, 0) + 1
        if item.band in _DOUBTED:
            doubted[source_id] = doubted.get(source_id, 0) + 1
        if item.truncated:
            truncated[source_id] = truncated.get(source_id, 0) + 1
    return [
        DaySource(
            source_id=source_id,
            published=published[source_id],
            doubted=doubted.get(source_id, 0),
            truncated=truncated.get(source_id, 0),
        )
        for source_id in sorted(published)
    ]


def _model_and_fingerprint(
    manifest: RunManifest, score_rows: Sequence[dict[str, str]]
) -> tuple[str, str]:
    """The model and pipeline stamp the day's summaries were written under.

    Read off the score ledger, as the model-change panel reads them (finding 70):
    the newest measurement on record, so a corrected day reports the stamp it now
    stands under. A day whose scorer never ran has no measurement to read, so it
    falls back to the newest run's declared summarize model and stamp.
    """
    if score_rows:
        newest = max(score_rows, key=lambda row: row.get("scored_at", ""))
        return newest["model_id"], newest["pipeline_fingerprint"]
    run = manifest.runs[-1]
    model_id = next(
        (use.model_ref.id for use in run.models if use.role is ModelRole.SUMMARIZE),
        None,
    )
    fingerprint = run.pipeline_fingerprints[0] if run.pipeline_fingerprints else None
    if model_id is None or fingerprint is None:
        raise ValueError(
            f"{manifest.date}: no scored item and no summarize model on the manifest, "
            "so the day's model cannot be named"
        )
    return model_id, fingerprint


def _throughput(health_rows: Sequence[dict[str, str]]) -> DayThroughput | None:
    """The day's token clock, summed over every timed attempt.

    Mirrors `model-work.ts throughputWithin` for one day: a row counts only if it
    reported a read rate or a write rate, and the day is null unless it recorded
    at least one of each - a rate needs both clocks.
    """
    reads = 0
    writes = 0
    prefill_ms = 0.0
    decode_ms = 0.0
    input_tokens = 0.0
    output_tokens = 0.0
    cached_tokens = 0.0
    for row in health_rows:
        read, write = _item_rates(row)
        if read is None and write is None:
            continue
        if read is not None:
            reads += 1
        if write is not None:
            writes += 1
        prefill_ms += _measured(row.get("prefill_ms")) or 0.0
        decode_ms += _measured(row.get("decode_ms")) or 0.0
        input_tokens += _measured(row.get("input_tokens")) or 0.0
        output_tokens += _measured(row.get("output_tokens")) or 0.0
        cached_tokens += _measured(row.get("cached_tokens")) or 0.0
    if reads == 0 or writes == 0:
        return None
    return DayThroughput(
        items=max(reads, writes),
        prefill_ms=round(prefill_ms),
        decode_ms=round(decode_ms),
        input_tokens=round(input_tokens),
        output_tokens=round(output_tokens),
        cached_tokens=round(cached_tokens),
    )


def _item_rates(row: dict[str, str]) -> tuple[float | None, float | None]:
    """One item's read and write rates, or None where the runtime timed neither.

    Cached prompt tokens are taken out of the read count: the machine did not
    read them. Mirrors `model-work.ts itemRates`.
    """
    prefill_ms = _measured(row.get("prefill_ms"))
    decode_ms = _measured(row.get("decode_ms"))
    prompt = _measured(row.get("input_tokens"))
    written = _measured(row.get("output_tokens"))
    evaluated = None if prompt is None else prompt - (_measured(row.get("cached_tokens")) or 0.0)
    read = (
        evaluated / (prefill_ms / 1000)
        if prefill_ms is not None and prefill_ms > 0 and evaluated is not None and evaluated > 0
        else None
    )
    write = (
        written / (decode_ms / 1000)
        if decode_ms is not None and decode_ms > 0 and written is not None and written > 0
        else None
    )
    return read, write


def _stage_timing(health_rows: Sequence[dict[str, str]]) -> list[DayStageTiming]:
    """One entry per stage the day timed, off the item-health census.

    `timed` and the totals mirror the console glance's `sample`/`timing`: a
    present cell counts, a zero included. The median is interpolated as
    `series.ts` takes it; the 90th and the total ride beside it so a window can
    add and re-divide them.
    """
    timings: list[DayStageTiming] = []
    for stage, column in _STAGE_TIMING_COLUMNS:
        values = sorted(
            value
            for value in (_measured(row.get(column)) for row in health_rows)
            if value is not None
        )
        if not values:
            continue
        timings.append(
            DayStageTiming(
                stage=stage,
                timed=len(values),
                sum_ms=round(sum(values)),
                p50_ms=round(_interpolated(values, 0.5)),
                p90_ms=round(_interpolated(values, 0.9)),
                max_ms=round(values[-1]),
            )
        )
    return timings


def _instruments(score_rows: Sequence[dict[str, str]]) -> list[DayInstrument]:
    """One entry per measured eval-row column, aggregated over the day.

    Every column of `INSTRUMENT_COLUMNS` that carried a value: the additive count
    and total, then the nearest-rank quartiles and range `eval-instruments.ts`
    draws. A column no row measured is left out, not stored as a row of zeroes.
    """
    instruments: list[DayInstrument] = []
    for column in sorted(INSTRUMENT_COLUMNS):
        values = sorted(
            value
            for value in (_measured(row.get(column)) for row in score_rows)
            if value is not None
        )
        if not values:
            continue
        instruments.append(
            DayInstrument(
                column=column,
                stat=DayDistribution(
                    count=len(values),
                    total=sum(values),
                    p25=_nearest_rank(values, 0.25),
                    p50=_nearest_rank(values, 0.5),
                    p75=_nearest_rank(values, 0.75),
                    minimum=values[0],
                    maximum=values[-1],
                ),
            )
        )
    return instruments


# --- writing -----------------------------------------------------------------


def write(state_root: Path, metrics: DayMetrics) -> Path:
    """Write one record, whole, with a temp-file-plus-rename.

    A correction rewrites the file rather than patching it, so a reader never
    sees a half-written day.
    """
    path = day_metrics_path(state_root, metrics.date)
    write_atomic(path, metrics.to_json())
    return path


def publish(
    *,
    state_root: Path,
    date: str,
    day: DigestDay,
    manifest: RunManifest,
) -> Path:
    """Build the day's record from its committed slice and write it.

    The one call the publication step and the backfill share, so the record is
    produced one way (Fowler).
    """
    metrics = build(
        date=date,
        day=day,
        manifest=manifest,
        score_rows=read_score_rows(state_root, date),
        health_rows=read_health_rows(state_root, date),
    )
    written = write(state_root, metrics)
    _log_extraction(date, metrics)
    return written


def _log_extraction(date: str, record: DayMetrics) -> None:
    """Say what the pass found and what the page drew, in the run log.

    Both rates are printed with the counts behind them, because a rate alone
    cannot say whether it moved or whether its denominator did - and telling
    those two apart is the whole reason the block exists.
    """
    extraction = record.extraction
    if extraction is None:
        LOG.info("extraction date=%s no item recorded the candidate pass", date)
        return
    unused = extractable_but_unused_rate(
        chartable_published=extraction.chartable_published,
        chartable_charted=extraction.chartable_charted,
    )
    integrity = span_integrity_rate(
        items=extraction.items, passed=extraction.span_integrity_pass
    )
    LOG.info(
        "extraction date=%s items=%s elements=%s chartable=%s narrative=%s unclassified=%s "
        "chartable_published=%s charted=%s unused_rate=%s span_integrity_rate=%s",
        date,
        extraction.items,
        extraction.elements_found,
        extraction.chartable,
        extraction.narrative,
        extraction.unclassified,
        extraction.chartable_published,
        extraction.chartable_charted,
        "-" if unused is None else f"{unused:.3f}",
        "-" if integrity is None else f"{integrity:.3f}",
    )


def backfill(state_root: Path, days: Iterable[tuple[str, DigestDay, RunManifest]]) -> list[Path]:
    """Rewrite the record for a set of already-published days.

    Each day is read from its own committed slice, so an old day gets the same
    whole-truth record a fresh publication would write.
    """
    return [
        publish(state_root=state_root, date=date, day=day, manifest=manifest)
        for date, day, manifest in days
    ]

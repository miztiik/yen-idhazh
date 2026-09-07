"""The day-metrics producer, proven against a hand-built day.

The record has to equal, field for field, what the frontend console reducers
compute from the same raw ledgers - that equality is what lets a reader replace
the whole-history walk with one file read (research findings 61-75). So the
expected numbers here are worked out by hand from a small fixture day and
asserted exactly, rather than recomputed by a second copy of the producer.

Driven by a bounded fixture and never by the committed archive: a per-item rule
is checked on a handful of built rows that can carry a case the archive has
never produced - two sources, a truncated item, an unattributed doubt, a failed
fetch that times one stage and no token (CLAUDE.md section 13, Rule #12).

The real injection canary cannot stand in for the throughput and stage-timing
figures: it writes a score ledger and a feed-health ledger but no item-health
ledger, so those two panels have no data on the canary day. They are exercised
here instead, and the gap is noted for whoever gives the canary an item-health
census.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from idhazh import ledger, publish_day_metrics
from idhazh.contracts.app_config import ModelRef
from idhazh.contracts.base import derive_url_key
from idhazh.contracts.day_metrics import DayInstrument, DayMetrics, DayStageTiming
from idhazh.contracts.digest_day import (
    DigestDay,
    DigestItem,
    DigestRunRef,
    DigestVerticalRef,
    DigestVisual,
)
from idhazh.contracts.eval_row import BandReason, ConfidenceBand, EvalRow
from idhazh.contracts.item_health import (
    FailureCode,
    ItemHealthRow,
    ItemOutcome,
    ItemStage,
)
from idhazh.contracts.run_manifest import (
    ModelRole,
    ModelUse,
    RunManifest,
    RunRecord,
    RunStatus,
)
from idhazh.contracts.visual_decision import VisualKind, VisualState
from idhazh.evals import writer as eval_writer

DATE = "2026-08-20"

_RENDERED_CHART = DigestVisual(
    kind=VisualKind.CHART,
    state=VisualState.RENDERED,
    path="digest/2026/08/20/energy-01/chart.svg",
)


def _item(
    item_id: str,
    source_id: str,
    band: ConfidenceBand,
    *,
    reason: BandReason | None = None,
    truncated: bool = False,
    visual: DigestVisual | None = None,
) -> DigestItem:
    return DigestItem(
        item_id=item_id,
        vertical="energy",
        title="A grid story",
        source_url=f"https://{source_id}.example.com/{item_id}",
        source_id=source_id,
        source_name=source_id.replace("-", " ").title(),
        summary="A short summary of one grid story.",
        key_points=["The reserve margin held."],
        band=band,
        band_reason=reason,
        truncated=truncated,
        visual=visual,
        introduced_by_run=1,
    )


def _day() -> DigestDay:
    """Four items over two sources: one high, two medium (one unattributed), one low."""
    items = [
        _item("energy-01", "grid-news", ConfidenceBand.HIGH, visual=_RENDERED_CHART),
        _item(
            "energy-02",
            "grid-news",
            ConfidenceBand.MEDIUM,
            reason=BandReason.UNSUPPORTED_NUMBER,
            truncated=True,
        ),
        _item("energy-03", "wire-co", ConfidenceBand.LOW, reason=BandReason.FAITHFULNESS),
        _item("energy-04", "wire-co", ConfidenceBand.MEDIUM),
    ]
    return DigestDay(
        version=DigestDay.schema_version(),
        date=DATE,
        generated_at=f"{DATE}T18:00:00Z",
        partial=True,
        items_planned=8,
        items_failed=1,
        runs=[
            DigestRunRef(n=1, at=f"{DATE}T06:00:00Z", items_added=4),
            DigestRunRef(n=2, at=f"{DATE}T18:00:00Z", items_added=0),
        ],
        verticals=[
            DigestVerticalRef(
                id="energy",
                display_name="Energy",
                count=4,
                considered=10,
                too_old=2,
                below_feed_floor=False,
            )
        ],
        items=items,
    )


def _run(n: int, *, planned: int, succeeded: int, failed: int, skipped: int) -> RunRecord:
    hour = "06" if n == 1 else "18"
    return RunRecord(
        run_id=f"{DATE}-{n}",
        n=n,
        started_at=f"{DATE}T{hour}:00:00Z",
        completed_at=f"{DATE}T{hour}:30:00Z",
        status=RunStatus.COMPLETED,
        commit_sha="0" * 40,
        runner="test-cpu",
        items_planned=planned,
        items_succeeded=succeeded,
        items_failed=failed,
        items_skipped=skipped,
        models=[
            ModelUse(
                role=ModelRole.SUMMARIZE,
                model_ref=ModelRef(
                    id="energy-model", repo="acme/energy", file="w.gguf", quantisation="Q4_K_M"
                ),
            )
        ],
        pipeline_fingerprints=["a" * 64],
        site_bytes=1000 * n,
        site_files=10 * n,
    )


def _manifest() -> RunManifest:
    """Two runs, so revision is 2 and the planned and failed counts are sums."""
    return RunManifest(
        version=RunManifest.schema_version(),
        date=DATE,
        runs=[
            _run(1, planned=5, succeeded=4, failed=1, skipped=0),
            _run(2, planned=3, succeeded=0, failed=0, skipped=3),
        ],
    )


def _score(
    item_id: str,
    source_id: str,
    band: ConfidenceBand,
    hhem: float,
    coverage: float,
    compression: float,
    *,
    determinism: bool = False,
    extraction: bool = False,
    output: str = "",
) -> EvalRow:
    url = f"https://{source_id}.example.com/{item_id}"
    return EvalRow(
        version=EvalRow.schema_version(),
        date=DATE,
        run_id=f"{DATE}-1",
        item_id=item_id,
        url_key=derive_url_key(url),
        source_url=url,
        title="A grid story",
        vertical="energy",
        model_id="energy-model",
        attempt=1,
        hhem=hhem,
        hhem_full=hhem,
        hhem_delta=0.0,
        truncation_flagged=False,
        coverage=coverage,
        compression=compression,
        extractiveness=0.2,
        verbatim_run=0.1,
        unsupported_numbers=0,
        hedge_dropped=False,
        extraction_suspect=extraction,
        band=band,
        source_word_count=500,
        source_seen_word_count=500,
        summary_word_count=100,
        pipeline_fingerprint="a" * 64,
        output_digest=derive_url_key(f"summary-{item_id}-{output}"),
        determinism_violation=determinism,
        scorer_version="canary-1",
        scored_at=f"{DATE}T06:12:00Z",
        score_ms=2000,
    )


def _scores() -> list[EvalRow]:
    """Three of the four items scored; energy-04 carries a band but no measurement."""
    return [
        _score("energy-01", "grid-news", ConfidenceBand.HIGH, 0.90, 0.80, 0.10),
        _score(
            "energy-02", "grid-news", ConfidenceBand.MEDIUM, 0.60, 0.50, 0.20, extraction=True
        ),
        _score("energy-03", "wire-co", ConfidenceBand.LOW, 0.30, 0.20, 0.30, determinism=True),
    ]


def _health(
    item_id: str,
    source_id: str,
    stage: ItemStage,
    outcome: ItemOutcome,
    *,
    code: FailureCode | None = None,
    fetch_ms: int | None = None,
    extract_ms: int | None = None,
    summarize_ms: int | None = None,
    prefill_ms: int | None = None,
    decode_ms: int | None = None,
    input_tokens: int | None = None,
    output_tokens: int | None = None,
    cached_tokens: int | None = None,
) -> ItemHealthRow:
    url = f"https://{source_id}.example.com/{item_id}"
    return ItemHealthRow(
        version=ItemHealthRow.schema_version(),
        date=DATE,
        run_id=f"{DATE}-1",
        item_id=item_id,
        url_key=derive_url_key(url),
        canonical_url=url,
        vertical="energy",
        source_id=source_id,
        stage=stage,
        outcome=outcome,
        code=code,
        fetch_ms=fetch_ms,
        extract_ms=extract_ms,
        summarize_ms=summarize_ms,
        prefill_ms=prefill_ms,
        decode_ms=decode_ms,
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        cached_tokens=cached_tokens,
    )


def _timed_health() -> list[ItemHealthRow]:
    """Two fully timed OK items and one fetch failure that times a stage but no token."""
    return [
        _health(
            "energy-01",
            "grid-news",
            ItemStage.PUBLISH,
            ItemOutcome.OK,
            fetch_ms=100,
            extract_ms=200,
            summarize_ms=3000,
            prefill_ms=500,
            decode_ms=2000,
            input_tokens=1000,
            output_tokens=300,
            cached_tokens=200,
        ),
        _health(
            "energy-02",
            "grid-news",
            ItemStage.PUBLISH,
            ItemOutcome.OK,
            fetch_ms=150,
            extract_ms=250,
            summarize_ms=4000,
            prefill_ms=1000,
            decode_ms=3000,
            input_tokens=2000,
            output_tokens=600,
            cached_tokens=0,
        ),
        _health(
            "energy-03",
            "wire-co",
            ItemStage.FETCH,
            ItemOutcome.FAILED,
            code=FailureCode.HTTP_SERVER_ERROR,
            fetch_ms=80,
        ),
    ]


def _stage(metrics: DayMetrics, stage: ItemStage) -> DayStageTiming:
    return next(entry for entry in metrics.stage_timing if entry.stage is stage)


def _instrument(metrics: DayMetrics, column: str) -> DayInstrument:
    return next(entry for entry in metrics.instruments if entry.column == column)


def test_the_producer_writes_the_whole_day_record(tmp_path: Path) -> None:
    state_root = tmp_path / "state"
    eval_writer.append(state_root, _scores())
    ledger.append_item_health(state_root, DATE, _timed_health())

    path = publish_day_metrics.day_metrics_path(state_root, DATE)
    # RED: no producer has run, so the record does not exist.
    assert not path.exists()

    written = publish_day_metrics.publish(
        state_root=state_root, date=DATE, day=_day(), manifest=_manifest()
    )

    # GREEN: the publication step wrote it, at the nested per-day path.
    assert written == path
    assert path.exists()
    assert path == state_root / "day-metrics" / "2026" / "08" / "20.json"

    metrics = DayMetrics.read(path)

    # Run identity, off the manifest.
    assert metrics.date == DATE
    assert metrics.revision == 2
    assert metrics.runs == 2
    assert metrics.items_planned == 8
    assert metrics.items_failed == 1

    # Model and pipeline, off the newest score row (finding 70).
    assert metrics.model_id == "energy-model"
    assert metrics.pipeline_fingerprint == "a" * 64

    # The published day.
    assert metrics.items_published == 4
    assert metrics.visuals_rendered == 1
    assert metrics.items_truncated == 1
    assert metrics.sources_present == 2
    assert metrics.addresses_considered == 10

    # Bands partition the published items.
    assert (metrics.bands.high, metrics.bands.medium, metrics.bands.low) == (1, 2, 1)

    # Each doubted item lands in one reason bucket; energy-04 is unattributed.
    assert metrics.reasons.unsupported_number == 1
    assert metrics.reasons.faithfulness == 1
    assert metrics.reasons.unattributed == 1
    assert metrics.reasons.not_scored == 0
    assert metrics.reasons.lead_missing == 0
    assert metrics.reasons.hedge_dropped == 0
    assert metrics.reasons.total() == 3

    # Off the score ledger.
    assert metrics.summaries_scored == 3
    assert metrics.determinism_violations == 1
    assert metrics.extraction_suspect == 1

    # Per source, off the published day.
    assert [(s.source_id, s.published, s.doubted, s.truncated) for s in metrics.sources] == [
        ("grid-news", 2, 1, 1),
        ("wire-co", 2, 2, 0),
    ]


def test_throughput_sums_only_the_timed_items(tmp_path: Path) -> None:
    state_root = tmp_path / "state"
    eval_writer.append(state_root, _scores())
    ledger.append_item_health(state_root, DATE, _timed_health())

    metrics = DayMetrics.read(
        publish_day_metrics.publish(
            state_root=state_root, date=DATE, day=_day(), manifest=_manifest()
        )
    )

    # The failed fetch timed no token, so it is out of the throughput sums; the
    # two OK items are in. items = max(reads, writes) = 2.
    assert metrics.throughput is not None
    assert metrics.throughput.items == 2
    assert metrics.throughput.prefill_ms == 1500
    assert metrics.throughput.decode_ms == 5000
    assert metrics.throughput.input_tokens == 3000
    assert metrics.throughput.output_tokens == 900
    assert metrics.throughput.cached_tokens == 200


def test_stage_timing_counts_the_failed_fetch(tmp_path: Path) -> None:
    state_root = tmp_path / "state"
    eval_writer.append(state_root, _scores())
    ledger.append_item_health(state_root, DATE, _timed_health())

    metrics = DayMetrics.read(
        publish_day_metrics.publish(
            state_root=state_root, date=DATE, day=_day(), manifest=_manifest()
        )
    )

    assert [entry.stage for entry in metrics.stage_timing] == [
        ItemStage.FETCH,
        ItemStage.EXTRACT,
        ItemStage.SUMMARIZE,
    ]

    fetch = _stage(metrics, ItemStage.FETCH)
    # Three fetch clocks [80, 100, 150], including the failed item's.
    assert fetch.timed == 3
    assert fetch.sum_ms == 330
    assert fetch.p50_ms == 100
    # The 90th is interpolated as series.ts takes it: 100 + (150-100)*0.8 = 140.
    assert fetch.p90_ms == 140
    assert fetch.max_ms == 150


def test_instruments_are_nearest_rank_quartiles(tmp_path: Path) -> None:
    state_root = tmp_path / "state"
    eval_writer.append(state_root, _scores())
    ledger.append_item_health(state_root, DATE, _timed_health())

    metrics = DayMetrics.read(
        publish_day_metrics.publish(
            state_root=state_root, date=DATE, day=_day(), manifest=_manifest()
        )
    )

    hhem = _instrument(metrics, "hhem")
    # hhem over [0.30, 0.60, 0.90], nearest-rank: p25=0.30, p50=0.60, p75=0.90.
    assert hhem.stat.count == 3
    assert hhem.stat.total == pytest.approx(1.80)
    assert hhem.stat.minimum == pytest.approx(0.30)
    assert hhem.stat.p25 == pytest.approx(0.30)
    assert hhem.stat.p50 == pytest.approx(0.60)
    assert hhem.stat.p75 == pytest.approx(0.90)
    assert hhem.stat.maximum == pytest.approx(0.90)

    coverage = _instrument(metrics, "coverage")
    assert coverage.stat.count == 3
    assert coverage.stat.total == pytest.approx(1.50)

    # A column no row measured is left out, never stored as a row of zeroes.
    assert not any(entry.column == "new_fact_rate" for entry in metrics.instruments)


def test_a_correction_rewrites_the_record_whole(tmp_path: Path) -> None:
    state_root = tmp_path / "state"
    eval_writer.append(state_root, _scores())
    ledger.append_item_health(state_root, DATE, _timed_health())

    publish_day_metrics.publish(
        state_root=state_root, date=DATE, day=_day(), manifest=_manifest()
    )

    # A third run corrects the day: the manifest gains a run, so revision and the
    # planned total move. The record is rewritten whole, never added to.
    corrected = _manifest().model_copy(
        update={
            "runs": [
                *_manifest().runs,
                _run(3, planned=2, succeeded=2, failed=0, skipped=0),
            ]
        }
    )
    path = publish_day_metrics.publish(
        state_root=state_root, date=DATE, day=_day(), manifest=corrected
    )

    metrics = DayMetrics.read(path)
    assert metrics.revision == 3
    assert metrics.runs == 3
    assert metrics.items_planned == 10
    assert metrics.items_failed == 1


def test_a_day_that_timed_nothing_has_no_throughput(tmp_path: Path) -> None:
    state_root = tmp_path / "state"
    eval_writer.append(state_root, _scores())
    # No item-health ledger at all, as on the injection canary day.

    metrics = DayMetrics.read(
        publish_day_metrics.publish(
            state_root=state_root, date=DATE, day=_day(), manifest=_manifest()
        )
    )

    assert metrics.throughput is None
    assert metrics.stage_timing == []
    # The score-derived figures still land.
    assert metrics.summaries_scored == 3
    assert metrics.model_id == "energy-model"


def test_scored_counts_distinct_published_items_not_ledger_rows(tmp_path: Path) -> None:
    """The ledger dedupes by measurement, not by item, so a day can hold more rows
    than it published: one item re-scored under a new output, and an item scored
    then dropped. The per-item counts join to the published set; the instrument
    distributions still read every row, as the console does."""
    state_root = tmp_path / "state"
    day = DigestDay(
        version=DigestDay.schema_version(),
        date=DATE,
        generated_at=f"{DATE}T18:00:00Z",
        partial=False,
        items_planned=2,
        items_failed=0,
        runs=[DigestRunRef(n=1, at=f"{DATE}T06:00:00Z", items_added=2)],
        verticals=[DigestVerticalRef(id="energy", display_name="Energy", count=2)],
        items=[
            _item("energy-01", "grid-news", ConfidenceBand.MEDIUM, reason=BandReason.FAITHFULNESS),
            _item("energy-02", "grid-news", ConfidenceBand.HIGH),
        ],
    )
    manifest = RunManifest(
        version=RunManifest.schema_version(),
        date=DATE,
        runs=[_run(1, planned=2, succeeded=2, failed=0, skipped=0)],
    )
    eval_writer.append(
        state_root,
        [
            # energy-01 scored twice, drifting once - two rows, one published item.
            _score("energy-01", "grid-news", ConfidenceBand.MEDIUM, 0.5, 0.5, 0.2, output="a"),
            _score(
                "energy-01",
                "grid-news",
                ConfidenceBand.MEDIUM,
                0.5,
                0.5,
                0.2,
                output="b",
                determinism=True,
            ),
            _score("energy-02", "grid-news", ConfidenceBand.HIGH, 0.9, 0.9, 0.1),
            # A row for an item this day did not publish.
            _score("energy-99", "ghost", ConfidenceBand.HIGH, 0.7, 0.7, 0.3),
        ],
    )

    metrics = DayMetrics.read(
        publish_day_metrics.publish(
            state_root=state_root, date=DATE, day=day, manifest=manifest
        )
    )

    # Two published items were scored; the four ledger rows and the ghost item do
    # not inflate it, and the item cannot outrun the published set.
    assert metrics.items_published == 2
    assert metrics.summaries_scored == 2
    assert metrics.determinism_violations == 1

    # The instrument still reads all four rows, matching the console reducer.
    assert _instrument(metrics, "hhem").stat.count == 4


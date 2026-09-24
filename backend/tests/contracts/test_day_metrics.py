"""Does a day's own measurements survive being written and read back?"""

from __future__ import annotations

import pytest

from idhazh.contracts.day_metrics import (
    DayBands,
    DayDistribution,
    DayInstrument,
    DayMetrics,
    DayReasons,
    DaySource,
    DayStageTiming,
    DayThroughput,
)
from idhazh.contracts.eval_row import BandReason, ConfidenceBand
from idhazh.contracts.item_health import ItemStage

pytestmark = pytest.mark.contract


#
# Row 21 ships the shape, not the producer or the reader. The generic oracle
# above already round-trips the committed fixture; these build a record in code
# instead of walking committed days (`CLAUDE.md` section 13), so they can carry
# the awkward case a real archive may never produce - a timed-nothing stage
# beside timed ones, an empty instrument beside a populated one - and prove the
# two halves of Andre's additive/non-additive split read back the way a later
# reducer needs.


def _day_metrics_sample() -> DayMetrics:
    """One coherent published day, built to satisfy every cross-field invariant."""
    return DayMetrics(
        version=DayMetrics.schema_version(),
        date="2026-08-24",
        revision=5,
        runs=5,
        model_id="qwen35-9b",
        items_published=6,
        items_planned=8,
        items_failed=2,
        visuals_rendered=2,
        items_truncated=1,
        summaries_scored=5,
        determinism_violations=0,
        extraction_suspect=1,
        sources_present=2,
        addresses_considered=20,
        bands=DayBands(high=4, medium=1, low=1),
        reasons=DayReasons(
            unsupported_number=1,
            not_scored=0,
            lead_missing=1,
            hedge_dropped=0,
            faithfulness=0,
            unattributed=0,
        ),
        throughput=DayThroughput(
            items=5,
            prefill_ms=12000,
            decode_ms=45000,
            input_tokens=21000,
            output_tokens=1800,
            cached_tokens=6000,
        ),
        stage_timing=[
            DayStageTiming(stage=ItemStage.PLAN, timed=0),
            DayStageTiming(
                stage=ItemStage.SUMMARIZE,
                timed=5,
                sum_ms=45000,
                p50_ms=8200,
                p90_ms=12000,
                max_ms=15000,
            ),
        ],
        instruments=[
            DayInstrument(
                column="hhem",
                stat=DayDistribution(
                    count=5, total=4.3, p25=0.78, p50=0.88, p75=0.94, minimum=0.55, maximum=0.99
                ),
            ),
            DayInstrument(column="coherence", stat=DayDistribution(count=0, total=0.0)),
        ],
        sources=[
            DaySource(source_id="the-hindu", published=4, doubted=1, truncated=1),
            DaySource(source_id="reuters", published=2, doubted=1, truncated=0),
        ],
    )


def test_day_metrics_round_trips_and_a_built_record_reads_back_identically() -> None:
    """A record the producer will write validates, and an additive count and a
    non-additive statistic both read back unchanged (Andre's split)."""
    once = _day_metrics_sample().to_json()
    reloaded = DayMetrics.from_json(once)
    assert reloaded.to_json() == once
    # Additive: stored as the number a reader adds across days.
    assert reloaded.items_published == 6
    assert reloaded.throughput is not None and reloaded.throughput.decode_ms == 45000
    hhem = next(item for item in reloaded.instruments if item.column == "hhem")
    assert hhem.stat.count == 5 and hhem.stat.total == 4.3
    # Non-additive: the day's own value the reader must recombine, not add.
    assert reloaded.sources_present == 2
    assert hhem.stat.p50 == 0.88
    # Decision 4: the revision stamp survives, so a later run can spot a stale record.
    assert reloaded.revision == 5


def test_day_metrics_keeps_an_empty_aggregate_apart_from_a_zero_one() -> None:
    """A timed-nothing stage and an empty instrument keep their absent figures;
    empty is not zero (the all-or-nothing validators), so a reducer never reads a
    missing median as a real 0."""
    reloaded = DayMetrics.from_json(_day_metrics_sample().to_json())
    plan = next(stage for stage in reloaded.stage_timing if stage.stage == ItemStage.PLAN)
    assert plan.timed == 0 and plan.sum_ms is None and plan.p50_ms is None
    empty = next(item for item in reloaded.instruments if item.column == "coherence")
    assert empty.stat.count == 0 and empty.stat.total == 0.0 and empty.stat.p50 is None


def test_day_metrics_bands_and_reasons_mirror_the_eval_vocabulary() -> None:
    """The day's partitions only hold if its buckets are the eval bands and
    reasons themselves. Coupling them here turns a new band or reason added to
    EvalRow red, rather than letting a doubted item go uncounted."""
    assert set(DayBands.model_fields) == {band.value for band in ConfidenceBand}
    assert set(DayReasons.model_fields) == {reason.value for reason in BandReason} | {"unattributed"}

"""The run-timeline projection, driven from a built fixture.

**Built, never read out of the committed tree.** The archive offers a handful of
distinct cases however far it grows and costs more to walk every time a run
appends (`CLAUDE.md` Guardrail #12, section 13). It also cannot produce the
shapes that matter here - a run whose shards overlap on the clock, an item that
died before the model saw it, and a bar whose steps outrun their own item -
because no committed census row carries an item clock at all.
"""

from __future__ import annotations

from datetime import date
from pathlib import Path
from typing import Final

import pytest
from conftest import seed_item_health

from idhazh import ledger
from idhazh.contracts.item_health import ItemHealthRow, ItemOutcome, ItemStage
from idhazh.contracts.run_timeline import STEP_COLUMNS, RunTimelineRow
from idhazh.telemetry.publish import dispatch, run_timeline, series

DAY: Final = "2026-09-16"
MONTH: Final = "2026-09"
RUN: Final = "2026-09-16-1"


def census_row(
    item_id: str,
    *,
    shard: int | None = None,
    started_at: str | None = None,
    total_ms: int | None = None,
    fetch_ms: int | None = None,
    extract_ms: int | None = None,
    label_ms: int | None = None,
    summary_ms: int | None = None,
    visual_plan_ms: int | None = None,
    faithfulness_ms: int | None = None,
) -> ItemHealthRow:
    """One census row with only the cells the timeline reads filled in."""
    return ItemHealthRow(
        version=ItemHealthRow.schema_version(),
        date=DAY,
        run_id=RUN,
        item_id=item_id,
        url_key="0" * 64,
        canonical_url=f"https://example.com/{item_id}",
        vertical="ai",
        source_id="example",
        stage=ItemStage.PUBLISH,
        outcome=ItemOutcome.OK,
        shard=shard,
        item_started_at=started_at,
        item_total_ms=total_ms,
        fetch_ms=fetch_ms,
        extract_ms=extract_ms,
        label_ms=label_ms,
        summary_ms=summary_ms,
        visual_plan_ms=visual_plan_ms,
        faithfulness_ms=faithfulness_ms,
    )


@pytest.fixture
def census(tmp_path: Path) -> Path:
    """One day of a run whose two shards overlap, written where the reader looks.

    Four items. The first two are shard 0 back to back; the third is shard 1 and
    starts while the first is still running, which is the overlap the `shard`
    column exists to tell apart from a contradiction. The fourth never reached a
    shard at all.
    """
    state = tmp_path / "state"
    seed_item_health(
        state,
        DAY,
        [
            census_row(
                "ai-01",
                shard=0,
                started_at="2026-09-16T06:00:00Z",
                total_ms=12_000,
                fetch_ms=2_000,
                extract_ms=1_000,
                label_ms=1_500,
                summary_ms=5_000,
                visual_plan_ms=500,
                faithfulness_ms=1_960,
            ),
            census_row(
                "ai-02",
                shard=0,
                started_at="2026-09-16T06:00:40Z",
                total_ms=2_000,
                fetch_ms=300,
                extract_ms=100,
                label_ms=200,
                summary_ms=1_000,
                visual_plan_ms=600,
                faithfulness_ms=90,
            ),
            # Died at fetch: one step and nothing after it, which the contract
            # says still draws.
            census_row(
                "ai-03",
                shard=1,
                started_at="2026-09-16T06:00:10Z",
                total_ms=500,
                fetch_ms=420,
            ),
            # Planned and never picked up. No start, no shard, no bar.
            census_row("ai-04"),
        ],
    )
    return state


def project(census: Path) -> list[RunTimelineRow]:
    return run_timeline.project(ledger.item_health_path(census, DAY))


def test_an_item_no_shard_picked_up_has_no_bar(census: Path) -> None:
    """An absent row reads as never worked, which is exactly what happened to it."""
    assert [row.item_id for row in project(census)] == ["ai-01", "ai-03", "ai-02"]


def test_the_zero_is_the_first_item_start_and_the_rest_are_offsets(census: Path) -> None:
    """The bar's position is the wait, so an item that queued has to sit right of it."""
    offsets = {row.item_id: row.start_offset_ms for row in project(census)}
    assert offsets == {"ai-01": 0, "ai-03": 10_000, "ai-02": 40_000}


def test_two_shards_may_overlap_on_the_clock(census: Path) -> None:
    """Correct exactly when the bars sit on different shards, which the row says."""
    rows = {row.item_id: row for row in project(census)}
    first, second = rows["ai-01"], rows["ai-03"]
    assert second.start_offset_ms < first.start_offset_ms + first.item_total_ms
    assert first.shard != second.shard


def test_the_scorers_clock_is_the_census_column_of_the_same_stopwatch(census: Path) -> None:
    """`stages/work.py` times the scorers once and files it as `faithfulness_ms`."""
    rows = {row.item_id: row for row in project(census)}
    assert rows["ai-01"].score_ms == 1_960
    assert rows["ai-03"].score_ms is None


def test_two_steps_have_no_producer_so_every_row_leaves_them_empty(census: Path) -> None:
    """Absent by design, and the panel says so rather than drawing an empty legend."""
    for row in project(census):
        for name in run_timeline.UNTIMED_STEPS:
            assert getattr(row, name) is None
    assert set(run_timeline.CENSUS_STEPS) | set(run_timeline.UNTIMED_STEPS) == set(STEP_COLUMNS)


def test_a_residual_is_signed_and_an_apportioned_plan_makes_it_negative(census: Path) -> None:
    """The one signal that says two steps counted part of one call twice."""
    rows = {row.item_id: row for row in project(census)}
    # 12,000 total against 11,960 of steps.
    assert rows["ai-01"].residual_ms == 40
    # 2000 total against 2290 of steps, because the plan is cut out of the
    # summary call rather than timed beside it.
    assert rows["ai-02"].residual_ms == -290
    # One step timed, so the other 80 is time nobody accounted for.
    assert rows["ai-03"].residual_ms == 80


def test_the_published_shard_is_what_the_contract_declares(census: Path, tmp_path: Path) -> None:
    """Header, order and every cell, read back through the model that wrote them."""
    digest_root = tmp_path / "public" / "digest"
    written = run_timeline.publish(
        state_root=census,
        digest_root=digest_root,
        keep_months=2,
        today=date.fromisoformat(DAY),
        months={MONTH},
        ensure_month=MONTH,
    )
    shard = run_timeline.shard_path(digest_root, MONTH)
    assert written == [shard]
    assert shard.read_text(encoding="utf-8").splitlines()[0] == ",".join(
        run_timeline.PUBLIC_COLUMNS
    )
    assert run_timeline.read_shard(shard) == project(census)


def test_a_month_with_no_census_still_publishes_an_empty_shard(tmp_path: Path) -> None:
    """A console asking for a month that never ran needs an empty answer, not a 404."""
    digest_root = tmp_path / "public" / "digest"
    run_timeline.publish(
        state_root=tmp_path / "state",
        digest_root=digest_root,
        keep_months=2,
        today=date.fromisoformat(DAY),
        months={MONTH},
        ensure_month=MONTH,
    )
    shard = run_timeline.shard_path(digest_root, MONTH)
    assert shard.is_file()
    assert run_timeline.read_shard(shard) == []


def test_the_dispatcher_routes_to_it_and_the_series_knows_its_directory() -> None:
    """A projection the route does not name never runs, whatever it can do."""
    assert "run-timeline" in [projection.name for projection in dispatch.PROJECTIONS]
    assert run_timeline.DIRNAME in series.PUBLISHED_ROOTS
    assert (run_timeline.DIRNAME, run_timeline.SUFFIX) in series.MONTH_SERIES

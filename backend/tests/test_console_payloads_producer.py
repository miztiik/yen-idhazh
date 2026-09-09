"""The seven console payload producers, driven from a built fixture.

Every fixture here is **built**, never read out of the committed tree: the
archive offers a handful of distinct cases however far it grows, and a test that
walks it costs more every time a run appends (`CLAUDE.md` Rule #12, section 13).
Building it is also the only way to get the awkward shapes - a month of twenty,
a run whose shards disagree, a day that published nothing.
"""

from __future__ import annotations

import csv
import json
import sys
from collections.abc import Iterator
from datetime import date
from pathlib import Path
from typing import Any, Final

import pytest

from idhazh import (
    publish_console,
    publish_console_band,
    publish_day_metrics,
    publish_feed_health,
    publish_machine,
    publish_run_days,
    publish_scores,
    publish_span_rollup,
)
from idhazh.contracts.app_config import CollectConfig, ConsoleConfig, ModelRef, RunConfig
from idhazh.contracts.console_band import Health, RouteId
from idhazh.contracts.day_metrics import DayBands, DayMetrics, DayReasons, DaySource
from idhazh.contracts.digest_day import DigestDay, DigestItem, DigestRunRef, DigestVerticalRef
from idhazh.contracts.eval_row import ConfidenceBand, EvalRow
from idhazh.contracts.feed_health import FeedHealthRow, FetchOutcome
from idhazh.contracts.public_eval import PublicEvalRow
from idhazh.contracts.public_feed_health import PublicFeedRow
from idhazh.contracts.run_manifest import (
    ModelRole,
    ModelUse,
    RunManifest,
    RunRecord,
    RunStatus,
)
from idhazh.contracts.runtime_counters import RuntimeCountersRow
from idhazh.contracts.span_rollup import RollupSpan, SpanRollupRow
from idhazh.contracts.visual_decision import VisualKind, VisualState

#: These are the published shapes and the committed digest tree, which is what
#: the `contract` selector is for. Its three sibling producer modules are in
#: `test_marks.UNMARKED_MODULES` and stay there - moving them is a change to
#: what those selectors mean and belongs in its own commit.
pytestmark = pytest.mark.contract

#: Twenty months of everything, which is more than any retention knob keeps and
#: enough that a producer reading them all is obvious in a handle count.
MONTHS: Final[tuple[str, ...]] = tuple(
    f"{2025 + (index + 4) // 12:04d}-{(index + 4) % 12 + 1:02d}" for index in range(20)
)
#: The newest month the fixture holds, which is what a daily run would name.
NEWEST: Final = MONTHS[-1]
NEWEST_DAY: Final = f"{NEWEST}-01"
TODAY: Final = date.fromisoformat(NEWEST_DAY)

CONSOLE: Final = ConsoleConfig()
RUN: Final = RunConfig()
COLLECT: Final = CollectConfig()


# --- the fixture -------------------------------------------------------------


def _eval_row(month: str) -> EvalRow:
    return EvalRow(
        version=EvalRow.schema_version(),
        date=f"{month}-01",
        run_id=f"{month}-01-1",
        item_id="energy-01",
        url_key="a" * 64,
        source_url="https://grid.example.com/energy-01",
        title="A grid story",
        vertical="energy",
        model_id="energy-model",
        attempt=1,
        hhem=0.9,
        hhem_full=0.9,
        hhem_delta=0.0,
        truncation_flagged=False,
        coverage=0.8,
        compression=0.2,
        extractiveness=0.4,
        band=ConfidenceBand.HIGH,
        summary_word_count=60,
        pipeline_fingerprint="b" * 64,
        output_digest="c" * 64,
        scorer_version="hhem-2.1",
        scored_at=f"{month}-01T06:10:00Z",
    )


def _ledger_cells(row: EvalRow) -> dict[str, str]:
    """The eval ledger's own serialisation: every cell a string, absent is blank."""
    payload = row.model_dump(mode="json")
    return {name: "" if payload[name] is None else str(payload[name]) for name in payload}


def _feed_row(month: str, *, feed_id: str, outcome: FetchOutcome, items: int) -> FeedHealthRow:
    return FeedHealthRow(
        version=FeedHealthRow.schema_version(),
        run_id=f"{month}-01-1",
        date=f"{month}-01",
        feed_id=feed_id,
        endpoint_key="d" * 64,
        checked_at=f"{month}-01T06:00:00Z",
        outcome=outcome,
        items=items,
        detail=None if outcome is FetchOutcome.OK else "our own one-line reason",
    )


def _counters_row(month: str, *, shard: int, prompt: int, seconds: float) -> RuntimeCountersRow:
    return RuntimeCountersRow(
        version=RuntimeCountersRow.schema_version(),
        date=f"{month}-01",
        run_id=f"{month}-01-1",
        shard=shard,
        shards=2,
        scraped_at=f"{month}-01T06:30:00Z",
        prompt_tokens_total=prompt,
        prompt_seconds_total=seconds,
    )


def _span_row(month: str) -> SpanRollupRow:
    return SpanRollupRow(
        version=SpanRollupRow.schema_version(),
        date=f"{month}-01",
        run_id=f"{month}-01-1",
        shard=0,
        span_name=RollupSpan.ITEM,
        count=4,
        total_ms=4000,
        unattributed_ms=120,
    )


def _item(item_id: str, *, charted: bool) -> DigestItem:
    visual = None
    if charted:
        visual = {
            "kind": VisualKind.CHART,
            "state": VisualState.RENDERED,
            "path": "digest/2026/08/20/energy-01/chart.svg",
        }
    return DigestItem.model_validate(
        {
            "item_id": item_id,
            "vertical": "energy",
            "title": "A grid story",
            "source_url": f"https://grid.example.com/{item_id}",
            "source_id": "grid-news",
            "source_name": "Grid News",
            "summary": "A short summary of one grid story.",
            "key_points": ["The reserve margin held."],
            "band": ConfidenceBand.HIGH,
            "band_reason": None,
            "truncated": False,
            "visual": visual,
            "introduced_by_run": 1,
        }
    )


def _day(stamp: str, *, items: int, charts: int) -> DigestDay:
    built = [_item(f"energy-{index + 1:02d}", charted=index < charts) for index in range(items)]
    return DigestDay(
        version=DigestDay.schema_version(),
        date=stamp,
        generated_at=f"{stamp}T18:00:00Z",
        partial=False,
        items_planned=items,
        items_failed=0,
        runs=[DigestRunRef(n=1, at=f"{stamp}T06:00:00Z", items_added=items)],
        verticals=[
            DigestVerticalRef(
                id="energy",
                display_name="Energy",
                count=items,
                considered=items + 2,
                too_old=0,
                below_feed_floor=False,
            )
        ],
        items=built,
    )


def _manifest(stamp: str, *, planned: int, succeeded: int, failed: int, site_bytes: int) -> RunManifest:
    return RunManifest(
        version=RunManifest.schema_version(),
        date=stamp,
        runs=[
            RunRecord(
                run_id=f"{stamp}-1",
                n=1,
                started_at=f"{stamp}T06:00:00Z",
                completed_at=f"{stamp}T06:30:00Z",
                status=RunStatus.COMPLETED,
                commit_sha="0" * 40,
                runner="test-cpu",
                items_planned=planned,
                items_succeeded=succeeded,
                items_failed=failed,
                models=[
                    ModelUse(
                        role=ModelRole.SUMMARIZE,
                        model_ref=ModelRef(
                            id="energy-model",
                            repo="acme/energy",
                            file="w.gguf",
                            quantisation="Q4_K_M",
                        ),
                    )
                ],
                pipeline_fingerprints=["a" * 64],
                site_bytes=site_bytes,
                site_files=10,
            )
        ],
    )


def _record(stamp: str) -> DayMetrics:
    return DayMetrics(
        version=DayMetrics.schema_version(),
        date=stamp,
        revision=1,
        runs=1,
        model_id="energy-model",
        pipeline_fingerprint="a" * 64,
        items_published=3,
        items_planned=4,
        items_failed=1,
        visuals_rendered=1,
        items_truncated=2,
        summaries_scored=3,
        determinism_violations=0,
        extraction_suspect=0,
        sources_present=1,
        sources=[DaySource(source_id="grid-news", published=3, doubted=2, truncated=2)],
        bands=DayBands(high=1, medium=1, low=1),
        # Two doubted items, so two reason buckets: the record refuses any other
        # pairing, which is the shape a fixture has to honour.
        reasons=DayReasons(
            unsupported_number=1,
            not_scored=0,
            lead_missing=0,
            hedge_dropped=0,
            faithfulness=1,
            unattributed=0,
        ),
    )


def _write_csv(path: Path, columns: tuple[str, ...], rows: list[dict[str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(columns), lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


@pytest.fixture
def tree(tmp_path: Path) -> tuple[Path, Path]:
    """Twenty months of state and twenty published days, one a month."""
    state = tmp_path / "state"
    digest = tmp_path / "frontend" / "public" / "digest"
    counters: list[dict[str, str]] = []
    for index, month in enumerate(MONTHS):
        stamp = f"{month}-01"
        _write_csv(
            state / "scores" / f"{month}.csv",
            EvalRow.csv_columns(),
            [_ledger_cells(_eval_row(month))],
        )
        _write_csv(
            state / "feed-health" / f"{month}.csv",
            FeedHealthRow.csv_columns(),
            [
                _feed_row(month, feed_id="grid-news", outcome=FetchOutcome.OK, items=4).csv_row(),
                _feed_row(
                    month, feed_id="wire-co", outcome=FetchOutcome.PERMANENT, items=0
                ).csv_row(),
            ],
        )
        _write_csv(
            state / "span-rollup" / f"{month}.csv",
            SpanRollupRow.csv_columns(),
            [_span_row(month).csv_row()],
        )
        record = state / "day-metrics" / month[:4] / month[5:7] / "01.json"
        record.parent.mkdir(parents=True, exist_ok=True)
        record.write_text(_record(stamp).to_json(), encoding="utf-8")
        counters.append(_counters_row(month, shard=0, prompt=1000, seconds=10.0).csv_row())
        counters.append(_counters_row(month, shard=1, prompt=1000, seconds=20.0).csv_row())
        day_dir = digest / month[:4] / month[5:7] / "01"
        day_dir.mkdir(parents=True, exist_ok=True)
        (day_dir / "digest.json").write_text(
            _day(stamp, items=3, charts=1).to_json(), encoding="utf-8"
        )
        (day_dir / "run.json").write_text(
            _manifest(
                stamp, planned=4, succeeded=3, failed=1, site_bytes=1_000_000 + index * 30_000
            ).to_json(),
            encoding="utf-8",
        )
    _write_csv(state / "runtime-counters.csv", RuntimeCountersRow.csv_columns(), counters)
    return state, digest


# --- the oracle: file handles, never wall clock ------------------------------


_OPENED: list[str] = []
_WATCHING = False


def _audit(event: str, args: tuple[Any, ...]) -> None:
    if _WATCHING and event == "open" and args and isinstance(args[0], str):
        _OPENED.append(args[0])


sys.addaudithook(_audit)


def _handles(root: Path) -> Iterator[list[str]]:
    """Every path opened inside `root` while the block runs.

    An audit hook rather than a stopwatch, because a stopwatch on this box
    cannot tell one month from twenty: a sibling row measured 16.6 percent
    run-to-run variance on identical work, which is more than nineteen months of
    fixture could ever cost. What the reads open is arithmetic and has no spread
    at all (Rule #10).
    """
    global _WATCHING
    seen: list[str] = []
    _OPENED.clear()
    _WATCHING = True
    try:
        yield seen
    finally:
        _WATCHING = False
        prefix = str(root)
        seen.extend(path for path in _OPENED if path.startswith(prefix))
        _OPENED.clear()


@pytest.fixture
def opened(tmp_path: Path) -> Iterator[list[str]]:
    yield from _handles(tmp_path)


def _publish_all(state: Path, digest: Path, *, months: set[str] | None) -> None:
    publish_scores.publish(
        state_root=state, digest_root=digest, keep_months=14, today=TODAY, months=months
    )
    publish_feed_health.publish(
        state_root=state, digest_root=digest, keep_months=14, today=TODAY, months=months
    )
    publish_machine.publish(
        state_root=state, digest_root=digest, keep_months=14, today=TODAY, months=months
    )
    publish_span_rollup.publish(
        state_root=state, digest_root=digest, keep_months=14, today=TODAY, months=months
    )
    publish_day_metrics.publish_public(
        state_root=state, digest_root=digest, keep_months=14, today=TODAY, months=months
    )
    publish_run_days.publish(
        digest_root=digest, keep_months=14, today=TODAY, months=months
    )


def test_the_second_run_opens_one_month_not_twenty(
    tree: tuple[Path, Path], opened: list[str]
) -> None:
    """The oracle of row 9, asserted on file handles.

    The first run backfills - every month's target is missing, so every month is
    read. The second names the one month it appended to and reads that one,
    which is decision 4: the run knows which month it just wrote.
    """
    state, digest = tree
    _publish_all(state, digest, months=None)
    _OPENED.clear()

    _publish_all(state, digest, months={NEWEST})

    read = [path for path in _OPENED if str(state) in path or str(digest) in path]
    source_months = {
        part
        for path in read
        for part in [Path(path).stem]
        if len(part) == 7 and part[4] == "-"
    }
    assert source_months == {NEWEST}, sorted(source_months)


def test_the_first_run_reads_every_month_and_the_second_writes_nothing(
    tree: tuple[Path, Path],
) -> None:
    """Byte equality, not a timestamp: a re-derived month is not rewritten."""
    state, digest = tree
    first = publish_scores.publish(
        state_root=state, digest_root=digest, keep_months=20, today=TODAY, months=None
    )
    assert len(first) == len(MONTHS)

    again = publish_scores.publish(
        state_root=state, digest_root=digest, keep_months=20, today=TODAY, months=None
    )

    assert again == []


def test_a_missing_target_is_written_even_when_its_month_was_not_named(
    tree: tuple[Path, Path],
) -> None:
    """A fresh clone, a deleted file and a first backfill all land.

    Without this a month outside the named set would be skipped for ever, and a
    console asking for it would get a 404 it cannot tell from a broken deploy.
    """
    state, digest = tree
    publish_scores.publish(
        state_root=state, digest_root=digest, keep_months=20, today=TODAY, months=None
    )
    publish_scores.shard_path(digest, MONTHS[0]).unlink()

    written = publish_scores.publish(
        state_root=state, digest_root=digest, keep_months=20, today=TODAY, months={NEWEST}
    )

    assert [path.stem for path in written] == [MONTHS[0]]


# --- retention ---------------------------------------------------------------


@pytest.mark.parametrize(
    ("dirname", "suffix"),
    [
        (publish_scores.DIRNAME, ".csv"),
        (publish_feed_health.DIRNAME, ".csv"),
        (publish_machine.DIRNAME, ".csv"),
        (publish_span_rollup.DIRNAME, ".csv"),
        (publish_day_metrics.PUBLIC_DIRNAME, ".json"),
        (publish_run_days.DIRNAME, ".json"),
    ],
)
def test_every_series_is_pruned_to_its_own_knob(
    tree: tuple[Path, Path], dirname: str, suffix: str
) -> None:
    """A producer that wrote without pruning would be the growing cost Rule #12
    refuses: a directory that gains a file a month and loses none."""
    state, digest = tree
    _publish_all(state, digest, months=None)

    kept = publish_console.published_months(digest, dirname, suffix)

    assert kept == list(MONTHS[-14:]), kept


def test_a_knob_below_one_month_would_delete_the_month_being_written(
    tree: tuple[Path, Path],
) -> None:
    _state, digest = tree
    with pytest.raises(ValueError, match="fewer than one month"):
        publish_console.prune_months(digest, "scores", ".csv", keep_months=0, today=TODAY)


# --- the trust boundary ------------------------------------------------------


def test_the_score_projection_drops_the_address_and_the_fetched_title(
    tree: tuple[Path, Path],
) -> None:
    """`url_key` and `source_url` identify the page rather than the measurement,
    and `title` is fetched text (Rule #11)."""
    state, digest = tree
    _publish_all(state, digest, months=None)

    shard = publish_scores.shard_path(digest, NEWEST)
    with shard.open("r", encoding="utf-8", newline="") as handle:
        header = tuple(csv.DictReader(handle).fieldnames or ())

    assert header == PublicEvalRow.csv_columns()
    assert not (publish_scores.FORBIDDEN_COLUMNS & set(header))
    assert publish_scores.read_shard(shard)[0].item_id == "energy-01"


def test_the_feed_projection_drops_the_hashed_address_and_keeps_our_own_reason(
    tree: tuple[Path, Path],
) -> None:
    state, digest = tree
    _publish_all(state, digest, months=None)

    rows = publish_feed_health.read_shard(publish_feed_health.shard_path(digest, NEWEST))

    assert "endpoint_key" not in PublicFeedRow.csv_columns()
    assert {row.feed_id for row in rows} == {"grid-news", "wire-co"}
    assert [row.detail for row in rows if row.feed_id == "wire-co"] == [
        "our own one-line reason"
    ]


def test_a_published_shard_reads_back_as_it_was_written(tree: tuple[Path, Path]) -> None:
    """A published shard is the one artifact nobody can re-derive once its
    source month is folded away, so reading it back is what says it still
    loads rather than merely still parses."""
    state, digest = tree
    _publish_all(state, digest, months=None)

    assert len(publish_scores.read_shard(publish_scores.shard_path(digest, NEWEST))) == 1
    assert len(publish_span_rollup.read_shard(publish_span_rollup.shard_path(digest, NEWEST))) == 1
    assert len(publish_machine.read_shard(publish_machine.shard_path(digest, NEWEST))) == 2
    assert len(publish_run_days.read_shard(publish_run_days.shard_path(digest, NEWEST))) == 1
    assert (
        len(publish_day_metrics.read_public_shard(publish_day_metrics.public_shard_path(digest, NEWEST)))
        == 1
    )


# --- the run-day reduction ---------------------------------------------------


def test_the_run_day_row_counts_the_page_and_not_the_planner(
    tree: tuple[Path, Path],
) -> None:
    """The manifest records what the planner decided; this records what survived
    to the page. A chart whose render failed is a visual and is not a published
    chart."""
    state, digest = tree
    _publish_all(state, digest, months=None)

    row = publish_run_days.read_shard(publish_run_days.shard_path(digest, NEWEST))[0]

    assert row.date == NEWEST_DAY
    assert row.published_items == 3
    assert row.published_charts == 1
    assert row.models == ["energy-model"]
    assert row.runs[0].planned == 4


def test_a_day_with_no_manifest_costs_the_month_that_day_and_no_more(
    tree: tuple[Path, Path],
) -> None:
    _unused_state, digest = tree
    orphan = digest / NEWEST[:4] / NEWEST[5:7] / "02"
    orphan.mkdir(parents=True)
    (orphan / "digest.json").write_text(
        _day(f"{NEWEST}-02", items=1, charts=0).to_json(), encoding="utf-8"
    )

    publish_run_days.publish(digest_root=digest, keep_months=14, today=TODAY, months=None)

    rows = publish_run_days.read_shard(publish_run_days.shard_path(digest, NEWEST))
    assert [row.date for row in rows] == [NEWEST_DAY]


# --- the band ----------------------------------------------------------------


def _band(state: Path, digest: Path) -> Any:
    _publish_all(state, digest, months=None)
    publish_console_band.publish(
        state_root=state,
        digest_root=digest,
        generated_at=f"{NEWEST_DAY}T19:00:00Z",
        today=TODAY,
        console=CONSOLE,
        run=RUN,
        collect=COLLECT,
    )
    return publish_console_band.read_band(publish_console_band.band_path(digest))


def test_the_band_names_the_newest_day_in_every_sentence(tree: tuple[Path, Path]) -> None:
    """The verdict, the size, the worst fact and the carries all stand on one
    day, so the band cannot name one day in its verdict and another in its
    worst fact."""
    state, digest = tree

    band = _band(state, digest)

    assert band.verdict.date == NEWEST_DAY
    assert band.verdict.sentence.startswith(f"{NEWEST_DAY} ran 1 run and published 3 of 4")
    assert band.verdict.health is Health.AMBER
    assert [square.label for square in band.verdict.runs] == ["Run 1 is worth a look"]
    assert band.months == list(MONTHS[-14:])


def test_a_run_worth_a_look_outranks_a_feed_at_the_same_severity(
    tree: tuple[Path, Path],
) -> None:
    """The runs are listed before the feeds and the order is load-bearing.

    `worst_of` sorts stably, so a tie goes to whichever candidate was built
    first. A rest clears itself after `availability_strikes_before_rest` skips
    where a failed run does not, so listing the feeds first would hand every tie
    to the state that fixes itself.
    """
    state, digest = tree

    band = _band(state, digest)

    pipelines = next(route for route in band.routes if route.id is RouteId.PIPELINES)
    assert pipelines.worst == "1 run worth a look"
    assert band.worst is not None
    assert band.worst.id is RouteId.PIPELINES


def test_a_feed_that_failed_its_way_into_a_rest_is_the_loudest_thing_on_the_strip() -> None:
    """Driven straight from built rows: the ledger the fixture holds is one read
    a month, which is too sparse to reach a rest inside a 90-day window."""
    rows = [
        _feed_row("2026-12", feed_id="wire-co", outcome=FetchOutcome.PERMANENT, items=0).model_copy(
            update={"run_id": f"2026-12-0{n}-1", "date": f"2026-12-0{n}"}
        )
        for n in range(1, 7)
    ]

    trouble = publish_console_band.feed_trouble(rows, COLLECT.availability_strikes_before_rest)
    worst = publish_console_band.worst_of(
        publish_console_band.pipelines_candidates(
            None,
            trouble,
            floor_pct=RUN.success_floor_pct,
            quarantine_after=COLLECT.availability_strikes_before_rest,
        )
    )

    assert trouble.rested == 1
    assert worst is not None
    assert worst.text == "1 feed resting"
    assert "asked again after 5 runs" in worst.sentence


def test_a_feed_read_only_through_a_robots_answer_is_unread_and_not_working() -> None:
    """Until 2026-09-03 a source that gave us no article at all was counted
    among the ones that did not fail."""
    rows = [
        _feed_row(
            "2026-12", feed_id="polite-co", outcome=FetchOutcome.ROBOTS_DENIED, items=0
        ).model_copy(update={"run_id": f"2026-12-0{n}-1", "date": f"2026-12-0{n}"})
        for n in range(1, 4)
    ]

    trouble = publish_console_band.feed_trouble(rows, COLLECT.availability_strikes_before_rest)

    assert (trouble.rested, trouble.failed, trouble.unread) == (0, 0, 1)


def test_the_band_prints_the_size_against_the_cap_with_the_days_it_measured(
    tree: tuple[Path, Path],
) -> None:
    """Rule #10: the number carries what it was measured over."""
    state, digest = tree

    band = _band(state, digest)

    assert band.size.bytes == 1_000_000 + 19 * 30_000
    # Three published days fall inside the 90-day span the widest preset offers,
    # and the oldest of them has no day before it to difference against.
    assert band.size.measured_days == 2
    assert "of the 1 GB limit" in band.size.sentence


def test_a_tree_with_no_run_says_so_rather_than_printing_a_zero(tmp_path: Path) -> None:
    """Null is a designed state. A band that printed 0 MB and a green verdict
    for a tree nothing has published is a lie a reader cannot see through."""
    state = tmp_path / "state"
    digest = tmp_path / "frontend" / "public" / "digest"
    digest.mkdir(parents=True)

    band = _band(state, digest)

    assert band.verdict.date is None
    assert band.verdict.health is Health.AMBER
    assert band.size.bytes is None
    assert band.months == []


def test_a_run_whose_shards_disagree_is_refused_whole(tree: tuple[Path, Path]) -> None:
    """Two servers answered for one shard and neither can be added to the other.
    A page that prints half a reconcilable run is worse than one that says which
    run it cannot read."""
    state, digest = tree
    rows = list(csv.DictReader((state / "runtime-counters.csv").read_text(encoding="utf-8").splitlines()))
    doubled = dict(rows[-1])
    doubled["prompt_tokens_total"] = "999999"
    _write_csv(
        state / "runtime-counters.csv",
        RuntimeCountersRow.csv_columns(),
        [*rows, doubled],
    )

    band = _band(state, digest)

    machine = next(route for route in band.routes if route.id is RouteId.MACHINE)
    assert machine.worst == "1 run cannot be read"


def test_the_band_is_written_only_when_its_bytes_move(tree: tuple[Path, Path]) -> None:
    state, digest = tree
    _publish_all(state, digest, months=None)
    stamp = f"{NEWEST_DAY}T19:00:00Z"
    first = publish_console_band.publish(
        state_root=state,
        digest_root=digest,
        generated_at=stamp,
        today=TODAY,
        console=CONSOLE,
        run=RUN,
        collect=COLLECT,
    )

    again = publish_console_band.publish(
        state_root=state,
        digest_root=digest,
        generated_at=stamp,
        today=TODAY,
        console=CONSOLE,
        run=RUN,
        collect=COLLECT,
    )

    assert first is not None
    assert again is None


def test_the_band_payload_is_small_enough_to_arrive_first(tree: tuple[Path, Path]) -> None:
    """Row 11 asks for at most 8 KB gzipped. Measured here on the raw bytes,
    which is the stricter side of that, so the row's own gate cannot be
    surprised by a shape this one let through."""
    state, digest = tree
    _band(state, digest)

    assert publish_console_band.band_path(digest).stat().st_size <= 8 * 1024


# --- words -------------------------------------------------------------------


def test_a_total_that_rounds_to_nothing_still_says_it_ran() -> None:
    assert publish_console_band.clock(None) is None
    assert publish_console_band.clock(0) is None
    assert publish_console_band.clock(1_000) == "<1 m"
    assert publish_console_band.clock(90 * 60_000) == "1 h 30 m"


def test_a_count_prints_at_the_precision_its_basis_supports() -> None:
    """Three significant figures stops a large answer claiming a hundred
    articles of accuracy nothing measured (Rule #10)."""
    assert publish_console_band.roughly(0) == "0"
    assert publish_console_band.roughly(7) == "7"
    assert publish_console_band.roughly(306_712) == "307,000"


def test_the_band_root_list_and_the_published_series_agree() -> None:
    """One list of roots, so a series added without a seed cannot pass the
    fresh-checkout guard by being absent from it."""
    series = {dirname for dirname, _suffix in publish_console.MONTH_SERIES}

    assert series | {publish_console.CONSOLE_DIRNAME} == set(publish_console.PUBLISHED_ROOTS)


def test_every_published_root_is_derived_from_the_digest_root(tmp_path: Path) -> None:
    """A hard-coded `frontend/public/...` makes a canary build read the real
    tree, and every canary assertion non-deterministic."""
    canary = tmp_path / "canary" / "digest"

    for dirname, suffix in publish_console.MONTH_SERIES:
        path = publish_console.month_path(canary, dirname, "2026-09", suffix)
        assert path.is_relative_to(tmp_path / "canary")
    assert publish_console_band.band_path(canary).is_relative_to(tmp_path / "canary")


def test_the_published_month_file_is_a_list_of_rows_each_carrying_its_stamp(
    tree: tuple[Path, Path],
) -> None:
    """A month of days is fetched as one file, and every row in it validates
    against its own schema (`CLAUDE.md` section 11)."""
    state, digest = tree
    _publish_all(state, digest, months=None)

    payload = json.loads(
        publish_run_days.shard_path(digest, NEWEST).read_text(encoding="utf-8")
    )

    assert isinstance(payload, list)
    assert {row["version"] for row in payload} == {
        __import__("idhazh.contracts.public_run_day", fromlist=["PublicRunDay"])
        .PublicRunDay.schema_version()
    }

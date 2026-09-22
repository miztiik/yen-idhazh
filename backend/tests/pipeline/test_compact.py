"""The closed-day fold: which days it takes, what it leaves, and what it never touches.

Driven by a built day tree, never by the committed one. A built tree carries the
cases the archive has never produced - a straggler arriving after a fold, a day
that crossed the boundary last night, two trees closed on the same date - and it
costs the same on a five-year archive as on a fresh clone (CLAUDE.md section 13).

Settlement itself is not asked here. `day_shards` decides which of two rows wins
a cell and which names it refuses, and `tests/pipeline/test_day_shards.py` holds
those questions. What this file asks is narrower: given a settlement that
already works, which days does the fold take, what does it write, and what does
it delete.
"""

from __future__ import annotations

import csv
from datetime import date as date_type
from datetime import timedelta
from pathlib import Path
from typing import Final

import pytest

from idhazh import day_shards, ledger
from idhazh.contracts.base import ServerJob
from idhazh.contracts.host_fingerprint import HostFingerprintRow
from idhazh.contracts.knobs.run import RunConfig
from idhazh.contracts.span_rollup import RollupSpan, SpanRollupRow
from idhazh.stages import compact

pytestmark = pytest.mark.contract

#: The run's own date every fold below is taken against, and the two days either
#: side of the boundary a seven-day cover draws. `days_in_window` names both
#: ends, so the oldest open day is seven days back and the day before it is the
#: newest day a fold may take.
TODAY: Final = "2026-09-17"
AFTER_DAYS: Final = 7
OLDEST_OPEN: Final = "2026-09-10"
NEWEST_CLOSED: Final = "2026-09-09"
OLDER_CLOSED: Final = "2026-09-04"

#: Every job of one full digest run that draws its own machine and records it:
#: one plan, eight work shards, one assemble. Ten writers, ten files, and one
#: day directory holding all of them.
WRITERS: Final[tuple[tuple[ServerJob, int], ...]] = (
    (ServerJob.PLAN, 0),
    *tuple((ServerJob.WORK, shard) for shard in range(8)),
    (ServerJob.ASSEMBLE, 0),
)


def a_machine(date: str, *, job: ServerJob, shard: int, **cells: object) -> HostFingerprintRow:
    """One machine row, shaped the way the contract's own validators demand."""
    return HostFingerprintRow.model_validate(
        {
            "date": date,
            "run_id": f"{date}-900000001",
            "job": job,
            "shard": shard,
            "fingerprint": "0123456789abcdef",
            "measured_at": f"{date}T00:00:00Z",
            **cells,
        }
    )


def a_span(date: str, *, shard: int, span: RollupSpan, total_ms: int) -> SpanRollupRow:
    """One span fold, shaped the way the contract's own validators demand."""
    return SpanRollupRow.model_validate(
        {
            "date": date,
            "run_id": f"{date}-900000001",
            "shard": shard,
            "span_name": span,
            "count": 1,
            "total_ms": total_ms,
        }
    )


def write(
    state: Path,
    tree: ledger.SegmentLedger,
    rows: list[HostFingerprintRow] | list[SpanRollupRow],
    *,
    date: str,
    run: int = 1,
    attempt: int = 1,
    job: ServerJob = ServerJob.PLAN,
    shard: int = 0,
) -> Path:
    """File one writer's rows the way a job files them, and say where they went.

    The real producer, so every test here starts from a tree a run could have
    left. `run` picks the run of the day, because two runs of one night are the
    case a day directory exists to carry.
    """
    ledger.write_segment(
        state,
        tree,
        rows,
        run_id=f"{date}-90000000{run}",
        attempt=attempt,
        job=job,
        shard=shard,
    )
    return state / tree.value / date[:4] / date[5:7] / date[8:10]


def names_in(day: Path) -> list[str]:
    """Every filename the day directory holds, in name order."""
    return sorted(path.name for path in day.iterdir())


def rows_in(path: Path) -> list[dict[str, str]]:
    """A file's rows, read without newline translation so a CRLF drift shows."""
    with path.open("r", encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def settled_in(state: Path, tree: ledger.SegmentLedger, date: str) -> list[dict[str, str]]:
    """What a reader settles for one day, whichever files the day is holding."""
    return day_shards.settled_day(
        state / tree.value,
        date,
        ledger.segment_key(tree),
        ledger.segment_contract(tree),
    )


def fold(state: Path, *, date: str = TODAY) -> compact.CompactionReport:
    """The fold every test here takes, against the run's own date."""
    return compact.stage_compact(state, date=date, after_days=AFTER_DAYS)


def a_full_run(state: Path, date: str) -> Path:
    """Ten jobs of one run, each filing its own machine into one day."""
    for job, shard in WRITERS:
        write(
            state,
            ledger.SegmentLedger.HOST_FINGERPRINT,
            [a_machine(date, job=job, shard=shard, cpu_model=f"{job.value}-{shard}")],
            date=date,
            job=job,
            shard=shard,
        )
    return state / ledger.HOST_FINGERPRINT_DIRNAME / date[:4] / date[5:7] / date[8:10]


# --- Which days the fold takes -------------------------------------------------


def test_a_store_with_no_days_folds_nothing_and_says_so(tmp_path: Path) -> None:
    """A fresh clone is not a fault, and neither is a store a fold already drained."""
    report = fold(tmp_path / ledger.STATE_DIRNAME)

    assert report == compact.CompactionReport(0, 0, 0, (), None, None)


def test_a_day_older_than_the_cover_folds_into_one_file(tmp_path: Path) -> None:
    """Ten writers leave ten files, and the fold leaves one holding every row.

    Two-sided on purpose. "One file is there" passes on a fold that wrote the
    settled file and kept the ten beside it, which is the shape that costs the
    day its whole reason for folding.
    """
    state = tmp_path / ledger.STATE_DIRNAME
    day = a_full_run(state, NEWEST_CLOSED)
    assert len(names_in(day)) == len(WRITERS)
    before = settled_in(state, ledger.SegmentLedger.HOST_FINGERPRINT, NEWEST_CLOSED)

    report = fold(state)

    assert names_in(day) == [day_shards.SETTLED_NAME]
    assert report.days_folded == 1
    assert report.files_replaced == len(WRITERS)
    assert report.rows_kept == len(WRITERS)
    assert report.trees_touched == (ledger.HOST_FINGERPRINT_DIRNAME,)
    assert rows_in(day / day_shards.SETTLED_NAME) == before


def test_the_oldest_open_day_is_left_alone_and_the_day_before_it_is_taken(
    tmp_path: Path,
) -> None:
    """The boundary, asserted from both sides so an off-by-one cannot pass.

    `run.settled_fold_after_days` names a cover and a cover names both its ends,
    so the oldest open day is `after_days` back from the run's own date. A fold
    that took it would delete files a shard of that day could still be writing.
    """
    state = tmp_path / ledger.STATE_DIRNAME
    open_day = a_full_run(state, OLDEST_OPEN)
    closed_day = a_full_run(state, NEWEST_CLOSED)

    report = fold(state)

    assert len(names_in(open_day)) == len(WRITERS), "a day a shard could still write was folded"
    assert names_in(closed_day) == [day_shards.SETTLED_NAME]
    assert report.days_folded == 1
    assert report.oldest_day_folded == NEWEST_CLOSED
    assert report.newest_day_folded == NEWEST_CLOSED


def test_the_cover_is_counted_back_from_the_date_it_is_given(tmp_path: Path) -> None:
    """A run that crosses midnight folds the days its own rows were written against.

    The same tree, folded twice against two dates a week apart. Counted from the
    clock instead, both passes would answer the same and the day the earlier run
    must not touch would go.
    """
    state = tmp_path / ledger.STATE_DIRNAME
    day = a_full_run(state, NEWEST_CLOSED)

    earlier = fold(state, date=OLDEST_OPEN)

    assert earlier.days_folded == 0
    assert len(names_in(day)) == len(WRITERS)

    later = fold(state, date=TODAY)

    assert later.days_folded == 1
    assert names_in(day) == [day_shards.SETTLED_NAME]


def test_every_closed_day_goes_in_one_pass_and_the_report_names_both_ends(
    tmp_path: Path,
) -> None:
    """A run whose predecessor never folded catches up rather than taking one day."""
    state = tmp_path / ledger.STATE_DIRNAME
    older = a_full_run(state, OLDER_CLOSED)
    newer = a_full_run(state, NEWEST_CLOSED)

    report = fold(state)

    assert names_in(older) == [day_shards.SETTLED_NAME]
    assert names_in(newer) == [day_shards.SETTLED_NAME]
    assert report.days_folded == 2
    assert report.oldest_day_folded == OLDER_CLOSED
    assert report.newest_day_folded == NEWEST_CLOSED


def test_two_trees_closed_on_one_day_are_both_named(tmp_path: Path) -> None:
    """Every ledger is folded, not the first one that has a closed day.

    `trees_touched` is what an operator reads to know which stores moved, so a
    tree that folded and was not named is a diff nobody can account for.
    """
    state = tmp_path / ledger.STATE_DIRNAME
    machines = a_full_run(state, NEWEST_CLOSED)
    spans = write(
        state,
        ledger.SegmentLedger.SPAN_ROLLUP,
        [a_span(NEWEST_CLOSED, shard=0, span=RollupSpan.ITEM, total_ms=900)],
        date=NEWEST_CLOSED,
        job=ServerJob.WORK,
    )

    report = fold(state)

    assert names_in(machines) == [day_shards.SETTLED_NAME]
    assert names_in(spans) == [day_shards.SETTLED_NAME]
    assert report.trees_touched == tuple(
        sorted((ledger.HOST_FINGERPRINT_DIRNAME, ledger.SPAN_ROLLUP_DIRNAME))
    )
    assert report.days_folded == 1, "one date, whichever trees recorded it"


# --- What a second fold does ---------------------------------------------------


def test_a_day_already_folded_is_never_folded_again(tmp_path: Path) -> None:
    """The second fold writes nothing, so a run that folds every day makes no diff.

    A byte comparison, because "the rows are the same" passes on a rewrite that
    reordered them - and a rewrite that reorders them is a diff on every run,
    which is the whole cost the fold exists to avoid.
    """
    state = tmp_path / ledger.STATE_DIRNAME
    day = a_full_run(state, NEWEST_CLOSED)
    fold(state)
    written = (day / day_shards.SETTLED_NAME).read_bytes()

    again = fold(state)

    assert again == compact.CompactionReport(0, 0, 0, (), None, None)
    assert (day / day_shards.SETTLED_NAME).read_bytes() == written


def test_a_straggler_that_lands_after_a_fold_is_folded_into_the_file_beside_it(
    tmp_path: Path,
) -> None:
    """A re-run of a closed day writes one more file, and the next fold takes it in.

    The case a fold that skipped any day holding `settled.csv` would lose. The
    straggler's rows have to survive, and the settled file it sits beside has to
    keep the rows it already held.
    """
    state = tmp_path / ledger.STATE_DIRNAME
    day = a_full_run(state, NEWEST_CLOSED)
    fold(state)
    write(
        state,
        ledger.SegmentLedger.HOST_FINGERPRINT,
        [a_machine(NEWEST_CLOSED, job=ServerJob.WORK, shard=9, cpu_model="a late shard")],
        date=NEWEST_CLOSED,
        run=2,
        job=ServerJob.WORK,
        shard=9,
    )
    assert len(names_in(day)) == 2

    report = fold(state)

    assert names_in(day) == [day_shards.SETTLED_NAME]
    assert report.days_folded == 1
    assert report.files_replaced == 1, (
        "the settled file is rewritten rather than deleted, so only the straggler goes"
    )
    machines = [row["cpu_model"] for row in rows_in(day / day_shards.SETTLED_NAME)]
    assert "a late shard" in machines
    assert len(machines) == len(WRITERS) + 1


def test_the_fold_changes_no_answer(tmp_path: Path) -> None:
    """A folded day and an unfolded day read identically, which is what makes it safe.

    The whole licence for folding at all. Taken through the reader every
    consumer uses rather than by comparing files, because the claim is about
    what a reader gets and not about how many files it opened to get it.
    """
    state = tmp_path / ledger.STATE_DIRNAME
    write(
        state,
        ledger.SegmentLedger.HOST_FINGERPRINT,
        [a_machine(NEWEST_CLOSED, job=ServerJob.PLAN, shard=0, cpu_model="the first try")],
        date=NEWEST_CLOSED,
        attempt=1,
    )
    write(
        state,
        ledger.SegmentLedger.HOST_FINGERPRINT,
        [a_machine(NEWEST_CLOSED, job=ServerJob.PLAN, shard=0, cpu_model="the second try")],
        date=NEWEST_CLOSED,
        attempt=2,
    )
    before = settled_in(state, ledger.SegmentLedger.HOST_FINGERPRINT, NEWEST_CLOSED)
    assert [row["cpu_model"] for row in before] == ["the second try"], (
        "the fixture has to carry a correction or this proves nothing"
    )

    fold(state)

    assert settled_in(state, ledger.SegmentLedger.HOST_FINGERPRINT, NEWEST_CLOSED) == before


# --- Which days a tree says it has ---------------------------------------------


def test_every_day_a_tree_recorded_is_listed_once_and_oldest_first(tmp_path: Path) -> None:
    """The fold's own listing, and a day with ten files is still one day."""
    state = tmp_path / ledger.STATE_DIRNAME
    a_full_run(state, NEWEST_CLOSED)
    a_full_run(state, OLDER_CLOSED)

    assert compact.recorded_days(state / ledger.HOST_FINGERPRINT_DIRNAME) == [
        OLDER_CLOSED,
        NEWEST_CLOSED,
    ]


def test_a_tree_that_was_never_written_lists_no_days(tmp_path: Path) -> None:
    """A store a clone has never run is not a fault."""
    assert compact.recorded_days(tmp_path / ledger.HOST_FINGERPRINT_DIRNAME) == []


def test_a_day_a_fold_already_settled_is_still_a_day_the_tree_recorded(
    tmp_path: Path,
) -> None:
    """The listing reads both shapes, so a folded day does not vanish from it.

    A folded day that stopped being listed would never be offered a straggler's
    fold, and the straggler's rows would sit unfolded for ever.
    """
    state = tmp_path / ledger.STATE_DIRNAME
    a_full_run(state, NEWEST_CLOSED)
    fold(state)

    assert compact.recorded_days(state / ledger.HOST_FINGERPRINT_DIRNAME) == [NEWEST_CLOSED]


# --- The knob ------------------------------------------------------------------


def test_the_cover_a_fresh_clone_folds_on_is_a_week() -> None:
    """A default is a promise, so the number a clone runs on is asserted, not assumed.

    Seven days: long enough that a day a slow re-run is still writing is never
    taken, short enough that a day's hundred small files do not sit for a month.
    """
    assert RunConfig().settled_fold_after_days == AFTER_DAYS
    assert (
        date_type.fromisoformat(TODAY) - date_type.fromisoformat(OLDEST_OPEN)
    ) == timedelta(days=AFTER_DAYS), "the fixture's boundary and the knob disagree"

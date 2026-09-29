"""Which closed days does the gardener's fold settle, what does it leave, and what does it never touch?

Driven by built day trees and by the fixtures under `tests/fixtures/day-shards/`,
never by the committed archive. A built tree carries the cases the archive has
never produced - a straggler after a fold, a day that closed at midnight, two
trees closed on one date - and it costs the same on a five-year archive as on a
fresh clone (CLAUDE.md section 13).

Settlement itself is not asked here: `tests/pipeline/test_day_shards.py` holds
which of two rows wins a cell. What this file asks is narrower - given a
settlement that works, which days the fold takes, what it writes, and what it
deletes.

A day is closed once one whole day has passed since it ended, measured from
00:00 UTC on the wake's own day. So at a wake on the 17th, the 15th is the
newest closed day and the 16th is still open.
"""

from __future__ import annotations

import csv
import shutil
from datetime import UTC, date, datetime, time
from pathlib import Path
from typing import Final

import pytest
from conftest import FIXTURES_DIR

from idhazh import day_shards, ledger
from idhazh.contracts.base import ServerJob
from idhazh.contracts.host_fingerprint import HostFingerprintRow
from idhazh.contracts.knobs.collect import UNBOUNDED_WINDOW
from idhazh.contracts.knobs.gardener import DEFAULT_CLOSED_AFTER_DAYS
from idhazh.contracts.ledger_name import DAY_TREES, LedgerName
from idhazh.contracts.span_rollup import RollupSpan, SpanRollupRow
from idhazh.gardener import closed_day_fold
from idhazh.gardener.closed_day_fold import Folded, FoldInterruptedError

pytestmark = pytest.mark.contract

#: The wake every fold below is taken at, and the two days either side of the
#: line it draws.
WAKE: Final = "2026-09-17"
OLDEST_OPEN: Final = "2026-09-16"
NEWEST_CLOSED: Final = "2026-09-15"
OLDER_CLOSED: Final = "2026-09-04"

#: Every job of one full digest run that records a machine: one plan, eight work
#: shards, one assemble. Ten writers, ten files, one day directory.
WRITERS: Final[tuple[tuple[ServerJob, int], ...]] = (
    (ServerJob.PLAN, 0),
    *tuple((ServerJob.WORK, shard) for shard in range(8)),
    (ServerJob.ASSEMBLE, 0),
)

DAY_SHARDS: Final = FIXTURES_DIR / "day-shards"


def midnight(day: str) -> datetime:
    """00:00 UTC on a day, the instant a wake measures from."""
    return datetime.combine(date.fromisoformat(day), time.min, tzinfo=UTC)


def fold(
    state: Path,
    *,
    wake: str = WAKE,
    dry_run: bool = False,
    skip: frozenset[Path] = frozenset(),
) -> Folded:
    """The fold every test here takes: every tree, at a wake, with the default rule."""
    return closed_day_fold.fold(
        state,
        DAY_TREES,
        now=midnight(wake),
        after_days=DEFAULT_CLOSED_AFTER_DAYS,
        dry_run=dry_run,
        skip=skip,
    )


def a_machine(day: str, *, job: ServerJob, shard: int, **cells: object) -> HostFingerprintRow:
    """One machine row, shaped the way the contract's own validators demand."""
    return HostFingerprintRow.model_validate(
        {
            "date": day,
            "run_id": f"{day}-900000001",
            "job": job,
            "shard": shard,
            "fingerprint": "0123456789abcdef",
            "measured_at": f"{day}T00:00:00Z",
            **cells,
        }
    )


def a_span(day: str, *, shard: int, span: RollupSpan, total_ms: int) -> SpanRollupRow:
    """One span total, shaped the way the contract's own validators demand."""
    return SpanRollupRow.model_validate(
        {
            "date": day,
            "run_id": f"{day}-900000001",
            "shard": shard,
            "span_name": span,
            "count": 1,
            "total_ms": total_ms,
        }
    )


def write(
    state: Path,
    tree: LedgerName,
    rows: list[HostFingerprintRow] | list[SpanRollupRow],
    *,
    day: str,
    run: int = 1,
    attempt: int = 1,
    job: ServerJob = ServerJob.PLAN,
    shard: int = 0,
) -> Path:
    """File one writer's rows the way a job files them, and say which day folder they went to."""
    ledger.write_segment(
        state,
        tree,
        rows,
        run_id=f"{day}-90000000{run}",
        attempt=attempt,
        job=job,
        shard=shard,
    )
    return ledger.path(state, tree, day)


def a_full_run(state: Path, day: str) -> Path:
    """Ten jobs of one run, each filing its own machine into one day."""
    for job, shard in WRITERS:
        write(
            state,
            LedgerName.HOST_FINGERPRINT,
            [a_machine(day, job=job, shard=shard, cpu_model=f"{job.value}-{shard}")],
            day=day,
            job=job,
            shard=shard,
        )
    return ledger.path(state, LedgerName.HOST_FINGERPRINT, day)


def names_in(folder: Path) -> list[str]:
    return sorted(path.name for path in folder.iterdir())


def rows_in(path: Path) -> list[dict[str, str]]:
    """A file's rows, read without newline translation so a CRLF drift shows."""
    with path.open("r", encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def settled_in(state: Path, tree: LedgerName, day: str) -> list[dict[str, str]]:
    """What a reader settles for one day, whichever files the day is holding."""
    return day_shards.settled_day(
        ledger.tree_root(state, tree), day, ledger.segment_key(tree), ledger.segment_contract(tree)
    )


def every_day(state: Path) -> dict[tuple[LedgerName, str], list[dict[str, str]]]:
    """Every recorded day of every tree, as a reader settles it.

    The whole tree, because the claim is about every day in it - and the tree is
    one built here, so the read costs the same whatever the archive holds.
    """
    answers: dict[tuple[LedgerName, str], list[dict[str, str]]] = {}
    for tree in DAY_TREES:
        root = ledger.tree_root(state, tree)
        for days in day_shards.dates_by_month(root, days=UNBOUNDED_WINDOW).values():
            for day in days:
                answers[(tree, day)] = settled_in(state, tree, day)
    return answers


def the_fixture_tree(root: Path) -> Path:
    """Three committed day fixtures copied into one state tree, and that tree.

    Six writer files over three machine days, three writer files of one span day
    where a second attempt corrects the first, and one span day an earlier fold
    already settled with a straggler and a pre-partition head beside it.
    """
    state = root / ledger.STATE_DIRNAME
    shutil.copytree(DAY_SHARDS / "closed-day" / ledger.STATE_DIRNAME, state)
    shutil.copytree(
        DAY_SHARDS / "writer-files" / "span-rollup",
        ledger.tree_root(state, LedgerName.SPAN_ROLLUP),
        dirs_exist_ok=True,
    )
    shutil.copytree(
        DAY_SHARDS / "migrated-day" / "span-rollup",
        ledger.tree_root(state, LedgerName.SPAN_ROLLUP),
        dirs_exist_ok=True,
    )
    return state


# --- The oracle ----------------------------------------------------------------


def test_the_fold_changes_no_answer_and_never_touches_an_open_day(tmp_path: Path) -> None:
    """Every day reads the same rows before and after, and the open day keeps its bytes.

    The whole licence for folding at all, taken through the reader every consumer
    uses rather than by comparing files: the claim is about what a reader gets,
    not how many files it opened to get it.
    """
    state = the_fixture_tree(tmp_path)
    wake = "2026-09-22"
    open_day = write(
        state,
        LedgerName.SPAN_ROLLUP,
        [a_span("2026-09-21", shard=0, span=RollupSpan.ITEM, total_ms=700)],
        day="2026-09-21",
        job=ServerJob.WORK,
    )
    open_bytes = {path.name: path.read_bytes() for path in open_day.iterdir()}
    before = every_day(state)
    assert len(before) == 6, "the fixture tree has to carry six days or this proves less"

    folded = fold(state, wake=wake)

    assert every_day(state) == before
    assert {path.name: path.read_bytes() for path in open_day.iterdir()} == open_bytes
    assert sorted((day.tree, day.day) for day in folded.days) == sorted(
        key for key in before if key[1] != "2026-09-21"
    )
    for day in folded.days:
        assert names_in(day.folder) == [day_shards.SETTLED_NAME]


# --- Which days the fold takes ---------------------------------------------------


def test_a_tree_with_no_days_folds_nothing_and_says_so(tmp_path: Path) -> None:
    """A fresh clone is not a fault, and neither is a tree a fold already drained."""
    assert fold(tmp_path / ledger.STATE_DIRNAME) == Folded(dry_run=False)


def test_a_closed_day_folds_into_one_file_holding_every_row(tmp_path: Path) -> None:
    """Ten writers leave ten files, and the fold leaves one holding every row.

    Two-sided on purpose: "one file is there" passes on a fold that wrote the
    settled file and kept the ten beside it.
    """
    state = tmp_path / ledger.STATE_DIRNAME
    day = a_full_run(state, NEWEST_CLOSED)
    before = settled_in(state, LedgerName.HOST_FINGERPRINT, NEWEST_CLOSED)

    folded = fold(state)

    assert names_in(day) == [day_shards.SETTLED_NAME]
    assert [(settled.tree, settled.day) for settled in folded.days] == [
        (LedgerName.HOST_FINGERPRINT, NEWEST_CLOSED)
    ]
    assert folded.files == len(WRITERS)
    assert rows_in(day / day_shards.SETTLED_NAME) == before


def test_the_newest_open_day_is_left_alone_and_the_day_before_it_is_taken(
    tmp_path: Path,
) -> None:
    """The line, asserted from both sides so an off-by-one cannot pass.

    The day before the wake ended at 00:00 UTC on the wake's own day, so no whole
    day has passed since and a re-run could still be writing it.
    """
    state = tmp_path / ledger.STATE_DIRNAME
    open_day = a_full_run(state, OLDEST_OPEN)
    closed_day = a_full_run(state, NEWEST_CLOSED)

    folded = fold(state)

    assert len(names_in(open_day)) == len(WRITERS), "a day a re-run could still write was folded"
    assert names_in(closed_day) == [day_shards.SETTLED_NAME]
    assert [settled.day for settled in folded.days] == [NEWEST_CLOSED]


def test_which_days_are_closed_is_measured_from_the_instant_handed_in(tmp_path: Path) -> None:
    """The same tree at two wakes a day apart, so the clock can decide nothing."""
    state = tmp_path / ledger.STATE_DIRNAME
    day = a_full_run(state, NEWEST_CLOSED)

    assert fold(state, wake="2026-09-16").days == ()
    assert len(names_in(day)) == len(WRITERS)

    assert [settled.day for settled in fold(state, wake=WAKE).days] == [NEWEST_CLOSED]
    assert names_in(day) == [day_shards.SETTLED_NAME]


def test_every_closed_day_goes_in_one_pass_so_a_missed_wake_catches_up(tmp_path: Path) -> None:
    """A wake after one that did not fold takes every day still waiting, oldest first."""
    state = tmp_path / ledger.STATE_DIRNAME
    older = a_full_run(state, OLDER_CLOSED)
    newer = a_full_run(state, NEWEST_CLOSED)

    folded = fold(state)

    assert names_in(older) == names_in(newer) == [day_shards.SETTLED_NAME]
    assert [settled.day for settled in folded.days] == [OLDER_CLOSED, NEWEST_CLOSED]


def test_two_trees_closed_on_one_day_are_both_folded(tmp_path: Path) -> None:
    """Every tree it is handed is folded, not the first one with a closed day."""
    state = tmp_path / ledger.STATE_DIRNAME
    machines = a_full_run(state, NEWEST_CLOSED)
    spans = write(
        state,
        LedgerName.SPAN_ROLLUP,
        [a_span(NEWEST_CLOSED, shard=0, span=RollupSpan.ITEM, total_ms=900)],
        day=NEWEST_CLOSED,
        job=ServerJob.WORK,
    )

    folded = fold(state)

    assert names_in(machines) == names_in(spans) == [day_shards.SETTLED_NAME]
    assert sorted(settled.tree for settled in folded.days) == sorted(
        (LedgerName.HOST_FINGERPRINT, LedgerName.SPAN_ROLLUP)
    )


def test_only_the_trees_handed_in_are_folded(tmp_path: Path) -> None:
    """A task folds the trees it walks, so a tree another task owns is left to that task."""
    state = tmp_path / ledger.STATE_DIRNAME
    machines = a_full_run(state, NEWEST_CLOSED)
    spans = write(
        state,
        LedgerName.SPAN_ROLLUP,
        [a_span(NEWEST_CLOSED, shard=0, span=RollupSpan.ITEM, total_ms=900)],
        day=NEWEST_CLOSED,
        job=ServerJob.WORK,
    )

    closed_day_fold.fold(
        state,
        [LedgerName.SPAN_ROLLUP],
        now=midnight(WAKE),
        after_days=DEFAULT_CLOSED_AFTER_DAYS,
        dry_run=False,
    )

    assert names_in(spans) == [day_shards.SETTLED_NAME]
    assert len(names_in(machines)) == len(WRITERS)


def test_a_day_folder_the_window_took_is_left_to_the_window(tmp_path: Path) -> None:
    """The window goes first, so a day it is removing is never written by the fold."""
    state = tmp_path / ledger.STATE_DIRNAME
    taken = a_full_run(state, OLDER_CLOSED)
    kept = a_full_run(state, NEWEST_CLOSED)

    folded = fold(state, skip=frozenset({taken}))

    assert len(names_in(taken)) == len(WRITERS)
    assert names_in(kept) == [day_shards.SETTLED_NAME]
    assert [settled.day for settled in folded.days] == [NEWEST_CLOSED]


# --- A dry run, and a fold that stops -----------------------------------------------


def test_a_dry_run_settles_every_day_it_would_fold_and_changes_nothing(tmp_path: Path) -> None:
    """The list a person reads before turning a fold live is the list the live fold takes."""
    state = tmp_path / ledger.STATE_DIRNAME
    day = a_full_run(state, NEWEST_CLOSED)
    before = {path.name: path.read_bytes() for path in day.iterdir()}

    rehearsed = fold(state, dry_run=True)

    assert {path.name: path.read_bytes() for path in day.iterdir()} == before
    assert rehearsed.dry_run is True
    assert [settled.day for settled in rehearsed.days] == [NEWEST_CLOSED]
    assert rehearsed.files == len(WRITERS)
    assert fold(state).days == rehearsed.days


def test_a_row_that_will_not_read_stops_the_fold_and_carries_the_days_before_it(
    tmp_path: Path,
) -> None:
    """The days settled before the failure stand, and the failed day keeps every file.

    A dry run reads the same rows, so it stops on the same day.
    """
    state = tmp_path / ledger.STATE_DIRNAME
    good = a_full_run(state, OLDER_CLOSED)
    bad = a_full_run(state, NEWEST_CLOSED)
    victim = sorted(bad.iterdir())[0]
    with victim.open("a", encoding="utf-8", newline="") as handle:
        handle.write("not,a,machine\n")

    with pytest.raises(FoldInterruptedError, match=f"host-fingerprint {NEWEST_CLOSED}") as stop:
        fold(state)

    assert stop.value.so_far.failed is True
    assert [settled.day for settled in stop.value.so_far.days] == [OLDER_CLOSED]
    assert names_in(good) == [day_shards.SETTLED_NAME]
    assert len(names_in(bad)) == len(WRITERS)


# --- What a second fold does -----------------------------------------------------


def test_a_day_already_folded_is_never_folded_again(tmp_path: Path) -> None:
    """The second fold writes nothing, so a wake that folds every day makes no diff.

    A byte comparison, because "the rows are the same" passes on a rewrite that
    reordered them - and that rewrite would be a diff on every wake.
    """
    state = tmp_path / ledger.STATE_DIRNAME
    day = a_full_run(state, NEWEST_CLOSED)
    fold(state)
    written = (day / day_shards.SETTLED_NAME).read_bytes()

    assert fold(state) == Folded(dry_run=False)
    assert (day / day_shards.SETTLED_NAME).read_bytes() == written


def test_a_straggler_that_lands_after_a_fold_is_folded_into_the_file_beside_it(
    tmp_path: Path,
) -> None:
    """A re-run of a closed day writes one more file, and the next wake takes it in."""
    state = tmp_path / ledger.STATE_DIRNAME
    day = a_full_run(state, NEWEST_CLOSED)
    fold(state)
    write(
        state,
        LedgerName.HOST_FINGERPRINT,
        [a_machine(NEWEST_CLOSED, job=ServerJob.WORK, shard=9, cpu_model="a late shard")],
        day=NEWEST_CLOSED,
        run=2,
        job=ServerJob.WORK,
        shard=9,
    )
    assert len(names_in(day)) == 2

    folded = fold(state)

    assert names_in(day) == [day_shards.SETTLED_NAME]
    assert folded.files == 1, "the settled file is rewritten, so only the straggler goes"
    machines = [row["cpu_model"] for row in rows_in(day / day_shards.SETTLED_NAME)]
    assert "a late shard" in machines
    assert len(machines) == len(WRITERS) + 1


def test_two_folds_of_one_closed_day_write_the_same_bytes(tmp_path: Path) -> None:
    """A fold is a function of the files it read, so folding the same day twice agrees.

    Compared byte for byte rather than row for row: a fold that agreed on the rows
    and disagreed on their order would be a diff every time it ran again.
    """
    first = the_fixture_tree(tmp_path / "first")
    second = the_fixture_tree(tmp_path / "second")

    fold(first, wake="2026-09-22")
    fold(second, wake="2026-09-22")

    def files_under(root: Path) -> dict[str, bytes]:
        return {
            path.relative_to(root).as_posix(): path.read_bytes()
            for path in sorted(root.rglob("*"))
            if path.is_file()
        }

    written = files_under(first)
    assert written, "the fixture folded to nothing, so this compared two empty trees"
    assert written == files_under(second)
    assert all(Path(relpath).name == day_shards.SETTLED_NAME for relpath in written)

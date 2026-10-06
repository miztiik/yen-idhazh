"""Does one compaction pass keep every row, read every date from one file, and say what it did?

The compaction is one task a ledger. These tests run the shipped task, found
through the registry the way the runner finds it, live over trees built under
`tmp_path` through the ledger door - the declarations ship `dry_run: true`, and
a test turns that off for itself only. Each oracle is named where it is
checked: a compact file holds exactly what settling its raw files gives; after
every pass the newest day the daily index names is the daily watermark; every
date is read from exactly one file, and a day lost with its file is named in
its closed month; a file that cannot be read is moved under set-aside at its
old path and counted, and the rest of its period packs; a day holding more raw
files than one period is built from packs the most and leaves the rest for the
next wake; a re-run that lands after its day was compacted replaces its first
attempt; a re-run that lands after its month closed re-opens the month,
which then holds what packing the late day first would have held; no pass
writes a path it deletes; each month past the monthly window is dropped once,
oldest first and at most `max_periods_per_run` a wake, by its listed paths and
unread; and a monthly window that only reports keeps every file it would drop,
packs the rest exactly as a live one would, and counts what it kept in
`selected`.

Nothing here reads the committed `state/` or a clock the test did not set
(CLAUDE.md sections 2 and 13).
"""

from __future__ import annotations

import json
import logging
import shutil
from datetime import UTC, date, datetime, time, timedelta
from pathlib import Path
from typing import Any, Final

import pytest
from conftest import CONFIG_DIR, CONTRACT_FIXTURES_DIR, read_text, seed_scores

from idhazh import ledger, month_partition
from idhazh.contracts.base import ServerJob
from idhazh.contracts.collection_prune import CollectionPruneRow, StopReason
from idhazh.contracts.eval_row import EvalRow
from idhazh.contracts.file_envelope import Period, WriterIdentity
from idhazh.contracts.gardener_fault import RecoveryNote
from idhazh.contracts.knobs.gardener import MonthsWindow
from idhazh.contracts.ledger_index import CompactEntry, CompactIndex, EntryState, Watermark
from idhazh.contracts.ledger_name import LedgerName
from idhazh.contracts.ledgers import LedgersConfig
from idhazh.contracts.visual_prune import VisualPruneRow
from idhazh.gardener import report, schedule
from idhazh.gardener.one_at_a_time import Pass
from idhazh.gardener.tasks import _monthly_period
from idhazh.ledger import paths

from ._task import context_for, run_task

pytestmark = pytest.mark.contract

VISUALS: Final = LedgerName.VISUAL_PRUNES
GARDENER: Final = LedgerName.GARDENER


def a_pass(on: str, *, run: str = "1", before: int = 1000) -> VisualPruneRow:
    """One reporting cleanup pass on one day."""
    return VisualPruneRow(
        version=VisualPruneRow.schema_version(),
        date=on,
        run_id=f"{on}-{run}",
        policy_months=-1,
        max_deletes_per_run=200,
        dry_run=True,
        candidates_found=0,
        deleted=0,
        skipped_by_fuse=0,
        fuse_tripped=False,
        bytes_reclaimed=0,
        oldest_kept=None,
        payload_bytes_before=before,
        payload_bytes_after=before,
    )


def filed(root: Path, row: VisualPruneRow, *, attempt: int = 1) -> Path:
    """One raw file of the cleanup report, through the door, as its own run files it."""
    (written,) = ledger.persist(
        root / ledger.STATE_DIRNAME,
        [row],
        ledger=VISUALS,
        covers=row.date,
        identity=WriterIdentity(
            run_id=row.run_id,
            attempt=attempt,
            job=ServerJob.RUN_TASKS,
            shard=0,
            producer="gardener.tasks.visual_prune",
            git_sha="a" * 40,
        ),
    )
    return written


def compact(root: Path, today: date, *, task: str = "compact-visual-prunes", **knobs: Any) -> Pass:
    """One live pass of a shipped compaction over this checkout, with these knobs changed."""
    return run_task(task, root, today=today, dry_run=False, **knobs)


def state(root: Path) -> Path:
    return root / ledger.STATE_DIRNAME


def daily_covers(root: Path, which: LedgerName = VISUALS) -> list[str]:
    """What the daily index names, oldest first."""
    index = CompactIndex.read(ledger.compact_index_path(state(root), which, Period.DAILY))
    return [entry.covers for entry in index.entries]


def monthly_covers(root: Path) -> list[str]:
    """What the monthly index names, oldest first."""
    index = CompactIndex.read(ledger.compact_index_path(state(root), VISUALS, Period.MONTHLY))
    return [entry.covers for entry in index.entries]


def watermark(root: Path, period: Period, which: LedgerName = VISUALS) -> str | None:
    path = ledger.watermark_path(state(root), which, period)
    return Watermark.read(path).through if path.is_file() else None


def compact_rows(root: Path, period: Period, covers: str) -> list[VisualPruneRow]:
    found = ledger.compact_file(state(root), VISUALS, period, covers)
    assert found is not None, f"no {period.value} file covers {covers}"
    return ledger.load([found], model=VisualPruneRow)


def files_under(root: Path) -> dict[str, bytes]:
    return {
        path.relative_to(root).as_posix(): path.read_bytes()
        for path in sorted(root.rglob("*"))
        if path.is_file()
    }


def days(first: str, last: str) -> list[str]:
    start, end = date.fromisoformat(first), date.fromisoformat(last)
    return [(start + timedelta(days=step)).isoformat() for step in range((end - start).days + 1)]


def disjoint(outcome: Pass) -> bool:
    """What the shard that lands a pass requires: no path both written and deleted."""
    return set(outcome.written).isdisjoint(outcome.taken)


# --- the day: what a compact file holds ------------------------------------------


def test_the_shipped_score_task_refreshes_the_console_files_without_a_live_override(
    tmp_path: Path,
) -> None:
    """New scores reach packed files on consecutive wakes, with no row changed or lost."""
    root = tmp_path / "checkout"
    which = LedgerName.SUMMARY_QUALITY_EVALS
    template = EvalRow.read(CONTRACT_FIXTURES_DIR / "eval-row" / "high.json")
    rows = [
        EvalRow.model_validate(
            {
                **template.model_dump(mode="json"),
                "date": on,
                "run_id": f"{on}-1",
                "scored_at": f"{on}T06:18:02Z",
            }
        )
        for on in ("2026-10-01", "2026-10-02", "2026-10-03")
    ]
    for row in rows:
        seed_scores(state(root), [row], run_id=row.run_id)

    first = run_task("compact-summary-quality-evals", root, today=date(2026, 10, 4))

    assert not first.dry_run and first.stopped_because is StopReason.EXHAUSTED
    assert watermark(root, Period.DAILY, which) == "2026-10-02"
    for row in rows[:2]:
        packed = ledger.compact_path(state(root), which, Period.DAILY, row.date)
        assert ledger.load([packed], model=EvalRow) == [row]
        assert ledger.list_raw_files(state(root), which, days={row.date}) == []
    pending = ledger.list_raw_files(state(root), which, days={rows[2].date})
    assert len(pending) == 1

    second = run_task("compact-summary-quality-evals", root, today=date(2026, 10, 5))

    assert not second.dry_run and second.stopped_because is StopReason.EXHAUSTED
    assert watermark(root, Period.DAILY, which) == "2026-10-03"
    assert ledger.load_days(state(root), which, {row.date for row in rows}, model=EvalRow) == rows
    assert ledger.list_raw_files(state(root), which, days={rows[2].date}) == []
    assert disjoint(first) and disjoint(second)


def test_a_compact_day_holds_exactly_what_settling_its_raw_files_gives_in_the_same_order(
    tmp_path: Path,
) -> None:
    """The oracle: nobody who reads a compact file has to settle it again."""
    root = tmp_path / "checkout"
    filed(root, a_pass("2026-09-20", run="1", before=100), attempt=1)
    filed(root, a_pass("2026-09-20", run="1", before=150), attempt=2)
    filed(root, a_pass("2026-09-20", run="2", before=200))
    filed(root, a_pass("2026-09-21", run="3", before=300))
    before = tmp_path / "before"
    shutil.copytree(root, before)

    outcome = compact(root, date(2026, 9, 23), max_periods_per_run=31)

    for day in ("2026-09-20", "2026-09-21"):
        settled = ledger.load_current_rows(
            state(before), VISUALS, model=VisualPruneRow, key=ledger.VISUAL_PRUNE_KEY, days={day}
        )
        assert compact_rows(root, Period.DAILY, day) == settled
    assert [row.payload_bytes_before for row in compact_rows(root, Period.DAILY, "2026-09-20")] == [
        150,
        200,
    ]
    assert ledger.list_raw_files(state(root), VISUALS) == []
    assert outcome.stopped_because is StopReason.EXHAUSTED and disjoint(outcome)


def test_a_first_pass_starts_at_its_oldest_raw_day_and_a_quiet_day_has_no_file(
    tmp_path: Path,
) -> None:
    """No day before the first raw day is recorded, and a day with no row is an entry with no file."""
    root = tmp_path / "checkout"
    filed(root, a_pass("2026-09-20"))

    compact(root, date(2026, 9, 23), max_periods_per_run=31)

    index = CompactIndex.read(ledger.compact_index_path(state(root), VISUALS, Period.DAILY))
    assert [entry.covers for entry in index.entries] == ["2026-09-20", "2026-09-21"]
    assert compact_rows(root, Period.DAILY, "2026-09-20") == [a_pass("2026-09-20")]
    assert index.entries[1] == CompactEntry(
        covers="2026-09-21", rows=0, bytes=0, state=EntryState.EMPTY
    )
    assert ledger.compact_file(state(root), VISUALS, Period.DAILY, "2026-09-21") is None
    assert ledger.compact_file(state(root), VISUALS, Period.DAILY, "2026-09-01") is None


def chosen_on(caplog: pytest.LogCaptureFixture) -> dict[str, Any]:
    """The periods the pass logged that it chose, as the one line says them, None left out."""
    (said,) = [
        record.getMessage().removeprefix("periods chosen ")
        for record in caplog.records
        if record.getMessage().startswith("periods chosen ")
    ]
    chosen: dict[str, Any] = json.loads(said)
    return chosen


@pytest.mark.parametrize("wake", [False, True], ids=["whole-listing", "wake-listing"])
def test_an_empty_ledger_writes_nothing_and_ends_empty(
    tmp_path: Path, caplog: pytest.LogCaptureFixture, wake: bool
) -> None:
    """The gardener's own ledger, live, before any run has filed a row: there is nothing to work on."""
    root = tmp_path / "checkout"
    state(root).mkdir(parents=True)

    with caplog.at_level(logging.INFO):
        outcome = compact(root, date(2026, 10, 4), task="compact-gardener", wake=wake)

    assert files_under(root) == {}
    assert (outcome.written, outcome.taken, outcome.stopped_because) == (
        (),
        (),
        StopReason.EXHAUSTED,
    )
    chosen = chosen_on(caplog)
    assert (chosen["days"], chosen["months"]) == ({"start": "none"}, {"start": "none"})
    assert "rerun_span" not in chosen


def test_after_every_pass_the_newest_day_the_daily_index_names_is_the_daily_watermark(
    tmp_path: Path,
) -> None:
    """The oracle a browser takes its edge from, a pass whose newest day had no rows included."""
    root = tmp_path / "checkout"
    filed(root, a_pass("2026-09-03"))

    for offset in range(4):
        compact(root, date(2026, 9, 10) + timedelta(days=offset))
        assert daily_covers(root)[-1] == watermark(root, Period.DAILY)
    assert watermark(root, Period.DAILY) == "2026-09-11"
    assert daily_covers(root)[0] == "2026-09-03"
    index = CompactIndex.read(ledger.compact_index_path(state(root), VISUALS, Period.DAILY))
    assert index.entries[-1].state is EntryState.EMPTY
    assert ledger.compact_file(state(root), VISUALS, Period.DAILY, "2026-09-11") is None


def test_a_pass_on_the_25th_takes_the_days_up_to_the_23rd(tmp_path: Path) -> None:
    """One whole day after a day ends, measured from the pass's own UTC day."""
    root = tmp_path / "checkout"
    filed(root, a_pass("2026-09-20"))

    outcome = compact(root, date(2026, 9, 25), max_periods_per_run=31)

    assert outcome.until == "2026-09-23"
    assert watermark(root, Period.DAILY) == "2026-09-23"


def test_a_pass_stops_at_its_budget_and_names_the_day_the_next_one_starts_at(
    tmp_path: Path,
) -> None:
    root = tmp_path / "checkout"
    filed(root, a_pass("2026-09-02"))

    outcome = compact(root, date(2026, 9, 23), max_periods_per_run=2)

    assert (outcome.stopped_because, outcome.resume_from) == (StopReason.CEILING, "2026-09-04")
    assert watermark(root, Period.DAILY) == "2026-09-03"


def test_a_re_run_that_files_fewer_rows_replaces_its_first_attempt_after_the_day_was_compacted(
    tmp_path: Path,
) -> None:
    """The oracle for a re-run: compact attempt 1, file attempt 2, compact again.

    Attempt 1 of one shard recorded two tasks and attempt 2 recorded one. The
    day is rebuilt from its compact rows and the new raw file together, and it
    must equal settling the two raw files - attempt 2's one row, not three.
    """
    root = tmp_path / "checkout"
    day, run = "2026-09-20", "2026-09-20-17000000001"
    first = [
        a_record("seen", run=run, attempt=1, on=day),
        a_record("traces", run=run, attempt=1, on=day),
    ]
    second = [a_record("seen", run=run, attempt=2, on=day)]
    recorded(state(root), first, attempt=1)
    compact(root, date(2026, 9, 23), task="compact-gardener", max_periods_per_run=31)
    recorded(state(root), second, attempt=2)

    outcome = compact(root, date(2026, 9, 24), task="compact-gardener", max_periods_per_run=31)

    both = tmp_path / "both" / ledger.STATE_DIRNAME
    recorded(both, first, attempt=1)
    recorded(both, second, attempt=2)
    settled = ledger.load_current_rows(
        both, GARDENER, model=CollectionPruneRow, key=ledger.COLLECTION_PRUNE_KEY
    )
    found = ledger.compact_file(state(root), GARDENER, Period.DAILY, day)
    assert found is not None
    assert ledger.load([found], model=CollectionPruneRow) == settled
    assert [(row.task, row.attempt) for row in settled] == [("seen", 2)]
    assert watermark(root, Period.DAILY, GARDENER) == "2026-09-22", "the re-run moved nothing back"
    assert ledger.list_raw_files(state(root), GARDENER) == []
    assert outcome.stopped_because is StopReason.EXHAUSTED and disjoint(outcome)


def a_record(task: str, *, run: str, attempt: int, on: str) -> CollectionPruneRow:
    """One gardener record row for one task, from the committed contract fixture."""
    fixture = CONTRACT_FIXTURES_DIR / "collection-prune-row" / "exhausted-dry-run.json"
    row = CollectionPruneRow.from_json(read_text(fixture))
    return row.model_copy(
        update={
            "date": on,
            "task": task,
            "run_id": run,
            "attempt": attempt,
            "job": ServerJob.RUN_TASKS,
            "shard": 0,
        }
    )


def recorded(state_dir: Path, rows: list[CollectionPruneRow], *, attempt: int) -> Path:
    """One shard's record, through the door, as the runner files it."""
    (written,) = ledger.persist(
        state_dir,
        rows,
        ledger=GARDENER,
        covers=rows[0].date,
        identity=WriterIdentity(
            run_id=rows[0].run_id,
            attempt=attempt,
            job=ServerJob.RUN_TASKS,
            shard=0,
            producer="gardener.runner",
            git_sha="b" * 40,
        ),
    )
    return written


def test_a_raw_file_that_cannot_be_read_is_set_aside_and_the_rest_of_its_day_packs(
    tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    """THE ORACLE for an unreadable raw file: it sits under set-aside at its old path, counted.

    The day's other file packs, the entry says one file was set aside, and the
    pass goes on to the days after it.
    """
    root = tmp_path / "checkout"
    written = filed(root, a_pass("2026-09-02"))
    stray = written.parent / "notes.txt"
    stray.write_text("not a ledger file\n", encoding="ascii")

    with caplog.at_level(logging.WARNING):
        outcome = compact(root, date(2026, 9, 23), max_periods_per_run=31)

    assert outcome.stopped_because is StopReason.EXHAUSTED, outcome.resume_from
    assert compact_rows(root, Period.DAILY, "2026-09-02") == [a_pass("2026-09-02")]
    moved = state(root) / "raw/visual-prunes/set-aside/raw/visual-prunes/2026/09/02/notes.txt"
    assert moved.read_text(encoding="ascii") == "not a ledger file\n"
    assert not stray.exists() and not written.exists()
    entries = {entry.covers: entry for entry in CompactIndex.read(index_of(root, Period.DAILY)).entries}
    assert (entries["2026-09-02"].state, entries["2026-09-02"].set_aside) == (EntryState.PACKED, 1)
    assert recovered(caplog, "2026-09-02") == [f"note={RecoveryNote.SET_ASIDE}"]
    assert watermark(root, Period.DAILY) == "2026-09-21", "the rest of the pass still ran"


def test_a_file_moved_aside_is_taken_from_its_path_and_frees_no_byte(tmp_path: Path) -> None:
    """A move keeps the file's bytes in git, so the record counts the delete and frees nothing.

    The day held nothing else, so it is a day with no row that set one file aside.
    """
    root = tmp_path / "checkout"
    folder = state(root) / "raw" / VISUALS.value / "2026" / "09" / "02"
    folder.mkdir(parents=True)
    (folder / "notes.txt").write_text("not a ledger file\n", encoding="ascii")

    outcome = compact(root, date(2026, 9, 23), max_periods_per_run=31)

    assert outcome.taken == ("state/raw/visual-prunes/2026/09/02/notes.txt",)
    assert "state/raw/visual-prunes/set-aside/raw/visual-prunes/2026/09/02/notes.txt" in (
        outcome.written
    )
    assert outcome.bytes_freed == 0
    entries = {entry.covers: entry for entry in CompactIndex.read(index_of(root, Period.DAILY)).entries}
    assert entries["2026-09-02"] == CompactEntry(
        covers="2026-09-02", rows=0, bytes=0, state=EntryState.EMPTY, set_aside=1
    )
    assert disjoint(outcome)


def test_a_day_with_three_raw_files_past_its_most_packs_its_most_and_the_next_wake_the_rest(
    tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    """THE ORACLE for extra raw files: the first pass packs the most and ends at the ceiling.

    The three files past it wait in the day's folder, the mark moves past the
    day, and the next wake takes them in as it takes a re-run, and is done.
    """
    root = tmp_path / "checkout"
    runs = ("1", "2", "3", "4", "5", "6")
    for run in runs:
        filed(root, a_pass("2026-09-02", run=run))

    with caplog.at_level(logging.WARNING):
        first = compact(
            root, date(2026, 9, 23), max_periods_per_run=31, max_raw_files_per_period=3
        )

    assert (first.stopped_because, first.resume_from) == (StopReason.CEILING, "2026-09-02")
    assert len(compact_rows(root, Period.DAILY, "2026-09-02")) == 3
    assert len(ledger.list_raw_files(state(root), VISUALS, days={"2026-09-02"})) == 3
    assert recovered(caplog, "2026-09-02") == [f"note={RecoveryNote.CARRIED_OVER}"]
    assert watermark(root, Period.DAILY) == "2026-09-21", "the mark moved past the day"

    second = compact(root, date(2026, 9, 23), max_periods_per_run=31, max_raw_files_per_period=3)

    assert (second.stopped_because, second.resume_from) == (StopReason.EXHAUSTED, None)
    assert sorted(row.run_id for row in compact_rows(root, Period.DAILY, "2026-09-02")) == [
        f"2026-09-02-{run}" for run in runs
    ]
    assert ledger.list_raw_files(state(root), VISUALS, days={"2026-09-02"}) == []
    assert disjoint(first) and disjoint(second)


def test_a_paused_family_is_compacted_all_the_same(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A status stops new rows, never the compaction: its rows were recorded already."""
    root = tmp_path / "checkout"
    filed(root, a_pass("2026-09-20"))
    registry = json.loads(read_text(CONFIG_DIR / paths.REGISTRY_FILENAME))
    for family in registry["families"]:
        if any(held["name"] == VISUALS.value for held in family["ledgers"]):
            family["lifecycle_status"] = "paused"
    monkeypatch.setattr(paths, "_CONFIG", LedgersConfig.model_validate(registry))

    compact(root, date(2026, 9, 23), max_periods_per_run=31)

    assert compact_rows(root, Period.DAILY, "2026-09-20") == [a_pass("2026-09-20")]


def test_a_dry_run_names_every_path_the_live_pass_changes_and_changes_nothing(
    tmp_path: Path,
) -> None:
    """Both trees are one tree copied, because a raw file is named by the instant it was written."""
    trees = [tmp_path / "dry", tmp_path / "live"]
    filed(trees[0], a_pass("2026-09-20"))
    filed(trees[0], a_pass("2026-09-21", run="2"))
    shutil.copytree(trees[0], trees[1])
    before = [files_under(root) for root in trees]

    dry = run_task(
        "compact-visual-prunes", trees[0], today=date(2026, 9, 23), max_periods_per_run=31
    )
    live = compact(trees[1], date(2026, 9, 23), max_periods_per_run=31)

    assert dry.dry_run and not live.dry_run
    assert files_under(trees[0]) == before[0], "a dry run changed a file"
    assert (dry.taken, dry.written) == (live.taken, live.written)
    after = files_under(trees[1])
    changed = {path for path in before[1] | after if before[1].get(path) != after.get(path)}
    assert changed == set(live.taken) | set(live.written)
    assert dry.bytes_freed == live.bytes_freed == sum(len(before[1][path]) for path in live.taken)


def test_the_record_row_a_pass_makes_is_one_the_gardener_ledger_accepts(tmp_path: Path) -> None:
    """`bytes_freed` is every byte the pass deleted, and `seen` counts all it looked at."""
    root = tmp_path / "checkout"
    filed(root, a_pass("2026-09-20"))
    sizes = {path: len(data) for path, data in files_under(root).items()}

    outcome = compact(root, date(2026, 9, 23), max_periods_per_run=31)
    row = report.row(
        outcome,
        task="compact-visual-prunes",
        context=context_for("compact-visual-prunes", root, today=date(2026, 9, 23)),
        duration_ms=0,
        work_ended_at="2026-09-23T00:41:00Z",
        cone_bytes=None,
        downloaded_bytes=None,
    )

    assert outcome.bytes_freed == sum(sizes[path] for path in outcome.taken) > 0
    assert row.deleted == len(outcome.taken) <= row.selected <= row.candidates_seen
    assert row.until == "2026-09-21"


# --- the month: absorbed whole, dropped on time ------------------------------------


def two_passes_into_october(root: Path) -> tuple[Pass, Pass]:
    """August's and September's days compacted, then August absorbed at the next wake."""
    filed(root, a_pass("2026-08-05"))
    filed(root, a_pass("2026-08-20", run="2"))
    first = compact(root, date(2026, 10, 20), max_periods_per_run=100)
    second = compact(root, date(2026, 10, 20), max_periods_per_run=100)
    return first, second


def test_a_month_is_absorbed_whole_at_the_wake_after_its_days_and_each_date_is_read_once(
    tmp_path: Path,
) -> None:
    """The oracle: no date is readable twice, and no day the watermark passed is skipped."""
    root = tmp_path / "checkout"
    filed(root, a_pass("2026-08-05"))
    filed(root, a_pass("2026-08-20", run="2"))
    first = compact(root, date(2026, 10, 20), max_periods_per_run=100)
    assert daily_covers(root)[0] == "2026-08-05", "a first pass starts at its oldest raw day"
    august = [
        row
        for day in days("2026-08-01", "2026-08-31")
        if ledger.compact_file(state(root), VISUALS, Period.DAILY, day) is not None
        for row in compact_rows(root, Period.DAILY, day)
    ]
    assert watermark(root, Period.MONTHLY) is None, "a month waits for the wake after its days"

    second = compact(root, date(2026, 10, 20), max_periods_per_run=100)

    assert watermark(root, Period.MONTHLY) == "2026-08"
    assert compact_rows(root, Period.MONTHLY, "2026-08") == august
    assert daily_covers(root)[0] == "2026-09-01"
    assert all(
        ledger.compact_file(state(root), VISUALS, Period.DAILY, day) is None
        for day in days("2026-08-01", "2026-08-31")
    )
    found = ledger.list_ledger_files(state(root), VISUALS)
    for day in days("2026-08-01", "2026-10-18"):
        assert len([source for source in found.sources if source.holds(day)]) == 1, day
    assert found.holes == ()
    assert disjoint(first) and disjoint(second)


def test_a_day_the_daily_index_lost_with_its_file_is_recorded_lost_and_its_month_closes(
    tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    """A hole nothing can rebuild no longer stops the month: the month closes and names the day."""
    root = tmp_path / "checkout"
    filed(root, a_pass("2026-08-05"))
    filed(root, a_pass("2026-08-10", run="2"))
    compact(root, date(2026, 10, 20), max_periods_per_run=100)
    index_path = ledger.compact_index_path(state(root), VISUALS, Period.DAILY)
    index = CompactIndex.read(index_path)
    kept = [entry for entry in index.entries if entry.covers != "2026-08-10"]
    index_path.write_bytes(index.model_copy(update={"entries": kept}).to_json().encode("ascii"))
    lost = ledger.compact_file(state(root), VISUALS, Period.DAILY, "2026-08-10")
    assert lost is not None
    lost.unlink()

    with caplog.at_level(logging.WARNING):
        outcome = compact(root, date(2026, 10, 20), max_periods_per_run=100)

    assert outcome.stopped_because is StopReason.EXHAUSTED
    assert watermark(root, Period.MONTHLY) == "2026-08"
    (august,) = CompactIndex.read(index_of(root, Period.MONTHLY)).entries
    assert (august.state, august.lost_days) == (EntryState.PACKED, ["2026-08-10"])
    assert compact_rows(root, Period.MONTHLY, "2026-08") == [a_pass("2026-08-05")]
    assert recovered(caplog, "2026-08-10") == [f"note={RecoveryNote.RECORDED_LOST}"]


def test_a_month_whose_index_names_a_day_file_the_tree_lacks_closes_with_that_day_lost(
    tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    """THE ORACLE for a packed day file that is gone: no file to set aside, and the day is lost.

    The month closes from its other day, listing the gone day in `lost_days`.
    """
    root = tmp_path / "checkout"
    filed(root, a_pass("2026-08-05"))
    filed(root, a_pass("2026-08-20", run="2"))
    compact(root, date(2026, 10, 20), max_periods_per_run=100)
    gone = ledger.compact_file(state(root), VISUALS, Period.DAILY, "2026-08-05")
    assert gone is not None
    gone.unlink()

    with caplog.at_level(logging.WARNING):
        outcome = compact(root, date(2026, 10, 20), max_periods_per_run=100)

    assert outcome.stopped_because is StopReason.EXHAUSTED, outcome.resume_from
    assert watermark(root, Period.MONTHLY) == "2026-08"
    (august,) = CompactIndex.read(index_of(root, Period.MONTHLY)).entries
    assert (august.state, august.lost_days, august.set_aside) == (
        EntryState.PACKED,
        ["2026-08-05"],
        0,
    )
    assert compact_rows(root, Period.MONTHLY, "2026-08") == [a_pass("2026-08-20", run="2")]
    assert recovered(caplog, "2026-08-05") == [f"note={RecoveryNote.RECORDED_LOST}"]


def test_a_day_file_that_cannot_be_read_when_its_month_closes_is_set_aside_and_its_day_lost(
    tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    """The file goes under set-aside at its old path, its day is lost, and the month counts it."""
    root = tmp_path / "checkout"
    filed(root, a_pass("2026-08-05"))
    filed(root, a_pass("2026-08-20", run="2"))
    compact(root, date(2026, 10, 20), max_periods_per_run=100)
    broken = ledger.compact_file(state(root), VISUALS, Period.DAILY, "2026-08-05")
    assert broken is not None
    broken.write_bytes(b"not a ledger file\n")

    with caplog.at_level(logging.WARNING):
        outcome = compact(root, date(2026, 10, 20), max_periods_per_run=100)

    assert outcome.stopped_because is StopReason.EXHAUSTED, outcome.resume_from
    (august,) = CompactIndex.read(index_of(root, Period.MONTHLY)).entries
    assert (august.state, august.lost_days, august.set_aside) == (
        EntryState.PACKED,
        ["2026-08-05"],
        1,
    )
    assert compact_rows(root, Period.MONTHLY, "2026-08") == [a_pass("2026-08-20", run="2")]
    moved = state(root) / "raw/visual-prunes/set-aside/compact/visual-prunes/daily/2026/08/05.parquet"
    assert moved.read_bytes() == b"not a ledger file\n"
    assert not broken.exists()
    assert recovered(caplog, "2026-08-05") == [
        f"note={RecoveryNote.SET_ASIDE}",
        f"note={RecoveryNote.RECORDED_LOST}",
    ]


def test_a_day_taken_again_and_then_its_month_keep_the_count_of_files_set_aside(
    tmp_path: Path,
) -> None:
    """A re-run re-takes the day and the month later closes; neither forgets the file moved aside."""
    root = tmp_path / "checkout"
    written = filed(root, a_pass("2026-08-05"))
    (written.parent / "notes.txt").write_text("not a ledger file\n", encoding="ascii")
    compact(root, date(2026, 9, 2), max_periods_per_run=100)
    filed(root, a_pass("2026-08-05", run="2"))

    compact(root, date(2026, 9, 2), max_periods_per_run=100)

    entries = {entry.covers: entry for entry in CompactIndex.read(index_of(root, Period.DAILY)).entries}
    assert (entries["2026-08-05"].rows, entries["2026-08-05"].set_aside) == (2, 1)

    compact(root, date(2026, 10, 20), max_periods_per_run=100)

    (august,) = CompactIndex.read(index_of(root, Period.MONTHLY)).entries
    assert (august.rows, august.set_aside, august.lost_days) == (2, 1, [])


def faults(caplog: pytest.LogCaptureFixture, naming: str, *, at: int = logging.WARNING) -> list[str]:
    """The `fault=` word of every record at or above `at` the pass logged about one period."""
    return [
        word
        for record in caplog.records
        if record.levelno >= at and naming in record.getMessage()
        for word in record.getMessage().split()
        if word.startswith("fault=")
    ]


def refusals(caplog: pytest.LogCaptureFixture, naming: str) -> list[str]:
    """The `fault=` word of every error the pass logged about one period."""
    return faults(caplog, naming, at=logging.ERROR)


def recovered(caplog: pytest.LogCaptureFixture, period: str) -> list[str]:
    """The `note=` word of every recovery the pass logged about one period."""
    return [
        word
        for record in caplog.records
        if f"period={period} " in record.getMessage()
        for word in record.getMessage().split()
        if word.startswith("note=")
    ]


def test_a_month_waits_one_wake_for_a_re_run_still_waiting_in_it(tmp_path: Path) -> None:
    """A raw day left in a month is taken again first, and the month goes at the next wake."""
    root = tmp_path / "checkout"
    filed(root, a_pass("2026-08-20", run="2", before=100))
    compact(root, date(2026, 10, 20), max_periods_per_run=100)
    filed(root, a_pass("2026-08-20", run="2", before=222), attempt=2)

    waited = compact(root, date(2026, 10, 20), max_periods_per_run=100)
    assert watermark(root, Period.MONTHLY) is None
    assert waited.stopped_because is StopReason.EXHAUSTED

    compact(root, date(2026, 10, 20), max_periods_per_run=100)
    assert [row.payload_bytes_before for row in compact_rows(root, Period.MONTHLY, "2026-08")] == [
        222
    ]


def test_a_raw_day_in_a_month_that_never_closed_is_refused_and_kept_and_never_re_opened(
    tmp_path: Path,
) -> None:
    """July is before the ledger's first packed month and behind the monthly mark: nothing re-opens it.

    The month has no entry to rewrite, so the day is refused by name and kept for
    a person, as one in a month that was dropped or sits in a packed year is.
    """
    root = tmp_path / "checkout"
    two_passes_into_october(root)
    stray = filed(root, a_pass("2026-07-10", run="9"))

    outcome = compact(root, date(2026, 10, 21), max_periods_per_run=100)

    assert (outcome.stopped_because, outcome.resume_from) == (StopReason.FAILED, "2026-07-10")
    assert stray.is_file()
    assert monthly_covers(root) == ["2026-08"]
    assert watermark(root, Period.DAILY) == "2026-10-19", "the rest of the pass still ran"


# --- a late file re-opens its month ------------------------------------------------


def test_a_late_re_run_re_opens_its_month_and_the_month_holds_each_key_once_as_settled(
    tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    """THE ORACLE for a late file: the month holds what packing the late day first would have held.

    August closes holding two work units' rows on one day. Then one unit's re-run
    files into that day again under the same record keys, and fewer rows. The
    next pass re-opens August: each key once, the re-run's one row in place of
    its first attempt's two, the late file gone, and a new day of the pass packed.
    """
    root = tmp_path / "checkout"
    day, first, second = "2026-08-20", "2026-08-20-17000000001", "2026-08-20-17000000002"
    recorded(
        state(root),
        [
            a_record("seen", run=first, attempt=1, on=day),
            a_record("traces", run=first, attempt=1, on=day),
        ],
        attempt=1,
    )
    recorded(state(root), [a_record("seen", run=second, attempt=1, on=day)], attempt=1)
    for _ in range(2):
        compact(root, date(2026, 10, 20), task="compact-gardener", max_periods_per_run=100)
    assert watermark(root, Period.MONTHLY, GARDENER) == "2026-08", "August is closed"
    late = recorded(state(root), [a_record("seen", run=first, attempt=2, on=day)], attempt=2)
    new = "2026-10-20"
    recorded(state(root), [a_record("seen", run=f"{new}-17000000003", attempt=1, on=new)], attempt=1)

    with caplog.at_level(logging.WARNING):
        outcome = compact(root, date(2026, 10, 22), task="compact-gardener", max_periods_per_run=100)

    august = ledger.compact_file(state(root), GARDENER, Period.MONTHLY, "2026-08")
    assert august is not None
    rows = ledger.load([august], model=CollectionPruneRow)
    assert [(row.run_id, row.task, row.attempt) for row in rows] == [
        (second, "seen", 1),
        (first, "seen", 2),
    ]
    index = ledger.compact_index_path(state(root), GARDENER, Period.MONTHLY)
    (entry,) = CompactIndex.read(index).entries
    assert (entry.covers, entry.state, entry.rows) == ("2026-08", EntryState.PACKED, 2)
    assert not late.exists()
    assert recovered(caplog, "2026-08") == [f"note={RecoveryNote.REOPENED_MONTH}"]
    assert outcome.stopped_because is StopReason.EXHAUSTED and disjoint(outcome)
    assert watermark(root, Period.MONTHLY, GARDENER) == "2026-08", "a re-open moves no mark"
    assert watermark(root, Period.DAILY, GARDENER) == new, "the pass's new days still packed"
    assert daily_covers(root, GARDENER)[-1] == new


def test_a_wake_re_opens_a_closed_month_a_re_run_landed_in_and_a_lost_day_is_lost_no_more(
    tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    """Under a wake's listing the re-open names what it reads, and the day it took is not lost.

    September is closed by hand with 2026-09-25 recorded lost, as a ledger that
    closes a month sooner than 30 days after it ends has it on 20 October. A
    re-run then files into 2026-09-25, inside the days the day step names
    because a re-run may still write there.
    """
    root = tmp_path / "checkout"
    september = a_packed_month(root, "2026-09")
    entry = CompactEntry(
        covers="2026-09", rows=1, bytes=september.stat().st_size, lost_days=["2026-09-25"]
    )
    a_monthly_index(root, [entry], through="2026-09")
    for period in (Period.DAILY, Period.YEARLY):
        an_empty_index(root, period)
    a_mark(root, Period.DAILY, "2026-10-18")
    late = filed(root, a_pass("2026-09-25", run="9"))

    with caplog.at_level(logging.WARNING):
        outcome = compact(root, date(2026, 10, 20), wake=True)

    assert [row.date for row in compact_rows(root, Period.MONTHLY, "2026-09")] == [
        "2026-09-05",
        "2026-09-25",
    ]
    (reopened,) = CompactIndex.read(index_of(root, Period.MONTHLY)).entries
    assert (reopened.rows, reopened.lost_days) == (2, [])
    assert not late.exists()
    assert recovered(caplog, "2026-09") == [f"note={RecoveryNote.REOPENED_MONTH}"]
    assert outcome.stopped_because is StopReason.EXHAUSTED and disjoint(outcome)


def test_a_re_opened_month_counts_once_against_the_cap(tmp_path: Path) -> None:
    """With a cap of one, the re-open is taken, the new day waits, and the pass stops at its ceiling."""
    root = tmp_path / "checkout"
    two_passes_into_october(root)
    late = filed(root, a_pass("2026-08-15", run="9"))
    waiting = filed(root, a_pass("2026-10-19", run="8"))

    outcome = compact(root, date(2026, 10, 21), max_periods_per_run=1)

    assert (outcome.stopped_because, outcome.resume_from) == (StopReason.CEILING, "2026-10-19")
    assert [row.date for row in compact_rows(root, Period.MONTHLY, "2026-08")] == [
        "2026-08-05",
        "2026-08-15",
        "2026-08-20",
    ]
    assert not late.exists()
    assert waiting.is_file()
    assert watermark(root, Period.DAILY) == "2026-10-18"


def test_a_late_file_that_cannot_be_read_is_set_aside_and_its_re_opened_month_counts_it(
    tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    """The re-open settles the late file it can read and moves the other aside, counted."""
    root = tmp_path / "checkout"
    two_passes_into_october(root)
    late = filed(root, a_pass("2026-08-15", run="9"))
    stray = late.parent / "notes.txt"
    stray.write_text("not a ledger file\n", encoding="ascii")

    with caplog.at_level(logging.WARNING):
        outcome = compact(root, date(2026, 10, 21), max_periods_per_run=100)

    assert outcome.stopped_because is StopReason.EXHAUSTED, outcome.resume_from
    assert [row.date for row in compact_rows(root, Period.MONTHLY, "2026-08")] == [
        "2026-08-05",
        "2026-08-15",
        "2026-08-20",
    ]
    (august,) = CompactIndex.read(index_of(root, Period.MONTHLY)).entries
    assert (august.rows, august.set_aside) == (3, 1)
    moved = state(root) / "raw/visual-prunes/set-aside/raw/visual-prunes/2026/08/15/notes.txt"
    assert moved.read_text(encoding="ascii") == "not a ledger file\n"
    assert not late.exists() and not stray.exists()
    assert recovered(caplog, "2026-08") == [f"note={RecoveryNote.REOPENED_MONTH}"]
    assert recovered(caplog, "2026-08-15") == [f"note={RecoveryNote.SET_ASIDE}"]


def test_a_re_open_whose_month_file_is_gone_is_refused_as_file_missing(
    tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    """Rebuilt from the late file alone, the month would hold only the day that ran again."""
    root = tmp_path / "checkout"
    two_passes_into_october(root)
    gone = ledger.compact_file(state(root), VISUALS, Period.MONTHLY, "2026-08")
    assert gone is not None
    gone.unlink()
    late = filed(root, a_pass("2026-08-15", run="9"))

    with caplog.at_level(logging.ERROR):
        outcome = compact(root, date(2026, 10, 21), max_periods_per_run=100)

    assert (outcome.stopped_because, outcome.resume_from) == (StopReason.FAILED, "2026-08")
    assert late.is_file()
    assert ledger.compact_file(state(root), VISUALS, Period.MONTHLY, "2026-08") is None
    assert refusals(caplog, "month=2026-08") == [f"fault={ledger.LedgerFault.FILE_MISSING}"]
    assert watermark(root, Period.DAILY) == "2026-10-19", "the rest of the pass still ran"


# --- the three indexes, and a file the index names that is gone -------------------

#: The indexes a pass that writes `daily.json` writes beside it when they are not there.
COARSER: Final = (Period.MONTHLY, Period.YEARLY)


def index_of(root: Path, period: Period) -> Path:
    return ledger.compact_index_path(state(root), VISUALS, period)


def test_a_pass_that_writes_the_daily_index_writes_the_other_two_empty_when_none_exists(
    tmp_path: Path,
) -> None:
    """The oracle: a ledger never holds daily.json alone, so a reader asks for no file that is not there."""
    root = tmp_path / "checkout"
    filed(root, a_pass("2026-09-20"))

    outcome = compact(root, date(2026, 9, 23), max_periods_per_run=31)

    for period in COARSER:
        held = CompactIndex.read(index_of(root, period))
        assert (held.ledger, held.period, held.entries) == (VISUALS, period, [])
        assert index_of(root, period).relative_to(root).as_posix() in outcome.written
        assert watermark(root, period) is None, f"an empty list is not a packed {period.value}"
    assert disjoint(outcome)


@pytest.mark.parametrize("period", COARSER)
def test_a_ledger_packed_before_the_indexes_were_written_together_gains_the_one_it_lacks(
    tmp_path: Path, period: Period
) -> None:
    """daily.json and its watermark, and no index for this period: the next pass that writes a day adds it."""
    root = tmp_path / "checkout"
    filed(root, a_pass("2026-09-20"))
    compact(root, date(2026, 9, 23), max_periods_per_run=31)
    index_of(root, period).unlink()

    outcome = compact(root, date(2026, 9, 24), max_periods_per_run=31)

    assert CompactIndex.read(index_of(root, period)).entries == []
    assert index_of(root, period).relative_to(root).as_posix() in outcome.written


@pytest.mark.parametrize("period", COARSER)
def test_a_pass_never_deletes_a_coarser_index_and_leaves_an_empty_one_as_it_is(
    tmp_path: Path, period: Period
) -> None:
    root = tmp_path / "checkout"
    filed(root, a_pass("2026-09-20"))
    compact(root, date(2026, 9, 23), max_periods_per_run=31)
    before = index_of(root, period).read_bytes()

    outcome = compact(root, date(2026, 9, 25), max_periods_per_run=31)

    shown = index_of(root, period).relative_to(root).as_posix()
    assert shown not in outcome.written and shown not in outcome.taken
    assert index_of(root, period).read_bytes() == before
    assert daily_covers(root)[-1] == "2026-09-23"


def a_mark(root: Path, period: Period, through: str) -> None:
    """One watermark of a period already packed through `through`, and nothing else of it."""
    mark = Watermark(
        version=Watermark.schema_version(),
        ledger=VISUALS,
        period=period,
        through=through,
        advanced_at="2026-03-20T00:41:00Z",
        run_id="2026-03-20-1",
    )
    path = ledger.watermark_path(state(root), VISUALS, period)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(mark.to_json().encode("ascii"))


def an_empty_index(root: Path, period: Period) -> None:
    """One period's index with no entries."""
    empty = CompactIndex(
        version=CompactIndex.schema_version(), ledger=VISUALS, period=period, entries=[]
    )
    path = index_of(root, period)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(empty.to_json().encode("ascii"))


@pytest.mark.parametrize("period", list(Period))
def test_an_index_its_watermark_says_was_packed_that_is_not_there_stops_the_pass_by_name(
    tmp_path: Path, period: Period
) -> None:
    """Read as empty, it would be rewritten naming only what this pass packs."""
    root = tmp_path / "checkout"
    if period is Period.DAILY:
        filed(root, a_pass("2026-09-20"))
        compact(root, date(2026, 9, 23), max_periods_per_run=31)
    elif period is Period.MONTHLY:
        a_month_file(root, "2026-01")
    else:
        a_mark(root, Period.YEARLY, "2025")
    assert watermark(root, period) is not None
    index_of(root, period).unlink(missing_ok=True)
    before = files_under(root)

    with pytest.raises(ValueError, match=f"^{ledger.LedgerFault.INDEX_MISSING}: "):
        compact(root, date(2026, 9, 24), max_periods_per_run=31)

    assert files_under(root) == before


def test_a_re_run_into_a_day_whose_packed_file_is_gone_is_refused_as_file_missing(
    tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    """Rebuilt from the re-run alone, the day would hold only the shards that ran again."""
    root = tmp_path / "checkout"
    filed(root, a_pass("2026-09-20"))
    compact(root, date(2026, 9, 23), max_periods_per_run=31)
    lost = ledger.compact_file(state(root), VISUALS, Period.DAILY, "2026-09-20")
    assert lost is not None
    lost.unlink()
    late = filed(root, a_pass("2026-09-20", before=222), attempt=2)

    with caplog.at_level(logging.ERROR):
        outcome = compact(root, date(2026, 9, 24), max_periods_per_run=31)

    assert (outcome.stopped_because, outcome.resume_from) == (StopReason.FAILED, "2026-09-20")
    assert late.is_file()
    assert ledger.compact_file(state(root), VISUALS, Period.DAILY, "2026-09-20") is None
    assert refusals(caplog, "day=2026-09-20") == [f"fault={ledger.LedgerFault.FILE_MISSING}"]
    assert watermark(root, Period.DAILY) == "2026-09-22", "the rest of the pass still ran"


def test_a_catch_up_pass_never_writes_a_path_it_deletes(tmp_path: Path) -> None:
    """Eligible months and many days are due at once, and none may stall the shard.

    A first run looks back five months, to May, from the month of its newest due day.
    """
    root = tmp_path / "checkout"
    filed(root, a_pass("2026-05-10"))

    passes = [
        compact(root, date(2026, 10, 20), max_periods_per_run=200, lookback=5) for _ in range(3)
    ]

    assert all(disjoint(outcome) for outcome in passes)
    assert watermark(root, Period.MONTHLY) == "2026-08"


def a_packed_month(root: Path, month: str) -> Path:
    """One month's own file, packed from one row filed on its 5th."""
    raw = filed(root / "scratch", a_pass(f"{month}-05"))
    return ledger.persist_period(
        state(root),
        ledger.load_stored([raw], model=VisualPruneRow),
        model=VisualPruneRow,
        ledger=VISUALS,
        period=Period.MONTHLY,
        covers=month,
        identity=WriterIdentity(
            run_id="2026-02-15-1",
            attempt=1,
            job=ServerJob.RUN_TASKS,
            shard=0,
            producer="gardener.tasks.compaction",
            git_sha="c" * 40,
        ),
        built_from=1,
    )


def a_monthly_index(root: Path, entries: list[CompactEntry], *, through: str) -> None:
    """The monthly index naming these entries, and the monthly watermark on `through`."""
    index = CompactIndex(
        version=CompactIndex.schema_version(),
        ledger=VISUALS,
        period=Period.MONTHLY,
        entries=entries,
    )
    index_path = ledger.compact_index_path(state(root), VISUALS, Period.MONTHLY)
    index_path.parent.mkdir(parents=True, exist_ok=True)
    index_path.write_bytes(index.to_json().encode("ascii"))
    mark = Watermark(
        version=Watermark.schema_version(),
        ledger=VISUALS,
        period=Period.MONTHLY,
        through=through,
        advanced_at="2026-02-15T00:41:00Z",
        run_id="2026-02-15-1",
    )
    mark_path = ledger.watermark_path(state(root), VISUALS, Period.MONTHLY)
    mark_path.parent.mkdir(parents=True, exist_ok=True)
    mark_path.write_bytes(mark.to_json().encode("ascii"))


def a_month_file(root: Path, month: str) -> Path:
    """One month already absorbed: its file, the monthly index and its watermark."""
    written = a_packed_month(root, month)
    a_monthly_index(
        root, [CompactEntry(covers=month, rows=1, bytes=written.stat().st_size)], through=month
    )
    return written


@pytest.mark.parametrize(
    ("today", "dropped"), [(date(2027, 4, 14), False), (date(2027, 4, 15), True)]
)
def test_a_month_file_goes_the_day_the_month_its_window_later_is_absorbed(
    tmp_path: Path, today: date, dropped: bool
) -> None:
    """At 13 months and 45 days, January 2026 goes on 15 April 2027, the day February 2027 is due."""
    root = tmp_path / "checkout"
    january = a_month_file(root, "2026-01")

    outcome = compact(root, today, max_periods_per_run=31)

    assert (january.relative_to(root).as_posix() in outcome.taken) is dropped
    assert january.is_file() is not dropped


def test_the_monthly_period_holds_exactly_its_window_of_months_on_every_day_of_two_years() -> None:
    """13 months at 45 days, counted by the absorbing rule, on every UTC day of 2027 and 2028."""
    window = MonthsWindow(unit="months", value=13)
    day = date(2027, 1, 1)
    while day < date(2029, 1, 1):
        now = datetime.combine(day, time.min, tzinfo=UTC)
        newest = day.strftime("%Y-%m")
        while not schedule.is_month_eligible(newest, now=now, after_days=45):
            newest = _monthly_period.shift(newest, -1)
        first = _monthly_period.first_kept_month(now=now, daily_keep_days=45, window=window)
        assert first is not None
        held = 0
        month = first
        while month <= newest:
            held += 1
            month = _monthly_period.shift(month, 1)
        assert held == 13, day
        day += timedelta(days=1)


# --- a window that only reports ----------------------------------------------------

#: A window of one month, so a ledger a few months old holds months past it.
ONE_MONTH: Final = {"unit": "months", "value": 1}

#: The wake the switch is read at. A one-month window then keeps September on,
#: and September is due: 47 whole days have passed since it ended, and 45 must.
NOVEMBER_WAKE: Final = date(2026, 11, 16)

#: The month files a one-month window drops at that wake.
PAST_THE_WINDOW: Final = ("2026-06", "2026-07", "2026-08")


def month_file(root: Path, month: str) -> Path:
    found = ledger.compact_file(state(root), VISUALS, Period.MONTHLY, month)
    assert found is not None, f"no month file holds {month}"
    return found


def window_pass(root: Path, today: date, *, reports: bool) -> Pass:
    """One live pass under a one-month window that deletes, or only reports.

    A first run looks back four months from the month of its newest due day, so
    on 20 October it reaches June.
    """
    return compact(
        root,
        today,
        max_periods_per_run=200,
        monthly_window=ONE_MONTH,
        month_deletes_dry_run=reports,
        lookback=4,
    )


def months_past_the_window(root: Path) -> None:
    """June to August in month files, September in day files, and two raw days due in November.

    Built by the shipped pass with its window only reporting, so every month the
    window drops at the November wake is still there.
    """
    for number, on in enumerate(("2026-06-05", "2026-07-05", "2026-08-05", "2026-09-05")):
        filed(root, a_pass(on, run=str(number + 1)))
    for _ in range(2):
        window_pass(root, date(2026, 10, 20), reports=True)
    assert watermark(root, Period.MONTHLY) == "2026-08", "June to August are month files"
    filed(root, a_pass("2026-10-25", run="5"))
    filed(root, a_pass("2026-11-10", run="6"))


def test_a_window_that_only_reports_packs_every_due_period_and_keeps_every_month_file(
    tmp_path: Path,
) -> None:
    """THE ORACLE for the window's switch, over two copies of one tree.

    With the window live a pass deletes the three month files past it. With the
    window only reporting the same pass keeps them, packs the same days and the
    same month, deletes only files whose rows sit in a coarser file, and counts
    the three in `selected` and not in `deleted`.
    """
    trees = [tmp_path / "live", tmp_path / "reports"]
    months_past_the_window(trees[0])
    shutil.copytree(trees[0], trees[1])
    every_day = days("2026-06-01", "2026-11-14")
    filed_rows = ledger.load_days(state(trees[1]), VISUALS, every_day, model=VisualPruneRow)
    dropped = {
        month_file(trees[1], month).relative_to(trees[1]).as_posix() for month in PAST_THE_WINDOW
    }

    live = window_pass(trees[0], NOVEMBER_WAKE, reports=False)
    reports = window_pass(trees[1], NOVEMBER_WAKE, reports=True)

    assert set(live.taken) - set(reports.taken) == dropped
    assert set(reports.taken) < set(live.taken)
    assert reports.selected - len(reports.taken) == len(dropped) == 3
    assert live.selected == len(live.taken)
    assert set(reports.written) == set(live.written)
    for root in trees:
        assert watermark(root, Period.MONTHLY) == "2026-09", "September is absorbed either way"
        assert watermark(root, Period.DAILY) == "2026-11-14", "every due day is taken either way"
    assert all(month_file(trees[1], month).is_file() for month in PAST_THE_WINDOW)
    assert all(
        ledger.compact_file(state(trees[0]), VISUALS, Period.MONTHLY, month) is None
        for month in PAST_THE_WINDOW
    )
    assert ledger.load_days(state(trees[1]), VISUALS, every_day, model=VisualPruneRow) == filed_rows
    left = ledger.load_days(state(trees[0]), VISUALS, every_day, model=VisualPruneRow)
    assert [row.date for row in left] == ["2026-09-05", "2026-10-25", "2026-11-10"]
    row = report.row(
        reports,
        task="compact-visual-prunes",
        context=context_for("compact-visual-prunes", trees[1], today=NOVEMBER_WAKE),
        duration_ms=0,
        work_ended_at="2026-11-16T00:41:00Z",
        cone_bytes=None,
        downloaded_bytes=None,
    )
    assert (row.dry_run, row.deleted) == (False, len(reports.taken))
    assert row.deleted < row.selected <= row.candidates_seen
    assert disjoint(live) and disjoint(reports)


def test_a_raw_day_past_a_window_that_only_reports_is_packed_and_not_dropped(
    tmp_path: Path,
) -> None:
    """A first pass takes it as if the window kept every month; a live window deletes it unread.

    With the window's deletes live, a first pass starts at the oldest raw day the
    window keeps, never before its keep line.
    """
    trees = [tmp_path / "live", tmp_path / "reports"]
    filed(trees[0], a_pass("2026-06-05"))
    filed(trees[0], a_pass("2026-09-05", run="2"))
    shutil.copytree(trees[0], trees[1])
    june = ["2026-06-05"]

    live = window_pass(trees[0], date(2026, 10, 20), reports=False)
    reports = window_pass(trees[1], date(2026, 10, 20), reports=True)

    kept = ledger.load_days(state(trees[1]), VISUALS, june, model=VisualPruneRow)
    assert kept == [a_pass("2026-06-05")]
    assert ledger.load_days(state(trees[0]), VISUALS, june, model=VisualPruneRow) == []
    assert (daily_covers(trees[1])[0], daily_covers(trees[0])[0]) == ("2026-06-05", "2026-09-05")
    assert ledger.list_raw_files(state(trees[1]), VISUALS) == []
    assert set(reports.taken) == set(live.taken), "its raw files go either way, packed or dropped"
    assert reports.selected == len(reports.taken), "a file this pass packed is not held back"


def test_a_dry_run_whose_window_only_reports_names_what_that_live_pass_does(
    tmp_path: Path,
) -> None:
    """The window's switch decides what a pass does, and `dry_run` whether any of it lands."""
    trees = [tmp_path / "dry", tmp_path / "live"]
    months_past_the_window(trees[0])
    shutil.copytree(trees[0], trees[1])
    before = files_under(trees[0])

    dry = run_task(
        "compact-visual-prunes",
        trees[0],
        today=NOVEMBER_WAKE,
        max_periods_per_run=200,
        monthly_window=ONE_MONTH,
        month_deletes_dry_run=True,
    )
    live = window_pass(trees[1], NOVEMBER_WAKE, reports=True)

    assert dry.dry_run and files_under(trees[0]) == before
    assert (dry.taken, dry.written, dry.selected) == (live.taken, live.written, live.selected)


def test_a_raw_day_in_a_closed_month_past_the_keep_line_is_left_to_the_drop_steps(
    tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    """A window that only reports names it and keeps it, and the day step neither re-opens nor refuses it.

    The drop steps own every raw day in a closed month past the line: a live
    window deletes it unread, and a window that only reports keeps it, as it
    keeps the month file. Under a wake's listing the drop step names July's raw
    folder, so the day step meets the stray at or below the daily mark.
    """
    root = tmp_path / "checkout"
    months_past_the_window(root)
    stray = filed(root, a_pass("2026-07-15", run="9"))

    with caplog.at_level(logging.WARNING):
        outcome = compact(
            root,
            NOVEMBER_WAKE,
            wake=True,
            max_periods_per_run=200,
            monthly_window=ONE_MONTH,
            month_deletes_dry_run=True,
            lookback=4,
        )

    assert outcome.stopped_because is StopReason.EXHAUSTED, outcome.resume_from
    assert stray.is_file()
    assert outcome.selected - len(outcome.taken) == 4, "three month files and the stray kept"
    assert compact_rows(root, Period.MONTHLY, "2026-07") == [a_pass("2026-07-05", run="2")]
    assert recovered(caplog, "2026-07") == []
    assert watermark(root, Period.DAILY) == "2026-11-14", "every due day is taken all the same"
    assert disjoint(outcome)


# --- each old month is dropped once ------------------------------------------------

#: The first wake whose keep line is October 2025. On 16 December 2026 the newest
#: month 45 whole days past its end is October 2026, and a 13-month window keeps
#: October 2025 to October 2026, so January to September 2025 are past the line.
DROP_WAKE: Final = date(2026, 12, 16)

#: An old month that held no row, so its entry names no file.
QUIET_MONTH: Final = "2025-03"

#: An old month whose entry says `packed` while its file is gone.
GONE_MONTH: Final = "2025-05"

#: Raw days left in old months. 2025-09-05 is in the one old month past the cap.
OLD_RAW_DAYS: Final = ("2025-02-05", "2025-04-05", "2025-07-05", "2025-09-05")

#: The old raw day that also holds a file that is not a ledger file.
UNREADABLE_DAY: Final = "2025-04-05"


def old_months(root: Path) -> None:
    """A ledger closed from January 2025 to September 2026 and marked there, as a live one is.

    Every month has its own file but two: QUIET_MONTH held no row, and
    GONE_MONTH's file is gone while its entry says `packed`. Raw files are left
    on OLD_RAW_DAYS, and UNREADABLE_DAY also holds a file that is not a ledger
    file.
    """
    entries: list[CompactEntry] = []
    for month in month_partition.months_between("2025-01", "2026-09"):
        if month == QUIET_MONTH:
            entries.append(CompactEntry(covers=month, rows=0, bytes=0, state=EntryState.EMPTY))
            continue
        written = a_packed_month(root, month)
        entries.append(CompactEntry(covers=month, rows=1, bytes=written.stat().st_size))
        if month == GONE_MONTH:
            written.unlink()
    a_monthly_index(root, entries, through="2026-09")
    for period in (Period.DAILY, Period.YEARLY):
        an_empty_index(root, period)
    for day in OLD_RAW_DAYS:
        held = filed(root, a_pass(day))
        if day == UNREADABLE_DAY:
            (held.parent / "notes.txt").write_text("not a ledger file\n", encoding="ascii")


@pytest.mark.parametrize("wake", [False, True], ids=["whole-listing", "wake-listing"])
def test_each_old_month_is_dropped_once_oldest_first_and_at_most_eight_a_wake(
    tmp_path: Path, caplog: pytest.LogCaptureFixture, wake: bool
) -> None:
    """THE ORACLE for the drop: nine months are past the line, so eight go at one wake, one at the next.

    The monthly index is the record of what is left to drop, so a month that has
    gone is never chosen again. Over a wake's listing the planner names only the
    ledger's marks, and the drop step names the months it takes itself. A raw
    day goes with its month, so one in the month past the cap waits for it.
    """
    root = tmp_path / "checkout"
    old_months(root)
    kept = [month_file(root, month) for month in month_partition.months_between("2025-10", "2026-09")]

    with caplog.at_level(logging.INFO):
        first = compact(root, DROP_WAKE, wake=wake)

    assert monthly_covers(root) == month_partition.months_between("2025-09", "2026-09")
    assert chosen_on(caplog)["drops"] == {
        "start": "oldest-indexed",
        "first": "2025-01",
        "last": "2025-08",
        "stopped_because": "ceiling",
        "resume_from": "2025-09",
    }
    assert (first.stopped_because, first.resume_from) == (StopReason.CEILING, "2025-09")
    assert ledger.raw_days(state(root), VISUALS) == ["2025-09-05"]

    caplog.clear()
    with caplog.at_level(logging.INFO):
        second = compact(root, DROP_WAKE, wake=wake)

    assert monthly_covers(root) == month_partition.months_between("2025-10", "2026-09")
    assert chosen_on(caplog)["drops"] == {
        "start": "oldest-indexed",
        "first": "2025-09",
        "last": "2025-09",
    }
    assert second.stopped_because is StopReason.EXHAUSTED
    assert ledger.raw_days(state(root), VISUALS) == []

    caplog.clear()
    with caplog.at_level(logging.INFO):
        third = compact(root, DROP_WAKE, wake=wake)

    assert chosen_on(caplog)["drops"] == {"start": "oldest-indexed"}
    assert (third.taken, third.written) == ((), ())
    taken = [*first.taken, *second.taken]
    assert len(taken) == len(set(taken)), "a file was deleted at two wakes"
    assert all(path.is_file() for path in kept)
    assert disjoint(first) and disjoint(second)


def test_a_window_that_only_reports_keeps_each_old_month_and_names_it_again_at_every_wake(
    tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    """It names what a live pass deletes at that wake, keeps all of it, and names it again next time."""
    trees = [tmp_path / "live", tmp_path / "reports"]
    old_months(trees[0])
    shutil.copytree(trees[0], trees[1])
    before = files_under(trees[1])

    live = compact(trees[0], DROP_WAKE)
    for _ in range(2):
        caplog.clear()
        with caplog.at_level(logging.INFO):
            reported = compact(trees[1], DROP_WAKE, month_deletes_dry_run=True)

        assert chosen_on(caplog)["drops"] == {
            "start": "oldest-indexed",
            "first": "2025-01",
            "last": "2025-08",
            "stopped_because": "ceiling",
            "resume_from": "2025-09",
        }
        assert (reported.taken, reported.written) == ((), ())
        assert reported.stopped_because is StopReason.EXHAUSTED, "a report takes nothing"
        assert reported.selected == len(live.taken) == 10, "six month files and four raw files"
    assert files_under(trees[1]) == before


def test_an_old_month_with_no_row_goes_unwarned_and_one_whose_file_is_gone_warns(
    tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    """An `empty` entry has no file to miss; a `packed` one without its file is a fault to name."""
    root = tmp_path / "checkout"
    old_months(root)

    with caplog.at_level(logging.WARNING):
        compact(root, DROP_WAKE)

    assert not {QUIET_MONTH, GONE_MONTH} & set(monthly_covers(root))
    assert faults(caplog, f"month={QUIET_MONTH}") == []
    assert faults(caplog, f"month={GONE_MONTH}") == [f"fault={ledger.LedgerFault.FILE_MISSING}"]


def test_a_raw_day_past_the_line_goes_by_its_listed_paths_even_when_a_file_cannot_be_read(
    tmp_path: Path,
) -> None:
    """Nothing of it is opened, so a file that is not a ledger file neither keeps it nor stops the pass."""
    root = tmp_path / "checkout"
    old_months(root)
    folder = ledger.raw_root(state(root), VISUALS).joinpath(*UNREADABLE_DAY.split("-"))
    held = sorted(path.relative_to(root).as_posix() for path in folder.iterdir())

    outcome = compact(root, DROP_WAKE)

    assert outcome.stopped_because is not StopReason.FAILED, outcome.resume_from
    assert len(held) == 2 and set(held) <= set(outcome.taken)
    assert not any((root / path).exists() for path in held)

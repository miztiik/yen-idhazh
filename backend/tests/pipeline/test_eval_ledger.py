"""When is a measurement new, and what does the ledger do with one it already holds?"""

from __future__ import annotations

import csv
from pathlib import Path

import pytest
from conftest import REPO_ROOT

from idhazh import day_partition
from idhazh.contracts.eval_row import EvalRow
from idhazh.evals import archive as score_archive
from idhazh.evals import writer
from idhazh.ledger import STATE_DIRNAME

from ._builders import (
    row,
)

pytestmark = pytest.mark.slow


def test_the_ledger_writes_its_header_once(tmp_path: Path) -> None:
    state = tmp_path / "state"
    assert writer.append(state, [row()]) == 1
    assert writer.append(state, [row(item_id="ai-02", output_digest="b" * 64)]) == 1
    days = writer.ledger_days(state)
    assert len(days) == 1, "both rows are the same day, so they share a file"
    with days[0].open(encoding="utf-8") as handle:
        lines = list(csv.reader(handle))
    assert len(lines) == 3
    assert tuple(lines[0]) == writer.columns()


def test_two_days_of_rows_land_in_two_files(tmp_path: Path) -> None:
    """A run either side of midnight writes both, and neither is wrong.

    The row's own `date` files it, not the day the writer happened to run, so a
    replay of an older day cannot put September's rows in August's file.
    """
    state = tmp_path / "state"
    august = row()
    september = row(date="2026-09-01", run_id="2026-09-01-1", url_key="e" * 64)

    assert writer.append(state, [september, august]) == 2

    assert [day_partition.date_of(day) for day in writer.ledger_days(state)] == [
        august.date,
        september.date,
    ]
    assert [record["date"] for record in writer.records(state)] == [august.date, september.date]


def test_a_re_observation_of_the_same_measurement_writes_no_row(tmp_path: Path) -> None:
    """The doc's promise: an item whose inputs did not change writes no row at all.

    A later day can re-plan an address the published ledger has no record of. The
    summary comes back word for word, the scorer reads it with the same
    instrument, and the second row would only inflate the denominator.
    """
    state = tmp_path / "state"
    assert writer.append(state, [row()]) == 1
    again = row(date="2026-08-22", run_id="2026-08-22-1", item_id="ai-07")
    assert writer.append(state, [again]) == 0
    with writer.ledger_days(state)[0].open(encoding="utf-8") as handle:
        assert len(list(csv.reader(handle))) == 2


def test_a_re_observation_in_a_later_month_still_writes_no_row(tmp_path: Path) -> None:
    """Dedupe spans the partitions, or filing by day would quietly reopen the door.

    The promise is that a count over the ledger is a count of items. A dedupe
    scoped to the day being written would let August's measurement come back
    in September as a second row about the same thing.
    """
    state = tmp_path / "state"
    held = row()
    assert writer.append(state, [held]) == 1

    later = row(date="2026-09-14", run_id="2026-09-14-1", item_id="ai-07")

    assert writer.append(state, [later]) == 0
    assert [day_partition.date_of(day) for day in writer.ledger_days(state)] == [held.date]


def test_one_batch_cannot_carry_the_same_measurement_twice(tmp_path: Path) -> None:
    """The guard reads the batch as well as the file, or a fresh ledger dodges it."""
    ledger = tmp_path / "state"
    assert writer.append(ledger, [row(), row(item_id="ai-09")]) == 1


def test_a_measurement_whose_month_was_archived_is_still_not_new(tmp_path: Path) -> None:
    """The dedupe spans the archives too, or deleting a shard reopens the door.

    Sharding was the first way this could break and the fix was to read every
    partition. Archiving is the second: a month past
    `observability.scores_full_grain_months` has no rows left to read at all, so
    a dedupe over the rows alone would call every measurement in it new on the
    day it was deleted - and a count over the ledger would stop being a count of
    items, which is the one thing this ledger promises it is not.
    """
    state = tmp_path / "state"
    assert writer.append(state, [row()]) == 1
    days = writer.ledger_days(state)
    month = day_partition.month_of(days[0])
    summary = score_archive.summarise(
        days, month=month, observation_key=writer.OBSERVATION_KEY
    )
    score_archive.write(score_archive.archive_path(state, month), summary)
    for day in days:
        day.unlink()

    assert not writer.ledger_days(state)
    assert writer.append(state, [row(date="2026-09-14", run_id="2026-09-14-1")]) == 0
    assert not writer.ledger_days(state), "the archived measurement was written again"


def test_a_changed_output_is_a_new_measurement(tmp_path: Path) -> None:
    """Identical inputs and different words is the defect the ledger exists to catch."""
    ledger = tmp_path / "state"
    writer.append(ledger, [row()])
    assert writer.append(ledger, [row(output_digest="c" * 64)]) == 1


def test_a_changed_scorer_is_a_new_measurement(tmp_path: Path) -> None:
    """Same words read by a different instrument is a reading worth keeping."""
    ledger = tmp_path / "state"
    writer.append(ledger, [row()])
    assert writer.append(ledger, [row(scorer_version="hhem-2.2-open@cccccccc")]) == 1


def test_writing_nothing_creates_nothing(tmp_path: Path) -> None:
    ledger = tmp_path / "state"
    assert writer.append(ledger, []) == 0
    assert not ledger.exists()


def test_the_ledger_columns_match_the_contract() -> None:
    assert writer.columns() == EvalRow.csv_columns()


def _newest_committed_day() -> Path | None:
    """The newest committed score day file, found by three bounded listings.

    Newest year, then newest month, then newest day. That costs at most twelve
    plus thirty-one directory entries however long the project runs, where
    `writer.ledger_days` walks every partition on record and gains one a day
    (`CLAUDE.md` section 13, Guardrail #12).
    """
    root = REPO_ROOT / STATE_DIRNAME / writer.LEDGER_DIRNAME
    at = root
    for _ in range(2):
        names = sorted(entry.name for entry in at.iterdir() if entry.is_dir())
        if not names:
            return None
        at = at / names[-1]
    days = sorted(at.glob("*.csv"))
    return days[-1] if days else None


def test_the_committed_ledger_carries_todays_columns() -> None:
    """The header is written once, and the file is appended to forever.

    A contract that grew a column while the committed header did not would put
    more cells on tomorrow's row than the header names, and the dashboard reads
    cells by position.

    **The newest day and not every day**, because the newest is the one the next
    run appends to, and `writer.append` checks exactly the days it writes. An
    older day file nothing writes to cannot be corrupted by a run, and walking
    all of them would cost one more open a day for ever.
    """
    newest = _newest_committed_day()
    if newest is None:
        pytest.skip("no ledger committed yet")
    assert writer.read_header(newest) == writer.columns(), newest.name


def test_the_committed_ledger_still_takes_a_row_today(tmp_path: Path) -> None:
    """The migration, run against the real file rather than a copy of its shape.

    `require_matching_header` compares the header tuple exactly, so the commit
    that gave the contract a `source_digest` column stopped the committed ledger
    loading until the file was widened by the same column. This appends to a byte
    copy of the newest committed day, which is the run a release blocker would
    fail - and it is one file rather than every committed day, for the reason
    above.
    """
    newest = _newest_committed_day()
    if newest is None:
        pytest.skip("no ledger committed yet")
    date = day_partition.date_of(newest)
    state = tmp_path / "state"
    copied = writer.ledger_path(state, date)
    copied.parent.mkdir(parents=True)
    copied.write_bytes(newest.read_bytes())
    before = copied.read_text(encoding="utf-8").count("\n")

    assert writer.append(state, [row(url_key="d" * 64, date=date)]) == 1

    assert writer.read_header(copied) == writer.columns()
    assert copied.read_text(encoding="utf-8").count("\n") == before + 1


def test_a_row_older_than_the_premise_column_records_its_absence(tmp_path: Path) -> None:
    """An empty cell, never a digest computed today.

    A row scored before 2026-08-27 recorded no premise. Filling it in now would
    name text nobody read and would make a labeller's disagreement unreadable -
    which is the one thing the column exists to prevent.

    Driven from a row with the column removed. Walking the committed ledger cost
    a parse per row and asserted the ledger STILL HELD a row older than the
    column, which is a fuse timed to the day the last one ages out of retention.
    The cell-count check it carried belongs to `require_matching_header`, which
    refuses a mismatched append at write time - proved below.
    """
    old = row().model_dump(mode="json")
    old.pop("source_digest")

    migrated = EvalRow.model_validate(old)

    assert migrated.source_digest is None


def test_appending_under_a_stale_header_fails_loudly(tmp_path: Path) -> None:
    """Silent corruption is the alternative, and it is unrecoverable once shipped."""
    state = tmp_path / "state"
    writer.append(state, [row()])
    day = writer.ledger_days(state)[0]
    kept = day.read_text(encoding="utf-8").split("\n")
    kept[0] = ",".join(writer.columns()[:-1])
    day.write_text("\n".join(kept), encoding="utf-8")
    with pytest.raises(ValueError, match="Migrate the ledger"):
        writer.append(state, [row(item_id="ai-02")])

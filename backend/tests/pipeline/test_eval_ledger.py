"""When is a measurement new, and what does the ledger do with one it already holds?

Every case here is driven from a ledger built in the test. What the committed
ledger happens to hold is the producer's question - `idhazh validate-days` reads
it back through this contract - and asking it here timed a red build to the day
retention rolled a day file out (`CLAUDE.md` section 13).
"""

from __future__ import annotations

import csv
from pathlib import Path

from idhazh import day_shards
from idhazh.contracts.base import ServerJob
from idhazh.contracts.eval_row import EvalRow
from idhazh.evals import archive as score_archive
from idhazh.evals import writer

from ._builders import (
    row,
)

#: The writer every case below files as. `assemble` is the job that scores a
#: whole day, and it runs one shard, so this is the identity a finished run
#: leaves. A case that needs two writers names its own second one.
A_RUN = "2026-08-21-1"


def put(
    state: Path, rows: list[EvalRow], *, run_id: str = A_RUN, attempt: int = 1
) -> int:
    """One writer's measurements, filed the way a finished run files them."""
    return writer.append_segment(
        state, rows, run_id=run_id, attempt=attempt, job=ServerJob.ASSEMBLE, shard=0
    )


def test_one_writers_rows_for_a_day_share_one_file_with_one_header(tmp_path: Path) -> None:
    """A writer owns its file, so its whole slice of a day is written at once."""
    state = tmp_path / "state"
    assert put(state, [row(), row(item_id="ai-02", output_digest="b" * 64)]) == 2
    days = writer.ledger_days(state)
    assert len(days) == 1, "one writer, one day, one file"
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

    assert put(state, [september, august]) == 2

    assert [day_shards.date_of(day) for day in writer.ledger_days(state)] == [
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
    assert put(state, [row()]) == 1
    again = row(date="2026-08-22", run_id="2026-08-22-1", item_id="ai-07")
    assert put(state, [again], run_id="2026-08-22-1") == 0
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
    assert put(state, [held]) == 1

    later = row(date="2026-09-14", run_id="2026-09-14-1", item_id="ai-07")

    assert put(state, [later], run_id="2026-09-14-1") == 0
    assert [day_shards.date_of(day) for day in writer.ledger_days(state)] == [held.date]


def test_one_batch_cannot_carry_the_same_measurement_twice(tmp_path: Path) -> None:
    """The guard reads the batch as well as the file, or a fresh ledger dodges it."""
    state = tmp_path / "state"
    assert put(state, [row(), row(item_id="ai-09")]) == 1


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
    assert put(state, [row()]) == 1
    days = writer.ledger_days(state)
    month = day_shards.date_of(days[0])[:7]
    summary = score_archive.summarise(
        days, month=month, observation_key=writer.OBSERVATION_KEY
    )
    score_archive.write(score_archive.archive_path(state, month), summary)
    for day in days:
        day.unlink()

    assert not writer.ledger_days(state)
    assert put(state, [row(date="2026-09-14", run_id="2026-09-14-1")], run_id="2026-09-14-1") == 0
    assert not writer.ledger_days(state), "the archived measurement was written again"


def test_a_changed_output_is_a_new_measurement(tmp_path: Path) -> None:
    """Identical inputs and different words is the defect the ledger exists to catch."""
    state = tmp_path / "state"
    put(state, [row()])
    assert put(state, [row(output_digest="c" * 64)], attempt=2) == 1


def test_a_changed_scorer_is_a_new_measurement(tmp_path: Path) -> None:
    """Same words read by a different instrument is a reading worth keeping."""
    state = tmp_path / "state"
    put(state, [row()])
    assert put(state, [row(scorer_version="hhem-2.2-open@cccccccc")], attempt=2) == 1


def test_writing_nothing_creates_nothing(tmp_path: Path) -> None:
    state = tmp_path / "state"
    assert put(state, []) == 0
    assert not state.exists()


def test_the_ledger_columns_match_the_contract() -> None:
    assert writer.columns() == EvalRow.csv_columns()


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

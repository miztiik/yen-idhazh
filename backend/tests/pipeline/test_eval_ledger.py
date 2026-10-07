"""When is a measurement new, and what does the ledger do with one it already holds?

Every case here is driven from a ledger built in the test. What the committed
ledger happens to hold is the producer's question - `idhazh check-publication` reads
it back through this contract - and asking it here timed a red build to the day
retention rolled a day file out (`CLAUDE.md` section 13).
"""

from __future__ import annotations

from pathlib import Path

from conftest import seed_scores

from idhazh import ledger
from idhazh.contracts.eval_row import EvalRow
from idhazh.contracts.ledger_name import LedgerName
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
    return seed_scores(state, rows, run_id=run_id, attempt=attempt)


def test_one_writers_rows_for_a_day_share_one_file(tmp_path: Path) -> None:
    """A writer owns its file, so its whole slice of a day is written at once."""
    state = tmp_path / "state"
    rows = [row(), row(item_id="ai-02", output_digest="b" * 64)]
    assert put(state, rows) == 2
    files = ledger.list_raw_files(state, LedgerName.SUMMARY_QUALITY_EVALS)
    assert len(files) == 1, "one writer, one day, one file"
    assert files[0].envelope.row_schema_version == EvalRow.schema_version()
    assert ledger.load([files[0].path], model=EvalRow) == rows


def test_two_days_of_rows_land_in_two_files(tmp_path: Path) -> None:
    """A run either side of midnight writes both, and neither is wrong.

    The row's own `date` files it, not the day the writer happened to run, so a
    replay of an older day cannot put September's rows in August's file.
    """
    state = tmp_path / "state"
    august = row()
    september = row(date="2026-09-01", run_id="2026-09-01-1", url_key="e" * 64)

    assert put(state, [september, august]) == 2

    assert [held.envelope.covers for held in ledger.list_raw_files(state, LedgerName.SUMMARY_QUALITY_EVALS)] == [
        august.date,
        september.date,
    ]
    assert [record["date"] for record in writer.records(state)] == [august.date, september.date]


def test_a_re_observation_on_a_later_day_keeps_its_own_days_row(tmp_path: Path) -> None:
    """A later day can re-plan an address the published ledger has no record of.

    If the summary comes back word for word and the scorer reads it with the
    same instrument, the later day files its own row, so a read of that day
    still sees what the day measured.
    """
    state = tmp_path / "state"
    assert put(state, [row()]) == 1
    again = row(date="2026-08-22", run_id="2026-08-22-1", item_id="ai-07")
    assert put(state, [again], run_id="2026-08-22-1") == 1

    assert ledger.held_days(state, LedgerName.SUMMARY_QUALITY_EVALS) == ["2026-08-21", "2026-08-22"]
    assert ledger.load_days(
        state, LedgerName.SUMMARY_QUALITY_EVALS, [again.date], model=EvalRow
    ) == [again]


def test_a_whole_ledger_read_keeps_one_row_across_months(tmp_path: Path) -> None:
    """A whole-ledger read settles across every partition, so a count over it counts measurements.

    August's measurement filed again in September is read once, and the row
    kept is the first.
    """
    state = tmp_path / "state"
    held = row()
    assert put(state, [held]) == 1

    later = row(date="2026-09-14", run_id="2026-09-14-1", item_id="ai-07")

    assert put(state, [later], run_id="2026-09-14-1") == 1
    assert list(writer.records(state)) == [held.csv_row()]


def test_one_write_carrying_the_same_measurement_twice_is_read_once(tmp_path: Path) -> None:
    """The settlement reads the file as well as the ledger, or a fresh ledger dodges it."""
    state = tmp_path / "state"
    assert put(state, [row(), row(item_id="ai-09")]) == 2
    assert len(list(writer.records(state))) == 1


def test_a_changed_output_is_a_new_measurement(tmp_path: Path) -> None:
    """Identical inputs and different words is the defect the ledger exists to catch."""
    state = tmp_path / "state"
    put(state, [row()])
    put(state, [row(output_digest="c" * 64)], run_id="2026-08-21-2")
    assert len(list(writer.records(state))) == 2


def test_a_changed_scorer_is_a_new_measurement(tmp_path: Path) -> None:
    """Same words read by a different instrument is a reading worth keeping."""
    state = tmp_path / "state"
    put(state, [row()])
    put(state, [row(scorer_version="hhem-2.2-open@cccccccc")], run_id="2026-08-21-2")
    assert len(list(writer.records(state))) == 2


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
    The cell-count check it carried went with the CSV files: the ledger door
    writes every row under the columns its contract declares.
    """
    old = row().model_dump(mode="json")
    old.pop("source_digest")

    migrated = EvalRow.model_validate(old)

    assert migrated.source_digest is None

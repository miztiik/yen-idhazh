"""Does the one-shot migration move every CSV row onto the door, once, and prove it?

The oracle is migration parity: every row the CSV held reads back from the file
the migration wrote, field for field and cell for cell, with no row lost and
none invented - and nothing is deleted until that is true. The exit codes are
the contract a person reads: 0 moved or nothing to move, 1 not proven or a CSV
left, 2 a committed file for the same work unit that holds other rows.

Every CSV here is written under `tmp_path` from contract rows, in the two
layouts the ledgers were committed as, so nothing reads the committed `state/`
(CLAUDE.md section 13).
"""

from __future__ import annotations

from pathlib import Path
from typing import Final

import pytest

from idhazh import ledger
from idhazh.contracts.base import ServerJob
from idhazh.contracts.feed_retirement import FeedRetirementRow, RetirementCause
from idhazh.contracts.ledger_name import LedgerName
from idhazh.contracts.visual_prune import VisualPruneRow
from utilities import migrate_csv

pytestmark = pytest.mark.contract

RUN_ID: Final = "2026-09-28-1"
GIT_SHA: Final = "b" * 40
ADDRESS: Final = "c" * 64
OTHER_ADDRESS: Final = "d" * 64


def a_410(*, on: str = "2026-09-02", key: str = ADDRESS) -> FeedRetirementRow:
    return FeedRetirementRow(
        version=FeedRetirementRow.schema_version(),
        feed_id="trade-press",
        endpoint_key=key,
        retired_on=on,
        decided_by_run=f"{on}-6",
        cause=RetirementCause.HTTP_410,
        evidence_run_ids=tuple(f"{on}-{n}" for n in range(1, 6)),
    )


def a_low_yield(*, on: str = "2026-09-20") -> FeedRetirementRow:
    return FeedRetirementRow(
        version=FeedRetirementRow.schema_version(),
        feed_id="quiet-desk",
        endpoint_key=OTHER_ADDRESS,
        retired_on=on,
        decided_by_run=f"{on}-3",
        cause=RetirementCause.LOW_YIELD,
        evidence_dates=("2026-09-18", "2026-09-19"),
    )


def a_pass(*, on: str, run: str, before: int = 1000) -> VisualPruneRow:
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


RETIREMENTS: Final = (a_410(), a_low_yield())
PASSES_06: Final = (a_pass(on="2026-09-06", run="3"), a_pass(on="2026-09-06", run="4"))
PASSES_07: Final = (a_pass(on="2026-09-07", run="1", before=2000),)


def write_csv(path: Path, rows: tuple[FeedRetirementRow, ...] | tuple[VisualPruneRow, ...]) -> Path:
    """One CSV file in the layout the ledger was committed as, header first."""
    columns = type(rows[0]).csv_columns() if rows else FeedRetirementRow.csv_columns()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        ledger.render_file(columns, [row.csv_row() for row in rows]), encoding="utf-8", newline=""
    )
    return path


def a_committed_tree(state: Path) -> Path:
    """Both ledgers as the repository held them before the move."""
    write_csv(state / "feed-retirements.csv", RETIREMENTS)
    write_csv(state / "visual-prunes" / "2026" / "09" / "06.csv", PASSES_06)
    write_csv(state / "visual-prunes" / "2026" / "09" / "07.csv", PASSES_07)
    return state


def run(state: Path, *extra: str) -> int:
    return migrate_csv.main(
        ["--state-dir", str(state), "--run-id", RUN_ID, "--git-sha", GIT_SHA, *extra]
    )


def snapshot(state: Path) -> dict[str, bytes]:
    """Every file under the state tree, by its path, with its bytes."""
    return {
        path.relative_to(state).as_posix(): path.read_bytes()
        for path in sorted(state.rglob("*"))
        if path.is_file()
    }


def test_every_row_of_both_ledgers_reads_back_and_the_csv_is_gone(tmp_path: Path) -> None:
    """The parity oracle, on a tree that carries the cases the committed one does.

    Two retirements on two days and two causes, and a cleanup day holding two
    runs beside a day holding one, so a migration that filed by run rather than
    by day, or dropped an evidence cell, would read back a different series.
    """
    state = a_committed_tree(tmp_path / "state")

    assert run(state) == migrate_csv.EXIT_MIGRATED

    assert migrate_csv.csv_files(state, LedgerName.FEED_RETIREMENTS) == []
    assert migrate_csv.csv_files(state, LedgerName.VISUAL_PRUNES) == []
    assert not (state / "visual-prunes").exists()
    assert ledger.load_retirements(state) == list(RETIREMENTS)
    assert ledger.load_visual_prunes(state) == [*PASSES_06, *PASSES_07]
    written = [
        *ledger.list_raw_files(state, LedgerName.FEED_RETIREMENTS),
        *ledger.list_raw_files(state, LedgerName.VISUAL_PRUNES),
    ]
    assert [held.envelope.covers for held in written] == [
        "2026-09-02",
        "2026-09-20",
        "2026-09-06",
        "2026-09-07",
    ]
    for held in written:
        identity = held.envelope.identity
        assert (identity.run_id, identity.attempt, identity.job, identity.shard) == (
            RUN_ID,
            1,
            ServerJob.MIGRATE,
            0,
        )
        assert (identity.producer, identity.git_sha) == (migrate_csv.PRODUCER, GIT_SHA)


def test_a_second_run_writes_nothing_and_exits_0(tmp_path: Path) -> None:
    """Running it twice is safe by construction: the same arguments mint the same units."""
    state = a_committed_tree(tmp_path / "state")
    assert run(state) == migrate_csv.EXIT_MIGRATED
    before = snapshot(state)

    assert run(state) == migrate_csv.EXIT_MIGRATED

    assert snapshot(state) == before


def test_a_run_that_stopped_before_deleting_is_finished_by_the_next(tmp_path: Path) -> None:
    """A file for the unit that matches is left alone, and the CSV beside it is deleted."""
    state = a_committed_tree(tmp_path / "state")
    assert run(state) == migrate_csv.EXIT_MIGRATED
    written = snapshot(state)
    a_committed_tree(state)

    assert run(state, "--git-sha", "e" * 40) == migrate_csv.EXIT_MIGRATED

    assert snapshot(state) == written
    assert migrate_csv.csv_files(state, LedgerName.VISUAL_PRUNES) == []


def test_a_committed_file_that_holds_other_rows_exits_2_and_deletes_nothing(
    tmp_path: Path,
) -> None:
    """Two migrations that disagree are both kept, because overwriting one is one-way."""
    state = a_committed_tree(tmp_path / "state")
    assert run(state) == migrate_csv.EXIT_MIGRATED
    written = snapshot(state)
    changed = (a_pass(on="2026-09-07", run="1", before=9999),)
    csv = write_csv(state / "visual-prunes" / "2026" / "09" / "07.csv", changed)

    assert run(state) == migrate_csv.EXIT_DISAGREES

    assert csv.exists()
    assert {name: data for name, data in snapshot(state).items() if name in written} == written


def test_check_exits_1_while_a_csv_remains_and_writes_nothing(tmp_path: Path) -> None:
    state = a_committed_tree(tmp_path / "state")
    before = snapshot(state)

    assert run(state, "--check") == migrate_csv.EXIT_NOT_PROVEN
    assert snapshot(state) == before

    assert run(state) == migrate_csv.EXIT_MIGRATED
    assert run(state, "--check") == migrate_csv.EXIT_MIGRATED


def test_a_row_that_does_not_read_as_its_contract_exits_1_and_moves_nothing(
    tmp_path: Path,
) -> None:
    """A row nobody can read is a row that would be lost, so the whole run stops."""
    state = a_committed_tree(tmp_path / "state")
    day = state / "visual-prunes" / "2026" / "09" / "07.csv"
    day.write_text(day.read_text(encoding="utf-8").replace(",2000,2000", ",2000,3000"), encoding="utf-8")
    before = snapshot(state)

    assert run(state) == migrate_csv.EXIT_NOT_PROVEN

    assert snapshot(state) == before


def test_a_cell_that_would_come_back_spelled_differently_removes_what_it_wrote(
    tmp_path: Path,
) -> None:
    """Cell for cell, not only field for field: `true` reads as a bool and comes back `True`.

    The row parses, so the file is written - and the read-back does not match
    the CSV the person committed, so the run removes the files it wrote and
    leaves every CSV where it was.
    """
    state = a_committed_tree(tmp_path / "state")
    day = state / "visual-prunes" / "2026" / "09" / "07.csv"
    day.write_text(day.read_text(encoding="utf-8").replace(",True,", ",true,"), encoding="utf-8")
    before = snapshot(state)

    assert run(state) == migrate_csv.EXIT_NOT_PROVEN

    assert snapshot(state) == before
    assert ledger.list_raw_files(state, LedgerName.VISUAL_PRUNES) == []


def test_one_ledger_can_be_moved_alone(tmp_path: Path) -> None:
    state = a_committed_tree(tmp_path / "state")

    assert run(state, "--ledger", LedgerName.VISUAL_PRUNES.value) == migrate_csv.EXIT_MIGRATED

    assert migrate_csv.csv_files(state, LedgerName.FEED_RETIREMENTS) != []
    assert migrate_csv.csv_files(state, LedgerName.VISUAL_PRUNES) == []
    assert ledger.list_raw_files(state, LedgerName.FEED_RETIREMENTS) == []


def test_a_header_only_csv_is_deleted_and_writes_no_file(tmp_path: Path) -> None:
    """The committed retirements held no row, and a ledger with no row moves as no file."""
    state = tmp_path / "state"
    write_csv(state / "feed-retirements.csv", ())

    assert run(state, "--ledger", LedgerName.FEED_RETIREMENTS.value) == migrate_csv.EXIT_MIGRATED

    assert snapshot(state) == {}


def test_a_malformed_run_id_is_refused_before_anything_is_read(tmp_path: Path) -> None:
    state = a_committed_tree(tmp_path / "state")
    before = snapshot(state)

    with pytest.raises(SystemExit):
        migrate_csv.main(["--state-dir", str(state), "--run-id", "today", "--git-sha", GIT_SHA])

    assert snapshot(state) == before

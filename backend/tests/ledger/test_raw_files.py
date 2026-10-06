"""Which raw files does a reader trust, and in what order does it read them?

The door writes a file per writer and removes nothing, so two attempts at one
work unit leave two files and a directory listing is whatever the filesystem
hands back. These tests hold the reader's half of that rule: the highest attempt
per unit, the order read from each file's own envelope, and a file this build
cannot read skipped by name rather than stopping the read.

Every tree here is written under `tmp_path` through the door itself, so nothing
reads the committed `state/` (CLAUDE.md section 13).
"""

from __future__ import annotations

import time
import uuid
from pathlib import Path
from typing import Final

import pytest
from conftest import CONTRACT_FIXTURES_DIR

from idhazh import ledger
from idhazh.contracts.base import ServerJob
from idhazh.contracts.file_envelope import Format, RowIdentity, WriterIdentity
from idhazh.contracts.item_health import ItemHealthRow
from idhazh.contracts.ledger_name import LedgerName
from idhazh.contracts.visual_prune import VisualPruneRow

pytestmark = pytest.mark.contract

WHICH: Final = LedgerName.VISUAL_PRUNES
A_DAY: Final = "2026-09-06"
NEXT_DAY: Final = "2026-09-07"


def a_pass(*, on: str = A_DAY, run: str = "1", before: int = 1000) -> VisualPruneRow:
    """One reporting cleanup pass, the shape every committed row has."""
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


def filed(state: Path, row: VisualPruneRow, *, attempt: int = 1, fmt: Format | None = None) -> Path:
    """One pass through the door, under the identity its own run would carry."""
    (written,) = ledger.persist(
        state,
        [row],
        ledger=WHICH,
        covers=row.date,
        identity=WriterIdentity(
            run_id=row.run_id,
            attempt=attempt,
            job=ServerJob.ASSEMBLE,
            shard=0,
            producer="gardener.tasks.visual_prune",
            git_sha="a" * 40,
        ),
        fmt=fmt,
    )
    return written


def test_a_ledger_nothing_wrote_has_no_files(tmp_path: Path) -> None:
    """A fresh clone has no raw folder, and that is no history rather than a fault."""
    assert ledger.list_raw_files(tmp_path, WHICH) == []
    assert ledger.load_current_rows(tmp_path, WHICH, model=VisualPruneRow, key=("date",)) == []


def test_files_come_back_by_the_day_they_cover_not_the_order_they_were_written(
    tmp_path: Path,
) -> None:
    """The later day is written first, so a reader that kept write order reads it first."""
    later = filed(tmp_path, a_pass(on=NEXT_DAY))
    earlier = filed(tmp_path, a_pass(on=A_DAY))

    assert [held.path for held in ledger.list_raw_files(tmp_path, WHICH)] == [earlier, later]


def test_one_days_files_come_back_by_their_write_instant_not_their_names(
    tmp_path: Path,
) -> None:
    """The order inside a day is the envelope's clock, so a name that sorts first changes nothing.

    A `file_id` starts with its clock, so a directory listing agrees with the
    envelope today. The second file is renamed to sort before the first, which
    is what a reader leaning on the listing would get wrong.
    """
    first = filed(tmp_path, a_pass(run="1"))
    time.sleep(0.005)
    second = filed(tmp_path, a_pass(run="2"))
    renamed = second.with_name(f"{uuid.UUID(int=0)}{second.suffix}")
    second.rename(renamed)
    assert renamed.name < first.name

    assert [held.path for held in ledger.list_raw_files(tmp_path, WHICH)] == [first, renamed]
    assert [row.run_id for row in ledger.load_visual_prunes(tmp_path)] == [
        f"{A_DAY}-1",
        f"{A_DAY}-2",
    ]


def test_the_highest_attempt_at_a_unit_is_the_one_read_whatever_was_written_last(
    tmp_path: Path,
) -> None:
    """A re-run replaces its attempt. The second attempt is written first here on purpose."""
    filed(tmp_path, a_pass(before=200), attempt=2)
    filed(tmp_path, a_pass(before=100), attempt=1)

    assert len(ledger.list_raw_files(tmp_path, WHICH)) == 2
    assert [row.payload_bytes_before for row in ledger.load_visual_prunes(tmp_path)] == [200]


def test_two_runs_of_one_day_are_two_units_and_both_are_read(tmp_path: Path) -> None:
    """A second run is a different unit, so the union keeps both passes."""
    filed(tmp_path, a_pass(run="1"))
    filed(tmp_path, a_pass(run="2"))

    assert len(ledger.load_visual_prunes(tmp_path)) == 2


def test_a_json_lines_file_is_read_like_a_parquet_one(tmp_path: Path) -> None:
    """`ledger.format` may name either container, so the walk takes every file in a day."""
    written = filed(tmp_path, a_pass(), fmt=Format.JSON)

    assert written.suffix == ".json"
    assert ledger.load_visual_prunes(tmp_path) == [a_pass()]


def test_a_file_filed_under_another_day_is_skipped_and_named(
    tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    """The envelope says which day a file covers, and the folder has to agree.

    A file moved into the wrong day folder was put there by something other than
    the door, so it is read as unreadable: skipped, with the path in the warning.
    """
    written = filed(tmp_path, a_pass(on=A_DAY))
    wrong = ledger.raw_path(tmp_path, WHICH, NEXT_DAY, uuid.UUID(written.stem))
    wrong.parent.mkdir(parents=True)
    written.rename(wrong)

    with caplog.at_level("WARNING"):
        assert ledger.list_raw_files(tmp_path, WHICH) == []

    assert f"raw/visual-prunes/2026/09/07/{wrong.name}" in caplog.text


def test_a_nested_state_root_warning_names_the_real_path(
    tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    """A trial case root is shown from its containing `state/`, not as production."""
    state = tmp_path / "state" / "pipeline-tests" / "case-2026-09-06"
    written = filed(state, a_pass(on=A_DAY))
    wrong = ledger.raw_path(state, WHICH, NEXT_DAY, uuid.UUID(written.stem))
    wrong.parent.mkdir(parents=True)
    written.rename(wrong)

    with caplog.at_level("WARNING"):
        assert ledger.list_raw_files(state, WHICH) == []

    assert (
        f"state/pipeline-tests/case-2026-09-06/raw/visual-prunes/2026/09/07/{wrong.name}"
        in caplog.text
    )


# --- the settlement, over rows written out literally --------------------------------

#: Two work units, spelled the way the door stamps a `unit_id` cell.
UNIT_A: Final = "7b2f1c84-0e5a-53d1-9c40-1f8b6a2e4d07"
UNIT_B: Final = "0c9d2e71-4a6b-5f30-8e12-3d4c5b6a7980"


def held(unit: str, attempt: int, *, run: str, before: int) -> ledger.StoredRow[VisualPruneRow]:
    """One row as a file holds it: the identity cells a writer stamped, and the row."""
    return ledger.StoredRow(
        identity=RowIdentity(
            ledger=WHICH,
            covers=A_DAY,
            run_id=f"{A_DAY}-{run}",
            attempt=attempt,
            job=ServerJob.ASSEMBLE,
            shard=0,
            unit_id=unit,
        ),
        row=a_pass(run=run, before=before),
    )


def test_settling_keeps_the_highest_attempt_of_each_unit_in_the_order_given() -> None:
    """Attempt 2 filed one row where attempt 1 filed two, and still replaces both."""
    first_try = [held(UNIT_A, 1, run="1", before=100), held(UNIT_A, 1, run="3", before=300)]
    other = held(UNIT_B, 1, run="2", before=200)
    second_try = held(UNIT_A, 2, run="1", before=111)

    settled = ledger.settle_rows([first_try, [other], [second_try]], ledger.VISUAL_PRUNE_KEY)

    assert settled == [other, second_try]


def test_one_attempt_that_wrote_a_unit_twice_is_its_later_file() -> None:
    """Two files at one attempt of one unit: the later file's rows, and only those."""
    earlier_file = [held(UNIT_A, 1, run="1", before=100), held(UNIT_A, 1, run="3", before=300)]
    later_file = [held(UNIT_A, 1, run="1", before=150)]

    settled = ledger.settle_rows([earlier_file, later_file], ledger.VISUAL_PRUNE_KEY)

    assert settled == later_file


def test_settling_keeps_the_first_row_of_a_key_two_units_both_filed() -> None:
    """Two runs that are not attempts at one unit, filing one key: the first filed wins."""
    earlier = held(UNIT_A, 1, run="1", before=100)
    later = held(UNIT_B, 1, run="1", before=999)

    assert ledger.settle_rows([[earlier], [later]], ledger.VISUAL_PRUNE_KEY) == [earlier]


def an_item(
    unit: str, *, machine: bool, fetch_ms: int | None = None
) -> ledger.StoredRow[ItemHealthRow]:
    """One item's health row, as a work shard (`machine`) or assemble's census filed it."""
    base = ItemHealthRow.model_validate_json(
        (CONTRACT_FIXTURES_DIR / "item-health-row" / "published.json").read_text(encoding="utf-8")
    )
    row = ItemHealthRow.model_validate(
        {
            **base.model_dump(),
            "machine_job": ServerJob.WORK if machine else None,
            "machine_shard": 0 if machine else None,
            "fetch_ms": fetch_ms,
        }
    )
    return ledger.StoredRow(
        identity=RowIdentity(
            ledger=LedgerName.ITEM_HEALTH,
            covers=row.date,
            run_id=row.run_id,
            attempt=1,
            job=ServerJob.WORK if machine else ServerJob.ASSEMBLE,
            shard=0,
            unit_id=unit,
        ),
        row=row,
    )


@pytest.mark.parametrize("census_first", [True, False], ids=["census-first", "work-first"])
def test_a_key_with_a_preference_keeps_the_row_it_prefers_whichever_was_filed_first(
    census_first: bool,
) -> None:
    """The item-health key prefers the row naming its machine, over any filing order."""
    work, census = an_item(UNIT_A, machine=True), an_item(UNIT_B, machine=False)
    files = [[census], [work]] if census_first else [[work], [census]]

    assert ledger.settle_rows(files, ledger.ITEM_HEALTH_KEY) == [work]


def test_a_settled_row_is_kept_whole_and_a_cell_only_the_dropped_row_held_is_named(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Rows are not merged cell by cell: the census row's own reading goes, and says so."""
    work = an_item(UNIT_A, machine=True)
    census = an_item(UNIT_B, machine=False, fetch_ms=40)

    with caplog.at_level("WARNING"):
        (kept,) = ledger.settle_rows([[census], [work]], ledger.ITEM_HEALTH_KEY)

    assert kept.row.fetch_ms is None
    assert "cell=fetch_ms" in caplog.text


# --- what the compaction reads: one day, strictly ---------------------------------


def test_one_days_files_are_read_strictly_and_a_stray_is_refused_by_name(tmp_path: Path) -> None:
    """A reader that deletes what it read may not skip a file, so one it cannot read stops it."""
    written = filed(tmp_path, a_pass())
    assert [one.path for one in ledger.read_day_files(tmp_path, WHICH, A_DAY)] == [written]
    stray = written.parent / "notes.txt"
    stray.write_text("not a ledger file\n", encoding="ascii")

    with pytest.raises(ValueError, match=r"raw/visual-prunes/2026/09/06/notes\.txt cannot be read"):
        ledger.read_day_files(tmp_path, WHICH, A_DAY)
    assert ledger.read_day_files(tmp_path, WHICH, NEXT_DAY) == []


def test_a_nested_state_root_refusal_names_the_real_path(tmp_path: Path) -> None:
    """Strict readers report the nested case root, not a false production path."""
    state = tmp_path / "state" / "pipeline-tests" / "case-2026-09-06"
    written = filed(state, a_pass())
    stray = written.parent / "notes.txt"
    stray.write_text("not a ledger file\n", encoding="ascii")

    with pytest.raises(
        ValueError,
        match=(
            r"state/pipeline-tests/case-2026-09-06/raw/visual-prunes/2026/09/06/"
            r"notes\.txt cannot be read"
        ),
    ):
        ledger.read_day_files(state, WHICH, A_DAY)


def test_one_days_folder_names_each_file_it_cannot_read_beside_the_files_it_can(
    tmp_path: Path,
) -> None:
    """The compaction moves a file it cannot read aside, so its read names that file and goes on."""
    written = filed(tmp_path, a_pass())
    stray = written.parent / "notes.txt"
    stray.write_text("not a ledger file\n", encoding="ascii")

    found = ledger.read_day_folder(tmp_path, WHICH, A_DAY)

    assert [one.path for one in found.files] == [written]
    assert [path for path, _why in found.unreadable] == [stray]
    assert ledger.read_day_folder(tmp_path, WHICH, NEXT_DAY) == ledger.DayFolder(
        files=[], unreadable=[]
    )


def test_the_days_a_ledger_holds_raw_files_for(tmp_path: Path) -> None:
    """Folder names only: an emptied day is not a raw day."""
    filed(tmp_path, a_pass(on=A_DAY))
    emptied = filed(tmp_path, a_pass(on=NEXT_DAY))
    emptied.unlink()

    assert ledger.raw_days(tmp_path, WHICH) == [A_DAY]

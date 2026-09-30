"""Is every date of a ledger read from exactly one file, and is a missing day named rather than skipped?

A ledger the door files lives in three kinds of file as it ages - raw files,
one compact file a day, one compact file a month - and the reader in
`ledger/ledger_files.py` reads the month when the monthly index names it, else
the day when the daily index names it, else the raw files of that day. These
tests hold that rule over a small tree holding all three, and hold the reader
to answering what the raw reader answered for a ledger nothing has compacted.

Every tree is written under `tmp_path` through the door, inside each test, so
nothing reads the committed `state/` (CLAUDE.md section 13).
"""

from __future__ import annotations

import logging
from datetime import date, timedelta
from pathlib import Path
from typing import Final

import pytest

from idhazh import ledger
from idhazh.contracts.base import ServerJob
from idhazh.contracts.feed_retirement import FeedRetirementRow
from idhazh.contracts.file_envelope import Period, RowIdentity, WriterIdentity
from idhazh.contracts.ledger_index import CompactEntry, CompactIndex
from idhazh.contracts.ledger_name import LedgerName
from idhazh.contracts.ledgers import Grain
from idhazh.contracts.visual_prune import VisualPruneRow

pytestmark = pytest.mark.contract

WHICH: Final = LedgerName.VISUAL_PRUNES

#: The writer the compact files name: a compaction, not the rows' own writers.
COMPACTION: Final = WriterIdentity(
    run_id="2026-09-28-1",
    attempt=1,
    job=ServerJob.RUN_TASKS,
    shard=0,
    producer="gardener.tasks.compaction",
    git_sha="0" * 40,
)


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


def filed(state: Path, row: VisualPruneRow, *, attempt: int = 1) -> Path:
    """One raw file, through the door, under the identity its own run carries."""
    (written,) = ledger.persist(
        state,
        [row],
        ledger=WHICH,
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


def kept(row: VisualPruneRow) -> ledger.StoredRow[VisualPruneRow]:
    """A row as a compact file keeps it: with the identity its raw file gave it."""
    unit = ledger.unit_id(
        ledger=WHICH,
        covers=row.date,
        run_id=row.run_id,
        job=ServerJob.RUN_TASKS,
        shard=0,
        producer="gardener.tasks.visual_prune",
    )
    return ledger.StoredRow(
        identity=RowIdentity(
            ledger=WHICH,
            covers=row.date,
            run_id=row.run_id,
            attempt=1,
            job=ServerJob.RUN_TASKS,
            shard=0,
            unit_id=str(unit),
        ),
        row=row,
    )


def compacted(state: Path, period: Period, covers: str, rows: list[VisualPruneRow]) -> Path:
    """One compact file, written through the door the way the compaction writes it."""
    return ledger.persist_period(
        state,
        [kept(row) for row in rows],
        model=VisualPruneRow,
        ledger=WHICH,
        period=period,
        covers=covers,
        identity=COMPACTION,
        built_from=len(rows),
    )


def indexed(state: Path, period: Period, covers: list[str]) -> Path:
    """One period's index naming these periods, written whole."""
    index = CompactIndex(
        version=CompactIndex.schema_version(),
        ledger=WHICH,
        period=period,
        entries=[CompactEntry(covers=one, rows=1, bytes=1) for one in covers],
    )
    path = ledger.compact_index_path(state, WHICH, period)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(index.to_json().encode("ascii"))
    return path


def days(first: str, last: str) -> list[str]:
    start, end = date.fromisoformat(first), date.fromisoformat(last)
    return [(start + timedelta(days=step)).isoformat() for step in range((end - start).days + 1)]


def a_tree_with_every_kind_of_file(state: Path) -> dict[str, Path]:
    """A month, three compacted days and a hole, a re-run waiting, and two open raw days.

    July is one month file. 1, 2 and 4 August are daily files, and 3 August is
    named by neither index, which is a hole; it still has a raw file, which is
    read and reported. 2 August has a re-run's raw file waiting for the next
    compaction, which is not read. 5 and 6 August have not been compacted.
    """
    made = {
        "july": compacted(state, Period.MONTHLY, "2026-07", [a_pass("2026-07-05")]),
        "first": compacted(state, Period.DAILY, "2026-08-01", [a_pass("2026-08-01")]),
        "second": compacted(state, Period.DAILY, "2026-08-02", [a_pass("2026-08-02")]),
        "fourth": compacted(state, Period.DAILY, "2026-08-04", []),
        "waiting": filed(state, a_pass("2026-08-02", before=7), attempt=2),
        "hole": filed(state, a_pass("2026-08-03")),
        "fifth": filed(state, a_pass("2026-08-05")),
        "sixth": filed(state, a_pass("2026-08-06", run="2")),
    }
    indexed(state, Period.MONTHLY, ["2026-07"])
    indexed(state, Period.DAILY, ["2026-08-01", "2026-08-02", "2026-08-04"])
    return made


def test_every_date_is_read_from_exactly_one_file_and_a_hole_is_named(tmp_path: Path) -> None:
    """The oracle: no date is readable twice, and a day the watermark passed is never skipped."""
    made = a_tree_with_every_kind_of_file(tmp_path)

    found = ledger.list_ledger_files(tmp_path, WHICH)

    for day in days("2026-07-01", "2026-08-06"):
        serving = [source for source in found.sources if source.holds(day)]
        assert len(serving) == 1, f"{day} is served by {len(serving)} files"
    assert found.holes == ("2026-08-03",)
    assert found.source_of("2026-07-31") == ledger.Source(
        covers="2026-07", period=Period.MONTHLY, paths=(made["july"],)
    )
    assert found.source_of("2026-08-03") == ledger.Source(
        covers="2026-08-03", period=None, paths=(made["hole"],)
    )
    served = {path for source in found.sources for path in source.paths}
    assert made["waiting"] not in served, "a re-run waiting in a compacted day was read"
    assert found.source_of("2026-08-07") is None


def test_the_rows_come_back_oldest_first_from_every_kind_of_file(
    tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    """The month, the days, the hole's raw file and the open raw days, each once, in date order."""
    a_tree_with_every_kind_of_file(tmp_path)

    with caplog.at_level(logging.WARNING):
        rows = ledger.load_visual_prunes(tmp_path)

    assert [row.date for row in rows] == [
        "2026-07-05",
        "2026-08-01",
        "2026-08-02",
        "2026-08-03",
        "2026-08-05",
        "2026-08-06",
    ]
    assert 7 not in {row.payload_bytes_before for row in rows}
    assert "state/compact/visual-prunes/index/daily.json" in caplog.text
    assert "2026-08-03" in caplog.text
    assert f"fault={ledger.LedgerFault.DAY_MISSING}" in caplog.text


def test_a_named_file_that_is_not_there_is_named_file_missing_and_the_other_days_still_read(
    tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    """An index naming a file that is gone is a fault, never an empty file read without a word."""
    made = a_tree_with_every_kind_of_file(tmp_path)
    made["first"].unlink()

    with caplog.at_level(logging.WARNING):
        rows = ledger.load_days(
            tmp_path, WHICH, days("2026-08-01", "2026-08-02"), model=VisualPruneRow
        )

    assert [row.date for row in rows] == ["2026-08-02"]
    lines = [record.getMessage() for record in caplog.records]
    assert any(
        f"fault={ledger.LedgerFault.FILE_MISSING}" in line
        and "state/compact/visual-prunes/index/daily.json" in line
        and "covers=2026-08-01" in line
        for line in lines
    ), lines


def test_a_daily_index_alone_is_named_index_missing_and_an_empty_monthly_one_is_not(
    tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    """The compaction writes the two together, so daily.json alone hides whatever months it packed."""
    compacted(tmp_path, Period.DAILY, "2026-08-01", [a_pass("2026-08-01")])
    indexed(tmp_path, Period.DAILY, ["2026-08-01"])

    with caplog.at_level(logging.WARNING):
        ledger.list_ledger_files(tmp_path, WHICH)
    assert f"fault={ledger.LedgerFault.INDEX_MISSING}" in caplog.text
    assert "state/compact/visual-prunes/index/monthly.json" in caplog.text

    indexed(tmp_path, Period.MONTHLY, [])
    caplog.clear()
    with caplog.at_level(logging.WARNING):
        found = ledger.list_ledger_files(tmp_path, WHICH)
    assert caplog.text == ""
    assert [source.covers for source in found.sources] == ["2026-08-01"]


def test_a_day_both_indexes_name_is_read_once_from_its_month(
    tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    """A pass that stopped between writing a month and deleting its days counts nothing twice."""
    compacted(tmp_path, Period.MONTHLY, "2026-07", [a_pass("2026-07-05")])
    compacted(tmp_path, Period.DAILY, "2026-07-05", [a_pass("2026-07-05")])
    indexed(tmp_path, Period.MONTHLY, ["2026-07"])
    indexed(tmp_path, Period.DAILY, ["2026-07-05"])

    with caplog.at_level(logging.WARNING):
        rows = ledger.load_visual_prunes(tmp_path)

    assert [row.date for row in rows] == ["2026-07-05"]
    assert "read from its month" in caplog.text


def test_a_ledger_nothing_has_compacted_reads_as_its_raw_files_did(tmp_path: Path) -> None:
    """Before a compaction runs live, the reader answers what the raw reader answered."""
    filed(tmp_path, a_pass("2026-09-06", before=100), attempt=1)
    filed(tmp_path, a_pass("2026-09-06", before=200), attempt=2)
    filed(tmp_path, a_pass("2026-09-07"))

    assert ledger.load_visual_prunes(tmp_path) == ledger.load_current_rows(
        tmp_path, WHICH, model=VisualPruneRow, key=ledger.VISUAL_PRUNE_KEY
    )
    assert [row.payload_bytes_before for row in ledger.load_visual_prunes(tmp_path)] == [200, 1000]


def test_a_file_that_cannot_be_read_is_skipped_by_its_path_and_so_is_an_index(
    tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    """A skipped file costs its own rows; an unreadable index is read as absent, and named."""
    broken = compacted(tmp_path, Period.DAILY, "2026-08-01", [a_pass("2026-08-01")])
    indexed(tmp_path, Period.DAILY, ["2026-08-01"])
    filed(tmp_path, a_pass("2026-08-02"))
    broken.write_bytes(b"PAR1 not a parquet file")

    with caplog.at_level(logging.WARNING):
        assert [row.date for row in ledger.load_visual_prunes(tmp_path)] == ["2026-08-02"]
    assert "state/compact/visual-prunes/daily/2026/08/01.parquet" in caplog.text

    monthly = indexed(tmp_path, Period.MONTHLY, ["2026-07"])
    monthly.write_bytes(b"{ not json")
    caplog.clear()
    with caplog.at_level(logging.WARNING):
        ledger.list_ledger_files(tmp_path, WHICH)
    assert "state/compact/visual-prunes/index/monthly.json" in caplog.text


def test_a_read_asking_for_another_ledgers_rows_is_refused_naming_both() -> None:
    with pytest.raises(ValueError, match="rows are VisualPruneRow") as refused:
        ledger.load_ledger_rows(Path("state"), WHICH, model=FeedRetirementRow)
    assert "FeedRetirementRow" in str(refused.value)


def test_every_ledger_the_registry_files_under_the_two_roots_has_a_key_and_a_reader() -> None:
    """A ledger that joins the two roots with no row in the door table could not be compacted."""
    door = {member for member in LedgerName if ledger.entry(member).grain is Grain.RAW_AND_COMPACT}

    assert door, "the registry files no ledger under the two roots, so nothing is checked"
    for member in door:
        assert ledger.door_key(member), member
        assert ledger.door_contract(member).__schema_stem__, member
    with pytest.raises(ValueError, match="has no key and no row contract"):
        ledger.door_key(LedgerName.SEEN)

"""Does the one-shot migration move every row today's CSV reader returns, and nothing else?

Each case builds a small CSV day tree under `tmp_path` the way the retired
writers filed one - one file per writer, `<run_id>-<attempt>-<job>-<shard>.csv` -
and runs the migration over it. Nothing here reads the committed `state/`
(CLAUDE.md section 13): the parity run over the committed tree is an operator's
one-off, and its figures are in the pull request that carried the move.
"""

from __future__ import annotations

from datetime import date
from pathlib import Path
from typing import Final

import pytest
from conftest import CONTRACT_FIXTURES_DIR

from idhazh import ledger
from idhazh.contracts.base import ServerJob
from idhazh.contracts.file_envelope import Period
from idhazh.contracts.host_fingerprint import HostFingerprintRow
from idhazh.contracts.item_health import ItemHealthRow
from idhazh.contracts.ledger_name import LedgerName
from idhazh.ledger import render_file
from utilities import migrate_to_parquet as migration

pytestmark = pytest.mark.contract

#: A day old enough to pack, and the day after it, which the rule does not admit yet.
OLD: Final = "2026-09-02"
NEW: Final = "2026-09-03"
#: The wake the migration runs on: a day is packed once a whole day has passed after it.
TODAY: Final = date(2026, 9, 4)
RUN: Final = "2026-09-29-9001"
SHA: Final = "0" * 40


def _item(day: str, item: str, *, machine: bool, words: int = 120) -> ItemHealthRow:
    """One item-health row, from the committed fixture, filed for `day`."""
    base = ItemHealthRow.model_validate_json(
        (CONTRACT_FIXTURES_DIR / "item-health-row" / "published.json").read_text(encoding="utf-8")
    )
    return ItemHealthRow.model_validate(
        {
            **base.model_dump(),
            "date": day,
            "run_id": f"{day}-100",
            "item_id": item,
            "source_words": words,
            "machine_job": ServerJob.WORK if machine else None,
            "machine_shard": 0 if machine else None,
        }
    )


def _host(name: str, day: str) -> HostFingerprintRow:
    """One half of a job's host row, from the committed fixture, filed for `day`."""
    base = HostFingerprintRow.model_validate_json(
        (CONTRACT_FIXTURES_DIR / "host-fingerprint-row" / name).read_text(encoding="utf-8")
    )
    return HostFingerprintRow.model_validate(
        {**base.model_dump(), "date": day, "run_id": f"{day}-100", "shard": 0}
    )


def _csv(state: Path, which: LedgerName, day: str, writer: str, rows: list[dict[str, str]]) -> Path:
    """One writer's CSV file of one day, in the layout the retired writers used."""
    folder = state / which.value / day[:4] / day[5:7] / day[8:10]
    folder.mkdir(parents=True, exist_ok=True)
    path = folder / f"{day}-100-{writer}.csv"
    columns = tuple(rows[0])
    path.write_text(render_file(columns, rows), encoding="utf-8", newline="")
    return path


def _run(state: Path, which: LedgerName) -> list[migration.Moved]:
    return migration.migrate(state, [which], run_id=RUN, git_sha=SHA, today=TODAY)


def test_every_day_reads_back_packed_or_raw_and_the_csv_goes(tmp_path: Path) -> None:
    """The old day is packed with its index and watermark, the new one stays raw.

    One item has a work shard's row and assemble's census row; the settled row
    is the one that names the machine, which is the preference the key declares.
    """
    state = tmp_path / "state"
    which = LedgerName.ITEM_HEALTH
    _csv(state, which, OLD, "1-work-00", [_item(OLD, "ai-01", machine=True).csv_row()])
    _csv(
        state,
        which,
        OLD,
        "1-assemble-00",
        [_item(OLD, "ai-01", machine=False).csv_row(), _item(OLD, "ai-02", machine=False).csv_row()],
    )
    _csv(state, which, NEW, "1-assemble-00", [_item(NEW, "ai-03", machine=False).csv_row()])

    (moved,) = _run(state, which)

    assert (moved.rows, moved.filed) == (3, 2)
    assert OLD in moved.packed and NEW not in moved.packed
    old = {row.item_id: row for row in ledger.load_days(state, which, [OLD], model=ItemHealthRow)}
    assert sorted(old) == ["ai-01", "ai-02"]
    assert old["ai-01"].machine_job is ServerJob.WORK, "the row naming its machine wins"
    assert ledger.compact_file(state, which, Period.DAILY, OLD) is not None
    assert ledger.watermark_path(state, which, Period.DAILY).is_file()
    assert [held.envelope.covers for held in ledger.list_raw_files(state, which)] == [NEW]
    assert not migration.left(state, [which])
    assert not (state / which.value).exists()


def test_a_probe_and_its_clock_arrive_as_one_row(tmp_path: Path) -> None:
    """A job's two halves shared one CSV file and one key; the door holds them whole."""
    state = tmp_path / "state"
    which = LedgerName.HOST_FINGERPRINT
    probe = _host("every-reading-taken.json", OLD)
    clock = _host("the-clock-a-job-kept.json", OLD)
    _csv(state, which, OLD, "1-work-00", [probe.csv_row(), clock.csv_row()])

    _run(state, which)

    (row,) = ledger.load_days(state, which, [OLD], model=HostFingerprintRow)
    assert row.cpu_model == probe.cpu_model
    assert row.job_seconds == clock.job_seconds


def test_a_second_run_writes_nothing_and_a_late_file_is_folded_in(tmp_path: Path) -> None:
    state = tmp_path / "state"
    which = LedgerName.ITEM_HEALTH
    _csv(state, which, OLD, "1-work-00", [_item(OLD, "ai-01", machine=True).csv_row()])
    _run(state, which)

    (again,) = _run(state, which)
    assert (again.days, again.filed) == (0, 0)

    _csv(state, which, OLD, "2-work-01", [_item(OLD, "ai-04", machine=True).csv_row()])
    (late,) = _run(state, which)

    assert late.filed == 1
    held = ledger.load_days(state, which, [OLD], model=ItemHealthRow)
    assert sorted(row.item_id for row in held) == ["ai-01", "ai-04"]
    assert not migration.left(state, [which])


def test_the_proof_refuses_a_day_that_does_not_read_back(tmp_path: Path) -> None:
    """The oracle bites: a later write of the migration's own unit changes one cell."""
    state = tmp_path / "state"
    which = LedgerName.ITEM_HEALTH
    rows = [_item(NEW, "ai-03", machine=False, words=120)]
    _csv(state, which, NEW, "1-assemble-00", [row.csv_row() for row in rows])
    _run(state, which)
    migration.prove(state, which, NEW, [row.csv_row() for row in rows])

    ledger.persist(
        state,
        [_item(NEW, "ai-03", machine=False, words=121)],
        ledger=which,
        covers=NEW,
        identity=migration._identity(RUN, SHA),
    )

    with pytest.raises(migration.NotProvenError, match="source_words"):
        migration.prove(state, which, NEW, [row.csv_row() for row in rows])


def test_check_says_whether_a_csv_is_left(tmp_path: Path) -> None:
    state = tmp_path / "state"
    which = LedgerName.ITEM_HEALTH
    _csv(state, which, NEW, "1-assemble-00", [_item(NEW, "ai-03", machine=False).csv_row()])
    argv = ["--state-dir", str(state), "--run-id", RUN, "--git-sha", SHA, "--check"]

    assert migration.main(argv) == migration.EXIT_NOT_PROVEN
    _run(state, which)
    assert migration.main(argv) == migration.EXIT_MIGRATED

"""Does the full chain move every row and delete no CSV of any root until all are proven?"""

from __future__ import annotations

from pathlib import Path
from typing import Final

import pytest
from conftest import SEED_COMMIT

from idhazh import day_shards, ledger
from idhazh.contracts.base import ServerJob
from idhazh.contracts.eval_row import DROPPED_CELLS as DROPPED_EVAL_CELLS
from idhazh.contracts.eval_row import RENAMED_CELLS, EvalRow
from idhazh.contracts.file_envelope import Period
from idhazh.contracts.host_fingerprint import HostFingerprintRow
from idhazh.contracts.ledger_name import LedgerName
from utilities import migrate_to_parquet as command
from utilities.ledger_migration import (
    csv_files,
    csv_layouts,
    phases,
    refusals,
)
from utilities.ledger_migration.identity import writer_identity
from utilities.ledger_migration.inputs import MigrationInputs

from ._fixtures import (
    EVALS,
    FIRST,
    HOST,
    ITEM,
    MONTH_ARGS,
    MONTHS,
    NEW,
    OLD,
    RUN,
    TODAY,
    Cells,
    by_key,
    clock_row,
    file_hashes,
    item_row,
    plan_named_roots,
    probe_row,
    read_back,
    run_migration,
    score_row,
    todays_reader,
    write_csv,
    write_shared_csv,
    writer_file_name,
)

pytestmark = pytest.mark.contract

#: The ledgers these cases build CSV trees for, each filed through the door.
MOVED: Final = (ITEM, EVALS, HOST)


def _under_old_headings(row: EvalRow) -> Cells:
    """An eval row under old names, with unused retired columns left empty."""
    retired = {current: old for old, current in RENAMED_CELLS.items()}
    cells = {retired.get(name, name): value for name, value in row.csv_row().items()}
    return cells | dict.fromkeys(sorted(DROPPED_EVAL_CELLS), "")


def test_every_row_todays_reader_returns_reads_back_and_every_csv_goes(tmp_path: Path) -> None:
    """All three ledgers, over every kind of file a CSV day held.

    A closed day's `settled.csv`, a committed head's `before-partition.csv`,
    writer files, a re-run's second attempt, a file under the eval ledger's old
    headings, and a closed day that held nothing. The door serves each day
    exactly as today's reader read it: no row lost, none invented, every cell
    equal. The old day is packed, with the first of its month before it as an
    empty day, and the new day stays a raw file.
    """
    state = tmp_path / "state"
    census = [item_row(OLD, "ai-01", machine=False), item_row(OLD, "ai-02", machine=False)]
    write_csv(state, ITEM, OLD, day_shards.SETTLED_NAME, [row.csv_row() for row in census])
    write_csv(
        state,
        ITEM,
        OLD,
        writer_file_name(OLD, 1, ServerJob.WORK),
        [item_row(OLD, "ai-01", machine=True).csv_row()],
    )
    write_csv(
        state,
        ITEM,
        NEW,
        ledger.BEFORE_PARTITION_NAME,
        [item_row(NEW, "ai-03", machine=True).csv_row()],
    )
    assembled = [item_row(NEW, "ai-03", machine=False), item_row(NEW, "ai-04", machine=False)]
    write_csv(
        state, ITEM, NEW, writer_file_name(NEW, 1, ServerJob.ASSEMBLE), [row.csv_row() for row in assembled]
    )
    write_csv(state, EVALS, OLD, day_shards.SETTLED_NAME, [score_row(OLD, 1).csv_row()])
    write_csv(
        state, EVALS, OLD, writer_file_name(OLD, 1, ServerJob.WORK), [score_row(OLD, 2, score_ms=100).csv_row()]
    )
    write_csv(
        state, EVALS, OLD, writer_file_name(OLD, 2, ServerJob.WORK), [score_row(OLD, 2, score_ms=200).csv_row()]
    )
    write_csv(state, EVALS, NEW, writer_file_name(NEW, 1, ServerJob.WORK), [_under_old_headings(score_row(NEW, 3))])
    write_csv(state, HOST, FIRST, day_shards.SETTLED_NAME, [], columns=HostFingerprintRow.csv_columns())
    halves = [probe_row(OLD).csv_row(), clock_row(OLD).csv_row()]
    write_csv(state, HOST, OLD, writer_file_name(OLD, 1, ServerJob.WORK), halves)
    halves = [probe_row(NEW, ServerJob.PLAN).csv_row(), clock_row(NEW, ServerJob.PLAN).csv_row()]
    write_csv(state, HOST, NEW, writer_file_name(NEW, 1, ServerJob.PLAN), halves)
    wanted = {which: todays_reader(state, which) for which in MOVED}
    lines = {
        which: sum(
            1
            for path in csv_files.left(state, [which], months=MONTHS)
            for _ in day_shards.rows_of(path)
        )
        for which in MOVED
    }

    moved = {each.which: each for each in run_migration(state, *MOVED)}

    for which, days in wanted.items():
        assert moved[which].rows == sum(len(rows) for rows in days.values())
        for day, rows in days.items():
            assert read_back(state, which, day) == rows, f"{which.value} {day}"
        assert moved[which].packed == [FIRST, OLD]
        assert ledger.raw_days(state, which) == [NEW]
        assert not csv_layouts.csv_root(state, which).exists(), (
            "every CSV file and emptied folder goes"
        )
    assert not csv_files.left(state, list(MOVED), months=MONTHS)
    item_key = (OLD, f"{OLD}-100", "ai-01")
    assert read_back(state, ITEM, OLD)[item_key]["machine_job"] == ServerJob.WORK.value
    assert {cells["score_ms"] for cells in read_back(state, EVALS, OLD).values()} == {"0", "200"}
    assert (lines[EVALS], moved[EVALS].rows) == (4, 3), "a re-run's first attempt is no row"
    assert list(read_back(state, EVALS, NEW).values()) == [score_row(NEW, 3).csv_row()]
    assert [len(wanted[HOST][day]) for day in (FIRST, OLD, NEW)] == [0, 1, 1]


def test_a_second_run_changes_no_byte(tmp_path: Path) -> None:
    """At the same wake, every period admitted by the compaction is already packed."""
    state = tmp_path / "state"
    write_csv(
        state,
        ITEM,
        NEW,
        writer_file_name(NEW, 1, ServerJob.ASSEMBLE),
        [item_row(NEW, "ai-03", machine=False).csv_row()],
    )
    write_csv(state, EVALS, NEW, writer_file_name(NEW, 1, ServerJob.WORK), [score_row(NEW, 1).csv_row()])
    write_csv(
        state,
        HOST,
        NEW,
        writer_file_name(NEW, 1, ServerJob.WORK),
        [probe_row(NEW).csv_row(), clock_row(NEW).csv_row()],
    )
    run_migration(state, *MOVED)
    before = file_hashes(tmp_path)
    waiting = [ledger.raw_days(state, which) for which in MOVED]

    again = run_migration(state, *MOVED)
    argv = ["--state-dir", str(state), "--run-id", RUN, "--git-sha", SEED_COMMIT]

    assert [(each.days, each.filed, each.packed) for each in again] == [(0, 0, [])] * 3
    assert command.main([*MONTH_ARGS, *argv]) == command.EXIT_MIGRATED
    assert file_hashes(tmp_path) == before
    assert waiting == [[NEW]] * 3, "the day the second run could have packed is still raw"


def test_repeated_roots_prove_every_day_before_deleting_any_csv(tmp_path: Path) -> None:
    state = tmp_path / "state"
    trials = [
        state / "pipeline-tests",
        state / "pipeline-tests-no-visual-plan",
        state / "pipeline-tests-production-settings",
    ]
    write_csv(
        trials[0],
        ITEM,
        OLD,
        writer_file_name(OLD, 1, ServerJob.WORK),
        [item_row(OLD, "ai-01", machine=True).csv_row()],
    )
    write_csv(
        trials[1],
        ITEM,
        OLD,
        writer_file_name(OLD, 1, ServerJob.WORK),
        [item_row(OLD, "ai-02", machine=True).csv_row()],
    )
    probe = probe_row(NEW)
    source = write_csv(trials[2], HOST, NEW, writer_file_name(NEW, 1, ServerJob.WORK), [probe.csv_row()])
    later = writer_identity(RUN, SEED_COMMIT).model_copy(update={"attempt": 2})
    ledger.persist(
        trials[2],
        [probe.model_copy(update={"cores": 64})],
        ledger=HOST,
        covers=NEW,
        identity=later,
    )
    csv_before = {
        path: path.read_bytes()
        for trial in trials
        for which in (ITEM, HOST)
        for path in csv_files.left(trial, [which], months=MONTHS)
    }

    with pytest.raises(refusals.NotProvenError, match="cores='64'"):
        phases.migrate_roots(
            MigrationInputs(
                state_dirs=trials,
                which=[ITEM, HOST],
                run_id=RUN,
                git_sha=SEED_COMMIT,
                today=TODAY,
                months=MONTHS,
            )
        )

    assert {
        path: path.read_bytes()
        for trial in trials
        for which in (ITEM, HOST)
        for path in csv_files.left(trial, [which], months=MONTHS)
    } == csv_before
    assert source.exists()
    assert not ledger.compact_index_path(trials[0], ITEM, Period.DAILY).exists()
    assert not ledger.compact_index_path(trials[1], ITEM, Period.DAILY).exists()
    assert not ledger.compact_index_path(trials[2], HOST, Period.DAILY).exists()


def test_full_chain_refuses_a_preferred_source_conflict_before_deleting_any_root(
    tmp_path: Path,
) -> None:
    roots = [tmp_path / "trial-a", tmp_path / "trial-b"]
    row = item_row(OLD, "ai-01", machine=False)
    sources = [
        write_csv(root, ITEM, OLD, writer_file_name(OLD, 1, ServerJob.ASSEMBLE), [row.csv_row()])
        for root in roots
    ]
    assert row.source_words is not None
    ledger.persist(
        roots[-1],
        [item_row(OLD, "ai-01", machine=True, words=row.source_words + 1)],
        ledger=ITEM,
        covers=OLD,
        identity=writer_identity(RUN, SEED_COMMIT).model_copy(update={"attempt": 2}),
    )
    assert not plan_named_roots(roots, ITEM)[-1].planned[ITEM][OLD].changed
    before = {path: path.read_bytes() for path in sources}
    with pytest.raises(refusals.NotProvenError, match=r"ai-01.*CSV supplies"):
        phases.migrate_roots(
            MigrationInputs(
                state_dirs=roots,
                which=[ITEM],
                run_id=RUN,
                git_sha=SEED_COMMIT,
                today=TODAY,
                months=MONTHS,
            )
        )
    assert {path: path.read_bytes() for path in sources} == before
    assert read_back(roots[0], ITEM, OLD) == by_key(ITEM, [row.csv_row()])


def test_legacy_full_chain_still_retires_an_empty_trial_csv_day(tmp_path: Path) -> None:
    root = tmp_path / "trial"
    source = write_shared_csv(root, LedgerName.SEEN, OLD, [])
    args = [
        *MONTH_ARGS,
        "--state-dir",
        str(root),
        "--ledger",
        LedgerName.SEEN.value,
        "--run-id",
        RUN,
        "--git-sha",
        SEED_COMMIT,
    ]
    assert command.main([*args, "--write"]) == 0
    assert source.exists()
    assert command.main([*args, "--verify"]) == 0
    assert command.main([*args, "--retire"]) == 0
    assert not source.exists()
    write_shared_csv(root, LedgerName.SEEN, OLD, [])
    assert command.main(args) == 0
    assert not source.exists()


def test_a_day_that_does_not_read_back_leaves_every_csv_of_every_ledger_in_place(
    tmp_path: Path,
) -> None:
    """The bite: the door serves one cell other than the one the migration filed.

    A file already on disk as a later attempt at the migration's own work unit
    holds `cores` differently, and a reader keeps a unit's highest attempt, so
    the host day reads that cell back. Item-health came across whole before it,
    and its CSV stays too: no CSV of any ledger goes until every day is proven.
    """
    state = tmp_path / "state"
    write_csv(
        state,
        ITEM,
        OLD,
        writer_file_name(OLD, 1, ServerJob.WORK),
        [item_row(OLD, "ai-01", machine=True).csv_row()],
    )
    probe = probe_row(OLD)
    write_csv(state, HOST, OLD, writer_file_name(OLD, 1, ServerJob.WORK), [probe.csv_row()])
    later = writer_identity(RUN, SEED_COMMIT).model_copy(update={"attempt": 2})
    ledger.persist(
        state, [probe.model_copy(update={"cores": 64})], ledger=HOST, covers=OLD, identity=later
    )
    kept = {path: path.read_bytes() for path in csv_files.left(state, list(MOVED), months=MONTHS)}

    with pytest.raises(refusals.NotProvenError, match=rf"host-fingerprint {OLD} .*cores='64'"):
        run_migration(state, *MOVED)

    assert {
        path: path.read_bytes() for path in csv_files.left(state, list(MOVED), months=MONTHS)
    } == kept
    assert len(kept) == 2

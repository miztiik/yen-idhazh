"""Does a plan say what the door will hold for each day before anything is written?"""

from __future__ import annotations

from dataclasses import FrozenInstanceError
from datetime import date
from pathlib import Path

import pytest
from conftest import SEED_COMMIT

from idhazh import ledger
from idhazh.contracts.base import ServerJob
from idhazh.contracts.host_fingerprint import HostFingerprintRow
from utilities.ledger_migration import (
    phases,
    planning,
)
from utilities.ledger_migration.identity import writer_identity
from utilities.ledger_migration.inputs import MigrationInputs

from ._fixtures import (
    HOST,
    ITEM,
    MONTHS,
    OLD,
    RUN,
    TODAY,
    by_key,
    clock_row,
    file_hashes,
    filled_cells,
    plan_named_roots,
    probe_row,
    read_back,
    run_migration,
    write_csv,
    writer_file_name,
)

pytestmark = pytest.mark.contract


def test_newer_host_stamp_does_not_require_rewriting_an_unchanged_row(tmp_path: Path) -> None:
    root = tmp_path / "trial"
    row = probe_row(OLD).model_copy(update={"version": "2026-09-20"})
    ledger.persist(
        root, [row], ledger=HOST, covers=OLD, identity=writer_identity(RUN, SEED_COMMIT)
    )
    source = write_csv(
        root, HOST, OLD, writer_file_name(OLD, 1, ServerJob.WORK),
        [row.csv_row() | {"version": "2026-09-19"}],
    )
    (plan,) = plan_named_roots([root], HOST)
    assert not plan.planned[HOST][OLD].changed
    before = file_hashes(tmp_path)
    phases.verify_roots([plan])
    assert file_hashes(tmp_path) == before
    phases.retire_roots(plan.inputs)
    assert not source.exists()
    assert read_back(root, HOST, OLD) == by_key(HOST, [row.csv_row()])


def test_migration_inputs_are_frozen_and_do_not_share_mutable_selections(tmp_path: Path) -> None:
    roots, names, months = [tmp_path], [ITEM], list(MONTHS)
    inputs = MigrationInputs(
        state_dirs=roots,
        which=names,
        run_id=RUN,
        git_sha=SEED_COMMIT,
        today=TODAY,
        months=months,
    )
    roots.clear()
    names.clear()
    months.clear()
    assert inputs.state_dirs == (tmp_path.resolve(),)
    assert inputs.which == (ITEM,)
    assert inputs.months == MONTHS
    with pytest.raises(FrozenInstanceError):
        inputs.today = date(2026, 9, 5)  # type: ignore[misc]
    (plan,) = planning.plan_roots(inputs)
    assert plan.inputs is inputs


@pytest.mark.parametrize("files", [1, 2], ids=["in one file", "in two files"])
def test_a_probe_and_its_clock_arrive_as_one_row(tmp_path: Path, files: int) -> None:
    """A job's two halves share one key, in one file or two, and the door holds one row of both.

    The probe writes the machine as the job starts and the clock writes the
    job's time at its end, into the job's own file. A re-run that reached only
    the clock left its half in a file of its own.
    """
    state = tmp_path / "state"
    probe, clock = probe_row(OLD), clock_row(OLD)
    if files == 1:
        write_csv(state, HOST, OLD, writer_file_name(OLD, 1, ServerJob.WORK), [probe.csv_row(), clock.csv_row()])
    else:
        write_csv(state, HOST, OLD, writer_file_name(OLD, 1, ServerJob.WORK), [probe.csv_row()])
        write_csv(state, HOST, OLD, writer_file_name(OLD, 2, ServerJob.WORK), [clock.csv_row()])

    (moved,) = run_migration(state, HOST)

    (row,) = ledger.load_days(state, HOST, [OLD], model=HostFingerprintRow)
    both = filled_cells(probe) | filled_cells(clock)
    assert filled_cells(probe).keys() & filled_cells(clock).keys() == set(ledger.HOST_FINGERPRINT_KEY)
    assert {name: row.csv_row()[name] for name in both} == both
    assert moved.rows == 1

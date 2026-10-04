"""Does the table of old CSV layouts agree with the registry and the declarations?

The table is held against the committed `config/ledgers.json` and compaction
declarations, which these cases read rather than build, so a pull request that
changes either is checked against it. A ledger the table does not declare is
refused by name.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from gardener.tasks._task import declared as task_declarations

from idhazh import config, ledger
from idhazh.contracts.base import ServerJob
from idhazh.contracts.knobs.gardener import CompactionPolicy
from idhazh.contracts.ledger_name import LedgerName
from utilities.ledger_migration import (
    csv_layouts,
    refusals,
)

from ._fixtures import (
    EVALS,
    NEW,
    file_hashes,
    plan_named_roots,
    read_back,
    run_migration,
    score_row,
    write_csv,
    writer_file_name,
)

pytestmark = pytest.mark.contract


def test_the_eval_ledgers_csv_tree_is_read_where_its_old_name_filed_it(tmp_path: Path) -> None:
    """A re-run of a commit from before the rename writes its CSV day under `scores/`.

    That tree is the one this moves for the eval ledger, whatever the ledger is
    called now, so a late CSV file still reaches the door under the new name.
    """
    state = tmp_path / "state"
    assert csv_layouts.csv_root(state, EVALS) == state / "scores"
    write_csv(state, EVALS, NEW, writer_file_name(NEW, 1, ServerJob.WORK), [score_row(NEW, 1).csv_row()])

    (moved,) = run_migration(state, EVALS)

    assert (moved.days, moved.rows) == (1, 1)
    assert list(read_back(state, EVALS, NEW).values()) == [score_row(NEW, 1).csv_row()]
    assert not (state / "scores").exists()


def test_every_unmoved_table_entry_is_the_registry_entry() -> None:
    """A ledger still on CSV sits where the registry files it, so its move changes neither.

    Read off the committed `config/ledgers.json`: a change that files a ledger's
    CSV somewhere else, and leaves its table entry behind, fails here.
    """
    door = set(csv_layouts.door_ledgers())
    unmoved = [name for name in csv_layouts.CSV_LEDGERS if name not in door]

    assert {name: csv_layouts.CSV_LEDGERS[name].old_entry for name in unmoved} == {
        name: ledger.entry(name) for name in unmoved
    }


def test_every_moved_ledger_keeps_its_old_window() -> None:
    """A moved ledger's committed compaction keeps every day a task kept of its CSV.

    Read off the committed declarations, so a change that shortens one fails
    here rather than at the first live pass that deletes those days.
    """
    tasks = task_declarations()
    moved = csv_layouts.door_ledgers()
    short: list[str] = []
    for name in moved:
        policy = tasks[f"compact-{name.value}"]
        assert isinstance(policy, CompactionPolicy), name
        if not config.compaction_reaches(policy, csv_layouts.CSV_LEDGERS[name].old_window):
            short.append(name.value)

    assert moved, "no ledger in the table has moved, so nothing is checked"
    assert short == []


def test_a_ledger_with_no_declared_csv_layout_is_refused_by_name(tmp_path: Path) -> None:
    which = LedgerName.VISUAL_PRUNES
    assert which not in csv_layouts.CSV_LEDGERS
    before = file_hashes(tmp_path)
    with pytest.raises(refusals.RefusedError, match=rf"{which.value}: no supported CSV layout"):
        plan_named_roots([tmp_path], which)
    with pytest.raises(refusals.RefusedError, match=which.value):
        csv_layouts.csv_root(tmp_path, which)
    assert file_hashes(tmp_path) == before

"""Does the table of old CSV layouts agree with the registry and the declarations?

The table is held against the committed registry and recorded pre-expiry
compaction declarations. A ledger the table does not declare is refused by name.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from gardener._historical_config import PRE_YEARLY_CONFIG

from idhazh import config, ledger
from idhazh.contracts.base import ServerJob
from idhazh.contracts.council_run_record import CouncilRunRecord, EvaluationStep
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
    write_shared_csv,
    writer_file_name,
)

pytestmark = pytest.mark.contract


def _a_council_old_row(**changes: str) -> dict[str, str]:
    """One old council row, in the headings the migrator reads before row 3."""
    return {
        "version": "2026-09-21T12:00",
        "date": NEW,
        "run_id": f"{NEW}-100",
        "judge_id": "paper-tenant",
        "shard": "-1",
        "shards": "2",
        "outcome": "completed",
        "started_at": f"{NEW}T00:00:00Z",
        "seconds_spent": "0.5",
        "model_calls": "",
        "tokens_in": "",
        "tokens_out": "",
        "model_seconds": "",
        "host_model": "",
    } | changes


def test_the_councils_shared_day_file_is_read_under_its_two_old_folders(
    tmp_path: Path,
) -> None:
    state = tmp_path / "state"
    old = LedgerName.COUNCIL_RUN_RECORDS
    assert csv_layouts.csv_root(state, old) == state / "llm-council" / "shard-outcomes"
    write_shared_csv(state, old, NEW, [_a_council_old_row()])

    (moved,) = run_migration(state, old)
    rows = ledger.load_days(state, old, [NEW], model=CouncilRunRecord)

    assert (moved.days, moved.rows) == (1, 1)
    assert len(rows) == 1
    assert rows[0].evaluation_step is EvaluationStep.SELECT_JUDGE_WORK
    assert rows[0].work_part_index is None
    assert rows[0].work_part_count == 2
    source = csv_layouts.csv_root(state, old) / NEW[:4] / NEW[5:7] / f"{NEW[8:10]}.csv"
    assert not source.exists(), "the migrated source day file is retired"


def test_a_filled_council_host_model_cell_stops_migration_by_name(tmp_path: Path) -> None:
    state = tmp_path / "state"
    old = LedgerName.COUNCIL_RUN_RECORDS
    write_shared_csv(state, old, NEW, [_a_council_old_row(host_model="machine-a")])

    with pytest.raises(refusals.NotProvenError, match="host_model"):
        plan_named_roots([state], old)

    assert (state / "llm-council").exists(), "refusal leaves the only copy untouched"


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


def test_every_moved_ledger_kept_its_old_window_before_yearly_expiry() -> None:
    """Recorded migration declarations preserve the windows held by the old CSV readers."""
    tasks = config.load_gardener(PRE_YEARLY_CONFIG).tasks
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

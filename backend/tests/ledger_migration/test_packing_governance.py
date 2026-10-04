"""Which compaction packs a migrated root, and which ledger or root is refused or filed raw?

A ledger the registry still files as CSV, one with no compaction, and one whose
compaction keeps less than its CSV was kept are refused before a file is
written; a root other than the state tree beside `config/` is filed raw and
never packed.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest
from conftest import CONFIG_DIR, REPO_ROOT, SEED_COMMIT

from idhazh import ledger
from idhazh.contracts.base import ServerJob
from idhazh.contracts.file_envelope import Period
from idhazh.contracts.ledgers import Grain
from utilities.ledger_migration import (
    csv_files,
    packing,
    phases,
    refusals,
)
from utilities.ledger_migration.inputs import MigrationInputs

from ._fixtures import (
    EVALS,
    ITEM,
    MONTHS,
    NEW,
    OLD,
    ON_CSV,
    RUN,
    TODAY,
    config_beside,
    entry_back_on_csv,
    feed_row,
    file_hashes,
    item_row,
    read_back,
    score_row,
    todays_reader,
    write_csv,
    writer_file_name,
)

pytestmark = pytest.mark.contract


def test_a_ledger_still_on_csv_is_refused(tmp_path: Path) -> None:
    """A run naming a ledger the registry still files as CSV is refused and writes nothing.

    Its writers still write CSV, so a door copy of its rows is one no reader
    opens. A door ledger named beside it does not move either: the whole run is
    refused before its first file is read. The registry beside this tree files
    one ledger the way it was filed before it moved, without its compaction.
    """
    state = tmp_path / "state"
    write_csv(state, ON_CSV, OLD, writer_file_name(OLD, 1, ServerJob.PLAN), [feed_row(OLD).csv_row()])
    write_csv(
        state,
        ITEM,
        OLD,
        writer_file_name(OLD, 1, ServerJob.WORK),
        [item_row(OLD, "ai-01", machine=True).csv_row()],
    )
    config_dir = config_beside(state)
    registry_path = config_dir / "ledgers.json"
    registry = json.loads(registry_path.read_text(encoding="utf-8"))
    for family in registry["families"]:
        family["ledgers"] = [
            entry_back_on_csv(ON_CSV) if held["name"] == ON_CSV.value else held
            for held in family["ledgers"]
        ]
    registry_path.write_text(json.dumps(registry), encoding="ascii")
    (config_dir / "gardener" / f"compact-{ON_CSV.value}.json").unlink()
    knobs_path = config_dir / "idhazh_gardener.json"
    knobs = json.loads(knobs_path.read_text(encoding="ascii"))
    knobs["task_names"].remove(f"compact-{ON_CSV.value}")
    knobs_path.write_text(json.dumps(knobs), encoding="ascii", newline="\n")
    before = file_hashes(tmp_path)

    with pytest.raises(
        refusals.RefusedError,
        match=f"config/ledgers.json files {ON_CSV.value} as {Grain.DAY_TREE.value},",
    ):
        phases.migrate_roots(
            MigrationInputs(
                state_dirs=[state],
                which=[ITEM, ON_CSV],
                run_id=RUN,
                git_sha=SEED_COMMIT,
                today=TODAY,
                config_dir=config_dir,
                months=MONTHS,
            )
        )

    assert file_hashes(tmp_path) == before


@pytest.mark.parametrize(
    ("change", "refusal"),
    [
        (None, "task_names does not list compact-summary-quality-evals"),
        (
            {"monthly_window": {"unit": "months", "value": 13}, "monthly_keep_days": None},
            "does not reach the window of forever that kept summary-quality-evals on CSV",
        ),
    ],
    ids=["no-compaction", "short-of-the-csv"],
)
def test_a_door_ledger_whose_compaction_cannot_hold_its_csv_is_refused(
    tmp_path: Path, change: dict[str, Any] | None, refusal: str
) -> None:
    """Refused before a file is read: nothing says which days to pack, or a pass deletes them.

    No task ever deleted an eval row, so a compaction keeping thirteen months
    would delete, at its first live pass, days its CSV still held.
    """
    state = tmp_path / "state"
    write_csv(state, EVALS, NEW, writer_file_name(NEW, 1, ServerJob.WORK), [score_row(NEW, 1).csv_row()])
    config_dir = config_beside(state)
    declaration = config_dir / "gardener" / f"compact-{EVALS.value}.json"
    if change is None:
        declaration.unlink()
        knobs_path = config_dir / "idhazh_gardener.json"
        knobs = json.loads(knobs_path.read_text(encoding="ascii"))
        knobs["task_names"].remove(declaration.stem)
        knobs_path.write_text(json.dumps(knobs), encoding="ascii", newline="\n")
    else:
        declared = json.loads(declaration.read_text(encoding="utf-8"))
        declaration.write_text(json.dumps(declared | change), encoding="ascii")
    before = file_hashes(tmp_path)

    with pytest.raises(refusals.RefusedError, match=refusal):
        phases.migrate_roots(
            MigrationInputs(
                state_dirs=[state],
                which=[EVALS],
                run_id=RUN,
                git_sha=SEED_COMMIT,
                today=TODAY,
                config_dir=config_dir,
                months=MONTHS,
            )
        )

    assert file_hashes(tmp_path) == before


def test_a_root_beside_no_config_is_filed_raw_and_never_packed(tmp_path: Path) -> None:
    """Only the state tree beside `config/` is packed; a trial run's tree inside it is filed raw.

    Nothing reads a packed trial root, and the trials task empties it, so its
    day files and indexes would be files nobody opens. Its days are still read
    back cell for cell before its CSV goes.
    """
    state = tmp_path / "state"
    trial = state / "pipeline-tests"
    write_csv(
        trial,
        ITEM,
        OLD,
        writer_file_name(OLD, 1, ServerJob.WORK),
        [item_row(OLD, "ai-01", machine=True).csv_row()],
    )
    wanted = todays_reader(trial, ITEM)

    ((_, moved),) = phases.migrate_roots(
        MigrationInputs(
            state_dirs=[trial],
            which=[ITEM],
            run_id=RUN,
            git_sha=SEED_COMMIT,
            today=TODAY,
            config_dir=config_beside(state),
            months=MONTHS,
        )
    )

    assert (moved.days, moved.filed, moved.packed) == (1, 1, [])
    assert ledger.raw_days(trial, ITEM) == [OLD], "a day the rule admits stays raw here"
    assert not ledger.compact_index_path(trial, ITEM, Period.DAILY).exists()
    assert read_back(trial, ITEM, OLD) == wanted[OLD]
    assert not csv_files.left(trial, [ITEM], months=MONTHS)
    assert packing.packs_here(REPO_ROOT / ledger.STATE_DIRNAME, CONFIG_DIR)
    assert not packing.packs_here(REPO_ROOT / ledger.STATE_DIRNAME / "pipeline-tests", CONFIG_DIR)

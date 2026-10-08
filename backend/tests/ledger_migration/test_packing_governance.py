"""Which compaction packs a migrated root, and which ledger or root is refused or filed raw?

A ledger the registry still files as CSV, one with no compaction, and one whose
compaction keeps less than its CSV was kept, with no named decision allowing
it, are refused before a file is written; an undeclared non-production root is
filed raw, while a declared trial root uses its own compaction policy.
"""

from __future__ import annotations

import json
from pathlib import Path
from types import MappingProxyType
from typing import Any

import pytest
from conftest import CONFIG_DIR, REPO_ROOT, SEED_COMMIT
from gardener._garden import a_config

from idhazh import config, ledger
from idhazh.contracts.base import ServerJob
from idhazh.contracts.file_envelope import Period
from idhazh.contracts.ledgers import Grain
from utilities.ledger_migration import (
    csv_files,
    csv_layouts,
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
    compaction_identity,
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
    write_csv(
        state, ON_CSV, OLD, writer_file_name(OLD, 1, ServerJob.PLAN), [feed_row(OLD).csv_row()]
    )
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
    write_csv(
        state, EVALS, NEW, writer_file_name(NEW, 1, ServerJob.WORK), [score_row(NEW, 1).csv_row()]
    )
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


def test_the_migration_packs_live_and_only_reports_month_deletes_whatever_the_declaration_says(
    tmp_path: Path,
) -> None:
    """A move deletes no month file its window would drop, even under a live declaration.

    The declaration here turns its month deletes live and its packing off, so only
    the migration's own override can give its copy the opposite two values.
    """
    config_dir = config_beside(tmp_path / "state")
    declaration = config_dir / "gardener" / f"compact-{ITEM.value}.json"
    declared = json.loads(declaration.read_text(encoding="utf-8"))
    declaration.write_text(
        json.dumps(declared | {"dry_run": True, "month_deletes_dry_run": False}), encoding="ascii"
    )

    policy = packing.declared([ITEM], config_dir)[ITEM]

    assert (policy.dry_run, policy.month_deletes_dry_run) == (False, True)


def test_a_trial_root_without_this_ledger_policy_is_filed_raw(tmp_path: Path) -> None:
    """An unconfigured item-health trial root is filed raw.

    Other trial compactions name the bench root, but none names this root for
    item-health, so migration must not infer that a policy applies to it.
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
    assert packing.packs_here(REPO_ROOT / ledger.STATE_DIRNAME / "pipeline-tests", CONFIG_DIR)
    assert not packing.packs_here(REPO_ROOT / ledger.STATE_DIRNAME / "pipeline-tests" / "case", CONFIG_DIR)


def test_migration_packs_only_a_trial_root_named_by_its_policy(tmp_path: Path) -> None:
    state = tmp_path / "state"
    trial = state / "pipeline-tests" / "production-settings"
    config_dir = a_config(tmp_path, CONFIG_DIR / "gardener")
    (config_dir / "ledgers.json").write_bytes((CONFIG_DIR / "ledgers.json").read_bytes())
    production = item_row(OLD, "production-row-01", machine=True)
    production_raw = ledger.persist(
        state, [production], ledger=ITEM, covers=OLD, identity=compaction_identity()
    )[0]
    production_bytes = production_raw.read_bytes()
    trial_row = item_row(OLD, "trial-row-01", machine=True)
    write_csv(
        trial,
        ITEM,
        OLD,
        writer_file_name(OLD, 1, ServerJob.WORK),
        [trial_row.csv_row()],
    )

    ((_, moved),) = phases.migrate_roots(
        MigrationInputs(
            state_dirs=[trial],
            which=[ITEM],
            run_id=RUN,
            git_sha=SEED_COMMIT,
            today=TODAY,
            config_dir=config_dir,
            months=MONTHS,
        )
    )

    daily = ledger.compact_file(trial, ITEM, Period.DAILY, OLD)
    assert daily is not None and daily.is_file()
    assert ledger.load_days(trial, ITEM, [OLD], model=type(trial_row)) == [trial_row]
    assert (moved.packed, moved.filed) == ([OLD], 1)
    assert production_raw.read_bytes() == production_bytes
    assert not ledger.compact_index_path(state, ITEM, Period.DAILY).exists()


def test_current_finite_retention_refuses_an_old_forever_csv_reader(tmp_path: Path) -> None:
    """Owner-approved expiry does not silently authorize a lossless CSV migration."""
    config_dir = a_config(tmp_path, CONFIG_DIR / "gardener")
    (config_dir / "ledgers.json").write_bytes((CONFIG_DIR / "ledgers.json").read_bytes())
    with pytest.raises(refusals.RefusedError, match="does not reach the window of forever"):
        packing.declared([EVALS], config_dir)


def test_a_named_decision_lets_the_door_keep_a_ledger_for_less_than_its_csv(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The same shorter compaction is accepted once the entry names who allowed it, and kept.

    The decision does not widen the compaction: the declared yearly expiry is
    what the migration packs under.
    """
    config_dir = a_config(tmp_path, CONFIG_DIR / "gardener")
    (config_dir / "ledgers.json").write_bytes((CONFIG_DIR / "ledgers.json").read_bytes())
    named = csv_layouts.CSV_LEDGERS[EVALS]._replace(shorter_by="a person, on a named day")
    monkeypatch.setattr(
        packing, "CSV_LEDGERS", MappingProxyType(dict(csv_layouts.CSV_LEDGERS) | {EVALS: named})
    )

    declared = packing.declared([EVALS], config_dir)

    assert (declared[EVALS].yearly_prune_enable, declared[EVALS].yearly_keep_months) == (True, 36)


def test_current_migration_initializes_new_indexes_but_refuses_a_lost_one(
    tmp_path: Path,
) -> None:
    """Only existing compact folders establish a tree under the finite expiry policy."""
    state = tmp_path / "state"
    write_csv(
        state,
        ITEM,
        OLD,
        writer_file_name(OLD, 1, ServerJob.WORK),
        [item_row(OLD, "ai-01", machine=True).csv_row()],
    )
    config_dir = a_config(tmp_path, CONFIG_DIR / "gardener")
    (config_dir / "ledgers.json").write_bytes((CONFIG_DIR / "ledgers.json").read_bytes())
    inputs = MigrationInputs(
        state_dirs=[state],
        which=[ITEM],
        run_id=RUN,
        git_sha=SEED_COMMIT,
        today=TODAY,
        config_dir=config_dir,
        months=MONTHS,
    )
    phases.migrate_roots(inputs)
    index = ledger.compact_index_path(state, ITEM, Period.YEARLY)
    assert index.is_file()
    index.unlink()
    policy = packing.declared([ITEM], config_dir)[ITEM]
    with pytest.raises(refusals.NotProvenError, match=r"index/yearly\.json is missing"):
        packing.pack(
            state,
            ITEM,
            compaction_identity(),
            repo_root=config_dir.parent,
            policy=policy,
            today=TODAY,
            months=MONTHS,
            first_ledger_year=config.load_gardener(config_dir).config.first_ledger_year,
        )

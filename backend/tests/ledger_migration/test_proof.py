"""Does every filled CSV cell stand as independent evidence when a day is proven?"""

from __future__ import annotations

from pathlib import Path

import pytest
from conftest import CONFIG_DIR, SEED_COMMIT

from idhazh import ledger
from idhazh.contracts.base import ServerJob
from idhazh.contracts.file_envelope import Period
from idhazh.contracts.item_health import ItemHealthRow
from idhazh.contracts.ledger_index import CompactIndex
from utilities.ledger_migration import (
    phases,
    planning,
    proof,
    refusals,
)
from utilities.ledger_migration.identity import writer_identity
from utilities.ledger_migration.inputs import MigrationInputs

from ._fixtures import (
    HOST,
    ITEM,
    MONTHS,
    NEW,
    OLD,
    RUN,
    TODAY,
    by_key,
    clock_row,
    compaction_identity,
    config_beside,
    file_hashes,
    item_row,
    plan_named_roots,
    probe_row,
    read_back,
    run_migration,
    write_csv,
    writer_file_name,
)

pytestmark = pytest.mark.contract


def test_proof_checks_duplicate_source_keys_and_names_a_missing_source_key(tmp_path: Path) -> None:
    row = item_row(OLD, "ai-01", machine=True)
    ledger.persist(
        tmp_path, [row], ledger=ITEM, covers=OLD, identity=writer_identity(RUN, SEED_COMMIT)
    )
    cells = row.csv_row()
    proof.prove(tmp_path, ITEM, OLD, [cells], source_rows=[cells, cells])
    absent = item_row(OLD, "ai-02", machine=True).csv_row()
    with pytest.raises(refusals.NotProvenError, match="missing CSV source key"):
        proof.prove(tmp_path, ITEM, OLD, [cells], source_rows=[absent, absent])


def test_verify_does_not_use_a_preferred_tampered_source_key_as_its_expectation(
    tmp_path: Path,
) -> None:
    root = tmp_path / "trial"
    row = item_row(OLD, "ai-01", machine=False)
    write_csv(root, ITEM, OLD, writer_file_name(OLD, 1, ServerJob.ASSEMBLE), [row.csv_row()])
    phases.write_roots(plan_named_roots([root], ITEM))
    assert row.source_words is not None
    ledger.persist(
        root,
        [item_row(OLD, "ai-01", machine=True, words=row.source_words + 1)],
        ledger=ITEM,
        covers=OLD,
        identity=writer_identity(RUN, SEED_COMMIT).model_copy(update={"attempt": 2}),
    )
    plans = plan_named_roots([root], ITEM)
    assert not plans[0].planned[ITEM][OLD].changed, "preference hides the changed source cell"
    before = file_hashes(tmp_path)
    with pytest.raises(refusals.NotProvenError, match="CSV supplies"):
        phases.verify_roots(plans)
    assert file_hashes(tmp_path) == before


def test_phase_verification_keeps_retained_keys_and_filled_host_cells(tmp_path: Path) -> None:
    root = tmp_path / "trial"
    write_csv(root, HOST, OLD, writer_file_name(OLD, 1, ServerJob.WORK), [clock_row(OLD).csv_row()])
    ledger.persist(
        root,
        [probe_row(OLD), probe_row(OLD, ServerJob.ASSEMBLE)],
        ledger=HOST,
        covers=OLD,
        identity=writer_identity(RUN, SEED_COMMIT),
    )
    phases.write_roots(plan_named_roots([root], HOST))
    before = file_hashes(tmp_path)
    plans = plan_named_roots([root], HOST)
    assert not plans[0].planned[HOST][OLD].changed
    phases.verify_roots(plans)
    phases.write_roots(plans)
    assert file_hashes(tmp_path) == before
    assert len(read_back(root, HOST, OLD)) == 2


@pytest.mark.parametrize("packed", [False, True], ids=["raw", "compact"])
def test_distinct_source_keys_and_an_unrelated_retained_key_do_not_hide_bad_output(
    tmp_path: Path, packed: bool
) -> None:
    root = tmp_path / ("state" if packed else "trial")
    config_dir = config_beside(root) if packed else CONFIG_DIR
    rows = [item_row(OLD, name, machine=False) for name in ("ai-01", "ai-02")]
    source = write_csv(
        root,
        ITEM,
        OLD,
        writer_file_name(OLD, 1, ServerJob.ASSEMBLE),
        [row.csv_row() for row in rows],
    )
    retained = item_row(OLD, "ai-03", machine=True)
    ledger.persist(
        root,
        [retained],
        ledger=ITEM,
        covers=OLD,
        identity=writer_identity(RUN, SEED_COMMIT),
    )
    inputs = MigrationInputs(
        state_dirs=[root],
        which=[ITEM],
        run_id=RUN,
        git_sha=SEED_COMMIT,
        today=TODAY,
        config_dir=config_dir,
        months=MONTHS,
    )
    phases.write_roots(planning.plan_roots(inputs))
    good = file_hashes(tmp_path)
    phases.verify_roots(planning.plan_roots(inputs))
    assert file_hashes(tmp_path) == good
    assert read_back(root, ITEM, OLD) == by_key(
        ITEM, [row.csv_row() for row in [*rows, retained]]
    )

    assert rows[1].source_words is not None
    bad = item_row(OLD, "ai-02", machine=True, words=rows[1].source_words + 1)
    if packed:
        path = ledger.compact_file(root, ITEM, Period.DAILY, OLD)
        assert path is not None
        stored = ledger.load_stored([path], model=ItemHealthRow)
        replacement = ledger.persist_period(
            root,
            [
                ledger.StoredRow(identity=held.identity, row=bad)
                if held.row.item_id == bad.item_id
                else held
                for held in stored
            ],
            model=ItemHealthRow,
            ledger=ITEM,
            period=Period.DAILY,
            covers=OLD,
            identity=compaction_identity(),
            built_from=1,
        )
        index_path = ledger.compact_index_path(root, ITEM, Period.DAILY)
        index = CompactIndex.read(index_path)
        entries = [
            entry.model_copy(update={"bytes": replacement.stat().st_size})
            if entry.covers == OLD
            else entry
            for entry in index.entries
        ]
        index_path.write_text(
            index.model_copy(update={"entries": entries}).to_json(),
            encoding="ascii",
            newline="\n",
        )
    else:
        ledger.persist(
            root,
            [rows[0], bad, retained],
            ledger=ITEM,
            covers=OLD,
            identity=writer_identity(RUN, SEED_COMMIT).model_copy(update={"attempt": 2}),
        )
    plans = planning.plan_roots(inputs)
    assert not plans[0].planned[ITEM][OLD].changed
    before = file_hashes(tmp_path)
    with pytest.raises(refusals.NotProvenError, match=r"ai-02.*CSV supplies"):
        phases.verify_roots(plans)
    with pytest.raises(refusals.NotProvenError, match=r"ai-02.*CSV supplies"):
        phases.retire_roots(inputs)
    assert file_hashes(tmp_path) == before
    assert source.exists()


def test_the_proof_refuses_a_day_that_does_not_read_back(tmp_path: Path) -> None:
    """The oracle bites: a later write of the migration's own unit changes one cell."""
    state = tmp_path / "state"
    rows = [item_row(NEW, "ai-03", machine=False, words=120)]
    write_csv(state, ITEM, NEW, writer_file_name(NEW, 1, ServerJob.ASSEMBLE), [row.csv_row() for row in rows])
    run_migration(state, ITEM)
    proof.prove(state, ITEM, NEW, [row.csv_row() for row in rows])

    ledger.persist(
        state,
        [item_row(NEW, "ai-03", machine=False, words=121)],
        ledger=ITEM,
        covers=NEW,
        identity=writer_identity(RUN, SEED_COMMIT),
    )

    with pytest.raises(refusals.NotProvenError, match="source_words"):
        proof.prove(state, ITEM, NEW, [row.csv_row() for row in rows])

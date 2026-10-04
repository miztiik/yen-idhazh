"""Do plan, write and verify stay read-only where promised, and does retire prove first?"""

from __future__ import annotations

from pathlib import Path

import pytest
from conftest import SEED_COMMIT

from idhazh import ledger
from idhazh.contracts.base import ServerJob
from utilities.ledger_migration import (
    csv_files,
    phases,
    refusals,
)
from utilities.ledger_migration.identity import writer_identity
from utilities.ledger_migration.inputs import MigrationInputs

from ._fixtures import (
    ITEM,
    MONTHS,
    OLD,
    RUN,
    TODAY,
    by_key,
    file_hashes,
    item_row,
    plan_named_roots,
    read_back,
    write_csv,
    writer_file_name,
)

pytestmark = pytest.mark.contract


def test_separate_phases_are_read_only_until_write_and_keep_csv_until_retire(
    tmp_path: Path,
) -> None:
    root = tmp_path / "trial"
    row = item_row(OLD, "ai-01", machine=True)
    csv = write_csv(root, ITEM, OLD, writer_file_name(OLD, 1, ServerJob.WORK), [row.csv_row()])
    csv_bytes = csv.read_bytes()
    before = file_hashes(tmp_path)

    plans = plan_named_roots([root], ITEM)
    assert file_hashes(tmp_path) == before
    assert plans[0].planned[ITEM][OLD].changed
    phases.write_roots(plans)
    assert csv.read_bytes() == csv_bytes
    written = file_hashes(tmp_path)
    fresh = plan_named_roots([root], ITEM)
    assert not fresh[0].planned[ITEM][OLD].changed
    assert phases.verify_roots(fresh)[0][1].days == 1
    phases.write_roots(fresh)
    assert file_hashes(tmp_path) == written
    (file,) = ledger.read_day_files(root, ITEM, OLD)
    identity = file.envelope.identity
    assert identity == writer_identity(RUN, SEED_COMMIT)
    assert read_back(root, ITEM, OLD) == by_key(ITEM, [row.csv_row()])
    phases.retire_roots(
        MigrationInputs(
            state_dirs=[root],
            which=[ITEM],
            run_id=RUN,
            git_sha=SEED_COMMIT,
            today=TODAY,
            months=MONTHS,
        )
    )
    assert not csv.exists()


@pytest.mark.parametrize("damage", ["missing", "changed", "unreadable"])
def test_verify_and_retire_refuse_output_without_deleting_any_root(
    tmp_path: Path, damage: str
) -> None:
    roots = [tmp_path / "trial-a", tmp_path / "trial-b"]
    row = item_row(OLD, "ai-01", machine=True)
    sources = [
        write_csv(root, ITEM, OLD, writer_file_name(OLD, 1, ServerJob.WORK), [row.csv_row()]) for root in roots
    ]
    phases.write_roots(plan_named_roots(roots, ITEM))
    (file,) = ledger.read_day_files(roots[-1], ITEM, OLD)
    if damage == "missing":
        file.path.unlink()
    elif damage == "unreadable":
        file.path.write_bytes(b"not a ledger")
    else:
        assert row.source_words is not None
        ledger.persist(
            roots[-1],
            [row.model_copy(update={"source_words": row.source_words + 1})],
            ledger=ITEM,
            covers=OLD,
            identity=writer_identity(RUN, SEED_COMMIT),
        )
    before = file_hashes(tmp_path)
    with pytest.raises(refusals.NotProvenError, match=rf"{ITEM.value} {OLD}"):
        phases.verify_roots(plan_named_roots(roots, ITEM))
    with pytest.raises(refusals.NotProvenError, match=rf"{ITEM.value} {OLD}"):
        phases.retire_roots(
            MigrationInputs(
                state_dirs=roots,
                which=[ITEM],
                run_id=RUN,
                git_sha=SEED_COMMIT,
                today=TODAY,
                months=MONTHS,
            )
        )
    assert file_hashes(tmp_path) == before
    assert all(path.exists() for path in sources)


def test_retire_replans_after_a_successful_proof_before_deleting_any_root(tmp_path: Path) -> None:
    roots = [tmp_path / "trial-a", tmp_path / "trial-b"]
    row = item_row(OLD, "ai-01", machine=True)
    for root in roots:
        write_csv(root, ITEM, OLD, writer_file_name(OLD, 1, ServerJob.WORK), [row.csv_row()])
    phases.write_roots(plan_named_roots(roots, ITEM))
    phases.verify_roots(plan_named_roots(roots, ITEM))
    write_csv(
        roots[-1],
        ITEM,
        OLD,
        writer_file_name(OLD, 2, ServerJob.WORK),
        [item_row(OLD, "ai-02", machine=True).csv_row()],
    )
    before = file_hashes(tmp_path)
    with pytest.raises(refusals.NotProvenError, match="missing"):
        phases.retire_roots(
            MigrationInputs(
                state_dirs=roots,
                which=[ITEM],
                run_id=RUN,
                git_sha=SEED_COMMIT,
                today=TODAY,
                months=MONTHS,
            )
        )
    assert file_hashes(tmp_path) == before


def test_a_late_write_converges_rows_and_work_identity_without_deleting_csv(tmp_path: Path) -> None:
    root = tmp_path / "trial"
    row = item_row(OLD, "ai-01", machine=True)
    write_csv(root, ITEM, OLD, writer_file_name(OLD, 1, ServerJob.WORK), [row.csv_row()])
    phases.write_roots(plan_named_roots([root], ITEM))
    (first,) = ledger.read_day_files(root, ITEM, OLD)
    later = item_row(OLD, "ai-02", machine=True)
    write_csv(root, ITEM, OLD, writer_file_name(OLD, 2, ServerJob.WORK), [later.csv_row()])
    phases.write_roots(plan_named_roots([root], ITEM))
    phases.verify_roots(plan_named_roots([root], ITEM))
    written = file_hashes(tmp_path)
    phases.write_roots(plan_named_roots([root], ITEM))
    assert file_hashes(tmp_path) == written
    assert {file.envelope.unit_id for file in ledger.read_day_files(root, ITEM, OLD)} == {
        first.envelope.unit_id
    }
    assert read_back(root, ITEM, OLD) == by_key(ITEM, [row.csv_row(), later.csv_row()])
    assert len(csv_files.left(root, [ITEM], months=MONTHS)) == 2
